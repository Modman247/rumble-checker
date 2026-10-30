# Rumble Checker

Linux controller diagnostic tool. Detects gamepads, shows vendor:product ID,
tests force feedback, displays controller mode (XInput/DInput/PS4/etc.),
reads battery level, and fixes udev permission issues — all in one GUI.

![Rumble Checker](screenshot.png)   

## Requirements

- `python-evdev` (`sudo pacman -S python-evdev`)

## Install

### Quick (Recommended)

Download `rumble-checker` and `install.sh` from the [latest release](https://github.com/Modman247/rumble-checker/releases), put them in the same folder, navigate to the folder through cli and make install.sh executable by chmod +x install.sh then run ./install.sh

chmod +x install.sh
./install.sh

### Arch Linux (AUR)

yay -S rumble-checker

Manual
sudo pacman -S python-evdev
wget https://github.com/Modman247/rumble-checker/releases/download/v1.0.0/rumble-checker
chmod +x rumble-checker && ./rumble-checker

Features

Detects all connected gamepads
Shows vendor:product ID, controller mode, battery level
Tests rumble with adjustable duration
Fixes udev permissions (adds input group, writes rules by vendor:product)
Works with 8BitDo, Xbox, PlayStation controllers

> **Note:** Battery level is read via the kernel's HID Battery Status service. It will not work with 8BitDo controllers using their proprietary Bluetooth reporting protocol (e.g., when in 8BitDo-specific modes that bypass standard HID battery reporting).

Modes Detected

Mode	                                Driver
XInput                              (Xbox 360/One) xpad
HID / DirectInput (Native)	        hid-generic
PlayStation (DS4/DualSense)	        hid-playstation
Steam Input	                        hid-steam

8BitDo Modes

Button Combo	       Mode	          Vendor:Product
SHARE + UP	         XInput	        2dc8:3106
SHARE + LEFT	       DInput         (Native) 2dc8:3105
SHARE + RIGHT	       Mac	          054c:05c4
SHARE + DOWN	       PSC	          054c:0cda
SHARE + UP + LEFT	   Genesis	      0079:0011

Made by Modman247
