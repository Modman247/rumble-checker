#!/usr/bin/env bash
set -e

ICON_NAME="rumble-checker"

sudo rm -f /usr/local/bin/$ICON_NAME
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/$ICON_NAME.png"
rm -f "$HOME/.local/share/applications/$ICON_NAME.desktop"

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
kbuildsycoca6 --noincremental

echo "Uninstalled."
