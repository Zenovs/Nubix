"""Application-wide constants for Nubix."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Nubix"
APP_ID = "com.nubix.app"
APP_VERSION = "0.2.7"

# Directories
CONFIG_DIR = Path.home() / ".config" / "nubix"
REMOTES_DIR = CONFIG_DIR / "remotes"
RCLONE_CONFIG_DIR = CONFIG_DIR / "rclone"
RCLONE_CONFIG_FILE = RCLONE_CONFIG_DIR / "rclone.conf"
LOG_DIR = CONFIG_DIR / "logs"
CACHE_DIR = Path.home() / ".cache" / "nubix"

# Config file names
GLOBAL_CONFIG_FILE = CONFIG_DIR / "config.yaml"
VAULT_FILE = CONFIG_DIR / "vault.enc"

# Autostart
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "nubix.desktop"

# Supported providers
SUPPORTED_PROVIDERS: list = []  # all rclone backends — see nubix/providers/__init__.py

# Sync modes
SYNC_MODE_FULL = "full"
SYNC_MODE_SELECTIVE = "selective"
SYNC_MODE_BIDIRECTIONAL = "bidirectional"

# Default settings
DEFAULT_BANDWIDTH_LIMIT = "0"  # 0 = unlimited in rclone notation
DEFAULT_LOG_RETENTION_DAYS = 30
DEFAULT_SYNC_INTERVAL_MINUTES = 30

# rclone binary name
RCLONE_BINARY = "rclone"

# rclone progress flags
RCLONE_FLAGS_BASE = [
    "--stats=1s",
    "--stats-one-line",
    "--progress",
    "--use-json-log",
    "--log-level=INFO",
]

# Keyring service name
KEYRING_SERVICE = "nubix"

# UI constants
SIDEBAR_WIDTH = 220
CARD_MIN_HEIGHT = 120
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600

# Transfer rate display
TRANSFER_HISTORY_SECONDS = 60

# Recent files panel
MAX_RECENT_FILES = 200
