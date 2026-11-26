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

import palm_writer as pw                             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
BG = np.array([1.0, 1.0, 1.0])
CUT_COL = np.array([0.86, 0.32, 0.30])


# ---------------------------------------------------------------- scene
class Scene:
    def __init__(self, path):
        d = json.load(open(path))
        self.p = d["params"]
        self.colors = {k: (np.array(c), a) for k, (c, a) in d["colors"].items()}
        self.static = {k: (np.array(m["v"], float), np.array(m["f"], int)) for k, m in d["static"].items()}
        self.moving = {k: (np.array(m["v"], float), np.array(m["f"], int)) for k, m in d["moving"].items()}
        self.stroke = self.p["PEN_STROKE"]

    def offsets(self, px, py, down):
        """Same mapping as haptic_box_v2.offsets(): palm coords -> part translations."""
        mx = -px
        cx, cy = mx - 16.0, py - 16.0
        dz = self.stroke * down
        return {"YBar": (0, cy, 0), "XBar": (cx, 0, 0), "Carriage": (cx, cy, 0), "Pen": (cx, cy, dz)}

    def objects(self, pose=(0, 0, 0), hide=(), alpha=None, color=None):
        """[(name, V, F, rgb, alpha)] for the given pen pose (palm x, y, down 0..1)."""
        alpha, color = alpha or {}, color or {}
        out = []
        off = self.offsets(*pose)
        for group in (self.static, self.moving):
            for k, (v, f) in group.items():
                if k in hide:
                    continue
                c, a = self.colors[k]
                if k in off:
                    v = v + np.array(off[k])
                out.append((k, v, f, np.array(color.get(k, c)), alpha.get(k, a)))
        return out

    def ink_points(self, x, y, z):
        """Machine-space points on the palm where the pen was down."""
        pts = [(-xi, self.p["PALM_Y"] + yi, self.p["PALM_Z"] + 0.15) for xi, yi, zi in zip(x, y, z)
               if zi < 0.5]
        return np.array(pts) if pts else np.zeros((0, 3))


# ---------------------------------------------------------------- camera
class Camera:
    def __init__(self, direction, center, extent, size=(1500, 1000), ss=2):
        c = np.asarray(direction, float)
        self.c = c / np.linalg.norm(c)                    # unit vector towards the camera
        f = -self.c
        r = np.cross(f, [0, 0, 1.0])
        if np.linalg.norm(r) < 1e-6:                      # looking straight down/up
            r = np.array([1.0, 0, 0])
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, f)
        self.W, self.H = size[0] * ss, size[1] * ss
        self.ss = ss
        self.center = np.asarray(center, float)
        self.scale = min(self.W, self.H) / extent          # px per mm

    def project(self, P):
        P = np.atleast_2d(P) - self.center
        sx, sy, d = P @ self.r, P @ self.u, P @ self.c
        return np.column_stack((self.W / 2 + sx * self.scale, self.H / 2 - sy * self.scale)), d

    def to_image(self, P):
        """Projected position in final (downsampled) image pixels."""
        xy, _ = self.project(P)
        return xy / self.ss


# ---------------------------------------------------------------- rasteriser
class Buffers:
    def __init__(self, cam):
        H, W = cam.H, cam.W
        self.z = np.full((H, W), -np.inf, np.float32)
        self.col = np.tile(BG, (H, W, 1)).astype(np.float32)
        self.id = np.full((H, W), -1, np.int32)
        self.n = np.zeros((H, W, 3), np.float32)

    def copy(self):
        b = Buffers.__new__(Buffers)
        b.z, b.col, b.id, b.n = self.z.copy(), self.col.copy(), self.id.copy(), self.n.copy()
        return b


def light_dir(cam):
    L = 0.35 * (-cam.r) + 0.75 * cam.u + 0.8 * cam.c
    return L / np.linalg.norm(L)


