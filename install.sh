#!/usr/bin/env bash
set -euo pipefail

APP="rumble-checker"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HOME/.local/lib/$APP"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "=== Installing $APP v2 ==="

# Python files
mkdir -p "$DEST_DIR"
cp "$SRC_DIR"/{backend.py,tk_app.py,cli.py,sfx.py,controllers.json} "$DEST_DIR/"
echo "  installed Python files to $DEST_DIR"

# Launcher scripts
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/$APP" << LAUNCHER
#!/bin/sh
exec python3 $DEST_DIR/tk_app.py "\$@"
LAUNCHER
chmod +x "$BIN_DIR/$APP"

cat > "$BIN_DIR/$APP-cli" << CLIBIN
#!/bin/sh
exec python3 $DEST_DIR/cli.py "\$@"
CLIBIN
chmod +x "$BIN_DIR/$APP-cli"
echo "  installed $BIN_DIR/$APP and $BIN_DIR/$APP-cli"

# Icon
mkdir -p "$ICON_DIR"
cp "$SRC_DIR/rumble-checker.png" "$ICON_DIR/$APP.png"
echo "  installed icon"

# .desktop
sed "s|^Exec=.*|Exec=$APP|" "$SRC_DIR/rumble-checker.desktop" \
  | sed "s|^Icon=.*|Icon=$APP|" \
  > "$DESKTOP_DIR/$APP.desktop"
echo "  installed .desktop"

# KDE cache refresh
rm -f "$HOME/.cache/icon-cache.kcache"
kbuildsycoca6 --noincremental 2>/dev/null || true
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo ""
echo "Done. Run: $APP"
echo "Or find it in your app launcher."
