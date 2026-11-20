"""The ring around a pin's picture: its look and how it is painted.

A ring is a border just inside the pin's finished edge (the safe-area line). It follows the
pin's shape, so it is a circle on a round pin, a heart on a heart pin, and so on. Anything
outside the ring (the strip that folds behind the pin) takes the ring's look too, so the
finished edge is clean.

A ring is a ``Ring``: thickness in mm, a colour, a material (flat, glossy, metallic, ...) and
optionally the path of an image used as the ring's pattern. Only Pillow is used: materials are
drawn with gradients, blurs and lighting, so they stay sharp at any print resolution.
"""

import colorsys
import math
import os
import random
from collections import namedtuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import shapes

MIN_MM = 1.2          # thinner than this vanishes in print and when the pin is pressed
MAX_MM = 6.0          # an absolute cap, however big the pin is
MAX_SHARE = 0.12      # of the pin's shorter side
DEFAULT_SHARE = 0.05

Ring = namedtuple("Ring", "mm col material image scale", defaults=("flat", None, 0.3))

MATERIALS = (("flat", "Matte"), ("glossy", "Gloss"), ("satin", "Satin"),
             ("metallic", "Metal"), ("pearl", "Pearl"), ("gradient", "Gradient"),
             ("grain", "Grain"), ("frost", "Frost"))
MATERIAL_NAMES = dict(MATERIALS)

CATEGORIES = ("Modern", "Aesthetic", "Cute", "Girly")

# One-tap styles: (category, name, material, colour, thickness share).
THEMES = (
    ("Modern", "Onyx", "glossy", (28, 30, 36), 1.0),
    ("Modern", "Chrome", "metallic", (176, 184, 196), 1.0),
    ("Modern", "Cloud", "flat", (238, 238, 234), 0.9),
    ("Modern", "Cobalt", "satin", (40, 84, 196), 1.0),
    ("Modern", "Graphite", "satin", (74, 80, 92), 1.0),
    ("Modern", "Ice", "frost", (186, 214, 236), 1.0),
    ("Modern", "Gold", "metallic", (214, 168, 70), 1.0),
    ("Modern", "Forest", "glossy", (28, 84, 64), 1.0),
    ("Aesthetic", "Sage", "grain", (150, 172, 142), 1.0),
    ("Aesthetic", "Sand", "satin", (216, 192, 160), 1.0),
    ("Aesthetic", "Terracotta", "flat", (196, 116, 88), 1.0),
    ("Aesthetic", "Mocha", "grain", (118, 86, 72), 1.0),
    ("Aesthetic", "Olive", "satin", (128, 128, 72), 1.0),
    ("Aesthetic", "Dusty blue", "frost", (146, 170, 196), 1.0),
    ("Aesthetic", "Oat", "grain", (232, 220, 200), 1.0),
    ("Aesthetic", "Plum", "flat", (112, 64, 92), 1.0),
    ("Cute", "Butter", "satin", (248, 224, 128), 1.1),
    ("Cute", "Mint", "flat", (150, 214, 190), 1.1),
    ("Cute", "Sky", "glossy", (140, 196, 236), 1.1),
    ("Cute", "Peach", "frost", (248, 184, 150), 1.1),
    ("Cute", "Lemon", "glossy", (250, 236, 110), 1.1),
    ("Cute", "Baby blue", "frost", (220, 232, 248), 1.1),
    ("Cute", "Apricot", "gradient", (250, 170, 120), 1.1),
    ("Cute", "Matcha", "satin", (176, 214, 140), 1.1),
    ("Girly", "Blush", "pearl", (244, 190, 200), 1.1),
    ("Girly", "Bubblegum", "glossy", (240, 120, 170), 1.1),
    ("Girly", "Lilac", "gradient", (200, 160, 230), 1.1),
    ("Girly", "Rose gold", "metallic", (214, 140, 128), 1.1),
    ("Girly", "Cherry", "glossy", (200, 40, 70), 1.1),
    ("Girly", "Peony", "satin", (236, 150, 180), 1.1),
    ("Girly", "Berry", "flat", (160, 50, 100), 1.1),
    ("Girly", "Orchid", "gradient", (214, 120, 200), 1.1),
)


# ---- thickness ----------------------------------------------------------------------

