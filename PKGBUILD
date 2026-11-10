pkgname=rumble-checker
pkgver=2.0.0
pkgrel=1
pkgdesc="Linux controller diagnostic tool - rumble, polling, drift, permissions"
arch=(any)
url="https://github.com/Modman247/rumble-checker"
license=(MIT)
depends=(python python-evdev)
optdepends=(python-dbus:"battery reading on some devices")
source=("$pkgname-$pkgver.tar.gz::https://github.com/Modman247/rumble-checker/archive/refs/tags/v2.0.tar.gz")
sha256sums=('SKIP')

package() {
    cd "$srcdir/rumble-checker-2.0"

    install -Dm644 backend.py "$pkgdir/usr/lib/rumble-checker/backend.py"
    install -Dm644 tk_app.py "$pkgdir/usr/lib/rumble-checker/tk_app.py"
    install -Dm644 cli.py "$pkgdir/usr/lib/rumble-checker/cli.py"
    install -Dm644 sfx.py "$pkgdir/usr/lib/rumble-checker/sfx.py"
    install -Dm644 controllers.json "$pkgdir/usr/lib/rumble-checker/controllers.json"
    install -Dm644 rumble-checker-icon.png "$pkgdir/usr/lib/rumble-checker/rumble-checker-icon.png"

    install -Dm755 /dev/null "$pkgdir/usr/bin/rumble-checker"
    printf '#!/bin/sh\ncd /usr/lib/rumble-checker\nexec python3 tk_app.py "$@"\n' > "$pkgdir/usr/bin/rumble-checker"

    install -Dm755 /dev/null "$pkgdir/usr/bin/rumble-checker-cli"
    printf '#!/bin/sh\ncd /usr/lib/rumble-checker\nexec python3 cli.py "$@"\n' > "$pkgdir/usr/bin/rumble-checker-cli"

    install -Dm644 rumble-checker.desktop "$pkgdir/usr/share/applications/rumble-checker.desktop"
    sed -i 's|^Exec=.*|Exec=/usr/bin/rumble-checker|' "$pkgdir/usr/share/applications/rumble-checker.desktop"
    sed -i 's|^Icon=.*|Icon=rumble-checker|' "$pkgdir/usr/share/applications/rumble-checker.desktop"

    install -Dm644 rumble-checker.png "$pkgdir/usr/share/icons/hicolor/256x256/apps/rumble-checker.png"
}
