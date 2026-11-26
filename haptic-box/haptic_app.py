#!/usr/bin/env python3
"""Haptic Palm Writer: desktop app for the haptic box.

Speak (or type) -> text -> the pen writes block capitals on the palm and the
Braille cells show the same letters. Without hardware it runs as a simulation;
with a GRBL board on USB it also drives the crossed-rail gantry.

    python3 haptic_app.py

Needs: numpy (always); vosk + sounddevice for listening; pyserial for hardware.

Keys (when the text box is not focused): Space pause/resume, R repeat word,
S skip to newest phrase, C clear, L listen on/off, +/- speed.
"""
import collections
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import palm_writer as pw

TICK_MS = int(pw.DT * 1000)
BRAILLE_ONLY_LETTER_S = 0.8      # how long a letter stays on the Braille cells in Braille-only mode
SCALE = 3.3                      # canvas px per mm
CANVAS_W, CANVAS_H = 420, 570
CX, CY = CANVAS_W / 2, 310       # canvas position of the palm centre

COL = dict(bg="#f7f7f5", palm="#f2d4c2", palm_edge="#c99a83", rail="#9aa4ad", ink="#1d4f7a",
           old_ink="#b9c9d8", pen_down="#c0392b", pen_up="#7f8c8d", window="#888888",
           done="#222222", current="#000000", current_bg="#ffe58a", queued="#9a9a9a",
           partial="#8a8a8a", dot_on="#222222", dot_off="#dddddd")


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
        root.title("Haptic Palm Writer")
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

        self._build_ui()
        self._draw_static()
        self.root.after(TICK_MS, self.tick)
        self.root.after(50, self.poll_inbox)

    # ---------------- UI
    def _build_ui(self):
        st = ttk.Style()
        st.configure("Big.TButton", font=("Sans", 12), padding=6)
        left = tk.Frame(self.root, bg=COL["bg"])
        left.pack(side="left", fill="y", padx=10, pady=10)
        right = tk.Frame(self.root, bg=COL["bg"])
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.cv = tk.Canvas(left, width=CANVAS_W, height=CANVAS_H, bg=COL["bg"], highlightthickness=0)
        self.cv.pack()
        tk.Label(left, text="Simulated palm view (as felt on your palm)", bg=COL["bg"],
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
        for tag in ("done", "queued", "partial"):
            self.txt.tag_configure(tag, foreground=COL[tag])
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
        ttk.Button(row, text="⏭ Skip (S)", style="Big.TButton", command=self.skip).pack(side="left", padx=4)
        ttk.Button(row, text="✕ Clear (C)", style="Big.TButton", command=self.clear).pack(side="left")

        sf = ttk.LabelFrame(right, text="Settings")
        sf.pack(fill="x", pady=8)
        self.speed = tk.DoubleVar(value=1.0)
        self.size = tk.DoubleVar(value=pw.LETTER_H)
        self.mode = tk.StringVar(value="both")
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
        for v, t in (("palm", "Palm writing"), ("braille", "Braille only"), ("both", "Both")):
            ttk.Radiobutton(f, text=t, value=v, variable=self.mode).pack(side="left")
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
                "minus": lambda: self.nudge_speed(-0.1), "equal": lambda: self.nudge_speed(0.1)}
        for k, fn in keys.items():
            self.root.bind("<%s>" % k, lambda e, fn=fn: None if e.widget == self.entry else fn())
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
        self.status.configure(text="%s   ·   %s   ·   speed %.1f×   ·   %s%s" % (
            q, hw, self.speed.get(), self._status_msg, "   ·   PAUSED" if self.paused else ""))

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
            if not self._start_next_word():
                return False
        kind, ch, data = self.events.pop(0)
        mode = self.mode.get()
        palm = mode in ("palm", "both")
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
        x, y, z = self.rows[i]
        if z < 0.5 and self.mode.get() != "braille":
            if self.pen[2] >= 0.5 or not self.ink:
                self.ink.append([])
            self.ink[-1].append((x, y))
            self._redraw_ink()
        self.pen = (x, y, z)
        self._draw_pen()
        self.row_i += self.speed.get()

    def _abort_current(self):
        self.events, self.rows, self.row_i = [], [], 0.0
        self.planner = pw.Planner()
        self.pen = (0.0, 0.0, pw.PEN_LIFT)
        self.ink, self.old_ink = [], []
        self._redraw_ink()
        self._draw_pen()
        if self.grbl:
            self.grbl.flush()

    # ---------------- controls
    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.configure(text="▶ Resume (Space)" if self.paused else "⏸ Pause (Space)")
        if self.grbl:
            self.grbl.realtime(b"!" if self.paused else b"~")
        self._refresh_status()

    def repeat(self):
        """Write the current word again from the start (or the last finished word)."""
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
        self.speed.set(round(min(2.0, max(0.5, self.speed.get() + d)), 1))
        self._refresh_status()

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
            if kind == "final":
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


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
