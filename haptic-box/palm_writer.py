#!/usr/bin/env python3
"""Text -> print-on-palm stroke trajectory for the haptic writing box.

Pipeline (this file covers steps 2-4; step 1 is optional via --live):
  1. speech -> text            (Vosk, offline, if installed)
  2. text   -> strokes         (single-stroke block capitals, all written on
                                the same spot of the palm, like print-on-palm)
  3. strokes -> timed path     (trapezoidal speed profile, pen up/down)
  4. path   -> joint angles    (5-bar parallel linkage inverse kinematics)

Coordinates (mm): origin = centre of the writing area on the palm,
+x = the reader's right, +y = toward the fingertips, z = pen lift above palm.

Usage:
    python3 palm_writer.py "HELLO WORLD"            # render palm_writer.gif
    python3 palm_writer.py "HELLO" --show            # live window
    python3 palm_writer.py "HELLO" --csv out.csv     # 5-bar joint trajectory (v1 box)
    python3 palm_writer.py "HELLO" --gcode out.nc --mirror   # GRBL G-code (v2 palm-down box)
    python3 palm_writer.py --check                   # workspace/kinematics check
    python3 palm_writer.py --live                    # mic -> Vosk (en-us) -> sim
    python3 palm_writer.py --live path/to/vosk-model # use a downloaded model
"""
import argparse
import sys
import numpy as np

# ---------------- parameters ----------------
LETTER_H = 45.0        # letter height on the palm (mm)
WORKSPACE = 70.0       # square the stylus must reach (mm)
# 5-bar linkage: motors at (-A, D) and (+A, D), proximal L1, distal L2
LINK_A, LINK_L1, LINK_L2, LINK_D = 20.0, 55.0, 80.0, 80.0
V_WRITE = 120.0        # mm/s while touching the palm
V_TRAVEL = 250.0       # mm/s pen up
ACCEL = 3000.0         # mm/s^2
PEN_LIFT = 6.0         # mm
T_PEN = 0.08           # s for pen down / up
T_LETTER_GAP = 0.25    # s pause between letters
T_WORD_GAP = 0.6       # s pause after the word-space cue
DT = 1 / 50            # s, servo update period (50 Hz)
# --------------------------------------------


# ---------- stroke font: block capitals on a unit-height grid ----------
def arc(cx, cy, rx, ry, a0, a1, n=None):
    """Elliptical arc from angle a0 to a1 (degrees, may run either way)."""
    n = n or max(4, int(abs(a1 - a0) / 10))
    t = np.radians(np.linspace(a0, a1, n))
    return list(zip(cx + rx * np.cos(t), cy + ry * np.sin(t)))


def L(*pts):
    return list(pts)


