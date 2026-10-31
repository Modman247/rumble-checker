#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$SCRIPT_DIR/dist/rumble-checker"
ICON_NAME="rumble-checker"
BIN_PATH="/usr/local/bin/$ICON_NAME"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$ICON_NAME.desktop"

[[ -f "$BIN" ]] || { echo "Error: $BIN not found. Build first." >&2; exit 1; }

# --- Binary ---
sudo install -m 755 "$BIN" "$BIN_PATH"

# --- Icon ---
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/rumble-checker.png" "$ICON_DIR/$ICON_NAME.png"

# --- Desktop entry ---
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Rumble Checker
Comment=Test and calibrate rumble/force feedback devices
Exec=$BIN_PATH
Icon=$ICON_NAME
Terminal=false
Categories=Utility;Accessibility;
EOF

# --- Refresh caches ---
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
