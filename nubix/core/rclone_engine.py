"""
rclone engine — the only module that spawns rclone subprocesses.

RcloneEngine manages the rclone binary and creates RcloneProcess instances.
RcloneProcess owns the subprocess and emits Qt signals from reader threads.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from nubix.constants import BISYNC_STATE_FILE, RCLONE_BINARY, RCLONE_CONFIG_FILE
from nubix.core.rclone_parser import parse_error_line, parse_progress_line
from nubix.core.sync_job import SyncJob, SyncMode, TransferStats
from nubix.exceptions import RcloneExecutionError, RcloneNotFoundError, RemoteNotConfiguredError

logger = logging.getLogger(__name__)


class _ReaderThread(QThread):
    """Reads lines from a subprocess stream and emits them as signals."""

    line_received = Signal(str)
    finished = Signal()

    def __init__(self, stream, parent=None):
        super().__init__(parent)
        self._stream = stream

    def run(self):
        try:
            for raw in self._stream:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self.line_received.emit(line)
        except Exception as e:
            logger.debug("Reader thread error: %s", e)
        finally:
            self.finished.emit()


# rclone bisync emits this string when its listing files are missing.
# It means --resync is required to rebuild the baseline.
_BISYNC_MISSING_LISTINGS = "cannot find prior Path1 or Path2 listings"

# rclone ≥ 1.64 outputs this when --resync is used without --resync-acknowledged.
# It appears at NOTICE level so parse_error_line() misses it — check the raw line.
_BISYNC_NEEDS_ACK = "resync-acknowledged"


class RcloneProcess(QObject):
    """
    Wraps a running rclone subprocess.

    Emits:
        progress_updated(TransferStats)
        file_transferred(str)
        error_occurred(str)
        finished(int)  — exit code
        resync_required()  — bisync listing files missing, next run needs --resync
    """

    progress_updated = Signal(object)  # TransferStats
    file_transferred = Signal(str)  # filename
    error_occurred = Signal(str)  # human-readable error
    finished = Signal(int)  # exit code
    resync_required = Signal()  # bisync listing files are missing
    resync_ack_required = Signal()  # rclone needs --resync-acknowledged (v1.64+)

    def __init__(self, process: subprocess.Popen, job_id: str, parent: QObject | None = None):
        super().__init__(parent)
        self._process = process
        self.job_id = job_id
        self._stdout_reader = _ReaderThread(process.stdout, self)
        self._stderr_reader = _ReaderThread(process.stderr, self)

        self._stdout_reader.line_received.connect(self._on_stdout)
        self._stderr_reader.line_received.connect(self._on_stderr)

        # Track when both readers are done before emitting finished
        self._readers_done = 0
        self._stdout_reader.finished.connect(self._on_reader_done)
        self._stderr_reader.finished.connect(self._on_reader_done)

        self._stdout_reader.start()
        self._stderr_reader.start()

    def _on_stdout(self, line: str):
        stats = parse_progress_line(line)
        if stats:
            self.progress_updated.emit(stats)
            if stats.current_file:
                self.file_transferred.emit(stats.current_file)
        else:
            logger.debug("rclone stdout [%s]: %s", self.job_id, line)

    def _on_stderr(self, line: str):
        # Detect the specific bisync "listing files missing" critical error immediately
        # so the state can be reset before the process even finishes.
        if _BISYNC_MISSING_LISTINGS in line:
            logger.warning("Bisync listing files missing — resync required: %s", self.job_id)
            self.resync_required.emit()

        # rclone ≥ 1.64 outputs a NOTICE (not ERROR) when --resync-acknowledged is
        # missing — parse_error_line() misses NOTICE level, so check the raw line.
        if _BISYNC_NEEDS_ACK in line:
            logger.info("rclone requires --resync-acknowledged — will add it on next run")
            self.resync_ack_required.emit()

        err = parse_error_line(line)
        if err:
            self.error_occurred.emit(err.message)
        else:
            # Also try to parse stats from stderr (rclone sometimes writes stats there)
            stats = parse_progress_line(line)
            if stats:
                self.progress_updated.emit(stats)
            else:
                # Log unrecognised stderr lines so failures are visible in the log
                logger.debug("rclone stderr [%s]: %s", self.job_id, line)

    def _on_reader_done(self):
        self._readers_done += 1
        if self._readers_done >= 2:
            exit_code = self._process.wait()
            logger.debug("rclone process %s exited with code %d", self.job_id, exit_code)
            self.finished.emit(exit_code)

    def pause(self):
        """Send SIGSTOP to pause the process."""
        try:
            os.kill(self._process.pid, signal.SIGSTOP)
        except ProcessLookupError:
            pass

    def resume(self):
        """Send SIGCONT to resume a paused process."""
        try:
            os.kill(self._process.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass

    def stop(self):
        """Terminate the process gracefully."""
        try:
            self._process.terminate()
        except ProcessLookupError:
            pass

    def kill(self):
        """Force-kill the process."""
        try:
            self._process.kill()
        except ProcessLookupError:
            pass

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid


class RcloneEngine(QObject):
    """Manages the rclone binary and creates RcloneProcess instances."""

    def __init__(self, binary_override: str = "", parent: QObject | None = None):
        super().__init__(parent)
        self._binary = self._resolve_binary(binary_override)
        self._resync_ack: Optional[bool] = None  # cached per-process lifetime

    def _resolve_binary(self, override: str) -> str:
        if override and Path(override).is_file():
            return override
        found = shutil.which(RCLONE_BINARY)
        if not found:
            raise RcloneNotFoundError()
        return found

    def check_version(self) -> str:
        """Return rclone version string."""
        result = subprocess.run(
            [self._binary, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.splitlines()[0] if result.stdout else "unknown"

    def list_remotes(self) -> list[str]:
        """Return list of configured remote names from rclone config."""
        result = subprocess.run(
            [self._binary, "listremotes", "--config", str(RCLONE_CONFIG_FILE)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return [r.rstrip(":") for r in result.stdout.splitlines() if r.strip()]

    def list_remote_dirs(self, remote_id: str, remote_path: str = "") -> list[dict]:
        """List directories at a remote path. Returns list of {name, is_dir} dicts."""
        path = f"{remote_id}:{remote_path}"
        result = subprocess.run(
            [
                self._binary,
                "lsjson",
                "--config",
                str(RCLONE_CONFIG_FILE),
                "--dirs-only",
                "--no-modtime",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("lsjson failed: %s", result.stderr)
            return []
        try:
            return json.loads(result.stdout) or []
        except Exception:
            return []

    def configure_remote(self, remote_id: str, config_args: list[str]) -> bool:
        """
        Configure a new rclone remote using rclone config create.
        config_args example: ["gdrive", "--drive-client-id", "xxx", ...]
        """
        cmd = [
            self._binary,
            "config",
            "create",
            remote_id,
            *config_args,
            "--config",
            str(RCLONE_CONFIG_FILE),
            "--non-interactive",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error("rclone config create failed: %s", result.stderr)
            return False
        return True

    def delete_remote(self, remote_id: str) -> bool:
        """Remove a remote from rclone config."""
        result = subprocess.run(
            [self._binary, "config", "delete", remote_id, "--config", str(RCLONE_CONFIG_FILE)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0

    # ------------------------------------------------------------------
    # Bisync first-run state tracking
    # ------------------------------------------------------------------

    def _is_bisync_initialized(self, job: SyncJob) -> bool:
        """Return True if bisync has been successfully run once for this job.

        Checks for the specific listing files for this job (not just any listing
        file) so that each remote is evaluated independently.
        """
        try:
            data = json.loads(BISYNC_STATE_FILE.read_text())
            if not data.get(job.remote_id):
                return False
        except Exception:
            return False

        # rclone bisync stores listing files as {safe_p1}--{safe_p2}.path1.lst
        # where safe = replace /\: with _ and strip leading/trailing _.
        p2_safe = re.sub(r"[/\\:]", "_", f"{job.remote_id}:{job.remote_path}").strip("_")
        bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"

        if not bisync_cache.exists() or not any(bisync_cache.rglob(f"*--{p2_safe}.path1.lst")):
            logger.info("rclone bisync listing missing for %s — forcing --resync", job.remote_id)
            self._reset_bisync_initialized(job.remote_id)
            return False

        return True

    def _supports_resync_acknowledged(self) -> bool:
        """Return True if this rclone supports --resync-acknowledged (v1.64+).

        Detects via version number — more reliable than help-text parsing because
        rclone prints 'help bisync' to stderr on some builds/platforms.
        """
        if self._resync_ack is None:
            try:
                result = subprocess.run(
                    [self._binary, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                m = re.search(r"rclone v(\d+)\.(\d+)", result.stdout)
                if m:
                    major, minor = int(m.group(1)), int(m.group(2))
                    self._resync_ack = (major, minor) >= (1, 64)
                    logger.debug(
                        "rclone version %d.%d — --resync-acknowledged supported: %s",
                        major,
                        minor,
                        self._resync_ack,
                    )
                else:
                    logger.debug("Could not parse rclone version from: %r", result.stdout[:80])
                    # Fallback: scan both stdout and stderr of 'help bisync'
                    h = subprocess.run(
                        [self._binary, "help", "bisync"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self._resync_ack = "--resync-acknowledged" in (h.stdout + h.stderr)
            except Exception:
                self._resync_ack = False
        return bool(self._resync_ack)

    def _mark_bisync_initialized(self, remote_id: str) -> None:
        """Persist that bisync is initialized for this remote."""
        try:
            try:
                data = json.loads(BISYNC_STATE_FILE.read_text())
            except Exception:
                data = {}
            data[remote_id] = True
            BISYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            BISYNC_STATE_FILE.write_text(json.dumps(data))
        except Exception as e:
            logger.warning("Could not write bisync state: %s", e)

    def _reset_bisync_initialized(self, remote_id: str) -> None:
        """Clear the initialized flag so the next run uses --resync to rebuild listings."""
        try:
            try:
                data = json.loads(BISYNC_STATE_FILE.read_text())
            except Exception:
                data = {}
            data.pop(remote_id, None)
            BISYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            BISYNC_STATE_FILE.write_text(json.dumps(data))
            logger.info("Bisync state reset for %s — next run will use --resync", remote_id)
        except Exception as e:
            logger.warning("Could not reset bisync state: %s", e)

    # ------------------------------------------------------------------

    def _remote_in_config(self, remote_id: str) -> bool:
        """Return True if remote_id exists in Nubix's rclone config file."""
        try:
            result = subprocess.run(
                [self._binary, "config", "show", remote_id, "--config", str(RCLONE_CONFIG_FILE)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "type" in result.stdout
        except Exception:
            return True  # assume present; let rclone fail with the real error

    def start_sync(self, job: SyncJob) -> RcloneProcess:
        """Build rclone command and launch a sync subprocess."""
        # Ensure local directory exists — bisync requires both paths to be present.
        try:
            job.local_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("Could not create local sync directory %s: %s", job.local_path, e)
        if not job.local_path.exists():
            # Check whether the failure is due to a missing mount point (external drive).
            # Walk up to find the first ancestor that does not exist.
            missing = job.local_path
            for parent in job.local_path.parents:
                if not parent.exists():
                    missing = parent
                else:
                    break
            if str(missing).startswith("/media/") or str(missing).startswith("/mnt/"):
                raise OSError(
                    f"Sync path not accessible: {job.local_path}\n"
                    f"The drive or mount point '{missing}' is not mounted. "
                    f"Please plug in the drive and try again, or change the sync path in Settings."
                )
            raise OSError(
                f"Local sync directory does not exist and could not be created: {job.local_path}"
            )

        # Check that the remote is actually configured — gives a clear error instead
        # of rclone's cryptic "error listing: directory not found".
        if not self._remote_in_config(job.remote_id):
            raise RemoteNotConfiguredError(job.remote_id)

        is_first_bisync = not self._is_bisync_initialized(job)
        cmd = self._build_command(job, resync=is_first_bisync)
        logger.info("Starting sync job %s: %s", job.job_id, " ".join(cmd))

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        rclone_proc = RcloneProcess(process, job.job_id)

        rid = job.remote_id

        # Reset state immediately when the "listing files missing" error is detected
        # in the rclone output — this way the very next sync attempt will use --resync
        # without waiting for the process to finish first.
        rclone_proc.resync_required.connect(lambda r=rid: self._reset_bisync_initialized(r))

        # If rclone tells us --resync-acknowledged is required, cache that so the
        # very next sync attempt adds the flag automatically.
        rclone_proc.resync_ack_required.connect(lambda: setattr(self, "_resync_ack", True))

        def _on_bisync_finished(code: int, remote_id: str = rid) -> None:
            if code == 0:
                self._mark_bisync_initialized(remote_id)
            elif code == 2:
                # Exit code 2 = bisync critical error (e.g. listing files missing,
                # conflict detected). Reset so next run uses --resync to rebuild.
                self._reset_bisync_initialized(remote_id)
            # Transient errors (network timeout, exit code 1) do NOT reset state —
            # the existing listings are still valid; forcing --resync would be wasteful.

        rclone_proc.finished.connect(_on_bisync_finished)

        return rclone_proc

    def _build_command(self, job: SyncJob, resync: bool = False) -> list[str]:
        remote_src = f"{job.remote_id}:{job.remote_path}"
        local_dst = str(job.local_path)

        # All modes use bisync so that local changes are also uploaded to the cloud.
        # path1 = local, path2 = remote (bisync convention)
        subcmd = "bisync"
        src, dst = local_dst, remote_src

        cmd = [
            self._binary,
            subcmd,
            src,
            dst,
            "--config",
            str(RCLONE_CONFIG_FILE),
            "--stats=1s",
            "--stats-one-line",
            "--use-json-log",
            "--log-level=INFO",
        ]

        # Google Drive-specific: skip native Docs/Sheets/Slides (not downloadable).
        # provider_type is stored as the rclone backend name ("drive") from the
        # provider registry, but may also be the legacy Nubix id "gdrive".
        if job.provider_type in ("drive", "gdrive"):
            cmd += ["--drive-skip-gdocs"]

        # First-time bisync: establish baseline without conflict errors.
        # rclone ≥ 1.64 requires --resync-acknowledged alongside --resync.
        if resync:
            cmd += ["--resync"]
            if self._supports_resync_acknowledged():
                cmd += ["--resync-acknowledged"]

        # Bandwidth limit
        if job.bandwidth_limit and job.bandwidth_limit != "0":
            cmd += ["--bwlimit", job.bandwidth_limit]

        # Selective sync filters
        for f in job.filters:
            cmd += ["--filter", f]

        return cmd

    def set_bandwidth_limit(self, limit: str) -> bool:
        """Set bandwidth limit via rclone RC (requires --rc to be running)."""
        try:
            import requests

            resp = requests.post(
                "http://localhost:5572/core/bwlimit",
                json={"rate": limit},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False
