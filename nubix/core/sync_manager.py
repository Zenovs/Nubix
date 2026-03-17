"""
SyncManager — owns and coordinates all active RcloneProcess instances.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal

from nubix.core.rclone_engine import RcloneEngine, RcloneProcess
from nubix.core.sync_job import JobStatus, SyncJob, TransferStats

logger = logging.getLogger(__name__)


class SyncManager(QObject):
    """Manages active sync jobs and aggregates their signals."""

    # Aggregated signals
    job_started = Signal(str)                   # job_id
    job_finished = Signal(str, int)             # job_id, exit_code
    job_failed = Signal(str, str)               # job_id, error_message
    job_status_changed = Signal(str, str)       # job_id, JobStatus value
    progress_updated = Signal(str, object)      # job_id, TransferStats
    file_transferred = Signal(str, str)         # job_id, filename
    any_job_active = Signal(bool)               # True if any job is running

    def __init__(self, engine: RcloneEngine, parent: QObject | None = None):
        super().__init__(parent)
        self._engine = engine
        self._processes: dict[str, RcloneProcess] = {}
        self._statuses: dict[str, JobStatus] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_job(self, job: SyncJob) -> None:
        """Start a sync job. Does nothing if already running."""
        if self._is_active(job.job_id):
            logger.debug("Job %s already running", job.job_id)
            return
        try:
            process = self._engine.start_sync(job)
            self._processes[job.job_id] = process
            self._set_status(job.job_id, JobStatus.SYNCING)

            process.progress_updated.connect(
                lambda stats, jid=job.job_id: self._on_progress(jid, stats)
            )
            process.file_transferred.connect(
                lambda fname, jid=job.job_id: self.file_transferred.emit(jid, fname)
            )
            process.error_occurred.connect(
                lambda msg, jid=job.job_id: self._on_error(jid, msg)
            )
            process.finished.connect(
                lambda code, jid=job.job_id: self._on_finished(jid, code)
            )

            self.job_started.emit(job.job_id)
            self._emit_any_active()
        except Exception as e:
            logger.error("Failed to start job %s: %s", job.job_id, e)
            self._set_status(job.job_id, JobStatus.ERROR)
            self.job_failed.emit(job.job_id, str(e))

    def stop_job(self, job_id: str) -> None:
        """Stop a running job."""
        proc = self._processes.get(job_id)
        if proc:
            proc.stop()
            self._set_status(job_id, JobStatus.IDLE)

    def pause_job(self, job_id: str) -> None:
        """Pause a running job (SIGSTOP)."""
        proc = self._processes.get(job_id)
        if proc:
            proc.pause()
            self._set_status(job_id, JobStatus.PAUSED)

    def resume_job(self, job_id: str) -> None:
        """Resume a paused job (SIGCONT)."""
        proc = self._processes.get(job_id)
        if proc:
            proc.resume()
            self._set_status(job_id, JobStatus.SYNCING)

    def stop_all(self) -> None:
        """Stop all active jobs."""
        for job_id in list(self._processes.keys()):
            self.stop_job(job_id)

    def get_status(self, job_id: str) -> JobStatus:
        return self._statuses.get(job_id, JobStatus.IDLE)

    def active_job_ids(self) -> list[str]:
        return [
            jid
            for jid, status in self._statuses.items()
            if status == JobStatus.SYNCING
        ]

    def is_any_active(self) -> bool:
        return len(self.active_job_ids()) > 0

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _is_active(self, job_id: str) -> bool:
        return self._statuses.get(job_id) == JobStatus.SYNCING

    def _set_status(self, job_id: str, status: JobStatus) -> None:
        self._statuses[job_id] = status
        self.job_status_changed.emit(job_id, status.value)

    def _on_progress(self, job_id: str, stats: TransferStats) -> None:
        self.progress_updated.emit(job_id, stats)

    def _on_error(self, job_id: str, msg: str) -> None:
        logger.warning("Job %s error: %s", job_id, msg)
        self.job_failed.emit(job_id, msg)

    def _on_finished(self, job_id: str, exit_code: int) -> None:
        self._processes.pop(job_id, None)
        if exit_code == 0:
            self._set_status(job_id, JobStatus.UP_TO_DATE)
        else:
            self._set_status(job_id, JobStatus.ERROR)
        self.job_finished.emit(job_id, exit_code)
        self._emit_any_active()

    def _emit_any_active(self) -> None:
        self.any_job_active.emit(self.is_any_active())
