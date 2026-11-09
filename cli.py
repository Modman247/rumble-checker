#!/usr/bin/env python3
"""Rumble Checker CLI."""

import argparse
import json
import sys

from backend import (
    parse_input_devices, test_rumble, pattern_pulse, pattern_alternate,
    pattern_ramp, detect_drift, full_report, fix_permissions, is_readable,
    remove_access,
)


def main():
    parser = argparse.ArgumentParser(description="Rumble Checker v2")
    sub = parser.add_subparsers(dest="cmd")

    # list
    sub.add_parser("list", help="List detected controllers")

    # rumble
    p_rumble = sub.add_parser("rumble", help="Test rumble")
    p_rumble.add_argument("--motor", choices=["left", "right", "both"], default="both")
    p_rumble.add_argument("--intensity", type=int, default=255, help="0-255")
    p_rumble.add_argument("--duration", type=int, default=500, help="ms")
    p_rumble.add_argument("--device", required=True, help="event node, e.g. /dev/input/event3")

    # pattern
    p_pat = sub.add_parser("pattern", help="Play rumble pattern")
    p_pat.add_argument("--type", choices=["pulse", "alternate", "ramp"], required=True)
    p_pat.add_argument("--motor", choices=["left", "right", "both"], default="both")
    p_pat.add_argument("--intensity", type=int, default=255)
    p_pat.add_argument("--duration", type=int, default=1000, help="ms (ramp only)")
    p_pat.add_argument("--count", type=int, default=5, help="bursts (pulse/alternate)")
    p_pat.add_argument("--device", required=True)

    # drift
    p_drift = sub.add_parser("drift", help="Check for stick drift")
    p_drift.add_argument("--device", required=True)
    p_drift.add_argument("--duration", type=float, default=2.0, help="sample window in seconds")
    p_drift.add_argument("--threshold", type=int, default=5000, help="evdev value threshold")

    # report
    sub.add_parser("report", help="Full JSON diagnostic report")

    # fix
    p_fix = sub.add_parser("fix", help="Fix permissions for a device")
    p_fix.add_argument("--device", required=True)
    p_fix.add_argument("--vendor", required=True)
    p_fix.add_argument("--product", required=True)
    p_fix.add_argument("--name", default="controller")

    # remove
    p_rm = sub.add_parser("remove", help="Remove udev rule for a device")
    p_rm.add_argument("--vendor", required=True)
    p_rm.add_argument("--product", required=True)

    args = parser.parse_args()

    if args.cmd == "list":
        devices = parse_input_devices()
        if not devices:
            print("No controllers found.")
            return
        for d in devices:
            access = "OK" if (d.event_path and is_readable(d.event_path)) else "DENIED"
            batt = d.battery or "N/A"
            fw = d.firmware or ""
            ff = "FF" if d.has_ff else "--"
            print(f"  {d.name:<28} {d.event_path:<18} {d.vendor}:{d.product}  "
                  f"{d.driver:<16} {d.brand} — {d.mode:<22} "
                  f"batt={batt:<5} {ff} fw={fw:<8} {d.connection:<4} {access}")

    elif args.cmd == "rumble":
        result = test_rumble(args.device, args.motor, args.intensity, args.duration)
        print(result)

    elif args.cmd == "pattern":
        if args.type == "pulse":
            result = pattern_pulse(args.device, args.motor, args.intensity, count=args.count)
        elif args.type == "alternate":
            result = pattern_alternate(args.device, args.intensity, count=args.count)
        else:
            result = pattern_ramp(args.device, args.motor, args.duration)
        print(result)

    elif args.cmd == "drift":
        results = detect_drift(args.device, args.duration, args.threshold)
        if not results:
            print("No axes found.")
            return
        for r in results:
            status = "DRIFT" if r.is_drifting else "OK"
            print(f"  {r.axis_name:<12} mean={r.mean:>8.1f}  max_delta={r.max_delta:>6}  {status}")

    elif args.cmd == "report":
        print(json.dumps(full_report(), indent=2))

    elif args.cmd == "fix":
        ok, msg = fix_permissions(args.device, args.name, args.vendor, args.product)
        print(msg)
        sys.exit(0 if ok else 1)

    elif args.cmd == "remove":
        ok, msg = remove_access(args.vendor, args.product)
        print(msg)
        sys.exit(0 if ok else 1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
