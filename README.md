# Nubix — Cloud Sync Manager für Ubuntu

Sync deine Dateien mit **Google Drive**, **Dropbox** und **Nextcloud** — einfach, sicher und kostenlos.

> Powered by [rclone](https://rclone.org) mit einer modernen grafischen Oberfläche.

---

## ⚡ Installation (ein Befehl)

Öffne ein Terminal (`Strg + Alt + T`) und füge folgenden Befehl ein:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Zenovs/Nubix/main/install.sh)
```

Das Skript installiert automatisch:
- rclone (Sync-Engine)
- alle benötigten Python-Pakete
- die Nubix App
- einen Eintrag im Anwendungsmenü

**Keine weiteren Schritte nötig.**

---

## Features

| Feature | Beschreibung |
|---|---|
| ☁ **Google Drive** | OAuth2-Login, volle Drive-Integration |
| 📦 **Dropbox** | OAuth2-Login |
| 🔒 **Nextcloud** | WebDAV mit Benutzername & Passwort |
| 🔄 **3 Sync-Modi** | Full, Selektiv, Bidirektional |
| 📊 **Live-Dashboard** | Fortschritt, Transferrate, aktuelle Datei |
| 🖥 **System Tray** | Läuft im Hintergrund, immer erreichbar |
| 🚀 **Bandbreiten-Limit** | Upload/Download drosseln |
| 🕐 **Zeitplaner** | Nur zu bestimmten Zeiten synchronisieren |
| 🔑 **Sichere Credentials** | GNOME Keyring (libsecret) |
| 🔔 **Auto-Update** | Neue Version? Ein Klick reicht |

---

## Screenshots

> *(Screenshots folgen nach dem ersten Release)*

---

## Systemanforderungen

- Ubuntu 20.04 oder neuer (oder kompatible Distribution mit apt)
- Internetverbindung zur Installation
- ~200 MB freier Speicher

---

## Deinstallation

```bash
bash ~/.local/share/nubix/uninstall.sh
```

---

## Entwicklung

```bash
git clone https://github.com/Zenovs/Nubix.git
cd Nubix
pip install -r requirements-dev.txt
python3 main.py
```

Tests:
```bash
pytest tests/ -v
```

---

## Architektur

```
nubix/
├── core/          # Business-Logik (kein UI)
│   ├── rclone_engine.py      # Subprocess-Verwaltung
│   ├── rclone_parser.py      # Output-Parsing
│   ├── sync_manager.py       # Job-Orchestrierung
│   ├── config_manager.py     # Einstellungen
│   ├── credential_vault.py   # GNOME Keyring
│   ├── remote_registry.py    # Verbindungs-Registry
│   ├── scheduler.py          # Zeitfenster-Planung
│   ├── bandwidth_controller.py
│   └── updater.py            # Auto-Updater (GitHub Releases)
├── providers/     # Ein Modul pro Cloud-Anbieter
└── ui/            # PySide6 GUI
    ├── main_window.py
    ├── system_tray.py
    ├── update_dialog.py
    ├── dashboard/     # Echtzeit-Monitoring
    ├── wizard/        # Setup-Assistent
    ├── settings/      # Einstellungen
    ├── logs/          # Log-Anzeige
    └── widgets/       # Wiederverwendbare Komponenten
```

---

## Lizenz

Proprietär — alle Rechte vorbehalten. Nicht für kommerzielle Nutzung, Weiterverteilung oder Modifikation ohne ausdrückliche Genehmigung des Autors.
