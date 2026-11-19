"""The coloured ring around a pin's picture.

A ring is a border drawn just inside the pin's finished edge (the safe-area line). It follows
the pin's shape, so it is a circle on a round pin, a heart on a heart pin, and so on. Anything
outside the ring (the strip that folds behind the pin) takes the ring's colour too, so the
edge of the finished pin is one clean colour.

A ring is stored on an Art as ``(thickness_mm, (r, g, b))`` or None for no ring.
"""

import colorsys

from PIL import Image, ImageDraw

from . import shapes

MIN_MM = 1.2          # thinner than this vanishes in print and when the pin is pressed
MAX_MM = 6.0          # an absolute cap, however big the pin is
MAX_SHARE = 0.12      # of the pin's shorter side
DEFAULT_SHARE = 0.05


def limits(fw, fh):
    """(smallest, largest) ring thickness in mm for a finished pin ``fw`` x ``fh`` mm."""
    short = min(fw, fh)
    hi = max(MIN_MM + 0.4, min(MAX_MM, short * MAX_SHARE))
    return MIN_MM, round(hi, 2)


def default_mm(fw, fh):
    """A good-looking starting thickness: about 5 % of the pin's shorter side."""
    lo, hi = limits(fw, fh)
    return round(max(lo, min(hi, min(fw, fh) * DEFAULT_SHARE)), 2)


def clamp(mm, fw, fh):
    """``mm`` held inside the allowed range for this pin."""
    lo, hi = limits(fw, fh)
    return max(lo, min(hi, float(mm)))


def mask(shape, fw, fh, mm, size, sx, sy, cx, cy, ss=3):
    """A smooth 'L' mask of ``size`` pixels: white inside the ring (the picture shows), black
    in the ring and beyond. ``sx`` / ``sy`` are pixels per mm and (cx, cy) the pin's centre
    in pixels.
    """
    w, h = size
    iw, ih = fw - 2 * mm, fh - 2 * mm
    big = Image.new("L", (w * ss, h * ss), 0)
    if iw > 0.5 and ih > 0.5:
        pts = shapes.outline(shape, iw, ih)
        ImageDraw.Draw(big).polygon(
            [((cx + x * sx) * ss, (cy + y * sy) * ss) for x, y in pts], fill=255)
    return big.resize((w, h), Image.LANCZOS)


def apply(img, ring, shape, fw, fh, w_mm, h_mm):
    """Paint ``ring`` onto ``img``, a picture of the paper-shape box ``w_mm`` x ``h_mm``."""
    mm, col = ring
    mm = clamp(mm, fw, fh)
    w, h = img.size
    m = mask(shape, fw, fh, mm, (w, h), w / w_mm, h / h_mm, w / 2, h / 2)
    return Image.composite(img, Image.new("RGB", img.size, tuple(col)), m)


def to_hex(col):
    """(r, g, b) -> '#rrggbb'."""
    return "#%02x%02x%02x" % tuple(int(v) for v in col)


def from_hex(text):
    """'#rrggbb' -> (r, g, b)."""
    text = text.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


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
