"""
Sync scheduler — runs sync jobs within configured time windows.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from nubix.core.sync_job import SyncJob, TimeWindow
from nubix.exceptions import SchedulerConflictError

logger = logging.getLogger(__name__)


def _windows_overlap(windows: list[TimeWindow]) -> bool:
    for i, w1 in enumerate(windows):
        for w2 in windows[i + 1:]:
            if w1.overlaps(w2):
                return True
    return False


def _is_in_window(windows: list[TimeWindow]) -> bool:
    """Return True if the current time falls inside any of the given windows."""
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday
    current_time = now.time()
    for w in windows:
        if weekday in w.days and w.start_time <= current_time <= w.end_time:
            return True
    return False


def _next_window_start(windows: list[TimeWindow]) -> Optional[datetime]:
    """Return the next datetime when a window starts."""
    now = datetime.now()
    weekday = now.weekday()
    current_time = now.time()

    candidates = []
    for w in windows:
        for day_offset in range(8):  # look 7 days ahead
            day = (weekday + day_offset) % 7
            if day in w.days:
                candidate = now.replace(
                    hour=w.start_time.hour,
                    minute=w.start_time.minute,
                    second=0,
                    microsecond=0,
                )
                if day_offset > 0:
                    from datetime import timedelta
                    candidate += timedelta(days=day_offset)
                if candidate > now:
                    candidates.append(candidate)

    return min(candidates) if candidates else None


class Scheduler(QObject):
    """Checks schedule windows every minute and triggers sync jobs."""

    trigger_start = Signal(str)   # job_id — start this job
    trigger_stop = Signal(str)    # job_id — stop this job

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._jobs: dict[str, SyncJob] = {}   # job_id -> SyncJob
        self._was_in_window: dict[str, bool] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(60_000)  # check every minute
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start()
        self._tick()  # immediate check on start

    def stop(self):
        self._timer.stop()

    def add_job(self, job: SyncJob) -> None:
        if not job.is_scheduled or not job.schedule_windows:
            return
        if _windows_overlap(job.schedule_windows):
            raise SchedulerConflictError(job.job_id)
        self._jobs[job.job_id] = job
        self._was_in_window[job.job_id] = False
        logger.debug("Scheduler registered job %s", job.job_id)

    def remove_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        self._was_in_window.pop(job_id, None)

    def update_job(self, job: SyncJob) -> None:
        self.remove_job(job.job_id)
        self.add_job(job)

    def get_next_run(self, job_id: str) -> Optional[datetime]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        return _next_window_start(job.schedule_windows)

    def _tick(self):
        for job_id, job in list(self._jobs.items()):
            in_window = _is_in_window(job.schedule_windows)
            was = self._was_in_window.get(job_id, False)

            if in_window and not was:
                logger.info("Scheduler: starting job %s (window opened)", job_id)
                self.trigger_start.emit(job_id)
            elif not in_window and was:
                logger.info("Scheduler: stopping job %s (window closed)", job_id)
                self.trigger_stop.emit(job_id)

            self._was_in_window[job_id] = in_window
