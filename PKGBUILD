pkgname=rumble-checker
pkgver=1.0.0
pkgrel=1
pkgdesc="Linux controller diagnostic - detect gamepads, test rumble, fix permissions"
arch=(x86_64)
url="https://github.com/Modman247/rumble-checker"
license=(MIT)
depends=(python-evdev tk)
source=(
    "https://github.com/Modman247/rumble-checker/releases/download/v${pkgver}/rumble-checker"
    "https://github.com/Modman247/rumble-checker/raw/main/rumble-checker.desktop"
    "https://github.com/Modman247/rumble-checker/raw/main/rumble-checker.png"
)

package() {
    install -Dm755 "rumble-checker" "${pkgdir}/usr/local/bin/rumble-checker"
    install -Dm644 "rumble-checker.desktop" "${pkgdir}/usr/share/applications/rumble-checker.desktop"
    install -Dm644 "rumble-checker.png" "${pkgdir}/usr/share/icons/hicolor/256x256/apps/rumble-checker.png"
}
sha256sums=('6d1e0ba07a19ead542134ed7fb4869f19787b78e0af4d7a34465b8c1fddd1daf'
            '641bdea8e5353f8616fbfd4572ea76c4dabccdc6d889e6bf179f7389495808b7'
            '2412434136383a43c5eaf0449012b87ff8447bd0c4bb1a19c79f13dab1aa6a62')
