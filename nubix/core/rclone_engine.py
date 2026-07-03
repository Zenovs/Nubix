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
    # Deliberately NOT named "finished": that would shadow QThread.finished
    # (the thread-lifecycle signal) and this one fires from inside run(),
    # i.e. before the thread has actually terminated.
    eof_reached = Signal()

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
            self.eof_reached.emit()


# rclone bisync emits this string when its listing files are missing.
# It means --resync is required to rebuild the baseline.
_BISYNC_MISSING_LISTINGS = "cannot find prior Path1 or Path2 listings"

# rclone bisync safety check: aborts when >50% of local files would be deleted.
# This happens when the local folder is out of sync with the recorded baseline
# (e.g. sync was interrupted mid-download). Resetting the baseline fixes it.
_BISYNC_TOO_MANY_DELETES = "too many deletes"

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
        self._stdout_reader.eof_reached.connect(self._on_reader_done)
        self._stderr_reader.eof_reached.connect(self._on_reader_done)

        self._stdout_reader.start()
        self._stderr_reader.start()

    def _on_stdout(self, line: str):
        stats = parse_progress_line(line)
        if stats:
            self.progress_updated.emit(stats)
            if stats.current_file:
                self.file_transferred.emit(stats.current_file)

    def _on_stderr(self, line: str):
        # Detect bisync errors that require a fresh --resync baseline immediately,
        # before the process finishes, so the very next run rebuilds correctly.
        if _BISYNC_MISSING_LISTINGS in line:
            logger.warning("Bisync listing files missing — resync required: %s", self.job_id)
            self.resync_required.emit()
        if _BISYNC_TOO_MANY_DELETES in line:
            logger.warning("Bisync too-many-deletes safety stop — resync required: %s", self.job_id)
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
                # Log plain-text (non-JSON) stderr lines — these are unusual and
                # often indicate errors that the JSON parser missed.
                if not line.startswith("{"):
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
        # A SIGSTOPped process queues SIGTERM until it is resumed — without
        # SIGCONT a paused job would survive as a frozen orphan forever.
        try:
            os.kill(self._process.pid, signal.SIGCONT)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            self._process.terminate()
        except ProcessLookupError:
            pass

    def kill(self):
        """Force-kill the process."""
        try:
            os.kill(self._process.pid, signal.SIGCONT)
        except (ProcessLookupError, PermissionError):
            pass
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
        try:
            result = subprocess.run(
                [self._binary, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("rclone version check failed: %s", e)
            return "unknown"
        return result.stdout.splitlines()[0] if result.stdout else "unknown"

    def list_remotes(self) -> list[str]:
        """Return list of configured remote names from rclone config."""
        try:
            result = subprocess.run(
                [self._binary, "listremotes", "--config", str(RCLONE_CONFIG_FILE)],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("rclone listremotes failed: %s", e)
            return []
        # Only lines ending with ":" are valid remote names; any other output
        # (warnings, errors) is silently discarded.
        return [r.rstrip(":") for r in result.stdout.splitlines() if r.strip().endswith(":")]

    def list_remote_dirs(self, remote_id: str, remote_path: str = "") -> list[dict]:
        """List directories at a remote path. Returns list of {name, is_dir} dicts."""
        path = f"{remote_id}:{remote_path}"
        try:
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
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("lsjson failed for %s: %s", path, e)
            return []
        if result.returncode != 0:
            logger.warning("lsjson failed: %s", result.stderr)
            return []
        try:
            return json.loads(result.stdout) or []
        except Exception:
            return []

    def _obscure(self, value: str) -> Optional[str]:
        """Obscure a password with `rclone obscure`, fed via stdin (not argv)."""
        try:
            result = subprocess.run(
                [self._binary, "obscure", "-"],
                input=value,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("rclone obscure failed: %s", e)
            return None
        if result.returncode != 0:
            logger.error("rclone obscure failed with code %d", result.returncode)
            return None
        return result.stdout.strip()

    def configure_remote(self, remote_id: str, config_args: list[str]) -> bool:
        """
        Configure a new rclone remote.
        config_args is a flat list: [backend_type, key1, value1, key2, value2, …]

        The section is written directly into Nubix's rclone config file
        instead of shelling out to `rclone config create` — command-line
        arguments are world-readable via /proc/<pid>/cmdline, so passing
        passwords or tokens through argv would leak them to every local
        process for the lifetime of the subprocess.
        """
        import configparser
        import tempfile

        if not config_args:
            return False
        remote_type, *rest = config_args
        if len(rest) % 2 != 0:
            logger.error("configure_remote: malformed key/value list for %s", remote_id)
            return False
        options = dict(zip(rest[::2], rest[1::2]))

        # Obscure password-type fields, matching `rclone config create --obscure`.
        # "pass" is the only password-type key the provider registry emits.
        if options.get("pass"):
            obscured = self._obscure(options["pass"])
            if obscured is None:
                return False
            options["pass"] = obscured

        parser = configparser.ConfigParser(interpolation=None)
        try:
            if RCLONE_CONFIG_FILE.exists():
                parser.read(RCLONE_CONFIG_FILE)
        except Exception as e:
            logger.error("Could not read rclone config: %s", e)
            return False

        parser[remote_id] = {"type": remote_type, **options}

        try:
            RCLONE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=RCLONE_CONFIG_FILE.parent, prefix=".rclone-conf-")
            try:
                with os.fdopen(fd, "w") as f:
                    parser.write(f)
                os.chmod(tmp, 0o600)
                os.replace(tmp, RCLONE_CONFIG_FILE)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error("Could not write rclone config: %s", e)
            return False
        logger.info("Configured remote %s (type %s)", remote_id, remote_type)
        return True

    def delete_remote(self, remote_id: str) -> bool:
        """Remove a remote from rclone config."""
        try:
            result = subprocess.run(
                [self._binary, "config", "delete", remote_id, "--config", str(RCLONE_CONFIG_FILE)],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("rclone config delete failed: %s", e)
            return False
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

        # rclone bisync stores listing files as {safe_p1}..{safe_p2}.path1.lst
        # where safe = replace /\: with _ and strip only leading _.
        p2_safe = re.sub(r"[/\\:]", "_", f"{job.remote_id}:{job.remote_path}").lstrip("_")
        bisync_cache = Path.home() / ".cache" / "rclone" / "bisync"

        if not bisync_cache.exists() or not any(bisync_cache.rglob(f"*..{p2_safe}.path1.lst")):
            logger.info("rclone bisync listing missing for %s — forcing --resync", job.remote_id)
            self._reset_bisync_initialized(job.remote_id)
            return False

        return True

    def _supports_resync_acknowledged(self) -> bool:
        """Return True if this rclone build supports --resync-acknowledged.

        Uses help-text probing — the only reliable method because distro
        packages (e.g. Kali/Debian) may report a high version number while
        still omitting flags that upstream added in that release.
        """
        if self._resync_ack is None:
            try:
                h = subprocess.run(
                    [self._binary, "help", "bisync"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self._resync_ack = "--resync-acknowledged" in (h.stdout + h.stderr)
                logger.debug("--resync-acknowledged supported: %s", self._resync_ack)
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

    def _clear_bisync_lock(self, job: SyncJob) -> None:
        """Delete a stale bisync lock file if one exists.

        rclone bisync creates a lock file at the start of each run and removes it
        when done.  If the process is killed mid-run the lock file remains and
        prevents every subsequent run from starting (exit code 1).

        Lock file naming: {safe_p1}..{safe_p2}.lck
        safe = replace /\\: with _ then strip leading _.
        """
        p1_safe = re.sub(r"[/\\:]", "_", str(job.local_path)).lstrip("_")
        p2_safe = re.sub(r"[/\\:]", "_", f"{job.remote_id}:{job.remote_path}").lstrip("_")
        lock_file = Path.home() / ".cache" / "rclone" / "bisync" / f"{p1_safe}..{p2_safe}.lck"
        if lock_file.exists():
            try:
                lock_file.unlink()
                logger.info("Removed stale bisync lock file for %s", job.remote_id)
            except OSError as e:
                logger.warning("Could not remove bisync lock file %s: %s", lock_file, e)

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

        # Remove any stale lock file left by a previously killed bisync run.
        self._clear_bisync_lock(job)

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
            "--stats=5s",
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

    def start_mount(
        self,
        remote_id: str,
        remote_path: str,
        mountpoint: Path,
        cache_mode: str = "full",
        cache_size: str = "1G",
    ) -> subprocess.Popen:
        """Launch rclone mount as a foreground subprocess (caller manages its lifetime)."""
        try:
            mountpoint.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise PermissionError(
                f"Cannot create mount directory '{mountpoint}'.\n"
                "Please choose a path inside your home folder, e.g.:\n"
                f"  {Path.home() / 'mnt' / mountpoint.name}"
            )
        remote_src = f"{remote_id}:{remote_path}"
        cmd = [
            self._binary,
            "mount",
            remote_src,
            str(mountpoint),
            "--config",
            str(RCLONE_CONFIG_FILE),
            "--vfs-cache-mode",
            cache_mode,
            "--vfs-cache-max-size",
            cache_size,
            "--allow-non-empty",
            "--log-level=ERROR",
            "--timeout=30s",
            "--contimeout=15s",
            "--dir-cache-time=5m",
            "--tpslimit=4",
            "--vfs-cache-poll-interval=5m",
        ]
        logger.info("Starting mount %s → %s: %s", remote_src, mountpoint, " ".join(cmd))
        # stdout/stderr must be discarded — piping them without a reader causes the 64 KB
        # pipe buffer to fill, which blocks rclone on write() and stalls all FUSE operations.
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def unmount(self, mountpoint: Path) -> bool:
        """Unmount a FUSE mountpoint using fusermount3 / fusermount."""
        for binary in ("fusermount3", "fusermount"):
            found = shutil.which(binary)
            if not found:
                continue
            try:
                result = subprocess.run(
                    [found, "-u", str(mountpoint)],
                    capture_output=True,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.warning("%s -u %s failed: %s", binary, mountpoint, e)
                continue
            if result.returncode == 0:
                logger.info("Unmounted %s via %s", mountpoint, binary)
                return True
        logger.warning("Could not unmount %s — fusermount3/fusermount not found", mountpoint)
        return False
