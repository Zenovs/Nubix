"""
rclone engine — the only module that spawns rclone subprocesses.

RcloneEngine manages the rclone binary and creates RcloneProcess instances.
RcloneProcess owns the subprocess and emits Qt signals from reader threads.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from nubix.constants import BISYNC_STATE_FILE, RCLONE_BINARY, RCLONE_CONFIG_FILE
from nubix.core.rclone_parser import parse_error_line, parse_progress_line
from nubix.core.sync_job import SyncJob, SyncMode, TransferStats
from nubix.exceptions import RcloneExecutionError, RcloneNotFoundError

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

    def _on_stderr(self, line: str):
        # Detect the specific bisync "listing files missing" critical error immediately
        # so the state can be reset before the process even finishes.
        if _BISYNC_MISSING_LISTINGS in line:
            logger.warning("Bisync listing files missing — resync required: %s", self.job_id)
            self.resync_required.emit()

        err = parse_error_line(line)
        if err:
            self.error_occurred.emit(err.message)
        else:
            # Also try to parse stats from stderr (rclone sometimes writes stats there)
            stats = parse_progress_line(line)
            if stats:
                self.progress_updated.emit(stats)

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

    def _is_bisync_initialized(self, remote_id: str) -> bool:
        """Return True if bisync has been successfully run once for this remote.

        Also verifies that rclone's listing files actually exist in its cache dir.
        If the cache is empty (e.g. after a system clean), forces --resync even if
        our state file claims the remote is already initialized.
        """
        try:
            data = json.loads(BISYNC_STATE_FILE.read_text())
            if not data.get(remote_id):
                return False
        except Exception:
            return False

        # Belt-and-suspenders: if rclone's bisync cache has no listing files at all,
        # the state in our file is stale — force a resync to rebuild them.
        bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"
        if not bisync_cache.exists() or not any(bisync_cache.rglob("*.lst")):
            logger.info(
                "rclone bisync listing files missing from cache — forcing --resync for %s",
                remote_id,
            )
            self._reset_bisync_initialized(remote_id)
            return False

        return True

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

    def start_sync(self, job: SyncJob) -> RcloneProcess:
        """Build rclone command and launch a sync subprocess."""
        is_first_bisync = not self._is_bisync_initialized(job.remote_id)
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

        def _on_bisync_finished(code: int, remote_id: str = rid) -> None:
            if code == 0:
                self._mark_bisync_initialized(remote_id)
            else:
                # Any failure: reset state so next run uses --resync.
                self._reset_bisync_initialized(remote_id)

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

        # Google Drive-specific: skip native Docs/Sheets/Slides (not downloadable)
        if job.provider_type == "gdrive":
            cmd += ["--drive-skip-gdocs"]

        # First-time bisync: establish baseline without conflict errors
        if resync:
            cmd += ["--resync"]

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
