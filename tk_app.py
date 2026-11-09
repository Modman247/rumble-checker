#!/usr/bin/env python3
"""Rumble Checker v2.0 — Tkinter frontend (retro Sega Genesis theme)."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import time

from backend import (
    parse_input_devices, test_rumble, pattern_pulse,
    pattern_alternate, pattern_ramp, detect_drift,
    is_readable, fix_permissions, remove_access, export_report,
    access_diagnostic, get_firmware, Device, check_steam_conflict,
)
import backend
from sfx import sfx


# ─── SEGA GENESIS PALETTE ───────────────────────────────────────
BG        = "#000000"
PANEL     = "#141414"
BORDER    = "#e60012"
WHITE     = "#f0f0f0"
RED       = "#e60012"
GREEN     = "#00d812"
YELLOW    = "#f8b800"
ORANGE    = "#f87858"
GRAY      = "#8a8a8a"
DARKGRAY  = "#1e1e1e"
SELECT    = "#2a2a2a"

FONT       = ("Courier", 10)
FONT_BOLD  = ("Courier", 10, "bold")
FONT_TITLE = ("Courier", 14, "bold")
FONT_SUB   = ("Courier", 11)
FONT_SMALL = ("Courier", 11)


class RumbleCheckerApp:
    def __init__(self, root):
        self.root = root
        root.title("Rumble Checker v2.0 — by Modman247")
        root.geometry("1280x1050")
        root.resizable(True, True)
        root.minsize(900, 500)
        root.configure(bg=BG)

        self.devices = []
        self.selected_device = None
        self._rumble_results = {}
        self._drift_results = None

        # ── TITLE ──
        tk.Label(root, text="Rumble Checker v2.0 — by Modman247",
                 font=FONT_TITLE, bg=BG, fg=RED).pack(pady=(8, 2), anchor="w", padx=10)
        top_row = tk.Frame(root, bg=BG)
        top_row.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(top_row, text="Detects gamepads, tests force feedback, fixes permissions",
                 font=FONT_SUB, bg=BG, fg=GRAY).pack(side="left")

        self.rescan_btn = self._make_btn(top_row, "Rescan", self.scan)
        self.rescan_btn.pack(side="right")

        # ── STATUS BAR ──
        self.status = tk.Label(root, text=" ", font=FONT_BOLD, bg=DARKGRAY,
                               fg=WHITE, anchor="w", padx=10, pady=5)
        self.status.pack(fill="x", side="bottom")

        # ── DEVICE TABLE (Treeview = perfect column alignment) ──
        tree_frame = tk.Frame(root, bg=PANEL, relief="flat", bd=0,
                              highlightbackground=BORDER, highlightthickness=2)
        tree_frame.pack(fill="both", expand=True, padx=10)

        self.tree = ttk.Treeview(tree_frame,
            columns=("name", "node", "id", "mode", "batt", "ff", "conn", "access"),
            show="headings", selectmode="browse")
        self.tree.heading("name", text="Controller")
        self.tree.heading("node", text="Device")
        self.tree.heading("id", text="Vendor:Product")
        self.tree.heading("mode", text="Mode")
        self.tree.heading("batt", text="Battery")
        self.tree.heading("ff", text="Rumble")
        self.tree.heading("conn", text="Conn")
        self.tree.heading("access", text="Access")
        self.tree.column("name", width=260)
        self.tree.column("node", width=165)
        self.tree.column("id", width=140)
        self.tree.column("mode", width=260)
        self.tree.column("batt", width=95)
        self.tree.column("ff", width=95)
        self.tree.column("conn", width=70)
        self.tree.column("access", width=95)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Retro.Treeview",
                        background=BG, foreground=GREEN,
                        fieldbackground=BG, font=("Courier", 14), rowheight=36)
        style.configure("Retro.Treeview.Heading",
                        background=PANEL, foreground=RED, font=FONT_BOLD)
        style.map("Retro.Treeview",
                  background=[("selected", SELECT)],
                  foreground=[("selected", WHITE)])
        style.configure("Retro.TButton", minsize=(100, 32),
                        borderwidth=3, relief="raised",
                        padding=(20, 8),
                        background=DARKGRAY, foreground=WHITE,
                        font=("Courier", 13, "bold"))
        style.map("Retro.TButton",
                  background=[("active", BORDER), ("disabled", DARKGRAY)],
                  foreground=[("disabled", WHITE)],
                  relief=[("disabled", "raised")])
        style.layout("Retro.TButton.Green", style.layout("Retro.TButton"))
        style.configure("Retro.TButton.Green",
                        minsize=(100, 32), borderwidth=3, relief="raised",
                        padding=(20, 8), font=("Courier", 13, "bold"),
                        background=DARKGRAY, foreground=GREEN)
        style.map("Retro.TButton.Green",
                  background=[("active", BORDER), ("disabled", DARKGRAY)],
                  foreground=[("disabled", GREEN)],
                  relief=[("disabled", "raised")])
        style.layout("Retro.TButton.Red", style.layout("Retro.TButton"))
        style.configure("Retro.TButton.Red",
                        minsize=(100, 32), borderwidth=3, relief="raised",
                        padding=(20, 8), font=("Courier", 13, "bold"),
                        background=DARKGRAY, foreground=RED)
        style.map("Retro.TButton.Red",
                  background=[("active", BORDER), ("disabled", DARKGRAY)],
                  foreground=[("disabled", RED)],
                  relief=[("disabled", "raised")])

        self.tree.configure(style="Retro.Treeview", height=5)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scrollbar.pack(side="right", fill="y", pady=4)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Motion>", self._tree_tooltip)
        self.tree.bind("<Leave>", self._tree_tooltip_hide)
        self._tree_tip = None

        # ── ACTION BUTTONS ROW (right-aligned, below device table) ──
        act_row = tk.Frame(root, bg=BG)
        act_row.pack(fill="x", padx=10, pady=8)


        self.btn_drift = self._make_btn(act_row, "Check Drift (3s)", self._check_drift)
        self.btn_drift.config(width=14)
        self.btn_drift.config(state="disabled")
        self.btn_drift.pack(side="right", padx=4)
        self._make_tooltip(self.btn_drift, "Check Drift (3s)\nSamples all stick axes for 3 seconds.\nDO NOT TOUCH THE CONTROLLER DURING SAMPLING.\nIf an axis doesn't return to center, it's flagged as DRIFT.")

        self.btn_fw = self._make_btn(act_row, "Read FW", self._read_fw)
        self.btn_fw.config(width=14)
        self.btn_fw.config(state="disabled")
        self.btn_fw.pack(side="right", padx=4)

        self.btn_recheck = self._make_btn(act_row, "Re-check", self._recheck_access)
        self.btn_recheck.config(width=14)
        self.btn_recheck.config(state="disabled")
        self.btn_recheck.pack(side="right", padx=4)
        self._make_tooltip(self.btn_recheck, "Re-check\nRe-runs access diagnostic for selected controller")

        self.btn_remove = self._make_btn(act_row, "Remove Access", self._remove_access)
        self.btn_remove.config(width=14)
        self.btn_remove.config(state="disabled")
        self.btn_remove.pack(side="right", padx=4)
        self._make_tooltip(self.btn_remove, "Remove Access\nRemoves udev rule for this VID:PID\n(Uses pkexec — will prompt for your password)")

        self.btn_fix = self._make_btn(act_row, "Fix Access", self._fix_access)
        self.btn_fix.config(width=14)
        self.btn_fw_update = self._make_btn(act_row, "FW Update", self._open_fw_updater)
        self.btn_fw_update.config(width=14)
        self.btn_fw_update.pack(side="right", padx=2)
        self._make_tooltip(self.btn_fw_update, "FW Update\nOpens 8BitDo's official web-based firmware updater (web.8bitdo.com)\n\nRequirements:\n  - Chromium-based browser (Chrome, Chromium, Edge)\n  - hidraw access (Fix Access covers this for 2dc8)\n\nCONTROLLER:\n  1. Power off controller\n  2. Plug in USB-C cable\n  3. Click 'Connect' in the web app\n  4. Select device and install\n\nDONGLE/RECEIVER:\n  1. Unplug dongle\n  2. Hold small button while plugging back in (bootloader mode)\n  3. Click 'Connect' in the web app\n  4. Select receiver and install")
        self.btn_export = self._make_btn(act_row, "Export", self._do_export)
        self.btn_export.config(width=14)
        self.btn_export.pack(side="right", padx=2)
        self._make_tooltip(self.btn_export, "Export\nGenerates a diagnostic report with system info, device scan, and test results\nSaves to ~/rumble-checker-report-YYYY-MM-DD.txt")
        self.btn_fix.config(state="disabled", style="Retro.TButton.Green")
        self.btn_fix.pack(side="right", padx=4)
        self._make_tooltip(self.btn_fix, "Fix Access\nAdds user to input group + writes udev rule for this VID:PID\n(Uses pkexec — will prompt for your password)")

        # ── CONTROL PANEL ──
        panel = tk.Frame(root, bg=PANEL, relief="flat", bd=0,
                         highlightbackground=BORDER, highlightthickness=2)
        panel.pack(fill="x", padx=10, pady=6, ipady=25)

        # Intensity slider (above buttons, 1/4 thicker)
        int_row = tk.Frame(panel, bg=PANEL)
        int_row.pack(fill="x", pady=2, padx=8)
        tk.Label(int_row, text="Intensity:", font=FONT_SMALL, bg=PANEL, fg=GRAY, width=10, anchor="w").pack(side="left")
        self.intensity_var = tk.IntVar(value=255)
        self.intensity_slider = tk.Scale(int_row, from_=0, to=255, variable=self.intensity_var,
                                         orient="horizontal", length=356, width=25,
                                         bg=PANEL, fg=WHITE, troughcolor=DARKGRAY,
                                         activebackground=RED, highlightthickness=0,
                                         font=FONT_SMALL, showvalue=False)
        self.intensity_slider.pack(side="left", padx=6)
        self.intensity_lbl = tk.Label(int_row, text="255", font=FONT_SMALL, bg=PANEL, fg=RED)
        self.intensity_lbl.pack(side="left")
        self.intensity_var.trace_add("write", lambda *_: self.intensity_lbl.config(text=str(self.intensity_var.get())))

        # Duration slider (below intensity, same size)
        dur_row = tk.Frame(panel, bg=PANEL)
        dur_row.pack(fill="x", pady=(2, 24), padx=8)
        tk.Label(dur_row, text="Duration:", font=FONT_SMALL, bg=PANEL, fg=GRAY, width=10, anchor="w").pack(side="left")
        self.duration_var = tk.IntVar(value=500)
        self.duration_slider = tk.Scale(dur_row, from_=100, to=3000, variable=self.duration_var,
                                        orient="horizontal", length=356, width=25,
                                        bg=PANEL, fg=WHITE, troughcolor=DARKGRAY,
                                        activebackground=RED, highlightthickness=0,
                                        font=FONT_SMALL, showvalue=False)
        self.duration_slider.pack(side="left", padx=6)
        self.duration_lbl = tk.Label(dur_row, text="500ms", font=FONT_SMALL, bg=PANEL, fg=RED)
        self.duration_lbl.pack(side="left")
        self.duration_var.trace_add("write", lambda *_: self.duration_lbl.config(text=f"{self.duration_var.get()}ms"))

        self.btn_btf = self._make_btn(dur_row, "BT Fix", self._bt_fix)
        self.btn_btf.config(width=14)
        self.btn_btf.config(state="disabled")
        self.btn_btf.pack(side="left", padx=6)
        self.btn_poll = ttk.Button(dur_row, text="Poll", style="Retro.TButton", width=10)
        self.btn_poll.pack(side="left", padx=6)
        self.btn_poll.bind("<Button-1>", lambda e: self._poll_popup())
        self.btn_poll.state(["disabled"])
        
        self.btn_measure = ttk.Button(dur_row, text="Measure", style="Retro.TButton", width=10)
        self.btn_measure.pack(side="left", padx=6)
        self.btn_measure.bind("<Button-1>", lambda e: self._measure_popup())
        self.btn_measure.state(["disabled"])
        self._make_tooltip(self.btn_poll, "Polling Rate\nShows the negotiated polling rate for this controller.\nUSB: reads bInterval from sysfs (the real kernel rate).\nBT: protocol-locked at 125 Hz (8 ms slot).\nDongle: not measurable from host.\n\nThis is the worst-case input latency:\n  1000 Hz = 1 ms, 125 Hz = 8 ms.")
        self._make_tooltip(self.btn_measure, "Event Rate (1s sample)\nNOT the polling rate. Counts evdev events in 1 second\nwhile you move a stick.\n\nUse for:\n  - Relative comparison between controllers\n  - Detecting a USB device stuck at a low rate\n  - Confirming the device is sending events\n\nWiggle a stick continuously during the 1s sample.")

        self._last_measured = None
        self._make_tooltip(self.btn_btf, "Bluetooth Fix\nShows troubleshooting steps for your specific\nBluetooth controller. Disconnects, pairing issues,\nrange problems, kernel BT fixes.")

        # Rumble buttons row

        # Pattern row (moved from top)
        pat_row = tk.Frame(panel, bg=PANEL)
        pat_row.pack(fill="x", pady=(4, 8), padx=8)
        tk.Label(pat_row, text="Pattern:", font=FONT_SMALL, bg=PANEL, fg=GRAY).pack(side="left", padx=(0, 4))
        self.pattern_var = tk.StringVar(value="pulse")
        for p in ("pulse", "alternate", "ramp"):
            tk.Radiobutton(pat_row, text=p, variable=self.pattern_var, value=p,
                           font=("Courier", 13, "bold"), bg=PANEL, fg=WHITE, selectcolor=DARKGRAY,
                           activebackground=PANEL, activeforeground=WHITE).pack(side="left", padx=12)
        self.btn_pattern = self._make_btn(pat_row, "Play", self._play_pattern)
        self._make_tooltip(self.btn_pattern, "Rumble Test\nSends a force feedback pulse to the selected controller.\nUses the current Intensity, Duration, and Pattern settings.\n\n  Intensity: motor strength (0-255)\n  Duration: how long the pulse lasts (100-3000ms)\n  Pattern: pulse (single), alternate (L/R), ramp (fade in/out)\n\nIf no rumble is felt, check:\n  - FF column in treeview (must be Yes)\n  - Access column (must be OK)\n  - Controller supports force feedback")
        self.btn_pattern.pack(side="left", padx=8)
        self.btn_pattern.config(state="disabled")

        self.btn_btest = self._make_btn(pat_row, "Btn Test", self._btn_test)
        self.btn_btest.config(width=14)
        self.btn_btest.config(state="disabled")
        self.btn_btest.pack(side="left", padx=8)
        self._make_tooltip(self.btn_btest, "Button/Axis Test\nOpens an overlay showing all buttons and axes.\nPress each one on your controller to verify it works.\nUnpressed items are reported when you click Done.")

        self.btn_mode = self._make_btn(pat_row, "Mode", self._show_mode)
        self.btn_mode.config(width=14)
        self.btn_mode.config(state="disabled")
        self.btn_mode.pack(side="left", padx=8)
        self._make_tooltip(self.btn_mode, "Mode Switch\nShows instructions to switch your controller\ninto a different input mode (XInput, DInput, PS4, Switch).\nFollow the steps, then click Rescan.")

        self.btn_udev = self._make_btn(pat_row, "Udev", self._scan_udev)
        self.btn_udev.config(width=14)
        self.btn_udev.config(state="disabled")
        self.btn_udev.pack(side="left", padx=8)
        self._make_tooltip(self.btn_udev, "Udev Scanner\nScans all udev rules for entries matching this controller's VID:PID.\nFlags potential conflicts (OpenRGB, Steam, other tools).")


        btn_row = tk.Frame(panel, bg=PANEL)
        tk.Label(btn_row, text="RUMBLE", font=("Courier", 11, "bold"), bg=PANEL, fg=GRAY).pack(pady=(16, 4))
        btn_row.pack(pady=(0, 4), anchor="center")

        self.btn_left = self._make_circle_btn(btn_row, "L", GREEN, lambda: self._test_rumble("left"))
        self.btn_left.pack(side="left", padx=6)
        self.btn_left.set_enabled(False)

        self.btn_both = self._make_circle_btn(btn_row, "BOTH", RED, lambda: self._test_rumble("both"))
        self.btn_both.pack(side="left", padx=6)
        self.btn_both.set_enabled(False)

        self.btn_right = self._make_circle_btn(btn_row, "R", "#4488ff", lambda: self._test_rumble("right"))
        self.btn_right.pack(side="left", padx=6)
        self.btn_right.set_enabled(False)









        # Drift result
        self.drift_result = tk.Label(panel, text="", font=FONT_SMALL, bg=PANEL, fg=GREEN,
                                     anchor="w", justify="left")
        self.drift_result.pack(fill="x", padx=8, pady=2)

        # Bottom row: access_info (left) + xpad button (right)
        bottom_row = tk.Frame(panel, bg=PANEL)
        bottom_row.pack(fill="x", padx=8, pady=2)

        self.access_info = tk.Label(bottom_row, text="", font=FONT_SMALL, bg=PANEL, fg=GRAY,
                                    anchor="w", justify="left")
        self.access_info.pack(side="left", fill="x", expand=True)

        self.btn_xpad = self._make_btn(bottom_row, "xpad", self._xpad_inject)
        self.btn_xpad.config(width=14)
        self.btn_xpad.config(state="disabled")
        self.btn_xpad.pack(side="right", padx=(4, 0))
        self._make_tooltip(self.btn_xpad, "xpad Inject\nForces the xpad kernel driver to claim this USB controller.\nFor unrecognized Xbox-protocol controllers.\nUSB only. Reverts on reboot.\n(Uses pkexec — will prompt for your password)")

        self.btn_trigff = self._make_btn(bottom_row, "TrigFF", self._trigger_ff)
        self.btn_trigff.config(width=14)
        self.btn_trigff.config(state="disabled")
        self.btn_trigff.pack(side="right", padx=(4, 4))
        self._make_tooltip(self.btn_trigff, "Trigger Haptics\nTests impulse trigger rumble (Xbox Series X/S only).\nBluetooth connection required.\nUses intensity slider for trigger strength.")

        self.btn_led = self._make_btn(bottom_row, "LED", self._led_test)
        self.btn_led.config(width=14)
        self.btn_led.config(state="disabled")
        self.btn_led.pack(side="right", padx=(0, 4))
        self._make_tooltip(self.btn_led, "LED / Lightbar Test\nFlashes the lightbar (DS4/DS5) or LED ring (Xbox)\nfor 2 seconds. Confirms the light is working.\nDS4/DS5: Bluetooth or USB.\nXbox: not controllable from host.")

        self._boot_sequence()

    def _tree_tooltip(self, event):
        """Show tooltip on treeview row hover."""
        row = self.tree.identify_row(event.y)
        if not row:
            self._tree_tooltip_hide(event)
            return
        idx = self.tree.index(row)
        if idx >= len(self.devices):
            return
        d = self.devices[idx]
        text = None
        if d.vendor == "28de" and d.product == "11ff":
            text = ("Steam Virtual Pad (XInput)\n"
                    "This is NOT a physical controller.\n"
                    "Steam Input created it to translate your\n"
                    "physical controller to Xbox layout.\n"
                    "Rumble tests here test the virtual pad,\n"
                    "NOT your real controller.")
        steam_vpad = (d.vendor == "28de" and d.product == "11ff")
        # Proton/Wine virtual pad check
        if not steam_vpad:
            self._virtual_pads = getattr(self, "_virtual_pads", None)
            if self._virtual_pads is None:
                self._virtual_pads = backend.detect_virtual_pads()
            dev_name = self.tree.set(row, "name")
            if dev_name in self._virtual_pads:
                info = self._virtual_pads[dev_name]
                tip = (
                    f"{info['creator']} Virtual Pad\n"
                    f"This is NOT a physical controller.\n"
                    f"Rumble tests here test the virtual pad,\n"
                    f"NOT your real controller."
                )
                if info.get("cmdline"):
                    tip += f"\n\nCreated by: {info['cmdline'][:80]}"
                self._show_tooltip(event, tip, "yellow")
                return
        if text:
            if self._tree_tip:
                self._tree_tip.destroy()
            self._tree_tip = tk.Toplevel(self.root)
            self._tree_tip.wm_overrideredirect(True)
            self._tree_tip.wm_geometry(f"+{event.x_root+12}+{event.y_root+12}")
            lbl = tk.Label(self._tree_tip, text=text, font=("Courier", 10),
                           bg="#222222", fg=YELLOW, padx=8, pady=4,
                           relief="solid", bd=1, wraplength=320, justify="left")
            lbl.pack()
            self._tree_tip.update_idletasks()
            tw = self._tree_tip.winfo_width()
            sw = self.root.winfo_screenwidth()
            if event.x_root + tw + 12 > sw:
                self._tree_tip.wm_geometry(f"+{event.x_root - tw - 12}+{event.y_root+12}")
        else:
            if self._tree_tip:
                self._tree_tip.destroy()
                self._tree_tip = None

    def _tree_tooltip_hide(self, event):
        if self._tree_tip:
            self._tree_tip.destroy()
            self._tree_tip = None

    def _make_tooltip(self, widget, text):
        """Simple hover tooltip. Text can be updated via widget._tooltip_text."""
        tip = None
        def show(e):
            nonlocal tip
            if tip: return
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            lbl = tk.Label(tip, text=widget._tooltip_text, font=("Courier", 10),
                           bg="#222222", fg=WHITE, padx=8, pady=4,
                           relief="solid", bd=1, wraplength=320)
            lbl.pack()
            tip.update_idletasks()
            tw, th = tip.winfo_width(), tip.winfo_height()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x = e.x_root + 12
            y = e.y_root + 12
            if x + tw > sw:
                x = e.x_root - tw - 12
            if y + th > sh:
                y = e.y_root - th - 12
            tip.wm_geometry(f"+{x}+{y}")
        def hide(e):
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None
        widget._tooltip_text = text
        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _make_btn(self, parent, text, command):
        def wrapped():
            sfx.click()
            command()
        return ttk.Button(parent, text=text, command=wrapped, style="Retro.TButton")

    def _make_circle_btn(self, parent, label, color, command, size=67):
        """Create a circular controller-style button."""
        canvas = tk.Canvas(parent, width=size, height=size, bg=PANEL,
                           highlightthickness=0, cursor="hand2")
        radius = size // 2 - 4
        cx, cy = size // 2, size // 2
        # Outer ring
        ring = canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                   outline=color, width=3, fill=DARKGRAY)
        # Inner circle
        circle = canvas.create_oval(cx - radius + 5, cy - radius + 5,
                                     cx + radius - 5, cy + radius - 5,
                                     outline="", fill=DARKGRAY)
        # Label text
        text = canvas.create_text(cx, cy, text=label, fill=color, font=("Courier", 10, "bold"))
        # State
        state = {"enabled": True}

        def on_enter(e):
            if state["enabled"]:
                canvas.itemconfigure(ring, fill=color)
                canvas.itemconfigure(circle, fill=color)
                canvas.itemconfigure(text, fill=BG)

        def on_leave(e):
            if state["enabled"]:
                canvas.itemconfigure(ring, fill=DARKGRAY)
                canvas.itemconfigure(circle, fill=DARKGRAY)
                canvas.itemconfigure(text, fill=color)

        def on_click(e):
            if state["enabled"]:
                sfx.click()
                command()

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_click)

        # Store reference for enabling/disabling
        canvas._circle_items = (ring, circle, text)
        canvas._circle_color = color
        canvas._circle_state = state

        def set_enabled(enabled):
            state["enabled"] = enabled
            if enabled:
                canvas.itemconfigure(ring, outline=color)
                canvas.itemconfigure(text, fill=color)
                canvas.config(cursor="hand2")
            else:
                canvas.itemconfigure(ring, outline="#333333")
                canvas.itemconfigure(circle, fill="#111111")
                canvas.itemconfigure(text, fill="#444444")
                canvas.config(cursor="arrow")

        canvas.set_enabled = set_enabled
        return canvas

    def _boot_sequence(self):
        sfx.power_on()
        self._set_status("POWER ON...", YELLOW)
        self.root.after(600, lambda: self._set_status("LOADING MODULES...", YELLOW))
        self.root.after(1200, lambda: self._set_status("SCANNING INPUT DEVICES...", YELLOW))
        self.root.after(1800, self.scan)

    def _bt_fix(self):
        if not self.selected_device:
            return
        d = self.selected_device
        if d.connection != "BT":
            messagebox.showinfo("BT Fix", "Selected controller is not connected via Bluetooth.")
            return

        lines = [f"Device: {d.name}", f"VID:PID: {d.vendor}:{d.product}", ""]

        lines.append("=== QUICK CHECKS ===")
        lines.append("  1. Is Bluetooth powered on?")
        lines.append("     bluetoothctl show  \u2192  'Powered: yes'")
        lines.append("  2. Is the adapter up?")
        lines.append("     sudo hciconfig hci0 up")
        lines.append("  3. Is the controller in range? (BT 4.0: ~10m)")
        lines.append("")

        if d.vendor == "054c" and d.product == "09cc":
            lines.append("=== DS4 SPECIFIC ===")
            lines.append("  - Re-pair: hold PS + SHARE until light flashes,")
            lines.append("    then select in bluetoothctl (pair + trust)")
            lines.append("  - If light flashes fast: battery critical")
            lines.append("  - If light flashes slow: pairing mode (normal)")
            lines.append("  - Firmware: connect via USB to update")
            lines.append("  - Known issue: DS4 disconnects after sleep.")
            lines.append("    Fix: echo 0 | sudo tee /sys/module/uhid/parameters/early")
            lines.append("")

        elif d.vendor == "054c" and d.product in ("0ce6", "0cf2"):
            lines.append("=== DUALSENSE SPECIFIC ===")
            lines.append("  - Re-pair: hold PS + CREATE until lightbar flashes")
            lines.append("  - Firmware: connect via USB to update")
            lines.append("  - Known issue: disconnects on kernel < 6.2")
            lines.append("    Fix: update kernel or use usbhid-ds module")
            lines.append("")

        elif d.vendor == "045e":
            lines.append("=== XBOX WIRELESS SPECIFIC ===")
            lines.append("  - Pair: hold Xbox button until it flashes,")
            lines.append("    hold BT button on adapter 3s, press Xbox again")
            lines.append("  - Known issue: BLE throttle (125Hz vs 1000Hz)")
            lines.append("    Fix: use 2.4GHz dongle for competitive play")
            lines.append("  - Firmware: Xbox app (Windows) or usbboot")
            lines.append("")

        elif d.vendor == "2dc8":
            lines.append("=== 8BITDO BT SPECIFIC ===")
            lines.append("  - Re-pair: hold MODE + SHARE for 3s until LED flashes")
            lines.append("  - Known issue: BT range shorter than dongle (~5m)")
            lines.append("  - Known issue: disconnects in DInput BT mode")
            lines.append("    Fix: use XInput mode for BT, or use dongle")
            lines.append("  - Firmware: web.8bitdo.com (USB only)")
            lines.append("")

        else:
            lines.append("=== GENERIC BT FIXES ===")
            lines.append("  - Forget + re-pair the device")
            lines.append("  - Check: bluetoothctl devices (is it listed?)")
            lines.append("  - Check: bluetoothctl info <MAC> (RSSI = signal)")
            lines.append("  - Try: sudo hciconfig hci0 up")
            lines.append("  - Kernel: sudo dmesg | grep bluetooth")
            lines.append("")

        lines.append("=== AFTER FIXING ===")
        lines.append("  Click Rescan to re-detect the controller.")

        messagebox.showinfo("BT Fix", "\n".join(lines))

    def _led_test(self):
        if not self.selected_device:
            return
        d = self.selected_device
        is_ps = d.vendor == "054c" and d.product in ("09cc", "0ce6", "0cf2")
        is_xbox = d.vendor == "045e" and d.product in ("02ea", "02fd", "0b12", "0b20")

        if is_xbox:
            messagebox.showinfo("LED Test",
                f"Device: {d.name}\n\n"
                "Xbox LED ring is NOT controllable from the host.\n"
                "It is managed by the Xbox hub/console.\n"
                "On PC, the LED state is fixed (white = connected).\n\n"
                "If the LED is off, the controller is not powered.")
            return

        if not is_ps:
            messagebox.showinfo("LED Test",
                f"Device: {d.name}\n\n"
                "This controller's LED is not controllable from the host.\n"
                "The light (if present) is managed by the controller's own firmware.\n\n"
                "LED testing is available for:\n"
                "  - DS4 / DualSense (USB only)\n"
                "  - Xbox Series (not available — hub-managed)")
            return

        if d.connection == "BT":
            messagebox.showinfo("LED Test",
                f"Device: {d.name}\nConnection: Bluetooth\n\n"
                "DS4/DS5 lightbar is NOT controllable from the host\n"
                "over Bluetooth. It is managed by the controller firmware\n"
                "(shows pairing status, battery level, etc.).\n\n"
                "To test the lightbar, connect via USB cable.")
            return

        import os, glob
        hidraw_path = None
        # Simple: match VID:PID in the realpath
        vid_pid = f"{d.vendor.upper()}:{d.product.upper()}"
        for hw in glob.glob("/dev/hidraw*"):
            try:
                real = os.path.realpath(os.path.join("/sys/class/hidraw", os.path.basename(hw), "device"))
                if vid_pid in real.upper():
                    hidraw_path = hw
                    break
            except Exception:
                continue

        if not hidraw_path:
            messagebox.showerror("LED Test", "Could not find hidraw device for this controller.")
            return

        self._set_status("FLASHING LIGHTBAR (2s)...", YELLOW)
        self.btn_led.config(state="disabled")

        def work():
            import time
            try:
                fd = os.open(hidraw_path, os.O_WRONLY)
                # DS4/DS5 lightbar report: [0x05, on, 0, 0, R, G, B, 0, 0]
                flash_colors = [
                    (0xFF, 0x00, 0x00),  # Red
                    (0x00, 0xFF, 0x00),  # Green
                    (0x00, 0x00, 0xFF),  # Blue
                    (0xFF, 0xFF, 0xFF),  # White
                ]
                for r, g, b in flash_colors:
                    # DS4 USB output report 0x05 (32 bytes)
                    # [0]=0x05 [1]=valid_flag0 [2]=valid_flag1 [3]=res
                    # [4]=motor_R [5]=motor_L [6]=R [7]=G [8]=B
                    # [9]=blink_on [10]=blink_off [11-31]=reserved
                    # valid_flag0 bit 2 (0x04) = lightbar RGB valid
                    report = bytearray(32)
                    report[0] = 0x05
                    report[1] = 0x02  # lightbar valid
                    report[6] = r
                    report[7] = g
                    report[8] = b
                    os.write(fd, bytes(report))
                    time.sleep(0.5)
                # Turn off (valid flag set, all RGB = 0)
                report = bytearray(32)
                report[0] = 0x05
                report[1] = 0x04
                os.write(fd, bytes(report))
                os.close(fd)
                ok, msg = True, "Lightbar flashed: Red → Green → Blue → White\nIf you saw all four colors, the lightbar is working."
            except PermissionError:
                ok, msg = False, f"Permission denied on {hidraw_path}.\nRun: sudo chmod 666 {hidraw_path}"
            except Exception as e:
                ok, msg = False, f"Failed: {e}"
            self.root.after(0, lambda: self._led_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _led_done(self, ok, msg):
        d = self.selected_device
        ps_lightbar = d and d.vendor == "054c" and d.product in ("09cc", "0ce6", "0cf2")
        xbox_series = d and d.vendor == "045e" and d.product in ("02ea", "02fd", "0b12", "0b20")
        self.btn_led.config(state="normal")
        if ok:
            sfx.ding()
            self._set_status("LIGHTBAR TEST PASSED", GREEN)
            messagebox.showinfo("LED Test", msg)
        else:
            sfx.error()
            self._set_status("LED TEST FAILED", RED)
            messagebox.showwarning("LED Test", msg)

    def _trigger_ff(self):
        if not self.selected_device:
            return
        d = self.selected_device
        if d.vendor != "045e" or d.product not in ("02ea", "02fd", "0b12", "0b20"):
            messagebox.showinfo("Trigger Haptics", "Not supported on this device.\nTrigger rumble requires Xbox Series X/S controller.")
            return
        if d.connection == "USB":
            messagebox.showinfo("Trigger Haptics",
                f"Device: {d.name}\nConnection: USB\n\n"
                "USB uses GIP protocol — trigger rumble is not available\n"
                "via the standard xpad driver.\n\n"
                "Options:\n"
                "  1. Connect via Bluetooth (recommended)\n"
                "  2. Install xpadneo kernel module (raw USB access)")
            return

        # Find hidraw device
        import os, glob
        hidraw_path = None
        for hw in glob.glob("/dev/hidraw*"):
            try:
                base = os.path.basename(hw)
                dev_path = os.path.join("/sys/class/hidraw", base, "device")
                if not os.path.exists(dev_path):
                    continue
                # Walk up to find the USB device
                p = dev_path
                for _ in range(5):
                    if not os.path.exists(p):
                        break
                    vid_file = os.path.join(p, "idVendor")
                    if os.path.exists(vid_file):
                        with open(vid_file) as f:
                            if f.read().strip() == d.vendor:
                                hidraw_path = hw
                                break
                    p = os.path.dirname(p)
                if hidraw_path:
                    break
            except Exception:
                continue

        if not hidraw_path:
            messagebox.showerror("Trigger Haptics", "Could not find hidraw device for this controller.")
            return

        intensity = self.intensity_var.get()
        self._set_status("TRIGGER RUMBLE (1s)...", YELLOW)
        self.btn_trigff.config(state="disabled")

        def work():
            import time
            try:
                fd = os.open(hidraw_path, os.O_WRONLY)
                # Report: [id, mode, mask, lT, rT, l, r, pulse, off, term]
                # mask 0x0C = triggers only
                start = bytes([0x01, 0x00, 0x0C, intensity, intensity, 0x00, 0x00, 0xFF, 0x00, 0xEB])
                stop  = bytes([0x01, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEB])
                os.write(fd, start)
                time.sleep(1.0)
                os.write(fd, stop)
                os.close(fd)
                ok, msg = True, "Trigger rumble sent.\nYou should have felt vibration in both triggers."
            except PermissionError:
                ok, msg = False, f"Permission denied on {hidraw_path}.\nRun: sudo chmod 666 {hidraw_path}"
            except Exception as e:
                ok, msg = False, f"Failed: {e}"
            self.root.after(0, lambda: self._trigff_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _trigff_done(self, ok, msg):
        d = self.selected_device
        xbox_series = d and d.vendor == "045e" and d.product in ("02ea", "02fd", "0b12", "0b20")
        self.btn_trigff.config(state="normal" if xbox_series else "disabled")
        if ok:
            sfx.ding()
            self._set_status("TRIGGER RUMBLE SENT", GREEN)
            messagebox.showinfo("Trigger Haptics", msg)
        else:
            sfx.error()
            self._set_status("TRIGGER RUMBLE FAILED", RED)
            messagebox.showwarning("Trigger Haptics", msg)

    def _xpad_inject(self):
        if not self.selected_device:
            return
        d = self.selected_device

        # Check if xpad new_id is available on this kernel
        import os
        new_id_path = "/sys/module/xpad/parameters/new_id"
        if not os.path.isfile(new_id_path):
            messagebox.showinfo(
                "xpad Inject Not Available",
                f"Device: {d.name}\n"
                f"VID:PID: {d.vendor}:{d.product}\n\n"
                "Your kernel does not expose the xpad new_id parameter.\n"
                "The xpad driver cannot claim this device at runtime.\n\n"
                "WHY:\n"
                "The new_id sysfs parameter was removed in recent kernels.\n"
                "The xpad driver's ID table is now compile-time only.\n\n"
                "OPTIONS:\n"
                "  1. Use a kernel with xpad new_id support (6.x or earlier)\n"
                "  2. Install xpadneo-dkms (BT-focused, may not work for USB)\n"
                "       yay -S xpadneo-dkms\n"
                "  3. Use Steam Input to remap this device to XInput layout\n\n"
                "This device will remain DInput until one of the above is applied."
            )
            return
        if d.connection != "USB":
            messagebox.showinfo("xpad Inject", "Only works on USB connections.\nBluetooth and dongle devices cannot use xpad new_id.")
            return
        vid = d.vendor
        pid = d.product
        msg = (
            f"Device: {d.name}\n"
            f"VID:PID: {vid}:{pid}\n"
            f"Connection: {d.connection}\n\n"
            "This forces the xpad kernel driver to claim this device\n"
            "by writing to /sys/bus/usb/drivers/xpad/new_id.\n\n"
            "USES:\n"
            "  - Unrecognized USB controllers that use Xbox protocol\n"
            "  - Controllers that show in lsusb but have no driver\n\n"
            "LIMITATIONS:\n"
            "  - USB only (not Bluetooth/dongle)\n"
            "  - Device must not already be claimed by another driver\n"
            "  - Reverts on reboot (use udev rule to persist)\n\n"
            "(Uses pkexec — will prompt for your password)"
        )
        if not messagebox.askokcancel("xpad Inject", msg):
            return
        self._set_status("INJECTING XPAD DRIVER...", YELLOW)
        self.btn_xpad.config(state="disabled")

        def work():
            import subprocess
            try:
                r = subprocess.run(
                    ['pkexec', 'sh', '-c', f'echo "{vid} {pid}" > /sys/bus/usb/drivers/xpad/new_id'],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    ok, out = True, f"Device {vid}:{pid} bound to xpad successfully.\nClick Rescan to see it."
                else:
                    ok, out = False, f"Failed: {r.stderr.strip() or r.stdout.strip() or 'unknown error'}\n\nPossible causes:\n  - Device already claimed by another driver\n  - Not an Xbox-protocol controller\n  - USB device not found"
            except subprocess.TimeoutExpired:
                ok, out = False, "Timed out. pkexec dialog may not have appeared."
            except Exception as e:
                ok, out = False, f"Error: {e}"
            self.root.after(0, lambda: self._xpad_done(ok, out))

        threading.Thread(target=work, daemon=True).start()

    def _xpad_done(self, ok, out):
        self.btn_xpad.config(state="normal")
        if ok:
            sfx.ding()
            self._set_status("XPAD INJECTED — RESCAN TO SEE DEVICE", GREEN)
            messagebox.showinfo("xpad Inject", out)
        else:
            sfx.error()
            self._set_status("XPAD INJECT FAILED", RED)
            messagebox.showwarning("xpad Inject", out)

    def _scan_udev(self):
        if not self.selected_device:
            return
        d = self.selected_device
        vid = d.vendor
        self._set_status(f"SCANNING UDEV RULES FOR {vid}:{d.product}...", YELLOW)

        import os, glob
        rule_dirs = ["/etc/udev/rules.d/", "/usr/lib/udev/rules.d/", "/run/udev/rules.d/"]
        matches = []
        for rd in rule_dirs:
            if not os.path.isdir(rd):
                continue
            for rf in sorted(glob.glob(os.path.join(rd, "*.rules"))):
                try:
                    with open(rf, "r") as f:
                        for line in f:
                            stripped = line.strip()
                            if not stripped or stripped.startswith("#"):
                                continue
                            if f'idVendor=="{vid}"' in stripped or f'idVendor=="{vid.upper()}"' in stripped:
                                matches.append((rf, stripped))
                except Exception:
                    pass

        # Flag known conflicts
        CONFLICT_HINTS = {
            "openrgb": "OpenRGB also claims this device",
            "steam": "Steam may be interfering",
            "gamepad": "Another gamepad tool claims this device",
        }
        lines = [f"Device: {d.name}", f"VID:PID: {vid}:{d.product}", ""]
        conflicts = 0
        if matches:
            for filepath, rule in matches:
                lines.append(f"{filepath}:")
                lines.append(f"  {rule}")
                lower = rule.lower()
                flagged = False
                for hint, msg in CONFLICT_HINTS.items():
                    if hint in lower:
                        lines.append(f"  \u26a0 CONFLICT: {msg}")
                        conflicts += 1
                        flagged = True
                        break
                if not flagged:
                    lines.append(f"  \u2192 OK")
                lines.append("")
            lines.append(f"Summary: {len(matches)} rule(s) match. {conflicts} potential conflict(s).")
        else:
            lines.append("No udev rules found matching this VID:PID.")
            lines.append("")
            lines.append("This means access is granted solely via group membership (input group).")

        if conflicts > 0:
            sfx.error()
            self._set_status(f"UDEV: {conflicts} CONFLICT(S) FOUND", ORANGE)
            messagebox.showwarning("Udev Scanner", "\n".join(lines))
        else:
            sfx.ding()
            self._set_status("UDEV: NO CONFLICTS", GREEN)
            messagebox.showinfo("Udev Scanner", "\n".join(lines))

    def _show_mode(self):
        if not self.selected_device:
            return
        d = self.selected_device
        MODES = {
            ("2dc8", "3106"): [
                ("XInput (Xbox)", "Hold SHARE + UP"),
                ("DInput (Native)", "Hold SHARE + LEFT"),
                ("Mac", "Hold SHARE + RIGHT"),
                ("PSC (PS Classic)", "Hold SHARE + DOWN"),
                ("Genesis", "Hold SHARE + UP + LEFT"),
            ],
            ("2dc8", "3095"): [
                ("XInput (Xbox)", "Hold SHARE + UP"),
                ("DInput (Native)", "Hold SHARE + LEFT"),
                ("Mac", "Hold SHARE + RIGHT"),
                ("PSC (PS Classic)", "Hold SHARE + DOWN"),
                ("Genesis", "Hold SHARE + UP + LEFT"),
            ],
            ("046d", "c21f"): [
                ("XInput (Xbox)", "Hold + button while plugging in USB"),
                ("DInput (PC)", "Plug in without holding any button"),
            ],
            ("046d", "c223"): [
                ("XInput (Xbox)", "Hold + button while plugging in USB"),
                ("DInput (PC)", "Plug in without holding any button"),
            ],
            ("054c", "0cda"): [
                ("DInput (fixed)", "No mode switching available. PS Classic is DInput only."),
            ],
        }
        key = (d.vendor, d.product)
        if key in MODES:
            modes = MODES[key]
            lines = [f"Device: {d.name}", f"Current mode: {d.mode}", ""]
            for mode_name, steps in modes:
                lines.append(f"{mode_name}:")
                lines.append(f"  {steps}")
                lines.append("")
            lines.append("After switching, wait 2s then click Rescan.")
            messagebox.showinfo("Mode Switch", "\n".join(lines))
        else:
            messagebox.showinfo("Mode Switch",
                f"Device: {d.name}\n\n"
                "No mode-switching instructions available for this controller.\n"
                "It may be a single-mode device or not yet in the database.")

    def _btn_test(self):
        if not self.selected_device or not self.selected_device.event_path:
            return
        dev_path = self.selected_device.event_path
        d = self.selected_device
        self._set_status("BUTTON TEST — PRESS EACH BUTTON ON YOUR CONTROLLER", YELLOW)

        # Button name map
        BTN_NAMES = {
            0x130: "A / Cross", 0x131: "B / Circle", 0x132: "X / Square",
            0x133: "Y / Triangle", 0x134: "L1", 0x135: "R1",
            0x136: "Share / Back", 0x137: "Options / Start",
            0x138: "PS / Guide", 0x139: "L3", 0x13a: "R3",
            0x13b: "L4 / Back", 0x13c: "R4 / Fwd",
            0x13d: "A", 0x13e: "B", 0x13f: "X", 0x140: "Y",
            0x141: "L2 Click", 0x142: "R2 Click",
            0x143: "DPad Up", 0x144: "DPad Down", 0x145: "DPad Left", 0x146: "DPad Right",
        }
        AXIS_NAMES = {
            0x00: "LX", 0x01: "LY", 0x02: "LT", 0x03: "RT",
            0x04: "RX", 0x05: "RY", 0x06: "Z", 0x07: "RZ",
            0x10: "Hat X", 0x11: "Hat Y",
        }

        # Open device and get capabilities
        import evdev, select as sel_mod
        try:
            dev = evdev.InputDevice(dev_path)
        except Exception as e:
            messagebox.showerror("Button Test", f"Cannot open device:\n{e}")
            return
        caps = dev.capabilities()
        key_codes = caps.get(evdev.ecodes.EV_KEY, [])
        abs_codes = [c for c, _ in caps.get(evdev.ecodes.EV_ABS, [])]
        dev.grab()

        # Build cell lists
        btn_cells = {}  # code -> (label_widget, pressed)
        ax_cells = {}   # code -> (label_widget, moved)

        # Toplevel
        win = tk.Toplevel(self.root)
        win.title(f"Button Test — {d.name}")
        win.configure(bg=BG)
        win.transient(self.root)
        win.resizable(False, False)

        tk.Label(win, text=f"Press each button on your {d.name}",
                 font=FONT_BOLD, bg=BG, fg=WHITE).pack(pady=(10, 4))
        tk.Label(win, text="Green = detected. Click Done when finished.",
                 font=FONT_SMALL, bg=BG, fg=GRAY).pack(pady=(0, 8))

        # Buttons grid
        if key_codes:
            btn_frame = tk.Frame(win, bg=BG)
            btn_frame.pack(pady=4)
            tk.Label(btn_frame, text="BUTTONS:", font=FONT_SMALL, bg=BG, fg=GRAY).pack(anchor="w")
            grid = tk.Frame(btn_frame, bg=BG)
            grid.pack()
            for i, code in enumerate(sorted(key_codes)):
                name = BTN_NAMES.get(code, f"BTN_{code:03x}")
                lbl = tk.Label(grid, text=f"  {name}  ", font=("Courier", 11, "bold"),
                               bg=DARKGRAY, fg=GRAY, relief="raised", bd=2, padx=6, pady=4)
                row, col = divmod(i, 4)
                lbl.grid(row=row, column=col, padx=5, pady=4)
                btn_cells[code] = (lbl, False)

        # Axes grid
        if abs_codes:
            ax_frame = tk.Frame(win, bg=BG)
            ax_frame.pack(pady=4)
            tk.Label(ax_frame, text="AXES / TRIGGERS (move each):", font=FONT_SMALL, bg=BG, fg=GRAY).pack(anchor="w")
            grid2 = tk.Frame(ax_frame, bg=BG)
            grid2.pack()
            for i, code in enumerate(sorted(abs_codes)):
                name = AXIS_NAMES.get(code, f"ABS_{code:02x}")
                lbl = tk.Label(grid2, text=f"  {name}  ", font=("Courier", 11, "bold"),
                               bg=DARKGRAY, fg=GRAY, relief="raised", bd=2, padx=6, pady=4)
                row, col = divmod(i, 4)
                lbl.grid(row=row, column=col, padx=5, pady=4)
                ax_cells[code] = (lbl, False)

        # Done button
        def on_done():
            dev.ungrab()
            dev.close()
            win.destroy()
            # Report
            unpressed_btns = [BTN_NAMES.get(c, f"BTN_{c:03x}") for c, (_, p) in btn_cells.items() if not p]
            unpressed_ax = [AXIS_NAMES.get(c, f"ABS_{c:02x}") for c, (_, m) in ax_cells.items() if not m]
            if not unpressed_btns and not unpressed_ax:
                sfx.ding()
                self._set_status("BUTTON TEST: ALL OK", GREEN)
                messagebox.showinfo("Button Test", f"Device: {d.name}\n\nALL BUTTONS AND AXES RESPONDED.\nNo dead inputs detected.")
            else:
                sfx.error()
                self._set_status("BUTTON TEST: ISSUES FOUND", ORANGE)
                lines = [f"Device: {d.name}", ""]
                if unpressed_btns:
                    lines.append(f"BUTTONS NOT PRESSED ({len(unpressed_btns)}):")
                    for b in unpressed_btns:
                        lines.append(f"  - {b}")
                    lines.append("")
                if unpressed_ax:
                    lines.append(f"AXES NOT MOVED ({len(unpressed_ax)}):")
                    for a in unpressed_ax:
                        lines.append(f"  - {a}")
                messagebox.showwarning("Button Test", "\n".join(lines))

        btn_frame2 = tk.Frame(win, bg=BG)
        btn_frame2.pack(pady=12)

        def on_clear():
            for code, (lbl, _) in btn_cells.items():
                btn_cells[code] = (lbl, False)
                lbl.config(bg=DARKGRAY, fg=GRAY)
            for code, (lbl, _) in ax_cells.items():
                ax_cells[code] = (lbl, False)
                lbl.config(bg=DARKGRAY, fg=GRAY)

        tk.Button(btn_frame2, text="Clear", command=on_clear,
                  font=("Courier", 11, "bold"), bg=DARKGRAY, fg=GRAY,
                  relief="raised", bd=2, padx=20, pady=4).pack(side="left", padx=4)
        tk.Button(btn_frame2, text="Done", command=on_done,
                  font=("Courier", 11, "bold"), bg=DARKGRAY, fg=WHITE,
                  relief="raised", bd=2, padx=20, pady=4).pack(side="left", padx=4)

        # Background event reader
        stop = [False]
        def reader():
            while not stop[0]:
                try:
                    ready, _, _ = sel_mod.select([dev.fd], [], [], 0.05)
                    if ready:
                        event = dev.read_one()
                        if not event:
                            continue
                        if event.type == evdev.ecodes.EV_KEY and event.value == 1:
                            if event.code in btn_cells:
                                lbl, _ = btn_cells[event.code]
                                btn_cells[event.code] = (lbl, True)
                                self.root.after(0, lambda l=lbl: l.config(bg=GREEN, fg=BG))
                        elif event.type == evdev.ecodes.EV_ABS:
                            if event.code in ax_cells:
                                lbl, _ = ax_cells[event.code]
                                ax_cells[event.code] = (lbl, True)
                                self.root.after(0, lambda l=lbl: l.config(bg=GREEN, fg=BG))
                except Exception:
                    break

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        def on_close():
            stop[0] = True
            dev.ungrab()
            dev.close()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _show_verdict(self):
        """Aggregate all test results into a one-line verdict."""
        if not self.selected_device:
            return
        d = self.selected_device
        issues = []
        ok_items = []

        # Rumble
        if d.has_ff:
            if self._rumble_results:
                for motor, res in self._rumble_results.items():
                    if res == "OK":
                        ok_items.append(f"{motor.upper()} rumble")
                    else:
                        issues.append(f"{motor.upper()} rumble FAILED ({res})")
            else:
                issues.append("rumble not tested")
        else:
            issues.append("no force feedback support")

        # Drift
        if self._drift_results:
            drifting = [r for r in self._drift_results if r.is_drifting]
            if drifting:
                for r in drifting:
                    issues.append(f"{r.axis_name} drifting (mean={r.mean:.0f})")
            else:
                ok_items.append("drift OK")
        else:
            issues.append("drift not tested")

        # Battery
        if d.battery and d.battery != "N/A":
            try:
                pct = int(d.battery.replace("%", ""))
                if pct > 50:
                    ok_items.append(f"battery {pct}%")
                elif pct > 20:
                    issues.append(f"battery low ({pct}%)")
                else:
                    issues.append(f"battery critical ({pct}%)")
            except:
                pass

        # Access
        if d.event_path:
            if is_readable(d.event_path):
                ok_items.append("access OK")
            else:
                issues.append("access DENIED")

        # Steam
        if d.vendor == "28de" and d.product == "11ff":
            issues.append("Steam virtual pad (not physical)")
        else:
            for vd in self.devices:
                if vd.vendor == "28de" and vd.product == "11ff":
                    issues.append("Steam virtual pad present (games use it, not this device)")
                    break

        # Format
        if issues:
            status_text = f"VERDICT: {len(issues)} ISSUE(S)"
            self._set_status(status_text, ORANGE)
            detail = "ISSUES:\n" + "\n".join(f"  - {i}" for i in issues)
            if ok_items:
                detail += "\n\nOK:\n" + "\n".join(f"  - {o}" for o in ok_items)
            messagebox.showwarning("Verdict", f"Device: {d.name}\n\n{detail}")
        else:
            self._set_status("VERDICT: ALL OK", GREEN)
            detail = "ALL CHECKS PASSED:\n" + "\n".join(f"  - {o}" for o in ok_items)
            messagebox.showinfo("Verdict", f"Device: {d.name}\n\n{detail}")

    def _set_status(self, text, color=WHITE):
        self.status.config(text=text, fg=color)

    # ─── SCAN ───────────────────────────────────────────────────

    def scan(self):
        sfx.click()
        self._set_status("SCANNING...", YELLOW)
        self.rescan_btn.config(state="disabled")

        def work():
            devices = parse_input_devices()
            self.root.after(0, lambda: self._scan_done(devices))

        threading.Thread(target=work, daemon=True).start()

    def _scan_done(self, devices):
        self.rescan_btn.config(state="normal")
        self.tree.delete(*self.tree.get_children())
        self._virtual_pads = None  # invalidate virtual pad cache
        self.devices = devices

        if not self.devices:
            self._set_status("NO CONTROLLERS FOUND — PLUG ONE IN AND RESCAN", RED)
            self._poll_devices()
            return

        for d in self.devices:
            access = "OK" if (d.event_path and is_readable(d.event_path)) else "DENIED"
            batt = d.battery or "N/A"
            ff = "Yes" if d.has_ff else "No"
            mode_str = f"{d.brand} - {d.mode}"

            tags = []
            if d.has_ff:
                tags.append("ff_yes")
            else:
                tags.append("ff_no")
            if access == "DENIED":
                tags.append("denied")
            if batt != "N/A":
                try:
                    pct = int(batt.replace("%", ""))
                    if pct > 50: tags.append("batt_green")
                    elif pct > 20: tags.append("batt_yellow")
                    else: tags.append("batt_red")
                except:
                    pass

            self.tree.insert("", "end", values=(
                d.name, d.event_path or "N/A",
                f"{d.vendor}:{d.product}", mode_str,
                batt, ff, d.connection, access
            ), tags=tags)

        self.tree.tag_configure("ff_yes", foreground=GREEN)
        self.tree.tag_configure("ff_no", foreground=RED)
        self.tree.tag_configure("denied", foreground=ORANGE)
        self.tree.tag_configure("batt_green", foreground=GREEN)
        self.tree.tag_configure("batt_yellow", foreground=YELLOW)
        self.tree.tag_configure("batt_red", foreground=RED)
        self._set_status(f"FOUND {len(self.devices)} CONTROLLER(S) — SELECT ONE TO BEGIN", GREEN)

        # Start hot-plug poll
        self._poll_devices()

    def _poll_devices(self):
        if not self.root.winfo_exists():
            return
        try:
            names_now = {d.name for d in parse_input_devices()}
            names_before = {d.name for d in self.devices}
            if names_now != names_before:
                sfx.ding()
                self._set_status("DEVICE CHANGED — RESCANNING", YELLOW)
                self.scan()
                return
        except Exception:
            pass
        self.root.after(3000, self._poll_devices)

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            self.btn_fix._tooltip_text = "Fix Access\nAdds user to input group + writes udev rule for this VID:PID\n(Uses pkexec — will prompt for your password)"
            return
        idx = self.tree.index(sel[0])
        if idx < len(self.devices):
            self.selected_device = self.devices[idx]
            d = self.selected_device
            has_ff = d.has_ff
            self.btn_left.set_enabled(has_ff)
            self.btn_right.set_enabled(has_ff)
            self.btn_both.set_enabled(has_ff)
            self.btn_pattern.config(state="normal" if has_ff else "disabled")
            self.btn_drift.config(state="normal" if d.event_path else "disabled")
            self.btn_btest.config(state="normal" if d.event_path else "disabled")
            self.btn_mode.config(state="normal")
            self.btn_udev.config(state="normal")
            self.btn_xpad.config(state="normal" if d.connection == "USB" else "disabled")
            self.btn_btf.config(state="normal" if d.connection == "BT" else "disabled")
            self.btn_poll.state(["!disabled"])
            self.btn_measure.state(["!disabled"])
            xbox_series = d.vendor == "045e" and d.product in ("02ea", "02fd", "0b12", "0b20")
            self.btn_trigff.config(state="normal" if xbox_series else "disabled")
            ps_lightbar = d.vendor == "054c" and d.product in ("09cc", "0ce6", "0cf2")
            self.btn_led.config(state="normal")
            self.btn_btf.config(state="normal" if d.connection == "BT" else "disabled")
            self.btn_fw.config(state="normal" if d.event_path else "disabled")
            needs_fix = d.event_path and not is_readable(d.event_path)
            self.btn_fix.config(state="normal" if needs_fix else "disabled",
                                style="Retro.TButton.Red" if needs_fix else "Retro.TButton.Green")
            self.btn_fix._tooltip_text = (
                "Adds user to input group + writes udev rule for this VID:PID"
                if needs_fix else "Access OK — no fix needed"
            )
            has_access = d.event_path and is_readable(d.event_path)
            self.btn_remove.config(state="normal" if has_access else "disabled",
                                   style="Retro.TButton.Red" if has_access else "Retro.TButton.Green")
            self.btn_remove._tooltip_text = (
                "Removes udev rule for this VID:PID\n(Uses pkexec — will prompt for your password)"
                if has_access else "No access to remove"
            )
            self.btn_recheck.config(state="normal")
            self.btn_recheck._tooltip_text = "Re-runs access diagnostic for selected controller"
            self._show_access()
            # Steam conflict check
            steam_warn = check_steam_conflict(d.event_path) if d.event_path else None
            self._show_vid_conflict(self.tree.selection()[0])

            # Also check for Steam virtual pad (28de:11ff) as proxy
            # Only warn on the PHYSICAL controller, not the virtual pad itself
            if not steam_warn and not (d.vendor == "28de" and d.product == "11ff"):
                for vd in self.devices:
                    if vd.vendor == "28de" and vd.product == "11ff":
                        steam_warn = (
                            "\u26a0 STEAM VIRTUAL PAD PRESENT (28de:11ff)\n"
                            "  Steam is translating your controller to XInput.\n"
                            "  Games see the virtual pad, not this device directly.\n"
                            "  Rumble/drift tests here test the REAL controller."
                        )
                        break
            if steam_warn:
                sfx.error()
                self._set_status("STEAM CONFLICT DETECTED", ORANGE)
                messagebox.showwarning("Steam Conflict", steam_warn)
            sfx.click()

    # ─── ACTIONS ────────────────────────────────────────────────

    def _test_rumble(self, motor):
        if not self.selected_device or not self.selected_device.event_path:
            return
        dev_path = self.selected_device.event_path
        intensity = self.intensity_var.get()
        duration = self.duration_var.get()
        self._set_status(f"TESTING {motor.upper()} ({duration}ms)...", YELLOW)

        self._last_rumble_motor = motor
        def work():
            result = test_rumble(dev_path, motor, intensity, duration)
            self.root.after(0, lambda: self._rumble_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _rumble_done(self, result):
        if self.selected_device:
            motor = getattr(self, '_last_rumble_motor', 'both')
            self._rumble_results[motor] = result
        if result == "OK":
            sfx.ding()
            self._set_status("RUMBLE TEST PASSED — YOU SHOULD HAVE FELT IT!", GREEN)
        elif result == "NO_FF":
            sfx.error()
            self._set_status("DEVICE DOES NOT SUPPORT FORCE FEEDBACK", RED)
        else:
            sfx.error()
            self._set_status(f"FAILED: {result}", RED)

    def _play_pattern(self):
        if not self.selected_device or not self.selected_device.event_path:
            return
        dev_path = self.selected_device.event_path
        intensity = self.intensity_var.get()
        pat = self.pattern_var.get()
        duration = self.duration_var.get()
        self._set_status(f"PLAYING {pat.upper()}...", YELLOW)

        def work():
            if pat == "pulse":
                r = pattern_pulse(dev_path, "both", intensity, count=5)
            elif pat == "alternate":
                r = pattern_alternate(dev_path, intensity, count=5)
            else:
                r = pattern_ramp(dev_path, "both", duration)
            self.root.after(0, lambda: self._rumble_done(r))

        threading.Thread(target=work, daemon=True).start()

    def _check_drift(self):
        if not self.selected_device or not self.selected_device.event_path:
            return
        dev_path = self.selected_device.event_path
        self._set_status("SAMPLING AXES (3s)... DON'T TOUCH THE STICKS", YELLOW)
        self.btn_drift.config(state="disabled")

        def work():
            results = detect_drift(dev_path, duration_s=3.0)
            self.root.after(0, lambda: self._drift_done(results))

        threading.Thread(target=work, daemon=True).start()

    def _drift_done(self, results):
        self.btn_drift.config(state="normal")
        self._drift_results = results
        if not results:
            self._set_status("NO AXES", YELLOW)
            messagebox.showinfo("Drift Check", "No axes found on this device.")
            return
        lines = []
        any_drift = False
        for r in results:
            st = "DRIFT" if r.is_drifting else "OK"
            if r.is_drifting:
                any_drift = True
            lines.append(f"{r.axis_name:<10} mean={r.mean:>7.1f}  delta={r.max_delta:>6}  {st}")
        if any_drift:
            sfx.error()
            self._set_status("DRIFT DETECTED", RED)
            messagebox.showwarning("Drift Check", "\n".join(lines))
        else:
            sfx.ding()
            self._set_status("NO DRIFT — ALL AXES OK", GREEN)
            messagebox.showinfo("Drift Check", "\n".join(lines))
        self._show_verdict()

    # ─── ACCESS ─────────────────────────────────────────────────

    def _show_access(self):
        if not self.selected_device:
            return
        d = self.selected_device
        info = access_diagnostic(d.event_path, d.vendor, d.product)
        self.access_info.config(text=(
            f"{info['device']}  |  {info['permissions']} {info['owner']}:{info['group']}\n"
            f"{info['user']} (uid={info['uid']})  |  input grp: {'Y' if info['in_input_group'] else 'N'}  |  "
            f"Read: {'Y' if info['readable'] else 'N'}  |  Flatpak: {'yes' if info['flatpak'] else 'no'}\n"
            f"Rule: {'EXISTS' if info['rule_exists'] else 'none'}  |  {info['rule_file']}"
        ))

    def _fix_access(self):
        if not self.selected_device:
            return
        d = self.selected_device
        info = access_diagnostic(d.event_path, d.vendor, d.product)
        msg = (
            f"Device:  {d.name}\n"
            f"Node:    {d.event_path}\n"
            f"Perms:   {info['permissions']} {info['owner']}:{info['group']}\n"
            f"User:    {info['user']}  in_input={'Y' if info['in_input_group'] else 'N'}\n"
            f"Readable:{' Y' if info['readable'] else ' N'}\n\n"
            "WILL DO:\n"
            f"  1. Add {info['user']} to 'input' group\n"
            f"  2. Write udev rule to {info['rule_file']}\n"
            f"  3. Reload udev\n\n"
            "RISKS:\n"
            "  - Persists across reboots\n"
            "  - Affects all users in input group\n\n"
            "PASSWORD PROMPT:\n"
            "  A system dialog will appear asking for your password.\n"
            "  This is pkexec — Linux's standard way for apps to perform\n"
            "  one privileged action. It only runs the commands above,\n"
            "  nothing else. Your password is never stored or sent anywhere."
        )
        if messagebox.askokcancel("Fix Access", msg):
            self._do_fix()

    def _do_fix(self):
        d = self.selected_device
        self._set_status("APPLYING FIX (MAY PROMPT FOR PASSWORD)...", YELLOW)
        self.btn_fix.config(state="disabled")

        def work():
            ok, msg = fix_permissions(d.event_path, d.name, d.vendor, d.product)
            self.root.after(0, lambda: self._fix_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _fix_done(self, ok, msg):
        if ok:
            sfx.level_complete()
            self._set_status("FIX APPLIED! ALL CONTROLLERS WITH THIS ID ARE NOW COVERED.", GREEN)
        else:
            sfx.error()
            self._set_status("FIX ATTEMPTED BUT DEVICE STILL NOT ACCESSIBLE.", RED)
        messagebox.showinfo("Fix Results", msg)
        self.scan()

    def _remove_access(self):
        if not self.selected_device:
            return
        d = self.selected_device
        info = access_diagnostic(d.event_path, d.vendor, d.product)
        msg = (
            f"Device:  {d.name}\n"
            f"VID:PID: {d.vendor}:{d.product}\n"
            f"Rule:    {'exists' if info['rule_exists'] else 'none'}\n\n"
            "WILL DO:\n"
            f"  1. Remove udev rule from {info['rule_file']}\n"
            f"  2. Reload udev\n\n"
            "WON'T DO:\n"
            "  - Remove group membership (use: sudo gpasswd -d $USER input)\n\n"
            "AFTER:\n"
            "  - Device shows DENIED until re-fixed or re-login"
        )
        if messagebox.askokcancel("Remove Access", msg):
            self._do_remove()

    def _do_remove(self):
        d = self.selected_device
        self._set_status("REMOVING ACCESS...", YELLOW)
        self.btn_remove.config(state="disabled")

        def work():
            ok, msg = remove_access(d.vendor, d.product)
            self.root.after(0, lambda: self._remove_done(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _remove_done(self, ok, msg):
        self.btn_remove.config(state="normal")
        if ok:
            sfx.ding()
            self._set_status("ACCESS REMOVED", GREEN)
        else:
            sfx.error()
            self._set_status("REMOVE FAILED", RED)
        messagebox.showinfo("Remove Results", msg)
        self._show_access()

    def _read_fw(self):
        if not self.selected_device:
            return
        d = self.selected_device
        self._set_status("READING FIRMWARE...", YELLOW)
        self.btn_fw.config(state="disabled")

        def work():
            fw = get_firmware(d.vendor, d.product, d.name, phys=d.uniq)
            self.root.after(0, lambda: self._fw_btn_done(fw))

        threading.Thread(target=work, daemon=True).start()

    def _fw_btn_done(self, fw):
        self.btn_fw.config(state="normal")
        if fw:
            sfx.ding()
            self._set_status(f"FIRMWARE: {fw}", GREEN)
        else:
            self._set_status("FIRMWARE: N/A", YELLOW)
            d = self.selected_device
            if d.vendor == "054c" and d.connection == "BT":
                messagebox.showinfo("Firmware", "DS4 firmware can only be read over USB.\nDisconnect Bluetooth and plug in a USB cable.")
            elif d.vendor != "054c" and d.vendor != "2dc8":
                messagebox.showinfo("Firmware", f"No firmware reader for {d.brand}.\nCurrently supported: DS4 (USB), 8BitDo.")
            elif d.vendor == "2dc8" and d.connection == "Dongle":
                messagebox.showinfo("Firmware", "8BitDo firmware can only be read when the controller is connected directly (USB cable or Bluetooth).\nThe 2.4 GHz dongle does not forward firmware queries.")
            else:
                messagebox.showinfo("Firmware", "Firmware read failed.\nDevice may not support it in current mode.")

    def _do_export(self):
        sfx.click()
        self._set_status("GENERATING REPORT...", YELLOW)
        self.btn_export.config(state="disabled")

        def work():
            path = export_report()
            self.root.after(0, lambda: self._export_done(path))

        threading.Thread(target=work, daemon=True).start()

    def _export_done(self, path):
        self.btn_export.config(state="normal")
        sfx.ding()
        self._set_status(f"REPORT SAVED: {path}", GREEN)

    def _open_fw_updater(self):
        import webbrowser
        sfx.click()
        self._set_status("OPENING 8BITDO FIRMWARE UPDATER...", YELLOW)
        webbrowser.open("https://web.8bitdo.com")
        self._set_status("PUT CONTROLLER IN UPDATE MODE (HOLD LB+RB WHILE PLUGGING USB)", GREEN)

    def _recheck_access(self):
        self._show_access()
        self._set_status("ACCESS RE-CHECKED", GREEN)
        sfx.click()
        self._show_verdict()



    def _show_vid_conflict(self, item):
        """Show popup when multiple controllers share the same VID:PID."""
        import subprocess
        vid_pid = self.tree.set(item, "id")
        if not vid_pid or ":" not in vid_pid:
            return

        # Count all rows with same VID:PID
        all_items = self.tree.get_children()
        same_vid = []
        for it in all_items:
            if self.tree.set(it, "id") == vid_pid:
                same_vid.append(self.tree.set(it, "name"))

        if len(same_vid) <= 1:
            return

        # Build popup
        win = tk.Toplevel(self.root)
        win.title("VID:PID Conflict")
        win.geometry("420x" + str(120 + len(same_vid) * 22))
        win.resizable(False, False)
        win.configure(bg="black")
        win.transient(self.root)
        win.update_idletasks()
        win.grab_set()

        tk.Label(win, text=f"⚠ {vid_pid} is shared by {len(same_vid)} controllers:",
                 font=("Courier", 11, "bold"), bg="black", fg="yellow",
                 anchor="w").pack(fill="x", padx=12, pady=(12, 4))

        for name in same_vid:
            marker = "  ← selected" if name == self.tree.set(item, "name") else ""
            tk.Label(win, text=f"  • {name}{marker}",
                     font=("Courier", 10), bg="black", fg="white",
                     anchor="w").pack(fill="x", padx=12)

        tk.Label(win, text="", bg="black").pack()

        # Check if Steam is running
        try:
            steam_running = subprocess.run(
                ["pgrep", "-x", "steam"], capture_output=True
            ).returncode == 0
        except Exception:
            steam_running = False

        def do_identify():
            subprocess.Popen(["xdg-open", "steam://controller/identify"])

        btn_frame = tk.Frame(win, bg="black")
        btn_frame.pack(pady=8)

        if steam_running:
            tk.Button(btn_frame, text="Identify via Steam",
                      font=("Courier", 10, "bold"), bg="gray30", fg="white",
                      activebackground="gray40", relief="raised", bd=2,
                      padx=12, pady=4, command=do_identify).pack(side="left", padx=6)
        else:
            tk.Button(btn_frame, text="Identify via Steam (Steam not running)",
                      font=("Courier", 10), bg="gray20", fg="gray50",
                      state="disabled", relief="raised", bd=2,
                      padx=12, pady=4).pack(side="left", padx=6)

        tk.Button(btn_frame, text="Close",
                  font=("Courier", 10), bg="gray30", fg="white",
                  activebackground="gray40", relief="raised", bd=2,
                  padx=12, pady=4, command=win.destroy).pack(side="left", padx=6)

        tk.Label(win, text="Steam flashes the physical controller's LED.",
                 font=("Courier", 9), bg="black", fg="gray50").pack(pady=(0, 8))


    def _poll_popup(self):
        """Show polling rate info for selected controller."""
        from backend import get_polling_rate
        item = self.tree.selection()
        if not item:
            return
        item = item[0]
        node = self.tree.set(item, "node")
        conn = self.tree.set(item, "conn")
        name = self.tree.set(item, "name")

        rate, detail = get_polling_rate(node, conn)

        # Build explanation
        if conn == "BT":
            explanation = (
                "WHAT THIS MEANS:\n"
                "Bluetooth Classic HID has a fixed 8 ms polling slot.\n"
                "The host polls the device every 8 ms — no faster, no slower.\n"
                "This is a protocol limitation, not a firmware or driver issue.\n"
                "No setting, update, or tool can change it.\n"
                "\n"
                "PRACTICAL IMPACT:\n"
                "Worst-case input latency = 8 ms (one full slot).\n"
                "Average latency = 4 ms (half a slot, if input is random).\n"
                "For competitive play, USB (1 ms at 1000 Hz) is measurably better.\n"
                "For casual play, 8 ms is imperceptible."
            )
        elif conn == "USB":
            explanation = (
                "WHAT THIS MEANS:\n"
                "USB interrupt endpoints are polled at a fixed interval defined\n"
                "by the bInterval field in the endpoint descriptor. The kernel\n"
                "reads this at enumeration and polls at that rate.\n"
                "\n"
                "How bInterval maps to Hz:\n"
                "  Full Speed (12 Mbps):  bInterval = milliseconds\n"
                "    bInterval=1 → 1000 Hz, bInterval=2 → 500 Hz, bInterval=4 → 250 Hz\n"
                "  High Speed (480 Mbps): bInterval = 2^(n-1) × 125 μs\n"
                "    bInterval=1 → 8000 Hz, bInterval=4 → 1000 Hz, bInterval=6 → 250 Hz\n"
                "\n"
                "PRACTICAL IMPACT:\n"
                "This is the negotiated rate — what the kernel is actually doing.\n"
                "If you expect 1000 Hz but see 250 Hz, the device firmware\n"
                "is requesting a slower interval (common on budget controllers)."
            )
        else:
            explanation = (
                "WHAT THIS MEANS:\n"
                "2.4 GHz dongles manage their own wireless link internally.\n"
                "The polling rate is set by the dongle's firmware and is NOT\n"
                "exposed to the host via any standard interface.\n"
                "\n"
                "TYPICAL RATES (vendor-dependent):\n"
                "  8BitDo dongles: 125–1000 Hz (varies by model)\n"
                "  Generic 2.4G dongles: usually 125–250 Hz\n"
                "  Xbox Wireless dongle: 1000 Hz\n"
                "\n"
                "The evdev layer sees events as they arrive — the effective\n"
                "latency is determined by the dongle's internal polling +\n"
                "airtime. You cannot measure or change this from the host."
            )

        win = tk.Toplevel(self.root)
        win.title(f"Polling Rate — {name}")
        win.geometry("540x540")
        win.resizable(False, False)
        win.configure(bg="black")
        win.transient(self.root)

        tk.Label(win, text="POLLING RATE", font=("Courier", 13, "bold"),
                 bg="black", fg="yellow").pack(pady=(14, 2))
        tk.Label(win, text=name, font=("Courier", 10),
                 bg="black", fg="gray60").pack()

        # Rate display
        rate_color = "lime" if "Hz" in rate and "N/A" not in rate else "orange"
        tk.Label(win, text=f"Rate: {rate}", font=("Courier", 12, "bold"),
                 bg="black", fg=rate_color).pack(pady=(10, 2))
        tk.Label(win, text=detail, font=("Courier", 10),
                 bg="black", fg="white").pack()

        # Explanation
        tk.Frame(win, bg="gray30", height=1).pack(fill="x", pady=10, padx=20)
        tk.Label(win, text=explanation, font=("Courier", 9),
                 bg="black", fg="gray80", justify="left").pack(fill="x", padx=16)

        tk.Button(win, text="Close", font=("Courier", 10, "bold"),
                  bg="gray30", fg="white", relief="raised", bd=2,
                  padx=16, pady=4, command=win.destroy).pack(pady=12)



    def _measure_popup(self):
        """Run 1-second event frequency measurement on selected controller."""
        import select, time as _time
        import evdev

        item = self.tree.selection()
        if not item:
            return
        item = item[0]
        node = self.tree.set(item, "node")
        conn = self.tree.set(item, "conn")
        name = self.tree.set(item, "name")
        dev_path = node if node.startswith("/dev/input/") else f"/dev/input/{node}"

        win = tk.Toplevel(self.root)
        win.title(f"Event Rate — {name}")
        win.geometry("540x420")
        win.resizable(False, False)
        win.configure(bg="black")
        win.transient(self.root)

        tk.Label(win, text="EVENT RATE (1s SAMPLE)", font=("Courier", 13, "bold"),
                 bg="black", fg="yellow").pack(pady=(14, 2))
        tk.Label(win, text=name, font=("Courier", 10),
                 bg="black", fg="gray60").pack()

        tk.Label(win,
                 text="This is NOT the polling rate.\n"
                      "It counts evdev events received in 1 second.\n"
                      "Move a stick continuously during sampling.\n"
                      "Use for relative comparison or to detect\n"
                      "a USB device stuck at a low rate.",
                 font=("Courier", 9), bg="black", fg="gray80",
                 justify="left").pack(pady=(8, 6), padx=16)

        status_label = tk.Label(win, text="Click Start, then WIGGLE A STICK for 1 second.",
                                font=("Courier", 10), bg="black", fg="white")
        status_label.pack(pady=4)

        result_label = tk.Label(win, text="", font=("Courier", 11, "bold"),
                                bg="black", fg="lime")
        result_label.pack(pady=6)

        def do_measure():
            status_label.config(text="Sampling... do not close this window.", fg="orange")
            win.update_idletasks()

            def _work():
                try:
                    dev = evdev.InputDevice(dev_path)
                    count = 0
                    end_time = _time.time() + 1.0
                    while _time.time() < end_time:
                        r, _, _ = select.select([dev.fd], [], [], 0.05)
                        if r:
                            try:
                                dev.read_one()
                                count += 1
                            except (OSError, EOFError):
                                break
                    dev.close()
                    # Store on device object for export
                    self._last_measured = count
                    self._measure_result = count
                    self._measure_error = None
                except Exception as e:
                    self._measure_error = str(e)

            import threading
            self._measure_result = None
            self._measure_error = None
            threading.Thread(target=_work, daemon=True).start()

            def _poll_result():
                if self._measure_result is not None:
                    self._measure_done(self._measure_result, result_label, status_label)
                elif self._measure_error is not None:
                    status_label.config(text=f"Error: {self._measure_error}", fg="red")
                elif win.winfo_exists():
                    win.after(50, _poll_result)

            win.after(50, _poll_result)

        tk.Button(win, text="Start (1s)", font=("Courier", 10, "bold"),
                  bg="gray30", fg="white", relief="raised", bd=2,
                  padx=16, pady=4, command=do_measure).pack(pady=4)
        tk.Button(win, text="Close", font=("Courier", 10),
                  bg="gray30", fg="white", relief="raised", bd=2,
                  padx=16, pady=4, command=win.destroy).pack(pady=8)
        win.update_idletasks()
        win.grab_set()

    def _measure_done(self, count, result_label, status_label):
        """Update measure popup with results."""
        # Store in backend dict so export can pick it up
        item = self.tree.selection()
        if item:
            node = self.tree.set(item[0], "node")
            node_clean = node.split("/")[-1]
            backend._measured_rates[node_clean] = count
        # Compare against theoretical
        item = self.tree.selection()
        theoretical = ""
        if item:
            conn = self.tree.set(item[0], "conn")
            if conn == "BT":
                theoretical = " (theoretical max: 125 Hz)"
            elif conn == "USB":
                theoretical = " (theoretical max: check Poll button)"

        result_label.config(
            text=f"{count} events/s{theoretical}\n"
                 f"Interpretation: this depends on how fast you moved.\n"
                 f"A steady circular stick motion at 1000 Hz polling\n"
                 f"typically yields 800–1000 events/s."
        )
        status_label.config(text="Done.", fg="gray60")


if __name__ == "__main__":
    try:
        import evdev
    except ImportError:
        print("python3-evdev not found. Install with:")
        print("  sudo pacman -S python-evdev")
        raise SystemExit(1)

    root = tk.Tk()
    root.iconphoto(True, tk.PhotoImage(file="rumble-checker-icon.png"))
    app = RumbleCheckerApp(root)
    root.mainloop()
