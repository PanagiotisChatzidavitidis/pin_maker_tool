"""Writing the printable PDF sheet.

Only pins that have an image are drawn. For each one the image is clipped to a circle, then a
thin cut line, the optional ring that marks the visible edge of the badge and four small
crop ticks are added. Empty
circles stay blank so they don't waste ink.
"""

import io

from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from .constants import BADGE_GAP, EXPORT_DPI, MM
from .imaging import render_art


def _pdf_image(art, d, dpi):
    """Render at print resolution and embed as high-quality JPEG (small files)."""
    img = render_art(art, d, dpi / 25.4)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0)
    buf.seek(0)
    return ImageReader(buf)


def build_pdf(path, layout, d, slots, guides=True, dpi=EXPORT_DPI, progress=None,
              face=None, gap=BADGE_GAP):
    """Write the sheet to ``path`` as a PDF.

    layout comes from compute_layout(), d is the pin diameter in mm and slots maps a circle
    number to its Art. d is the diameter of the circle that gets cut out. face is the
    diameter of the visible badge: guides draws a dotted ring that size, so you can see what
    stays in view and what folds behind. gap is the space between circles (it sets the
    length of the crop ticks), dpi is the resolution of the embedded images, and progress
    (optional) is called as progress(done, total) after each pin.
    """
    W, H = layout["page_w"], layout["page_h"]
    c = pdfcanvas.Canvas(path, pagesize=(W * MM, H * MM))
    c.setTitle("Pin sheet")
    cache = {}
    w = d * MM
    r = w / 2
    total = sum(1 for i in range(len(layout["points"])) if i in slots)
    done = 0

    for idx, (cx, cy) in enumerate(layout["points"]):
        art = slots.get(idx)
        if art is None:
            continue
        # An image + view that is used on several pins is rendered only once.
        k = art.key()
        if k not in cache:
            cache[k] = _pdf_image(art, d, dpi)
        # Our layout measures from the top-left corner; PDF measures from the bottom-left.
        # Flip y.
        x, y = cx * MM, (H - cy) * MM

        # Clip to the pin circle so the square image can't spill outside it.
        c.saveState()
        p = c.beginPath()
        p.circle(x, y, r)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(cache[k], x - r, y - r, w, w)
        c.restoreState()

        # cut line
        c.setStrokeColor(Color(0.55, 0.55, 0.55))
        c.setLineWidth(0.25)
        c.circle(x, y, r, stroke=1, fill=0)

        # ring marking the visible edge of the badge (optional)
        if guides and face and face < d - 0.2:
            c.setStrokeColor(Color(0.75, 0.75, 0.75))
            c.setLineWidth(0.2)
            c.setDash(1, 1.5)
            c.circle(x, y, face / 2 * MM, stroke=1, fill=0)
            c.setDash()

        # crop ticks
        tick, off = min(2.0, gap * 0.6) * MM, 0.4 * MM
        c.setStrokeColor(Color(0.2, 0.2, 0.2))
        c.setLineWidth(0.25)
        c.line(x, y + r + off, x, y + r + off + tick)
        c.line(x, y - r - off, x, y - r - off - tick)
        c.line(x + r + off, y, x + r + off + tick, y)
        c.line(x - r - off, y, x - r - off - tick, y)

        done += 1
        if progress:
            progress(done, total)

    c.showPage()
    c.save()
