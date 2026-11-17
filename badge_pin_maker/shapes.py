"""Pin shapes: round, square, rectangle, oval, pentagon, hexagon, triangle and heart.

Every shape is a closed outline, a list of (x, y) points in millimetres around its own centre
(0, 0), that exactly fills a ``w`` x ``h`` box. The rest of the app draws, masks, clips and
packs pins by using that one outline, so adding a shape means adding it here. There is no
window code in this file.
"""

import math
from functools import lru_cache

from PIL import Image, ImageDraw

SHAPES = ["Round", "Square", "Rectangle", "Oval", "Pentagon", "Hexagon", "Triangle", "Heart"]
DEFAULT_SHAPE = "Round"

# Shapes that are always the same proportions, so a custom size asks for just one number
# (across for round, a side for square and triangle).
ONE_SIZE = ("Round", "Square", "Triangle")
# Shapes whose outline is a curve rather than straight sides (drawn with more points).
SMOOTH = ("Round", "Oval", "Heart")


def _ellipse(n):
    return [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]


def _polygon(sides, start):
    """A regular polygon with ``sides`` corners, the first at angle ``start`` (degrees)."""
    return [(math.cos(math.radians(start + 360.0 * i / sides)),
             math.sin(math.radians(start + 360.0 * i / sides))) for i in range(sides)]


def _heart(n):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x, y))
    return pts