def limits(fw, fh):
    """(smallest, largest) ring thickness in mm for a finished pin ``fw`` x ``fh`` mm."""
    short = min(fw, fh)
    hi = max(MIN_MM + 0.4, min(MAX_MM, short * MAX_SHARE))
    return MIN_MM, round(hi, 2)


def default_mm(fw, fh, share=1.0):
    """A good-looking starting thickness: about 5 % of the pin's shorter side."""
    lo, hi = limits(fw, fh)
    return round(max(lo, min(hi, min(fw, fh) * DEFAULT_SHARE * share)), 2)


def clamp(mm, fw, fh):
    """``mm`` held inside the allowed range for this pin."""
    lo, hi = limits(fw, fh)
    return max(lo, min(hi, float(mm)))


# ---- colours and saving -------------------------------------------------------------

def to_hex(col):
    """(r, g, b) -> '#rrggbb'."""
    return "#%02x%02x%02x" % tuple(int(v) for v in col)


def from_hex(text):
    """'#rrggbb' -> (r, g, b)."""
    text = text.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def as_ring(r):
    """Any ring-like value (a Ring, or an old (mm, colour) pair) as a Ring."""
    if r is None or isinstance(r, Ring):
        return r
    return Ring(float(r[0]), tuple(r[1]), *tuple(r[2:]))


def key(r):
    """A hashable summary of a ring, used to cache pictures."""
    if r is None:
        return None
    r = as_ring(r)
    return (round(r.mm, 2), tuple(r.col), r.material, r.image or "", round(r.scale, 2))


def to_saved(r, base=None):
    """A ring as plain data for a canvas file. ``base`` (the canvas's folder) lets the pattern
    image also be stored by relative path.
    """
    r = as_ring(r)
    d = {"mm": r.mm, "color": to_hex(r.col), "material": r.material}
    if r.image:
        d["image"], d["scale"] = r.image, r.scale
        if base:
            try:
                d["rel"] = os.path.relpath(r.image, base)
            except ValueError:
                pass
    return d


def from_saved(data, base=None):
    """The ring from saved data (the old [mm, '#rrggbb'] form too), or None if unreadable."""
    try:
        if isinstance(data, (list, tuple)):
            return Ring(float(data[0]), from_hex(str(data[1])))
        mat = data.get("material", "flat")
        mat = mat if mat in MATERIAL_NAMES else "flat"
        image = None
        for cand in (data.get("image") or "",
                     os.path.join(base, data["rel"]) if base and data.get("rel") else ""):
            if cand and os.path.isfile(cand):
                image = os.path.abspath(cand)
                break
        return Ring(float(data["mm"]), from_hex(str(data["color"])), mat, image,
                    float(data.get("scale", 0.3)))
    except (TypeError, ValueError, IndexError, KeyError, AttributeError):
        return None


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _mul(c, f):
    return tuple(max(0, min(255, round(v * f))) for v in c)


def tidy(col):
    """Nudge a colour so a ring in it reads well in print: not too pale, not too dark."""
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in col))
    l = max(0.22, min(0.80, l))
    s = max(s, 0.0) if s < 0.12 else max(0.35, s)
    return tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l, s))


def dominant_colours(img, n=6):
    """The main colours of a picture, best ring candidates first.

    The picture is shrunk and grouped into a few colours. A colour scores for how much of the
    picture it covers and for being lively (a grey or near-white ring looks like no ring), so
    the first one is a good automatic choice. Each is tidied for print.
    """
    small = img.convert("RGB")
    small.thumbnail((96, 96))
    q = small.quantize(colors=max(n + 2, 8), method=Image.MEDIANCUT)
    pal = q.getpalette()
    total = small.size[0] * small.size[1]
    found = []
    for count, idx in sorted(q.getcolors(), reverse=True):
        col = tuple(pal[idx * 3:idx * 3 + 3])
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in col))
        lively = 0.35 + s
        tone = 1.0 if 0.15 <= l <= 0.88 else 0.35
        found.append(((count / total) ** 0.5 * lively * tone, col))
    found.sort(reverse=True)
    out = []
    for _score, col in found:
        col = tidy(col)
        if all(sum(abs(a - b) for a, b in zip(col, o)) > 60 for o in out):
            out.append(col)
        if len(out) >= n:
            break
    return out or [(120, 120, 120)]


# ---- shape masks --------------------------------------------------------------------

