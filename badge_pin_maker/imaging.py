"""Images, and the maths that places them inside a pin circle.

A Source is a loaded picture. An Art is one pin's view of a Source (zoom, centre point,
rotation). render_art() turns an Art into the finished square image for a pin of a given
size. Only Pillow is used here; no windows are involved.
"""

import math
import os

from PIL import Image, ImageOps


AFFINE = getattr(Image, "Transform", Image).AFFINE


def base_crop(size):
    """Side (source px) of the square 'cover' crop at zoom 1."""
    return min(size)


def ppi_for(size, zoom, d_mm):
    """Effective print resolution (pixels per inch) of an image of ``size`` pixels, at ``zoom``,
    on a pin ``d_mm`` wide.
    """
    return base_crop(size) / zoom / (d_mm / 25.4)


class Source:
    """A loaded image: full-res for the PDF, small copy for fast previews."""
    def __init__(self, img, path=""):
        """Keep the full-size picture (for printing) plus a small copy that keeps previews
        fast.
        """
        self.full = img
        self.path = path
        # nothing ever changes these pictures in place, so a small one that needs no shrinking
        # can simply be the full one (no copy)
        w, h = img.size
        scale = 1200 / max(w, h)
        self.small = img if scale >= 1 else img.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS, reducing_gap=2.0)
        self._mips = {0: self.small}
        self._bg = None
        self._flips = {}

    @property
    def bg(self):
        """The picture's background colour (an RGB tuple), found once from its edges. It fills
        any part of a pin the picture doesn't reach, so there is never a stray white gap.
        """
        if self._bg is None:
            self._bg = edge_colour(self.small)
        return self._bg

    def flipped(self, img):
        """``img`` (the full or a small copy of this picture) mirrored left to right. Made once
        per copy and kept, so a flipped pin costs nothing extra to redraw.
        """
        pic = self._flips.get(id(img))
        if pic is None:
            pic = self._flips[id(img)] = ImageOps.mirror(img)
        return pic

    def mip(self, level):
        """The small picture shrunk ``2 ** level`` times (made once). Drawing a tiny preview
        from one of these is many times quicker than from the 1200 px picture.
        """
        level = max(0, min(level, 4))
        while level > 0 and min(self.small.size) // (2 ** level) < 96:
            level -= 1                       # never so small that previews would look soft
        pic = self._mips.get(level)
        if pic is None:
            pic = self._mips[level] = self.small.reduce(2 ** level)
        return pic


class Art:
    """One pin's image + view: zoom, normalised centre (cx, cy), rotation."""
    def __init__(self, source, zoom=1.0, cx=0.5, cy=0.5, angle=0.0, flip=False):
        """zoom 1.0 = the image just covers the pin. cx / cy = the point of the image that sits
        in the middle of the pin, as a fraction (0 to 1) of its width and height. angle is
        in degrees, clockwise.
        """
        self.source, self.zoom, self.cx, self.cy, self.angle = source, zoom, cx, cy, angle
        self.flip = flip                   # True = the picture is mirrored left to right

    def copy(self):
        """A separate copy of the view (used for undo snapshots). The image itself is shared,
        not duplicated.
        """
        return Art(self.source, self.zoom, self.cx, self.cy, self.angle, self.flip)

    def key(self):
        """A hashable summary of this view, used to cache rendered images. Values are rounded
        so tiny float noise doesn't defeat the cache.
        """
        return (id(self.source), round(self.zoom, 4), round(self.cx, 4),
                round(self.cy, 4), round(self.angle, 2), bool(self.flip))

    def ppi(self, d_mm):
        """Effective print resolution of the image on a pin of d_mm."""
        return ppi_for(self.source.full.size, self.zoom, d_mm)