# Each glyph: list of strokes; each stroke: list of (x, y) in letter units.
# Stroke order follows ordinary handwriting so it feels familiar on the palm.
FONT = {
    "A": [L((0, 0), (.375, 1), (.75, 0)), L((.15, .4), (.6, .4))],
    "B": [L((0, 0), (0, 1)), L((0, 1), (.35, 1)) + arc(.35, .76, .3, .24, 90, -90)
          + L((0, .52), (.4, .52)) + arc(.4, .26, .32, .26, 90, -90) + L((0, 0))],
    "C": [arc(.4, .5, .4, .5, 45, 315)],
    "D": [L((0, 0), (0, 1)), L((0, 1), (.3, 1)) + arc(.3, .5, .4, .5, 90, -90) + L((0, 0))],
    "E": [L((.7, 1), (0, 1), (0, 0), (.7, 0)), L((0, .5), (.55, .5))],
    "F": [L((.7, 1), (0, 1), (0, 0)), L((0, .5), (.55, .5))],
    "G": [arc(.4, .5, .4, .5, 45, 360) + L((.45, .5))],
    "H": [L((0, 1), (0, 0)), L((.7, 1), (.7, 0)), L((0, .5), (.7, .5))],
    "I": [L((.35, 1), (.35, 0))],
    "J": [L((.6, 1), (.6, .3)) + arc(.3, .3, .3, .3, 0, -180)],
    "K": [L((0, 1), (0, 0)), L((.7, 1), (0, .45), (.7, 0))],
    "L": [L((0, 1), (0, 0), (.65, 0))],
    "M": [L((0, 0), (0, 1), (.4, .4), (.8, 1), (.8, 0))],
    "N": [L((0, 0), (0, 1), (.7, 0), (.7, 1))],
    "O": [arc(.4, .5, .4, .5, 90, 450)],
    "P": [L((0, 0), (0, 1), (.4, 1)) + arc(.4, .75, .3, .25, 90, -90) + L((0, .5))],
    "Q": [arc(.4, .5, .4, .5, 90, 450), L((.45, .25), (.85, -.05))],
    "R": [L((0, 0), (0, 1), (.4, 1)) + arc(.4, .75, .3, .25, 90, -90) + L((0, .5)),
          L((.3, .5), (.7, 0))],
    "S": [arc(.35, .75, .33, .25, 20, 270) + arc(.35, .25, .35, .25, 90, -160)],
    "T": [L((0, 1), (.7, 1)), L((.35, 1), (.35, 0))],
    "U": [L((0, 1), (0, .35)) + arc(.35, .35, .35, .35, 180, 360) + L((.7, 1))],
    "V": [L((0, 1), (.35, 0), (.7, 1))],
    "W": [L((0, 1), (.2, 0), (.4, .6), (.6, 0), (.8, 1))],
    "X": [L((0, 1), (.7, 0)), L((.7, 1), (0, 0))],
    "Y": [L((0, 1), (.35, .5), (.7, 1)), L((.35, .5), (.35, 0))],
    "Z": [L((0, 1), (.7, 1), (0, 0), (.7, 0))],
    "0": [arc(.3, .5, .3, .5, 90, 450)],
    "1": [L((.1, .8), (.35, 1), (.35, 0))],
    "2": [arc(.35, .7, .35, .3, 150, -20) + L((0, 0), (.7, 0))],
    "3": [arc(.35, .75, .33, .25, 150, -90) + arc(.35, .25, .35, .25, 90, -150)],
    "4": [L((.5, 0), (.5, 1), (0, .35), (.75, .35))],
    "5": [L((.65, 1), (.05, 1), (.02, .55)) + arc(.35, .3, .35, .3, 140, -150)],
    "6": [arc(.35, .5, .35, .5, 60, 200) + arc(.35, .3, .35, .3, 200, 560)],
    "7": [L((0, 1), (.7, 1), (.25, 0))],
    "8": [arc(.35, .75, .28, .25, 270, -90) + arc(.35, .25, .35, .25, 90, 450)],
    "9": [arc(.35, .7, .35, .3, 0, 360) + L((.7, .7), (.6, 0))],
    "?": [arc(.35, .75, .3, .25, 160, -60) + L((.35, .35)), L((.35, .08), (.35, 0))],
}
# Cues that are not letters (handled specially by text_to_strokes):
#   " "  -> one short tap at the centre, then a longer pause
#   "."  -> two quick taps (end of sentence)


def glyph_mm(ch, height=None):
    """Glyph strokes scaled to `height` (default LETTER_H) and centred on the origin."""
    h = height or LETTER_H
    strokes = [np.array(s, float) for s in FONT[ch]]
    allp = np.vstack(strokes)
    lo, hi = allp.min(0), allp.max(0)
    centre = np.array([(lo[0] + hi[0]) / 2, 0.5])
    return [(s - centre) * h for s in strokes]


def word_events(word, last=True, height=None):
    """Events for one word: ('glyph', ch, strokes) / ('tap', ch, n) / ('pause', ch, s)."""
    out = []
    for ch in word.upper():
        if ch in FONT:
            out += [("glyph", ch, glyph_mm(ch, height)), ("pause", ch, T_LETTER_GAP)]
        elif ch in ".!":
            out.append(("tap", ch, 2))
    if not last:
        out += [("tap", " ", 1), ("pause", " ", T_WORD_GAP)]
    return out


def text_to_events(text, height=None):
    words = text.split()
    for wi, word in enumerate(words):
        yield from word_events(word, wi == len(words) - 1, height)


# ---------- Braille (English Grade 1, uncontracted) ----------
_BR = dict(zip("abcdefghijklmnopqrstuvwxyz",
               "1 12 14 145 15 124 1245 125 24 245 13 123 134 1345 135 1234 12345 1235 234 "
               "2345 136 1236 2456 1346 13456 1356".split()))
_BR.update({".": "256", ",": "2", "?": "236", "!": "235", "'": "3", "-": "36", "#": "3456"})


def braille_cells(ch, prev=""):
    """Braille cells for one character as a list of dot-number tuples. A digit gets the
    number sign unless the previous character was also a digit."""
    c = ch.lower()
    if c.isdigit():
        cell = tuple(int(d) for d in _BR["jabcdefghi"[int(c)]])
        return [cell] if prev.isdigit() else [tuple(int(d) for d in _BR["#"]), cell]
    if c in _BR:
        return [tuple(int(d) for d in _BR[c])]
    return []


