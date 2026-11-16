"""Fixed numbers and lookup tables shared by the whole app.

Nothing in here changes while the program runs. Lengths are in millimetres unless a name
says otherwise (MM converts millimetres into PDF points).
"""

import platform


MM = 72.0 / 25.4  # points per millimetre

# Fixed layout settings (millimetres)
PAGE_MARGIN = 5.0
BADGE_GAP = 3.0
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
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "Letter (8.5x11 in)": (215.9, 279.4),
    "Legal (8.5x14 in)": (215.9, 355.6),
    "Tabloid (11x17 in)": (279.4, 431.8),
    "4x6 in photo": (101.6, 152.4),
    "5x7 in photo": (127.0, 177.8),
    "Custom...": None,
}

# name -> (finished pin size, caption, size of the paper circle to print and cut)
# The paper has to be bigger than the pin so it can wrap around the edge and fold behind. The
# printed sizes follow what pin-badge machine makers publish for each finished size.
PIN_SIZES = {
    "25 mm pin": (25, "Small pin", 35),
    "32 mm pin": (32, "Pin badge", 44),
    "38 mm pin": (38, "Medium", 50),
    "44 mm pin": (44, "Classic", 55),
    "50 mm pin": (50, "Large", 60),
    "58 mm pin": (58, "Most popular", 70),
    "75 mm pin": (75, "Extra large", 85),
    "Custom...": None,
}


def cut_size(finished):
    """The paper circle (mm) to print and cut for a pin that ends up ``finished`` mm across:
    the published size for the standard pins, and the same extra edge for any other size.
    """
    for fin, _, cut in filter(None, PIN_SIZES.values()):
        if abs(fin - finished) < 1e-6:
            return float(cut)
    return finished + EXTRA_EDGE