def mask(shape, fw, fh, mm, size, sx, sy, cx, cy, ss=3):
    """A smooth 'L' mask of ``size`` pixels: white inside the pin's outline shrunk by ``mm``.
    ``sx`` / ``sy`` are pixels per mm and (cx, cy) the pin's centre in pixels. With ``mm`` 0
    it is the finished face; with the ring's thickness it is where the picture shows.
    """
    w, h = size
    iw, ih = fw - 2 * mm, fh - 2 * mm
    big = Image.new("L", (w * ss, h * ss), 0)
    if iw > 0.5 and ih > 0.5:
        pts = shapes.outline(shape, iw, ih)
        ImageDraw.Draw(big).polygon(
            [((cx + x * sx) * ss, (cy + y * sy) * ss) for x, y in pts], fill=255)
    return big.resize((w, h), Image.LANCZOS)


# ---- painting the materials ---------------------------------------------------------

def _wedges(size, cx, cy, n, colour_at):
    """A picture of ``n`` thin slices around (cx, cy), each filled by ``colour_at(0..1)``:
    the basis of every material that changes along the ring.
    """
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    far = math.hypot(*size) * 1.5
    step = 2 * math.pi / n
    for i in range(n):
        a0, a1 = i * step, (i + 1) * step * 1.03
        d.polygon([(cx, cy), (cx + far * math.cos(a0), cy + far * math.sin(a0)),
                   (cx + far * math.cos(a1), cy + far * math.sin(a1))],
                  fill=colour_at((i + 0.5) / n))
    return im


def _lit(img, hmap, sigma, strength, spec=0):
    """Light ``img`` as if the ring were a raised, rounded tube lit from the top left."""
    k = max(0.06, 6.0 / max(1.0, sigma))
    e = hmap.filter(ImageFilter.Kernel((3, 3), (-1, -1, 0, -1, 0, 1, 0, 1, 1), k, 128))
    hi = e.point(lambda v: int(max(0, min(255, (v - 128) * 2)) * strength))
    lo = e.point(lambda v: int(max(0, min(255, (128 - v) * 2)) * strength))
    img = Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, hi)
    img = Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, lo.point(lambda v: v // 1))
    if spec:
        sp = e.point(lambda v: int(max(0, min(255, (v - 175) * 5)) * spec))
        img = Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, sp)
    return img


_tiles = {}


def _tile_image(path):
    """A custom pattern image, loaded once."""
    t = _tiles.get(path)
    if t is None:
        if len(_tiles) > 6:
            _tiles.clear()
        t = Image.open(path)
        t = t.convert("RGB")
        t.thumbnail((1600, 1600), Image.LANCZOS)
        _tiles[path] = t
    return t


def pattern_ppi(ring, fw, fh):
    """Print sharpness (pixels per inch) of a ring's pattern image, or None without one."""
    r = as_ring(ring)
    if not r or not r.image:
        return None
    try:
        t = _tile_image(r.image)
    except (OSError, ValueError):
        return None
    mm = max(1.0, r.scale * min(fw, fh))
    return t.size[0] / (mm / 25.4)


