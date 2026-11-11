#!/usr/bin/env python3
"""Rumble Checker v2 — backend. No GUI imports."""

import os
import re
import time
import stat
import glob
import json
import pwd
import grp
import subprocess
from dataclasses import dataclass
from typing import Callable

from evdev import InputDevice, ecodes, ff

# --- BlueZ battery (optional) ---
try:
    import dbus as _dbus
    _HAS_DBUS = True
except ImportError:
    _HAS_DBUS = False


# ─── DATA CLASSES ───────────────────────────────────────────────

@dataclass
class DriftResult:
    axis_name: str
    neutral: int
    mean: float
    max_delta: float
    is_drifting: bool


# ─── MODE DETECTION ─────────────────────────────────────────────

DRIVER_TO_MODE = {
    "xpad": "XInput",
    "hid-xpadneo": "XInput",
    "hid-playstation": "PlayStation Native",
    "playstation": "PlayStation Native",
    "hid-sony": "PlayStation Native",
    "sony": "PlayStation Native",
    "hid-nintendo": "Switch Pro",
    "nintendo": "Switch Pro",
    "hid-steam": "Steam Input",
    "hid-generic": "DInput / Native",
    "dragonrise": "DInput / Native",
}

# VID:PID → pretty brand name ONLY. Cosmetic. Falls back to device name.
BRAND_LABELS = {
    "057e:2009": "MAYFLASH Magic NS2",
    "33df:0011": "MAYFLASH Receiver",
    "045e:028e": "Xbox 360",
    "045e:02fd": "Xbox One",
    "045e:02e0": "Xbox One S",
    "045e:0b13": "Xbox One",
    "054c:09cc": "DS4 (Slim)",
    "054c:0cda": "PS Classic",
    "054c:05c4": "DS4 (Original)",
    "054c:0ce6": "DualSense",
    "057e:2009": "Switch Pro",
    "057e:200e": "Joy-Con L",
    "057e:200f": "Joy-Con R",
    "2dc8:3106": "8BitDo",
    "2dc8:3105": "8BitDo",
}

# Name hints for 8BitDo detection (catches dongle pass-through)
EBITDO_NAME_HINTS = ("8bitdo",)


def get_controller_mode(sysfs_path: str) -> str:
    if not sysfs_path:
        return "unknown"
    full_path = "/sys" + sysfs_path
    device_dir = os.path.dirname(os.path.dirname(full_path))
    driver_link = os.path.join(device_dir, "driver")
    if os.path.islink(driver_link):
        return os.path.basename(os.readlink(driver_link))
    return "unknown"


# Load the controller DB (confirmed devices). Authoritative when present.
try:
    _DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "controllers.json")
    CONTROLLERS = json.load(open(_DB_PATH))
except Exception:
    CONTROLLERS = {}


def get_mode_display(vendor: str, product: str, driver: str, name: str = "") -> tuple[str, str]:
    """Return (brand, mode). Confirmed JSON entry wins; else driver/name fallback."""
    mode = DRIVER_TO_MODE.get(driver, driver if driver != "unknown" else "Unknown")
    vp = f"{vendor}:{product}"

    # Confirmed device in the JSON DB -> authoritative
    entry = CONTROLLERS.get(vp)
    if entry and "name" in entry and "mode" in entry:
        return entry["name"], entry["mode"]

    # 8BitDo detection via name (catches dongle pass-through, all Magic modes)
    name_lower = name.lower()
    if any(h in name_lower for h in EBITDO_NAME_HINTS):
        return "8BitDo", mode

    # Brand from VID:PID table, fallback to raw name
    brand = BRAND_LABELS.get(vp, name)
    return brand, mode


# ─── DEVICE ENUMERATION ─────────────────────────────────────────

def parse_input_devices() -> list[Device]:
    devices = []
    with open('/proc/bus/input/devices') as f:
        content = f.read()
    blocks = re.split(r'\n\n', content)
    for block in blocks:
        lines = block.strip().split('\n')
        name = handlers = ff_str = vendor = product = sysfs = uniq = ""
        for line in lines:
            if line.startswith('N: Name='):
                name = line.split('Name=', 1)[1]
            elif line.startswith('H: Handlers='):
                handlers = line.split('Handlers=', 1)[1]
            elif line.startswith('B: FF='):
                ff_str = line.split('FF=', 1)[1]
            elif line.startswith('I:'):
                if 'Vendor=' in line:
                    vendor = line.split('Vendor=')[1].split()[0]
                if 'Product=' in line:
                    product = line.split('Product=')[1].split()[0]
            elif line.startswith('S: Sysfs='):
                sysfs = line.split('Sysfs=', 1)[1]
            elif line.startswith('U: Uniq='):
                uniq = line.split('Uniq=', 1)[1]

        if 'js' not in handlers and not ff_str:
            continue
        if not name:
            continue

        event_match = re.search(r'event(\d+)', handlers)
        event_node = f"/dev/input/event{event_match.group(1)}" if event_match else ""

        driver = get_controller_mode(sysfs)
        brand, mode = get_mode_display(vendor, product, driver, name)
        battery = get_battery_level(uniq, sysfs)
        fw = None
        connection = _get_connection(sysfs)
        # Dongle-only hardware masquerading as USB (e.g. F710 Nano
        # Receiver presents the pad's own VID:PID). Trust the DB.
        if connection == "USB":
            _e = CONTROLLERS.get(f"{vendor}:{product}")
            if _e and "Dongle" in _e.get("conn", "") and "USB" not in _e.get("conn", ""):
                connection = "Dongle"

        devices.append(Device(
            name=name,
            event_path=event_node,
            vendor=vendor,
            product=product,
            sysfs=sysfs,
            uniq=uniq,
            has_ff=bool(ff_str),
            driver=driver,
            mode=mode,
            brand=brand,
            battery=battery,
            firmware=fw,
            connection=connection,
        ))
    return devices