def braille_unicode(text):
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(" ")
        for cell in braille_cells(ch, text[i - 1] if i else ""):
            out.append(chr(0x2800 + sum(1 << (d - 1) for d in cell)))
    return "".join(out)


# ---------- timed path ----------
def profile(length, vmax, acc):
    """Trapezoidal motion: return arc-length samples s(t) at DT."""
    if length < 1e-9:
        return np.zeros(1)
    t_acc = vmax / acc
    if acc * t_acc ** 2 > length:           # triangle profile
        t_acc = np.sqrt(length / acc)
        vmax = acc * t_acc
    t_flat = (length - acc * t_acc ** 2) / vmax
    T = 2 * t_acc + t_flat
    t = np.arange(0, T + DT, DT).clip(max=T)
    s = np.where(t < t_acc, 0.5 * acc * t ** 2,
                 np.where(t < t_acc + t_flat, 0.5 * acc * t_acc ** 2 + vmax * (t - t_acc),
                          length - 0.5 * acc * (T - t) ** 2))
    return s


def follow(poly, vmax):
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    cum = np.concatenate(([0], np.cumsum(seg)))
    s = profile(cum[-1], vmax, ACCEL)
    return np.column_stack((np.interp(s, cum, poly[:, 0]), np.interp(s, cum, poly[:, 1])))


class Planner:
    """Turns events into (x, y, z) samples at DT, remembering pen position between calls,
    so a live app can plan one letter at a time."""

    def __init__(self):
        self.pos = np.zeros(2)
        self.z = PEN_LIFT

    def _hold(self, rows, seconds, zz=None):
        n = max(1, int(round(seconds / DT)))
        z0, z1 = self.z, (self.z if zz is None else zz)
        for k in range(n):
            rows.append((*self.pos, z0 + (z1 - z0) * (k + 1) / n))
        self.z = z1

    def _move(self, rows, poly, v):
        for p in follow(np.asarray(poly, float), v)[1:]:
            rows.append((*p, self.z))
        self.pos = np.asarray(poly[-1], float)

    def rows(self, kind, data):
        rows = []
        if kind == "glyph":
            for stroke in data:
                self._move(rows, [self.pos, stroke[0]], V_TRAVEL)
                self._hold(rows, T_PEN, 0.0)
                self._move(rows, stroke, V_WRITE)
                self._hold(rows, T_PEN, PEN_LIFT)
        elif kind == "tap":
            self._move(rows, [self.pos, (0.0, 0.0)], V_TRAVEL)
            for _ in range(data):
                self._hold(rows, T_PEN, 0.0)
                self._hold(rows, 0.05)
                self._hold(rows, T_PEN, PEN_LIFT)
        elif kind == "pause":
            self._hold(rows, data)
        elif kind == "home":
            self._move(rows, [self.pos, (0.0, 0.0)], V_TRAVEL)
        return rows


def build_path(text):
    """Return arrays t, x, y, z, and a list of (t_start, kind, ch) for captions."""
    rows, labels = [], []
    pl = Planner()
    for kind, ch, data in list(text_to_events(text)) + [("home", "", None)]:
        labels.append((len(rows) * DT, kind, ch))
        rows += pl.rows(kind, data)
    a = np.array(rows) if rows else np.zeros((1, 3))
    t = np.arange(len(a)) * DT
    return t, a[:, 0], a[:, 1], a[:, 2], labels


# ---------- G-code for a Cartesian (crossed-rail) gantry running GRBL ----------
def event_gcode(kind, data, mirror=False, speed=1.0):
    """GRBL G-code for one event. The pen solenoid is on the spindle-enable output
    (M3 = pen up into the palm, M5 = retract). Coordinates are relative to the palm
    centre (set it as work zero with G10 L20 P1 X0 Y0 during calibration).
    mirror=True flips x for the palm-down box (pen writes from below)."""
    sx = -1.0 if mirror else 1.0
    fw, ft = V_WRITE * 60 * speed, V_TRAVEL * 60 * speed

    def xy(p):
        return "X%.2f Y%.2f" % (sx * p[0], p[1])

    g = []
    if kind == "glyph":
        for stroke in data:
            g.append("G0 " + xy(stroke[0]))
            g += ["M3 S1000", "G4 P%.2f" % T_PEN]
            g += ["G1 %s F%.0f" % (xy(p), fw) for p in stroke[1:]]
            g += ["M5", "G4 P%.2f" % T_PEN]
    elif kind == "tap":
        g.append("G0 X0 Y0")
        for _ in range(data):
            g += ["M3 S1000", "G4 P%.2f" % (T_PEN + 0.05), "M5", "G4 P%.2f" % T_PEN]
    elif kind == "pause":
        g.append("G4 P%.2f" % (data / speed))
    elif kind == "home":
        g.append("G0 X0 Y0")
    return g


