"""Tests for SyncManager job lifecycle (pause/stop/double-start guards)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nubix.core.sync_job import JobStatus, SyncJob
from nubix.core.sync_manager import SyncManager


@pytest.fixture
def job():
    return SyncJob(
        remote_id="test_remote",
        provider_type="drive",
        local_path=Path("/tmp/nubix-test"),
        remote_path="",
        job_id="test_remote",
    )


@pytest.fixture
def engine():
    eng = MagicMock()
    eng.start_sync.return_value = MagicMock()
    return eng


@pytest.fixture
def manager(engine, qcore_app):
    return SyncManager(engine)


def test_start_job_starts_engine(manager, engine, job):
    manager.start_job(job)
    engine.start_sync.assert_called_once_with(job)
    assert manager.get_status(job.job_id) == JobStatus.SYNCING


def test_running_job_is_not_started_twice(manager, engine, job):
    manager.start_job(job)
    manager.start_job(job)
    assert engine.start_sync.call_count == 1


def test_paused_job_is_not_started_again(manager, engine, job):
    """A paused job still has a live (SIGSTOPped) rclone process — starting a
    second bisync on the same pair would corrupt the baseline."""
    manager.start_job(job)
    manager.pause_job(job.job_id)
    assert manager.get_status(job.job_id) == JobStatus.PAUSED

    manager.start_job(job)
    assert engine.start_sync.call_count == 1


def test_paused_job_counts_as_active(manager, engine, job):
    manager.start_job(job)
    manager.pause_job(job.job_id)
    assert manager.is_any_active()
    assert job.job_id in manager.active_job_ids()


def test_stop_job_stops_process_and_resets_status(manager, engine, job):
    manager.start_job(job)
    proc = engine.start_sync.return_value
    manager.stop_job(job.job_id)
    proc.stop.assert_called_once()
    assert manager.get_status(job.job_id) == JobStatus.IDLE
    assert not manager.is_any_active()


def test_stop_job_keeps_engine_finished_handler_connected(manager, engine, job):
    """stop_job must only disconnect the manager's own finished slot — a
    blanket disconnect() would also sever the engine's bisync-state handler."""
    manager.start_job(job)
    proc = engine.start_sync.return_value
    manager.stop_job(job.job_id)
    # The manager disconnects exactly its own slot, not all slots
    assert proc.finished.disconnect.called
    args, _kwargs = proc.finished.disconnect.call_args
    assert args, "disconnect() was called without a specific slot"


def test_resume_after_pause(manager, engine, job):
    manager.start_job(job)
    manager.pause_job(job.job_id)
    manager.resume_job(job.job_id)
    assert manager.get_status(job.job_id) == JobStatus.SYNCING
