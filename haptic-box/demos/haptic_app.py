#!/usr/bin/env python3
"""DEMO: ComLang companion app with a live simulation of the box.

Speak (or type) -> text -> the pen writes block capitals on the palm and the Braille cells show
the same letter at the same time. Fully offline.

This is a proper simulation of the product: the app runs the device software (comlang.Session,
the same as `python -m comlang`) and talks over the controller protocol to the box's FIRMWARE
(firmware/mcu, the same C code as the real board) built for the PC with a model of the hardware.
What you see is what the firmware does: the pen and gantry are drawn from the firmware's step
counters, the Braille cells from its cell outputs, the speaker display is the firmware's own LCD
pixels, and the on-screen box controls press the simulated buttons, wheel and hand pad, which the
firmware debounces and reports back exactly as on the real box. Connect a real board instead of
the simulated one and nothing else changes.

    ./start.sh          or     python3 demos/haptic_app.py

Needs: numpy (always); vosk + sounddevice for listening; pyserial for hardware.

Keys (when the text box is not focused): Space pause/resume (wheel press), R repeat word,
+/- faster/slower (wheel roll), M mode (both / palm / Braille), Esc reset (speaker),
H hand on/off the box, J block the pen (simulated obstruction), S skip to newest phrase, C clear, L listen on/off, D speaker display,
T cover test.
"""
import collections
import csv
import os
import queue
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from comlang import engine as pw, protocol                    # noqa: E402
from comlang.protocol import MODES, MODE_NAME                 # noqa: E402
from comlang.session import Session, SPEED_MIN, SPEED_MAX     # noqa: E402
from comlang.speech import Listener                           # noqa: E402
from comlang.devices import serial_ports                      # noqa: E402
from comlang.devices.mcu import Mcu, SerialTransport           # noqa: E402
from comlang.devices.sim import SimBoard, LCD_W, LCD_H         # noqa: E402

try:
    import cad_render
except ImportError:          # numpy missing etc. -> 2D palm view only
    cad_render = None

VIEW_3D_SIZE = (760, 680)
HIDE_3D = ()
HAND = {"HandDummy": 0.45, "ForearmDummy": 0.45}
VIEWS_3D = {   # name: (camera direction, centre, extent mm, alpha overrides)
    "Cut-away": ((0.5, -0.78, 0.75), (0, 150, 10), 470,
                 dict(HAND, TopPlate=0.82, Shell=0.9)),
    "Close-up at the pen": ((0.62, -0.62, 0.48), (0, 160, 14), 230,
                            dict(HAND, TopPlate=0.7, Shell=0.92)),
    "Top, through the hand": ((0, 0, 1), (0, 140, 0), 520,
                              dict(HAND, TopPlate=0.6, Shell=0.0)),
    "Side, through the box": ((1, -0.12, 0.18), (0, 140, 12), 520,
                              dict(HAND, TopPlate=0.75, Shell=0.85, ForearmPad=0.6)),
    "Product (outside)": ((0.55, -0.85, 0.62), (0, 140, 10), 520,
                          {"HandDummy": 0.0, "ForearmDummy": 0.0}),
}
PRESS_S = 0.7          # how long the 3D hand shows a digit pressing a button
PRESS_DIGIT = {"faster": "Wheel", "slower": "Wheel", "pause": "Wheel", "repeat": "Repeat"}
# a box control -> the simulated hardware input that produces it
BOX_INPUT = {"pause": ("press", "wheel"), "repeat": ("press", "repeat"), "mode": ("press", "mode"),
             "reset": ("press", "reset"), "faster": ("roll", 1), "slower": ("roll", -1)}
STATUS_MS = 30                   # how often the app asks the controller where the pen is

TICK_MS = int(pw.DT * 1000)
COVERS = ("none (open window)", "nitrile glove film 0.1 mm", "latex sheet 0.2 mm", "silicone sheet 0.5 mm",
          "TPU film 0.1 mm", "PET film 0.05 mm", "Lycra / elastane fabric", "PTFE film 0.1 mm")
TRIALS_CSV = os.path.join(ROOT, "trials", "cover_trials.csv")
SCALE = 3.3                      # canvas px per mm
CANVAS_W, CANVAS_H = 420, 570
CX, CY = CANVAS_W / 2, 310       # canvas position of the palm centre

COL = dict(bg="#f7f7f5", palm="#f2d4c2", palm_edge="#c99a83", rail="#9aa4ad", ink="#1d4f7a",
           old_ink="#b9c9d8", pen_down="#c0392b", pen_up="#7f8c8d", window="#888888",
           done="#222222", current="#000000", current_bg="#ffe58a", queued="#9a9a9a",
           partial="#8a8a8a", dot_on="#222222", dot_off="#dddddd", cancelled="#c0392b")


