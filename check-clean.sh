#!/usr/bin/env bash
echo "=== Binary ==="
which rumble-checker 2>/dev/null || echo "clean"
ls /usr/local/bin/rumble-checker 2>/dev/null || echo "clean"
ls /usr/bin/rumble-checker 2>/dev/null || echo "clean"

echo "=== User .desktop ==="
ls ~/.local/share/applications/rumble-checker.desktop 2>/dev/null || echo "clean"

echo "=== System .desktop ==="
ls /usr/share/applications/rumble-checker.desktop 2>/dev/null || echo "clean"
ls /usr/local/share/applications/rumble-checker.desktop 2>/dev/null || echo "clean"

echo "=== Icon (user) ==="
ls ~/.local/share/icons/hicolor/256x256/apps/rumble-checker.png 2>/dev/null || echo "clean"

echo "=== Icon (system) ==="
ls /usr/share/icons/hicolor/256x256/apps/rumble-checker.png 2>/dev/null || echo "clean"

echo "=== Desktop shortcut ==="
rm -f "$HOME/Desktop/rumble-checker.desktop"
ls ~/Desktop/rumble-checker.desktop 2>/dev/null || echo "clean"

echo "=== Package (RPM) ==="
rpm -q rumble-checker 2>/dev/null || echo "clean"

echo "=== Package (pacman) ==="
pacman -Q rumble-checker 2>/dev/null || echo "clean"

echo "=== Debug leftovers ==="
ls /usr/src/debug/rumble-checker 2>/dev/null || echo "clean"
chmod +x check-clean.sh
