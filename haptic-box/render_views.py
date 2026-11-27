#!/usr/bin/env python3
"""Render the v2 CAD model (meshes exported by haptic_box_v2.FCMacro) to images.

A small numpy z-buffer rasteriser: correct occlusion, flat shading, outline edges,
transparent parts, section cuts with filled cut faces, plus annotations.

    HAPTIC_DUMP=build/v2_mesh.json freecadcmd haptic_box_v2.FCMacro
    python3 render_views.py              # all views -> renders/
    python3 render_views.py product top  # selected views
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402

from comlang import engine as pw                      # noqa: E402

from cad_render import (Scene, Camera, Buffers, raster, edges, draw_points, render,  # noqa: E402
                        trans_layer, opaque_base, HERE, MESH)

OUT = os.path.join(HERE, "renders")


# ---------------------------------------------------------------- annotation helpers
def figure(img, title=None, note=None):
    h, w = img.shape[:2]
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img, interpolation="lanczos")
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    if title:
        ax.text(24, 40, title, fontsize=19, weight="bold", color="#222")
    if note:
        ax.text(24, 72, note, fontsize=12, color="#555")
    return fig, ax


def callout(ax, cam, p3, text, dx, dy, color="#222"):
    x, y = cam.to_image(p3)[0]
    ax.annotate(text, (x, y), (x + dx, y + dy), fontsize=12, color=color,
                ha="left" if dx >= 0 else "right", va="center",
                arrowprops=dict(arrowstyle="-", color="#444", lw=1.0, shrinkA=2, shrinkB=0),
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#bbb", lw=0.6, alpha=0.92))
    ax.plot([x], [y], "o", ms=3.5, color="#444")


def callouts(ax, cam, items, img_w, top=110, bottom=None, margin=22):
    """Labels stacked in the left/right margins, leader lines to 3D anchors.
    items: (p3, text) or (p3, text, 'L'|'R')."""
    pts = []
    for it in items:
        (x, y) = cam.to_image(np.array(it[0], float))[0]
        side = it[2] if len(it) > 2 else ("L" if x < img_w / 2 else "R")
        pts.append((x, y, it[1], side))
    for side in ("L", "R"):
        group = sorted([q for q in pts if q[3] == side], key=lambda q: q[1])
        last = top - 40
        placed = []
        for x, y, t, _ in group:
            h = 22 * (t.count("\n") + 1) + 14
            ty = max(y, last + h / 2 + 4)
            placed.append((x, y, t, ty))
            last = ty + h / 2
        if bottom and placed and last > bottom:            # push the column up if it overflows
            shift = last - bottom
            placed = [(x, y, t, ty - shift) for x, y, t, ty in placed]
        for x, y, t, ty in placed:
            tx = margin if side == "L" else img_w - margin
            ax.annotate(t, (x, y), (tx, ty), fontsize=12, color="#222",
                        ha="left" if side == "L" else "right", va="center",
                        arrowprops=dict(arrowstyle="-", color="#555", lw=0.9, shrinkA=3, shrinkB=0),
                        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#bbb", lw=0.6))
            ax.plot([x], [y], "o", ms=3.5, color="#333")


def dim(ax, cam, a3, b3, text, off_px=(0, 0), color="#0b5394"):
    """Dimension line between two 3D points, offset in image pixels."""
    a, b = cam.to_image(np.array([a3, b3]))
    o = np.array(off_px, float)
    pa, pb = a + o, b + o
    ax.annotate("", pa, pb, arrowprops=dict(arrowstyle="<->", color=color, lw=1.2,
                                            shrinkA=0, shrinkB=0))
    for p, q in ((a, pa), (b, pb)):
        if np.linalg.norm(o) > 0:
            ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=0.6, ls=":")
    m = (pa + pb) / 2
    ax.text(m[0], m[1], text, color=color, fontsize=11.5, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9))


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=100)
    plt.close(fig)
    print("wrote", os.path.relpath(path, HERE))


# ---------------------------------------------------------------- views
def view_product(sc):
    P = sc.p
    cam = Camera((0.55, -0.85, 0.62), (0, 140, 40), 560, (1500, 1050))
    objs = sc.objects(pose=(0, 0, 0), alpha={"TopPlate": 0.0, "HandDummy": 0.0, "ForearmDummy": 0.0})
    img = render(cam, objs)
    fig, ax = figure(img, "ComLang palm-writing box (v2 prototype, 20 mm flat)",
                     "Right hand palm-down in the glove-shaped recess; the pen writes on the palm from below, "
                     "through a cover.")
    B, H, PZ = P["buttons"], P["BOX_H"], P["PALM_Z"]
    D = P["display"]
    callouts(ax, cam, [
        ((B["Wheel"][0], B["Wheel"][1], PZ + 2.5), "thumb scroll roller: roll = speed,\npress = pause", "L"),
        ((B["Repeat"][0], B["Repeat"][1], PZ + 2.5), "Repeat: raised circular arrow\n(little finger)", "R"),
        ((B["Mode"][0], B["Mode"][1], H), "Mode (free hand): palm / Braille / both", "L"),
        ((0, P["PALM_Y"], PZ), "cover over the pen window\n(replaceable membrane)", "R"),
        ((0, 20, PZ), "%.1f mm deep glove-shaped recess,\nopen to the front for the wrist" % P["RECESS"], "L"),
        ((P["braille"][0][0], P["braille"][0][1], PZ), "pop-out Braille pins under\nindex + middle fingertips", "L"),
        ((D["x"], D["y"], H), "speaker display\n(text faces the speaker)", "R"),
        ((B["Reset"][0], B["Reset"][1], H), "speaker's Reset", "R"),
        ((0, -100, H - 10), "forearm pad (separate part)", "R"),
        ((130, 200, H / 2), "box %d x %d x %d mm" % (P["BOX_W"], P["BOX_L"], H), "R"),
    ], img.shape[1])
    save(fig, "v2_product.png")


def view_cutaway(sc, pose=(-10, 8, 1)):
    P = sc.p
    cam = Camera((0.5, -0.78, 0.75), (0, 160, 8), 470, (1500, 1100))
    objs = sc.objects(pose=pose, hide=("WristPad",),
                      alpha={"TopPlate": 0.85, "HandDummy": 0.8, "ForearmDummy": 0.8, "Shell": 0.9,
                             "ForearmPad": 0.75, "CoverMembrane": 0.8, "SpeakerDisplay": 0.6})
    t, x, y, z, _ = pw.build_path("H")
    img = render(cam, objs, ink=sc.ink_points(x, y, z))
    fig, ax = figure(img, "Cut-away: flat CoreXY gantry, 20 mm box",
                     "Top plate, hand and walls transparent. Two flat BLDC motors drive two belts lying in two "
                     "flat layers; the gantry slides on the Y-rods, the carriage on the twin X-rods.")
    PY, PZ, F = P["PALM_Y"], P["PALM_Z"], P["FLOOR"]
    cy, cx = PY + pose[1], -pose[0]
    MA, MB, BX = P["MOTOR_A"], P["MOTOR_B"], P["BELT_X"]
    za, zb = P["BELT_A_Z"] + 1.5, P["BELT_B_Z"] + 1.5
    callouts(ax, cam, [
        ((P["RAIL_X"], cy, P["Z_XROD"]), "gantry: Y-blocks + twin X-rods\n(moves in y)", "R"),
        ((cx + 20, cy, 11), "carriage + mini solenoid\nand wedge pen lifter", "R"),
        ((cx, cy, PZ + 1), "pen tip pressing the cover\ninto the palm", "R"),
        ((-P["RAIL_X"], P["PALM_Y"] - 55, P["Z_YROD"]), "Y-rod (D5): rail of the gantry", "L"),
        ((-BX, 225, za), "belt A (lower layer)", "L"),
        ((BX, 90, zb), "belt B (upper layer)", "R"),
        ((MA[0], MA[1], F + P["MOTOR_H"]), "flat BLDC motor A (x + y)", "L"),
        ((MB[0], MB[1], F + P["MOTOR_H"]), "flat BLDC motor B (x - y)", "R"),
        ((60, 27, 6), "phase 2: CM5 carrier", "R"),
        ((-60, 27, 6), "controller: Pico + 2 BLDC drivers", "L"),
        ((P["braille"][0][0], P["braille"][0][1], 12), "pop-out Braille actuators", "L"),
        ((P["display"]["x"], P["display"]["y"], P["BOX_H"]), "speaker display", "R"),
        ((P["buttons"]["Wheel"][0], P["buttons"]["Wheel"][1], P["BOX_H"]), "thumb scroll roller", "L"),
        ((0, -60, 45), "forearm on its pad (translucent)", "L"),
    ], img.shape[1], top=120, bottom=1070)
    save(fig, "v2_cutaway.png")


def view_section(sc):
    P = sc.p
    cut_x = 0.0                                  # plane through the pen axis (pen at palm centre)
    cam = Camera((1, 0, 0), (0, 150, 25), 240, (2400, 600))
    objs = sc.objects(pose=(0, 0, 1), alpha={"TopPlate": 0.0, "HandDummy": 0.55, "Shell": 0.0,
                                             "ForearmDummy": 0.55})
    img = render(cam, objs, clip=(0, cut_x))
    fig, ax = figure(img, "Section through the pen axis (x = 0), pen DOWN: box %d mm tall (was 54)" % P["BOX_H"],
                     "Reddish = cut faces. Hand (translucent) palm-down in the %.1f mm glove recess; the pen rises "
                     "through the window and presses the cover into the palm." % P["RECESS"])
    H, PZ, PU, L = P["BOX_H"], P["PALM_Z"], P["PLATE_UNDER"], P["BOX_L"]
    y0 = -142
    dim(ax, cam, (cut_x, L + 4, 0), (cut_x, L + 4, H), "%d" % H, (0, 0))
    dim(ax, cam, (cut_x, L + 30, 0), (cut_x, L + 30, PZ), "%.1f palm" % PZ, (0, 0))
    dim(ax, cam, (cut_x, 0, -8), (cut_x, L, -8), "%d box" % L, (0, 0))
    dim(ax, cam, (cut_x, y0, -8), (cut_x, 0, -8), "142 pad", (0, 0))
    dim(ax, cam, (cut_x, P["PALM_Y"] - 42, H + 30), (cut_x, P["PALM_Y"] + 42, H + 30),
        "84 window", (0, 0))
    PY = P["PALM_Y"]
    callouts(ax, cam, [
        ((cut_x, -60, 45), "forearm", "L"),
        ((cut_x, 100, 40), "hand, palm down (medium)", "L"),
        ((cut_x, -80, 12), "forearm pad", "L"),
        ((cut_x, PY - P["IDLER_DY"] - 5, P["BELT_A_Z"] + 1.5), "belt A run (lower layer)", "L"),
        ((cut_x, 240, PU - 2), "top plate: %.1f + %.1f mm" % (P["BASE_T"], P["RECESS"]), "L"),
        ((cut_x, 340, H - 4), "speaker display", "R"),
        ((cut_x, PY, PZ + 1.5), "pen tip: 1.5 mm into the palm,\nthrough the cover", "R"),
        ((cut_x, PY + P["XROD_DY"], P["Z_XROD"]), "twin X-rods + carriage", "R"),
        ((cut_x, PY + P["IDLER_DY"] + 5, P["BELT_B_Z"] + 1.5), "belt B run (upper layer)", "R"),
    ], img.shape[1], top=130, bottom=560)
    save(fig, "v2_section.png")


def view_section_detail(sc, down=1):
    P = sc.p
    cam = Camera((1, 0, 0), (0, 160, 24), 95, (1500, 660))
    objs = sc.objects(pose=(0, 0, down), alpha={"TopPlate": 0.0, "HandDummy": 0.0, "Shell": 0.0},
                      hide=("ForearmDummy", "ForearmPad"))
    img = render(cam, objs, clip=(0, 0.0))
    fig, ax = figure(img, "Section detail at the pen (x = 0), pen %s" % ("DOWN" if down else "UP"),
                     "Heights from the table (mm). Retracted: tip %.1f mm below the cover; pressed: 1.5 mm into "
                     "the palm." % (P["PALM_Z"] - P["PEN_UP_TIP"]))
    H, PZ, PU, PY = P["BOX_H"], P["PALM_Z"], P["PLATE_UNDER"], P["PALM_Y"]
    yd = PY + 32
    for i, (z, t) in enumerate(((P["FLOOR"], "%.1f base" % P["FLOOR"]), (P["Z_XROD"], "%.1f X-rods" % P["Z_XROD"]),
                                (PU, "%d" % PU), (PZ, "%.1f palm" % PZ), (H, "%d top" % H))):
        dim(ax, cam, (0, yd + 6 * i, 0), (0, yd + 6 * i, z), t, (0, 0))
    dim(ax, cam, (0, PY - 42, H + 4), (0, PY + 42, H + 4), "window 84", (0, 0))
    callouts(ax, cam, [
        ((0, PY - 28, 30), "hand, palm down (palm skin at z = %.1f)" % PZ, "L"),
        ((0, PY - 45, PZ - 0.2), "cover: membrane on a drop-in frame", "L"),
        ((0, PY, PZ + 1.5 if down else P["PEN_UP_TIP"]), "pen tip, 0.5 mm radius point", "R"),
        ((0, PY + 2, 5.5), "pen lifter: mini solenoid + wedge\n(force set by the tip spring)", "R"),
        ((0, PY - P["XROD_DY"], P["Z_XROD"]), "twin X-rods D5 (z %.1f)" % P["Z_XROD"], "L"),
        ((0, PY - P["IDLER_DY"] - 5, P["BELT_A_Z"] + 1.5), "belt A, lower layer (clamped)", "L"),
        ((0, PY + P["IDLER_DY"] + 5, P["BELT_B_Z"] + 1.5), "belt B, upper layer (clamped)", "R"),
        ((0, PY - 52, PU + 1), "top plate floor layer, %.1f mm aluminium" % P["BASE_T"], "L"),
    ], img.shape[1], top=140, bottom=620)
    save(fig, "v2_section_detail.png" if down else "v2_section_detail_up.png")


def view_top(sc):
    P = sc.p
    cam = Camera((0, 0, 1), (0, 140, 0), 580, (1250, 1450))
    objs = sc.objects(pose=(0, 0, 0), alpha={"HandDummy": 0.55, "ForearmDummy": 0.6, "TopPlate": 0.0,
                                             "CoverMembrane": 0.6})
    img = render(cam, objs)
    fig, ax = figure(img, "Top layout (right hand)", "Coordinates in mm: x from the centre line, y from the box front edge.")
    H = P["BOX_H"] + 8
    W2, L = P["BOX_W"] / 2, P["BOX_L"]
    dim(ax, cam, (-W2, -10, H), (W2, -10, H), "%d" % P["BOX_W"], (0, 0))
    dim(ax, cam, (W2 + 12, 0, H), (W2 + 12, L, H), "%d" % L, (0, 0))
    dim(ax, cam, (W2 + 12 + 30, 0, H), (W2 + 42, P["PALM_Y"], H), "155 to writing centre", (0, 0))
    dim(ax, cam, (W2 + 12 + 60, 0, H), (W2 + 72, P["WRIST_Y"], H), "100 wrist", (0, 0))
    B = P["buttons"]
    items = [((B["Wheel"][0], B["Wheel"][1], H), "thumb roller (%d, %d)" % tuple(B["Wheel"]), "L"),
             ((B["Repeat"][0], B["Repeat"][1], H), "Repeat D26 (%d, %d)" % tuple(B["Repeat"]), "R"),
             ((B["Mode"][0], B["Mode"][1], H), "Mode D24, free hand (%d, %d)" % tuple(B["Mode"]), "L"),
             ((B["Reset"][0], B["Reset"][1], H), "speaker Reset (%d, %d)" % tuple(B["Reset"]), "R")]
    items += [((x, y, H), "Braille cell, %s (%d, %d)" % (f, x, y), "L")
              for (x, y), f in zip(P["braille"], ("index", "middle"))]
    D = P["display"]
    items += [((P["wrist_pad"][0], P["wrist_pad"][1], H), "hand-present pad (0, 75)", "L"),
              ((84, 335, H), "mic grille", "R"), ((0, -70, H), "forearm pad", "R"),
              ((D["x"], D["y"], H), "speaker display 3.5\" (%d, %d)" % (D["x"], D["y"]), "L"),
              ((40, P["PALM_Y"] - 40, H), "cover cassette %d x %d over the 84 window" % (P["COVER"], P["COVER"]), "R"),
              ((0, P["PALM_Y"], H), "writing centre (0, 155)", "R")]
    callouts(ax, cam, items, img.shape[1], top=150)
    save(fig, "v2_top.png")


def view_layers(sc):
    """Exploded stack: top plate, hand, gantry, base."""
    P = sc.p
    cam = Camera((0.55, -0.85, 0.42), (0, 185, 100), 640, (1400, 1250))
    lift = {n: 80 for n in ("TopPlate", "WristPad", "BraillePins", "BrailleCells", "ButtonSwitches", "Mic",
                            "SpeakerDisplay") + tuple(n for n in sc.static if n.startswith("Button"))}
    lift.update({"CoverFrame": 130, "CoverMembrane": 130, "HandDummy": 210, "ForearmDummy": 210})
    objs = []
    for name, V, F, rgb, a in sc.objects(pose=(0, 0, 0), hide=("ForearmPad",),
                                         alpha={"HandDummy": 0.35, "ForearmDummy": 0.5, "TopPlate": 0.0}):
        objs.append((name, V + np.array([0, 0, lift.get(name, 0)]), F, rgb, a))
    img = render(cam, objs)
    fig, ax = figure(img, "Exploded build stack (20 mm box)", "Base tray with gantry and electronics; top plate with controls, "
                     "Braille and display; drop-in cover; hand.")
    H = P["BOX_H"]
    callouts(ax, cam, [
        ((-110, 40, H + 80), "3  top plate: %.1f mm aluminium floor + %.1f mm\n    recess layer, window, holes" % (P["BASE_T"], P["RECESS"]), "L"),
        ((P["display"]["x"] - 30, P["display"]["y"], H + 80), "    Braille cells, switches, display\n    mounted in / under the plate", "L"),
        ((50, P["PALM_Y"], P["PALM_Z"] + 130), "4  drop-in cover cassette (lifts out)", "R"),
        ((0, 140, H + 240), "5  hand rests palm-down in the recess", "R"),
        ((0, P["PALM_Y"] - 10, 12), "2  flat CoreXY gantry + pen on the base", "R"),
        ((125, 80, 10), "1  base tray: 1.5 mm aluminium base, 2 mm walls,\n    electronics, flat motors", "R"),
    ], img.shape[1], top=150)
    save(fig, "v2_exploded.png")


def anim_writing(sc, text="HI"):
    P = sc.p
    cam = Camera((0.62, -0.62, 0.48), (0, 155, 14), 230, (900, 680), ss=2)
    t, x, y, z, _ = pw.build_path(text)
    step = 3
    idx = list(range(0, len(t), step))
    alpha = {"TopPlate": 0.80, "HandDummy": 0.5, "ForearmDummy": 0.55, "Shell": 0.9, "ForearmPad": 0.75,
             "CoverMembrane": 0.8}
    hide = ("WristPad",)
    objs0 = sc.objects(hide=hide, alpha=alpha)
    moving = set(sc.moving)
    static_names = {o[0] for o in objs0 if o[0] not in moving}
    base = opaque_base(cam, objs0, static_names)
    tcache = {n: trans_layer(cam, V, F, rgb) for n, V, F, rgb, a in objs0 if a > 0.01}
    fig = plt.figure(figsize=(9, 6.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    im = ax.imshow(np.ones((680, 900, 3)))
    ttl = ax.text(18, 34, "", fontsize=15, weight="bold", color="#222")
    ax.text(18, 60, "Pen presses the cover up into the palm and writes from below (mirrored as print-on-palm)",
            fontsize=10, color="#555")

    def frame(k):
        i = idx[k]
        down = max(0.0, 1.0 - z[i] / pw.PEN_LIFT)
        objs = sc.objects(pose=(x[i], y[i], down), hide=hide, alpha=alpha)
        img = render(cam, objs, base=base, opaque_cache=static_names, trans_cache=tcache,
                     ink=sc.ink_points(x[:i + 1], y[:i + 1], z[:i + 1]))
        im.set_data(img)
        ttl.set_text('Writing "%s"   pen %s' % (text, "DOWN" if down > 0.5 else "up"))
        return [im, ttl]

    anim = FuncAnimation(fig, frame, frames=len(idx), blit=False)
    os.makedirs(OUT, exist_ok=True)
    anim.save(os.path.join(OUT, "v2_writing.gif"), writer=PillowWriter(fps=int(1 / (pw.DT * step))))
    plt.close(fig)
    print("wrote renders/v2_writing.gif (%d frames)" % len(idx))


def view_hands(sc):
    """Small / medium / large hands resting in the well, top view, with the reach results."""
    import hand_model as HM
    P = sc.p
    imgs = []
    cam = Camera((0, 0, 1), (0, 175, 0), 300, (620, 800))
    for size in ("small", "medium", "large"):
        objs = sc.objects(hand=size, hide=("ForearmPad",), alpha={"TopPlate": 0.0, "HandDummy": 0.15,
                                                                 "ForearmDummy": 0.15})
        imgs.append((size, render(cam, objs)))
    fig = plt.figure(figsize=(18.6, 9.6), dpi=100)
    fig.text(0.012, 0.965, "Hand sizes in the glove-shaped recess (top view)", fontsize=19, weight="bold", color="#222")
    fig.text(0.012, 0.935, "Glove print: each digit and the palm is the hull over all three hand sizes + 5 mm. "
             "Every size reaches the thumb roller and Repeat without moving the hand.", fontsize=12, color="#555")
    B = P["button_spec"]
    for i, (size, img) in enumerate(imgs):
        ax = fig.add_axes([0.005 + i * 0.333, 0.12, 0.323, 0.79])
        ax.imshow(img)
        ax.axis("off")
        L, Bw, label = HM.SIZES[size]
        h = HM.Hand(size, P["WRIST_Y"], P["PALM_Z"], P["TS"])
        lines = ["%s: hand %d x %d mm (%s)" % (size.capitalize(), L, Bw, label)]
        for name in ("Wheel", "Repeat"):
            _, (dg, sw, short) = h.posed(name, B)
            lines.append("%-6s %-6s swing %2.0f°  %s" % (name, dg, sw, "reaches" if short <= 0.5 else
                                                             "short %.0f mm" % short))
        lines.append("palm centre %+.1f mm from the writing centre" % (h.palm_centre[1] - P["PALM_Y"]))
        fig.text(0.012 + i * 0.333, 0.105, "\n".join(lines), fontsize=11.5, family="monospace", va="top",
                 color="#222")
    save(fig, "v2_hand_sizes.png")


def view_press(sc, size="medium"):
    """The two resting-hand controls in use (close-up, medium hand) + the free-hand Mode button."""
    P = sc.p
    shots = []
    W, R, M = P["buttons"]["Wheel"], P["buttons"]["Repeat"], P["buttons"]["Mode"]
    pz = P["PALM_Z"]
    views = {"Wheel": ((0.25, -0.8, 0.75), (W[0] + 20, W[1], pz + 6), 150, "Wheel"),
             "Repeat": ((0.7, -0.5, 0.7), (R[0] - 10, R[1], pz + 6), 150, "Repeat"),
             "Mode": ((0.3, -0.7, 0.8), (M[0] + 10, M[1] + 5, P["BOX_H"]), 110, "rest")}
    for name, (d, c, ext, pose) in views.items():
        cam = Camera(d, c, ext, (620, 560))
        objs = sc.objects(hand=size, hand_pose=pose, hide=("ForearmPad", "WristPad"),
                          alpha={"TopPlate": 0.0, "HandDummy": 0.25, "ForearmDummy": 0.25})
        shots.append((name, render(cam, objs)))
    fig = plt.figure(figsize=(18.6, 6.4), dpi=100)
    fig.text(0.012, 0.94, "Controls without lifting the resting hand (%s hand)" % size, fontsize=19,
             weight="bold", color="#222")
    desc = {"Wheel": "thumb swings out ~22° onto the roller: roll = speed, press = pause",
            "Repeat": "little finger swings out onto the circular-arrow cap",
            "Mode": "free hand: Mode (palm / Braille / both)"}
    for i, (name, img) in enumerate(shots):
        ax = fig.add_axes([0.005 + i * 0.333, 0.02, 0.323, 0.82])
        ax.imshow(img)
        ax.axis("off")
        ax.set_title(desc[name], fontsize=12.5)
    save(fig, "v2_button_press.png")


def view_symbols(sc):
    """Close-ups of every control's tactile symbol, seen from above."""
    P = sc.p
    B = P["buttons"]
    pz, H = P["PALM_Z"], P["BOX_H"]
    items = [("Thumb roller: + far end (faster), - near end\n(slower), || press = pause (marks incised)", B["Wheel"], pz, 46),
             ("Repeat: circular arrow", B["Repeat"], P["CAP_TOP"], 36),
             ("Mode: Braille cell + pen stroke", B["Mode"], H, 34),
             ("Reset (speaker): x", B["Reset"], H, 30)]
    fig = plt.figure(figsize=(18.6, 5.6), dpi=100)
    fig.text(0.012, 0.93, "Tactile symbols on every control (raised 0.8 mm on the caps, 1.4 mm lines)", fontsize=19,
             weight="bold", color="#222")
    for i, (title, (x, y), z, ext) in enumerate(items):
        cam = Camera((0.35, -0.75, 0.75), (x, y, z), ext, (600, 520))
        objs = sc.objects(hide=("HandDummy", "ForearmDummy"), alpha={"TopPlate": 0.0})
        img = render(cam, objs)
        ax = fig.add_axes([0.005 + i * 0.25, 0.02, 0.24, 0.78])
        ax.imshow(img)
        ax.axis("off")
        ax.set_title(title, fontsize=12.5)
    save(fig, "v2_symbols.png")


def view_section_detail_up(sc):
    view_section_detail(sc, down=0)


VIEWS = {"product": view_product, "cutaway": view_cutaway, "section": view_section,
         "detail": view_section_detail, "detail_up": view_section_detail_up, "hands": view_hands, "press": view_press,
         "top": view_top, "exploded": view_layers, "symbols": view_symbols, "writing": anim_writing}

if __name__ == "__main__":
    sc = Scene(MESH)
    for name in sys.argv[1:] or VIEWS:
        VIEWS[name](sc)
