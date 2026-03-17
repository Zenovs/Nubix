#!/usr/bin/env bash
# Download and install the latest rclone binary

set -euo pipefail

INSTALL_DIR="/usr/local/bin"
ARCH=$(uname -m)

case "$ARCH" in
    x86_64)  RCLONE_ARCH="amd64" ;;
    aarch64) RCLONE_ARCH="arm64" ;;
    armv7l)  RCLONE_ARCH="arm-v7" ;;
    *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "Downloading rclone for linux/$RCLONE_ARCH..."
TMP=$(mktemp -d)
cd "$TMP"

curl -fsSL "https://downloads.rclone.org/rclone-current-linux-${RCLONE_ARCH}.zip" -o rclone.zip
unzip -q rclone.zip
RCLONE_DIR=$(find . -name "rclone" -type f | head -1)

echo "Installing rclone to $INSTALL_DIR..."
sudo install -m 755 "$RCLONE_DIR" "$INSTALL_DIR/rclone"

rm -rf "$TMP"
echo "rclone $(rclone version | head -1) installed successfully."