def _paint(r, ctx):
    """The ring's coloured surface, before it is lit, as an image of the whole area."""
    size, cx, cy, px = ctx["size"], ctx["cx"], ctx["cy"], ctx["px"]
    col, mat = r.col, r.material
    w, hh = size
    if r.image:
        try:
            t = _tile_image(r.image)
        except (OSError, ValueError):
            t = None
        if t is not None:
            tp = max(8, int(r.scale * min(ctx["fw"], ctx["fh"]) * px))
            t = t.resize((tp, max(1, round(tp * t.size[1] / t.size[0]))), Image.LANCZOS)
            out = Image.new("RGB", size)
            x0 = int(cx - w // 2) % t.size[0] - t.size[0]
            y0 = int(cy - hh // 2) % t.size[1] - t.size[1]
            for y in range(y0, hh, t.size[1]):
                for x in range(x0, w, t.size[0]):
                    out.paste(t, (x, y))
            return out
    if mat == "metallic":
        dark, light = _mul(col, 0.55), _mix(col, (255, 255, 255), 0.6)

        def at(u):
            v = 0.5 + 0.5 * math.cos(2 * math.pi * 2 * u + 0.7)
            v2 = 0.5 + 0.5 * math.cos(2 * math.pi * 3 * u + 2.1)
            return _mix(_mix(dark, col, v), light, (max(0, v2 - 0.45) / 0.55) ** 2 * 0.75)
        return _wedges(size, cx, cy, 360, at)
    if mat == "pearl":
        base = _mix(col, (255, 255, 255), 0.45)
        return _wedges(size, cx, cy, 240, lambda u: _mix(base, (
            (255, 236, 244), (232, 244, 255), (240, 255, 238))[int(u * 6) % 3],
            0.35 + 0.25 * math.sin(2 * math.pi * 3 * u)))
    if mat == "gradient":
        hue, lig, sat = colorsys.rgb_to_hls(*(v / 255 for v in col))
        other = tuple(round(v * 255) for v in colorsys.hls_to_rgb(
            (hue + 0.07) % 1, min(0.9, lig + 0.16), sat))
        side = int(math.hypot(w, hh) * 1.2) + 2
        ramp = Image.linear_gradient("L").resize((side, side), Image.BILINEAR)
        ramp = ramp.rotate(45, resample=Image.BICUBIC)
        x0, y0 = (side - w) // 2, (side - hh) // 2
        ramp = ramp.crop((x0, y0, x0 + w, y0 + hh))
        return Image.composite(Image.new("RGB", size, other), Image.new("RGB", size, col),
                               ramp)
    if mat in ("grain", "frost"):
        base = Image.new("RGB", size, _mix(col, (255, 255, 255), 0.22) if mat == "frost" else col)
        g = max(1, round(px * (0.05 if mat == "frost" else 0.08)))
        gw, gh = w // g + 2, hh // g + 2
        noise = Image.frombytes("L", (gw, gh), random.Random(7).randbytes(gw * gh))
        noise = noise.resize((gw * g, gh * g), Image.NEAREST).crop((0, 0, w, hh))
        soft = ImageChops.soft_light(base, noise.convert("RGB"))
        return Image.blend(base, soft, 0.9 if mat == "grain" else 0.6)
    return Image.new("RGB", size, tuple(col))        # flat, glossy


_STRENGTH = {"flat": (0.12, 0.0), "glossy": (0.5, 0.7), "satin": (0.3, 0.2),
             "metallic": (0.55, 0.35), "pearl": (0.4, 0.45), "gradient": (0.3, 0.25),
             "grain": (0.22, 0.0), "frost": (0.3, 0.1)}

_layers = {}


def layer(ring, shape, fw, fh, size, sx, sy, cx, cy, ss=2):
    """Paint a ring. Returns (surface, inside): ``surface`` is an RGB picture of ``size`` pixels
    showing the ring's material (it covers everything, the mask picks the ring out) and
    ``inside`` is the 'L' mask that is white where the pin's picture shows.
    """
    r = as_ring(ring)
    mm = clamp(r.mm, fw, fh)
    ck = (key(r._replace(mm=mm)), shape, round(fw, 2), round(fh, 2), size, round(sx, 3),
          round(sy, 3), round(cx, 1), round(cy, 1))
    hit = _layers.get(ck)
    if hit is not None:
        return hit
    px = (sx + sy) / 2
    face = mask(shape, fw, fh, 0, size, sx, sy, cx, cy, ss)
    inside = mask(shape, fw, fh, mm, size, sx, sy, cx, cy, ss)
    mat = "pattern" if r.image else r.material
    ctx = dict(size=size, cx=cx, cy=cy, px=px, fw=fw, fh=fh, mm=mm)
    surface = _paint(r, ctx)
    strength, spec = _STRENGTH.get(mat, (0.3, 0.0))
    if strength:
        band = ImageChops.subtract(face, inside)
        sigma = max(1.2, mm * px * 0.28)
        surface = _lit(surface, band.filter(ImageFilter.GaussianBlur(sigma)), sigma,
                       strength, spec)
    if len(_layers) > 12:
        _layers.clear()
    _layers[ck] = (surface, inside)
    return surface, inside


def apply(img, ring, shape, fw, fh, w_mm, h_mm):
    """Paint ``ring`` onto ``img``, a picture of the paper-shape box ``w_mm`` x ``h_mm``."""
    w, h = img.size
    surface, inside = layer(ring, shape, fw, fh, (w, h), w / w_mm, h / h_mm, w / 2, h / 2)
    return Image.composite(img.convert("RGB"), surface, inside)
