#!/usr/bin/env python3
"""Kinematic simulation of two meshing spur gears (20T driver, 40T driven).

Gears use true involute tooth profiles (ISO standard rack: module m,
20 deg pressure angle, addendum 1.0 m, dedendum 1.25 m).

Usage:
    python3 gear_sim.py            # render gears.mp4 + gears.gif
    python3 gear_sim.py --show     # live interactive window
"""
import sys
import numpy as np
import matplotlib
if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from matplotlib.patches import Polygon, Circle

MODULE = 2.0                      # mm
PRESSURE_ANGLE = np.radians(20)   # rad
N1, N2 = 20, 40                   # tooth counts
RPM1 = 30.0                       # driver speed
FPS, DURATION = 30, 4.0           # 4 s = 2 rev of gear 1 = 1 rev of gear 2 (seamless loop)


def inv(a):
    return np.tan(a) - a


def gear_profile(n, m=MODULE, alpha=PRESSURE_ANGLE, pts=20):
    """Return (x, y) outline of an involute spur gear centred at origin, tooth 0 on +x."""
    rp = m * n / 2                 # pitch radius
    rb = rp * np.cos(alpha)        # base radius
    ra = rp + m                    # addendum radius
    rf = rp - 1.25 * m             # root radius
    half_tooth = np.pi / (2 * n)   # half tooth thickness (angle) at pitch circle

    def half_angle(r):            # tooth half-angle at radius r (r >= rb)
        return half_tooth + inv(alpha) - inv(np.arccos(rb / r))

    r_flank = np.linspace(max(rb, rf), ra, pts)
    th_flank = half_angle(r_flank)
    if rf < rb:                    # radial segment below the base circle
        r_flank = np.concatenate(([rf], r_flank))
        th_flank = np.concatenate(([th_flank[0]], th_flank))

    xs, ys = [], []
    pitch = 2 * np.pi / n
    for i in range(n):
        c = i * pitch
        # right flank (root -> tip), tip land, left flank (tip -> root)
        a_r = c - th_flank
        tip = np.linspace(c - th_flank[-1], c + th_flank[-1], 5)
        a_l = (c + th_flank)[::-1]
        # root arc to the next tooth
        root = np.linspace(c + th_flank[0], c + pitch - th_flank[0], 6)
        ang = np.concatenate((a_r, tip, a_l, root))
        rad = np.concatenate((r_flank, np.full(5, ra), r_flank[::-1], np.full(6, rf)))
        xs.append(rad * np.cos(ang))
        ys.append(rad * np.sin(ang))
    return np.concatenate(xs), np.concatenate(ys), dict(rp=rp, rb=rb, ra=ra, rf=rf)


def rotate(x, y, th, cx=0.0, cy=0.0):
    c, s = np.cos(th), np.sin(th)
    return np.column_stack((cx + c * x - s * y, cy + s * x + c * y))


x1, y1, g1 = gear_profile(N1)
x2, y2, g2 = gear_profile(N2)
CENTER_DIST = g1["rp"] + g2["rp"]           # 60 mm
RATIO = N2 / N1                             # 2.0
OMEGA1 = RPM1 * 2 * np.pi / 60              # rad/s
PHASE2 = np.pi / N2                         # put a tooth gap of gear 2 opposite tooth 0 of gear 1

fig, ax = plt.subplots(figsize=(9, 6), dpi=100)
fig.patch.set_facecolor("#f7f7f5")
ax.set_aspect("equal")
ax.set_xlim(-g1["ra"] - 6, CENTER_DIST + g2["ra"] + 6)
ax.set_ylim(-g2["ra"] - 6, g2["ra"] + 6)
ax.axis("off")

p1 = Polygon(rotate(x1, y1, 0), closed=True, fc="#4C78A8", ec="#1d3557", lw=1)
p2 = Polygon(rotate(x2, y2, PHASE2, CENTER_DIST), closed=True, fc="#F58518", ec="#7a3e00", lw=1)
ax.add_patch(p1)
ax.add_patch(p2)
for cx, g in ((0, g1), (CENTER_DIST, g2)):
    ax.add_patch(Circle((cx, 0), g["rp"], fill=False, ls="--", lw=0.6, ec="#555"))
    ax.add_patch(Circle((cx, 0), 3, fc="#222"))
# reference spokes so rotation is easy to follow
spoke1, = ax.plot([], [], color="white", lw=3)
spoke2, = ax.plot([], [], color="white", lw=3)
# line of action through pitch point
pp = g1["rp"]
d = np.array([np.sin(PRESSURE_ANGLE), np.cos(PRESSURE_ANGLE)]) * 14
ax.plot([pp - d[0], pp + d[0]], [-d[1], d[1]], color="#c0392b", lw=1, ls=":")

info = ax.text(0.01, 0.99, "", transform=ax.transAxes, va="top", family="monospace", fontsize=9)
ax.set_title(f"Spur gear mesh  {N1}T → {N2}T   (m = {MODULE} mm, α = 20°, ratio {RATIO:.0f}:1)")


def update(frame):
    t = frame / FPS
    th1 = OMEGA1 * t
    th2 = PHASE2 - th1 / RATIO
    p1.set_xy(rotate(x1, y1, th1))
    p2.set_xy(rotate(x2, y2, th2, CENTER_DIST))
    spoke1.set_data([0, g1["rf"] * 0.8 * np.cos(th1)], [0, g1["rf"] * 0.8 * np.sin(th1)])
    spoke2.set_data([CENTER_DIST, CENTER_DIST + g2["rf"] * 0.8 * np.cos(th2 - PHASE2)],
                    [0, g2["rf"] * 0.8 * np.sin(th2 - PHASE2)])
    info.set_text(
        f"t = {t:5.2f} s\n"
        f"Gear 1 ({N1}T): {RPM1:5.1f} rpm CCW  rev {th1 / (2*np.pi):5.2f}\n"
        f"Gear 2 ({N2}T): {RPM1/RATIO:5.1f} rpm CW   rev {th1 / RATIO / (2*np.pi):5.2f}\n"
        f"Pitch-line speed: {OMEGA1 * g1['rp']:.1f} mm/s"
    )
    return p1, p2, spoke1, spoke2, info


frames = int(FPS * DURATION)
anim = FuncAnimation(fig, update, frames=frames, interval=1000 / FPS, blit=False)

if "--show" in sys.argv:
    plt.show()
else:
    anim.save("gears.mp4", writer=FFMpegWriter(fps=FPS, bitrate=2000))
    anim.save("gears.gif", writer=PillowWriter(fps=FPS))
    update(7); fig.savefig("gears_frame.png")
    print(f"Center distance {CENTER_DIST} mm, ratio {RATIO}:1 -> gears.mp4, gears.gif, gears_frame.png")
