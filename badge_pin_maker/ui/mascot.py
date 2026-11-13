"""Ozzie, the hamster mascot, in three versions: Ozzie, Mr Ozzie and Ms Ozzie.

The pictures are ordinary image files in the assets/ folder. They are found by name, whatever
the capital letters, spaces or underscores: ozzie.png, MrOzzie.png, "ms ozzie.png"... A picture
with a flat background (a cream square, say) is cut out automatically, so the hamster sits
cleanly on every theme.
"""

import os
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageTk

from ..paths import asset_path

# (id, name shown, one cute line about it)
MASCOTS = [
    ("ozzie", "Ozzie", "Our fluffy original, always up for cuddles!"),
    ("mr_ozzie", "Mr Ozzie", "Bow tie on, whiskers neat and ever so polite!"),
    ("ms_ozzie", "Ms Ozzie", "A pretty bow and a little sparkle of charm!"),
]
DEFAULT = "ozzie"
INFO = {mid: (name, note) for mid, name, note in MASCOTS}
EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg")

current = DEFAULT                      # the mascot in use (the app sets it from the settings)
_cache = {}                            # id -> (file, modified time, cut-out image)


def set_current(mid):
    """Use ``mid`` as the mascot (an unknown id means the default one)."""
    global current
    current = mid if mid in INFO else DEFAULT


def _key(text):
    """A name with only its lower-case letters, so "Mr_Ozzie", "MrOzzie" and "mr ozzie" match."""
    return re.sub(r"[^a-z]", "", text.lower())


def find_file(mid):
    """The picture file for a mascot in assets/, or None if there isn't one."""
    folder = os.path.dirname(asset_path("x"))
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for ext in EXTENSIONS:                          # .png wins over .jpg
        for name in names:
            stem, e = os.path.splitext(name)
            if e.lower() == ext and _key(stem) == _key(mid):
                return os.path.join(folder, name)
    return None


def available():
    """True if at least one mascot picture is in the assets folder."""
    return any(find_file(mid) for mid in INFO)


def _cut_out(im):
    """Make a flat background transparent. Pictures that already have transparency are left
    alone. The background is whatever colour fills the corners; only the part connected to the
    edge goes, so light colours inside the hamster stay.
    """
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema()[0] < 250:
        return im
    rgb = im.convert("RGB")
    w, h = rgb.size
    corners = [rgb.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    bg = corners[0]
    if any(max(abs(c[i] - bg[i]) for i in range(3)) > 28 for c in corners):
        return im                                    # not a flat background
    # the flood fill is slow in pure Python, so it runs on a small copy (about 256 px) and the
    # result is scaled back up and sharpened again; that is plenty for a soft cut-out edge
    k = max(1, max(w, h) // 256)
    sw, sh = max(1, w // k), max(1, h // k)
    small = rgb.resize((sw, sh), Image.BILINEAR)
    diff = ImageChops.difference(small, Image.new("RGB", (sw, sh), bg)).convert("L")
    mask = diff.point(lambda v: 255 if v > 26 else 0)        # 255 = part of the picture
    edge = [(x, 0) for x in range(sw)] + [(x, sh - 1) for x in range(sw)] \
        + [(0, y) for y in range(sh)] + [(sw - 1, y) for y in range(sh)]
    for p in edge:
        if mask.getpixel(p) == 0:
            ImageDraw.floodfill(mask, p, 128)        # the background reachable from the edge
    alpha = mask.point(lambda v: 0 if v == 128 else 255)
    if k > 1:
        alpha = alpha.resize((w, h), Image.BICUBIC).point(
            lambda v: max(0, min(255, (v - 96) * 4)))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(alpha)
    return im


def _load_cutout(path, stamp):
    """The cut-out of the picture at ``path``. It is made once and kept in a cache folder (named
    after the file's date and size, so a changed picture is cut out again); later starts just
    read it back, which is much quicker than cutting it out.
    """
    from .. import settings
    folder = os.path.join(settings.DATA_DIR, "cache")
    key = f"{_key(os.path.splitext(os.path.basename(path))[0])}-{int(stamp)}-" \
          f"{os.path.getsize(path)}.png"
    kept = os.path.join(folder, key)
    try:
        if os.path.exists(kept):
            im = Image.open(kept)
            im.load()
            return im
    except (OSError, ValueError):
        pass
    im = Image.open(path)
    im.thumbnail((1024, 1024), Image.LANCZOS)
    im = _cut_out(im)
    try:
        os.makedirs(folder, exist_ok=True)
        for old in os.listdir(folder):                 # drop out-of-date versions of this one
            if old.split("-")[0] == key.split("-")[0] and old != key:
                os.remove(os.path.join(folder, old))
        im.save(kept)
    except OSError:
        pass
    return im


def image(mid=None):
    """The cut-out picture of a mascot (the one in use by default) as a PIL image, or None."""
    mid = mid or current
    path = find_file(mid)
    if path is None:
        return None
    try:
        stamp = os.path.getmtime(path)
        hit = _cache.get(mid)
        if hit and hit[0] == path and hit[1] == stamp:
            return hit[2]
        im = _load_cutout(path, stamp)
        _cache[mid] = (path, stamp, im)
        return im
    except (OSError, ValueError):
        return None


def square(mid, size, pad=0.04):
    """The mascot as a transparent square picture ``size`` pixels wide (trimmed to the
    hamster, never cropped, a little space around it), or None.
    """
    im = image(mid)
    if im is None:
        return None
    box = im.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
    if box:
        im = im.crop(box)
    inner = max(1, round(size * (1 - 2 * pad)))
    im = ImageOps.contain(im, (inner, inner), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return out


def photo(mid, size):
    """A Tk picture of a mascot ``size`` pixels square, or None. Keep a reference to it."""
    im = square(mid, size)
    return ImageTk.PhotoImage(im) if im is not None else None
