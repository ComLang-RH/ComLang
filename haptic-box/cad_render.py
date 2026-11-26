"""Numpy-only renderer for the v2 CAD model (meshes exported by haptic_box_v2.FCMacro).

Used by render_views.py (still images, GIF) and by haptic_app.py (live 3D simulation).
Orthographic z-buffer rasteriser with flat shading, outline edges, transparent parts and
section cuts. LiveView renders moving parts as pre-rasterised sprites that are shifted per
frame (exact for an orthographic camera and translating parts), fast enough for real time.
"""
import json
import os

import numpy as np

import palm_writer as pw

HERE = os.path.dirname(os.path.abspath(__file__))
MESH = os.path.join(HERE, "build", "v2_mesh.json")
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
        # anatomical hand + forearm variants: hands[size][pose or "arm"] = (V, F)
        self.hands = {sz: {k: (np.array(m["v"], float), np.array(m["f"], int)) for k, m in poses.items()}
                      for sz, poses in d.get("hands", {}).items()}

    def palm_offset(self, size):
        """How far (mm, y) this hand size's palm centre sits from the writing centre."""
        import hand_model as HM
        h = HM.Hand(size, self.p["WRIST_Y"], self.p["PALM_Z"], self.p["TS"])
        return h.palm_centre[1] - self.p["PALM_Y"]

    def offsets(self, px, py, down):
        """Same mapping as haptic_box_v2.offsets(): palm coords -> part translations."""
        mx = -px
        cx, cy = mx - self.p.get("PEN_DX", 16.0), py - self.p.get("PEN_DY", 16.0)
        dz = self.stroke * down
        return {"YBar": (0, cy, 0), "XBar": (cx, 0, 0), "Carriage": (cx, cy, 0), "Pen": (cx, cy, dz)}

    def objects(self, pose=(0, 0, 0), hide=(), alpha=None, color=None, hand="medium", hand_pose="rest"):
        """[(name, V, F, rgb, alpha)] for the given pen pose (palm x, y, down 0..1), with the
        anatomical hand of size `hand` in `hand_pose` ('rest', 'Pause', 'Repeat', 'Speed')."""
        alpha, color = alpha or {}, color or {}
        out = []
        off = self.offsets(*pose)
        for group in (self.static, self.moving):
            for k, (v, f) in group.items():
                if k in hide:
                    continue
                if k == "HandDummy" and hand in self.hands:
                    v, f = self.hands[hand][hand_pose]
                elif k == "ForearmDummy" and hand in self.hands:
                    v, f = self.hands[hand]["arm"]
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
        with np.errstate(invalid="ignore"):
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




# ---------------------------------------------------------------- live view (app)
class LiveView:
    """Real-time view: static parts rasterised once, moving parts as shifted sprites."""

    def __init__(self, scene, direction, center, extent, size, hide=(), alpha=None, hand="medium"):
        self.sc = scene
        self.cam = cam = Camera(direction, center, extent, size, ss=1)
        objs = scene.objects(pose=(0, 0, 0), hide=hide, alpha=alpha, hand=hand)
        moving = set(scene.moving)
        self.base = Buffers(cam)
        self.trans = []
        self.hand_layers = {}
        for name, V, F, rgb, a in objs:
            if name in moving or name == "HandDummy":
                continue
            if a <= 0.01:
                raster(cam, self.base, V, F, rgb, hash(name) % 100000)
            else:
                tz, tcol, te = trans_layer(cam, V, F, rgb)
                self.trans.append((name, tz, tcol, te, a))
        hd = [o for o in objs if o[0] == "HandDummy"]
        if hd:                                    # one pre-rendered layer per hand pose
            _, _, _, rgb, a = hd[0]
            poses = scene.hands.get(hand, {})
            for pose in [p for p in poses if p != "arm"] or ["rest"]:
                V, F = poses[pose] if poses else scene.static["HandDummy"]
                tz, tcol, te = trans_layer(cam, V, F, rgb)
                self.hand_layers[pose] = ("HandDummy", tz, tcol, te, max(a, 0.01))
        # moving parts: rasterise un-placed meshes, keep the covered pixels as a sprite
        self.sprites = {}
        for name in scene.moving:
            V, F = scene.moving[name]
            c, a = scene.colors[name]
            b = Buffers(cam)
            raster(cam, b, V, F, np.array(c), hash(name) % 100000)
            m = np.isfinite(b.z)
            ys, xs = np.nonzero(m)
            if not len(ys):
                continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            sl = (slice(y0, y1), slice(x0, x1))
            self.sprites[name] = (y0, x0, m[sl], b.z[sl], b.col[sl], b.id[sl], b.n[sl])

    def frame(self, px, py, down, ink=None, hand_pose="rest"):
        cam = self.cam
        buf = self.base.copy()
        H, W = buf.z.shape
        for name, (dx, dy, dz) in self.sc.offsets(px, py, down).items():
            if name not in self.sprites:
                continue
            y0, x0, m, z, col, idb, n = self.sprites[name]
            t = np.array([dx, dy, dz], float)
            sx = int(round(t @ cam.r * cam.scale))
            sy = int(round(-(t @ cam.u) * cam.scale))
            sd = float(t @ cam.c)
            Y0, X0 = y0 + sy, x0 + sx
            h, w = m.shape
            a0, b0 = max(0, -Y0), max(0, -X0)
            a1, b1 = min(h, H - Y0), min(w, W - X0)
            if a1 <= a0 or b1 <= b0:
                continue
            src = (slice(a0, a1), slice(b0, b1))
            dst = (slice(Y0 + a0, Y0 + a1), slice(X0 + b0, X0 + b1))
            zz = z[src] + sd
            mm = m[src] & (zz > buf.z[dst])
            buf.z[dst][mm] = zz[mm]
            buf.col[dst][mm] = col[src][mm]
            buf.id[dst][mm] = idb[src][mm]
            buf.n[dst][mm] = n[src][mm]
        if ink is not None and len(ink):
            draw_points(cam, buf, ink, np.array([0.08, 0.25, 0.55]), max(2, int(1.8 * cam.scale)))
        e = edges(buf, cam)
        col = buf.col.copy()
        col[e] *= 0.30
        layers = list(self.trans)
        if self.hand_layers:
            layers.append(self.hand_layers.get(hand_pose, self.hand_layers.get("rest")))
        for _, tz, tcol, te, a in sorted(layers, key=lambda l: float(np.median(l[1][np.isfinite(l[1])]))
                                         if np.isfinite(l[1]).any() else 0):
            mask = tz > buf.z
            col[mask] = (1 - a) * tcol[mask] + a * col[mask]
            em = te & mask
            col[em] *= 0.55
        return (np.clip(col, 0, 1) * 255).astype(np.uint8)


def ppm(img):
    """uint8 HxWx3 -> PPM bytes (Tk PhotoImage can show this without Pillow)."""
    h, w = img.shape[:2]
    return b"P6 %d %d 255\n" % (w, h) + img.tobytes()
