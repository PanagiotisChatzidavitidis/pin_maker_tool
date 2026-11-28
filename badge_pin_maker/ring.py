"""The ring around a pin's picture: its look and how it is painted.

A ring is a border just inside the pin's finished edge (the safe-area line). It follows the
pin's shape, so it is a circle on a round pin, a heart on a heart pin, and so on. Anything
outside the ring (the strip that folds behind the pin) takes the ring's look too, so the
finished edge is clean.

Every style here is built for print: flat, crisp, graphic ink (a solid band, two-tone bands,
a band with a fine line, a gradient, polka dots, a stitched line, a gold-foil look, or your
own pattern). Nothing relies on fake 3D lighting that looks odd once it is printed.
Only Pillow is used, so the ring is painted at whatever resolution is asked for.

A ring is a ``Ring``: thickness in mm, a main colour, a style, an optional accent colour
(``col2``), and optionally the path of an image used as the ring's pattern.
"""

import colorsys
import math
import os
from collections import namedtuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import shapes

MIN_MM = 1.2          # thinner than this vanishes in print and when the pin is pressed
MAX_MM = 6.0          # an absolute cap, however big the pin is
MAX_SHARE = 0.12      # of the pin's shorter side
DEFAULT_SHARE = 0.05

# the last five fields only matter for a custom pattern image: how it repeats ("tile", "mirror"
# or "fill"), how far it is moved across / down (fractions of one repeat), its turn in degrees
# and how much the ring colour tints it (0 to 1).
Ring = namedtuple("Ring", "mm col style image scale col2 mode ox oy rot tint",
                  defaults=("solid", None, 0.3, None, "tile", 0.0, 0.0, 0.0, 0.0))
PATTERN_MODES = (("tile", "Repeat"), ("mirror", "Mirror"), ("fill", "Fill"))

STYLES = (("solid", "Solid"), ("duo", "Duo"), ("double", "Double"), ("gradient", "Ombre"),
          ("dots", "Polka"), ("stitch", "Stitch"), ("foil", "Foil"), ("pattern", "Mine"))
STYLE_NAMES = dict(STYLES)
TWO_COLOUR = ("duo", "double", "dots", "stitch")      # styles that also use the accent colour
THICKER = {"duo": 1.8, "double": 2.2, "dots": 2.4, "stitch": 2.4}   # smallest sensible mm

# what an older canvas file called its materials, as today's styles
_OLD = {"flat": "solid", "glossy": "solid", "satin": "solid", "pearl": "solid",
        "grain": "solid", "frost": "solid", "metallic": "foil", "gradient": "gradient"}

CREAM, INK = (250, 245, 236), (30, 32, 38)
FOILS = (("Gold", (218, 168, 62)), ("Rose gold", (214, 140, 128)),
         ("Silver", (176, 184, 196)), ("Champagne", (226, 200, 150)))


# ---- thickness ----------------------------------------------------------------------

def limits(fw, fh, style=None):
    """(smallest, largest) ring thickness in mm for a finished pin ``fw`` x ``fh`` mm. Styles
    made of several lines need a little more room to stay crisp."""
    short = min(fw, fh)
    hi = max(MIN_MM + 0.4, min(MAX_MM, short * MAX_SHARE))
    lo = min(THICKER.get(style, MIN_MM), hi - 0.3)
    return lo, round(hi, 2)


def default_mm(fw, fh, share=1.0, style=None):
    """A good-looking starting thickness: about 5 % of the pin's shorter side."""
    lo, hi = limits(fw, fh, style)
    return round(max(lo, min(hi, min(fw, fh) * DEFAULT_SHARE * share)), 2)


def clamp(mm, fw, fh, style=None):
    """``mm`` held inside the allowed range for this pin (and style)."""
    lo, hi = limits(fw, fh, style)
    return max(lo, min(hi, float(mm)))


