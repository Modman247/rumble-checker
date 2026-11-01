#!/usr/bin/env bash
set -euo pipefail

APP_NAME="rumble-checker"
BIN_PATH="/usr/local/bin/$APP_NAME"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$APP_NAME.desktop"

# --- Remove files ---
sudo rm -f "$BIN_PATH"
rm -f "$ICON_DIR/$APP_NAME.png"
rm -f "$DESKTOP_FILE"
rm -f "$HOME/Desktop/$APP_NAME.desktop"

# --- Orphaned debug sources ---
if [ -d "/usr/src/debug/$APP_NAME" ]; then
    sudo rm -rf "/usr/src/debug/$APP_NAME"
    echo "  removed /usr/src/debug/$APP_NAME"
fi

# --- XDG / GTK icon cache ---
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || \
    rm -f "$HOME/.local/share/icons/hicolor/icon-theme.cache"

# --- Desktop database ---
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# --- KDE Plasma (icon pixmap cache + sycoca) ---
rm -f "$HOME/.cache/icon-cache.kcache"
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental 2>/dev/null
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental 2>/dev/null
fi

echo "Uninstalled $APP_NAME"
