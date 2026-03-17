# Changelog

## [0.2.6] — 2026-03-17

### Bugfixes

- Fix browser not opening on OAuth: use `--auth-no-open-browser` so rclone never tries to open a browser (fails inside AppImage), then open via `QDesktopServices` which works reliably

## [0.2.5] — 2026-03-17

### Changes

- Remove cloud icon (☁) from sidebar header

## [0.2.4] — 2026-03-17

### Changes

- Remove hardcoded "Google Drive · Dropbox · Nextcloud" from install.sh, README, and constants — Nubix supports 40+ rclone providers
- install.sh: add `Cache-Control: no-cache` to GitHub API call to prevent stale version responses
- install.sh: add `--retry 3 --retry-delay 3` to AppImage download for transient network errors

## [0.2.3] — 2026-03-17

### Bugfixes

- Fix in-app update staying on old version after restart: `os.execv(sys.executable)` re-launched the Python binary inside the old AppImage squashfs mount; now uses `$APPIMAGE` env var to exec the new AppImage file directly

## [0.2.2] — 2026-03-17

### Bugfixes

- Fix two browser tabs opening on OAuth: rclone already opens the browser itself; removed redundant `QDesktopServices.openUrl()` call from `_on_auth_url`

## [0.2.1] — 2026-03-17

### Bugfixes

- Fix `QWizard::field: No such field 'sync_mode_value'`: field was registered as `"sync_mode"` but accessed as `"sync_mode_value"` everywhere — name unified; Python `property` replaced with Qt `Property`
- Fix `SyncModePage` `changedSignal` belonging to child `QButtonGroup` instead of the page — add `_sync_mode_changed` Signal on the page class
- Fix confirmation page showing wrong provider name for non-Dropbox/Drive/Nextcloud providers — use `get_provider()` instead of hardcoded 3-entry dict

## [0.2.0] — 2026-03-17

### Bugfixes

- Fix dashboard not showing connections after wizard: rclone type was missing from `config_args`, causing `rclone config create` to fail silently and skip `add_remote`
- Fix WebDAV providers (Nextcloud, ownCloud, etc.) using wrong rclone backend — now correctly uses `webdav` type with `vendor` parameter
- Add error dialog in wizard when rclone configuration fails (instead of silent failure)
- Implement "Start sync now" on confirmation page — passes SyncManager to wizard

## [0.1.9] — 2026-03-17

### Bugfixes

- Fix update checker always showing outdated: `nubix/__init__.py` had hardcoded `0.1.0` — now reads correct version
- Fix license string: changed from MIT to Proprietary

## [0.1.8] — 2026-03-17

### Bugfixes

- Fix "No provider selected" error: use Qt `Property` instead of Python `property` so `QWizard.field("provider_id")` reads the selection correctly

## [0.1.7] — 2026-03-17

### Bugfixes

- Fix ASCII art misalignment in dashboard empty state: switched to HTML `<pre>` tag for correct monospace rendering
- Replace sidebar ASCII art header with clean styled text (avoids mixed block/box-drawing char width issues)

## [0.1.5] — 2026-03-17

### Features

- Update tab in Settings: check for updates, see release notes, download & install in one click
- Progress bar during download, automatic restart after installation

## [0.1.4] — 2026-03-17

### Bugfixes

- Fix LogViewer crash: add `@Slot(str, int)` so Qt meta-object can invoke `_append_line`
- Fix wizard provider field: `registerField` signal must belong to the page — add `_provider_id_changed` Signal
- Fix OAuth browser: rclone provider type must come before `--auth-no-open-browser` flag
- Improve auth URL detection with regex to handle all rclone output formats

## [0.1.3] — 2026-03-17

### Features

- ASCII art logo visible in sidebar header, dashboard empty state, and README
- All 40+ rclone backends supported (Google Drive, OneDrive, Dropbox, Box,
  pCloud, MEGA, S3, Backblaze B2, Nextcloud, WebDAV, SFTP, FTP, SMB, and more)
- Searchable provider list replaces 3-button grid
- OAuth browser authorization now works: uses QDesktopServices + fallback URL link
- Auth forms for S3 (access key/secret), SFTP/FTP (host/user/pass), Simple (MEGA etc.)
- Settings nav item now opens the Settings dialog correctly

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
