"""Parametric adult hand + forearm, PALM DOWN, for the haptic box (geometry as numbers only).

Used by haptic_box_v2.FCMacro to build the solids, size the hand well, place the buttons and
check reach. Coordinates as in the CAD: x across (+x = user's right), y away from the user,
z up; the palm rests on the well floor at z = palm_z.

Anthropometry (approximate adult values from common tables such as ANSUR / PeopleSize;
confirm against your own user group):
    hand length = wrist crease -> middle fingertip, hand breadth = across the knuckles (MCP).
"""
import math

SIZES = {
    "small": (165.0, 70.0, "~5th percentile woman"),
    "medium": (190.0, 87.0, "~50th percentile man"),
    "large": (205.0, 97.0, "~95th percentile man"),
}
# name, x-offset at the knuckles for the medium hand (+ = thumb side), length / hand length,
# spread angle in degrees (+ = towards the thumb), radius scale
FINGERS = [("index", 30, 0.375, 5, 1.00), ("middle", 10, 0.425, 0, 1.00),
           ("ring", -10, 0.400, -4, 0.95), ("little", -30, 0.315, -10, 0.86)]
PHALANX = (0.47, 0.30, 0.23)          # proximal / middle / distal share of finger length
FLAT = 2.0                             # soft tissue flattened where palm and forearm rest (mm)


def _unit(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n)


class Hand:
    def __init__(self, size, wrist_y, palm_z, ts):
        L, B, self.label = SIZES[size]
        self.size, self.L, self.B = size, L, B
        self.k, self.kl = B / 87.0, L / 190.0
        self.wrist_y, self.palm_z, self.ts = wrist_y, palm_z, ts
        self.palm_len = 0.55 * L
        self.mcp_y = wrist_y + self.palm_len
        self.palm_centre = (0.0, wrist_y + 0.5 * self.palm_len)
        self.thumb_dir = _unit(ts * 0.6, 0.8)

    # ---- body sections: (y, half width, half thickness); ellipses, bottom flattened by FLAT
    def palm_sections(self):
        B, k, y0 = self.B, self.k, self.wrist_y
        return [(y0 - 3, 0.33 * B, 19 * k), (y0 + 0.35 * self.palm_len, 0.50 * B, 16 * k),
                (self.mcp_y - 6, 0.50 * B, 13.5 * k), (self.mcp_y + 4, 0.46 * B, 11.5 * k)]

    def arm_sections(self):
        B, k, y0 = self.B, self.k, self.wrist_y
        return [(y0 - 250, 0.40 * B, 30 * k), (y0 - 80, 0.36 * B, 24 * k), (y0 - 2, 0.33 * B, 19 * k)]

    # ---- digits: chains of joint centres (x, y, z) with radii; capsules between them
    def _finger_rest(self, fx, ratio, spread, rs):
        k, pz = self.k, self.palm_z
        Lf = ratio * self.L
        a = math.radians(spread)
        d = (self.ts * math.sin(a), math.cos(a))
        s = [p * Lf for p in PHALANX]
        r = [9.5 * k * rs, 8.5 * k * rs, 7.5 * k * rs, 6.8 * k * rs]
        p0 = (self.ts * fx * self.k, self.mcp_y - 6)
        along = [0, s[0], s[0] + s[1], s[0] + s[1] + s[2] - r[3]]
        zs = [pz + 11 * k, pz + r[1] + 0.5, pz + r[2] + 0.3, pz + r[3]]
        pts = [(p0[0] + d[0] * u, p0[1] + d[1] * u, z) for u, z in zip(along, zs)]
        return pts, r, d

    def _thumb_rest(self):
        k, kl, pz = self.k, self.kl, self.palm_z
        cmc = (self.ts * 0.30 * self.B, self.wrist_y + 18 * kl)
        s = [44 * kl, 32 * kl, 27 * kl]
        r = [12.5 * k, 11 * k, 10 * k, 9.5 * k]
        d = self.thumb_dir
        along = [0, s[0], s[0] + s[1], s[0] + s[1] + s[2] - r[3]]
        zs = [pz + 15 * k, pz + 11 * k, pz + 10 * k, pz + 9.5 * k]
        pts = [(cmc[0] + d[0] * u, cmc[1] + d[1] * u, z) for u, z in zip(along, zs)]
        return pts, r, d

    def rest(self):
        out = {"thumb": self._thumb_rest()}
        for name, fx, ratio, spread, rs in FINGERS:
            out[name] = self._finger_rest(fx, ratio, spread, rs)
        return out

    @staticmethod
    def aim(chain, target, press_z):
        """Swing a digit about its base towards target (x, y) and press its pad down to
        press_z. Returns (new chain, swing angle deg, shortfall mm)."""
        pts, r, d = chain
        bx, by = pts[0][0], pts[0][1]
        reach = math.hypot(pts[3][0] - bx, pts[3][1] - by)
        D = math.hypot(target[0] - bx, target[1] - by)
        a = _unit(target[0] - bx, target[1] - by)
        swing = math.degrees(math.acos(max(-1.0, min(1.0, a[0] * d[0] + a[1] * d[1]))))
        scale = min(D, reach) / reach                 # flex the digit if the target is closer
        new = []
        for i, p in enumerate(pts):
            u = math.hypot(p[0] - bx, p[1] - by) * scale
            z = p[2]
            if i == 3:
                z = press_z + r[3]                    # pad on the (pressed) button top
            elif i == 2:
                z = max(p[2], press_z + r[2] - 1.5)
            new.append((bx + a[0] * u, by + a[1] * u, z))
        return (new, r, a), swing, max(0.0, D - reach)

    def press_target(self, button):
        """Where the digit's pad must land to press `button`, and the pad height when pressed."""
        ch = self.rest()[button["digit"]]
        if button["shape"] == "bar":                  # press straight down where the tip rests
            tip = ch[0][3]
            y = min(max(tip[1], button["y"] - button["l"] / 2 + 4), button["y"] + button["l"] / 2 - 4)
            return (button["x"], y), self.palm_z - 1.0
        if button.get("symbol") == "wheel":           # thumb pad on the crown of the roller; its
            return (button["x"], button["y"]), button["top"] - 0.5   # press switch travels 0.5 mm
        bx, by = ch[0][0][0], ch[0][0][1]
        a = _unit(button["x"] - bx, button["y"] - by)
        inset = button["r"] - 5.0                     # land 5 mm inside the near edge
        return (button["x"] - a[0] * inset, button["y"] - a[1] * inset), button["top"] - 1.0

    def posed_short(self, button):
        target, z = self.press_target(button)
        return self.aim(self.rest()[button["digit"]], target, z)[2]

    def posed(self, pose, buttons):
        """Digit chains for pose 'rest' or a button name ('Wheel', 'Repeat')."""
        ch = self.rest()
        if pose == "rest":
            return ch, None
        b = buttons[pose]
        target, z = self.press_target(b)
        ch[b["digit"]], swing, short = self.aim(ch[b["digit"]], target, z)
        return ch, (b["digit"], swing, short)