def presets(fw, fh, style=None):
    """Thin / Medium / Bold thicknesses (mm) for this pin."""
    lo, hi = limits(fw, fh, style)
    short = min(fw, fh)
    return [round(max(lo, min(hi, short * share)), 2) for share in (0.035, 0.055, 0.085)]


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


def accent_for(style, col):
    """The accent colour a style uses when none was chosen: cream or ink for contrast."""
    if style == "double":
        return tuple(col)
    return CREAM if _lum(col) < 0.62 else INK


def accent(r):
    """The ring's accent colour (the chosen one, else the automatic one)."""
    return tuple(r.col2) if r.col2 else accent_for(r.style, r.col)


def key(r):
    """A hashable summary of a ring, used to cache pictures."""
    if r is None:
        return None
    r = as_ring(r)
    return (round(r.mm, 2), tuple(r.col), r.style, r.image or "", round(r.scale, 2),
            tuple(r.col2) if r.col2 else None,
            (r.mode, round(r.ox, 3), round(r.oy, 3), round(r.rot, 1), round(r.tint, 2))
            if r.image else None)


def to_saved(r, base=None):
    """A ring as plain data for a canvas file. ``base`` (the canvas's folder) lets the pattern
    image also be stored by relative path.
    """
    r = as_ring(r)
    d = {"mm": r.mm, "color": to_hex(r.col), "style": r.style}
    if r.col2:
        d["color2"] = to_hex(r.col2)
    if r.image:
        d["image"], d["scale"] = r.image, r.scale
        d["pattern"] = {"mode": r.mode, "ox": r.ox, "oy": r.oy, "rot": r.rot, "tint": r.tint}
        if base:
            try:
                d["rel"] = os.path.relpath(r.image, base)
            except ValueError:
                pass
    return d


def from_saved(data, base=None):
    """The ring from saved data (older files too), or None if unreadable."""
    try:
        if isinstance(data, (list, tuple)):
            return Ring(float(data[0]), from_hex(str(data[1])))
        st = data.get("style") or _OLD.get(data.get("material"), "solid")
        st = st if st in STYLE_NAMES else "solid"
        image = None
        for cand in (data.get("image") or "",
                     os.path.join(base, data["rel"]) if base and data.get("rel") else ""):
            if cand and os.path.isfile(cand):
                image = os.path.abspath(cand)
                break
        if st == "pattern" and not image:
            st = "solid"
        col2 = from_hex(str(data["color2"])) if data.get("color2") else None
        p = data.get("pattern") or {}
        mode = p.get("mode") if p.get("mode") in dict(PATTERN_MODES) else "tile"
        return Ring(float(data["mm"]), from_hex(str(data["color"])), st, image,
                    float(data.get("scale", 0.3)), col2, mode, float(p.get("ox", 0)),
                    float(p.get("oy", 0)), float(p.get("rot", 0)), float(p.get("tint", 0)))
    except (TypeError, ValueError, IndexError, KeyError, AttributeError):
        return None


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _mul(c, f):
    return tuple(max(0, min(255, round(v * f))) for v in c)


def _lum(col):
    """Perceived brightness 0..1."""
    r, g, b = (v / 255 for v in col)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _hls(col, h=None, l=None, s=None, dh=0.0):
    """``col`` with its hue / lightness / saturation replaced (or the hue shifted by ``dh``)."""
    hh, ll, ss = colorsys.rgb_to_hls(*(v / 255 for v in col))
    hh = (hh + dh) % 1 if h is None else h
    ll = ll if l is None else l
    ss = ss if s is None else s
    return tuple(round(v * 255) for v in colorsys.hls_to_rgb(hh, ll, ss))


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


def brightness(img):
    """How light a picture is overall, 0 (black) to 1 (white)."""
    small = img.convert("L")
    small.thumbnail((48, 48))
    px = list(small.getdata())
    return sum(px) / (255 * max(1, len(px)))


# ---- recommendations ----------------------------------------------------------------

