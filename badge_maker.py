#!/usr/bin/env python3
"""
Badge Pin Maker
===============
1. Pick a paper size and a pin size - the sheet is laid out automatically.
2. Click a circle (or drop image files onto the sheet) to add photos.
   Position / zoom / rotate each photo under the pin shape.
3. Export a PDF or print directly. Empty circles print blank.
4. Save the sheet as a project to reopen and edit it later.

Requirements:
    pip install pillow reportlab
Optional (drag and drop of image files):
    pip install tkinterdnd2
(tkinter ships with Python; on Linux: sudo apt install python3-tk)

Run:
    python badge_maker.py

Shortcuts:  Ctrl+N new   Ctrl+O open   Ctrl+S save   Ctrl+Shift+S save as
            Ctrl+E export PDF   Ctrl+P print   Ctrl+Z undo   Ctrl+Y redo
            Delete  clear the circle under the mouse
(On macOS use Cmd instead of Ctrl.)
"""

import io
import json
import math
import os
import platform
import re
import subprocess
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageDraw, ImageOps, ImageTk
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import Color

MM = 72.0 / 25.4  # points per millimetre

# Fixed layout settings (millimetres)
PAGE_MARGIN = 5.0
BADGE_GAP = 3.0
SAFE_INSET = 3.0   # the ring that folds behind the pin; outside it is not visible

# Print quality
EXPORT_DPI = 600   # resolution of the photos inside the exported PDF
LOW_PPI = 200      # below this a photo is flagged as low resolution

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")
PROJECT_EXT = ".pinproj"
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".badge_pin_maker.json")

IS_MAC = platform.system() == "Darwin"
MOD = "Command" if IS_MAC else "Control"
MOD_LABEL = "Cmd" if IS_MAC else "Ctrl"

# Lo-fi cosy palette
PETROL = "#005F73"
TEAL = "#008080"
TEAL_HOVER = "#1A9696"
TEAL_DARK = "#006767"
SAND = "#EACDB2"
ORCHID = "#BB76A3"
PLUM = "#7A5677"
WARN = "#C9772B"

BG = "#F6EADD"
CARD = "#FCF6EE"
BORDER = "#E3C9AE"
TEXT = "#2C4651"
MUTED = "#80787A"
BLUSH = "#E4D1D9"
SHADOW = "#CDB2C0"

AFFINE = getattr(Image, "Transform", Image).AFFINE


def _detect_dnd():
    """Use tkinterdnd2 for drag and drop when it is installed and working."""
    try:
        from tkinterdnd2 import TkinterDnD, DND_FILES
        probe = TkinterDnD.Tk()
        probe.withdraw()
        probe.destroy()
        return TkinterDnD.Tk, DND_FILES
    except Exception:  # noqa: BLE001
        return tk.Tk, None


_RootBase, DND_FILES = _detect_dnd()

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

# name -> (diameter, caption)
PIN_SIZES = {
    "25 mm pin": (25, "Small pin"),
    "32 mm pin": (32, "Pin badge"),
    "38 mm pin": (38, "Medium"),
    "44 mm pin": (44, "Classic"),
    "50 mm pin": (50, "Large"),
    "58 mm pin": (58, "Most popular"),
    "75 mm pin": (75, "Extra large"),
    "Custom...": None,
}


# --------------------------------------------------------------------------
# Settings (remembered between sessions)
# --------------------------------------------------------------------------
def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Layout engine
# --------------------------------------------------------------------------
def _grid_layout(W, H, margin, d, gap):
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
    min_x, max_x = min(p[0] for p in pts) - d / 2, max(p[0] for p in pts) + d / 2
    min_y, max_y = min(p[1] for p in pts) - d / 2, max(p[1] for p in pts) + d / 2
    dx = (W - (max_x - min_x)) / 2 - min_x
    dy = (H - (max_y - min_y)) / 2 - min_y
    return [(x + dx, y + dy) for x, y in pts]


def compute_layout(paper_w, paper_h, d, margin, gap):
    """Try portrait/landscape x grid/staggered and keep whichever fits most."""
    orients = [("portrait", min(paper_w, paper_h), max(paper_w, paper_h)),
               ("landscape", max(paper_w, paper_h), min(paper_w, paper_h))]
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


# --------------------------------------------------------------------------
# Photo model + transform maths
# --------------------------------------------------------------------------
class Source:
    """A loaded photo: full-res for the PDF, small copy for fast previews."""
    def __init__(self, img, path=""):
        self.full = img
        self.path = path
        self.small = img.copy()
        self.small.thumbnail((1200, 1200), Image.LANCZOS)


class Art:
    """One pin's photo + view: zoom, normalised centre (cx, cy), rotation."""
    def __init__(self, source, zoom=1.0, cx=0.5, cy=0.5, angle=0.0):
        self.source, self.zoom, self.cx, self.cy, self.angle = source, zoom, cx, cy, angle

    def copy(self):
        return Art(self.source, self.zoom, self.cx, self.cy, self.angle)

    def key(self):
        return (id(self.source), round(self.zoom, 4), round(self.cx, 4),
                round(self.cy, 4), round(self.angle, 2))

    def ppi(self, d_mm):
        """Effective print resolution of the photo on a pin of d_mm."""
        return ppi_for(self.source.full.size, self.zoom, d_mm)


def ppi_for(size, zoom, d_mm):
    return base_crop(size) / zoom / (d_mm / 25.4)


def load_source(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img) or img
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        img = Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img)
    img = img.convert("RGB")
    img.thumbnail((4000, 4000), Image.LANCZOS)
    return Source(img, os.path.abspath(path))


def base_crop(size):
    """Side (source px) of the square 'cover' crop at zoom 1."""
    return min(size)


def render_transform(img, out_w, out_h, k, cxp, cyp, angle, cache=None):
    """
    Render `img` into an out_w x out_h picture.
    k   = source pixels per output pixel (bigger = more zoomed out)
    cxp, cyp = source pixel shown at the output centre
    angle = clockwise rotation in degrees
    Areas the photo doesn't reach are white.
    """
    iw, ih = img.size
    m = max(1.0, k)                      # pre-shrink for clean downsampling
    if m > 1.0:
        ck = (id(img), round(m, 3))
        small = cache.get(ck) if cache is not None else None
        if small is None:
            small = img.resize((max(1, round(iw / m)), max(1, round(ih / m))), Image.LANCZOS)
            if cache is not None:
                cache.clear()
                cache[ck] = small
        sx, sy = small.size[0] / iw, small.size[1] / ih
        img, cxp, cyp, k = small, cxp * sx, cyp * sy, k * sx
    t = math.radians(angle)
    cs, sn = math.cos(t), math.sin(t)
    a, b = k * cs, k * sn
    d, e = -k * sn, k * cs
    c = cxp - (a * out_w / 2 + b * out_h / 2)
    f = cyp - (d * out_w / 2 + e * out_h / 2)
    return img.transform((out_w, out_h), AFFINE, (a, b, c, d, e, f),
                         resample=Image.BICUBIC, fillcolor=(255, 255, 255))


