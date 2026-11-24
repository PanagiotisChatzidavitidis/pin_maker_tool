"""Simple picture filters that behave on paper.

Every filter is a gentle colour or tone change (no blur, grain or effects that go muddy in
print) and has an intensity from 0 to 1 that fades it in over the original. Whatever the
filter, the result keeps its darkest and lightest tones inside what an inkjet or laser
printer can hold, so shadows do not clog and highlights do not vanish into the paper.

A filter on a pin is ``(name, amount)`` or ``None``. Filters are applied to the cropped
picture (``apply``), before the ring is painted.
"""

import random
from collections import namedtuple
from functools import lru_cache

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat

Filter = namedtuple("Filter", "name amount")

LO, HI = 5, 250          # the tones kept on every picture, so nothing prints as a solid black


def _lut(fn):
    return [max(0, min(255, round(fn(v)))) for v in range(256)]


def _tone(img, lo=0, hi=255, gamma=1.0):
    """Lift the blacks to ``lo``, tame the whites to ``hi``; gamma below 1 brightens."""
    lut = _lut(lambda v: lo + (hi - lo) * (v / 255) ** gamma)
    return img.point(lut * (3 if img.mode == "RGB" else 1))


def _tint(img, r=1.0, g=1.0, b=1.0):
    """Scale the red, green and blue channels (a warm or cool cast)."""
    return img.point(_lut(lambda v: v * r) + _lut(lambda v: v * g) + _lut(lambda v: v * b))


def _sat(img, f):
    return ImageEnhance.Color(img).enhance(f)


def _con(img, f):
    return ImageEnhance.Contrast(img).enhance(f)


def _bri(img, f):
    return ImageEnhance.Brightness(img).enhance(f)


def _duo(img, dark, light, mid=None, cutoff=1, contrast=1.0):
    """Two (or three) ink colours: dark tones become ``dark``, light tones ``light``."""
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=cutoff)
    if contrast != 1.0:
        g = _con(g, contrast)
    return ImageOps.colorize(g, dark, light, mid=mid)


def _mono(img):
    return ImageOps.grayscale(img).convert("RGB")


@lru_cache(maxsize=8)
def _noise(cells_w, cells_h):
    """Fixed (seeded) noise, 128 on average, so a pin looks the same every time it is drawn."""
    rnd = random.Random(20260)
    a = Image.frombytes("L", (cells_w, cells_h), rnd.randbytes(cells_w * cells_h))
    b = Image.frombytes("L", (cells_w, cells_h), rnd.randbytes(cells_w * cells_h))
    return ImageChops.add(a, b, scale=2.0)       # two uniforms averaged: a softer bell curve


def _grain(img, amount, cells=360):
    """Film grain: ``cells`` grains across the picture whatever its pixel size, so it is the
    same size on screen and on paper (about a printer dot at 32 mm), with ``amount`` 0 to 255
    of swing.
    """
    w, h = img.size
    ch = max(8, round(cells * h / w))
    g = _noise(cells, ch).resize((w, h), Image.BICUBIC)
    k = amount / 60.0                             # the noise itself swings about +-60
    g = g.point(_lut(lambda v: 128 + (v - 128) * k))
    return ImageChops.add(img, g.convert("RGB"), scale=1.0, offset=-128)


def _split(img, shadow, light):
    """Tint the shadows and the highlights differently: shadow / light are (r, g, b) pushes."""
    chans = []
    for c in range(3):
        chans += _lut(lambda v, c=c: v + shadow[c] * (1 - v / 255) ** 2 + light[c] * (v / 255) ** 2)
    return img.point(chans)


# ---- the filters: name -> function that turns a picture into the full-strength result -----
def _warm(i):
    return _sat(_tint(i, 1.07, 1.0, 0.90), 1.08)


def _cool(i):
    return _sat(_tint(i, 0.92, 1.0, 1.08), 1.05)


def _vivid(i):
    return _con(_sat(i, 1.38), 1.07)


def _pop(i):                          # the print booster: paper is duller than a screen
    return _bri(_con(_sat(i, 1.18), 1.10), 1.03)


def _golden(i):
    return _sat(_tone(_tint(i, 1.10, 1.03, 0.84), 0, 255, 0.92), 1.1)


def _soft(i):
    return _tone(_sat(i, 0.78), 20, 255, 0.9)


def _matte(i):
    return _con(_tone(i, 26, 232), 0.96)


def _fade(i):
    return _tint(_tone(_sat(i, 0.8), 24, 236), 1.03, 1.0, 0.95)


def _mono_f(i):
    return _tone(_mono(i), 8, 248)


def _noir(i):
    g = _con(ImageOps.autocontrast(ImageOps.grayscale(i), cutoff=2), 1.3)
    return _tone(g.convert("RGB"), 10, 246)


def _sepia(i):
    return _duo(i, (38, 22, 10), (252, 240, 214))


def _blush(i):
    return _duo(i, (96, 30, 62), (255, 238, 238))


def _sage(i):
    return _duo(i, (34, 58, 46), (240, 245, 228))


def _ocean(i):
    return _duo(i, (14, 40, 88), (228, 241, 251))


def _lilac(i):
    return _duo(i, (58, 36, 100), (246, 238, 255))


def _grain35(i):                      # classic 35 mm: warm, a touch faded, visible grain
    return _grain(_tone(_sat(_tint(i, 1.04, 1.0, 0.94), 0.92), 10, 246), 24)


def _analog(i):                       # faded, warm, soft: an old print in a shoebox
    return _grain(_tint(_tone(_sat(i, 0.85), 22, 238), 1.06, 1.0, 0.88), 12)


def _finegrain(i):                    # fine, even grain and nothing else
    return _grain(_con(i, 1.04), 14, 520)