def colourways(img):
    """Ready-made colours for the picture: ``(from_picture, classics)``. Each is a list of
    (name, (r, g, b)). The first picture colour is the best match.
    """
    pal = dominant_colours(img, 6)
    base = pal[0]
    mine = [("Match", base)]
    mine.append(("Pop", tidy(_hls(base, dh=0.5, l=0.52, s=0.7))))
    mine.append(("Soft", _hls(base, l=0.86, s=min(0.7, colorsys.rgb_to_hls(
        *(v / 255 for v in base))[2]))))
    mine.append(("Deep", _hls(base, l=0.24)))
    for extra in pal[1:3]:
        mine.append(("Also", extra))
    classics = [("Cream", CREAM), ("White", (255, 255, 255)), ("Ink", INK)] + [
        (n, c) for n, c in FOILS[:3]]
    return mine, classics


def recommend(img, fw, fh):
    """The best rings for this picture, best first: a list of (label, Ring)."""
    mine, _classics = colourways(img)
    base = dict(mine)["Match"]
    light = brightness(img)
    hue = colorsys.rgb_to_hls(*(v / 255 for v in base))[0]
    deep, soft = dict(mine)["Deep"], dict(mine)["Soft"]
    ring = lambda style, col, col2=None, share=1.0: Ring(
        default_mm(fw, fh, share, style), col, style, None, 0.3, col2)
    clean = ring("double", INK if light > 0.62 else CREAM, base)
    picks = [
        ("Match", ring("solid", base)),
        ("Clean", clean),
        ("Duo", ring("duo", deep, soft)),
        ("Ombre", ring("gradient", base, None, 1.2)),
        ("Stitched", ring("stitch", soft if light < 0.5 else base, CREAM
                          if light < 0.5 else CREAM, 1.2)),
        ("Foil", ring("foil", FOILS[2][1] if 0.45 < hue < 0.72 else FOILS[0][1], None, 1.1)),
    ]
    if light < 0.3 or light > 0.82:       # very dark / very light picture: a clean frame first
        picks.insert(0, picks.pop(1))
    return picks


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


# ---- painting the styles ------------------------------------------------------------

def _solid(size, col):
    return Image.new("RGB", size, tuple(col))


def _wedges(size, cx, cy, n, colour_at):
    """A picture of ``n`` thin slices around (cx, cy), each filled by ``colour_at(0..1)``."""
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


def _lit(img, hmap, sigma, strength):
    """Give the foil a soft rounded sheen (the only style with any lighting)."""
    k = max(0.06, 6.0 / max(1.0, sigma))
    e = hmap.filter(ImageFilter.Kernel((3, 3), (-1, -1, 0, -1, 0, 1, 0, 1, 1), k, 128))
    hi = e.point(lambda v: int(max(0, min(255, (v - 128) * 2)) * strength))
    lo = e.point(lambda v: int(max(0, min(255, (128 - v) * 2)) * strength))
    img = Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, hi)
    return Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, lo)


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


def _tiled(r, ctx):
    """The pattern image laid over the whole area, repeated, mirrored or enlarged to fill, moved,
    turned and tinted as the ring says (None if the image cannot be read).
    """
    size = ctx["size"]
    w, hh = size
    try:
        t = _tile_image(r.image)
    except (OSError, ValueError):
        return None
    iw, ih = t.size
    if r.mode == "fill":              # one big picture: this size covers the pin (1x to 3x)
        zoom = 1 + (r.scale - 0.08) / 0.72 * 2
        tp = max(8, int(max(w, hh * iw / ih) * zoom))
    else:
        tp = max(8, int(r.scale * min(ctx["fw"], ctx["fh"]) * ctx["px"]))
    t = t.resize((tp, max(1, round(tp * ih / iw))), Image.LANCZOS)
    if r.mode == "mirror":            # 2 x 2 mirrored: no hard seams between repeats
        m = Image.new("RGB", (t.size[0] * 2, t.size[1] * 2))
        m.paste(t, (0, 0))
        m.paste(ImageOps.mirror(t), (t.size[0], 0))
        m.paste(ImageOps.flip(t), (0, t.size[1]))
        m.paste(ImageOps.flip(ImageOps.mirror(t)), t.size)
        t = m
    tw, th = t.size
    diag = int(math.hypot(w, hh)) + 4      # big enough to turn and still cover the area
    out = Image.new("RGB", (diag, diag))
    x0 = (int(diag / 2 - tw / 2 + r.ox * tw)) % tw - tw
    y0 = (int(diag / 2 - th / 2 + r.oy * th)) % th - th
    for y in range(y0, diag, th):
        for x in range(x0, diag, tw):
            out.paste(t, (x, y))
    if r.rot:
        out = out.rotate(-r.rot, Image.BICUBIC)
    left, top = (diag - w) // 2, (diag - hh) // 2
    out = out.crop((left, top, left + w, top + hh))
    if r.tint > 0:
        out = Image.blend(out, _solid(size, tuple(r.col)), min(1.0, r.tint))
    return out