def render_art(art, d_mm, px_per_mm, small=False):
    img = art.source.small if small else art.source.full
    iw, ih = img.size
    t = max(1, int(d_mm * px_per_mm))
    k = base_crop(img.size) / art.zoom / t
    return render_transform(img, t, t, k, art.cx * iw, art.cy * ih, art.angle)


# --------------------------------------------------------------------------
# PDF export (only filled circles are drawn; empty ones stay blank)
# --------------------------------------------------------------------------
def _pdf_image(art, d, dpi):
    """Render at print resolution and embed as high-quality JPEG (small files)."""
    img = render_art(art, d, dpi / 25.4)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0)
    buf.seek(0)
    return ImageReader(buf)


def build_pdf(path, layout, d, slots, guides=True, dpi=EXPORT_DPI, progress=None):
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
        k = art.key()
        if k not in cache:
            cache[k] = _pdf_image(art, d, dpi)
        x, y = cx * MM, (H - cy) * MM

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

    c.showPage()
    c.save()


def print_pdf(path):
    system = platform.system()
    if system == "Windows":
        try:
            os.startfile(path, "print")  # type: ignore[attr-defined]
        except OSError:
            os.startfile(path)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["lp", "-o", "scaling=100", path], check=False)
    else:
        if subprocess.run(["which", "lp"], capture_output=True).returncode == 0:
            subprocess.run(["lp", "-o", "scaling=100", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)


# --------------------------------------------------------------------------
# Styling helpers
# --------------------------------------------------------------------------
def setup_style(root):
    root.configure(bg=BG)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    base = ("Segoe UI", 10) if platform.system() == "Windows" else (
        ("Helvetica Neue", 11) if platform.system() == "Darwin" else ("DejaVu Sans", 10))
    st.configure(".", background=BG, foreground=TEXT, font=base)
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=CARD)
    st.configure("Card.TLabel", background=CARD, foreground=TEXT)
    st.configure("Muted.TLabel", background=CARD, foreground=MUTED)
    st.configure("CardTitle.TLabel", background=CARD, foreground=PETROL,
                 font=("Georgia", 12, "bold"))
    st.configure("Title.TLabel", background=BG, foreground=PETROL, font=("Georgia", 20, "bold"))
    st.configure("Hint.TLabel", background=BG, foreground=MUTED)
    st.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, focuscolor=CARD)
    st.map("Card.TCheckbutton", background=[("active", CARD)],
           indicatorcolor=[("selected", TEAL)])
    st.configure("Accent.TButton", background=TEAL, foreground="white", padding=(16, 9),
                 borderwidth=0, focusthickness=0, focuscolor=TEAL, font=(base[0], 10, "bold"))
    st.map("Accent.TButton", background=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)])
    st.configure("Soft.TButton", background=SAND, foreground=TEXT, padding=(12, 7),
                 borderwidth=0, focusthickness=0, focuscolor=SAND)
    st.map("Soft.TButton", background=[("pressed", "#D6B391"), ("active", "#E2C3A4")])
    st.configure("Horizontal.TScale", background=CARD, troughcolor=BORDER)
    st.configure("Teal.Horizontal.TProgressbar", troughcolor=BORDER, background=TEAL,
                 bordercolor=BG, lightcolor=TEAL, darkcolor=TEAL, thickness=6)
    st.configure("TCombobox", fieldbackground="white", background=SAND, bordercolor=BORDER,
                 arrowcolor=TEAL, padding=4)
    st.configure("TEntry", fieldbackground="white", bordercolor=BORDER, padding=3)
    st.configure("TSpinbox", fieldbackground="white", bordercolor=BORDER, arrowcolor=TEAL)
    root.option_add("*TCombobox*Listbox.selectBackground", TEAL)
    root.option_add("*TCombobox*Listbox.background", "white")
    return base


def make_card(parent, title, pady=(0, 10)):
    outer = tk.Frame(parent, bg=BORDER)
    outer.pack(fill="x", pady=pady)
    inner = ttk.Frame(outer, style="Card.TFrame", padding=(14, 10))
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    if title:
        ttk.Label(inner, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))
    return inner


class StatTile(tk.Frame):
    """A small card with a big value and a caption underneath."""
    def __init__(self, parent, font_family):
        super().__init__(parent, bg=BORDER)
        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.value = tk.Label(inner, bg=CARD, fg=PETROL, anchor="w",
                              font=("Georgia", 20, "bold"))
        self.value.pack(fill="x", padx=14, pady=(9, 0))
        self.caption = tk.Label(inner, bg=CARD, fg=MUTED, anchor="w",
                                font=(font_family, 9))
        self.caption.pack(fill="x", padx=14, pady=(0, 10))

    def set(self, value, caption, warn=False):
        self.value.config(text=value)
        self.caption.config(text=caption, fg=WARN if warn else MUTED)


