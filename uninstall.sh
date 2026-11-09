#!/usr/bin/env bash
set -euo pipefail

APP_NAME="rumble-checker"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$APP_NAME.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
UDEV_RULE="/etc/udev/rules.d/99-rumble-checker.rules"
PROJECT_DIR="$HOME/Desktop/rumble-checker-v2-final"

echo "=== Uninstalling $APP_NAME v2 ==="

if [ -f "$UDEV_RULE" ]; then
    sudo rm -f "$UDEV_RULE"
    sudo udevadm control --reload-rules
    echo "  removed udev rule"
fi

rm -f "$DESKTOP_FILE"
rm -f "$HOME/Desktop/$APP_NAME.desktop"
echo "  removed .desktop"

rm -f "$ICON_DIR/$APP_NAME.png"
echo "  removed icon"

if [ -d "$PROJECT_DIR" ]; then
    rm -rf "$PROJECT_DIR"
    echo "  removed project dir"
fi

if getent group input | grep -q "$USER"; then
    read -p "  Remove $USER from input group? (y/N) " ans
    if [ "$ans" = "y" ]; then
        sudo gpasswd -d "$USER" input
        echo "  removed from input group (relogin to apply)"
    fi
fi

gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || \
    rm -f "$HOME/.local/share/icons/hicolor/icon-theme.cache"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

rm -f "$HOME/.cache/icon-cache.kcache"
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental 2>/dev/null
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental 2>/dev/null
fi

echo "Done. Run check_clean.sh to verify."