def edge_colour(img):
    """The dominant colour along the picture's border: the background that a pin shows where
    the picture runs out. The most common (coarsely grouped) edge colour wins, and the exact
    colour is the average of the edge pixels in that group, so noise and JPEG speckle don't
    matter. A busy photo with no clear background still gets a sensible, average colour.
    """
    w, h = img.size
    t = max(1, min(w, h) // 50)                     # border strip about 2 % wide
    strips = [img.crop((0, 0, w, t)), img.crop((0, h - t, w, h)),
              img.crop((0, t, t, h - t)), img.crop((w - t, t, w, h - t))]
    px = []
    for strip in strips:
        if strip.size[0] and strip.size[1]:
            px.extend(strip.getdata())
    if not px:
        return (255, 255, 255)
    if len(px) > 6000:
        px = px[::len(px) // 6000]                  # plenty for finding the main colour
    bins = {}
    for r, g, b in px:
        bins.setdefault((r >> 4, g >> 4, b >> 4), []).append((r, g, b))
    best = max(bins.values(), key=len)
    n = len(best)
    return (sum(c[0] for c in best) // n, sum(c[1] for c in best) // n,
            sum(c[2] for c in best) // n)


def load_source(path):
    """Open an image file ready for use: fix phone-camera rotation, flatten transparency onto
    white and cap huge images at 4000 px.
    """
    img = Image.open(path)
    if max(img.size) > 8000:
        img.draft("RGB", (4000, 4000))       # JPEGs can be decoded already shrunk
    if img.getexif().get(0x0112, 1) != 1:    # only a picture with a rotation tag needs turning
        img = ImageOps.exif_transpose(img) or img
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        img = Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > 4000:
        img.thumbnail((4000, 4000), Image.LANCZOS)
    img.load()
    return Source(img, os.path.abspath(path))


def render_transform(img, out_w, out_h, k, cxp, cyp, angle, cache=None,
                     resample=Image.BICUBIC, fill=(255, 255, 255)):
    """
    Render `img` into an out_w x out_h picture.
    k   = source pixels per output pixel (bigger = more zoomed out)
    cxp, cyp = source pixel shown at the output centre
    angle = clockwise rotation in degrees
    resample = Pillow filter; the crop window passes a cheaper one while you drag
    fill = colour for areas the image doesn't reach (the picture's own background).
    """
    iw, ih = img.size
    # When zoomed far out, shrink the image in one clean step first. Shrinking by a big
    # factor inside the transform itself would look jagged.
    m = max(1.0, k)                      # pre-shrink for clean downsampling
    if m > 1.0:
        ck = (id(img), round(m, 3))
        small = cache.get(ck) if cache is not None else None
        if small is None:
            small = img.resize((max(1, round(iw / m)), max(1, round(ih / m))), Image.LANCZOS,
                               reducing_gap=2.0)      # shrinks by whole steps first: much faster
            if cache is not None:
                # Only the latest shrunk copy is kept: memory stays small, and dragging in
                # the crop window reuses it.
                cache.clear()
                cache[ck] = small
        sx, sy = small.size[0] / iw, small.size[1] / ih
        img, cxp, cyp, k = small, cxp * sx, cyp * sy, k * sx
    # PIL asks "which source pixel belongs at this output pixel?", so the six numbers a..f
    # describe output -> source: a scale, the rotation, and the offset that puts the chosen
    # point (cxp, cyp) in the middle of the output.
    t = math.radians(angle)
    cs, sn = math.cos(t), math.sin(t)
    a, b = k * cs, k * sn
    d, e = -k * sn, k * cs
    c = cxp - (a * out_w / 2 + b * out_h / 2)
    f = cyp - (d * out_w / 2 + e * out_h / 2)
    return img.transform((out_w, out_h), AFFINE, (a, b, c, d, e, f),
                         resample=resample, fillcolor=tuple(fill))


def render_art(art, d_mm, px_per_mm, small=False):
    """Render one pin's picture as a square, ``d_mm`` millimetres wide at ``px_per_mm`` pixels
    per mm. ``small=True`` uses the small preview copy of the image.
    """
    t = max(1, int(d_mm * px_per_mm))
    if small:
        # pick the shrunk copy of the picture that is still at least as sharp as the output
        k0 = base_crop(art.source.small.size) / art.zoom / t
        img = art.source.mip(int(math.log2(k0)) if k0 >= 2 else 0)
    else:
        img = art.source.full
    iw, ih = img.size
    k = base_crop(img.size) / art.zoom / t
    if art.flip:
        img = art.source.flipped(img)
    return render_transform(img, t, t, k, art.cx * iw, art.cy * ih, art.angle,
                            fill=art.source.bg)
