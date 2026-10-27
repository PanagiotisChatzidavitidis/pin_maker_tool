"""Fixed numbers and lookup tables shared by the whole app.

Nothing in here changes while the program runs. Lengths are in millimetres unless a name
says otherwise (MM converts millimetres into PDF points).
"""

import platform


MM = 72.0 / 25.4  # points per millimetre

# Layout settings (millimetres)
PAGE_MARGIN = 5.0
BADGE_GAP = 3.0    # default space between two cut circles (can be changed in the app)
MAX_GAP = 20.0
# Canvases saved before badge sizes had a separate "visible" and "cut" diameter treated the
# outer 3 mm of every circle as the part that folds behind the pin.
LEGACY_FOLD = 3.0

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

# Pin sizes. A pin badge has two diameters that matter when you cut your own artwork:
#   face - the finished, visible badge (this is the size people call "a 58 mm pin")
#   cut  - the paper circle you cut out. It is bigger, because the rim of the paper wraps
#          around the edge of the shell and folds behind the pin.
# The cut sizes are typical values for round pin-badge presses (about 5 mm of paper on each
# side, a little more on the biggest badges). Presses differ by a millimetre or two, so
# the app lets you change the cut diameter to match your own press and paper.
# name -> (face diameter, cut diameter, caption)
PIN_SIZES = {
    "25 mm pin": (25, 35, "Mini"),
    "32 mm pin": (32, 42, "Small"),
    "37 mm pin": (37, 48, "Classic"),
    "38 mm pin": (38, 48, "1½ inch"),
    "44 mm pin": (44, 54, "Medium"),
    "50 mm pin": (50, 60, "Large"),
    "58 mm pin": (58, 68, "Most popular"),
    "75 mm pin": (75, 87, "Extra large"),
    "Custom...": None,
}
