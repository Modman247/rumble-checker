#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="rumble-checker"
LIB_DIR="/usr/local/lib/$APP_NAME"
BIN_PATH="/usr/local/bin/$APP_NAME"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$APP_NAME.desktop"

echo "=== Installing $APP_NAME v2 ==="

# --- Python files ---
sudo mkdir -p "$LIB_DIR"
sudo cp "$SCRIPT_DIR"/{backend.py,tk_app.py,cli.py,sfx.py,controllers.json,rumble-checker-icon.png} "$LIB_DIR/"
echo "  installed Python files to $LIB_DIR"

# --- Launcher ---
sudo bash -c "printf '#!/bin/sh\ncd /usr/local/lib/$APP_NAME\nexec python3 tk_app.py \"\$@\"\n' > $BIN_PATH && chmod 755 $BIN_PATH"
echo "  installed $BIN_PATH"

# --- CLI launcher ---
sudo bash -c "printf '#!/bin/sh\ncd /usr/local/lib/$APP_NAME\nexec python3 cli.py \"\$@\"\n' > /usr/local/bin/$APP_NAME-cli && chmod 755 /usr/local/bin/$APP_NAME-cli"
echo "  installed /usr/local/bin/$APP_NAME-cli"

# --- Icon ---
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/rumble-checker.png" "$ICON_DIR/$APP_NAME.png"
echo "  installed icon"

# --- Desktop entry ---
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Rumble Checker
Exec=$BIN_PATH
Icon=$APP_NAME
Terminal=false
Categories=Utility;
EOF
echo "  installed .desktop"

# --- Refresh caches ---
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
rm -f "$HOME/.cache/icon-cache.kcache"
kbuildsycoca6 --noincremental 2>/dev/null || true

echo ""
echo "Done. Run: $APP_NAME"
