"""Tests for rclone output parsing."""

from __future__ import annotations

import json

import pytest

from nubix.core.rclone_parser import parse_error_line, parse_progress_line


class TestParseProgressLine:
    def test_empty_line_returns_none(self):
        assert parse_progress_line("") is None

    def test_whitespace_returns_none(self):
        assert parse_progress_line("   ") is None

    def test_json_stats_line(self):
        data = {
            "level": "info",
            "msg": "stats",
            "stats": {
                "bytes": 1024,
                "totalBytes": 2048,
                "speed": 512.0,
                "eta": 2,
                "transfers": 3,
                "totalTransfers": 10,
                "errors": 0,
                "transferring": [{"name": "myfile.txt"}],
            },
        }
        result = parse_progress_line(json.dumps(data))
        assert result is not None
        assert result.bytes_done == 1024
        assert result.bytes_total == 2048
        assert result.speed_bps == 512.0
        assert result.percent == pytest.approx(50.0)
        assert result.current_file == "myfile.txt"

    def test_json_no_stats_key_returns_none(self):
        data = {"level": "info", "msg": "some log message"}
        assert parse_progress_line(json.dumps(data)) is None

    def test_ansi_progress_line(self):
        line = "Transferred:   512 MiB / 1.000 GiB, 50%, 10 MiB/s, ETA 51s"
        result = parse_progress_line(line)
        assert result is not None
        assert result.percent == pytest.approx(50.0)

    def test_malformed_json_returns_none(self):
        assert parse_progress_line("{not valid json}") is None

    def test_non_stats_line_returns_none(self):
        assert parse_progress_line("INFO: Starting sync run") is None


class TestParseErrorLine:
    def test_empty_line_returns_none(self):
        assert parse_error_line("") is None

    def test_auth_error_classified(self):
        result = parse_error_line("ERROR: 401 Unauthorized: token expired")
        assert result is not None
        assert result.category == "auth"

    def test_quota_error_classified(self):
        result = parse_error_line("ERROR: quota exceeded for user")
        assert result is not None
        assert result.category == "quota"

    def test_network_error_classified(self):
        result = parse_error_line("ERROR: connection timeout after 30s")
        assert result is not None
        assert result.category == "network"

    def test_not_found_classified(self):
        result = parse_error_line("ERROR: 404 not found")
        assert result is not None
        assert result.category == "not_found"

    def test_unknown_error_classified(self):
        result = parse_error_line("ERROR: something went wrong")
        assert result is not None
        assert result.category == "unknown"

    def test_info_line_returns_none(self):
        assert parse_error_line("INFO: Transferring file.txt") is None

    def test_json_error_line(self):
        data = {"level": "error", "msg": "401 Unauthorized"}
        result = parse_error_line(json.dumps(data))
        assert result is not None
        assert result.category == "auth"
