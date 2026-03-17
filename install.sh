#!/usr/bin/env bash
# ============================================================
#  Nubix Installer — Cloud Sync Manager für Ubuntu
#  Einfach ausführen:
#    bash <(curl -fsSL https://raw.githubusercontent.com/Zenovs/Nubix/main/install.sh)
# ============================================================

set -euo pipefail

# ---- Farben ------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ---- Hilfsfunktionen ---------------------------------------
info()    { echo -e "${BLUE}[Nubix]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗] FEHLER:${NC} $*"; exit 1; }

confirm() {
    echo -e "${YELLOW}$* [J/n]:${NC} \c"
    read -r ans
    [[ "$ans" =~ ^[Nn]$ ]] && return 1 || return 0
}

# ---- Banner ------------------------------------------------
echo ""
echo -e "${BOLD}${BLUE}"
echo "  ███╗   ██╗██╗   ██╗██████╗ ██╗██╗  ██╗"
echo "  ████╗  ██║██║   ██║██╔══██╗██║╚██╗██╔╝"
echo "  ██╔██╗ ██║██║   ██║██████╔╝██║ ╚███╔╝ "
echo "  ██║╚██╗██║██║   ██║██╔══██╗██║ ██╔██╗ "
echo "  ██║ ╚████║╚██████╔╝██████╔╝██║██╔╝ ██╗"
echo "  ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "  ${BOLD}Cloud Sync Manager für Ubuntu${NC}"
echo -e "  Google Drive · Dropbox · Nextcloud"
echo ""
echo "  ─────────────────────────────────────────"
echo ""

# ---- Betriebssystem prüfen ---------------------------------
if [[ "$(uname -s)" != "Linux" ]]; then
    error "Nubix unterstützt momentan nur Linux (Ubuntu)."
fi

if ! command -v apt-get &>/dev/null; then
    error "Dieses Skript benötigt apt (Ubuntu/Debian). Andere Distributionen werden noch nicht unterstützt."
fi

INSTALL_DIR="$HOME/.local/share/nubix"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

info "Installationsverzeichnis: ${INSTALL_DIR}"
echo ""

# ---- Sudo-Passwort einmalig abfragen -----------------------
info "Für die Installation werden Administrator-Rechte benötigt."
info "Bitte gib dein Passwort ein (wird nur für apt verwendet):"
sudo -v || error "Sudo-Zugriff verweigert."

# Sudo-Session im Hintergrund auffrischen
( while true; do sudo -n true; sleep 50; done ) &
SUDO_REFRESH_PID=$!
trap "kill $SUDO_REFRESH_PID 2>/dev/null || true" EXIT

# ---- System-Pakete installieren ----------------------------
echo ""
info "Installiere System-Abhängigkeiten..."
sudo apt-get update -qq

PKGS_TO_INSTALL=()
check_pkg() {
    dpkg -s "$1" &>/dev/null || PKGS_TO_INSTALL+=("$1")
}

check_pkg rclone
check_pkg python3
check_pkg python3-pip
check_pkg python3-venv
check_pkg libgl1
check_pkg libglib2.0-0
check_pkg libdbus-1-3
check_pkg libsecret-1-0
check_pkg libxkbcommon-x11-0
check_pkg libxcb-icccm4
check_pkg libxcb-image0
check_pkg libxcb-keysyms1
check_pkg libxcb-randr0
check_pkg libxcb-render-util0
check_pkg libxcb-xinerama0
check_pkg libxcb-cursor0

