"""Core data structures for sync jobs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from pathlib import Path
from typing import Optional


class SyncMode(str, Enum):
    FULL = "full"
    SELECTIVE = "selective"
    BIDIRECTIONAL = "bidirectional"
    MOUNT = "mount"  # rclone VFS mount — on-demand download, no local copy


class JobStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    PAUSED = "paused"
    ERROR = "error"
    UP_TO_DATE = "up_to_date"
    MOUNTED = "mounted"  # rclone mount is active


@dataclass
class TimeWindow:
    """A recurring time window during which syncing is allowed."""

    days: list[int]  # 0=Monday … 6=Sunday
    start_time: time
    end_time: time

    def overlaps(self, other: "TimeWindow") -> bool:
        common_days = set(self.days) & set(other.days)
        if not common_days:
            return False
        return self.start_time < other.end_time and other.start_time < self.end_time


@dataclass
class TransferStats:
    """Real-time transfer statistics emitted by rclone."""

    bytes_done: int = 0
    bytes_total: int = 0
    speed_bps: float = 0.0
    eta_seconds: Optional[int] = None
    current_file: str = ""
    percent: float = 0.0
    files_transferred: int = 0
    files_total: int = 0
    errors: int = 0


@dataclass
class SyncJob:
    """Represents a single configured sync job."""

    remote_id: str
    provider_type: str
    local_path: Path
    remote_path: str
    sync_mode: SyncMode = SyncMode.FULL
    filters: list[str] = field(default_factory=list)
    bandwidth_limit: str = "0"
    is_scheduled: bool = False
    schedule_windows: list[TimeWindow] = field(default_factory=list)
    mount_cache_mode: str = "full"
    mount_cache_size: str = "1G"
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "remote_id": self.remote_id,
            "provider_type": self.provider_type,
            "local_path": str(self.local_path),
            "remote_path": self.remote_path,
            "sync_mode": self.sync_mode.value,
            "filters": self.filters,
            "bandwidth_limit": self.bandwidth_limit,
            "is_scheduled": self.is_scheduled,
            "schedule_windows": [
                {
                    "days": w.days,
                    "start_time": w.start_time.isoformat(),
                    "end_time": w.end_time.isoformat(),
                }
                for w in self.schedule_windows
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncJob":
        windows = [
            TimeWindow(
                days=w["days"],
                start_time=time.fromisoformat(w["start_time"]),
                end_time=time.fromisoformat(w["end_time"]),
            )
            for w in data.get("schedule_windows", [])
        ]
        return cls(
            job_id=data.get("job_id", str(uuid.uuid4())),
            remote_id=data["remote_id"],
            provider_type=data["provider_type"],
            local_path=Path(data["local_path"]),
            remote_path=data["remote_path"],
            sync_mode=SyncMode(data.get("sync_mode", "full")),
            filters=data.get("filters", []),
            bandwidth_limit=data.get("bandwidth_limit", "0"),
            is_scheduled=data.get("is_scheduled", False),
            schedule_windows=windows,
        )