class App:
    """The demo UI. It is a Session sink: the on_* methods below are called by the session."""

    def __init__(self, root):
        self.root = root
        root.title("ComLang (demo)")
        root.configure(bg=COL["bg"])
        self.inbox = queue.Queue()
        self.listener = None
        self.board = self.mcu = None           # simulated board (or None with a real one) + its link
        self.ink, self.old_ink = [], []
        self.pen_xy, self.pen_down, self.cells = (0.0, 0.0), False, (0, 0)
        self.fb_seen = -1
        self.speaker = None                    # speaker display window
        self.trial = None                      # cover-material test window
        self.ui_ready = False
        self.s = Session([self])

        self._build_ui()
        self._draw_static()
        self.ui_ready = True
        if os.environ.get("COMLANG_BOARD", "sim") == "sim":
            self.start_sim()
        self.on_changed(self.s)
        self.root.after(TICK_MS, self.tick)
        self.root.after(STATUS_MS, self.poll_box)
        self.root.after(50, self.poll_inbox)
        self.scene, self.live, self.live_cache, self.frame_due = None, None, {}, 0.0
        self.hand_pose = "rest"
        self.root.after(100, self.init_3d)

    # ---------------- Session sink (what the app shows that is not hardware)
    def on_letter(self, ch, word):
        self.letter_lbl.configure(text=ch or " ")
        if ch:
            self.old_ink, self.ink = self.ink, []
            self.br_txt.configure(text=pw.braille_unicode(ch))
            self.cv.itemconfigure(self.cv_label, text=word)
            self._redraw_ink()
        else:
            self.br_txt.configure(text="")

    def on_abort(self):
        self.ink, self.old_ink = [], []
        if self.ui_ready:
            self._redraw_ink()
            self._render_3d(force=True)

    def on_control(self, action):
        if action in PRESS_DIGIT:
            self.press(PRESS_DIGIT[action])

    def on_message(self, text):
        self._status_msg = text

    def on_changed(self, s):
        if not self.ui_ready:
            return
        for var, val in ((self.speed, s.speed), (self.mode, s.mode)):
            if var.get() != val:
                var.set(val)
        self.pause_btn.configure(text="▶ Resume (Space)" if s.paused else "⏸ Pause (Space)")
        self._render_transcript()
        self._refresh_status()
        self._render_speaker()

    # ---------------- the box controller (simulated firmware or a real board)
    def start_sim(self):
        try:
            self.board = SimBoard()
        except Exception as e:
            self.s.say("Could not build/start the simulated firmware (needs cmake + a C compiler): %s" % e)
            return
        self._attach(self.board.transport)
        self.board_lbl.configure(text="simulated box (firmware/mcu)")

    def _attach(self, transport):
        self.mcu = Mcu(transport, self.inbox, lambda m: self.inbox.put(("error", m)),
                       mirror=self.mirror.get())
        self.s.sinks.append(self.mcu)
        self.mcu.on_speed(self.s.speed)
        self.mcu.on_changed(self.s)

    def _detach(self):
        if self.mcu:
            self.s.sinks.remove(self.mcu)
            self.mcu.close()
        if self.board:
            self.board.close()
        self.mcu = self.board = None

    def box(self, action):
        """A control on the box. With the simulated board this presses the simulated hardware
        (the firmware reports it back, as on the real box); with a real board the app can only
        stand in for the button, so it calls the session directly."""
        if self.board:
            how, arg = BOX_INPUT[action]
            getattr(self.board, how)(arg)
        else:
            self.s.handle(action)

    def set_hand(self, present):
        if self.board:
            self.board.set_hand(present)
        else:
            self.s.set_hand(present)
        self.hand_on.set(present)

    def toggle_jam(self):
        """Simulated obstruction (a finger, an object) blocking the carriage: the firmware's stall
        detection stops the pen; the wheel resumes once it is clear."""
        self.jammed.set(not self.jammed.get())
        if self.board:
            self.board.jam(self.jammed.get())

    def poll_box(self):
        """Ask the controller where the pen is and draw what the hardware is doing."""
        self.root.after(STATUS_MS, self.poll_box)
        if not self.mcu:
            return
        self.mcu.request_status()
        st = self.mcu.status
        if st:
            sx = -1.0 if self.mirror.get() else 1.0
            xy = (sx * st["x"], st["y"])                  # back to palm coordinates
            down = (self.board.pen > 0) if self.board else bool(st["pen"])
            cells = self.board.braille if self.board else (st["b1"], st["b2"])
            if down and self.s.mode != "braille":
                if not self.pen_down or not self.ink:
                    self.ink.append([])
                self.ink[-1].append(xy)
                self._redraw_ink()
            moved = xy != self.pen_xy or down != self.pen_down
            self.pen_xy, self.pen_down = xy, down
            if cells != self.cells:
                self.cells = cells
                self._draw_braille([protocol.mask_dots(c) for c in cells])
            if moved:
                self._draw_pen()
                self._render_3d()
        if self.board and self.board.fb_version != self.fb_seen:
            self.fb_seen = self.board.fb_version
            self._render_speaker()

    # ---------------- live 3D (CAD) view
    def init_3d(self):
        if cad_render is None:
            self.view3d_status.configure(text="3D view needs numpy")
            return
        if not os.path.exists(cad_render.MESH):
            self.view3d_status.configure(text="building CAD model with FreeCAD (about 1 min)...")
            threading.Thread(target=self._build_mesh, daemon=True).start()
            return
        self.scene = cad_render.Scene(cad_render.MESH)
        self.select_view()

    def _build_mesh(self):
        macro = os.path.join(cad_render.HERE, "haptic_box_v2.FCMacro")
        env = dict(os.environ, HAPTIC_DUMP=cad_render.MESH)
        try:
            subprocess.run(["freecadcmd", macro], cwd=cad_render.HERE, env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
            self.inbox.put(("mesh_ready", ""))
        except Exception as e:
            self.inbox.put(("error", "Could not build the CAD model (is FreeCAD installed?): %s" % e))

    def select_view(self):
        if self.scene is None:
            return
        key = (self.view_name.get(), self.hand_size.get())
        if key in self.live_cache:
            self.live = self.live_cache[key]
            self._render_3d(force=True)
            return
        self.view3d_status.configure(text="preparing '%s' view, %s hand..." % key)
        d, c, ext, alpha = VIEWS_3D[key[0]]

        def work():
            lv = cad_render.LiveView(self.scene, d, c, ext, VIEW_3D_SIZE, hide=HIDE_3D, alpha=alpha,
                                     hand=key[1])
            self.inbox.put(("view_ready", (key, lv)))
        threading.Thread(target=work, daemon=True).start()

    def press(self, button):
        """Show the digit that would press `button` on the box doing so in the 3D view."""
        self.hand_pose = button
        self._render_3d(force=True)

        def release():
            if self.hand_pose == button:
                self.hand_pose = "rest"
                self._render_3d(force=True)
        self.root.after(int(PRESS_S * 1000), release)

    def _render_3d(self, force=False):
        if getattr(self, "live", None) is None or (not force and self.tabs.index("current") != 0):
            return
        now = time.monotonic()
        if not force and now < self.frame_due:
            return
        x, y = self.pen_xy
        dy = self.scene.palm_offset(self.hand_size.get())   # letters centred on this hand's palm
        down = 1.0 if self.pen_down else 0.0
        pts = [(px, py + dy, 0.0) for seg in self.ink for px, py in seg]
        ink = self.scene.ink_points(*zip(*pts)) if pts else None
        img = self.live.frame(x, y + dy, down, ink, self.hand_pose)
        self.photo.configure(data=cad_render.ppm(img), format="PPM")
        self.frame_due = now + max(0.04, 1.5 * (time.monotonic() - now))

    # ---------------- UI
    def _build_ui(self):
        st = ttk.Style()
        st.configure("Big.TButton", font=("Sans", 12), padding=6)
        left = tk.Frame(self.root, bg=COL["bg"])
        left.pack(side="left", fill="y", padx=10, pady=10)
        right = tk.Frame(self.root, bg=COL["bg"])
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.tabs = ttk.Notebook(left)
        self.tabs.pack(fill="both", expand=True)
        # tab 1: live 3D simulation of the CAD model
        t3 = tk.Frame(self.tabs, bg="white")
        self.tabs.add(t3, text="  3D box (CAD model)  ")
        bar = tk.Frame(t3, bg="white")
        bar.pack(fill="x", pady=(4, 0))
        tk.Label(bar, text="View:", bg="white").pack(side="left", padx=(6, 2))
        self.view_name = tk.StringVar(value="Cut-away")
        vb = ttk.Combobox(bar, textvariable=self.view_name, values=list(VIEWS_3D), state="readonly",
                          width=22)
        vb.pack(side="left")
        vb.bind("<<ComboboxSelected>>", lambda e: self.select_view())
        self.view3d_status = tk.Label(bar, text="", bg="white", fg="#777")
        self.view3d_status.pack(side="left", padx=8)
        self.photo = tk.PhotoImage(width=VIEW_3D_SIZE[0], height=VIEW_3D_SIZE[1])
        self.view3d = tk.Label(t3, image=self.photo, bg="white")
        self.view3d.pack()
        # tab 2: the palm as felt
        t2 = tk.Frame(self.tabs, bg=COL["bg"])
        self.tabs.add(t2, text="  Palm (as felt)  ")
        self.cv = tk.Canvas(t2, width=CANVAS_W, height=CANVAS_H, bg=COL["bg"], highlightthickness=0)
        self.cv.pack()
        tk.Label(t2, text="Simulated palm view (as felt on your palm)", bg=COL["bg"],
                 fg="#666").pack()

        top = tk.Frame(right, bg=COL["bg"])
        top.pack(fill="x")
        self.letter_lbl = tk.Label(top, text=" ", font=("Sans", 72, "bold"), width=2, bg="white",
                                   relief="groove")
        self.letter_lbl.pack(side="left")
        bf = tk.Frame(top, bg=COL["bg"])
        bf.pack(side="left", padx=16)
        tk.Label(bf, text="Braille cells (index, middle finger)", bg=COL["bg"]).pack(anchor="w")
        self.br = tk.Canvas(bf, width=150, height=110, bg="white", highlightthickness=1)
        self.br.pack(anchor="w")
        self.br_txt = tk.Label(bf, text="", font=("Sans", 20), bg=COL["bg"])
        self.br_txt.pack(anchor="w")
        self._draw_braille([])

        tk.Label(right, text="Heard / written", bg=COL["bg"], anchor="w").pack(fill="x", pady=(12, 0))
        self.txt = tk.Text(right, height=9, width=48, wrap="word", font=("Sans", 15),
                           relief="groove", padx=8, pady=6)
        self.txt.pack(fill="both", expand=True)
        for tag in ("done", "queued", "partial", "cancelled"):
            self.txt.tag_configure(tag, foreground=COL[tag])
        self.txt.tag_configure("cancelled", overstrike=True)
        self.txt.tag_configure("current", foreground=COL["current"], background=COL["current_bg"])
        self.txt.tag_configure("partial", font=("Sans", 15, "italic"))
        self.txt.configure(state="disabled")

        self.status = tk.Label(right, text="", bg=COL["bg"], anchor="w", font=("Sans", 11))
        self.status.pack(fill="x", pady=4)

        row = tk.Frame(right, bg=COL["bg"])
        row.pack(fill="x", pady=4)
        self.entry = ttk.Entry(row, font=("Sans", 14))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.write_typed())
        ttk.Button(row, text="Write", style="Big.TButton", command=self.write_typed).pack(side="left", padx=4)

        s = self.s
        row = tk.Frame(right, bg=COL["bg"])
        row.pack(fill="x", pady=4)
        self.listen_btn = ttk.Button(row, text="🎤 Listen (L)", style="Big.TButton", command=self.toggle_listen)
        self.listen_btn.pack(side="left")
        self.pause_btn = ttk.Button(row, text="⏸ Pause (Space)", style="Big.TButton",
                                    command=lambda: self.box("pause"))
        self.pause_btn.pack(side="left", padx=4)
        ttk.Button(row, text="↺ Repeat (R)", style="Big.TButton",
                   command=lambda: self.box("repeat")).pack(side="left")
        ttk.Button(row, text="− Slower (−)", style="Big.TButton",
                   command=lambda: self.box("slower")).pack(side="left", padx=4)
        ttk.Button(row, text="+ Faster (+)", style="Big.TButton",
                   command=lambda: self.box("faster")).pack(side="left")
        ttk.Button(row, text="⠿/ Mode (M)", style="Big.TButton",
                   command=lambda: self.box("mode")).pack(side="left", padx=4)
        row = tk.Frame(right, bg=COL["bg"])
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="✕ Reset (Esc)", style="Big.TButton",
                   command=lambda: self.box("reset")).pack(side="left")
        ttk.Button(row, text="⏭ Skip (S)", style="Big.TButton", command=s.skip).pack(side="left", padx=4)
        ttk.Button(row, text="Clear (C)", style="Big.TButton", command=self.clear).pack(side="left")
        ttk.Button(row, text="🖵 Speaker display (D)", style="Big.TButton",
                   command=self.open_speaker).pack(side="left", padx=4)
        ttk.Button(row, text="Cover test (T)", style="Big.TButton", command=self.open_trial).pack(side="left")

        sf = ttk.LabelFrame(right, text="Settings")
        sf.pack(fill="x", pady=8)
        self.speed = tk.DoubleVar(value=s.speed)
        self.size = tk.DoubleVar(value=s.letter_h)
        self.mode = tk.StringVar(value=s.mode)
        self.hand_on = tk.BooleanVar(value=s.hand_present)
        self.hand_size = tk.StringVar(value="medium")
        self.mirror = tk.BooleanVar(value=True)
        self.model = tk.StringVar(value="en-us")
        self.port = tk.StringVar()
        # settings -> session (the session is the single source of truth)
        self.speed.trace_add("write", lambda *_: s.speed != self.speed.get() and s.set_speed(self.speed.get()))
        self.size.trace_add("write", lambda *_: setattr(s, "letter_h", self.size.get()))
        self.mirror.trace_add("write", lambda *_: self.mcu and setattr(self.mcu, "mirror", self.mirror.get()))
        self.mode.trace_add("write", lambda *_: s.mode != self.mode.get() and s.set_mode(self.mode.get()))

        def scale(label, var, lo, hi, r):
            f = tk.Frame(sf)
            f.pack(fill="x", padx=6)
            tk.Label(f, text=label, width=16, anchor="w").pack(side="left")
            tk.Scale(f, variable=var, from_=lo, to=hi, resolution=r, orient="horizontal",
                     length=220).pack(side="left")

        scale("Speed (×)", self.speed, SPEED_MIN, SPEED_MAX, 0.1)
        scale("Letter height (mm)", self.size, 30, 60, 5)
        f = tk.Frame(sf)
        f.pack(fill="x", padx=6, pady=2)
        tk.Label(f, text="Output", width=16, anchor="w").pack(side="left")
        for v in MODES:
            ttk.Radiobutton(f, text=MODE_NAME[v], value=v, variable=self.mode).pack(side="left")
        f = tk.Frame(sf)
        f.pack(fill="x", padx=6, pady=2)
        tk.Label(f, text="Hand size (3D)", width=16, anchor="w").pack(side="left")
        for v, t in (("small", "Small (~5th % woman)"), ("medium", "Medium (~50th % man)"),
                     ("large", "Large (~95th % man)")):
            ttk.Radiobutton(f, text=t, value=v, variable=self.hand_size,
                            command=self.select_view).pack(side="left")
        ttk.Checkbutton(f, text="on the box (H)", variable=self.hand_on,
                        command=lambda: self.set_hand(self.hand_on.get())).pack(side="left", padx=8)
        self.jammed = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="block the pen (J)", variable=self.jammed,
                        command=lambda: self.board and self.board.jam(self.jammed.get())).pack(side="left")
        f = tk.Frame(sf)
        f.pack(fill="x", padx=6, pady=2)
        tk.Label(f, text="Speech model", width=16, anchor="w").pack(side="left")
        ttk.Entry(f, textvariable=self.model, width=24).pack(side="left")
        tk.Label(f, text=" language code or model folder", fg="#777").pack(side="left")

        f = tk.Frame(sf)
        f.pack(fill="x", padx=6, pady=(2, 6))
        tk.Label(f, text="Box controller", width=16, anchor="w").pack(side="left")
        self.board_lbl = tk.Label(f, text="none", fg="#555", width=26, anchor="w")
        self.board_lbl.pack(side="left")
        cb = ttk.Combobox(f, textvariable=self.port, width=14, values=[d for d, _ in serial_ports()])
        cb.configure(postcommand=lambda: cb.configure(values=[d for d, _ in serial_ports()]))
        cb.pack(side="left")
        self.conn_btn = ttk.Button(f, text="Use real board", command=self.toggle_connect)
        self.conn_btn.pack(side="left", padx=4)
        ttk.Checkbutton(f, text="mirror (palm-down)", variable=self.mirror).pack(side="left")

        keys = {k: (lambda a=a: self.box(a)) for k, a in protocol.DEMO_KEYS.items()}
        keys.update({"s": s.skip, "c": self.clear, "l": self.toggle_listen, "d": self.open_speaker,
                     "t": self.open_trial, "h": lambda: self.set_hand(not self.hand_on.get()),
                     "j": self.toggle_jam})
        for k, fn in keys.items():
            self.root.bind_all("<%s>" % k, lambda e, fn=fn: None if isinstance(e.widget, (tk.Entry, ttk.Entry))
                               else fn())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self._status_msg = "Type something and press Enter, or press Listen and speak."

    def _refresh_status(self):
        s = self.s
        q = "Waiting: %d words (~%.0f s)" % (len(s.words), s.behind_s()) if s.words else "Queue empty"
        hw = "simulated box" if self.board else "box on %s" % self.mcu.t.name if self.mcu else "no controller"
        self.status.configure(text="%s   ·   %s   ·   %s   ·   speed %.1f×   ·   %s%s%s" % (
            q, hw, MODE_NAME[s.mode], s.speed, self._status_msg,
            "   ·   PAUSED" if s.paused else "", "" if s.hand_present else "   ·   NO HAND"))

    # ---------------- palm canvas
    def to_cv(self, x, y):
        return CX + x * SCALE, CY - y * SCALE

    def _draw_static(self):
        c = self.cv
        s = SCALE
        # palm and fingers (palm-view: fingertips up, thumb on the right for a right hand)
        c.create_oval(CX - 48 * s, CY - 55 * s, CX + 48 * s, CY + 55 * s, fill=COL["palm"],
                      outline=COL["palm_edge"], width=2)
        for fx, fl in ((-30, 30), (-10, 38), (10, 36), (30, 28)):
            c.create_oval(CX + (fx - 8) * s, CY - (50 + fl) * s, CX + (fx + 8) * s, CY - 46 * s,
                          fill=COL["palm"], outline=COL["palm_edge"])
        w = pw.WORKSPACE / 2
        c.create_rectangle(*self.to_cv(-w - 5, w + 5), *self.to_cv(w + 5, -w - 5), dash=(4, 3),
                           outline=COL["window"])
        self.rail_x = c.create_line(0, 0, 0, 0, fill=COL["rail"], width=5)
        self.rail_y = c.create_line(0, 0, 0, 0, fill=COL["rail"], width=5)
        self.old_ink_ids, self.ink_ids = [], []
        self.pen_id = c.create_oval(0, 0, 0, 0, fill=COL["pen_up"], outline="")
        self.cv_label = c.create_text(CANVAS_W / 2, CANVAS_H - 18, text="", font=("Sans", 12))
        self._draw_pen()

    def _draw_pen(self):
        x, y = self.pen_xy
        z = 0.0 if self.pen_down else pw.PEN_LIFT
        px, py = self.to_cv(x, y)
        self.cv.coords(self.rail_x, 10, py, CANVAS_W - 10, py)        # crossed rails
        self.cv.coords(self.rail_y, px, 10, px, CANVAS_H - 40)
        r = 9 if z < 0.5 else 6
        self.cv.coords(self.pen_id, px - r, py - r, px + r, py + r)
        self.cv.itemconfigure(self.pen_id, fill=COL["pen_down"] if z < 0.5 else COL["pen_up"])
        self.cv.tag_raise(self.pen_id)

    def _redraw_ink(self):
        for i in self.ink_ids + self.old_ink_ids:
            self.cv.delete(i)
        self.ink_ids, self.old_ink_ids = [], []
        for pts, ids, col, wd in ((self.old_ink, self.old_ink_ids, COL["old_ink"], 4),
                                  (self.ink, self.ink_ids, COL["ink"], 6)):
            for seg in pts:
                if len(seg) > 1:
                    flat = [v for p in seg for v in self.to_cv(*p)]
                    ids.append(self.cv.create_line(*flat, fill=col, width=wd, capstyle="round",
                                                   joinstyle="round"))
        self.cv.tag_raise(self.rail_x)
        self.cv.tag_raise(self.rail_y)
        self.cv.tag_raise(self.pen_id)

    # ---------------- Braille cells
    def _draw_braille(self, cells):
        b = self.br
        b.delete("all")
        for k in range(2):
            dots = cells[k] if k < len(cells) else ()
            x0 = 25 + k * 65
            for d in range(1, 7):
                col, rowi = (0 if d <= 3 else 1), (d - 1) % 3
                x, y = x0 + col * 26, 22 + rowi * 32
                on = d in dots
                b.create_oval(x - 9, y - 9, x + 9, y + 9, fill=COL["dot_on"] if on else COL["dot_off"],
                              outline="")

    # ---------------- transcript
    def _render_transcript(self):
        t = self.txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        for word, _, state in self.s.transcript[-200:]:
            t.insert("end", word.upper() + " ", state)
        if self.s.partial:
            t.insert("end", self.s.partial + "…", "partial")
        t.configure(state="disabled")
        t.see("end")

    def write_typed(self):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        self.s.add_text(text)

    def tick(self):
        self.root.after(TICK_MS, self.tick)
        self.s.tick()

    def clear(self):
        self.s.clear()
        self.cv.itemconfigure(self.cv_label, text="")

    # ---------------- speaker display: rendered from the SAME messages the box's display gets
    def open_speaker(self):
        if self.speaker is not None and self.speaker.winfo_exists():
            self.speaker.lift()
            return
        w = self.speaker = tk.Toplevel(self.root)
        w.title("ComLang - speaker display")
        w.configure(bg="black")
        bar = tk.Frame(w, bg="black")             # packed first so it is never cut off
        bar.pack(side="bottom", fill="x", padx=20, pady=10)
        tk.Button(bar, text="✕  RESET  (output is wrong)", font=("Sans", 18, "bold"), bg="#c0392b", fg="white",
                  activebackground="#e74c3c", command=lambda: self.box("reset")).pack(side="left")
        tk.Button(bar, text="⏸ Pause", font=("Sans", 18),
                  command=lambda: self.box("pause")).pack(side="left", padx=10)
        if self.board:                            # the firmware's own LCD pixels, 2x
            tk.Label(w, text="The box's display, as drawn by the firmware (480 x 320)", bg="black",
                     fg="#777").pack(side="top", anchor="w", padx=20, pady=(10, 0))
            self.sp_img = tk.PhotoImage(width=LCD_W * 2, height=LCD_H * 2)
            tk.Label(w, image=self.sp_img, bg="black", bd=0).pack(padx=20, pady=6)
        else:                                     # real board: same messages, drawn by the app
            w.geometry("1000x420")
            self.sp_img = None
            self.sp_now = tk.Text(w, height=1, font=("Sans", 54, "bold"), bg="black", fg="white", bd=0,
                                  highlightthickness=0)
            self.sp_now.pack(fill="x", padx=20, pady=(16, 0))
            self.sp_now.tag_configure("done", foreground="#777777")
            self.sp_now.tag_configure("cur", foreground="black", background="#ffd84a")
            self.sp_now.tag_configure("todo", foreground="white")
            self.sp_status = tk.Label(w, text="", font=("Sans", 16), bg="black", fg="#bbbbbb", anchor="w")
            self.sp_status.pack(side="bottom", fill="x", padx=20)
            self.sp_txt = tk.Text(w, height=3, font=("Sans", 26), wrap="word", bg="black", fg="#bbbbbb", bd=0,
                                  highlightthickness=0)
            self.sp_txt.pack(fill="both", expand=True, padx=20)
            for tag, col in (("done", "#9a9a9a"), ("current", "#ffd84a"), ("queued", "#ffffff"),
                             ("cancelled", "#e0584a"), ("partial", "#777777")):
                self.sp_txt.tag_configure(tag, foreground=col)
            self.sp_txt.tag_configure("cancelled", overstrike=True)
        self.fb_seen = -1
        self._render_speaker()

    def _render_speaker(self):
        if self.speaker is None or not self.speaker.winfo_exists():
            return
        if self.sp_img is not None:
            raw = self.board.frame() if self.board else None
            if raw:
                import numpy as np
                v = np.frombuffer(raw, "<u2").reshape(LCD_H, LCD_W)
                rgb = np.dstack(((v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3)).astype(np.uint8)
                rgb = rgb.repeat(2, 0).repeat(2, 1)
                self.sp_img.configure(data=b"P6 %d %d 255\n" % (LCD_W * 2, LCD_H * 2) + rgb.tobytes(),
                                      format="PPM")
            return
        st = protocol.parse_display(protocol.display_lines(self.s.display_state()))
        t = self.sp_now
        t.configure(state="normal")
        t.delete("1.0", "end")
        for i, c in enumerate(st["letters"]):
            t.insert("end", c, "done" if i < st["k"] else "cur" if i == st["k"] else "todo")
        t.configure(state="disabled")
        t = self.sp_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        for word, state in st["transcript"]:
            t.insert("end", word + " ", state)
        if st["partial"]:
            t.insert("end", st["partial"] + "…", "partial")
        t.configure(state="disabled")
        t.see("end")
        self.sp_status.configure(text="%s · %d word(s) waiting%s%s" % (
            MODE_NAME[st["mode"]], st["waiting"], " · PAUSED" if st["paused"] else "",
            "" if st["hand"] else " · NO HAND"))

    def open_trial(self):
        if self.trial is not None and self.trial.win.winfo_exists():
            self.trial.win.lift()
        else:
            self.trial = CoverTrial(self)

    def toggle_listen(self):
        if self.listener and self.listener.is_alive():
            self.listener.stop()
            self.listener = None
            self.listen_btn.configure(text="🎤 Listen (L)")
            self.s.set_partial("")
        else:
            self.listener = Listener(self.model.get().strip() or "en-us", self.inbox)
            self.listener.start()
            self.listen_btn.configure(text="■ Stop listening (L)")

    def toggle_connect(self):
        """Switch between the simulated board and a real one on USB."""
        if self.board is None and self.mcu:              # real -> simulated
            self._detach()
            self.start_sim()
            self.conn_btn.configure(text="Use real board")
            return
        port = self.port.get().strip()
        if not port:
            self.s.say("Pick the box controller's USB port first")
            return
        try:
            transport = SerialTransport(port)
        except ImportError:
            self.s.say("A real board needs:  pip install pyserial")
            return
        except Exception as e:
            self.s.say("Could not open %s: %s" % (port, e))
            return
        self._detach()
        self._attach(transport)
        self.board_lbl.configure(text="real box on %s" % port)
        self.conn_btn.configure(text="Use simulated box")

    def poll_inbox(self):
        self.root.after(50, self.poll_inbox)
        while True:
            try:
                kind, text = self.inbox.get_nowait()
            except queue.Empty:
                break
            if kind == "mesh_ready":
                self.init_3d()
            elif kind == "view_ready":
                key, lv = text
                self.live_cache[key] = lv
                if key == (self.view_name.get(), self.hand_size.get()):
                    self.live = lv
                    self.view3d_status.configure(text="")
                    self._render_3d(force=True)
            elif kind == "action":                       # a control on the box, from the firmware
                self.s.handle(text)
            elif kind == "fault":                        # the firmware stopped by itself (stall)
                self.s.fault(text)
            elif kind == "final":
                self.s.set_partial("")
                self.s.add_text(text)
            elif kind == "partial":
                self.s.set_partial(text)
            elif kind in ("status", "error"):
                self.s.say(text)
                if kind == "error" and self.listener and not self.listener.is_alive():
                    self.listen_btn.configure(text="🎤 Listen (L)")
                    self.listener = None

    def quit(self):
        if self.listener:
            self.listener.stop()
        self._detach()
        self.root.destroy()



class CoverTrial:
    """Experiment T13: how well letters are recognised through different cover materials.
    The operator picks the material (and tip / force), the app writes random letters one by
    one; after each, the operator types what the participant reports. Every answer is appended
    to trials/cover_trials.csv; the window shows accuracy per material so far."""
    LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, app):
        self.app = app
        w = self.win = tk.Toplevel(app.root)
        w.title("ComLang - cover material test (T13)")
        self.vars = {k: tk.StringVar(value=v) for k, v in (
            ("participant", "P01"), ("cover", COVERS[0]), ("tip", "T10 (1.0 mm radius)"),
            ("force", "0.6 N"), ("n", "10"))}
        g = tk.Frame(w)
        g.pack(fill="x", padx=10, pady=8)
        for r, (k, label) in enumerate((("participant", "Participant"), ("cover", "Cover material"),
                                         ("tip", "Pen tip"), ("force", "Force"), ("n", "Letters per block"))):
            tk.Label(g, text=label, width=16, anchor="w").grid(row=r, column=0, sticky="w")
            if k == "cover":
                ttk.Combobox(g, textvariable=self.vars[k], values=COVERS, width=34).grid(row=r, column=1, sticky="w")
            else:
                ttk.Entry(g, textvariable=self.vars[k], width=36).grid(row=r, column=1, sticky="w")
        self.start_btn = ttk.Button(w, text="Start block", command=self.start)
        self.start_btn.pack(anchor="w", padx=10)
        self.info = tk.Label(w, text="Letter size and speed come from the main window. Mode is set to palm only.",
                             font=("Sans", 13), anchor="w", justify="left")
        self.info.pack(fill="x", padx=10, pady=6)
        f = tk.Frame(w)
        f.pack(fill="x", padx=10)
        tk.Label(f, text="Participant says:").pack(side="left")
        self.answer = ttk.Entry(f, width=6, font=("Sans", 18), state="disabled")
        self.answer.pack(side="left", padx=6)
        self.answer.bind("<Return>", lambda e: self.record())
        ttk.Button(f, text="Repeat letter", command=self.repeat).pack(side="left")
        self.summary = tk.Label(w, text="", font=("TkFixedFont", 11), anchor="w", justify="left")
        self.summary.pack(fill="x", padx=10, pady=8)
        self.seq, self.target, self.t_done = [], None, None
        self.show_summary()

    def start(self):
        try:
            n = max(1, int(self.vars["n"].get()))
        except ValueError:
            n = 10
        self.seq = random.sample(self.LETTERS, min(n, 26)) + random.choices(self.LETTERS, k=max(0, n - 26))
        self.app.clear()
        self.app.s.set_mode("palm")
        self.start_btn.configure(state="disabled")
        self.next()

    def next(self):
        if not self.seq:
            self.target = None
            self.start_btn.configure(state="normal")
            self.info.configure(text="Block finished. Change the cover and start the next block.")
            return
        self.target = self.seq.pop(0)
        self.present()

    def present(self):
        self.answer.configure(state="disabled")
        self.info.configure(text="Writing letter %d ... (operator: %s)" % (
            int(self.vars["n"].get() or 10) - len(self.seq), self.target))
        self.app.s.add_text(self.target)
        self.win.after(200, self.wait)

    def repeat(self):
        if self.target and self.app.s.idle():
            self.present()

    def wait(self):
        if not self.win.winfo_exists():
            return
        if self.app.s.idle():
            self.t_done = time.monotonic()
            self.answer.configure(state="normal")
            self.answer.delete(0, "end")
            self.answer.focus_set()
            self.info.configure(text="Ask the participant which letter it was, type it, press Enter (? = no idea).")
        else:
            self.win.after(200, self.wait)

    def record(self):
        if not self.target or self.t_done is None:
            return
        resp = self.answer.get().strip().upper()[:1] or "?"
        row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "participant": self.vars["participant"].get(),
               "cover": self.vars["cover"].get(), "tip": self.vars["tip"].get(), "force": self.vars["force"].get(),
               "letter_mm": self.app.s.letter_h, "speed": self.app.s.speed, "target": self.target,
               "response": resp, "correct": int(resp == self.target),
               "response_s": round(time.monotonic() - self.t_done, 1)}
        os.makedirs(os.path.dirname(TRIALS_CSV), exist_ok=True)
        new = not os.path.exists(TRIALS_CSV)
        with open(TRIALS_CSV, "a", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(row))
            if new:
                wr.writeheader()
            wr.writerow(row)
        self.t_done = None
        self.show_summary()
        self.next()

    def show_summary(self):
        stats = collections.OrderedDict()
        if os.path.exists(TRIALS_CSV):
            with open(TRIALS_CSV) as f:
                for r in csv.DictReader(f):
                    s = stats.setdefault(r["cover"], [0, 0])
                    s[0] += int(r["correct"])
                    s[1] += 1
        lines = ["%-32s %5s %7s" % ("cover", "n", "correct")]
        lines += ["%-32s %5d %6.0f%%" % (k[:32], n, 100.0 * c / n) for k, (c, n) in stats.items()]
        self.summary.configure(text="\n".join(lines) + "\n(%s)" % os.path.relpath(TRIALS_CSV))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