if [[ ${#PKGS_TO_INSTALL[@]} -gt 0 ]]; then
    info "Installiere: ${PKGS_TO_INSTALL[*]}"
    sudo apt-get install -y "${PKGS_TO_INSTALL[@]}" 2>&1 | grep -E "(Installiere|Installing|Unpacking)" | sed 's/^/  /' || true
    success "System-Pakete installiert."
else
    success "Alle System-Pakete bereits vorhanden."
fi

# ---- Nubix herunterladen -----------------------------------
echo ""
info "Lade Nubix herunter..."

mkdir -p "$INSTALL_DIR"

# GitHub API: neueste Version ermitteln
LATEST=$(curl -fsSL "https://api.github.com/repos/Zenovs/Nubix/releases/latest" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tag_name','').lstrip('v'))" 2>/dev/null || echo "")

if [[ -z "$LATEST" ]]; then
    warn "Kann keine Release-Version ermitteln — lade Quellcode von main..."
    USE_SOURCE=true
else
    info "Neueste Version: ${BOLD}v${LATEST}${NC}"
    USE_SOURCE=false
fi

if [[ "$USE_SOURCE" == "false" ]]; then
    # Prüfe ob AppImage-Asset vorhanden
    APPIMAGE_URL=$(curl -fsSL "https://api.github.com/repos/Zenovs/Nubix/releases/latest" \
        | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('assets', []):
    if a['name'].endswith('.AppImage'):
        print(a['browser_download_url'])
        break
" 2>/dev/null || echo "")
fi

if [[ -n "${APPIMAGE_URL:-}" ]]; then
    # ---- AppImage installieren (bevorzugt) -----------------
    info "Lade AppImage herunter..."
    APPIMAGE_PATH="$INSTALL_DIR/Nubix-${LATEST}.AppImage"

    curl -fL --progress-bar "$APPIMAGE_URL" -o "$APPIMAGE_PATH"
    chmod +x "$APPIMAGE_PATH"

    # Symlink in ~/.local/bin
    mkdir -p "$BIN_DIR"
    ln -sf "$APPIMAGE_PATH" "$BIN_DIR/nubix"
    success "AppImage installiert: $APPIMAGE_PATH"

else
    # ---- Aus Quellcode installieren (Fallback) --------------
    warn "Kein AppImage-Release gefunden — installiere aus Quellcode."
    info "Lade Quellcode herunter..."

    if command -v git &>/dev/null; then
        if [[ -d "$INSTALL_DIR/.git" ]]; then
            git -C "$INSTALL_DIR" pull --quiet
        else
            git clone --quiet --depth=1 https://github.com/Zenovs/Nubix.git "$INSTALL_DIR"
        fi
    else
        sudo apt-get install -y git -qq
        git clone --quiet --depth=1 https://github.com/Zenovs/Nubix.git "$INSTALL_DIR"
    fi
    success "Quellcode heruntergeladen."

    # Virtuelle Python-Umgebung
    info "Erstelle Python-Umgebung..."
    python3 -m venv "$INSTALL_DIR/.venv" --system-site-packages
    source "$INSTALL_DIR/.venv/bin/activate"

    info "Installiere Python-Abhängigkeiten (kann 1-2 Minuten dauern)..."
    pip install --quiet --upgrade pip
    pip install --quiet -r "$INSTALL_DIR/requirements.txt"
    success "Python-Abhängigkeiten installiert."

    # Startskript erstellen
    mkdir -p "$BIN_DIR"
    cat > "$BIN_DIR/nubix" << EOF
#!/usr/bin/env bash
source "$INSTALL_DIR/.venv/bin/activate"
exec python3 "$INSTALL_DIR/main.py" "\$@"
EOF
    chmod +x "$BIN_DIR/nubix"
    success "Startskript erstellt: $BIN_DIR/nubix"
fi

# ---- Desktop-Integration -----------------------------------
echo ""
info "Richte Desktop-Integration ein..."

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/nubix.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Nubix
GenericName=Cloud Sync Manager
Comment=Sync files with Google Drive, Dropbox and Nextcloud
Exec=$BIN_DIR/nubix
Icon=nubix
Terminal=false
StartupNotify=true
Categories=Network;FileTransfer;
Keywords=cloud;sync;dropbox;google;drive;nextcloud;
EOF

# Desktop-Datenbank aktualisieren
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
success "Desktop-Eintrag erstellt (App erscheint im Anwendungsmenü)."

# ---- PATH prüfen -------------------------------------------
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    warn "~/.local/bin ist nicht in deinem PATH."
    info "Füge folgende Zeile zu deiner ~/.bashrc oder ~/.zshrc hinzu:"
    echo ""
    echo -e "    ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo ""
    # Automatisch einfügen
    SHELL_RC=""
    [[ -f "$HOME/.bashrc" ]] && SHELL_RC="$HOME/.bashrc"
    [[ -f "$HOME/.zshrc" ]]  && SHELL_RC="$HOME/.zshrc"
    if [[ -n "$SHELL_RC" ]]; then
        if confirm "Soll ich das automatisch in $SHELL_RC eintragen?"; then
            echo '' >> "$SHELL_RC"
            echo '# Nubix — lokale Binaries' >> "$SHELL_RC"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
            success "PATH wurde in $SHELL_RC eingetragen."
            export PATH="$BIN_DIR:$PATH"
        fi
    fi
fi

# ---- Deinstallations-Skript --------------------------------
cat > "$INSTALL_DIR/uninstall.sh" << 'UNINSTALL'
#!/usr/bin/env bash
echo "Deinstalliere Nubix..."
rm -f  "$HOME/.local/bin/nubix"
rm -f  "$HOME/.local/share/applications/nubix.desktop"
rm -rf "$HOME/.local/share/nubix"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Nubix wurde entfernt."
echo "Konfigurationsdaten in ~/.config/nubix wurden NICHT gelöscht."
echo "Zum vollständigen Entfernen: rm -rf ~/.config/nubix"
UNINSTALL
chmod +x "$INSTALL_DIR/uninstall.sh"

# ---- Fertig ------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}  ✓ Nubix wurde erfolgreich installiert!${NC}"
echo ""
echo -e "  ${BOLD}Starten:${NC}"
echo -e "    Terminal:   ${BLUE}nubix${NC}"
echo -e "    Anwendungsmenü: suche nach ${BLUE}Nubix${NC}"
echo ""
echo -e "  ${BOLD}Deinstallieren:${NC}"
echo -e "    bash ${BLUE}~/.local/share/nubix/uninstall.sh${NC}"
echo ""
echo -e "  ${BOLD}Projekt:${NC}  https://github.com/Zenovs/Nubix"
echo ""

# Starten anbieten
if confirm "Soll Nubix jetzt gestartet werden?"; then
    nubix &
    disown
    success "Nubix wurde gestartet."
fi
