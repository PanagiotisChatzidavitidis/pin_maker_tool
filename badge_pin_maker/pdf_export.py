"""Writing the printable PDF sheet.

Only pins that have an image are drawn. For each one the image is clipped to the pin's shape, then a
thin cut line, the optional safe-area ring and four small crop ticks are added. Empty
shapes stay blank so they don't waste ink.
"""

import io
from concurrent.futures import ThreadPoolExecutor

from reportlab import rl_config
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from .constants import BADGE_GAP, EXPORT_DPI, MM
from .imaging import render_art
from .shapes import outline

# reportlab turns every image into ASCII text by default, in slow pure Python (it was most of the
# time of an export) and 25% bigger. Raw binary streams are perfectly normal in a PDF.
rl_config.useA85 = 0


def _pdf_image(art, w, h, dpi):
    """Render at print resolution and embed as high-quality JPEG (small files)."""
    img = render_art(art, w, dpi / 25.4, h_mm=h)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0)
    buf.seek(0)
    return ImageReader(buf)


def _path(canv, pts, x, y):
    """A PDF path along ``pts`` (mm from the shape's centre) around the page point (x, y)."""
    p = canv.beginPath()
    for n, (px, py) in enumerate(pts):
        X, Y = x + px * MM, y - py * MM              # the PDF's y axis points up
        p.moveTo(X, Y) if n == 0 else p.lineTo(X, Y)
    p.close()
    return p


def build_pdf(path, layout, pin, slots, guides=True, dpi=EXPORT_DPI, progress=None):
    """Write the sheet to ``path`` as a PDF.

    layout comes from compute_layout(); pin describes the pin (its shape, the paper shape's
    width and height w x h in mm, and the finished face fw x fh inside it); slots maps a
    position number to its Art. guides draws the dotted ring around the pin's finished face,
    dpi is the resolution of the embedded images, and progress (optional) is called as
    progress(done, total) after each pin.
    """
    W, H = layout["page_w"], layout["page_h"]
    shape, pw, ph = pin["shape"], pin["w"], pin["h"]
    c = pdfcanvas.Canvas(path, pagesize=(W * MM, H * MM))
    c.setTitle("Pin sheet")
    cut = outline(shape, pw, ph)
    face = outline(shape, pin["fw"], pin["fh"])
    total = sum(1 for i in range(len(layout["points"])) if i in slots)
    done = 0
    # Rendering the pictures is the slow part. An image + view used on several pins is rendered
    # only once, and several are rendered at the same time (Pillow does that work outside
    # Python's lock). The pins are still drawn in order, each as soon as its picture is ready.
    pool = ThreadPoolExecutor(max_workers=4)
    cache = {}
    for idx in range(len(layout["points"])):
        art = slots.get(idx)
        if art is not None and art.key() not in cache:
            cache[art.key()] = pool.submit(_pdf_image, art, pw, ph, dpi)

    for idx, (cx, cy) in enumerate(layout["points"]):
        art = slots.get(idx)
        if art is None:
            continue
        k = art.key()
        # Our layout measures from the top-left corner; PDF measures from the bottom-left.
        # Flip y.
        x, y = cx * MM, (H - cy) * MM

        # Clip to the pin's shape so the rectangular image can't spill outside it.
        c.saveState()
        c.clipPath(_path(c, cut, x, y), stroke=0, fill=0)
        c.drawImage(cache[k].result(), x - pw * MM / 2, y - ph * MM / 2, pw * MM, ph * MM)
        c.restoreState()

        # cut line
        c.setStrokeColor(Color(0.55, 0.55, 0.55))
        c.setLineWidth(0.25)
        c.drawPath(_path(c, cut, x, y), stroke=1, fill=0)

        # the finished face of the pin (optional dotted guide)
        if guides and pin["fw"] < pw and pin["fh"] < ph:
            c.setStrokeColor(Color(0.75, 0.75, 0.75))
            c.setLineWidth(0.2)
            c.setDash(1, 1.5)
            c.drawPath(_path(c, face, x, y), stroke=1, fill=0)
            c.setDash()

        # crop ticks
        tick, off = min(2.0, BADGE_GAP * 0.6) * MM, 0.4 * MM
        rx, ry = pw * MM / 2, ph * MM / 2
        c.setStrokeColor(Color(0.2, 0.2, 0.2))
        c.setLineWidth(0.25)
        c.line(x, y + ry + off, x, y + ry + off + tick)
        c.line(x, y - ry - off, x, y - ry - off - tick)
        c.line(x + rx + off, y, x + rx + off + tick, y)
        c.line(x - rx - off, y, x - rx - off - tick, y)

        done += 1
        if progress:
            progress(done, total)

    pool.shutdown()
    c.showPage()
    c.save()
