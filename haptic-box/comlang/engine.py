"""ComLang engine: text -> touch. Shared by the device runtime (comlang.runtime) and every demo.

Text -> single-stroke block capitals written on the same spot of the palm (print-on-palm),
English Grade 1 Braille cells, a timed pen path (trapezoidal speed profile, pen up/down) and
controller commands for the crossed-bar gantry.

Coordinates (mm): origin = centre of the writing area on the palm, +x = the reader's right,
+y = toward the fingertips, z = pen lift above the palm.
"""
import numpy as np

# ---------------- parameters (copied into the firmware by tools/gen_firmware_tables.py) ----------------
LETTER_H = 45.0        # letter height on the palm (mm)
WORKSPACE = 70.0       # square the stylus must reach (mm)
V_WRITE = 120.0        # mm/s while touching the palm
V_TRAVEL = 250.0       # mm/s pen up
ACCEL = 3000.0         # mm/s^2
PEN_LIFT = 6.0         # mm
T_PEN = 0.08           # s for pen down / up
T_LETTER_GAP = 0.25    # s pause between letters
T_WORD_GAP = 0.6       # s pause after the word-space cue
DT = 1 / 50            # s, planner sample period (50 Hz)
# --------------------------------------------------------------------------------------------------

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
# Cues that are not letters (handled by word_events):
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
        elif kind == "longtap":                      # cue: pen held on the palm centre for `data` s
            self._move(rows, [self.pos, (0.0, 0.0)], V_TRAVEL)
            self._hold(rows, T_PEN, 0.0)
            self._hold(rows, data)
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


# ---------- commands for the box controller (firmware/mcu; format in protocol.py) ----------
def event_commands(kind, data, mirror=True):
    """Queued controller commands for one event. Positions in 0.01 mm from the palm centre
    (work zero, set by calibration); mirror=True flips x for the palm-down box (pen from below).
    Speeds are for 1.0x: the controller applies the speed override (V) itself."""
    sx = -1 if mirror else 1

    def m(p, v):
        return "m %d %d %d" % (round(sx * p[0] * 100), round(p[1] * 100), v)

    def d(s):
        return "d %d" % round(s * 1000)

    c = []
    if kind == "glyph":
        for stroke in data:
            c.append(m(stroke[0], V_TRAVEL))
            c += ["p 1", d(T_PEN)]
            c += [m(p, V_WRITE) for p in stroke[1:]]
            c += ["p 0", d(T_PEN)]
    elif kind == "tap":
        c.append(m((0, 0), V_TRAVEL))
        for _ in range(data):
            c += ["p 1", d(T_PEN + 0.05), "p 0", d(T_PEN)]
    elif kind == "longtap":
        c += [m((0, 0), V_TRAVEL), "p 1", d(T_PEN + data), "p 0", d(T_PEN)]
    elif kind == "pause":
        c.append(d(data))
    elif kind == "home":
        c.append(m((0, 0), V_TRAVEL))
    return c


def text_commands(text, mirror=True):
    c = []
    for kind, _, data in list(text_to_events(text)) + [("home", "", None)]:
        c += event_commands(kind, data, mirror)
    return "\n".join(c) + "\n"

