# Nubix

A modern cloud sync manager for Ubuntu. Sync your files with Google Drive, Dropbox, and Nextcloud — powered by [rclone](https://rclone.org), with a clean graphical interface.

## Features

- **Google Drive, Dropbox, Nextcloud** — add multiple accounts of each provider
- **Three sync modes**: Full (download everything), Selective (choose folders), Bidirectional
- **Real-time dashboard** — see what's syncing, transfer speed, and progress
- **System tray** — runs quietly in the background
- **Bandwidth throttling** — limit upload/download speed
- **Scheduler** — sync only during certain hours
- **Secure credentials** — stored in GNOME Keyring (libsecret)
- **Open source** — your data never touches our servers

## Requirements

- Ubuntu 22.04+ (or any Linux with a desktop environment)
- Python 3.10+
- rclone

## Installation

### 1. Install rclone

```bash
sudo apt install rclone
# or
bash scripts/install_rclone.sh
```

### 2. Install Nubix

```bash
# From source
git clone https://github.com/Zenovs/Nubix.git
cd Nubix
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
python main.py
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Development

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## Architecture

```
nubix/
├── core/          # Business logic — no UI imports
│   ├── rclone_engine.py      # Subprocess management
│   ├── rclone_parser.py      # Output parsing
│   ├── sync_manager.py       # Job orchestration
│   ├── config_manager.py     # Settings persistence
│   ├── credential_vault.py   # GNOME Keyring / encrypted file
│   ├── remote_registry.py    # Cloud connection registry
│   ├── scheduler.py          # Time-window scheduling
│   └── bandwidth_controller.py
├── providers/     # One module per cloud provider
│   ├── google_drive.py
│   ├── dropbox.py
│   └── nextcloud.py
└── ui/            # PySide6 GUI
    ├── main_window.py
    ├── system_tray.py
    ├── dashboard/     # Real-time sync monitoring
    ├── wizard/        # Setup wizard
    ├── settings/      # Settings dialog
    ├── logs/          # Log viewer
    └── widgets/       # Reusable components
```

## License

MIT
