"""Working out where the pin circles go on a sheet of paper.

Given a paper size and a pin diameter this tries a plain grid and a staggered ("honeycomb")
packing, in portrait and in landscape, and keeps whichever fits the most pins. All positions
are circle centres in millimetres, measured from the top-left corner of the page. There is
no drawing code here, only arithmetic.
"""

import math


def _grid_layout(W, H, margin, d, gap):
    """Plain rows and columns, centred on the sheet. Returns circle centres (x, y) in mm."""
    uw, uh = W - 2 * margin, H - 2 * margin
    if uw < d or uh < d:
        return []
    cols = int((uw + gap + 1e-9) // (d + gap))
    rows = int((uh + gap + 1e-9) // (d + gap))
    if cols < 1 or rows < 1:
        return []
    block_w = cols * d + (cols - 1) * gap
    block_h = rows * d + (rows - 1) * gap
    x0, y0 = (W - block_w) / 2, (H - block_h) / 2
    return [(x0 + d / 2 + c * (d + gap), y0 + d / 2 + r * (d + gap))
            for r in range(rows) for c in range(cols)]


def _hex_layout(W, H, margin, d, gap):
    """Staggered (honeycomb) packing - fits more circles per sheet."""
    uw, uh = W - 2 * margin, H - 2 * margin
    if uw < d or uh < d:
        return []
    # Every other row is shifted by half a circle, and rows sit closer together (by a factor
    # of sqrt(3)/2) because the circles nest into the gaps of the row above.
    pitch = d + gap
    row_h = pitch * math.sqrt(3) / 2
    rows = int((uh - d) // row_h) + 1
    cols_even = int((uw + gap + 1e-9) // pitch)
    cols_odd = int((uw - pitch / 2 + gap + 1e-9) // pitch)
    if rows < 1 or cols_even < 1:
        return []
    pts = []
    for r in range(rows):
        odd = r % 2 == 1
        n = cols_odd if odd else cols_even
        off = pitch / 2 if odd else 0
        for c in range(n):
            pts.append((d / 2 + off + c * pitch, d / 2 + r * row_h))
    if not pts:
        return []
    # The block of circles is built from the top-left corner; now centre it on the page.
    min_x, max_x = min(p[0] for p in pts) - d / 2, max(p[0] for p in pts) + d / 2
    min_y, max_y = min(p[1] for p in pts) - d / 2, max(p[1] for p in pts) + d / 2
    dx = (W - (max_x - min_x)) / 2 - min_x
    dy = (H - (max_y - min_y)) / 2 - min_y
    return [(x + dx, y + dy) for x, y in pts]


def compute_layout(paper_w, paper_h, d, margin, gap):
    """Try portrait/landscape x grid/staggered and keep whichever fits most."""
    orients = [("portrait", min(paper_w, paper_h), max(paper_w, paper_h)),
               ("landscape", max(paper_w, paper_h), min(paper_w, paper_h))]
    # Try all four combinations and give each a score; the biggest score wins. Most pins
    # first, then a plain grid beats a staggered one, then portrait beats landscape.
    best = None
    for o_name, W, H in orients:
        for method in ("grid", "staggered"):
            pts = (_grid_layout(W, H, margin, d, gap) if method == "grid"
                   else _hex_layout(W, H, margin, d, gap))
            score = (len(pts), method == "grid", o_name == "portrait")
            if best is None or score > best[0]:
                best = (score, dict(points=pts, page_w=W, page_h=H,
                                    method=method, orientation=o_name))
    return best[1]


def first_free(n_slots, occupied):
    """Index of the first circle that has no image yet, or None when they are all used."""
    return next((i for i in range(n_slots) if i not in occupied), None)


def fill_order(n_slots, slots, start, copies):
    """Indices to fill: the clicked slot first, then free slots in reading order."""
    out = [start]
    for i in range(n_slots):
        if len(out) >= copies:
            break
        if i != start and i not in slots:
            out.append(i)
    return out[:copies]
