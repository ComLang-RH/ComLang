#!/usr/bin/env python3
"""ComLang: companion app for the haptic palm-writing box.

Speak (or type) -> text -> the pen writes block capitals on the palm and the
Braille cells show the same letter at the same time. Fully offline. Without hardware it
runs as a simulation; with a GRBL board on USB it also drives the crossed-bar gantry.

    python3 haptic_app.py

Needs: numpy (always); vosk + sounddevice for listening; pyserial for hardware.

Keys (when the text box is not focused): Space pause/resume (wheel press), R repeat word,
+/- faster/slower (wheel roll), M mode (both / palm / Braille), Esc reset (speaker),
S skip to newest phrase, C clear, L listen on/off, D speaker display, T cover test.
"""
import collections
import csv
import os
import random
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import subprocess

import palm_writer as pw

try:
    import cad_render
except ImportError:          # numpy missing etc. -> 2D palm view only
    cad_render = None

VIEW_3D_SIZE = (760, 680)
HIDE_3D = ()
HAND = {"HandDummy": 0.45, "ForearmDummy": 0.45}
VIEWS_3D = {   # name: (camera direction, centre, extent mm, alpha overrides)
    "Cut-away": ((0.5, -0.78, 0.75), (0, 150, 30), 470,
                 dict(HAND, TopPlate=0.82, Shell=0.9)),
    "Close-up at the pen": ((0.62, -0.62, 0.48), (0, 160, 38), 230,
                            dict(HAND, TopPlate=0.7, Shell=0.92)),
    "Top, through the hand": ((0, 0, 1), (0, 140, 0), 520,
                              dict(HAND, TopPlate=0.6, Shell=0.0)),
    "Side, through the box": ((1, -0.12, 0.18), (0, 140, 40), 520,
                              dict(HAND, TopPlate=0.75, Shell=0.85, ForearmPad=0.6)),
    "Product (outside)": ((0.55, -0.85, 0.62), (0, 140, 35), 520,
                          {"HandDummy": 0.0, "ForearmDummy": 0.0}),
}
PRESS_S = 0.7          # how long the 3D hand shows a digit pressing a button

TICK_MS = int(pw.DT * 1000)
BRAILLE_ONLY_LETTER_S = 0.8      # how long a letter stays on the Braille cells in Braille-only mode
FLASH_S = 0.5                    # Braille cue: all six dots up on both cells for this long
MODES = ("both", "palm", "braille")                       # Mode button cycles through these
MODE_NAME = {"both": "palm + Braille", "palm": "palm only", "braille": "Braille only"}
COVERS = ("none (open window)", "nitrile glove film 0.1 mm", "latex sheet 0.2 mm", "silicone sheet 0.5 mm",
          "TPU film 0.1 mm", "PET film 0.05 mm", "Lycra / elastane fabric", "PTFE film 0.1 mm")
TRIALS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trials", "cover_trials.csv")
SCALE = 3.3                      # canvas px per mm
CANVAS_W, CANVAS_H = 420, 570
CX, CY = CANVAS_W / 2, 310       # canvas position of the palm centre

COL = dict(bg="#f7f7f5", palm="#f2d4c2", palm_edge="#c99a83", rail="#9aa4ad", ink="#1d4f7a",
           old_ink="#b9c9d8", pen_down="#c0392b", pen_up="#7f8c8d", window="#888888",
           done="#222222", current="#000000", current_bg="#ffe58a", queued="#9a9a9a",
           partial="#8a8a8a", dot_on="#222222", dot_off="#dddddd", cancelled="#c0392b")