def _rot(v, deg):
    a = math.radians(deg)
    return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a))


def _seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2))
    return math.hypot(p[0] - ax - t * vx, p[1] - ay - t * vy), t


def clearance(hands, centre, cap_r):
    """Smallest gap (mm, plan view) between a round cap and any resting digit or palm."""
    g = 1e9
    for h in hands:
        for pts, r, _ in h.rest().values():
            for i in range(3):
                dist, t = _seg_dist(centre, pts[i], pts[i + 1])
                g = min(g, dist - (r[i] + t * (r[i + 1] - r[i])) - cap_r)
        # palm (ellipse-ish footprint, conservative as a rectangle)
        hx, y0, y1 = h.B / 2, h.wrist_y - 3, h.mcp_y + 4
        dx = max(0.0, abs(centre[0]) - hx)
        dy = max(0.0, y0 - centre[1], centre[1] - y1)
        g = min(g, math.hypot(dx, dy) - cap_r)
    return g


def place_buttons(wrist_y, palm_z, ts, cap_top, gap=2.0):
    """Controls for the RESTING hand, placed where digits can actually go without moving the hand:
    the thumb wheel (roll = speed, press = pause) on the thumb's outward swing arc, Repeat on the
    little finger's outward swing arc,
    each at the smallest swing that clears every resting hand size by `gap` and that every
    size can reach. (Mode is rare and sits on the free-hand strip; no other comfortable digit
    position is left, see DESIGN.md §4.6.)"""
    hs = [Hand(s, wrist_y, palm_z, ts) for s in SIZES]
    med = hs[1]
    out = {}
    for name, digit, rad, sign, sym in (("Wheel", "thumb", 13.0, -ts, "wheel"),
                                        ("Repeat", "little", 13.0, ts, "repeat")):
        best = None
        for swing in range(15, 61):
            pts, r, d = med.rest()[digit]
            dd = _rot(d, sign * swing)
            for rho in range(30, 140):
                c = (pts[0][0] + dd[0] * rho, pts[0][1] + dd[1] * rho)
                if clearance(hs, c, rad) < gap:
                    continue
                b = dict(shape="round", digit=digit, r=rad, top=cap_top, x=c[0], y=c[1], symbol=sym)
                if all(h.posed_short(b) <= 0.0 for h in hs):
                    best = b
                break
            if best:
                break
        if best and digit == "thumb":
            a = _unit(best["x"] - pts[0][0], best["y"] - pts[0][1])
            best["roll"] = a              # tangent of the wheel = the thumb's axis when on it
        out[name] = best
    return out


# ---------------------------------------------------------------- glove-shaped print
def convex_hull(pts):
    """2D convex hull (monotone chain), counter-clockwise, no repeated end point."""
    P = sorted(set((round(x, 4), round(y, 4)) for x, y in pts))
    if len(P) < 3:
        return P

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def glove_outline(hands, margin=5.0):
    """Glove-shaped print instead of a hand print: one smooth 'glove finger' per digit and a
    palm, each the convex hull of that part over ALL hand sizes, grown by the part radius plus
    `margin`. Returns [(name, hull points (x, y), offset mm)]. Hands of any size between the
    smallest and largest model (and of other proportions) fall inside it with room to spare."""
    out = []
    palm = []
    for h in hands:
        for y, hw, _ in h.palm_sections():
            palm += [(-hw, y), (hw, y)]
        for name, (pts, r, _) in h.rest().items():
            palm.append(pts[0][:2])                        # digit roots belong to the palm
            if name == "thumb":
                palm.append(pts[1][:2])                    # thumb web
    out.append(("palm", convex_hull(palm), margin))
    for name in ["thumb"] + [f[0] for f in FINGERS]:
        pts2, rmax = [], 0.0
        for h in hands:
            pts, r, _ = h.rest()[name]
            pts2 += [p[:2] for p in pts]
            rmax = max(rmax, max(r))
        out.append((name, convex_hull(pts2), rmax + margin))
    return out
