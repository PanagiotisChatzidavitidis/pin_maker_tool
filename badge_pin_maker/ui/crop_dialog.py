"""The window where you position an image under the pin circle."""

import math
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from ..constants import LOW_PPI, SAFE_INSET
from ..imaging import base_crop, ppi_for, render_transform
from . import theme as T
from .dialogs import messagebox, set_titlebar, set_window_icon


class CropDialog(tk.Toplevel):
    """The pin circle stays fixed; the image moves/zooms/rotates underneath it.
    result = (zoom, cx, cy, angle, copies) after Continue, or None after Skip/Cancel.
    stop   = True when the user ended a multi-image batch."""
    CW, CH = 680, 470
    VW = 330
    ZMIN, ZMAX = 0.3, 6.0

    def __init__(self, parent, source, d, max_copies=0, art=None, title="Crop image",
                 batch=None):
        """Build the window: the image canvas, the zoom / rotate controls and the buttons.
        """
        super().__init__(parent)
        self.configure(bg=T.BG)
        self.title(title)
        set_window_icon(self)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        self.stop = False
        self.src = source
        self.d = d
        self.max_copies = max_copies
        self._cache = {}
        self._last = None
        self._image = None

        # fixed viewport (the pin) in the middle of the canvas
        self.vw = self.VW
        self.inset = SAFE_INSET * (self.vw / d)
        self.vx0, self.vy0 = (self.CW - self.vw) / 2, (self.CH - self.vw) / 2
        self.cut_mask = self._circle_mask(0)
        self.safe_mask = self._circle_mask(self.inset)
        self.black = Image.new("RGB", (self.CW, self.CH), T.CROP_DIM)

        self.cx = art.cx if art else 0.5
        self.cy = art.cy if art else 0.5
        self.v_zoom = tk.DoubleVar(value=math.log(art.zoom if art else 1.0))
        self.v_angle = tk.DoubleVar(value=art.angle if art else 0.0)
        self.v_copies = tk.IntVar(value=1)

        self.cv = tk.Canvas(self, width=self.CW, height=self.CH, bg=T.BG,
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
        set_titlebar(self)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    # ---- helpers
    def _circle_mask(self, inset):
        """A mask of the pin circle shrunk by ``inset`` pixels. Used to light up the part of
        the image that stays visible.
        """
        s = 2  # supersample for smooth edges
        m = Image.new("L", (self.CW * s, self.CH * s), 0)
        x0, y0 = (self.vx0 + inset) * s, (self.vy0 + inset) * s
        x1, y1 = (self.vx0 + self.vw - inset) * s, (self.vy0 + self.vw - inset) * s
        if x1 > x0 and y1 > y0:
            ImageDraw.Draw(m).ellipse((x0, y0, x1, y1), fill=255)
        return m.resize((self.CW, self.CH), Image.LANCZOS)

    @property
    def zoom(self):
        """The current zoom factor. (The slider stores its logarithm so that zooming feels
        even.)
        """
        return math.exp(self.v_zoom.get())

    def zoom_by(self, f):
        """Multiply the zoom by ``f``, staying within the allowed range."""
        z = min(self.ZMAX, max(self.ZMIN, self.zoom * f))
        self.v_zoom.set(math.log(z))

    def rotate_by(self, deg):
        """Turn the image by ``deg`` degrees, wrapping around so the angle stays between -180
        and 180.
        """
        a = self.v_angle.get() + deg
        self.v_angle.set(((a + 180) % 360) - 180)

    def reset(self):
        """Back to the starting view: centred, upright, zoom 100%."""
        self.cx = self.cy = 0.5
        self.v_angle.set(0.0)
        self.v_zoom.set(0.0)

    def on_press(self, e):
        """Remember where a drag started."""
        self._last = (e.x, e.y)

    def on_drag(self, e):
        """Dragging moves the image underneath the (fixed) pin circle."""
        if self._last is None:
            return
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self._last = (e.x, e.y)
        img = self.src.small
        iw, ih = img.size
        # k = source pixels per screen pixel. The sine / cosine turn a mouse move into a
        # move across the (possibly rotated) image.
        k = base_crop(img.size) / self.zoom / self.vw
        t = math.radians(self.v_angle.get())
        cs, sn = math.cos(t), math.sin(t)
        # moving the picture with the mouse = moving the crop centre the other way
        self.cx = min(1.0, max(0.0, self.cx - k * (cs * dx + sn * dy) / iw))
        self.cy = min(1.0, max(0.0, self.cy - k * (-sn * dx + cs * dy) / ih))
        self.update_view()

    def update_view(self):
        """Redraw the image and the pin outline, and refresh the zoom, rotation and sharpness
        labels.
        """
        zoom, angle = self.zoom, self.v_angle.get()
        self.zoom_lbl.config(text=f"{zoom * 100:.0f}%")
        self.angle_lbl.config(text=f"{angle:.0f}°")

        ppi = ppi_for(self.src.full.size, zoom, self.d)
        if ppi >= 300:
            self.q_lbl.config(text=f"{ppi:.0f} dpi · Sharp", foreground=T.TEAL)
        elif ppi >= LOW_PPI:
            self.q_lbl.config(text=f"{ppi:.0f} dpi · Fine", foreground=T.TEXT)
        else:
            self.q_lbl.config(text=f"{ppi:.0f} dpi · Low, may print soft", foreground=T.WARN)

        img = self.src.small
        iw, ih = img.size
        k = base_crop(img.size) / zoom / self.vw
        # Render the image for the whole canvas, then darken it in two steps so it is easy
        # to see what ends up on the pin.
        bright = render_transform(img, self.CW, self.CH, k, self.cx * iw, self.cy * ih,
                                  angle, self._cache)
        mid = Image.blend(bright, self.black, 0.38)       # folds behind the pin
        dim = Image.blend(bright, self.black, 0.74)       # outside the pin
        layer = Image.composite(mid, dim, self.cut_mask)
        final = Image.composite(bright, layer, self.safe_mask)
        self._image = ImageTk.PhotoImage(final)
        self.cv.delete("all")
        self.cv.create_image(0, 0, anchor="nw", image=self._image)
        x0, y0 = self.vx0, self.vy0
        x1, y1 = x0 + self.vw, y0 + self.vw
        i = self.inset
        self.cv.create_oval(x0, y0, x1, y1, outline=T.CROP_HALO, width=5)   # readable on any image
        self.cv.create_oval(x0, y0, x1, y1, outline=T.CROP_LINE, width=2)
        if self.vw - 2 * i > 2:
            self.cv.create_oval(x0 + i, y0 + i, x1 - i, y1 - i, outline="#FFE2C4",
                                width=2, dash=(5, 4))

    def on_stop(self):
        """End a multi-image batch: nothing more will be cropped."""
        self.stop = True
        self.destroy()

    def on_ok(self):
        """Accept the crop. If more copies were asked for than there are free circles, ask
        before trimming the number down.
        """
        try:
            copies = int(self.v_copies.get())
        except (ValueError, tk.TclError):
            copies = 1
        if self.max_copies > 0 and copies > self.max_copies:
            free = self.max_copies
            if not messagebox.askokcancel(
                    "Squeak! Too many copies",
                    f"Squeak! You asked for {copies} copies but only {free} circle"
                    f"{' is' if free == 1 else 's are'} free.\n\n"
                    f"Is it okay if I only add {free}?", parent=self,
                    ok="Okay, add them", cancel="Go back"):
                return
        copies = max(1, min(self.max_copies, copies)) if self.max_copies > 0 else 1
        self.result = (self.zoom, self.cx, self.cy, self.v_angle.get(), copies)
        self.destroy()