# ---------------------------------------------------------------- speech
class Listener(threading.Thread):
    """Mic -> Vosk. Posts ('status'|'error'|'partial'|'final', text) to `out`."""

    def __init__(self, model, out):
        super().__init__(daemon=True)
        self.model, self.out, self.stop_evt = model, out, threading.Event()

    def run(self):
        try:
            import json
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
        except ImportError:
            self.out.put(("error", "Listening needs:  pip install vosk sounddevice"))
            return
        try:
            SetLogLevel(-1)
            self.out.put(("status", "Loading speech model (first time downloads ~40 MB)..."))
            if os.path.isdir(self.model):
                if not os.path.isdir(os.path.join(self.model, "am")):
                    raise RuntimeError("%r is not a Vosk model folder" % self.model)
                m = Model(model_path=self.model)
            else:
                m = Model(lang=self.model)
            rate = int(sd.query_devices(kind="input")["default_samplerate"])
            rec = KaldiRecognizer(m, rate)
            audio = queue.Queue()
            with sd.RawInputStream(samplerate=rate, blocksize=rate // 4, dtype="int16",
                                   channels=1, callback=lambda d, *_: audio.put(bytes(d))):
                self.out.put(("status", "Listening (%d Hz)" % rate))
                while not self.stop_evt.is_set():
                    try:
                        data = audio.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        text = json.loads(rec.Result()).get("text", "")
                        if text:
                            self.out.put(("final", text))
                    else:
                        self.out.put(("partial", json.loads(rec.PartialResult()).get("partial", "")))
            self.out.put(("status", "Stopped listening"))
        except Exception as e:      # model download, no microphone, ...
            self.out.put(("error", "Speech: %s" % e))

    def stop(self):
        self.stop_evt.set()


# ---------------------------------------------------------------- hardware
class Grbl:
    """Streams G-code lines to a GRBL board, waiting for 'ok' after each line."""

    def __init__(self, port, log):
        import serial                    # pyserial
        self.log = log
        self.ser = serial.Serial(port, 115200, timeout=0.1)
        time.sleep(2.0)                  # GRBL resets when the port opens
        self.ser.reset_input_buffer()
        self.lines = queue.Queue()
        self.alive = True
        threading.Thread(target=self._run, daemon=True).start()
        self.send(["G21", "G90", "M5"])

    def send(self, lines):
        for ln in lines:
            self.lines.put(ln)

    def realtime(self, byte):            # '!' feed hold, '~' resume, b'\x18' reset
        self.ser.write(byte)

    def flush(self):
        with self.lines.mutex:
            self.lines.queue.clear()
        self.realtime(b"\x18")
        time.sleep(0.1)
        self.send(["$X", "M5"])

    def _run(self):
        while self.alive:
            try:
                ln = self.lines.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.ser.write((ln + "\n").encode())
                t0 = time.monotonic()
                while time.monotonic() - t0 < 30:
                    r = self.ser.readline().decode(errors="replace").strip()
                    if r == "ok":
                        break
                    if r.startswith(("error", "ALARM")):
                        self.log("GRBL %s on: %s" % (r, ln))
                        break
            except Exception as e:
                self.log("Serial: %s" % e)
                self.alive = False

    def close(self):
        self.alive = False
        try:
            self.ser.write(b"M5\n")
            self.ser.close()
        except Exception:
            pass


def serial_ports():
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except ImportError:
        return []