def _ombre(r, ctx):
    """A smooth two-colour gradient across the ring (the second colour is a pretty shift of
    the first unless one was chosen)."""
    w, hh = ctx["size"]
    other = tuple(r.col2) if r.col2 else _hls(r.col, dh=0.07, l=min(0.9, colorsys.rgb_to_hls(
        *(v / 255 for v in r.col))[1] + 0.16))
    side = int(math.hypot(w, hh) * 1.2) + 2
    ramp = Image.linear_gradient("L").resize((side, side), Image.BILINEAR)
    ramp = ramp.rotate(45, resample=Image.BICUBIC)
    x0, y0 = (side - w) // 2, (side - hh) // 2
    ramp = ramp.crop((x0, y0, x0 + w, y0 + hh))
    return Image.composite(Image.new("RGB", ctx["size"], other),
                           Image.new("RGB", ctx["size"], tuple(r.col)), ramp)


def _foil(r, ctx):
    """A gold / silver / rose-foil look: a soft sweep of light and dark in the colour."""
    col = r.col
    dark, light = _mul(col, 0.62), _mix(col, (255, 255, 255), 0.62)

    def at(u):
        v = 0.5 + 0.5 * math.cos(2 * math.pi * 2 * u + 0.7)
        v2 = 0.5 + 0.5 * math.cos(2 * math.pi * 3 * u + 2.1)
        return _mix(_mix(dark, col, v), light, (max(0, v2 - 0.45) / 0.55) ** 2 * 0.7)
    return _wedges(ctx["size"], ctx["cx"], ctx["cy"], 360, at)


def _outline_px(shape, w_mm, h_mm, ctx, ss):
    """The outline of a ``w_mm`` x ``h_mm`` version of the pin, as pixel points (at ``ss``x)."""
    pts = shapes.outline(shape, max(0.5, w_mm), max(0.5, h_mm))
    return [((ctx["cx"] + x * ctx["sx"]) * ss, (ctx["cy"] + y * ctx["sy"]) * ss)
            for x, y in pts]


def _along(pts, n):
    """``n`` points evenly spaced along a closed outline, with the direction at each."""
    loop = pts + pts[:1]
    seg = [math.dist(a, b) for a, b in zip(loop, loop[1:])]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(n):
        target = total * k / n
        while i < len(seg) - 1 and acc + seg[i] < target:
            acc += seg[i]
            i += 1
        t = (target - acc) / seg[i] if seg[i] else 0
        (x0, y0), (x1, y1) = loop[i], loop[i + 1]
        out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    return out, total


def _polka(img, r, ctx, ss):
    """Cream dots in a row down the middle of the band."""
    d = ImageDraw.Draw(img)
    mid = _outline_px(ctx["shape"], ctx["fw"] - ctx["mm"], ctx["fh"] - ctx["mm"], ctx, ss)
    px = ctx["px"] * ss
    rad = ctx["mm"] * 0.2 * px
    n = max(8, round(_along(mid, 4)[1] / (rad * 4.2)))
    col = accent(r)
    for x, y in _along(mid, n)[0]:
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=col)