def raster(cam, buf, V, F, rgb, oid, clip=None, depth_only=None):
    """Rasterise one mesh into buf. clip=(axis, value): drop world points with p[axis] > value
    and paint the inside of cut solids with CUT_COL."""
    xy, d = cam.project(V)
    tri = F
    P = xy[tri]                     # (m,3,2)
    D = d[tri]
    W3 = V[tri]
    n = np.cross(W3[:, 1] - W3[:, 0], W3[:, 2] - W3[:, 0])
    nl = np.linalg.norm(n, axis=1)
    good = nl > 1e-12
    n[good] /= nl[good, None]
    facing = n @ cam.c                                  # >0: front face (outward normals)
    nn = np.where(facing[:, None] < 0, -n, n)
    L = light_dir(cam)
    shade = 0.40 + 0.60 * np.clip(nn @ L, 0, 1) + 0.10 * np.clip(nn @ cam.c, 0, 1)
    H, Wd = buf.z.shape
    x0 = np.clip(np.floor(P[:, :, 0].min(1)).astype(int), 0, Wd - 1)
    x1 = np.clip(np.ceil(P[:, :, 0].max(1)).astype(int), 0, Wd - 1)
    y0 = np.clip(np.floor(P[:, :, 1].min(1)).astype(int), 0, H - 1)
    y1 = np.clip(np.ceil(P[:, :, 1].max(1)).astype(int), 0, H - 1)
    ax = clip[0] if clip else None
    for i in np.nonzero(good & (x1 >= x0) & (y1 >= y0))[0]:
        (ax_, ay_), (bx, by), (cx_, cy_) = P[i]
        area = (bx - ax_) * (cy_ - ay_) - (by - ay_) * (cx_ - ax_)
        if abs(area) < 1e-9:
            continue
        xs = np.arange(x0[i], x1[i] + 1) + 0.5
        ys = np.arange(y0[i], y1[i] + 1) + 0.5
        X, Y = np.meshgrid(xs, ys)
        w0 = ((bx - X) * (cy_ - Y) - (by - Y) * (cx_ - X)) / area
        w1 = ((cx_ - X) * (ay_ - Y) - (cy_ - Y) * (ax_ - X)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        z = w0 * D[i, 0] + w1 * D[i, 1] + w2 * D[i, 2]
        if clip:
            wc = w0 * W3[i, 0, ax] + w1 * W3[i, 1, ax] + w2 * W3[i, 2, ax]
            m &= wc <= clip[1]
        sl = (slice(y0[i], y1[i] + 1), slice(x0[i], x1[i] + 1))
        zb = buf.z[sl]
        m &= z > zb
        if not m.any():
            continue
        zb[m] = z[m]
        if depth_only is not None:
            continue
        cut = clip is not None and facing[i] < 0
        c = 0.45 * rgb + 0.55 * CUT_COL if cut else rgb * min(shade[i], 1.15)
        buf.col[sl][m] = np.clip(c, 0, 1)
        buf.id[sl][m] = -2 if cut else oid
        buf.n[sl][m] = nn[i] if not cut else -cam.c


def edges(buf, cam, depth_tol_mm=1.5):
    """Outline pixels: object boundaries, depth jumps and creases."""
    z, idb, n = buf.z, buf.id, buf.n
    e = np.zeros(z.shape, bool)
    tol = depth_tol_mm
    for dy, dx in ((0, 1), (1, 0)):
        a = (slice(0, z.shape[0] - dy), slice(0, z.shape[1] - dx))
        b = (slice(dy, None), slice(dx, None))
        diff = idb[a] != idb[b]
        dz = np.abs(np.nan_to_num(z[a] - z[b], posinf=1e9, neginf=1e9)) > tol
        crease = (n[a] * n[b]).sum(-1) < 0.85
        both_bg = (idb[a] < 0) & (idb[b] < 0) & (idb[a] != -2) & (idb[b] != -2)
        m = (diff | dz | crease) & ~both_bg
        e[a] |= m
    return e


def draw_points(cam, buf, P3, rgb, radius_px, oid=-3):
    """Depth-tested round dots (used for ink on the palm)."""
    if len(P3) == 0:
        return
    xy, d = cam.project(P3)
    r = radius_px
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = (xx ** 2 + yy ** 2) <= r * r
    H, W = buf.z.shape
    for (x, y), dd in zip(xy, d):
        xi, yi = int(x), int(y)
        if r <= xi < W - r and r <= yi < H - r:
            sl = (slice(yi - r, yi + r + 1), slice(xi - r, xi + r + 1))
            m = disk & (dd + 0.5 > buf.z[sl])
            buf.col[sl][m] = rgb
            buf.z[sl][m] = dd + 0.5
            buf.id[sl][m] = oid


def trans_layer(cam, V, F, rgb, clip=None):
    tb = Buffers(cam)
    raster(cam, tb, V, F, rgb, 7, clip)
    return tb.z, tb.col, edges(tb, cam) & (tb.id >= 0)


def render(cam, objs, clip=None, ink=None, ink_rgb=(0.08, 0.25, 0.55), base=None, opaque_cache=None,
           trans_cache=None):
    """Returns an RGB image (downsampled). Transparent objects are blended over the opaque pass."""
    opaque = [o for o in objs if o[4] <= 0.01]
    trans = [o for o in objs if o[4] > 0.01]
    if base is not None:
        buf = base.copy()
    else:
        buf = Buffers(cam)
    for k, (name, V, F, rgb, a) in enumerate(opaque):
        if opaque_cache is not None and name in opaque_cache:
            continue
        raster(cam, buf, V, F, rgb, hash(name) % 100000, clip)
    if ink is not None:
        draw_points(cam, buf, ink, np.array(ink_rgb), max(2, int(1.8 * cam.scale)))
    e = edges(buf, cam)
    col = buf.col.copy()
    col[e] *= 0.30
    # transparent parts: nearest layer of each object, blended far -> near
    layers = []
    for name, V, F, rgb, a in trans:
        if trans_cache is not None and name in trans_cache:
            tz, tcol, te = trans_cache[name]
        else:
            tz, tcol, te = trans_layer(cam, V, F, rgb, clip)
        mask = tz > buf.z
        if not mask.any():
            continue
        layers.append((float(np.median(tz[mask])), mask, tcol, te, a))
    for _, mask, tcol, te, a in sorted(layers, key=lambda l: l[0]):
        col[mask] = (1 - a) * tcol[mask] + a * col[mask]
        em = te & mask
        col[em] = col[em] * 0.55
    ss = cam.ss
    H, W = col.shape[0] // ss, col.shape[1] // ss
    return col[:H * ss, :W * ss].reshape(H, ss, W, ss, 3).mean((1, 3))


def opaque_base(cam, objs, names, clip=None):
    """Pre-rasterised buffers for opaque objects that do not move (animation speed-up)."""
    buf = Buffers(cam)
    for name, V, F, rgb, a in objs:
        if name in names and a <= 0.01:
            raster(cam, buf, V, F, rgb, hash(name) % 100000, clip)
    return buf


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
    cam = Camera((0.55, -0.85, 0.62), (0, 120, 60), 520, (1500, 1050))
    objs = sc.objects(pose=(0, 0, 0), alpha={"TopPlate": 0.0, "HandDummy": 0.0, "ForearmDummy": 0.0},
                      color={"TopPlate": (0.90, 0.91, 0.92)})
    img = render(cam, objs)
    fig, ax = figure(img, "Haptic palm-writing box (v2 prototype)",
                     "Right hand palm-down in the tactile recess; the pen writes on the palm from below.")
    B, H = P["buttons"], P["BOX_H"]
    callouts(ax, cam, [
        ((B["Pause"][0], B["Pause"][1], H + 4), "Pause button (thumb)"),
        ((B["Repeat"][0], B["Repeat"][1], H + 4), "Repeat button (thumb)"),
        ((B["Speed"][0], B["Speed"][1], H + 4), "Speed button (little finger)", "R"),
        ((P["braille"][0][0], P["braille"][0][1] + 14, H + 10), "Braille cells under\nindex + middle fingertips", "L"),
        ((82, 297, H), "microphone grille", "R"),
        ((0, -100, H), "forearm pad (separate part)"),
        ((130, 160, 35), "box 260 x 330 x 72 mm", "R"),
        ((0, P["PALM_Y"], H + 30), "pen writes on the palm\nfrom below (hidden)", "R"),
    ], img.shape[1])
    save(fig, "v2_product.png")


def view_cutaway(sc, pose=(-10, 8, 1)):
    P = sc.p
    cam = Camera((0.5, -0.78, 0.75), (0, 170, 40), 360, (1500, 1050))
    objs = sc.objects(pose=pose, hide=("ForearmPad", "ForearmDummy", "ButtonPause", "ButtonRepeat",
                                       "ButtonSpeed", "WristPad"),
                      alpha={"TopPlate": 0.82, "HandDummy": 0.80, "Shell": 0.9})
    t, x, y, z, _ = pw.build_path("H")
    img = render(cam, objs, ink=sc.ink_points(x, y, z))
    fig, ax = figure(img, "Cut-away: crossed-rail XY gantry under the palm",
                     "Top plate, hand and walls drawn transparent; pen pressed into the palm after writing H.")
    PY, PZ = P["PALM_Y"], P["PALM_Z"]
    cy = PY + pose[1] - 16
    cx = -pose[0] - 16
    callouts(ax, cam, [
        ((60, cy, 34), "Y-bar: moves in y on two y-rails", "R"),
        ((cx, PY - 55, 48), "X-bar: moves in x on two x-rails", "L"),
        ((cx + 16, cy + 16, 30), "carriage + push solenoid\n(pen offset 16/16 mm)", "R"),
        ((-pose[0], PY + pose[1], PZ + 1), "pen tip in the palm", "R"),
        ((-116, 120, 27), "y-belt (both sides) + sync shaft", "L"),
        ((70, 70, 42), "x-belt (front + back) + sync shaft", "R"),
        ((0, 262, 38), "Y stepper NEMA14", "R"),
        ((-88, 30, 64), "X stepper NEMA14", "L"),
        ((52, 36, 22), "Raspberry Pi 5", "R"),
        ((-27, 33, 20), "motion controller (GRBL)", "L"),
        ((-30, 280, 66), "Braille cell modules", "L"),
        ((60, 280, 18), "Braille driver board", "R"),
        ((-104, 160, 62), "button switches", "L"),
        ((42, PY - 42, P["BOX_H"]), "84 mm window in top plate", "R"),
    ], img.shape[1], top=120, bottom=1020)
    save(fig, "v2_cutaway.png")


def view_section(sc):
    P = sc.p
    cut_x = 0.0                                  # plane through the pen axis (pen at palm centre)
    cam = Camera((1, 0, 0), (0, 95, 66), 182, (1700, 640))
    objs = sc.objects(pose=(0, 0, 1), alpha={"TopPlate": 0.0, "HandDummy": 0.0, "Shell": 0.0},
                      hide=("ForearmDummy",))
    img = render(cam, objs, clip=(0, cut_x))
    fig, ax = figure(img, "Section through the pen axis (x = 0), pen DOWN",
                     "Reddish = cut faces. Hand palm-down in the 2 mm recess; the pen rises through the window.")
    H, PZ, PU = P["BOX_H"], P["PALM_Z"], P["PLATE_UNDER"]
    y0 = -142
    dim(ax, cam, (cut_x, 322, 0), (cut_x, 322, H), "72", (0, 0))
    dim(ax, cam, (cut_x, 0, -8), (cut_x, 330, -8), "330 box", (0, 0))
    dim(ax, cam, (cut_x, y0, -8), (cut_x, 0, -8), "142 pad", (0, 0))
    dim(ax, cam, (cut_x, P["PALM_Y"] - 42, H + 14), (cut_x, P["PALM_Y"] + 42, H + 14),
        "84 window", (0, 0))
    dim(ax, cam, (cut_x, 40, PU), (cut_x, 40, H), "6 plate", (60, 0))
    PY = P["PALM_Y"]
    callouts(ax, cam, [
        ((cut_x, PY, PZ + 1.5), "pen tip: 1.5 mm into the palm\n(spring-limited, ~0.6 N)", "R"),
        ((cut_x, PY, 50), "push solenoid, 7.5 mm stroke", "R"),
        ((cut_x, PY - 16, 34), "Y-bar (z = 34)", "L"),
        ((cut_x, PY - 85, 48), "x-rail + X-bar end block (z = 48)", "L"),
        ((cut_x, 262, 25), "Y stepper", "R"),
        ((cut_x, 270, 58), "Braille cell module", "R"),
        ((cut_x, 120, 95), "hand, palm down", "L"),
        ((cut_x, -80, 50), "forearm pad", "L"),
        ((cut_x, 30, 12), "electronics bay", "L"),
    ], img.shape[1], top=130, bottom=600)
    save(fig, "v2_section.png")


def view_section_detail(sc, down=1):
    P = sc.p
    cam = Camera((1, 0, 0), (0, 150, 52), 122, (1500, 1050))
    objs = sc.objects(pose=(0, 0, down), alpha={"TopPlate": 0.0, "HandDummy": 0.0, "Shell": 0.0},
                      hide=("ForearmDummy", "ForearmPad"))
    img = render(cam, objs, clip=(0, 0.0))
    fig, ax = figure(img, "Section detail at the pen (x = 0), pen %s" % ("DOWN" if down else "UP"),
                     "Heights from the table (mm). Pen retracted: tip 6 mm below the palm; pressed: 1.5 mm into it.")
    H, PZ, PU, PY = P["BOX_H"], P["PALM_Z"], P["PLATE_UNDER"], P["PALM_Y"]
    yd = PY + 44
    dim(ax, cam, (0, yd, 0), (0, yd, 34), "34", (0, 0))
    dim(ax, cam, (0, yd + 7, 0), (0, yd + 7, 48), "48", (0, 0))
    dim(ax, cam, (0, yd + 14, 0), (0, yd + 14, PU), "66", (0, 0))
    dim(ax, cam, (0, yd + 21, 0), (0, yd + 21, H), "72", (0, 0))
    dim(ax, cam, (0, PY - 56, PU), (0, PY - 56, H), "6", (0, 0))
    dim(ax, cam, (0, PY - 62, PZ), (0, PY - 62, H), "2", (0, 0))
    dim(ax, cam, (0, PY - 42, H + 16), (0, PY + 42, H + 16), "window 84", (0, 0))
    dim(ax, cam, (0, PY + 14, PZ - 6), (0, PY + 14, PZ + 1.5), "7.5 stroke", (0, 0))
    callouts(ax, cam, [
        ((0, PY - 30, 85), "hand, palm down (palm skin at z = 70)", "L"),
        ((0, PY, PZ + 1.5 if down else PZ - 6), "pen tip, 0.5 mm radius point", "R"),
        ((0, PY - 4, 40), "push solenoid + return spring\n(pen force set by tip spring)", "L"),
        ((-16, PY - 16, 34), "Y-bar, 8 mm rod (z 34)", "L"),
        ((-16, PY - 16 - 12, 44), "carriage: cross block on both bars", "L"),
        ((-16, PY + 60, 48), "X-bar, 8 mm rod (z 48)", "R"),
        ((0, PY - 52, 69), "top plate, 6 mm", "L"),
    ], img.shape[1], top=140, bottom=1000)
    save(fig, "v2_section_detail.png" if down else "v2_section_detail_up.png")


def view_top(sc):
    P = sc.p
    cam = Camera((0, 0, 1), (0, 120, 0), 540, (1250, 1450))
    objs = sc.objects(pose=(0, 0, 0), alpha={"HandDummy": 0.55, "ForearmDummy": 0.6, "TopPlate": 0.0},
                      color={"TopPlate": (0.92, 0.93, 0.94)})
    img = render(cam, objs)
    fig, ax = figure(img, "Top layout (right hand)", "Coordinates in mm: x from the centre line, y from the box front edge.")
    H = P["BOX_H"] + 8
    W2 = P["BOX_W"] / 2
    dim(ax, cam, (-W2, -10, H), (W2, -10, H), "260", (0, 0))
    dim(ax, cam, (W2 + 12, 0, H), (W2 + 12, P["BOX_L"], H), "330", (0, 0))
    dim(ax, cam, (W2 + 12 + 30, 0, H), (W2 + 42, P["PALM_Y"], H), "155 to writing centre", (0, 0))
    dim(ax, cam, (-42, P["PALM_Y"] - 54, H), (42, P["PALM_Y"] - 54, H), "84 window", (0, 0))
    dim(ax, cam, (W2 + 12 + 60, 0, H), (W2 + 72, P["WRIST_Y"], H), "100 wrist", (0, 0))
    items = [((x, y, H), "%s button (%d, %d)" % (n, x, y)) for n, (x, y) in P["buttons"].items()]
    items += [((x, y, H), "Braille cell, %s (%d, %d)" % (f, x, y), "L")
              for (x, y), f in zip(P["braille"], ("index", "middle"))]
    items += [((P["wrist_pad"][0], P["wrist_pad"][1], H), "hand-present pad (0, 75)", "R"),
              ((84, 297, H), "mic grille", "R"), ((0, -70, H), "forearm pad", "R"),
              ((0, P["PALM_Y"], H), "writing centre (0, 155)", "R")]
    callouts(ax, cam, items, img.shape[1], top=150)
    save(fig, "v2_top.png")


def view_layers(sc):
    """Exploded stack: top plate, hand, gantry, base."""
    P = sc.p
    cam = Camera((0.55, -0.85, 0.42), (0, 165, 130), 600, (1400, 1250))
    lift = {"TopPlate": 90, "WristPad": 90, "BraillePins": 90, "ButtonPause": 90, "ButtonRepeat": 90,
            "ButtonSpeed": 90, "HandDummy": 210, "ForearmDummy": 210,
            "BrailleCells": 90, "ButtonSwitches": 90, "Mic": 90}
    objs = []
    for name, V, F, rgb, a in sc.objects(pose=(0, 0, 0), hide=("ForearmPad",),
                                         alpha={"HandDummy": 0.35, "ForearmDummy": 0.5, "TopPlate": 0.0}):
        objs.append((name, V + np.array([0, 0, lift.get(name, 0)]), F, rgb, a))
    img = render(cam, objs)
    fig, ax = figure(img, "Exploded build stack", "Base tray with gantry and electronics; top plate with buttons and Braille; hand.")
    H = P["BOX_H"]
    callouts(ax, cam, [
        ((-110, 40, H + 90), "3  top plate (6 mm): recess, window,\n    button + Braille holes", "L"),
        ((-30, 285, H + 60), "    Braille cells + button switches\n    mounted under the plate", "L"),
        ((0, 140, H + 240), "4  hand rests palm-down in the recess", "R"),
        ((0, P["PALM_Y"] - 10, 48), "2  XY gantry + pen on the base", "R"),
        ((125, 80, 30), "1  base tray: 3 mm walls, floor,\n    electronics, steppers", "R"),
    ], img.shape[1], top=150)
    save(fig, "v2_exploded.png")


def anim_writing(sc, text="HI"):
    P = sc.p
    cam = Camera((0.62, -0.62, 0.48), (0, 155, 52), 230, (900, 680), ss=2)
    t, x, y, z, _ = pw.build_path(text)
    step = 3
    idx = list(range(0, len(t), step))
    alpha = {"TopPlate": 0.80, "HandDummy": 0.75, "Shell": 0.9}
    hide = ("ForearmPad", "ForearmDummy", "WristPad")
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
    ax.text(18, 60, "Pen rises through the window and writes on the palm from below (mirrored as print-on-palm)",
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


VIEWS = {"product": view_product, "cutaway": view_cutaway, "section": view_section,
         "detail": view_section_detail,
         "top": view_top, "exploded": view_layers, "writing": anim_writing}

if __name__ == "__main__":
    sc = Scene(os.path.join(HERE, "build", "v2_mesh.json"))
    for name in sys.argv[1:] or VIEWS:
        VIEWS[name](sc)