def _rounded(pts, radius, seg):
    """The polygon ``pts`` with every corner rounded off by ``radius`` (in the same units),
    each corner a small arc of ``seg`` steps.
    """
    out, n = [], len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 == 0 or l2 == 0:
            continue
        u1, u2 = (v1[0] / l1, v1[1] / l1), (v2[0] / l2, v2[1] / l2)
        cosa = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        half = math.acos(cosa) / 2
        if half < 1e-6 or half > math.pi / 2 - 1e-6:
            out.append(p1)
            continue
        t = min(radius / math.tan(half), l1 / 2, l2 / 2)          # how far the arc starts
        r = t * math.tan(half)
        a = (p1[0] + u1[0] * t, p1[1] + u1[1] * t)
        b = (p1[0] + u2[0] * t, p1[1] + u2[1] * t)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        lb = math.hypot(*bis) or 1.0
        c = (p1[0] + bis[0] / lb * r / math.sin(half), p1[1] + bis[1] / lb * r / math.sin(half))
        a0 = math.atan2(a[1] - c[1], a[0] - c[0])
        a1 = math.atan2(b[1] - c[1], b[0] - c[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi        # the short way round
        for j in range(seg + 1):
            ang = a0 + da * j / seg
            out.append((c[0] + r * math.cos(ang), c[1] + r * math.sin(ang)))
    return out


def _fit(pts, w, h):
    """Scale and move ``pts`` so they exactly fill a w x h box centred on (0, 0)."""
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    sx, sy = w / (x1 - x0), h / (y1 - y0)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return [((x - mx) * sx, (y - my) * sy) for x, y in pts]


@lru_cache(maxsize=512)
def outline(shape, w, h, detail=1):
    """The outline of ``shape`` filling a ``w`` x ``h`` mm box, as a tuple of (x, y) points
    around (0, 0). ``detail`` 1 is smooth enough to print; 0 is a light version for the maths
    of packing pins on a sheet.
    """
    fine = detail > 0
    if shape in ("Round", "Oval"):
        raw = _ellipse(180 if fine else 40)
    elif shape in ("Square", "Rectangle"):
        corner = min(w, h) * 0.10
        raw = _rounded(_fit([(-1, -1), (1, -1), (1, 1), (-1, 1)], w, h), corner,
                       10 if fine else 3)
    elif shape == "Pentagon":
        raw = _fit(_polygon(5, -90), w, h)
        raw = _rounded(raw, min(w, h) * 0.05, 8 if fine else 2)
    elif shape == "Hexagon":
        raw = _fit(_polygon(6, 0 if w > h else -90), w, h)    # flat on top when wide
        raw = _rounded(raw, min(w, h) * 0.05, 8 if fine else 2)
    elif shape == "Triangle":
        raw = _fit([(0, -1), (0.866, 0.5), (-0.866, 0.5)], w, h)
        raw = _rounded(raw, min(w, h) * 0.07, 8 if fine else 2)
    elif shape == "Heart":
        raw = _heart(200 if fine else 48)
    else:
        raise ValueError(f"unknown shape {shape!r}")
    return tuple(_fit(raw, w, h))


def _inside(pts, x, y):
    """Is the point (x, y) inside the polygon ``pts``? (The usual ray-crossing test.)"""
    inside, n = False, len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def contains(shape, w, h, x, y):
    """Is the point (x, y), measured in mm from the shape's centre, inside it?"""
    if abs(x) > w / 2 or abs(y) > h / 2:
        return False
    if shape in ("Round", "Oval"):
        return (2 * x / w) ** 2 + (2 * y / h) ** 2 <= 1.0
    return _inside(outline(shape, w, h), x, y)


def canvas_points(shape, w, h, cx, cy, scale, grow=0.0):
    """The outline as a flat [x0, y0, x1, y1, ...] list for a Tk canvas: centred on the
    pixel (cx, cy), ``scale`` pixels per mm, and with the box ``grow`` pixels bigger all
    round (used for halos and drop highlights).
    """
    ww, hh = w * scale, h * scale
    if grow and ww > 0 and hh > 0:
        pts = _fit(outline(shape, w, h), ww + 2 * grow, hh + 2 * grow)
        scale = 1.0
    else:
        pts = outline(shape, w, h)
    flat = []
    for x, y in pts:
        flat.append(cx + x * scale)
        flat.append(cy + y * scale)
    return flat


def mask(shape, w_px, h_px, inner_w=None, inner_h=None, ss=3):
    """A smooth 'L' mask, ``w_px`` x ``h_px``, white inside the shape. With ``inner_w`` and
    ``inner_h`` (pixels) the shape is drawn that much smaller, centred (the pin's front face
    inside its paper).
    """
    big = Image.new("L", (w_px * ss, h_px * ss), 0)
    iw = w_px if inner_w is None else inner_w
    ih = h_px if inner_h is None else inner_h
    if iw > 1 and ih > 1:
        pts = _fit(outline(shape, 1.0, 1.0), iw * ss, ih * ss)
        cx, cy = w_px * ss / 2, h_px * ss / 2
        ImageDraw.Draw(big).polygon([(cx + x, cy + y) for x, y in pts], fill=255)
    return big.resize((w_px, h_px), Image.LANCZOS)


# ---- distances, for packing shapes on a sheet ---------------------------------------

def _seg_dist2(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    ex, ey = ax + t * dx - p[0], ay + t * dy - p[1]
    return ex * ex + ey * ey


def _crosses(p1, p2, p3, p4):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (o(p1, p2, p3) > 0) != (o(p1, p2, p4) > 0) and (o(p3, p4, p1) > 0) != (o(p3, p4, p2) > 0)


def apart(A, B, dx, dy, gap):
    """True when outline ``A`` and a copy of ``A`` moved by (dx, dy) are at least ``gap``
    millimetres from each other. ``B`` is A's points moved by that amount.
    """
    ax0, ax1 = min(p[0] for p in A), max(p[0] for p in A)
    ay0, ay1 = min(p[1] for p in A), max(p[1] for p in A)
    if abs(dx) >= ax1 - ax0 + gap or abs(dy) >= ay1 - ay0 + gap:
        return True                                  # the boxes are far enough apart
    Bm = [(x + dx, y + dy) for x, y in B]
    g2 = gap * gap
    n, m = len(A), len(Bm)
    for i in range(n):
        a1, a2 = A[i], A[(i + 1) % n]
        for j in range(m):
            b1, b2 = Bm[j], Bm[(j + 1) % m]
            if _crosses(a1, a2, b1, b2):
                return False
            if (_seg_dist2(a1, b1, b2) < g2 or _seg_dist2(b1, a1, a2) < g2):
                return False
    return not (_inside(A, Bm[0][0], Bm[0][1]) or _inside(Bm, A[0][0], A[0][1]))


def _smallest(ok, lo, hi, steps=22):
    """The smallest value in [lo, hi] for which ``ok(value)`` holds (``ok`` goes from False
    to True once as the value grows; ``hi`` is known to be fine).
    """
    for _ in range(steps):
        mid = (lo + hi) / 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi


@lru_cache(maxsize=256)
def pitches(shape, w, h, gap):
    """How close copies of a shape may sit with ``gap`` mm between their outlines. Returns
    (px, dy_aligned, dy_offset): the spacing along a row, the row spacing when rows line up,
    and the row spacing when every other row is shifted by half of px so the shapes nest.
    """
    A = outline(shape, w, h, 0)
    px = _smallest(lambda v: apart(A, A, v, 0, gap), 0.0, w + gap)
    dy_a = _smallest(lambda v: apart(A, A, 0, v, gap), 0.0, h + gap)

    def nested(v):
        return (apart(A, A, px / 2, v, gap) and apart(A, A, -px / 2, v, gap)
                and apart(A, A, 0, 2 * v, gap))
    dy_o = _smallest(nested, 0.0, h + gap)
    return px, dy_a, dy_o