def text_gcode(text, mirror=False):
    g = ["G21", "G90", "M5"]
    for kind, _, data in list(text_to_events(text)) + [("home", "", None)]:
        g += event_gcode(kind, data, mirror)
    return "\n".join(g) + "\n"


# ---------- 5-bar kinematics ----------
def base(side):
    return np.array([side * LINK_A, LINK_D])


def ik(p, side):
    """Joint angle (rad) and elbow point of one arm; side=-1 left, +1 right (elbows out)."""
    b = base(side)
    d = np.asarray(p, float) - b
    r = np.hypot(*d)
    if not abs(LINK_L1 - LINK_L2) < r < LINK_L1 + LINK_L2:
        raise ValueError("point %s out of reach" % (p,))
    phi = np.arctan2(d[1], d[0])
    alpha = np.arccos((LINK_L1 ** 2 + r ** 2 - LINK_L2 ** 2) / (2 * LINK_L1 * r))
    th = phi + side * alpha
    return th, b + LINK_L1 * np.array([np.cos(th), np.sin(th)])


def transmission_quality(p):
    """Smallest of the elbow and end-effector angles' distance from 0/180 deg."""
    (_, e1), (_, e2) = ik(p, -1), ik(p, 1)
    p = np.asarray(p, float)

    def ang(u, v):
        return np.degrees(np.arccos(np.clip(u @ v / np.linalg.norm(u) / np.linalg.norm(v), -1, 1)))

    a = [ang(p - e1, p - e2), ang(base(-1) - e1, p - e1), ang(base(1) - e2, p - e2)]
    return min(min(x, 180 - x) for x in a)


def check():
    g = np.linspace(-WORKSPACE / 2, WORKSPACE / 2, 29)
    q = min(transmission_quality((x, y)) for x in g for y in g)
    print("5-bar: A=%.0f L1=%.0f L2=%.0f D=%.0f mm" % (LINK_A, LINK_L1, LINK_L2, LINK_D))
    print("Workspace %.0f x %.0f mm reachable; worst transmission angle margin %.1f deg"
          % (WORKSPACE, WORKSPACE, q))
    assert q > 25, "linkage too close to a singularity"
    for ch in FONT:
        pts = np.vstack(glyph_mm(ch))
        assert np.all(np.abs(pts) <= WORKSPACE / 2), "glyph %s outside workspace" % ch
    print("All %d glyphs fit inside the workspace." % len(FONT))
    t, *_ = build_path("THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG")
    n = len("THEQUICKBROWNFOXJUMPSOVERTHELAZYDOG")
    print("Pangram: %d letters in %.1f s  ->  %.0f letters/min (~%.0f words/min)"
          % (n, t[-1], 60 * n / t[-1], 60 * n / t[-1] / 5))
    print("KINEMATICS OK")


def joint_trajectory(x, y):
    out = np.empty((len(x), 2))
    for i, p in enumerate(zip(x, y)):
        out[i] = np.degrees([ik(p, -1)[0], ik(p, 1)[0]])
    return out


