#!/usr/bin/env python3
"""DEMO: print-on-palm preview and the v0.1 5-bar linkage, on top of the shared engine.

The text -> touch engine itself (font, Braille, planner, G-code) is comlang/engine.py and is
the same code the device runtime uses; this file only adds the v0.1 5-bar kinematics, the
matplotlib preview and a CLI.

Usage (from haptic-box/):
    python3 demos/palm_writer.py "HELLO WORLD"            # render palm_writer.gif
    python3 demos/palm_writer.py "HELLO" --show            # live window
    python3 demos/palm_writer.py "HELLO" --csv out.csv     # 5-bar joint trajectory (v0.1 box)
    python3 demos/palm_writer.py "HELLO" --commands out.txt  # box controller commands (protocol.py)
    python3 demos/palm_writer.py --check                   # workspace/kinematics check
    python3 demos/palm_writer.py --live                    # mic -> Vosk (en-us) -> preview
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comlang.engine import *            # noqa: E402,F401,F403  (re-exported for the CAD macros)
from comlang.engine import (WORKSPACE, DT, FONT, glyph_mm, build_path, text_commands,  # noqa: E402
                            braille_unicode)

# v0.1 5-bar linkage: motors at (-A, D) and (+A, D), proximal L1, distal L2
LINK_A, LINK_L1, LINK_L2, LINK_D = 20.0, 55.0, 80.0, 80.0

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
    ap.add_argument("--commands", help="write the box controller commands (comlang/protocol.py)")
    ap.add_argument("--no-mirror", action="store_true", help="palm-up rig: do not flip x")
    a = ap.parse_args()
    if a.check:
        check()
    elif a.live:
        live(a.live)
    elif a.commands:
        open(a.commands, "w").write(text_commands(a.text, not a.no_mirror))
        print("Wrote", a.commands, "| Braille:", braille_unicode(a.text))
    elif a.csv:
        t, x, y, z, _ = build_path(a.text)
        j = joint_trajectory(x, y)
        np.savetxt(a.csv, np.column_stack((t, x, y, z, j)), delimiter=",", fmt="%.3f",
                   header="t_s,x_mm,y_mm,z_mm,left_deg,right_deg", comments="")
        print("Wrote", a.csv, len(t), "samples")
    else:
        animate(a.text, a.show, a.out)
