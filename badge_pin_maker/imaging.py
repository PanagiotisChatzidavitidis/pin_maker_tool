"""Photos, and the maths that places them inside a pin circle.

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
    """Effective print resolution (pixels per inch) of a photo of ``size`` pixels, at ``zoom``,
    on a pin ``d_mm`` wide.
    """
    return base_crop(size) / zoom / (d_mm / 25.4)


class Source:
    """A loaded photo: full-res for the PDF, small copy for fast previews."""
    def __init__(self, img, path=""):
        """Keep the full-size picture (for printing) plus a small copy that keeps previews
        fast.
        """
        self.full = img
        self.path = path
        self.small = img.copy()
        self.small.thumbnail((1200, 1200), Image.LANCZOS)


class Art:
    """One pin's photo + view: zoom, normalised centre (cx, cy), rotation."""
    def __init__(self, source, zoom=1.0, cx=0.5, cy=0.5, angle=0.0):
        """zoom 1.0 = the photo just covers the pin. cx / cy = the point of the photo that sits
        in the middle of the pin, as a fraction (0 to 1) of its width and height. angle is
        in degrees, clockwise.
        """
        self.source, self.zoom, self.cx, self.cy, self.angle = source, zoom, cx, cy, angle

    def copy(self):
        """A separate copy of the view (used for undo snapshots). The photo itself is shared,
        not duplicated.
        """
        return Art(self.source, self.zoom, self.cx, self.cy, self.angle)

    def key(self):
        """A hashable summary of this view, used to cache rendered images. Values are rounded
        so tiny float noise doesn't defeat the cache.
        """
        return (id(self.source), round(self.zoom, 4), round(self.cx, 4),
                round(self.cy, 4), round(self.angle, 2))

    def ppi(self, d_mm):
        """Effective print resolution of the photo on a pin of d_mm."""
        return ppi_for(self.source.full.size, self.zoom, d_mm)


def load_source(path):
    """Open an image file ready for use: fix phone-camera rotation, flatten transparency onto
    white and cap huge photos at 4000 px.
    """
    img = Image.open(path)
    img = ImageOps.exif_transpose(img) or img
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        img = Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img)
    img = img.convert("RGB")
    img.thumbnail((4000, 4000), Image.LANCZOS)
    return Source(img, os.path.abspath(path))


def render_transform(img, out_w, out_h, k, cxp, cyp, angle, cache=None):
    """
    Render `img` into an out_w x out_h picture.
    k   = source pixels per output pixel (bigger = more zoomed out)
    cxp, cyp = source pixel shown at the output centre
    angle = clockwise rotation in degrees
    Areas the photo doesn't reach are white.
    """
    iw, ih = img.size
    # When zoomed far out, shrink the photo in one clean step first. Shrinking by a big
    # factor inside the transform itself would look jagged.
    m = max(1.0, k)                      # pre-shrink for clean downsampling
    if m > 1.0:
        ck = (id(img), round(m, 3))
        small = cache.get(ck) if cache is not None else None
        if small is None:
            small = img.resize((max(1, round(iw / m)), max(1, round(ih / m))), Image.LANCZOS)
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
                         resample=Image.BICUBIC, fillcolor=(255, 255, 255))


def render_art(art, d_mm, px_per_mm, small=False):
    """Render one pin's picture as a square, ``d_mm`` millimetres wide at ``px_per_mm`` pixels
    per mm. ``small=True`` uses the small preview copy of the photo.
    """
    img = art.source.small if small else art.source.full
    iw, ih = img.size
    t = max(1, int(d_mm * px_per_mm))
    k = base_crop(img.size) / art.zoom / t
    return render_transform(img, t, t, k, art.cx * iw, art.cy * ih, art.angle)