# ---------------------------------------------------------------- app
class App:
    def __init__(self, root):
        self.root = root
        root.title("ComLang")
        root.configure(bg=COL["bg"])
        self.inbox = queue.Queue()
        self.listener = None
        self.grbl = None

        # writing state
        self.words = collections.deque()       # (word, phrase_id) waiting
        self.transcript = []                   # [word, phrase_id, state] state: queued/current/done
        self.phrase_id = 0
        self.events = []                       # events of the current word
        self.rows, self.row_i = [], 0.0
        self.cur_word = None                   # index into transcript
        self.planner = pw.Planner()
        self.ink, self.old_ink = [], []
        self.pen = (0.0, 0.0, pw.PEN_LIFT)
        self.paused = False
        self.wrote_any = False
        self.partial = ""
        self.cues = collections.deque()        # touch cues (mode change, reset) before the next word
        self.letters, self.letter_k = [], 0
        self.speaker = None                    # speaker display window
        self.trial = None                      # cover-material test window

        self._build_ui()
        self._draw_static()
        self.root.after(TICK_MS, self.tick)
        self.root.after(50, self.poll_inbox)
        self.scene, self.live, self.live_cache, self.frame_due = None, None, {}, 0.0
        self.hand_pose = "rest"
        self.root.after(100, self.init_3d)

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
        if self.live is None or (not force and self.tabs.index("current") != 0):
            return
        now = time.monotonic()
        if not force and now < self.frame_due:
            return
        x, y, z = self.pen
        dy = self.scene.palm_offset(self.hand_size.get())   # letters centred on this hand's palm
        down = max(0.0, min(1.0, 1.0 - z / pw.PEN_LIFT))
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

        row = tk.Frame(right, bg=COL["bg"])
        row.pack(fill="x", pady=4)
        self.listen_btn = ttk.Button(row, text="🎤 Listen (L)", style="Big.TButton", command=self.toggle_listen)
        self.listen_btn.pack(side="left")
        self.pause_btn = ttk.Button(row, text="⏸ Pause (Space)", style="Big.TButton", command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=4)
        ttk.Button(row, text="↺ Repeat (R)", style="Big.TButton", command=self.repeat).pack(side="left")
        ttk.Button(row, text="− Slower (−)", style="Big.TButton",
                   command=lambda: self.nudge_speed(-0.1)).pack(side="left", padx=4)
        ttk.Button(row, text="+ Faster (+)", style="Big.TButton",
                   command=lambda: self.nudge_speed(0.1)).pack(side="left")
        self.mode_btn = ttk.Button(row, text="⠿/ Mode (M)", style="Big.TButton", command=self.cycle_mode)
        self.mode_btn.pack(side="left", padx=4)
        row = tk.Frame(right, bg=COL["bg"])
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="✕ Reset (Esc)", style="Big.TButton", command=self.reset).pack(side="left")
        ttk.Button(row, text="⏭ Skip (S)", style="Big.TButton", command=self.skip).pack(side="left", padx=4)
        ttk.Button(row, text="Clear (C)", style="Big.TButton", command=self.clear).pack(side="left")
        ttk.Button(row, text="🖵 Speaker display (D)", style="Big.TButton",
                   command=self.open_speaker).pack(side="left", padx=4)
        ttk.Button(row, text="Cover test (T)", style="Big.TButton", command=self.open_trial).pack(side="left")

        sf = ttk.LabelFrame(right, text="Settings")
        sf.pack(fill="x", pady=8)
        self.speed = tk.DoubleVar(value=1.0)
        self.size = tk.DoubleVar(value=pw.LETTER_H)
        self.mode = tk.StringVar(value="both")
        self.hand_size = tk.StringVar(value="medium")
        self.mirror = tk.BooleanVar(value=True)
        self.model = tk.StringVar(value="en-us")
        self.port = tk.StringVar()

        def scale(label, var, lo, hi, r):
            f = tk.Frame(sf)
            f.pack(fill="x", padx=6)
            tk.Label(f, text=label, width=16, anchor="w").pack(side="left")
            tk.Scale(f, variable=var, from_=lo, to=hi, resolution=r, orient="horizontal",
                     length=220).pack(side="left")

        scale("Speed (×)", self.speed, 0.5, 2.0, 0.1)
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
        f = tk.Frame(sf)
        f.pack(fill="x", padx=6, pady=2)
        tk.Label(f, text="Speech model", width=16, anchor="w").pack(side="left")
        ttk.Entry(f, textvariable=self.model, width=24).pack(side="left")
        tk.Label(f, text=" language code or model folder", fg="#777").pack(side="left")
        f = tk.Frame(sf)
        f.pack(fill="x", padx=6, pady=(2, 6))
        tk.Label(f, text="Box (GRBL, USB)", width=16, anchor="w").pack(side="left")
        self.port_cb = ttk.Combobox(f, textvariable=self.port, values=serial_ports(), width=16,
                                    postcommand=lambda: self.port_cb.configure(values=serial_ports()))
        self.port_cb.pack(side="left")
        self.conn_btn = ttk.Button(f, text="Connect", command=self.toggle_connect)
        self.conn_btn.pack(side="left", padx=4)
        ttk.Checkbutton(f, text="palm-down box (mirror)", variable=self.mirror).pack(side="left")

        keys = {"space": self.toggle_pause, "r": self.repeat, "s": self.skip, "c": self.clear,
                "l": self.toggle_listen, "plus": lambda: self.nudge_speed(0.1),
                "minus": lambda: self.nudge_speed(-0.1), "equal": lambda: self.nudge_speed(0.1),
                "KP_Add": lambda: self.nudge_speed(0.1), "KP_Subtract": lambda: self.nudge_speed(-0.1),
                "m": self.cycle_mode, "Escape": self.reset, "d": self.open_speaker, "t": self.open_trial}
        for k, fn in keys.items():
            self.root.bind_all("<%s>" % k, lambda e, fn=fn: None if isinstance(e.widget, (tk.Entry, ttk.Entry))
                               else fn())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.set_status("Type something and press Enter, or press Listen and speak.")

    def set_status(self, msg):
        self._status_msg = msg
        self._refresh_status()

    def _refresh_status(self):
        letters = sum(len([c for c in self.transcript[i][0] if c.isalnum()]) for i, _ in self.words)
        per_letter = 2.1 if self.mode.get() != "braille" else BRAILLE_ONLY_LETTER_S
        behind = letters * per_letter / self.speed.get()
        q = "Waiting: %d words (~%.0f s)" % (len(self.words), behind) if self.words else "Queue empty"
        hw = "box connected" if self.grbl else "simulation"
        self.status.configure(text="%s   ·   %s   ·   %s   ·   speed %.1f×   ·   %s%s" % (
            q, hw, MODE_NAME[self.mode.get()], self.speed.get(), self._status_msg,
            "   ·   PAUSED" if self.paused else ""))
        self._render_speaker()

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
        x, y, z = self.pen
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
        for word, _, state in self.transcript[-200:]:
            t.insert("end", word.upper() + " ", state)
        if self.partial:
            t.insert("end", self.partial + "…", "partial")
        t.configure(state="disabled")
        t.see("end")
        self._render_speaker()

    def add_text(self, text):
        words = [w for w in text.split() if any(c in pw.FONT or c in ".!" for c in w.upper())]
        if not words:
            return
        self.phrase_id += 1
        for w in words:
            self.transcript.append([w, self.phrase_id, "queued"])
            self.words.append((len(self.transcript) - 1, self.phrase_id))
        self._render_transcript()
        self._refresh_status()

    def write_typed(self):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        self.add_text(text)

    # ---------------- writing engine
    def _start_next_word(self):
        if not self.words:
            return False
        idx, _ = self.words.popleft()
        self.cur_word = idx
        self.transcript[idx][2] = "current"
        word = self.transcript[idx][0]
        ev = pw.word_events(word, last=True, height=self.size.get())
        if self.wrote_any:                         # word-space cue before every word but the first
            ev = [("tap", " ", 1), ("pause", " ", pw.T_WORD_GAP)] + ev
        self.events = ev
        self.letters = [c for c in word.upper() if c in pw.FONT]
        self.letter_k = 0
        self.wrote_any = True
        self._render_transcript()
        self._refresh_status()
        return True

    def _start_next_event(self):
        while not self.events:
            if self.cur_word is not None:
                self.transcript[self.cur_word][2] = "done"
                self.cur_word = None
                self._render_transcript()
            if self.cues:                          # touch cues go before the next word
                self.events.append(self.cues.popleft())
                continue
            if not self._start_next_word():
                return False
        kind, ch, data = self.events.pop(0)
        mode = self.mode.get()
        palm = mode in ("palm", "both")
        if kind == "flash":                        # Braille cue: all dots up, `data` times
            self._draw_braille([range(1, 7), range(1, 7)])
            self.br_txt.configure(text="⠿⠿")
            n = max(1, int(FLASH_S / pw.DT))
            self.rows = ([self.pen] * n + [None] * (n // 2)) * data
            self.row_i = 0.0
            return True
        if kind == "glyph":
            self.old_ink, self.ink = self.ink, []
            self.letter_lbl.configure(text=ch)
            word = self.transcript[self.cur_word][0].upper()
            prev = self.letters[self.letter_k - 1] if self.letter_k else ""
            self.letter_k += 1
            cells = pw.braille_cells(ch, prev) if mode in ("braille", "both") else []
            self._draw_braille(cells)
            self.br_txt.configure(text=pw.braille_unicode(ch))
            self.cv.itemconfigure(self.cv_label, text=word)
            self._redraw_ink()
            self._render_speaker()
        if palm:
            self.rows = self.planner.rows(kind, data)
            if self.grbl:
                self.grbl.send(pw.event_gcode(kind, data, self.mirror.get(), self.speed.get()))
        else:                                       # Braille only: just hold the letter
            dur = {"glyph": BRAILLE_ONLY_LETTER_S, "tap": 0.3}.get(kind, data if kind == "pause" else 0)
            self.rows = [self.pen] * max(1, int(dur / pw.DT))
        self.row_i = 0.0
        return True

    def tick(self):
        self.root.after(TICK_MS, self.tick)
        if self.paused:
            return
        if self.row_i >= len(self.rows) and not self._start_next_event():
            if self.letter_lbl.cget("text") != " " and not self.words:
                self.letter_lbl.configure(text=" ")
                self._draw_braille([])
                self.br_txt.configure(text="")
            return
        i = int(self.row_i)
        if self.rows[i] is None:                   # gap inside a Braille flash cue
            self._draw_braille([])
            self.row_i += self.speed.get()
            return
        x, y, z = self.rows[i]
        if z < 0.5 and self.mode.get() != "braille":
            if self.pen[2] >= 0.5 or not self.ink:
                self.ink.append([])
            self.ink[-1].append((x, y))
            self._redraw_ink()
        self.pen = (x, y, z)
        self._draw_pen()
        self._render_3d()
        self.row_i += self.speed.get()

    def _abort_current(self):
        self.events, self.rows, self.row_i = [], [], 0.0
        self.planner = pw.Planner()
        self.pen = (0.0, 0.0, pw.PEN_LIFT)
        self.ink, self.old_ink = [], []
        self._redraw_ink()
        self._draw_pen()
        self._render_3d(force=True)
        if self.grbl:
            self.grbl.flush()

    # ---------------- controls
    def toggle_pause(self):
        self.press("Wheel")                      # wheel press = pause / resume
        self.paused = not self.paused
        self.pause_btn.configure(text="▶ Resume (Space)" if self.paused else "⏸ Pause (Space)")
        if self.grbl:
            self.grbl.realtime(b"!" if self.paused else b"~")
        self._refresh_status()

    def repeat(self):
        """Write the current word again from the start (or the last finished word)."""
        self.press("Repeat")
        if self.cur_word is not None:
            idx = self.cur_word
        else:
            done = [i for i, w in enumerate(self.transcript) if w[2] == "done"]
            if not done:
                return
            idx = done[-1]
        self._abort_current()
        self.cur_word = None
        self.transcript[idx][2] = "queued"
        self.words.appendleft((idx, self.transcript[idx][1]))
        self._render_transcript()
        self.set_status("Repeating %s" % self.transcript[idx][0].upper())

    def skip(self):
        """Drop everything except the newest phrase."""
        if not self.words and self.cur_word is None:
            return
        newest = self.phrase_id
        self._abort_current()
        if self.cur_word is not None:
            self.transcript[self.cur_word][2] = "done"
            self.cur_word = None
        keep = collections.deque((i, p) for i, p in self.words if p == newest)
        for i, p in self.words:
            if p != newest:
                self.transcript[i][2] = "done"
        self.words = keep
        self._render_transcript()
        self.set_status("Skipped to the newest phrase")

    def clear(self):
        self._abort_current()
        self.cues.clear()
        self.words.clear()
        self.transcript.clear()
        self.cur_word, self.wrote_any, self.partial = None, False, ""
        self.letter_lbl.configure(text=" ")
        self._draw_braille([])
        self.br_txt.configure(text="")
        self.cv.itemconfigure(self.cv_label, text="")
        self._render_transcript()
        self.set_status("Cleared")

    def nudge_speed(self, d):
        """Thumb wheel roll: away from the palm = faster (+), in = slower (-)."""
        self.press("Wheel")
        self.speed.set(round(min(2.0, max(0.5, self.speed.get() + d)), 1))
        self._refresh_status()

    def _cue(self, palm_taps, flashes, long_press=False):
        """Queue a touch cue the user feels in the current mode: pen taps (or one long press)
        and/or Braille flashes (all dots up)."""
        m = self.mode.get()
        if m in ("palm", "both") and long_press:
            self.cues.append(("longtap", " ", 0.6))
        elif m in ("palm", "both") and palm_taps:
            self.cues.append(("tap", " ", palm_taps))
        if m in ("braille", "both") and flashes:
            self.cues.append(("flash", None, flashes))

    def cycle_mode(self):
        """Mode button: palm + Braille -> palm only -> Braille only. The new mode is confirmed
        by touch: a long pen press (0.6 s) when the pen is now on, one Braille flash when the cells
        are on. (One short tap is already the word gap, three taps the correction cue.)"""
        m = MODES[(MODES.index(self.mode.get()) + 1) % len(MODES)]
        self.mode.set(m)
        self._cue(0, 1, long_press=True)
        self.set_status("Mode: %s" % MODE_NAME[m])

    def reset(self):
        """Speaker's Reset: the speaker saw on the display that the output is wrong. Stop, drop the
        current and queued words (shown struck through) and send the correction cue: 3 pen taps
        and/or 2 Braille flashes, so the user knows to discard what they just felt."""
        dropped = ([self.cur_word] if self.cur_word is not None else []) + [i for i, _ in self.words]
        self._abort_current()
        for i in dropped:
            self.transcript[i][2] = "cancelled"
        self.words.clear()
        self.cur_word, self.wrote_any, self.letters = None, False, []
        self.cues.clear()
        if self.paused:
            self.toggle_pause()
        self._cue(3, 2)
        self.letter_lbl.configure(text=" ")
        self._render_transcript()
        self.set_status("Reset: %d word(s) dropped, correction cue sent" % len(dropped))

    # ---------------- speaker display (what the user is receiving, large, for the speaker)
    def open_speaker(self):
        if self.speaker is not None and self.speaker.winfo_exists():
            self.speaker.lift()
            return
        w = self.speaker = tk.Toplevel(self.root)
        w.title("ComLang - speaker display")
        w.configure(bg="black")
        w.geometry("1000x420")
        self.sp_now = tk.Text(w, height=1, font=("Sans", 54, "bold"), bg="black", fg="white", bd=0,
                              highlightthickness=0)
        self.sp_now.pack(fill="x", padx=20, pady=(16, 0))
        self.sp_now.tag_configure("done", foreground="#777777")
        self.sp_now.tag_configure("cur", foreground="black", background="#ffd84a")
        self.sp_now.tag_configure("todo", foreground="white")
        self.sp_txt = tk.Text(w, height=4, font=("Sans", 26), wrap="word", bg="black", fg="#bbbbbb", bd=0,
                              highlightthickness=0)
        self.sp_txt.pack(fill="both", expand=True, padx=20)
        for tag, col in (("done", "#9a9a9a"), ("current", "#ffd84a"), ("queued", "#ffffff"),
                         ("cancelled", "#e0584a"), ("partial", "#777777")):
            self.sp_txt.tag_configure(tag, foreground=col)
        self.sp_txt.tag_configure("cancelled", overstrike=True)
        bar = tk.Frame(w, bg="black")
        bar.pack(fill="x", padx=20, pady=10)
        tk.Button(bar, text="✕  RESET  (output is wrong)", font=("Sans", 18, "bold"), bg="#c0392b", fg="white",
                  activebackground="#e74c3c", command=self.reset).pack(side="left")
        tk.Button(bar, text="⏸ Pause", font=("Sans", 18), command=self.toggle_pause).pack(side="left", padx=10)
        self.sp_status = tk.Label(bar, text="", font=("Sans", 16), bg="black", fg="#bbbbbb")
        self.sp_status.pack(side="left", padx=10)
        self._render_speaker()

    def _render_speaker(self):
        if self.speaker is None or not self.speaker.winfo_exists():
            return
        t = self.sp_now
        t.configure(state="normal")
        t.delete("1.0", "end")
        if self.cur_word is not None and self.letters:
            k = self.letter_k - 1
            for i, c in enumerate(self.letters):
                t.insert("end", c, "done" if i < k else "cur" if i == k else "todo")
        t.configure(state="disabled")
        t = self.sp_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        for word, _, state in self.transcript[-60:]:
            t.insert("end", word.upper() + " ", state)
        if self.partial:
            t.insert("end", self.partial + "…", "partial")
        t.configure(state="disabled")
        t.see("end")
        q = len(self.words)
        self.sp_status.configure(text="%s · %d word(s) waiting%s" % (
            MODE_NAME[self.mode.get()], q, " · PAUSED" if self.paused else ""))

    # ---------------- cover-material recognition test (T13)
    def open_trial(self):
        if self.trial is not None and self.trial.win.winfo_exists():
            self.trial.win.lift()
        else:
            self.trial = CoverTrial(self)

    def idle(self):
        return not self.words and not self.events and self.cur_word is None and not self.cues and \
            self.row_i >= len(self.rows)

    def toggle_listen(self):
        if self.listener and self.listener.is_alive():
            self.listener.stop()
            self.listener = None
            self.listen_btn.configure(text="🎤 Listen (L)")
            self.partial = ""
            self._render_transcript()
        else:
            self.listener = Listener(self.model.get().strip() or "en-us", self.inbox)
            self.listener.start()
            self.listen_btn.configure(text="■ Stop listening (L)")

    def toggle_connect(self):
        if self.grbl:
            self.grbl.close()
            self.grbl = None
            self.conn_btn.configure(text="Connect")
            self.set_status("Box disconnected")
            return
        port = self.port.get().strip()
        if not port:
            self.set_status("Pick the box's USB port first")
            return
        try:
            self.grbl = Grbl(port, lambda m: self.inbox.put(("error", m)))
        except ImportError:
            self.set_status("Hardware needs:  pip install pyserial")
            return
        except Exception as e:
            self.set_status("Could not open %s: %s" % (port, e))
            return
        self.conn_btn.configure(text="Disconnect")
        self.set_status("Box connected on %s (zero = palm centre)" % port)

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
            elif kind == "final":
                self.partial = ""
                self.add_text(text)
            elif kind == "partial":
                if text != self.partial:
                    self.partial = text
                    self._render_transcript()
            elif kind == "status":
                self.set_status(text)
            elif kind == "error":
                self.set_status(text)
                if self.listener and not self.listener.is_alive():
                    self.listen_btn.configure(text="🎤 Listen (L)")
                    self.listener = None

    def quit(self):
        if self.listener:
            self.listener.stop()
        if self.grbl:
            self.grbl.close()
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
        self.app.mode.set("palm")
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
        self.app.add_text(self.target)
        self.win.after(200, self.wait)

    def repeat(self):
        if self.target and self.app.idle():
            self.present()

    def wait(self):
        if not self.win.winfo_exists():
            return
        if self.app.idle():
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
               "letter_mm": self.app.size.get(), "speed": self.app.speed.get(), "target": self.target,
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