def _get_connection(sysfs_path: str) -> str:
    """Determine connection type from sysfs path.

    BT:     "uhid" in path (Bluetooth HID)
    USB:    USB parent VID matches HID device VID (direct cable)
    Dongle: USB parent VID differs from HID device VID (2.4G receiver)
    """
    if not sysfs_path:
        return "?"
    if "uhid" in sysfs_path:
        return "BT"
    if "/usb" not in sysfs_path:
        return "USB"

    # Distinguish direct USB cable from 2.4G dongle:
    # 1. If path contains 0003:VID:PID → compare to USB parent idVendor.
    #    Match = direct cable. Mismatch = dongle.
    # 2. If path has NO 0003:VID:PID (e.g. 8BitDo dongle virtual devices)
    #    → check USB parent idVendor against known dongle VIDs.
    _known_dongle_vids = {'2dc8'}  # 8BitDo
    try:
        parts = sysfs_path.split("/")
        usb_dev = None
        for p in parts:
            if re.match(r'^\d+-\d+$', p):
                usb_dev = p
                break
        if not usb_dev:
            return "USB"

        vid_file = f"/sys/bus/usb/devices/{usb_dev}/idVendor"
        pid_file = f"/sys/bus/usb/devices/{usb_dev}/idProduct"
        if not os.path.isfile(vid_file):
            return "USB"
        with open(vid_file) as f:
            usb_vid = f.read().strip().lower()
        usb_pid = ""
        if os.path.isfile(pid_file):
            with open(pid_file) as f:
                usb_pid = f.read().strip().lower()

        m = re.search(r'0003:([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})', sysfs_path)
        if m:
            hid_vid = m.group(1).lower()
            hid_pid = m.group(2).lower()
            if usb_vid != hid_vid:
                return "Dongle"
            if usb_pid and usb_pid != hid_pid:
                return "Dongle"
            return "USB"
        else:
            # No HID VID in path — check if USB parent is a known dongle
            if usb_vid in _known_dongle_vids:
                return "Dongle"
            return "USB"
    except Exception:
        pass
    return "USB"

def _fmt_battery(ps_dir: str):
    """Return 'NN%' or 'NN% ⚡' (charging/full), or None if unreadable."""
    cap_file = os.path.join(ps_dir, "capacity")
    if not os.path.exists(cap_file):
        return None
    try:
        val = open(cap_file).read().strip()
        status_file = os.path.join(ps_dir, "status")
        if os.path.exists(status_file):
            st = open(status_file).read().strip()
            if st in ("Charging", "Full"):
                return f"{val}% \u26a1"
        return f"{val}%"
    except Exception:
        return None


def get_battery_level(uniq: str, sysfs_path: str) -> str | None:
    if uniq:
        mac_lower = uniq.lower()
        # DS4 / DualSense (hid-playstation driver)
        ps_entry = f"/sys/class/power_supply/ps-controller-battery-{mac_lower}"
        if os.path.isdir(ps_entry):
            b = _fmt_battery(ps_entry)
            if b:
                return b
        # DS3 (hid-sony driver) — different filename prefix
        sony_entry = f"/sys/class/power_supply/sony_controller_battery_{mac_lower}"
        if os.path.isdir(sony_entry):
            b = _fmt_battery(sony_entry)
            if b:
                return b
    if sysfs_path:
        match = re.search(r'input/input(\d+)', sysfs_path)
        if match:
            ps_link = f"/sys/class/input/input{match.group(1)}/power_supply"
            if os.path.islink(ps_link):
                ps_path = os.path.realpath(ps_link)
                b = _fmt_battery(ps_path)
                if b:
                    return b
    ps_base = "/sys/class/power_supply"
    if os.path.isdir(ps_base):
        for entry in os.listdir(ps_base):
            entry_path = os.path.join(ps_base, entry)
            cap_file = os.path.join(entry_path, "capacity")
            if not os.path.exists(cap_file):
                continue
            dev_link = os.path.join(entry_path, "device")
            if os.path.islink(dev_link):
                real = os.path.realpath(dev_link)
                if sysfs_path and sysfs_path.lstrip("/") in real:
                    try:
                        return f"{open(cap_file).read().strip()}%"
                    except Exception:
                        pass
    return None


# ─── FIRMWARE ───────────────────────────────────────────────────

def _find_hidraw(vendor: str, product: str, phys: str = "") -> str | None:
    """Find /dev/hidraw* matching a device.
    USB: match idVendor/idProduct files.
    BT (uhid): match VID:PID in the resolved device path.
    """
    # Uppercase for sysfs path matching (e.g. "054C:09CC")
    vp_upper = f"{vendor.upper()}:{product.upper()}"
    for hidraw in glob.glob("/dev/hidraw*"):
        try:
            name = os.path.basename(hidraw)
            # Method 1: USB — check idVendor/idProduct files
            sysfs_path = f"/sys/class/hidraw/{name}/device"
            if os.path.isdir(sysfs_path):
                vid_file = os.path.join(sysfs_path, "idVendor")
                if os.path.exists(vid_file):
                    vid = open(vid_file).read().strip()
                    pid = open(os.path.join(sysfs_path, "idProduct")).read().strip()
                    if vid == vendor and pid == product:
                        return hidraw
            # Method 2: BT/uhid — VID:PID is in the resolved path
            # e.g. /sys/devices/virtual/misc/uhid/0005:054C:09CC.0065
            resolved = os.path.realpath(f"/sys/class/hidraw/{name}/device")
            if vp_upper in resolved.upper():
                return hidraw
        except Exception:
            continue
    return None

def get_firmware(vendor: str, product: str, name: str = "", phys: str = "") -> str | None:
    if vendor == "054c" and product in ("05c4", "09cc"):
        return _read_ds4_fw(vendor, product, phys)
    if vendor == "2dc8":
        return _read_8bitdo_fw(vendor, product, phys)
    return None


def _read_ds4_fw(vendor: str, product: str, phys: str = "") -> str | None:
    hidraw = _find_hidraw(vendor, product, phys)
    if not hidraw:
        return None
    try:
        with open(hidraw, "rb") as f:
            data = f.read(64)
        major, minor, patch = data[3], data[4], data[5]
        # Sanity check: valid DS4 fw is like 3.1.0, 3.2.0, etc.
        if major > 99 or minor > 99 or patch > 99:
            return None
        return f"{major}.{minor}.{patch}"
    except Exception:
        return None


