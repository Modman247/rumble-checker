#!/usr/bin/env bash

APP="rumble-checker"
FOUND=0

check() {
    if [ -e "$1" ]; then
        echo "  FOUND: $1"
        FOUND=1
    else
        echo "  clean"
    fi
}

check_cmd() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "  FOUND: $(command -v "$1")"
        FOUND=1
    else
        echo "  clean"
    fi
}

echo "=== Binary ==="
check_cmd "$APP"
check "/usr/local/bin/$APP"
check "/usr/local/bin/$APP-cli"
check "$HOME/.local/bin/$APP"

echo "=== Python files ==="
check "/usr/local/lib/$APP"

echo "=== User .desktop ==="
check "$HOME/.local/share/applications/$APP.desktop"

echo "=== System .desktop ==="
check "/usr/share/applications/$APP.desktop"
check "/usr/local/share/applications/$APP.desktop"

echo "=== Icon (user) ==="
check "$HOME/.local/share/icons/hicolor/256x256/apps/$APP.png"

echo "=== Icon (system) ==="
check "/usr/share/icons/hicolor/256x256/apps/$APP.png"
check "/usr/local/share/icons/hicolor/256x256/apps/$APP.png"

echo "=== Desktop shortcut ==="
check "$HOME/Desktop/$APP.desktop"

echo "=== Udev rule ==="
check "/etc/udev/rules.d/99-rumble-checker.rules"

echo "=== Config / state ==="
check "$HOME/.config/$APP"
check "$HOME/.cache/$APP"
check "$HOME/.local/state/$APP"

echo "=== Package (pacman) ==="
pacman -Q "$APP" 2>/dev/null || echo "  clean"

echo "=== Package (flatpak) ==="
flatpak list --app 2>/dev/null | grep -i "$APP" || echo "  clean"

echo "=== Debug / build leftovers ==="
check "/usr/src/debug/$APP"
check "/usr/src/$APP"

echo ""
if [ "$FOUND" -eq 1 ]; then
    echo "⚠ Leftovers found — see above."
else
    echo "✓ All clean."
fi
