"""Tests for the file watcher's event filtering."""

from types import SimpleNamespace

from nubix.core.file_watcher import _DebounceHandler


def _handler(calls):
    return _DebounceHandler("r1", lambda rid: calls.append(rid))


def test_write_events_trigger_callback():
    calls = []
    h = _handler(calls)
    for etype in ("created", "modified", "deleted", "moved", "closed"):
        h.dispatch(SimpleNamespace(event_type=etype, src_path="/data/file.txt"))
    assert len(calls) == 5


def test_read_only_events_are_ignored():
    """Browsing the folder (file manager, rclone listing scans) opens files
    without writing — that must not arm the sync debounce."""
    calls = []
    h = _handler(calls)
    for etype in ("opened", "closed_no_write"):
        h.dispatch(SimpleNamespace(event_type=etype, src_path="/data/file.txt"))
    assert calls == []


def test_temp_file_suffixes_are_ignored():
    calls = []
    h = _handler(calls)
    for name in ("x.swp", "x.tmp", "x.part", "x.partial", "x~"):
        h.dispatch(SimpleNamespace(event_type="modified", src_path=f"/data/{name}"))
    assert calls == []


def test_bytes_src_path_is_handled():
    calls = []
    h = _handler(calls)
    h.dispatch(SimpleNamespace(event_type="modified", src_path=b"/data/file.txt"))
    h.dispatch(SimpleNamespace(event_type="modified", src_path=b"/data/skip.tmp"))
    assert len(calls) == 1
