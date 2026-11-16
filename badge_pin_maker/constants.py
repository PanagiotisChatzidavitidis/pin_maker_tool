"""Fixed numbers and lookup tables shared by the whole app.

Nothing in here changes while the program runs. Lengths are in millimetres unless a name
says otherwise (MM converts millimetres into PDF points).
"""

import platform


MM = 72.0 / 25.4  # points per millimetre

# Fixed layout settings (millimetres)
PAGE_MARGIN = 5.0
BADGE_GAP = 6.0     # space between neighbouring pin circles: room to cut each one out by hand
EXTRA_EDGE = 11.0  # extra paper (total, mm) a custom pin needs so it can wrap around the back

# Print quality
EXPORT_DPI = 600   # resolution of the images inside the exported PDF
LOW_PPI = 200      # below this an image is flagged as low resolution

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")
CANVAS_EXT = ".pinproj"

IS_MAC = platform.system() == "Darwin"
MOD = "Command" if IS_MAC else "Control"
MOD_LABEL = "Cmd" if IS_MAC else "Ctrl"


# --------------------------------------------------------------------------
# Data: paper sizes and pin sizes (all in millimetres)
# --------------------------------------------------------------------------
PAPER_SIZES = {
    "A6 – Lil' Batch": (105.0, 148.0),
    "A5 – Mini Batch": (148.0, 210.0),
    "A4 – Chunky Batch": (210.0, 297.0),
    "A3 – Jumbo Batch": (297.0, 420.0),
    "Custom – Dream Batch": None,
}
DEFAULT_PAPER = "A4 – Chunky Batch"
CUSTOM_PAPER = "Custom – Dream Batch"

# name -> (finished pin size, caption, size of the paper circle to print and cut)
# The paper has to be bigger than the pin so it can wrap around the edge and fold behind. The
# printed sizes follow what pin-badge machine makers publish for each finished size.
PIN_SIZES = {
    "25 mm – Marshmallow": (25, "Tiny and soft", 35),
    "32 mm – Macaron": (32, "Small and sweet", 44),
    "38 mm – Mochi": (38, "Squishy medium", 50),
    "44 mm – Strawberry Tart": (44, "A classic treat", 55),
    "50 mm – Cupcake": (50, "Big and fluffy", 60),
    "58 mm – Cinnamon Roll": (58, "The crowd favourite", 70),
    "75 mm – Cheesecake": (75, "A whole giant slice", 85),
    "Custom – Chef's Special": None,
}
DEFAULT_PIN = "32 mm – Macaron"
CUSTOM_PIN = "Custom – Chef's Special"

# Names used by older versions (in saved settings and canvases) -> where they live now.
_OLD_PAPER = {"A3": "A3 – Jumbo Batch", "A4": "A4 – Chunky Batch", "A5": "A5 – Mini Batch",
              "A6": "A6 – Lil' Batch"}
_OLD_PAPER_DIMS = {
    "Letter (8.5x11 in)": (215.9, 279.4), "Legal (8.5x14 in)": (215.9, 355.6),
    "Tabloid (11x17 in)": (279.4, 431.8), "4x6 in photo": (101.6, 152.4),
    "5x7 in photo": (127.0, 177.8),
}
_OLD_PIN = {f"{fin} mm pin": key for key, v in PIN_SIZES.items() if v for fin in [v[0]]}


def paper_from_saved(name):
    """Turn a saved paper name (from any version) into one of today's names. Returns
    (name, dims): dims is (width, height) in mm when an old paper no longer in the list
    became "Custom", otherwise None.
    """
    if name in PAPER_SIZES:
        return name, None
    if name in _OLD_PAPER:
        return _OLD_PAPER[name], None
    return CUSTOM_PAPER, _OLD_PAPER_DIMS.get(name)


def pin_from_saved(name):
    """Turn a saved pin name (from any version) into one of today's names."""
    if name in PIN_SIZES:
        return name
    return _OLD_PIN.get(name, CUSTOM_PIN)


def paper_short(name):
    """The cute part of a paper name: "Chunky Batch" for "A4 – Chunky Batch"."""
    return name.split(" – ", 1)[-1] if name in PAPER_SIZES else "Dream Batch"


def pin_short(name, diameter=None):
    """A short pin label for cards: "Macaron · 32 mm", or "Chef's Special · 40 mm"."""
    data = PIN_SIZES.get(name)
    if data is None:
        return f"Chef's Special · {diameter} mm" if diameter else "Chef's Special"
    return f"{name.split(' – ', 1)[-1]} · {data[0]} mm"


def cut_size(finished):
    """The paper circle (mm) to print and cut for a pin that ends up ``finished`` mm across:
    the published size for the standard pins, and the same extra edge for any other size.
    """
    for fin, _, cut in filter(None, PIN_SIZES.values()):
        if abs(fin - finished) < 1e-6:
            return float(cut)
    return finished + EXTRA_EDGE