def _cinema(i):                       # teal shadows, warm highlights, firm contrast
    return _grain(_con(_sat(_split(i, (-8, 2, 14), (16, 4, -12)), 0.92), 1.1), 16, 420)


def _polaroid(i):                     # instant film: creamy lift, slightly green shadows
    return _grain(_tint(_tone(_con(i, 0.92), 28, 240, 0.95), 1.04, 1.02, 0.92), 10, 300)


def _silver(i):                       # black and white film, punchy with coarse grain
    g = _con(ImageOps.autocontrast(ImageOps.grayscale(i), cutoff=1), 1.2).convert("RGB")
    return _grain(_tone(g, 10, 244), 26, 330)


def _dream(i):                        # soft glow: highlights bloom over the picture
    w = i.size[0]
    glow = i.filter(ImageFilter.GaussianBlur(max(2, w / 55)))
    return _tone(ImageChops.screen(i, _bri(glow, 0.8)), 8, 250)


def _disposable(i):                   # flash-on-a-disposable: punchy, warm, coarse grain
    return _grain(_tint(_con(_sat(i, 1.22), 1.12), 1.05, 1.0, 0.94), 20, 280)


# id, label, group, function, the intensity it starts at
_ALL = (
    ("grain35", "35mm Grain", "Aesthetic", _grain35, 0.8),
    ("analog", "Analog", "Aesthetic", _analog, 0.8),
    ("finegrain", "Fine Grain", "Aesthetic", _finegrain, 0.9),
    ("cinema", "Cinematic", "Aesthetic", _cinema, 0.8),
    ("polaroid", "Polaroid", "Aesthetic", _polaroid, 0.8),
    ("silver", "Silver", "Aesthetic", _silver, 0.9),
    ("dream", "Dreamy", "Aesthetic", _dream, 0.7),
    ("disposable", "Disposable", "Aesthetic", _disposable, 0.8),
    ("pop", "Pop", "Colour", _pop, 0.6),
    ("vivid", "Vivid", "Colour", _vivid, 0.6),
    ("warm", "Warm", "Colour", _warm, 0.7),
    ("cool", "Cool", "Colour", _cool, 0.7),
    ("soft", "Soft", "Soft and glow", _soft, 0.8),
    ("matte", "Matte", "Soft and glow", _matte, 0.8),
    ("fade", "Fade", "Soft and glow", _fade, 0.8),
    ("golden", "Golden", "Soft and glow", _golden, 0.7),
    ("mono", "Mono", "Black and white", _mono_f, 1.0),
    ("noir", "Noir", "Black and white", _noir, 1.0),
    ("sepia", "Sepia", "Black and white", _sepia, 1.0),
    ("blush", "Blush", "Duotone", _blush, 1.0),
    ("sage", "Sage", "Duotone", _sage, 1.0),
    ("ocean", "Ocean", "Duotone", _ocean, 1.0),
    ("lilac", "Lilac", "Duotone", _lilac, 1.0),
)
FUNCS = {n: f for n, _l, _g, f, _d in _ALL}
NAMES = {n: l for n, l, _g, _f, _d in _ALL}
DEFAULTS = {n: d for n, _l, _g, _f, d in _ALL}
GROUPS = tuple(dict.fromkeys(g for _n, _l, g, _f, _d in _ALL))


def in_group(group):
    """[(id, label)] of one group, in display order."""
    return [(n, l) for n, l, g, _f, _d in _ALL if g == group]


def as_filter(f):
    """A ``Filter`` from a tuple / list / None; None for an unknown name or a zero amount."""
    if not f:
        return None
    try:
        name, amount = f[0], float(f[1])
    except (TypeError, ValueError, IndexError):
        return None
    if name not in FUNCS or amount <= 0.004:
        return None
    return Filter(name, min(1.0, amount))


def key(f):
    """A hashable summary for caches (None when there is no filter)."""
    f = as_filter(f)
    return None if f is None else (f.name, round(f.amount, 2))


def label(f):
    f = as_filter(f)
    return "" if f is None else NAMES[f.name]


def to_saved(f):
    f = as_filter(f)
    return {"name": f.name, "amount": round(f.amount, 3)} if f else None


def from_saved(data):
    if not isinstance(data, dict):
        return None
    return as_filter((data.get("name"), data.get("amount", 1.0)))


def apply(img, f):
    """``img`` with the filter on (the same picture back when there is no filter)."""
    f = as_filter(f)
    if f is None:
        return img
    src = img.convert("RGB")
    out = FUNCS[f.name](src)
    if out.mode != "RGB":
        out = out.convert("RGB")
    if f.amount < 0.996:
        out = Image.blend(src, out, f.amount)
    return _tone(out, LO, HI)


def recommend(img):
    """Three filters that suit this picture: [(id, amount)], best first. Dark pictures are
    lifted, bright ones get a matte finish, very colourful ones are calmed (they print duller
    anyway), washed-out ones get a print boost, and so on.
    """
    small = img.convert("RGB").resize((48, 48))
    r, g, b = ImageStat.Stat(small).mean
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    sat = ImageStat.Stat(small.convert("HSV")).mean[1] / 255
    warmth = r - b
    if lum < 0.38:
        order = ["cinema", "soft", "golden"]
    elif lum > 0.70:
        order = ["matte", "dream", "cool"]
    elif sat > 0.55:
        order = ["matte", "analog", "finegrain"]
    elif sat < 0.18:
        order = ["silver", "pop", "grain35"]
    elif warmth > 25:
        order = ["cinema", "matte", "cool"]
    elif warmth < -15:
        order = ["analog", "warm", "polaroid"]
    else:
        order = ["grain35", "pop", "polaroid"]
    return [(n, DEFAULTS[n]) for n in order]
