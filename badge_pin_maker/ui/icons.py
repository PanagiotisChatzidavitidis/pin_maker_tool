"""Round canvas thumbnails and the app logo, as images ready for Tk."""

import os

from PIL import Image, ImageDraw, ImageOps, ImageTk

from ..imaging import Art, Source, render_art
from ..paths import asset_path
from . import theme as T


def _circle_alpha(size):
    """A round transparency mask (drawn big, then shrunk, for smooth edges) used to cut
    pictures into circles.
    """
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def make_icon(art, size=56):
    """Round thumbnail of the canvas's first pin, or a generic pin icon."""
    im = None
    if art:
        path, zoom, cx, cy, angle = art
        try:
            img = Image.open(path)
            img.draft("RGB", (800, 800))
            img = ImageOps.exif_transpose(img) or img
            img = img.convert("RGB")
            img.thumbnail((600, 600), Image.LANCZOS)
            im = render_art(Art(Source(img, path), zoom, cx, cy, angle), 1.0, size, small=True)
        except Exception:  # noqa: BLE001
            im = None
    if im is None:
        S = size * 4
        im = Image.new("RGB", (S, S), T.HOVER_RING)
        dr = ImageDraw.Draw(im)
        m, a, c = S * 0.14, S * 0.14, S / 2
        dr.ellipse((m, m, S - m, S - m), outline="white", width=max(2, S // 32))
        dr.line((c - a, c, c + a, c), fill="white", width=max(2, S // 20))
        dr.line((c, c - a, c, c + a), fill="white", width=max(2, S // 20))
        im = im.resize((size, size), Image.LANCZOS)
    im = im.convert("RGBA")
    im.putalpha(_circle_alpha(size))
    return ImageTk.PhotoImage(im)


def load_logo(size):
    """Use assets/logo.png as the app logo, else fall back to the default pin icon."""
    p = asset_path("logo.png")
    if os.path.isfile(p):
        try:
            im = Image.open(p).convert("RGBA")
            # trim empty transparent borders so the logo uses the full space
            bbox = im.getchannel("A").getbbox()
            if bbox:
                im = im.crop(bbox)
            # scale to fit inside a square WITHOUT cropping, then centre it
            im = ImageOps.contain(im, (size, size), Image.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
            return ImageTk.PhotoImage(canvas)
        except Exception:  # noqa: BLE001
            pass
    return make_icon(None, size)