def _read_8bitdo_fw(vendor: str, product: str, phys: str = "") -> str | None:
    hidraw = _find_hidraw(vendor, product, phys)
    if not hidraw:
        return None
    try:
        cmd = bytes([0x81, 0x05, 0x00, 0x21, 0x01])
        with open(hidraw, "r+b") as f:
            f.write(cmd)
            f.flush()
            time.sleep(0.05)
            reply = f.read(64)
        if reply[0] == 0x82:
            return f"{reply[2]}.{reply[3]}"
    except Exception:
        pass
    return None


def get_latest_8bitdo_fw(type_id: int) -> str | None:
    cache_dir = os.path.expanduser("~/.cache/rumble-checker")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "fw.json")

    if os.path.exists(cache_file):
        try:
            cache = json.load(open(cache_file))
            if time.time() - cache.get("ts", 0) < 86400 and str(type_id) in cache.get("data", {}):
                return cache["data"][str(type_id)]
        except Exception:
            pass

    try:
        import urllib.request
        req = urllib.request.Request(
            "http://dl.8bitdo.com:8080/firmware/select",
            data=b"",
            headers={"Type": str(type_id), "Beta": "0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get("msgState") == 1 and data.get("list"):
            latest = max(data["list"], key=lambda x: x.get("date", ""))
            version = str(latest["version"])
            cache = {}
            if os.path.exists(cache_file):
                try:
                    cache = json.load(open(cache_file))
                except Exception:
                    pass
            cache.setdefault("data", {})[str(type_id)] = version
            cache["ts"] = time.time()
            json.dump(cache, open(cache_file, "w"))
            return version
    except Exception:
        pass
    return None


# ─── RUMBLE ─────────────────────────────────────────────────────

def test_rumble(event_path: str, motor: str = "both", intensity: int = 255,
                duration_ms: int = 500) -> str:
    dev = InputDevice(event_path)
    caps = dev.capabilities()
    if ecodes.EV_FF not in caps:
        dev.close()
        return "NO_FF"

    # evdev expects 0-65535; our API is 0-255, scale up
    strong = (intensity * 257) if motor in ("left", "both") else 0
    weak = (intensity * 257) if motor in ("right", "both") else 0

    rumble = ff.Rumble(strong_magnitude=strong, weak_magnitude=weak)
    effect = ff.Effect(
        ecodes.FF_RUMBLE, -1, 0,
        ff.Trigger(0, 0),
        ff.Replay(duration_ms, 0),
        ff.EffectType(ff_rumble_effect=rumble),
    )
    try:
        effect_id = dev.upload_effect(effect)
        dev.write(ecodes.EV_FF, effect_id, 1)
        time.sleep(duration_ms / 1000 + 0.1)
        dev.erase_effect(effect_id)
        dev.close()
        return "OK"
    except Exception as e:
        dev.close()
        return f"ERROR: {e}"


def pattern_pulse(event_path: str, motor: str = "both", intensity: int = 255,
                  count: int = 5, interval_ms: int = 100, pulse_ms: int = 80) -> str:
    for _ in range(count):
        r = test_rumble(event_path, motor, intensity, pulse_ms)
        if r != "OK":
            return r
        time.sleep(interval_ms / 1000)
    return "OK"


def pattern_alternate(event_path: str, intensity: int = 255,
                      count: int = 5, interval_ms: int = 100, pulse_ms: int = 80) -> str:
    for _ in range(count):
        r = test_rumble(event_path, "left", intensity, pulse_ms)
        if r != "OK":
            return r
        time.sleep(interval_ms / 1000)
        r = test_rumble(event_path, "right", intensity, pulse_ms)
        if r != "OK":
            return r
        time.sleep(interval_ms / 1000)
    return "OK"


def pattern_ramp(event_path: str, motor: str = "both", duration_ms: int = 1000) -> str:
    dev = InputDevice(event_path)
    caps = dev.capabilities()
    if ecodes.EV_FF not in caps:
        dev.close()
        return "NO_FF"

    steps = 20
    step_ms = max(duration_ms // steps, 10)
    try:
        for i in range(steps * 2):
            if i < steps:
                intensity = int(255 * i / (steps - 1))
            else:
                intensity = int(255 * (steps * 2 - i - 1) / (steps - 1))
            strong = (intensity * 257) if motor in ("left", "both") else 0
            weak = (intensity * 257) if motor in ("right", "both") else 0
            rumble = ff.Rumble(strong_magnitude=strong, weak_magnitude=weak)
            effect = ff.Effect(
                ecodes.FF_RUMBLE, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(step_ms, 0),
                ff.EffectType(ff_rumble_effect=rumble),
            )
            eid = dev.upload_effect(effect)
            dev.write(ecodes.EV_FF, eid, 1)
            time.sleep(step_ms / 1000)
            dev.erase_effect(eid)
        dev.close()
        return "OK"
    except Exception as e:
        dev.close()
        return f"ERROR: {e}"


# ─── DRIFT DETECTION ────────────────────────────────────────────

def detect_drift(event_path: str, duration_s: float = 2.0,
                 threshold: int = 5000) -> list[DriftResult]:
    import select
    try:
        dev = InputDevice(event_path)
    except PermissionError:
        print(f"ERROR: Cannot read {event_path} — access denied. Use 'fix' first.")
        return []
    except OSError as e:
        print(f"ERROR: Cannot open {event_path}: {e}")
        return []
    caps = dev.capabilities()
    abs_axes = caps.get(ecodes.EV_ABS, {})
    if not abs_axes:
        dev.close()
        return []

    axis_samples: dict[int, list[int]] = {a: [] for a in abs_axes}
    deadline = time.time() + duration_s
    dev.grab()
    try:
        while time.time() < deadline:
            ready, _, _ = select.select([dev.fd], [], [], 0.05)
            if ready:
                event = dev.read_one()
                if event and event.type == ecodes.EV_ABS:
                    axis_samples.setdefault(event.code, []).append(event.value)
    finally:
        dev.ungrab()
        dev.close()

    results = []
    axis_names = {
        ecodes.ABS_X: "ABS_X", ecodes.ABS_Y: "ABS_Y",
        ecodes.ABS_RX: "ABS_RX", ecodes.ABS_RY: "ABS_RY",
        ecodes.ABS_THROTTLE: "ABS_THROTTLE", ecodes.ABS_RZ: "ABS_RZ",
        ecodes.ABS_HAT0X: "ABS_HAT0X", ecodes.ABS_HAT0Y: "ABS_HAT0Y",
    }
    for code, samples in axis_samples.items():
        if not samples:
            continue
        neutral = 0
        mean = sum(samples) / len(samples)
        max_delta = max(abs(s - neutral) for s in samples)
        results.append(DriftResult(
            axis_name=axis_names.get(code, f"ABS_{code}"),
            neutral=neutral,
            mean=mean,
            max_delta=max_delta,
            is_drifting=max_delta > threshold,
        ))
    return results


# ─── HOT-PLUG MONITORING ────────────────────────────────────────

def monitor_devices(callback: Callable[[str, str], None], poll_interval: float = 3.0):
    known: set[str] = set()
    while True:
        devices = parse_input_devices()
        current = {d.name for d in devices}
        for name in current - known:
            callback("added", name)
        for name in known - current:
            callback("removed", name)
        known = current
        time.sleep(poll_interval)


# ─── ACCESS / PERMISSIONS ───────────────────────────────────────

def is_flatpak() -> bool:
    return os.path.exists("/run/host/user") or "container" in os.environ.get("container", "")


def is_in_input_group() -> bool:
    try:
        groups = grp.getgrnam('input').gr_mem
        return pwd.getpwuid(os.getuid()).pw_name in groups
    except KeyError:
        return False


def is_readable(event_path: str) -> bool:
    if is_in_input_group():
        return True
    try:
        import stat as stat_mod
        st = os.stat(event_path)
        return bool(st.st_mode & stat_mod.S_IROTH)
    except OSError:
        return False


def access_diagnostic(event_path: str, vendor: str, product: str) -> dict:
    info = {
        "device": event_path,
        "permissions": "",
        "owner": "",
        "group": "",
        "user": pwd.getpwuid(os.getuid()).pw_name,
        "uid": os.getuid(),
        "in_input_group": is_in_input_group(),
        "readable": is_readable(event_path),
        "flatpak": is_flatpak(),
        "udev_rule": (
            f'SUBSYSTEM=="input", ATTRS{{idVendor}}=="{vendor}", '
            f'ATTRS{{idProduct}}=="{product}", '
            f'MODE="0666", ENV{{ID_INPUT_JOYSTICK}}="1"'
        ),
        "rule_file": "/etc/udev/rules.d/99-rumble-checker.rules",
        "rule_exists": False,
    }

    try:
        st = os.stat(event_path)
        info["permissions"] = stat.filemode(st.st_mode)
        info["owner"] = pwd.getpwuid(st.st_uid).pw_name
        info["group"] = grp.getgrgid(st.st_gid).gr_name
    except Exception as e:
        info["permissions"] = f"error: {e}"

    rule_file = info["rule_file"]
    if os.path.exists(rule_file):
        try:
            content = open(rule_file).read()
            info["rule_exists"] = vendor in content and product in content
        except Exception:
            pass

    return info


def fix_permissions(event_path: str, name: str, vendor: str, product: str) -> tuple[bool, str]:
    if is_flatpak():
        return True, ("Running in Flatpak — device access handled by sandbox.\n"
                       "If DENIED, device likely not connected or driver not exposing it.")

    username = pwd.getpwuid(os.getuid()).pw_name
    rule_path = "/etc/udev/rules.d/99-rumble-checker.rules"
    rule_line = (
        f'SUBSYSTEM=="input", ATTRS{{idVendor}}=="{vendor}", '
        f'ATTRS{{idProduct}}=="{product}", '
        f'MODE="0666", ENV{{ID_INPUT_JOYSTICK}}="1"')

    cmd_parts = []
    if not is_in_input_group():
        cmd_parts.append(f"usermod -aG input {username}")
    cmd_parts.append(
        f'grep -q "idVendor.*{vendor}.*idProduct.*{product}" {rule_path} 2>/dev/null || '
        f'echo "{rule_line}" >> {rule_path}; '
        f'udevadm control --reload-rules 2>/dev/null; '
        f'udevadm trigger --subsystem-match=input 2>/dev/null; true')

    combined = " && ".join(cmd_parts)

    try:
        result = subprocess.run(
            ['pkexec', 'bash', '-c', combined],
            capture_output=True, text=True, timeout=30)
        messages = []
        if not is_in_input_group():
            if result.returncode == 0:
                messages.append("✓ Added to input group (log out/in required)")
            else:
                messages.append(f"✗ usermod failed: {result.stderr.strip()}")
        if result.returncode == 0:
            messages.append(f"✓ Udev rule written + reloaded for {vendor}:{product}")
        else:
            messages.append(f"✗ Udev rule failed: {result.stderr.strip()}")

        readable = is_readable(event_path)
        if readable:
            messages.append("✓ Device is now readable")
        else:
            messages.append("✗ Still not readable — log out and back in")

        return readable, "\n".join(messages)
    except FileNotFoundError:
        return False, f"✗ pkexec not found. Run manually:\n  sudo usermod -aG input $USER"
    except Exception as e:
        return False, f"✗ Error: {e}"


def remove_access(vendor: str, product: str) -> tuple[bool, str]:
    username = pwd.getpwuid(os.getuid()).pw_name
    rule_file = "/etc/udev/rules.d/99-rumble-checker.rules"
    in_group = is_in_input_group()

    cmd_parts = []
    if in_group:
        cmd_parts.append(f"gpasswd -d {username} input")
    cmd_parts.append(f"grep -v 'idVendor.*{vendor}.*idProduct.*{product}' {rule_file} > /tmp/rc_tmp 2>/dev/null && mv /tmp/rc_tmp {rule_file} 2>/dev/null || true")
    cmd_parts.append("udevadm control --reload-rules 2>/dev/null || true")
    cmd_parts.append("udevadm trigger --subsystem-match=input 2>/dev/null || true")

    combined = " && ".join(cmd_parts)

    try:
        result = subprocess.run(
            ['pkexec', 'bash', '-c', combined],
            capture_output=True, text=True, timeout=20)
        messages = []
        if in_group:
            if result.returncode == 0:
                messages.append("✓ Removed from input group (log out/in required)")
            else:
                messages.append(f"✗ gpasswd failed: {result.stderr.strip()}")
        else:
            messages.append("Already not in input group")
        if result.returncode == 0:
            messages.append(f"✓ Udev rule removed + reloaded for {vendor}:{product}")
        else:
            messages.append(f"✗ Udev step failed: {result.stderr.strip()}")
        return True, "\n".join(messages)
    except FileNotFoundError:
        return False, "✗ pkexec not found. Run manually:\n  sudo gpasswd -d $USER input"
    except Exception as e:
        return False, f"✗ Error: {e}"


# ─── JSON REPORT ────────────────────────────────────────────────

def full_report() -> dict:
    devices = parse_input_devices()
    report = {"devices": []}
    for d in devices:
        entry = {
            "name": d.name,
            "event": d.event_path,
            "vendor": d.vendor,
            "product": d.product,
            "id": f"{d.vendor}:{d.product}",
            "driver": d.driver,
            "mode": d.mode,
            "brand": d.brand,
            "battery": d.battery,
            "firmware": d.firmware,
            "connection": d.connection,
            "ff": d.has_ff,
            "access": "OK" if (d.event_path and is_readable(d.event_path)) else "DENIED",
            "rumble": {},
            "drift": [],
        }
        if d.has_ff and d.event_path:
            entry["rumble"]["left"] = test_rumble(d.event_path, "left", 255, 200)
            entry["rumble"]["right"] = test_rumble(d.event_path, "right", 255, 200)
            entry["rumble"]["both"] = test_rumble(d.event_path, "both", 255, 200)
        drift = detect_drift(d.event_path) if d.event_path else []
        entry["drift"] = [
            {"axis": r.axis_name, "mean": round(r.mean, 1),
             "max_delta": r.max_delta, "drifting": r.is_drifting}
            for r in drift
        ]
        report["devices"].append(entry)
    return report

def get_battery_bluetooth(name, phys=None):
    """Read battery % via BlueZ D-Bus (GATT Battery Service)."""
    if not _HAS_DBUS:
        return None
    try:
        bus = _dbus.SystemBus()
        mgr = bus.get_object("org.bluez", "/")
        objects = mgr.GetManagedObjects()
        for path, props in objects.items():
            if "org.bluez.Battery1" not in props:
                continue
            bt_name = props.get("org.bluez.Device1", {}).get("Name", "")
            if name and bt_name and (name in bt_name or bt_name in name):
                pct = props["org.bluez.Battery1"].get("Percentage")
                if pct is not None:
                    return int(pct)
        return None
    except Exception:
        return None
@dataclass
class Device:
    name: str
    event_path: str
    vendor: str
    product: str
    sysfs: str
    uniq: str
    has_ff: bool
    driver: str
    mode: str
    brand: str
    battery: str | None = None
    firmware: str | None = None
    connection: str = "USB"


_measured_rates: dict[str, int] = {}


def get_polling_rate(node: str, conn: str) -> tuple[str, str]:
    """Return (rate_str, detail_str) for a device node.

    USB: reads bInterval from sysfs interrupt endpoints.
    BT:  protocol-locked at 125 Hz (8 ms HID slot).
    Dongle: not measurable from host.
    """
    if conn == "BT":
        return "125 Hz", "Bluetooth HID — protocol-locked, 8 ms slot"

    if conn != "USB":
        return "N/A", "2.4G dongle — link rate internal to dongle firmware"

    import os, glob
    # Resolve sysfs path via /sys/class/input/input{N}/device
    # /dev/input/eventX is a char dev, NOT a symlink to sysfs.
    node_clean = node.split("/")[-1]
    real = None
    for input_dir in glob.glob("/sys/class/input/input*"):
        if os.path.exists(f"{input_dir}/{node_clean}"):
            real = os.path.realpath(f"{input_dir}/device")
            break
    if not real:
        return "N/A", f"could not resolve sysfs path (node={node_clean})"

    # Walk up to find USB device component (pattern: N-M, no colon)
    parts = real.split("/")
    usb_dev = None
    for i, p in enumerate(parts):
        if re.match(r'^\d+-\d+$', p):
            usb_dev = p
            break

    if not usb_dev:
        return "N/A", "no USB parent found in sysfs path"

    dev_path = f"/sys/bus/usb/devices/{usb_dev}"
    if not os.path.isdir(dev_path):
        return "N/A", f"usb device dir not found: {dev_path}"

    # Read speed
    speed = 12  # default full speed
    speed_file = f"{dev_path}/speed"
    if os.path.isfile(speed_file):
        with open(speed_file) as f:
            speed = int(f.read().strip())

    speed_label = {12: "FS", 480: "HS", 5000: "SS", 10000: "SS+"}.get(speed, f"{speed}Mbps")

    # Find interrupt endpoints (ep_8X = IN, skip ep0/ep_80 control)
    best_hz = 0
    best_bi = 0
    for ep_dir in sorted(glob.glob(f"{dev_path}/ep*")):
        ep_name = os.path.basename(ep_dir)
        # Skip control endpoint (ep0 or ep_80)
        if ep_name in ("ep0", "ep_80"):
            continue
        # Prefer IN endpoints (0x80-0xFF)
        try:
            ep_addr = int(ep_name.replace("ep_", "").replace("ep", ""), 16) if "_" in ep_name else int(ep_name.replace("ep", ""), 16)
        except ValueError:
            ep_addr = 0
        if ep_addr and (ep_addr & 0x80) == 0:
            continue  # skip OUT endpoints

        # Try 'interval' file first (newer kernels)
        # Format: "0ms" (not applicable), "1ms", "125us", etc.
        int_file = f"{ep_dir}/interval"
        if os.path.isfile(int_file):
            with open(int_file) as f:
                raw = f.read().strip()
            try:
                if raw.endswith("ms"):
                    interval_us = int(raw[:-2]) * 1000
                elif raw.endswith("us"):
                    interval_us = int(raw[:-2])
                else:
                    interval_us = int(raw)
            except ValueError:
                interval_us = 0
            if interval_us > 0:
                hz = 1_000_000 / interval_us
                if hz > best_hz:
                    best_hz = hz
                    best_bi = interval_us
                continue
            # interval=0 means "use bInterval instead" — fall through

        # Fall back to bInterval
        bi_file = f"{ep_dir}/bInterval"
        if not os.path.isfile(bi_file):
            continue
        with open(bi_file) as f:
            bi = int(f.read().strip())
        if bi == 0:
            continue

        if speed >= 480:
            # High/Super speed: 2^(bi-1) microframes of 125us
            interval_us = (2 ** (bi - 1)) * 125
        else:
            # Full/Low speed: bi milliseconds
            interval_us = bi * 1000

        hz = 1_000_000 / interval_us
        if hz > best_hz:
            best_hz = hz
            best_bi = bi

    if best_hz == 0:
        # Fallback: parse binary descriptors file (no ep_* dirs on some kernels)
        desc_file = f"{dev_path}/descriptors"
        if os.path.isfile(desc_file):
            try:
                import struct as _struct
                with open(desc_file, "rb") as f:
                    data = f.read()
                offset = 18  # skip device descriptor
                while offset + 7 <= len(data):
                    bLength = data[offset]
                    bType = data[offset + 1]
                    if bType == 5 and bLength == 7:
                        addr = data[offset + 2]
                        attrs = data[offset + 3]
                        bi = data[offset + 6]
                        if (attrs & 0x03) == 3 and (addr & 0x80):
                            # Interrupt IN endpoint found
                            if speed >= 480:
                                interval_us = (2 ** (bi - 1)) * 125
                            else:
                                interval_us = bi * 1000
                            if interval_us > 0:
                                best_hz = 1_000_000 / interval_us
                                best_bi = bi
                            break
                        offset += bLength
                    elif bType in (2, 4, 6, 0x04) and bLength >= 9:
                        offset += bLength
                    elif 2 <= bLength <= 40:
                        offset += bLength
                    else:
                        break
            except Exception:
                pass

    if best_hz == 0:
        return "N/A", f"no interrupt endpoints found (speed={speed_label})"

    return f"{best_hz:.0f} Hz", f"bInterval={best_bi}, USB {speed_label}"


def get_evdev_caps(node: str) -> str:
    """Return a formatted string of evdev capabilities for a device node.

    Equivalent to 'evtest --list /dev/input/<node>' but formatted for the report.
    """
    import evdev
    node_clean = node.split("/")[-1]
    try:
        dev = evdev.InputDevice(f"/dev/input/{node_clean}")
    except (OSError, PermissionError) as e:
        return f"  (could not read capabilities: {e})"

    lines = []
    caps = dev.capabilities(verbose=True, absinfo=True)

    # Keys are tuples: ('EV_KEY', 1), ('EV_ABS', 3), ('EV_FF', 21)
    # Items: EV_KEY → (('BTN_A', 'BTN_GAMEPAD', 'BTN_SOUTH'), 304)
    #        EV_ABS → (('ABS_X', 0), AbsInfo(...))
    #        EV_FF  → ('FF_RUMBLE', 80)

    ev_key = ('EV_KEY', 1)
    if ev_key in caps:
        btns = caps[ev_key]
        btn_names = []
        for item in btns:
            if isinstance(item, tuple) and len(item) >= 1:
                n = item[0]
                if isinstance(n, tuple):
                    btn_names.append(n[0])
                elif isinstance(n, str):
                    btn_names.append(n)
            else:
                btn_names.append(str(item))
        gamepad_btns = [b for b in btn_names if b.startswith("BTN_")]
        if gamepad_btns:
            lines.append(f"  Buttons ({len(gamepad_btns)}): {', '.join(sorted(gamepad_btns))}")

    ev_abs = ('EV_ABS', 3)
    if ev_abs in caps:
        axes = caps[ev_abs]
        axis_lines = []
        for item in axes:
            if isinstance(item, tuple) and len(item) >= 2:
                n = item[0]
                info = item[1]
                name = n[0] if isinstance(n, tuple) else str(n)
                if isinstance(info, evdev.AbsInfo):
                    axis_lines.append(
                        f"    {name}: min={info.min} max={info.max} "
                        f"fuzz={info.fuzz} flat={info.flat} res={info.resolution}"
                    )
                else:
                    axis_lines.append(f"    {name}")
        if axis_lines:
            lines.append(f"  Axes ({len(axis_lines)}):")
            lines.extend(axis_lines)

    # FF effects (EV_FF = 0x15)
    ev_ff = ('EV_FF', 21)
    if ev_ff in caps:
        ff = caps[ev_ff]
        ff_names = []
        for item in ff:
            if isinstance(item, tuple) and len(item) >= 1:
                n = item[0]
                ff_names.append(n[0] if isinstance(n, tuple) else str(n))
            else:
                ff_names.append(str(item))
        if ff_names:
            lines.append(f"  FF Effects: {', '.join(sorted(ff_names))}")

    # Input properties
    props = dev.input_props(verbose=True)
    if props:
        prop_names = []
        for item in props:
            if isinstance(item, tuple) and len(item) >= 1:
                n = item[0]
                prop_names.append(n[0] if isinstance(n, tuple) else str(n))
            else:
                prop_names.append(str(item))
        if prop_names:
            lines.append(f"  Properties: {', '.join(prop_names)}")

    dev.close()
    if not lines:
        return "  (no capabilities reported)"
    return "\n".join(lines)


def export_report() -> str:
    """Generate a diagnostic report file. Returns the file path."""
    from datetime import datetime
    import platform

    lines = []
    lines.append('=== RUMBLE CHECKER DIAGNOSTIC REPORT ===')
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('')

    # System
    lines.append('=== SYSTEM ===')
    try:
        lines.append(f'Kernel: {platform.release()}')
    except Exception:
        pass
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if 'PRETTY_NAME' in line:
                    lines.append(f'Distro: {line.split("=", 1)[1].strip().strip(chr(34))}')
                    break
    except Exception:
        pass
    lines.append(f'Python: {platform.python_version()}')
    lines.append('Rumble Checker: v2.0')
    lines.append('')

    # USB
    lines.append('=== USB DEVICES ===')
    try:
        r = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
        _raw = r.stdout.strip().splitlines()
        _known_vids = ('054c', '045e', '2dc8', '046d', '0955', '0e6f',
                       '0079', '20bc', '0f0d', '0ca3', '1235', '2820', '057e')
        _filtered = []
        for _l in _raw:
            _l_lower = _l.lower()
            if any(_v in _l_lower for _v in _known_vids) or 'root' in _l_lower or 'hub' in _l_lower:
                _filtered.append(_l)
        lines.append('\n'.join(_filtered) if _filtered else '(no matching devices)')
    except Exception as e:
        lines.append(f'(lsusb failed: {e})')
    lines.append('')

    # Input devices (filtered: gamepads only — must have ABS or FF)
    lines.append('=== INPUT DEVICES (gamepads only) ===')
    try:
        with open('/proc/bus/input/devices') as f:
            raw = f.read()
        blocks = raw.strip().split('\n\n')
        for block in blocks:
            if ('B: ABS=' in block or 'B: FF=' in block) and 'B: REL=' not in block:
                lines.append(block)
                lines.append('')
    except Exception:
        lines.append('(could not read /proc/bus/input/devices)')
    lines.append('')
    lines.append('=== /dev/input PERMISSIONS ===')
    try:
        r = subprocess.run(['ls', '-la', '/dev/input/'], capture_output=True, text=True, timeout=5)
        lines.append(r.stdout.strip())
    except Exception:
        pass
    lines.append('')

    # Udev rules
    lines.append('=== UDEV RULES (input-related) ===')
    try:
        r = subprocess.run(['udevadm', 'rules'], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if 'input' in line.lower() or 'hidraw' in line.lower():
                lines.append(line)
    except Exception:
        lines.append('(udevadm rules failed)')
    rule_file = '/etc/udev/rules.d/99-rumble-checker.rules'
    if os.path.exists(rule_file):
        lines.append(f'')
        lines.append(f'--- {rule_file} ---')
        lines.append(open(rule_file).read().strip())
    lines.append('')

    # Our scan
    lines.append('=== CONTROLLERS (Rumble Checker scan) ===')
    devices = parse_input_devices()
    for d in devices:
        access = 'OK' if (d.event_path and is_readable(d.event_path)) else 'DENIED'
        lines.append(f'  {d.name} | {d.vendor}:{d.product} | {d.brand} | {d.mode} | '
             f'{d.battery} | {d.has_ff} | {d.connection} | {access}')
        # Polling rate
        if hasattr(d, 'poll_rate'):
            lines.append(f"    Poll: {d.poll_rate} ({d.poll_detail})")
        elif d.connection == 'BT':
            lines.append("    Poll: 125 Hz (Bluetooth HID, protocol-locked)")
        elif d.connection == 'USB':
            pr, pd = get_polling_rate(d.event_path, 'USB')
            lines.append(f"    Poll: {pr} ({pd})")
        else:
            lines.append("    Poll: N/A (2.4G dongle, not measurable from host)")
        # Measured event rate (if user ran Measure during session)
        _node_clean = d.event_path.split("/")[-1]
        if _node_clean in _measured_rates:
            lines.append(f"    Measured: {_measured_rates[_node_clean]} events/s (1s sample)")
        # Evdev capabilities
        caps_str = get_evdev_caps(d.event_path)
        lines.append(caps_str)

    lines.append('')

    # Rumble test results
    lines.append('=== RUMBLE TEST RESULTS ===')
    for d in devices:
        if d.has_ff and d.event_path:
            l = test_rumble(d.event_path, 'left', 255, 200)
            r = test_rumble(d.event_path, 'right', 255, 200)
            b = test_rumble(d.event_path, 'both', 255, 200)
            lines.append(f'  {d.name}: L={l} R={r} Both={b}')
    lines.append('')

    # Drift
    lines.append('=== DRIFT RESULTS ===')
    for d in devices:
        if d.event_path:
            results = detect_drift(d.event_path, duration_s=2.0)
            if results:
                for r in results:
                    st = 'DRIFT' if r.is_drifting else 'OK'
                    lines.append(f'  {d.name} {r.axis_name}: mean={r.mean:.1f} delta={r.max_delta} {st}')
    lines.append('')

    # Bluetooth
    lines.append('=== BLUETOOTH DEVICES ===')
    try:
        r = subprocess.run(['bluetoothctl', 'devices'], capture_output=True, text=True, timeout=5)
        lines.append(r.stdout.strip() or '(none)')
    except Exception:
        lines.append('(bluetoothctl not available)')
    lines.append('')

    # Permissions
    lines.append('=== USER PERMISSIONS ===')
    try:
        r = subprocess.run(['id'], capture_output=True, text=True, timeout=5)
        lines.append(r.stdout.strip())
        r = subprocess.run(['groups'], capture_output=True, text=True, timeout=5)
        lines.append(r.stdout.strip())
    except Exception:
        pass
    lines.append('')

    # Fuser — who is holding each controller's event node
    lines.append('=== DEVICE HOLDERS (fuser) ===')
    try:
        for d in devices:
            if d.event_path:
                r = subprocess.run(['fuser', d.event_path], capture_output=True, text=True, timeout=3)
                holders = (r.stdout + r.stderr).strip()
                if holders:
                    lines.append(f'  {d.event_path} ({d.name}): {holders}')
                else:
                    lines.append(f'  {d.event_path} ({d.name}): (not held)')
        if not any(d.event_path for d in devices):
            lines.append('  (no devices with event nodes)')
    except Exception as e:
        lines.append(f'  (error: {e})')
    lines.append('')

    # Steam status
    lines.append('=== STEAM STATUS ===')
    try:
        r = subprocess.run(['pgrep', '-a', 'steam'], capture_output=True, text=True, timeout=3)
        steam_procs = r.stdout.strip()
        if steam_procs:
            lines.append(f'  Running: {steam_procs.splitlines()[0]}')
        else:
            lines.append('  Not running')
        # Check for Steam virtual pads (28de:11ff)
        r2 = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=3)
        virtual = [l for l in r2.stdout.splitlines() if '28de:11ff' in l]
        if virtual:
            lines.append(f'  Virtual pad(s) detected: {len(virtual)}')
            for v in virtual:
                lines.append(f'    {v.strip()}')
        else:
            lines.append('  No Steam virtual pads (28de:11ff) detected')
    except Exception as e:
        lines.append(f'  (error: {e})')
    lines.append('')

    # Kernel modules (input/hid related)
    lines.append('=== KERNEL MODULES (input/hid) ===')
    try:
        r = subprocess.run(['lsmod'], capture_output=True, text=True, timeout=3)
        mods = [l for l in r.stdout.splitlines()
                if any(k in l for k in ('hid', 'xpad', 'joydev', 'uinput', 'usbhid', 'bt'))]
        if mods:
            for m in mods:
                lines.append(f'  {m.strip()}')
        else:
            lines.append('  (none found)')
    except Exception as e:
        lines.append(f'  (error: {e})')
    lines.append('')

    # Hidraw devices
    lines.append('=== HIDRAW DEVICES ===')
    try:
        r = subprocess.run(['ls', '-la', '/dev/hidraw*'], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                lines.append(f'  {line}')
        else:
            lines.append('  (no hidraw devices)')
    except Exception as e:
        lines.append(f'  (error: {e})')
    lines.append('')

    # Dmesg tail (filtered to input/hid/usb/steam-relevant)
    lines.append('=== DMESSG (last 50 lines, input/hid/usb) ===')
    try:
        r = subprocess.run(['dmesg', '--level=err,warn,info'], capture_output=True, text=True, timeout=5)
        all_lines = r.stdout.strip().splitlines()
        _vids = tuple(d.vendor for d in devices if d.vendor and d.vendor != '0000')
        keywords = ('input', 'hid', 'xpad', 'usb', 'uinput', 'joydev', 'uhid', 'playstation') + _vids
        filtered = [l for l in all_lines if any(k in l.lower() for k in keywords)]
        if filtered:
            for l in filtered[-50:]:
                lines.append(f'  {l}')
        else:
            lines.append('  (no relevant kernel messages)')
    except Exception as e:
        lines.append(f'  (error: {e})')
    lines.append('')

    lines.append('=== END OF REPORT ===')

    filename = f'rumble-checker-report-{datetime.now().strftime("%Y-%m-%d")}.txt'
    path = os.path.expanduser(f'~/Desktop/{filename}')
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    return path


def check_steam_conflict(event_path: str) -> str | None:
    """Return warning string if Steam is holding the device, else None."""
    try:
        r = subprocess.run(['fuser', event_path], capture_output=True, text=True, timeout=3)
        output = (r.stdout + r.stderr).strip()
        if not output:
            return None
        pids = [p for p in output.split() if p.lstrip('-').isdigit()]
        for pid in pids:
            try:
                pr = subprocess.run(['ps', '-p', pid, '-o', 'comm='], capture_output=True, text=True, timeout=2)
                comm = pr.stdout.strip().lower()
                if any(k in comm for k in ('steam', 'gamescope', 'steamwebhelper')):
                    return (
                        f"\u26a0 STEAM IS HOLDING THIS CONTROLLER (pid {pid}, {comm})\n"
                        f"  Fix: Close Steam, or disable Steam Input for this device\n"
                        f"  (Steam > Settings > Controller > General Controller Settings > Disable)"
                    )
            except Exception:
                continue
    except Exception:
        pass
    return None

def detect_virtual_pads() -> dict:
    """Detect userspace virtual HID pads (Proton/Wine).
    Returns {device_name: {"creator": str, "cmdline": str}}
    Only includes non-BT, non-Steam(28de:11ff) uhid devices."""
    import os, subprocess

    result = {}
    uhid_dir = "/sys/class/uhid"
    if not os.path.isdir(uhid_dir):
        return result

    uhid_pids = {}
    try:
        out = subprocess.run(
            ["fuser", "/dev/uhid"], capture_output=True, text=True
        )
        if out.returncode in (0, 1):
            parts = out.stdout.split(":", 1)
            if len(parts) > 1:
                for p in parts[1].split():
                    try:
                        pid = int(p)
                        cmd_file = f"/proc/{pid}/cmdline"
                        if os.path.isfile(cmd_file):
                            with open(cmd_file, "rb") as f:
                                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
                            cmd_l = cmd.lower()
                            if "proton" in cmd_l:
                                uhid_pids[pid] = ("Proton", cmd)
                            elif "wine" in cmd_l:
                                uhid_pids[pid] = ("Wine", cmd)
                    except (ValueError, PermissionError, OSError):
                        pass
    except Exception:
        pass

    for entry in os.listdir(uhid_dir):
        path = os.path.join(uhid_dir, entry)
        if not os.path.isdir(path):
            continue

        name_file = os.path.join(path, "name")
        if not os.path.isfile(name_file):
            continue
        with open(name_file) as f:
            dev_name = f.read().strip()
        if not dev_name:
            continue

        real = os.path.realpath(path)
        if "bluetooth" in real.lower() or "hci" in real.lower():
            continue

        if len(uhid_pids) == 1:
            creator, cmdline = list(uhid_pids.values())[0]
        elif len(uhid_pids) > 1:
            creator = "Proton/Wine (multiple)"
            cmdline = ""
        else:
            creator = "userspace process"
            cmdline = ""

        result[dev_name] = {"creator": creator, "cmdline": cmdline}

    return result


