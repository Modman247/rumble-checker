#!/usr/bin/env bash
set -euo pipefail

ICON_NAME="rumble-checker"
BIN_PATH="/usr/local/bin/$ICON_NAME"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$ICON_NAME.desktop"

if ! sudo -n true 2>/dev/null; then
    echo "Error: requires sudo (password). Run interactively." >&2
    exit 1
fi

sudo rm -f "$BIN_PATH"
rm -f "$ICON_DIR/$ICON_NAME.png"
rm -f "$DESKTOP_FILE"

gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Uninstalled $ICON_NAME"