# --------------------------------------------------------------------------
# Crop dialog
# --------------------------------------------------------------------------
class CropDialog(tk.Toplevel):
    """The pin circle stays fixed; the photo moves/zooms/rotates underneath it.
    result = (zoom, cx, cy, angle, copies) after Continue, or None after Skip/Cancel.
    stop   = True when the user ended a multi-photo batch."""
    CW, CH = 680, 470
    VW = 330
    ZMIN, ZMAX = 0.3, 6.0

    def __init__(self, parent, source, d, max_copies=0, art=None, title="Crop photo",
                 batch=None):
        super().__init__(parent)
        self.configure(bg=BG)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        self.stop = False
        self.src = source
        self.d = d
        self.max_copies = max_copies
        self._cache = {}
        self._last = None
        self._photo = None

        # fixed viewport (the pin) in the middle of the canvas
        self.vw = self.VW
        self.inset = SAFE_INSET * (self.vw / d)
        self.vx0, self.vy0 = (self.CW - self.vw) / 2, (self.CH - self.vw) / 2
        self.cut_mask = self._circle_mask(0)
        self.safe_mask = self._circle_mask(self.inset)
        self.black = Image.new("RGB", (self.CW, self.CH), (6, 34, 42))

        self.cx = art.cx if art else 0.5
        self.cy = art.cy if art else 0.5
        self.v_zoom = tk.DoubleVar(value=math.log(art.zoom if art else 1.0))
        self.v_angle = tk.DoubleVar(value=art.angle if art else 0.0)
        self.v_copies = tk.IntVar(value=1)

        self.cv = tk.Canvas(self, width=self.CW, height=self.CH, bg="#0B2E37",
                            highlightthickness=0, cursor="fleur")
        self.cv.pack(padx=14, pady=(14, 8))

        card = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
        card.pack(fill="x", padx=14)

        r1 = ttk.Frame(card, style="Card.TFrame")
        r1.pack(fill="x")
        ttk.Label(r1, text="Zoom", style="Card.TLabel", width=7).pack(side="left")
        ttk.Scale(r1, from_=math.log(self.ZMIN), to=math.log(self.ZMAX),
                  variable=self.v_zoom).pack(side="left", fill="x", expand=True, padx=8)
        self.zoom_lbl = ttk.Label(r1, text="100%", style="Card.TLabel", width=6)
        self.zoom_lbl.pack(side="left")

        r2 = ttk.Frame(card, style="Card.TFrame")
        r2.pack(fill="x", pady=(8, 0))
        ttk.Label(r2, text="Rotate", style="Card.TLabel", width=7).pack(side="left")
        ttk.Button(r2, text="↺ 90°", style="Soft.TButton", width=6,
                   command=lambda: self.rotate_by(-90)).pack(side="left")
        ttk.Scale(r2, from_=-180, to=180, variable=self.v_angle).pack(
            side="left", fill="x", expand=True, padx=8)
        ttk.Button(r2, text="↻ 90°", style="Soft.TButton", width=6,
                   command=lambda: self.rotate_by(90)).pack(side="left")
        self.angle_lbl = ttk.Label(r2, text="0°", style="Card.TLabel", width=6, anchor="e")
        self.angle_lbl.pack(side="left")

        r3 = ttk.Frame(card, style="Card.TFrame")
        r3.pack(fill="x", pady=(10, 0))
        ttk.Button(r3, text="Reset", style="Soft.TButton", command=self.reset).pack(side="left")
        if max_copies > 0:
            ttk.Label(r3, text="Copies", style="Card.TLabel").pack(side="left", padx=(18, 6))
            ttk.Spinbox(r3, from_=1, to=max_copies, textvariable=self.v_copies,
                        width=5).pack(side="left")
            ttk.Label(r3, text=f"of {max_copies} free circle{'s' if max_copies != 1 else ''}",
                      style="Muted.TLabel").pack(side="left", padx=6)
        self.q_lbl = ttk.Label(r3, text="", style="Card.TLabel")
        self.q_lbl.pack(side="right")

        foot = ttk.Frame(self)
        foot.pack(fill="x", padx=14, pady=12)
        ttk.Button(foot, text="Continue", style="Accent.TButton", command=self.on_ok).pack(side="right")
        if batch and batch[1] > 1:
            ttk.Button(foot, text="Skip", style="Soft.TButton",
                       command=self.destroy).pack(side="right", padx=8)
            ttk.Button(foot, text="Stop", style="Soft.TButton",
                       command=self.on_stop).pack(side="right")
        else:
            ttk.Button(foot, text="Cancel", style="Soft.TButton",
                       command=self.destroy).pack(side="right", padx=8)
        ttk.Label(foot, style="Hint.TLabel", justify="left",
                  text="Drag to move · scroll to zoom\nBright = visible on the pin · "
                       "shaded ring = folds behind").pack(side="left")

        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_drag)
        self.cv.bind("<MouseWheel>", lambda e: self.zoom_by(1.1 if e.delta > 0 else 1 / 1.1))
        self.cv.bind("<Button-4>", lambda e: self.zoom_by(1.1))
        self.cv.bind("<Button-5>", lambda e: self.zoom_by(1 / 1.1))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.on_ok())
        self.v_zoom.trace_add("write", lambda *_: self.update_view())
        self.v_angle.trace_add("write", lambda *_: self.update_view())

        self.update_view()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    # ---- helpers
    def _circle_mask(self, inset):
        s = 2  # supersample for smooth edges
        m = Image.new("L", (self.CW * s, self.CH * s), 0)
        x0, y0 = (self.vx0 + inset) * s, (self.vy0 + inset) * s
        x1, y1 = (self.vx0 + self.vw - inset) * s, (self.vy0 + self.vw - inset) * s
        if x1 > x0 and y1 > y0:
            ImageDraw.Draw(m).ellipse((x0, y0, x1, y1), fill=255)
        return m.resize((self.CW, self.CH), Image.LANCZOS)

    @property
    def zoom(self):
        return math.exp(self.v_zoom.get())

    def zoom_by(self, f):
        z = min(self.ZMAX, max(self.ZMIN, self.zoom * f))
        self.v_zoom.set(math.log(z))

    def rotate_by(self, deg):
        a = self.v_angle.get() + deg
        self.v_angle.set(((a + 180) % 360) - 180)

    def reset(self):
        self.cx = self.cy = 0.5
        self.v_angle.set(0.0)
        self.v_zoom.set(0.0)

    def on_press(self, e):
        self._last = (e.x, e.y)

    def on_drag(self, e):
        if self._last is None:
            return
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self._last = (e.x, e.y)
        img = self.src.small
        iw, ih = img.size
        k = base_crop(img.size) / self.zoom / self.vw
        t = math.radians(self.v_angle.get())
        cs, sn = math.cos(t), math.sin(t)
        # moving the picture with the mouse = moving the crop centre the other way
        self.cx = min(1.0, max(0.0, self.cx - k * (cs * dx + sn * dy) / iw))
        self.cy = min(1.0, max(0.0, self.cy - k * (-sn * dx + cs * dy) / ih))
        self.update_view()

    def update_view(self):
        zoom, angle = self.zoom, self.v_angle.get()
        self.zoom_lbl.config(text=f"{zoom * 100:.0f}%")
        self.angle_lbl.config(text=f"{angle:.0f}°")

        ppi = ppi_for(self.src.full.size, zoom, self.d)
        if ppi >= 300:
            self.q_lbl.config(text=f"{ppi:.0f} dpi · Sharp", foreground=TEAL)
        elif ppi >= LOW_PPI:
            self.q_lbl.config(text=f"{ppi:.0f} dpi · Fine", foreground=TEXT)
        else:
            self.q_lbl.config(text=f"{ppi:.0f} dpi · Low, may print soft", foreground=WARN)

        img = self.src.small
        iw, ih = img.size
        k = base_crop(img.size) / zoom / self.vw
        bright = render_transform(img, self.CW, self.CH, k, self.cx * iw, self.cy * ih,
                                  angle, self._cache)
        mid = Image.blend(bright, self.black, 0.38)       # folds behind the pin
        dim = Image.blend(bright, self.black, 0.74)       # outside the pin
        layer = Image.composite(mid, dim, self.cut_mask)
        final = Image.composite(bright, layer, self.safe_mask)
        self._photo = ImageTk.PhotoImage(final)
        self.cv.delete("all")
        self.cv.create_image(0, 0, anchor="nw", image=self._photo)
        x0, y0 = self.vx0, self.vy0
        x1, y1 = x0 + self.vw, y0 + self.vw
        i = self.inset
        self.cv.create_oval(x0, y0, x1, y1, outline="white", width=2)
        if self.vw - 2 * i > 2:
            self.cv.create_oval(x0 + i, y0 + i, x1 - i, y1 - i, outline="#FFE2C4",
                                width=2, dash=(5, 4))

    def on_stop(self):
        self.stop = True
        self.destroy()

    def on_ok(self):
        try:
            copies = int(self.v_copies.get())
        except (ValueError, tk.TclError):
            copies = 1
        if self.max_copies > 0 and copies > self.max_copies:
            free = self.max_copies
            if not messagebox.askokcancel(
                    "Not enough free circles",
                    f"You asked for {copies} copies but only {free} circle"
                    f"{' is' if free == 1 else 's are'} free.\n\n"
                    f"Only {free} will be added.", parent=self):
                return
        copies = max(1, min(self.max_copies, copies)) if self.max_copies > 0 else 1
        self.result = (self.zoom, self.cx, self.cy, self.v_angle.get(), copies)
        self.destroy()


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------
class BadgeApp(_RootBase):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self._loading = True

        self.title("Untitled — Badge Pin Maker")
        geo = self.settings.get("size")
        if not (isinstance(geo, str) and re.fullmatch(r"\d{3,4}x\d{3,4}", geo)):
            geo = "1220x820"
        self.geometry(geo)
        self.minsize(1020, 720)
        self.base_font = setup_style(self)

        self.slots = {}          # slot index -> Art
        self.layout = None
        self.geo = None          # (scale, ox, oy, params)
        self.hover = None
        self.selected = None
        self.popup = None
        self._photo_cache = {}
        self._after = None
        self._status_after = None
        self._undo, self._redo = [], []
        self.project_path = None
        self.dirty = False

        s = self.settings
        paper = s.get("paper") if s.get("paper") in PAPER_SIZES else "A4"
        pin = s.get("pin") if s.get("pin") in PIN_SIZES else "32 mm pin"
        self.v_paper = tk.StringVar(value=paper)
        self.v_pw = tk.StringVar(value=str(s.get("pw", "210")))
        self.v_ph = tk.StringVar(value=str(s.get("ph", "297")))
        self.v_pin = tk.StringVar(value=pin)
        self.v_d = tk.StringVar(value=str(s.get("d", "32")))
        self.v_guides = tk.BooleanVar(value=bool(s.get("guides", True)))

        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        for v in (self.v_paper, self.v_pw, self.v_ph, self.v_pin, self.v_d, self.v_guides):
            v.trace_add("write", self._on_setting)
        self.v_paper.trace_add("write", lambda *_: self._paper_changed())
        self.v_pin.trace_add("write", lambda *_: self._pin_changed())
        self._paper_changed()
        self._pin_changed()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._loading = False
        self.set_status()

    # ---- menu / shortcuts ---------------------------------------------------
    def _build_menu(self):
        def acc(k):
            return f"{MOD_LABEL}+{k}"
        mb = tk.Menu(self)
        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="New project", accelerator=acc("N"), command=self.new_project)
        fm.add_command(label="Open project…", accelerator=acc("O"), command=self.open_project)
        fm.add_command(label="Save project", accelerator=acc("S"), command=self.save_project)
        fm.add_command(label="Save project as…", accelerator=acc("Shift+S"),
                       command=self.save_project_as)
        fm.add_separator()
        fm.add_command(label="Export PDF…", accelerator=acc("E"), command=self.export_pdf)
        fm.add_command(label="Print", accelerator=acc("P"), command=self.print_now)
        fm.add_separator()
        fm.add_command(label="Quit", command=self.on_close)
        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="Undo", accelerator=acc("Z"), command=self.undo)
        em.add_command(label="Redo", accelerator=acc("Y"), command=self.redo)
        em.add_separator()
        em.add_command(label="Clear all photos", command=self.clear_all)
        mb.add_cascade(label="File", menu=fm)
        mb.add_cascade(label="Edit", menu=em)
        self.config(menu=mb)

    def _bind_shortcuts(self):
        def handler(fn):
            return lambda e: (fn(), "break")[1]
        table = [("n", self.new_project), ("o", self.open_project), ("s", self.save_project),
                 ("Shift-S", self.save_project_as), ("e", self.export_pdf),
                 ("p", self.print_now), ("z", self.undo), ("y", self.redo),
                 ("Shift-Z", self.redo)]
        for key, fn in table:
            self.bind(f"<{MOD}-{key}>", handler(fn))
            if len(key) == 1:
                self.bind(f"<{MOD}-{key.upper()}>", handler(fn))
        self.bind("<Delete>", self.delete_selected)
        self.bind("<Escape>", lambda e: self.close_popup())

    # ---- UI --------------------------------------------------------------
    def _build_ui(self):
        # status bar first so it claims the bottom edge
        status = tk.Frame(self, bg=CARD)
        status.pack(side="bottom", fill="x")
        tk.Frame(self, bg=BORDER, height=1).pack(side="bottom", fill="x")
        self.status_lbl = tk.Label(status, bg=CARD, fg=MUTED, anchor="w", padx=14, pady=6,
                                   font=(self.base_font[0], 9))
        self.status_lbl.pack(side="left")
        tk.Label(status, bg=CARD, fg=MUTED, padx=14, font=(self.base_font[0], 9),
                 text=f"{MOD_LABEL}+Z undo  ·  {MOD_LABEL}+S save  ·  {MOD_LABEL}+P print"
                 ).pack(side="right")
        self.export_bar = ttk.Progressbar(status, length=160, mode="determinate",
                                          style="Teal.Horizontal.TProgressbar")

        left = ttk.Frame(self, padding=(18, 16, 8, 16))
        left.pack(side="left", fill="y")
        right = ttk.Frame(self, padding=(8, 16, 18, 16))
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Badge Pin Maker", style="Title.TLabel").pack(anchor="w", pady=(0, 14))

        f = make_card(left, "1 · Paper size")
        ttk.Combobox(f, textvariable=self.v_paper, values=list(PAPER_SIZES),
                     state="readonly", width=30).pack(fill="x")
        self.paper_custom = ttk.Frame(f, style="Card.TFrame")
        for lbl, var in (("W", self.v_pw), ("H", self.v_ph)):
            ttk.Label(self.paper_custom, text=lbl, style="Card.TLabel").pack(side="left")
            ttk.Entry(self.paper_custom, textvariable=var, width=6).pack(side="left", padx=4)
        ttk.Label(self.paper_custom, text="mm", style="Muted.TLabel").pack(side="left")

        f = make_card(left, "2 · Pin size")
        ttk.Combobox(f, textvariable=self.v_pin, values=list(PIN_SIZES),
                     state="readonly", width=30).pack(fill="x")
        self.pin_custom = ttk.Frame(f, style="Card.TFrame")
        ttk.Label(self.pin_custom, text="Diameter", style="Card.TLabel").pack(side="left")
        ttk.Entry(self.pin_custom, textvariable=self.v_d, width=6).pack(side="left", padx=4)
        ttk.Label(self.pin_custom, text="mm", style="Muted.TLabel").pack(side="left")
        self.pin_note = ttk.Label(f, style="Muted.TLabel")
        self.pin_note.pack(anchor="w", pady=(6, 0))

        f = make_card(left, "3 · Photos")
        tip = "Click a circle to add photos. Select several files to fill many circles at once."
        if DND_FILES:
            tip += " You can also drop image files onto the sheet."
        ttk.Label(f, style="Muted.TLabel", justify="left", wraplength=250,
                  text=tip).pack(anchor="w")
        ttk.Button(f, text="Clear all", style="Soft.TButton",
                   command=self.clear_all).pack(anchor="w", pady=(8, 0))

        ttk.Checkbutton(left, text="Show safe-area guide", variable=self.v_guides,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(2, 8), padx=2)
        a = ttk.Frame(left)
        a.pack(fill="x")
        ttk.Button(a, text="Export PDF", style="Accent.TButton",
                   command=self.export_pdf).pack(side="left", expand=True, fill="x")
        ttk.Button(a, text="Print", style="Accent.TButton",
                   command=self.print_now).pack(side="left", expand=True, fill="x", padx=(8, 0))

        # ---- right: stat tiles + sheet preview
        hdr = ttk.Frame(right)
        hdr.pack(fill="x")
        for c in range(4):
            hdr.columnconfigure(c, weight=1, uniform="tiles")
        self.t_sheet = StatTile(hdr, self.base_font[0])
        self.t_layout = StatTile(hdr, self.base_font[0])
        self.t_pins = StatTile(hdr, self.base_font[0])
        self.t_filled = StatTile(hdr, self.base_font[0])
        for c, tile in enumerate((self.t_sheet, self.t_layout, self.t_pins, self.t_filled)):
            tile.grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else 8, 0))
        self.fill_bar = ttk.Progressbar(right, mode="determinate",
                                        style="Teal.Horizontal.TProgressbar")
        self.fill_bar.pack(fill="x", pady=(10, 10))

        self.cv = tk.Canvas(right, bg=BLUSH, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.schedule_redraw())
        self.cv.bind("<Button-1>", self.on_click)
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<Leave>", lambda e: self._set_hover(None))
        if DND_FILES:
            self.cv.drop_target_register(DND_FILES)
            self.cv.dnd_bind("<<Drop>>", self.on_drop)

    # ---- status bar -----------------------------------------------------------
    def _idle_text(self):
        t = "Click a circle to add photos"
        if DND_FILES:
            t += "  ·  or drop image files onto the sheet"
        return t

    def set_status(self, text=None, hold=4000):
        if self._status_after:
            self.after_cancel(self._status_after)
            self._status_after = None
        self.status_lbl.config(text=text or self._idle_text())
        if text and hold:
            self._status_after = self.after(hold, self._clear_status)

    def _clear_status(self):
        self._status_after = None
        self.set_status()

    # ---- settings helpers ---------------------------------------------------
    @staticmethod
    def _num(var, default):
        try:
            return float(str(var.get()).replace(",", "."))
        except (ValueError, tk.TclError):
            return default

    def _on_setting(self, *_):
        self.schedule_redraw()
        if not self._loading:
            self._mark_dirty()

    def _paper_changed(self):
        dims = PAPER_SIZES.get(self.v_paper.get())
        if dims is None:
            self.paper_custom.pack(anchor="w", pady=(8, 0))
        else:
            self.paper_custom.pack_forget()
            self.v_pw.set(f"{dims[0]:g}")
            self.v_ph.set(f"{dims[1]:g}")

    def _pin_changed(self):
        data = PIN_SIZES.get(self.v_pin.get())
        if data is None:
            self.pin_custom.pack(anchor="w", pady=(8, 0))
            self.pin_note.config(text="Enter the cut diameter of your pin.")
        else:
            self.pin_custom.pack_forget()
            self.v_d.set(str(data[0]))
            self.pin_note.config(text=data[1])

    def _params(self):
        return dict(pw=max(10.0, self._num(self.v_pw, 210)),
                    ph=max(10.0, self._num(self.v_ph, 297)),
                    d=max(1.0, self._num(self.v_d, 32)))

    def compute(self):
        p = self._params()
        self.layout = compute_layout(p["pw"], p["ph"], p["d"], PAGE_MARGIN, BADGE_GAP)
        return p

    def _dir(self, key):
        d = self.settings.get(key)
        return d if d and os.path.isdir(d) else os.path.expanduser("~")

    def _store_settings(self):
        self.settings.update(
            paper=self.v_paper.get(), pw=self.v_pw.get(), ph=self.v_ph.get(),
            pin=self.v_pin.get(), d=self.v_d.get(), guides=bool(self.v_guides.get()),
            size=f"{self.winfo_width()}x{self.winfo_height()}")
        save_settings(self.settings)

    # ---- undo / dirty state -------------------------------------------------
    def _update_title(self):
        name = os.path.basename(self.project_path) if self.project_path else "Untitled"
        self.title(f"{name}{'*' if self.dirty else ''} — Badge Pin Maker")

    def _mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _mark_clean(self):
        self.dirty = False
        self._update_title()

    def _snapshot(self):
        return {i: a.copy() for i, a in self.slots.items()}

    def _push_undo(self):
        self._undo.append(self._snapshot())
        del self._undo[:-60]
        self._redo.clear()
        self._mark_dirty()

    def undo(self):
        if not self._undo:
            self.set_status("Nothing to undo")
            return
        self.close_popup()
        self._redo.append(self._snapshot())
        self.slots = self._undo.pop()
        self._mark_dirty()
        self.schedule_redraw()
        self.set_status("Undone")

    def redo(self):
        if not self._redo:
            self.set_status("Nothing to redo")
            return
        self.close_popup()
        self._undo.append(self._snapshot())
        self.slots = self._redo.pop()
        self._mark_dirty()
        self.schedule_redraw()
        self.set_status("Redone")

    # ---- slots -------------------------------------------------------------
    def _n(self):
        return len(self.layout["points"]) if self.layout else 0

    def _filled(self):
        n = self._n()
        return sum(1 for i in self.slots if i < n)

    def hit(self, x, y):
        if not self.layout or not self.geo:
            return None
        s, ox, oy, p = self.geo
        mx, my = (x - ox) / s, (y - oy) / s
        for i, (cx, cy) in enumerate(self.layout["points"]):
            if (mx - cx) ** 2 + (my - cy) ** 2 <= (p["d"] / 2) ** 2:
                return i
        return None

    def on_click(self, e):
        self.close_popup()
        idx = self.hit(e.x, e.y)
        if idx is None:
            return
        if idx in self.slots:
            self.show_popup(idx)
        else:
            self.choose_photos(idx)

    def delete_selected(self, event=None):
        try:
            if isinstance(self.focus_get(), (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)):
                return
        except (KeyError, tk.TclError):
            pass
        idx = self.hover if self.hover in self.slots else self.selected
        if idx is not None and idx in self.slots:
            self.close_popup()
            self.clear_slot(idx)

    # ---- floating Clear / Modify buttons ------------------------------------
    def show_popup(self, idx):
        self.close_popup()
        self.selected = idx
        s, ox, oy, p = self.geo
        cx, cy = self.layout["points"][idx]
        x, y, w = ox + cx * s, oy + cy * s, p["d"] * s

        # highlight the selected circle
        self.cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2,
                            outline=PLUM, width=3, tags="selected")

        frame = tk.Frame(self.cv, bg=PLUM)
        inner = ttk.Frame(frame, style="Card.TFrame", padding=(8, 8))
        inner.pack(padx=1, pady=1)
        ttk.Button(inner, text="Clear", style="Soft.TButton",
                   command=lambda: self._popup_action(self.clear_slot, idx)).pack(side="left")
        ttk.Button(inner, text="Modify", style="Accent.TButton",
                   command=lambda: self._popup_action(self.modify_slot, idx)).pack(
            side="left", padx=(8, 0))
        frame.update_idletasks()
        pw, ph = frame.winfo_reqwidth(), frame.winfo_reqheight()
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        px = min(max(x - pw / 2, 6), max(6, cw - pw - 6))
        py = y - w / 2 - ph - 8                    # above the circle...
        if py < 6:
            py = y + w / 2 + 8                     # ...or below if there's no room
        py = min(py, max(6, ch - ph - 6))
        self.popup = frame
        self.cv.create_window(px, py, anchor="nw", window=frame, tags="popup")

    def close_popup(self):
        if self.popup is not None:
            self.cv.delete("popup")
            self.popup.destroy()
            self.popup = None
        self.cv.delete("selected")
        self.selected = None

    def _popup_action(self, fn, idx):
        self.close_popup()
        fn(idx)

    # ---- adding photos ------------------------------------------------------
    def choose_photos(self, start=None):
        paths = filedialog.askopenfilenames(
            title="Choose photos", initialdir=self._dir("photo_dir"),
            filetypes=[("Images", " ".join(f"*{e}" for e in IMG_EXTS)), ("All files", "*.*")])
        if not paths:
            return
        paths = list(self.tk.splitlist(paths))
        self.settings["photo_dir"] = os.path.dirname(paths[0])
        self.add_photos(paths, start)

    def on_drop(self, event):
        paths = list(self.tk.splitlist(event.data))
        x = event.x_root - self.cv.winfo_rootx()
        y = event.y_root - self.cv.winfo_rooty()
        self.close_popup()
        self.add_photos(paths, self.hit(x, y))

    def add_photos(self, paths, start=None):
        """Crop each photo in turn and place it on the next free circles."""
        paths = [p for p in paths if p.lower().endswith(IMG_EXTS)]
        if not paths:
            self.set_status("No image files found")
            return
        p = self._params()
        n = self._n()
        free_now = n - sum(1 for k in self.slots if k < n)
        if free_now <= 0:
            messagebox.showinfo(
                "Sheet is full",
                "There are no free circles left.\n\nClear a circle, or choose a "
                "different paper or pin size.")
            return
        if len(paths) > free_now:
            if not messagebox.askokcancel(
                    "Not enough free circles",
                    f"You selected {len(paths)} photos but only {free_now} circle"
                    f"{' is' if free_now == 1 else 's are'} free.\n\n"
                    f"Only the first {free_now} will be added."):
                return
            paths = paths[:free_now]
        pushed = False
        placed = 0
        total = len(paths)
        for j, path in enumerate(paths, 1):
            occupied = {k for k in self.slots if k < n}
            free = n - len(occupied)
            if free <= 0:
                left = total - j + 1
                messagebox.showinfo(
                    "Sheet is full",
                    f"The sheet is full. {left} photo{'s were' if left != 1 else ' was'} "
                    f"not added.")
                break
            try:
                source = load_source(path)
            except Exception as ex:  # noqa: BLE001
                messagebox.showerror("Error", f"Could not open image:\n{os.path.basename(path)}\n{ex}")
                continue
            title = f"Crop photo {j} of {total}" if total > 1 else "Crop photo"
            dlg = CropDialog(self, source, p["d"], max_copies=free, title=title,
                             batch=(j, total))
            self.wait_window(dlg)
            if dlg.stop:
                break
            if dlg.result is None:
                continue
            zoom, cx, cy, angle, copies = dlg.result
            if start is not None and start not in occupied:
                s, start = start, None
            else:
                s = first_free(n, occupied)
            if not pushed:
                self._push_undo()
                pushed = True
            for i in fill_order(n, occupied, s, copies):
                self.slots[i] = Art(source, zoom, cx, cy, angle)
            placed += copies
            self.redraw()
        if placed:
            self.set_status(f"Added {placed} pin{'s' if placed != 1 else ''}")

    def modify_slot(self, idx):
        art = self.slots.get(idx)
        if art is None:
            return
        p = self._params()
        dlg = CropDialog(self, art.source, p["d"], max_copies=0, art=art, title="Modify crop")
        self.wait_window(dlg)
        if dlg.result is not None:
            self._push_undo()
            art.zoom, art.cx, art.cy, art.angle = dlg.result[:4]
            self.schedule_redraw()

    def clear_slot(self, idx):
        if idx in self.slots:
            self._push_undo()
            del self.slots[idx]
            self.schedule_redraw()

    def clear_all(self):
        if self._filled():
            self.close_popup()
            self._push_undo()
            self.slots.clear()
            self.schedule_redraw()
            self.set_status(f"Cleared all photos — {MOD_LABEL}+Z to undo")

    # ---- drawing -----------------------------------------------------------
    def schedule_redraw(self):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(50, self.redraw)

    def _preview_photo(self, art, p, s):
        key = (art.key(), round(p["d"], 2), round(s, 3))
        ph = self._photo_cache.get(key)
        if ph is None:
            if len(self._photo_cache) > 400:
                self._photo_cache.clear()
            im = render_art(art, p["d"], s, small=True).convert("RGBA")
            big = Image.new("L", (im.size[0] * 3, im.size[1] * 3), 0)
            ImageDraw.Draw(big).ellipse((0, 0, big.size[0] - 1, big.size[1] - 1), fill=255)
            im.putalpha(big.resize(im.size, Image.LANCZOS))
            ph = ImageTk.PhotoImage(im)
            self._photo_cache[key] = ph
        return ph

    def redraw(self):
        if self._after:
            self.after_cancel(self._after)
        self._after = None
        self.close_popup()
        p = self.compute()
        L = self.layout
        W, H = L["page_w"], L["page_h"]
        cv = self.cv
        cv.delete("all")
        self.hover = None
        cw, ch = max(cv.winfo_width(), 50), max(cv.winfo_height(), 50)
        s = min((cw - 40) / W, (ch - 40) / H)
        ox, oy = (cw - W * s) / 2, (ch - H * s) / 2
        self.geo = (s, ox, oy, p)

        for off, col in ((6, "#D8C3CD"), (4, SHADOW), (2, "#BFA0B2")):
            cv.create_rectangle(ox + off, oy + off, ox + W * s + off, oy + H * s + off,
                                fill=col, outline="")
        cv.create_rectangle(ox, oy, ox + W * s, oy + H * s, fill="white", outline="#D9C6CF")

        w = p["d"] * s
        ins = SAFE_INSET * s
        tick, off = min(2.0, BADGE_GAP * 0.6) * s, 0.4 * s
        guides = self.v_guides.get()
        low = 0
        for i, (cx, cy) in enumerate(L["points"]):
            x, y = ox + cx * s, oy + cy * s
            art = self.slots.get(i)
            if art is None:
                cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2,
                               outline="#D7B0CA", dash=(4, 4), fill="#FDF8FB")
                a = w * 0.10
                cv.create_line(x - a, y, x + a, y, fill="#CF9BBB", width=2, capstyle="round")
                cv.create_line(x, y - a, x, y + a, fill="#CF9BBB", width=2, capstyle="round")
                continue
            cv.create_image(x, y, image=self._preview_photo(art, p, s))
            cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2, outline="#6B5666")
            if guides and w / 2 - ins > 1:
                cv.create_oval(x - w / 2 + ins, y - w / 2 + ins, x + w / 2 - ins,
                               y + w / 2 - ins, outline="#FFFFFF", dash=(3, 3))
            for (x1, y1, x2, y2) in ((x, y - w / 2 - off, x, y - w / 2 - off - tick),
                                      (x, y + w / 2 + off, x, y + w / 2 + off + tick),
                                      (x - w / 2 - off, y, x - w / 2 - off - tick, y),
                                      (x + w / 2 + off, y, x + w / 2 + off + tick, y)):
                cv.create_line(x1, y1, x2, y2, fill=TEXT)
            if art.ppi(p["d"]) < LOW_PPI:
                low += 1
                r = max(6, w * 0.09)
                bx, by = x + w * 0.34, y - w * 0.34
                cv.create_oval(bx - r, by - r, bx + r, by + r, fill=WARN, outline="white")
                cv.create_text(bx, by, text="!", fill="white",
                               font=(self.base_font[0], max(7, int(r * 1.2)), "bold"))

        n, filled = self._n(), self._filled()
        self._update_stats(L, n, filled, low)
        if n == 0:
            cv.create_text(cw / 2, ch / 2, fill="#a00",
                           text="Pin doesn't fit on this paper — choose a smaller size.")

    def _update_stats(self, L, n, filled, low):
        W, H = L["page_w"], L["page_h"]
        short = self.v_paper.get().split(" (")[0].replace("Custom...", "Custom")
        self.t_sheet.set(short, f"{W:g} × {H:g} mm · {L['orientation'].capitalize()}")
        if L["method"] == "staggered":
            self.t_layout.set("Staggered", "Honeycomb packing")
        else:
            self.t_layout.set("Grid", "Straight rows")
        self.t_pins.set(str(n), f"pin{'s' if n != 1 else ''} per sheet")
        if low:
            self.t_filled.set(str(filled), f"of {n} filled · {low} low-res", warn=True)
        else:
            self.t_filled.set(str(filled), f"of {n} filled")
        self.fill_bar.config(maximum=max(n, 1), value=filled)

    def on_motion(self, e):
        self._set_hover(self.hit(e.x, e.y))

    def _set_hover(self, idx):
        if idx == self.hover:
            return
        self.hover = idx
        self.cv.delete("hover")
        self.cv.config(cursor="hand2" if idx is not None else "")
        if idx is None or not self.geo:
            if self._status_after is None:
                self.set_status()
            return
        self.status_lbl.config(
            text="Click to modify or clear" if idx in self.slots
            else "Click to add photos")
        s, ox, oy, p = self.geo
        cx, cy = self.layout["points"][idx]
        x, y, w = ox + cx * s, oy + cy * s, p["d"] * s
        self.cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2,
                            outline=ORCHID, width=3, tags="hover")

    # ---- projects ----------------------------------------------------------
    def _confirm_discard(self):
        """True when it is fine to replace/close the current sheet."""
        if not (self.dirty and self.slots):
            return True
        ans = messagebox.askyesnocancel("Unsaved changes",
                                        "Save changes to this project first?")
        if ans is None:
            return False
        if ans:
            return self.save_project()
        return True

    def new_project(self):
        if not self._confirm_discard():
            return
        self.close_popup()
        self.slots.clear()
        self._undo.clear()
        self._redo.clear()
        self.project_path = None
        self._mark_clean()
        self.schedule_redraw()
        self.set_status("New project")

    def save_project(self):
        if not self.project_path:
            return self.save_project_as()
        return self._save_to(self.project_path)

    def save_project_as(self):
        initial = (os.path.basename(self.project_path) if self.project_path
                   else "pins" + PROJECT_EXT)
        path = filedialog.asksaveasfilename(
            defaultextension=PROJECT_EXT, filetypes=[("Pin project", f"*{PROJECT_EXT}")],
            initialdir=self._dir("project_dir"), initialfile=initial, title="Save project")
        if not path:
            return False
        return self._save_to(path)

    def _save_to(self, path):
        base = os.path.dirname(os.path.abspath(path))
        photos, index = [], {}
        for a in self.slots.values():
            sp = a.source.path
            if sp not in index:
                try:
                    rel = os.path.relpath(sp, base)
                except ValueError:
                    rel = ""
                index[sp] = len(photos)
                photos.append({"path": sp, "rel": rel})
        data = {
            "app": "badge-pin-maker", "version": 1,
            "paper": self.v_paper.get(), "paper_w": self.v_pw.get(), "paper_h": self.v_ph.get(),
            "pin": self.v_pin.get(), "diameter": self.v_d.get(),
            "guides": bool(self.v_guides.get()),
            "photos": photos,
            "slots": [{"slot": i, "photo": index[a.source.path], "zoom": a.zoom,
                       "cx": a.cx, "cy": a.cy, "angle": a.angle}
                      for i, a in sorted(self.slots.items())],
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as ex:
            messagebox.showerror("Save project", f"Could not save:\n{ex}")
            return False
        self.project_path = path
        self.settings["project_dir"] = base
        self._mark_clean()
        self.set_status(f"Saved {os.path.basename(path)}")
        return True

    def open_project(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open project", initialdir=self._dir("project_dir"),
            filetypes=[("Pin project", f"*{PROJECT_EXT}"), ("All files", "*.*")])
        if path:
            self._load_from(path)

    def _load_from(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("app") != "badge-pin-maker":
                raise ValueError("This is not a Badge Pin Maker project.")
        except (OSError, ValueError) as ex:
            messagebox.showerror("Open project", f"Could not open project:\n{ex}")
            return
        base = os.path.dirname(os.path.abspath(path))

        sources, missing = [], []
        for ph in data.get("photos", []):
            orig = ph.get("path") or ""
            rel = ph.get("rel") or ""
            src = None
            for cand in (orig, os.path.join(base, rel) if rel else "",
                         os.path.join(base, os.path.basename(orig)) if orig else ""):
                if cand and os.path.isfile(cand):
                    try:
                        src = load_source(cand)
                        break
                    except Exception:  # noqa: BLE001
                        pass
            if src is None:
                missing.append(os.path.basename(orig) or "?")
            sources.append(src)

        slots = {}
        for sl in data.get("slots", []):
            try:
                src = sources[int(sl["photo"])]
                if src is None:
                    continue
                slots[int(sl["slot"])] = Art(src, float(sl.get("zoom", 1.0)),
                                             float(sl.get("cx", 0.5)), float(sl.get("cy", 0.5)),
                                             float(sl.get("angle", 0.0)))
            except (KeyError, ValueError, TypeError, IndexError):
                continue

        self._loading = True
        self.close_popup()
        paper = data.get("paper")
        paper = paper if paper in PAPER_SIZES else "Custom..."
        self.v_paper.set(paper)
        if PAPER_SIZES[paper] is None:
            self.v_pw.set(str(data.get("paper_w", "210")))
            self.v_ph.set(str(data.get("paper_h", "297")))
        pin = data.get("pin")
        pin = pin if pin in PIN_SIZES else "Custom..."
        self.v_pin.set(pin)
        if PIN_SIZES[pin] is None:
            self.v_d.set(str(data.get("diameter", "32")))
        self.v_guides.set(bool(data.get("guides", True)))
        self.slots = slots
        self._undo.clear()
        self._redo.clear()
        self.project_path = path
        self.settings["project_dir"] = base
        self._loading = False
        self._mark_clean()
        self.redraw()
        self.set_status(f"Opened {os.path.basename(path)}")
        if missing:
            messagebox.showwarning(
                "Missing photos",
                "These photos could not be found and were left empty:\n\n"
                + "\n".join(missing[:10]) + ("\n…" if len(missing) > 10 else ""))

    def on_close(self):
        if not self._confirm_discard():
            return
        self._store_settings()
        self.destroy()

    # ---- output ------------------------------------------------------------
    def _prepare_export(self):
        p = self.compute()
        n = self._n()
        active = {i: a for i, a in self.slots.items() if i < n}
        if not active:
            messagebox.showwarning("Nothing to export", "Add at least one photo first.")
            return None
        low = sum(1 for a in active.values() if a.ppi(p["d"]) < LOW_PPI)
        if low and not messagebox.askyesno(
                "Low resolution",
                f"{low} pin{'s use' if low != 1 else ' uses'} a photo that will print below "
                f"{LOW_PPI} dpi and may look soft.\n\nContinue anyway?"):
            return None
        return p, active

    def _progress(self, done, total):
        self.export_bar.config(maximum=max(total, 1), value=done)
        self.update_idletasks()

    def _write_pdf(self, path, p, active):
        self.set_status("Building PDF…", hold=0)
        self.export_bar.config(value=0)
        self.export_bar.pack(side="right", padx=(0, 8))
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            build_pdf(path, self.layout, p["d"], active, guides=self.v_guides.get(),
                      dpi=EXPORT_DPI, progress=self._progress)
            return True
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror("Export error", str(ex))
            return False
        finally:
            self.export_bar.pack_forget()
            self.config(cursor="")
            self.set_status()

    def export_pdf(self):
        prep = self._prepare_export()
        if not prep:
            return
        stem = os.path.splitext(os.path.basename(self.project_path))[0] if self.project_path else "pins"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialdir=self._dir("export_dir"), initialfile=f"{stem}.pdf",
            title="Export PDF")
        if not path:
            return
        self.settings["export_dir"] = os.path.dirname(path)
        if self._write_pdf(path, *prep):
            self.set_status(f"Exported {os.path.basename(path)}")

    def print_now(self):
        prep = self._prepare_export()
        if not prep:
            return
        tmp = os.path.join(tempfile.gettempdir(), "pin_sheet.pdf")
        if not self._write_pdf(tmp, *prep):
            return
        try:
            print_pdf(tmp)
            self.set_status("Print job started")
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror("Print error", str(ex))


if __name__ == "__main__":
    BadgeApp().mainloop()