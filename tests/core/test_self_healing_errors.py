"""Tests for the self-healing bisync error classification."""

from nubix.app import is_self_healing_error


def test_recovery_conditions_are_self_healing():
    """These are fixed by the automatic --resync on the next run — a 'Sync
    Error' popup for them would alarm the user about nothing."""
    for msg in (
        "Bisync critical error: cannot find prior Path1 or Path2 listings, "
        "likely due to critical error on prior run",
        "Bisync aborted. Must run --resync to recover.",
        "Bisync too many deletes safety stop",
    ):
        assert is_self_healing_error(msg), msg


def test_real_errors_are_not_self_healing():
    for msg in (
        "error listing: unexpected error occurred",
        "error during march: march failed with 20 error(s)",
        "Failed to sync: couldn't connect: 401 unauthorized",
        "",
    ):
        assert not is_self_healing_error(msg), msg
