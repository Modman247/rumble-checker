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

echo "=== Project dir ==="
check "$HOME/Desktop/rumble-checker-v2-final"
check "$HOME/rumble-checker-v2-final"

echo "=== Udev rule ==="
check "/etc/udev/rules.d/99-rumble-checker.rules"

echo "=== User .desktop ==="
check "$HOME/.local/share/applications/$APP.desktop"

echo "=== System .desktop ==="
check "/usr/share/applications/$APP.desktop"
check "/usr/local/share/applications/$APP.desktop"

echo "=== Icon (user) ==="
check "$HOME/.local/share/icons/hicolor/256x256/apps/$APP.png"

echo "=== Icon (system) ==="
check "/usr/share/icons/hicolor/256x256/apps/$APP.png"

echo "=== Desktop shortcut ==="
check "$HOME/Desktop/$APP.desktop"

echo "=== Input group ==="
if getent group input | grep -q "$USER"; then
    echo "  FOUND: $USER in input group"
    FOUND=1
else
    echo "  clean"
fi

echo "=== Package (pacman) ==="
pacman -Q "$APP" 2>/dev/null || echo "  clean"

echo "=== Package (AUR) ==="
pacman -Qs "$APP" 2>/dev/null | grep -v "^$" || echo "  clean"

echo ""
if [ "$FOUND" -eq 1 ]; then
    echo "⚠ Leftovers found — see above."
else
    echo "✓ All clean."
fi
