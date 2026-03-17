"""
Stateless parsing functions for rclone stdout/stderr output.

rclone can emit either ANSI progress lines or JSON log lines depending on flags.
With --use-json-log we get structured JSON, making parsing reliable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from nubix.core.sync_job import TransferStats


@dataclass
class RcloneError:
    """A classified error from rclone output."""

    category: str  # "auth", "quota", "not_found", "network", "unknown"
    message: str
    raw_line: str


# Regex for ANSI progress line fallback:
# "Transferred:   1.234 GiB / 2.345 GiB, 52%, 10.5 MiB/s, ETA 1m30s"
_ANSI_PROGRESS_RE = re.compile(
    r"Transferred:\s+(?P<done>[0-9.]+\s*\w+)\s*/\s*(?P<total>[0-9.]+\s*\w+)"
    r",\s*(?P<pct>\d+)%"
    r"(?:,\s*(?P<speed>[0-9.]+\s*\w+/s))?"
    r"(?:,\s*ETA\s*(?P<eta>[\w]+))?",
    re.IGNORECASE,
)

_SIZE_UNITS = {
    "b": 1,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
}

_ERROR_PATTERNS = [
    (re.compile(r"401|403|unauthorized|forbidden|invalid_grant|token", re.I), "auth"),
    (re.compile(r"quota|storage.*full|no space|insufficient", re.I), "quota"),
    (re.compile(r"not found|no such file|404", re.I), "not_found"),
    (re.compile(r"network|connection|timeout|refused|reset|EOF", re.I), "network"),
]


def _parse_size_to_bytes(size_str: str) -> int:
    """Convert a human-readable size like '1.234 GiB' to bytes."""
    size_str = size_str.strip()
    match = re.match(r"([0-9.]+)\s*(\w+)?", size_str)
    if not match:
        return 0
    value = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    return int(value * _SIZE_UNITS.get(unit, 1))


def _parse_eta_to_seconds(eta_str: str) -> Optional[int]:
    """Convert ETA string like '1m30s' or '2h5m' to seconds."""
    if not eta_str or eta_str in ("-", ""):
        return None
    total = 0
    for amount, unit in re.findall(r"(\d+)([hms])", eta_str):
        amount = int(amount)
        if unit == "h":
            total += amount * 3600
        elif unit == "m":
            total += amount * 60
        elif unit == "s":
            total += amount
    return total if total > 0 else None


def parse_progress_line(line: str) -> Optional[TransferStats]:
    """
    Parse a rclone progress/stats line and return TransferStats.

    Handles both JSON log format (--use-json-log) and ANSI progress lines.
    Returns None if the line doesn't contain parseable stats.
    """
    line = line.strip()
    if not line:
        return None

    # Try JSON first (preferred with --use-json-log)
    if line.startswith("{"):
        try:
            data = json.loads(line)
            return _parse_json_log(data)
        except (json.JSONDecodeError, KeyError):
            return None

    # Fallback: ANSI progress line
    m = _ANSI_PROGRESS_RE.search(line)
    if m:
        done = _parse_size_to_bytes(m.group("done"))
        total = _parse_size_to_bytes(m.group("total"))
        pct = float(m.group("pct") or 0)
        speed_str = m.group("speed") or "0 B/s"
        speed = _parse_size_to_bytes(speed_str.replace("/s", ""))
        eta = _parse_eta_to_seconds(m.group("eta") or "")
        return TransferStats(
            bytes_done=done,
            bytes_total=total,
            speed_bps=float(speed),
            eta_seconds=eta,
            percent=pct,
        )

    return None


def _parse_json_log(data: dict) -> Optional[TransferStats]:
    """Parse a rclone JSON log entry."""
    # rclone JSON stats are nested under 'stats' key in the message
    level = data.get("level", "")
    msg = data.get("msg", "")

    # Stats message
    stats = data.get("stats")
    if stats:
        bytes_done = stats.get("bytes", 0)
        bytes_total = stats.get("totalBytes", 0)
        speed = stats.get("speed", 0.0)
        eta = stats.get("eta")
        pct = (bytes_done / bytes_total * 100) if bytes_total > 0 else 0
        transferring = stats.get("transferring", [])
        current_file = transferring[0].get("name", "") if transferring else ""
        return TransferStats(
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            speed_bps=float(speed),
            eta_seconds=int(eta) if eta is not None else None,
            current_file=current_file,
            percent=pct,
            files_transferred=stats.get("transfers", 0),
            files_total=stats.get("totalTransfers", 0),
            errors=stats.get("errors", 0),
        )

    return None


def parse_error_line(line: str) -> Optional[RcloneError]:
    """
    Classify a rclone stderr/error line into a known error category.

    Returns None if the line is not an error.
    """
    line = line.strip()
    if not line:
        return None

    # Try JSON error
    if line.startswith("{"):
        try:
            data = json.loads(line)
            level = data.get("level", "")
            if level in ("error", "critical"):
                msg = data.get("msg", line)
                return RcloneError(
                    category=_classify_error(msg),
                    message=msg,
                    raw_line=line,
                )
        except json.JSONDecodeError:
            pass

    # Check for ERROR: prefix in plain text
    if re.match(r"ERROR\s*:", line, re.I) or re.match(r"CRITICAL\s*:", line, re.I):
        return RcloneError(
            category=_classify_error(line),
            message=line,
            raw_line=line,
        )

    return None


def _classify_error(text: str) -> str:
    for pattern, category in _ERROR_PATTERNS:
        if pattern.search(text):
            return category
    return "unknown"