def _stitch(img, r, ctx, ss):
    """A dashed line down the middle of the band, like embroidery."""
    d = ImageDraw.Draw(img)
    mid = _outline_px(ctx["shape"], ctx["fw"] - ctx["mm"], ctx["fh"] - ctx["mm"], ctx, ss)
    px = ctx["px"] * ss
    width = max(2.0, ctx["mm"] * 0.13 * px)
    dash = ctx["mm"] * 0.62 * px
    total = _along(mid, 4)[1]
    n = max(8, round(total / (dash * 1.75)))
    pts, _t = _along(mid, n * 8)
    col = accent(r)
    per = 8
    for k in range(n):
        seg = pts[k * per:k * per + 5]           # 4 of every 8 steps are the dash
        if len(seg) >= 2:
            d.line(seg, fill=col, width=round(width), joint="curve")
            for x, y in (seg[0], seg[-1]):
                d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=col)


_layers = {}


def layer(ring, shape, fw, fh, size, sx, sy, cx, cy, ss=2):
    """Paint a ring. Returns (surface, inside): ``surface`` is an RGB picture of ``size`` pixels
    showing the ring (it covers everything, the mask picks the ring out) and ``inside`` is the
    'L' mask that is white where the pin's picture shows.
    """
    r = as_ring(ring)
    style = r.style if r.style != "pattern" or r.image else "solid"
    mm = clamp(r.mm, fw, fh, style)
    ck = (key(r._replace(mm=mm)), shape, round(fw, 2), round(fh, 2), size, round(sx, 3),
          round(sy, 3), round(cx, 1), round(cy, 1))
    hit = _layers.get(ck)
    if hit is not None:
        return hit
    px = (sx + sy) / 2
    ctx = dict(size=size, cx=cx, cy=cy, sx=sx, sy=sy, px=px, fw=fw, fh=fh, mm=mm, shape=shape)

    def inset(k):
        return mask(shape, fw, fh, k, size, sx, sy, cx, cy, ss)

    inside = inset(mm)
    col = tuple(r.col)
    surface = None
    if style == "pattern":
        surface = _tiled(r, ctx)
    if style == "gradient":
        surface = _ombre(r, ctx)
    elif style == "foil":
        surface = _foil(r, ctx)
        band = ImageChops.subtract(inset(0), inside)
        sigma = max(1.2, mm * px * 0.28)
        surface = _lit(surface, band.filter(ImageFilter.GaussianBlur(sigma)), sigma, 0.3)
    elif style == "duo":
        surface = Image.composite(_solid(size, accent(r)), _solid(size, col), inset(mm * 0.6))
    elif style == "double":
        # a wide band, a gap where the picture shows through, then a fine line
        surface = Image.composite(_solid(size, accent(r)), _solid(size, col), inset(mm * 0.8))
        gap = ImageChops.subtract(inset(mm * 0.52), inset(mm * 0.8))
        inside = ImageChops.lighter(inside, gap)
    elif style in ("dots", "stitch"):
        big = Image.new("RGB", (size[0] * ss, size[1] * ss), col)
        (_polka if style == "dots" else _stitch)(big, r, ctx, ss)
        surface = big.resize(size, Image.LANCZOS)
    if surface is None:
        surface = _solid(size, col)
    if len(_layers) > 12:
        _layers.clear()
    _layers[ck] = (surface, inside)
    return surface, inside


def apply(img, ring, shape, fw, fh, w_mm, h_mm):
    """Paint ``ring`` onto ``img``, a picture of the paper-shape box ``w_mm`` x ``h_mm``."""
    w, h = img.size
    surface, inside = layer(ring, shape, fw, fh, (w, h), w / w_mm, h / h_mm, w / 2, h / 2)
    return Image.composite(img.convert("RGB"), surface, inside)
