# Changelog

## [0.1.2] — 2026-03-17

### UI Redesign

- Complete dark theme: deep navy background, purple accent (#7C5CFC)
- Gradient sidebar header, accent-highlighted navigation
- Redesigned sync cards with gradient progress bars and styled buttons
- Dark-friendly status badges (blue/green/orange/red)
- Modern transfer rate widget with filled sparkline
- Consistent typography, spacing, and hover states throughout

## [0.1.1] — 2026-03-17

### Bugfixes

- Fix startup crash: `_stack` widget was referenced before creation in `MainWindow`
- Remove deprecated Qt attributes `AA_EnableHighDpiScaling` / `AA_UseHighDpiPixmaps`
- Fix `scheduler_tab.py`: replace dynamic `__import__` with proper `QTime` import, remove unused variable
- Fix black formatting in scheduler tab

## [0.1.0] — 2026-03-17

### Initial Release

- Google Drive, Dropbox, and Nextcloud (WebDAV) support via rclone
- Three sync modes: Full Sync, Selective Sync, Bidirectional
- Real-time dashboard with transfer rate and progress bars
- System tray icon with quick actions
- Setup wizard for adding cloud connections
- Bandwidth throttling (upload & download limits)
- Scheduler: sync only during defined time windows
- Secure credential storage via GNOME Keyring (libsecret)
- Automatic update checker — notifies when a new version is available
- Log viewer with export functionality
- `.deb` and AppImage packages for Ubuntu
