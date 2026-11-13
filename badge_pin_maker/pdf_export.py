"""Writing the printable PDF sheet.

Only pins that have an image are drawn. For each one the image is clipped to a circle, then a
thin cut line, the optional safe-area ring and four small crop ticks are added. Empty
circles stay blank so they don't waste ink.
"""

import io
from concurrent.futures import ThreadPoolExecutor

from reportlab import rl_config
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from .constants import BADGE_GAP, EXPORT_DPI, MM, SAFE_INSET
from .imaging import render_art

# reportlab turns every image into ASCII text by default, in slow pure Python (it was most of the
# time of an export) and 25% bigger. Raw binary streams are perfectly normal in a PDF.
rl_config.useA85 = 0


def _pdf_image(art, d, dpi):
    """Render at print resolution and embed as high-quality JPEG (small files)."""
    img = render_art(art, d, dpi / 25.4)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0)
    buf.seek(0)
    return ImageReader(buf)


def build_pdf(path, layout, d, slots, guides=True, dpi=EXPORT_DPI, progress=None):
    """Write the sheet to ``path`` as a PDF.

    layout comes from compute_layout(), d is the pin diameter in mm and slots maps a circle
    number to its Art. guides draws the dotted safe-area ring, dpi is the resolution of the
    embedded images, and progress (optional) is called as progress(done, total) after each
    pin.
    """
    W, H = layout["page_w"], layout["page_h"]
    c = pdfcanvas.Canvas(path, pagesize=(W * MM, H * MM))
    c.setTitle("Pin sheet")
    w = d * MM
    r = w / 2
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
            cache[art.key()] = pool.submit(_pdf_image, art, d, dpi)

    for idx, (cx, cy) in enumerate(layout["points"]):
        art = slots.get(idx)
        if art is None:
            continue
        k = art.key()
        # Our layout measures from the top-left corner; PDF measures from the bottom-left.
        # Flip y.
        x, y = cx * MM, (H - cy) * MM

        # Clip to the pin circle so the square image can't spill outside it.
        c.saveState()
        p = c.beginPath()
        p.circle(x, y, r)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(cache[k].result(), x - r, y - r, w, w)
        c.restoreState()

        # cut line
        c.setStrokeColor(Color(0.55, 0.55, 0.55))
        c.setLineWidth(0.25)
        c.circle(x, y, r, stroke=1, fill=0)

        # safe-area ring (optional)
        if guides:
            ins = SAFE_INSET * MM
            if r - ins > 0:
                c.setStrokeColor(Color(0.75, 0.75, 0.75))
                c.setLineWidth(0.2)
                c.setDash(1, 1.5)
                c.circle(x, y, r - ins, stroke=1, fill=0)
                c.setDash()

        # crop ticks
        tick, off = min(2.0, BADGE_GAP * 0.6) * MM, 0.4 * MM
        c.setStrokeColor(Color(0.2, 0.2, 0.2))
        c.setLineWidth(0.25)
        c.line(x, y + r + off, x, y + r + off + tick)
        c.line(x, y - r - off, x, y - r - off - tick)
        c.line(x + r + off, y, x + r + off + tick, y)
        c.line(x - r - off, y, x - r - off - tick, y)

        done += 1
        if progress:
            progress(done, total)

    pool.shutdown()
    c.showPage()
    c.save()
