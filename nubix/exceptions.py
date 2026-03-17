"""Custom exception hierarchy for Nubix."""

from __future__ import annotations


class NubixError(Exception):
    """Base exception for all Nubix errors."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class RcloneNotFoundError(NubixError):
    """rclone binary not found on the system."""

    def __init__(self):
        super().__init__(
            "rclone binary not found",
            "rclone is not installed. Please install it with: sudo apt install rclone",
        )


class RcloneExecutionError(NubixError):
    """rclone process exited with a non-zero return code."""

    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"rclone exited with code {returncode}: {stderr}",
            f"Sync failed (exit code {returncode}). Check the log for details.",
        )


class RemoteNotConfiguredError(NubixError):
    """The requested remote is not configured."""

    def __init__(self, remote_id: str):
        self.remote_id = remote_id
        super().__init__(
            f"Remote '{remote_id}' is not configured",
            f"Cloud connection '{remote_id}' has not been set up yet.",
        )


class AuthenticationError(NubixError):
    """Authentication with the cloud provider failed."""

    def __init__(self, provider: str, detail: str = ""):
        self.provider = provider
        super().__init__(
            f"Authentication failed for {provider}: {detail}",
            f"Could not connect to {provider}. Please re-authenticate.",
        )


class SchedulerConflictError(NubixError):
    """Overlapping time windows in the scheduler."""

    def __init__(self, remote_id: str):
        self.remote_id = remote_id
        super().__init__(
            f"Overlapping schedule windows for remote '{remote_id}'",
            "Two or more schedule windows overlap. Please fix the schedule settings.",
        )


class VaultAccessError(NubixError):
    """Cannot access the credential vault (keyring unavailable)."""

    def __init__(self, detail: str = ""):
        super().__init__(
            f"Credential vault access failed: {detail}",
            "Could not access the system keyring. Credentials may not be saved securely.",
        )


class ConfigValidationError(NubixError):
    """Configuration file contains invalid values."""

    def __init__(self, field: str, expected: str, got: str):
        self.field = field
        super().__init__(
            f"Config validation failed for '{field}': expected {expected}, got {got}",
            f"Configuration error in field '{field}'. Please check your settings.",
        )