# ---------- preview ----------
def animate(text, show=False, out="palm_writer.gif"):
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from matplotlib.patches import Ellipse

    t, x, y, z, labels = build_path(text)
    fig, ax = plt.subplots(figsize=(6, 7), dpi=90)
    fig.patch.set_facecolor("#f7f7f5")
    ax.set_aspect("equal")
    ax.set_xlim(-90, 90)
    ax.set_ylim(-75, 130)
    ax.axis("off")
    # palm outline (rough) and workspace window
    ax.add_patch(Ellipse((0, 0), 90, 105, fc="#f2d4c2", ec="#c99a83", lw=1.5))
    for fx, fl in ((-30, 60), (-10, 75), (10, 72), (30, 58)):
        ax.add_patch(Ellipse((fx, 52 + fl / 2), 17, fl, fc="#f2d4c2", ec="#c99a83", lw=1))
    ax.add_patch(Ellipse((52, 10), 20, 55, angle=-30, fc="#f2d4c2", ec="#c99a83", lw=1))
    w = WORKSPACE / 2
    ax.plot([-w, w, w, -w, -w], [-w, -w, w, w, -w], ":", color="#888", lw=1)
    ink, = ax.plot([], [], "-", color="#2b5d8a", lw=3, solid_capstyle="round")
    arms = [ax.plot([], [], "o-", color=c, lw=4, ms=7)[0] for c in ("#4a77a8", "#f2851a")]
    tip = ax.scatter([0], [0], s=80, zorder=5)
    caption = ax.text(0, -68, "", ha="center", fontsize=14, family="monospace")
    ax.set_title("Print-on-palm writer: 5-bar linkage", fontsize=11)

    step = 2  # render every 2nd servo frame (25 fps)
    frames = range(0, len(t), step)
    lab_t = np.array([l[0] for l in labels]) if labels else np.zeros(1)

    def draw(i):
        # ink trail: current letter only, drawn where pen is down
        k = np.searchsorted(lab_t, t[i], side="right") - 1
        start = int(lab_t[max(k, 0)] / DT) if labels else 0
        seg = slice(start, i + 1)
        xs, ys = x[seg].copy(), y[seg].copy()
        up = z[seg] > 0.5
        xs[up], ys[up] = np.nan, np.nan
        ink.set_data(xs, ys)
        p = (x[i], y[i])
        for side, line in zip((-1, 1), arms):
            _, e = ik(p, side)
            b = base(side)
            line.set_data([b[0], e[0], p[0]], [b[1], e[1], p[1]])
        tip.set_offsets([p])
        tip.set_color("#c0392b" if z[i] < 0.5 else "#999999")
        shown = "".join(l[2] for l in labels if l[0] <= t[i] and l[1] == "glyph"
                        or (l[0] <= t[i] and l[2] == " " and l[1] == "tap"))
        caption.set_text(shown[-18:])
        return [ink, *arms, tip, caption]

    anim = FuncAnimation(fig, draw, frames=frames, interval=1000 * DT * step, blit=True)
    if show:
        plt.show()
    else:
        anim.save(out, writer=PillowWriter(fps=int(1 / (DT * step))))
        print("Saved", out, "(%.1f s of writing)" % t[-1])


# ---------- optional live speech input ----------
def live(model):
    """Microphone -> Vosk (offline) -> final phrases -> printed + previewed.

    `model` is either an unpacked Vosk model directory (contains am/ and conf/)
    or a language code such as "en-us"; a language code makes Vosk download its
    small model once into ~/.cache/vosk.
    """
    import os
    try:
        import json
        import queue
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer, SetLogLevel
    except ImportError:
        sys.exit("--live needs:  pip install vosk sounddevice")
    SetLogLevel(-1)
    if os.path.isdir(model):
        if not os.path.isdir(os.path.join(model, "am")):
            sys.exit("%r is not a Vosk model folder (no am/ inside). Pass a model folder from "
                     "https://alphacephei.com/vosk/models or a language code, e.g. --live en-us"
                     % model)
        m = Model(model_path=model)
    else:
        print("Loading Vosk model for language %r (downloads once to ~/.cache/vosk)..." % model)
        m = Model(lang=model)
    rate = int(sd.query_devices(kind="input")["default_samplerate"])
    rec = KaldiRecognizer(m, rate)
    q = queue.Queue()
    with sd.RawInputStream(samplerate=rate, blocksize=rate // 4, dtype="int16", channels=1,
                           callback=lambda d, *_: q.put(bytes(d))):
        print("Listening at %d Hz... speak; Ctrl+C to stop" % rate)
        try:
            while True:
                if rec.AcceptWaveform(q.get()):
                    text = json.loads(rec.Result()).get("text", "")
                    if text:
                        t, *_ = build_path(text)
                        print("HEARD: %-40s  -> %.1f s on the palm" % (text, t[-1]))
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default="HELLO WORLD.")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--csv")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--live", nargs="?", const="en-us", metavar="MODEL_DIR_OR_LANG",
                    help="mic -> Vosk; default downloads the small en-us model")
    ap.add_argument("--out", default="palm_writer.gif")
    ap.add_argument("--gcode", help="write GRBL G-code for the crossed-rail gantry")
    ap.add_argument("--mirror", action="store_true", help="palm-down box: flip x in G-code")
    a = ap.parse_args()
    if a.check:
        check()
    elif a.live:
        live(a.live)
    elif a.gcode:
        open(a.gcode, "w").write(text_gcode(a.text, a.mirror))
        print("Wrote", a.gcode, "| Braille:", braille_unicode(a.text))
    elif a.csv:
        t, x, y, z, _ = build_path(a.text)
        j = joint_trajectory(x, y)
        np.savetxt(a.csv, np.column_stack((t, x, y, z, j)), delimiter=",", fmt="%.3f",
                   header="t_s,x_mm,y_mm,z_mm,left_deg,right_deg", comments="")
        print("Wrote", a.csv, len(t), "samples")
    else:
        animate(a.text, a.show, a.out)
