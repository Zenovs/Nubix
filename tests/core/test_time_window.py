"""Tests for TimeWindow — including overnight (wrap-past-midnight) windows."""

from datetime import time

from nubix.core.sync_job import TimeWindow


def _w(start, end, days=None):
    return TimeWindow(days=days or [0, 1, 2, 3, 4, 5, 6], start_time=start, end_time=end)


class TestContains:
    def test_normal_window(self):
        w = _w(time(9, 0), time(17, 0))
        assert w.contains(time(12, 0))
        assert not w.contains(time(8, 59))
        assert not w.contains(time(17, 1))

    def test_boundaries_inclusive(self):
        w = _w(time(9, 0), time(17, 0))
        assert w.contains(time(9, 0))
        assert w.contains(time(17, 0))

    def test_overnight_window(self):
        w = _w(time(22, 0), time(6, 0))
        assert w.contains(time(23, 30))
        assert w.contains(time(2, 0))
        assert w.contains(time(22, 0))
        assert w.contains(time(6, 0))
        assert not w.contains(time(12, 0))
        assert not w.contains(time(21, 59))


class TestOverlaps:
    def test_disjoint_days_never_overlap(self):
        a = _w(time(9, 0), time(17, 0), days=[0])
        b = _w(time(9, 0), time(17, 0), days=[1])
        assert not a.overlaps(b)

    def test_plain_overlap(self):
        a = _w(time(9, 0), time(12, 0))
        b = _w(time(11, 0), time(14, 0))
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_adjacent_windows_do_not_overlap(self):
        a = _w(time(9, 0), time(12, 0))
        b = _w(time(12, 0), time(14, 0))
        assert not a.overlaps(b)

    def test_overnight_overlaps_morning_window(self):
        night = _w(time(22, 0), time(6, 0))
        morning = _w(time(5, 0), time(8, 0))
        assert night.overlaps(morning)
        assert morning.overlaps(night)

    def test_overnight_does_not_overlap_midday(self):
        night = _w(time(22, 0), time(6, 0))
        midday = _w(time(10, 0), time(16, 0))
        assert not night.overlaps(midday)
        assert not midday.overlaps(night)
