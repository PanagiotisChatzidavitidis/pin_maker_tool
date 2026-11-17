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


def pin_from_saved(name, shape="Round"):
    """Turn a saved pin size name (from any version) into one of today's names for ``shape``."""
    table = sizes_for(shape)
    if name in table:
        return name
    return _OLD_PIN.get(name, CUSTOM_PIN) if shape == "Round" else CUSTOM_PIN


def paper_short(name):
    """The cute part of a paper name: "Chunky Batch" for "A4 – Chunky Batch"."""
    return name.split(" – ", 1)[-1] if name in PAPER_SIZES else "Dream Batch"


def pin_short(name, diameter=None, shape="Round", height=None):
    """A short pin label for cards: "Macaron · 32 mm" (round), "Heart · 53 × 57.5 mm",
    or "Chef's Special · 40 mm" for a custom size.
    """
    data = sizes_for(shape).get(name)
    if shape == "Round":
        if data is None:
            return f"Chef's Special · {diameter} mm" if diameter else "Chef's Special"
        return f"{name.split(' – ', 1)[-1]} · {data[0]:g} mm"
    if data is None:
        dims = f"{diameter} × {height} mm" if diameter and height else "custom"
    else:
        dims = name
    return f"{shape} · {dims}"


def cut_size(finished):
    """The paper circle (mm) to print and cut for a pin that ends up ``finished`` mm across:
    the published size for the standard pins, and the same extra edge for any other size.
    """
    for fin, _, cut in filter(None, PIN_SIZES.values()):
        if abs(fin - finished) < 1e-6:
            return float(cut)
    return finished + EXTRA_EDGE


# ---- shapes other than round ---------------------------------------------------------
# For each shape: (finished width, finished height, where the size comes from, the paper size
# the supplier publishes or None). Sizes are what pin-badge machine and mould makers list
# (Brildor, American Button Machines, ChiButtons, Mybuttonmachine); where the paper size is
# not published it is worked out from the finished size with the extra edge below.
_OTHER = {
    "Square": [
        (25.4, 25.4, "1 in · American Button Machines", None),
        (37, 37, "Brildor", None),
        (50.8, 50.8, "2 in · American Button Machines", (69.0, 69.0)),
        (58, 58, "Brildor", None),
        (63.5, 63.5, "2.5 in · American Button Machines", None),
        (76.2, 76.2, "3 in · American Button Machines", None),
    ],
    "Rectangle": [
        (44.5, 69.9, "1.75 × 2.75 in · American Button Machines", None),
        (50, 90, "Brildor", None),
        (50.8, 76.2, "2 × 3 in · American Button Machines", (70.5, 95.8)),
        (63.5, 88.9, "2.5 × 3.5 in · American Button Machines", None),
        (38.1, 114.3, "1.5 × 4.5 in · American Button Machines", None),
    ],
    "Oval": [
        (45, 65, "Brildor, standing up", None),
        (44.5, 69.9, "1.75 × 2.75 in · American Button Machines", None),
    ],
    "Pentagon": [
        (58, 60, "ChiButtons", (70.0, 75.0)),
    ],
    "Hexagon": [
        (58, 65, "ChiButtons, point up", None),
        (66, 58, "Mybuttonmachine, flat on top", None),
    ],
    "Triangle": [
        (40, 34.64, "Brildor, 40 mm sides", None),
    ],
    "Heart": [
        (53, 57.5, "ChiButtons", (63.0, 70.0)),
        (57, 52, "Brildor", None),
    ],
}
_COMMON_PIN = {"Square": "50.8 × 50.8 mm", "Rectangle": "50.8 × 76.2 mm"}
_WRAP = {"Square": None, "Rectangle": None, "Oval": 5.5, "Pentagon": 6.5, "Hexagon": 6.0,
         "Triangle": 7.0, "Heart": 5.5}        # paper edge (mm) on every side, if not published


def _size_key(fw, fh):
    return f"{fw:g} × {fh:g} mm"


def _build_tables():
    tables = {"Round": dict(PIN_SIZES)}
    for shape, rows in _OTHER.items():
        t = {}
        for fw, fh, caption, cut in rows:
            t[_size_key(fw, fh)] = (fw, fh, caption, cut)
        t[CUSTOM_PIN] = None
        tables[shape] = t
    return tables


_TABLES = _build_tables()


def sizes_for(shape):
    """The pin sizes offered for ``shape``: name -> data, ending with the custom entry (None).
    For Round the data is (finished size, caption, paper size); for the others it is
    (finished width, finished height, where it comes from, published paper size or None).
    """
    return _TABLES.get(shape, _TABLES["Round"])


def default_pin(shape):
    """The size picked when you switch to ``shape``."""
    if shape == "Round":
        return DEFAULT_PIN
    return _COMMON_PIN.get(shape) or next(iter(_TABLES[shape]))


def cut_dims(shape, fw, fh):
    """The paper shape (width, height in mm) to print and cut for a pin whose finished face is
    fw x fh: the published size where there is one, otherwise the finished size plus the
    extra edge that wraps round the back.
    """
    if shape == "Round":
        d = cut_size(fw)
        return d, d
    for row in _OTHER[shape]:
        if abs(row[0] - fw) < 1e-6 and abs(row[1] - fh) < 1e-6 and row[3]:
            return row[3]
    wrap = _WRAP[shape]
    if wrap is None:                                   # square and rectangle corners need more
        wrap = 4.7 + 0.1 * min(fw, fh)
    if shape == "Triangle":                            # stays equilateral
        cw = fw + 2 * wrap
        return cw, cw * fh / fw
    return fw + 2 * wrap, fh + 2 * wrap
