"""The window where you position an image under the pin shape."""

import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from .. import ring as ring_mod
from .. import shapes
from ..constants import LOW_PPI
from ..imaging import base_crop, ppi_for, render_transform
from . import theme as T
from .dialogs import messagebox, set_titlebar, set_window_icon
from .ring_studio import RingStudio
from .widgets import FlatSlider, Toggle


class CropDialog(tk.Toplevel):
    """The pin circle stays fixed; the image moves/zooms/rotates underneath it.
    result = (zoom, cx, cy, angle, copies, flip, ring) after Continue, or None after Skip/Cancel.
    stop   = True when the user ended a multi-image batch.

    The window can be resized: the picture area (and the pin circle in it) grows with it.
    While you drag or zoom the picture is drawn with a quick filter; a moment after you stop
    it is redrawn at full quality.
    """
    CW, CH = 720, 440            # starting size of the picture area
    ZMIN, ZMAX = 0.3, 6.0        # zoom limits (the minimum drops further for very wide images)
    FILL = 0.84                  # how much of the picture area's short side the pin takes up
    FOLD_A, OUT_A = 97, 196      # how strongly (0-255) the fold ring / outside is dimmed
    WHEEL_STEP = 1.12            # zoom factor of one wheel notch or + / - press

    def __init__(self, parent, source, pin, max_copies=0, art=None, title="Crop image",
                 batch=None):
        """Build the window: the picture area, the zoom / rotate controls and the buttons.
        """
        super().__init__(parent)
        self.withdraw()                      # build off-screen, then show centred
        self.configure(bg=T.BG)
        self.title(title)
        set_window_icon(self)
        try:
            if parent is not None and parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass
        self.result = None
        self.stop = False
        self.src = source
        self.pin = pin                       # shape, paper size (w x h) and finished size (fw x fh)
        self.shape = pin["shape"]
        self.d, self.dh = pin["w"], pin["h"]
        self.aspect = self.d / self.dh
        self.max_copies = max_copies
        self._cache = {}
        self._last = None
        self._image = None
        self._img_item = None
        self._guides = []
        self._hq_job = self._cfg_job = self._anim_job = self._guide_job = None
        self._z_target = None                # zoom the wheel / buttons are easing towards
        self._anchor = (0.0, 0.0)            # point (from the pin centre) the zoom stays on

        # zoom limits: "fit" shows the whole picture inside the pin, which for a wide image
        # needs a zoom below the usual minimum
        sw, sh = source.small.size
        self.fit_zoom = base_crop((sw, sh), self.aspect) / max(sw, sh * self.aspect)
        start_zoom = art.zoom if art else 1.0
        self.zmin = min(self.ZMIN, self.fit_zoom, start_zoom)
        self.zmax = max(self.ZMAX, start_zoom)

        self.cx = art.cx if art else 0.5
        self.cy = art.cy if art else 0.5
        self.v_zoom = tk.DoubleVar(value=math.log(start_zoom))
        self.v_angle = tk.DoubleVar(value=art.angle if art else 0.0)
        self.flipped = bool(art.flip) if art else False     # mirrored left to right
        self.v_copies = tk.IntVar(value=1)

        # the ring inside the pin's edge (None = no ring); see ring.py
        self.r_lo, self.r_hi = ring_mod.limits(pin["fw"], pin["fh"])
        had = ring_mod.as_ring(art.ring) if art else None
        self.v_ring = tk.BooleanVar(value=bool(had))
        self.v_ring_mm = tk.DoubleVar(value=ring_mod.clamp(
            had.mm if had else ring_mod.default_mm(pin["fw"], pin["fh"]),
            pin["fw"], pin["fh"]))
        self.ring_col = tuple(had.col) if had else (128, 128, 128)
        self.ring_material = (had.material if had.material in ring_mod.MATERIAL_NAMES
                              else "flat") if had else "glossy"
        self.ring_image = had.image if had else None
        self.ring_scale = had.scale if had else 0.3
        self.theme_id = None                 # index of the style tapped last (None once tweaked)
        self._palette = []
        self._plain = None                   # the picture without the ring, as last drawn
        self.studio = None                   # the Ring Studio panel, once opened
        self._grew = 0                       # how much wider the window got for the panel
        self._bold = tkfont.nametofont("TkDefaultFont").copy()
        self._bold.configure(weight="bold")

        # picture area size and the fixed viewport (the pin) in the middle of it
        self.cw, self.ch = self.CW, self.CH

        # ---- header: title on the left, print quality on the right
        head = self._head = ttk.Frame(self, padding=(20, 16, 20, 8))
        head.pack(side="top", fill="x")
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text="Position your image", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(titles, text=f"{self._d_text()}  ·  the pin stays put, "
                               "the picture moves", style="Sub.TLabel").pack(anchor="w")
        self.q_pill = tk.Label(head, bg=T.CARD, fg=T.TEAL, font=self._bold, padx=12, pady=5,
                               highlightthickness=1, highlightbackground=T.BORDER)
        self.q_pill.pack(side="right")

        # ---- footer (packed first so it always stays visible when the window is small)
        foot = ttk.Frame(self, padding=(20, 2, 20, 16))
        foot.pack(side="bottom", fill="x")
        ttk.Button(foot, text="Continue", style="Accent.TButton",
                   command=self.on_ok).pack(side="right")
        if batch and batch[1] > 1:
            ttk.Button(foot, text="Skip", style="Soft.TButton",
                       command=self.destroy).pack(side="right", padx=8)
            ttk.Button(foot, text="Stop", style="Soft.TButton",
                       command=self.on_stop).pack(side="right")
        else:
            ttk.Button(foot, text="Cancel", style="Soft.TButton",
                       command=self.destroy).pack(side="right", padx=8)
        ttk.Label(foot, style="Hint.TLabel", justify="left",
                  text="Drag to move  ·  scroll to zoom  ·  arrows nudge\n"
                       "Bright = visible on the pin  ·  shaded ring = folds behind"
                  ).pack(side="left")

        # ---- controls card
        edge = tk.Frame(self, bg=T.BORDER)
        edge.pack(side="bottom", fill="x", padx=20, pady=(10, 10))
        card = ttk.Frame(edge, style="Card.TFrame", padding=(16, 12))
        card.pack(fill="both", expand=True, padx=1, pady=1)
        card.columnconfigure(2, weight=1)

        ttk.Label(card, text="Zoom", style="Card.TLabel", width=7).grid(row=0, column=0,
                                                                         sticky="w")
        ttk.Button(card, text="−", style="Tool.TButton", width=6,
                   command=lambda: self.zoom_by(1 / self.WHEEL_STEP)).grid(row=0, column=1)
        FlatSlider(card, self.v_zoom, math.log(self.zmin), math.log(self.zmax),
                   origin=math.log(self.zmin), snaps=(0.0,), snap_tol=0.025,
                   command=self._stop_anim).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(card, text="+", style="Tool.TButton", width=6,
                   command=lambda: self.zoom_by(self.WHEEL_STEP)).grid(row=0, column=3)
        self.zoom_lbl = ttk.Label(card, text="100%", style="Value.TLabel", width=6,
                                  anchor="e")
        self.zoom_lbl.grid(row=0, column=4, sticky="e")

        ttk.Label(card, text="Rotate", style="Card.TLabel", width=7).grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(card, text="↺ 90°", style="Tool.TButton", width=6,
                   command=lambda: self.rotate_by(-90)).grid(row=1, column=1, pady=(8, 0))
        FlatSlider(card, self.v_angle, -180, 180, origin=0, snaps=(-180, -90, 0, 90, 180),
                   snap_tol=3).grid(row=1, column=2, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(card, text="↻ 90°", style="Tool.TButton", width=6,
                   command=lambda: self.rotate_by(90)).grid(row=1, column=3, pady=(8, 0))
        self.angle_lbl = ttk.Label(card, text="0°", style="Value.TLabel", width=6,
                                   anchor="e")
        self.angle_lbl.grid(row=1, column=4, sticky="e", pady=(8, 0))

        ttk.Label(card, text="Ring", style="Card.TLabel", width=7).grid(
            row=2, column=0, sticky="w", pady=(8, 0))
        Toggle(card, self.v_ring, command=self._ring_toggled, bg=T.CARD).grid(
            row=2, column=1, pady=(8, 0))
        rr = ttk.Frame(card, style="Card.TFrame")
        rr.grid(row=2, column=2, columnspan=3, sticky="ew", padx=10, pady=(8, 0))
        self.ring_hint = ttk.Label(rr, text="Add a coloured border inside the edge",
                                   style="Muted.TLabel")
        self.ring_hint.pack(side="left")
        self.ring_btn = ttk.Button(rr, text="Style ›", style="Soft.TButton",
                                   command=self.studio_open)
        self.ring_lbl = ttk.Label(rr, text="", style="Value.TLabel")
        self.v_ring_mm.trace_add("write", lambda *_: self._ring_slid())
        self._ring_show()

        r3 = ttk.Frame(card, style="Card.TFrame")
        r3.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(12, 0))
        ttk.Button(r3, text="Fill", style="Soft.TButton", command=self.fill).pack(side="left")
        ttk.Button(r3, text="Fit", style="Soft.TButton", command=self.fit).pack(
            side="left", padx=6)
        ttk.Button(r3, text="Reset", style="Soft.TButton", command=self.reset).pack(
            side="left")
        ttk.Button(r3, text="Flip ⇆", style="Soft.TButton", command=self.flip_h).pack(
            side="left", padx=(6, 0))
        if max_copies > 0:
            ttk.Label(r3, text="Copies", style="Card.TLabel").pack(side="left", padx=(22, 6))
            ttk.Spinbox(r3, from_=1, to=max_copies, textvariable=self.v_copies,
                        width=5).pack(side="left")
            ttk.Label(r3, text=f"of {max_copies} free spot{'s' if max_copies != 1 else ''}",
                      style="Muted.TLabel").pack(side="left", padx=6)

        # ---- the picture area (gets all the spare room when the window grows)
        self.mid = tk.Frame(self, bg=T.BG)
        self.mid.pack(side="top", fill="both", expand=True, padx=20, pady=(2, 0))
        stage = tk.Frame(self.mid, bg=T.BORDER)
        stage.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(stage, width=self.CW, height=self.CH, bg=T.CARD,
                            highlightthickness=0, cursor="fleur")
        self.cv.pack(fill="both", expand=True, padx=1, pady=1)

        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_drag)
        self.cv.bind("<ButtonRelease-1>", lambda e: self._show_guides())
        self.cv.bind("<Double-Button-1>", self._toggle_fit)
        self.cv.bind("<MouseWheel>", lambda e: self._wheel(e, 1 if e.delta > 0 else -1))
        self.cv.bind("<Button-4>", lambda e: self._wheel(e, 1))
        self.cv.bind("<Button-5>", lambda e: self._wheel(e, -1))
        self.cv.bind("<Configure>", self._on_canvas_resize)
        self.bind("<Escape>", self._escape)
        self.bind("<Return>", lambda e: self.on_ok())
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.bind(f"<{key}>", self._key(lambda dx=dx, dy=dy: self._pan(2 * dx, 2 * dy)))
            self.bind(f"<Shift-{key}>",
                      self._key(lambda dx=dx, dy=dy: self._pan(12 * dx, 12 * dy)))
        for key in ("plus", "equal", "KP_Add"):
            self.bind(f"<{key}>", self._key(lambda: self.zoom_by(self.WHEEL_STEP)))
        for key in ("minus", "KP_Subtract"):
            self.bind(f"<{key}>", self._key(lambda: self.zoom_by(1 / self.WHEEL_STEP)))
        self.v_zoom.trace_add("write", lambda *_: self.update_view())
        self.v_angle.trace_add("write", lambda *_: self.update_view())

        self._layout()
        self.update_view(fast=False)

        # size the window to its content (but never taller than the screen), centre it on the
        # screen and show it
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(self.winfo_reqwidth(), sw - 40)
        h = min(self.winfo_reqheight(), sh - 110)
        self.minsize(min(w, 620), min(h, 560))
        x, y = (sw - w) // 2, (sh - h) // 2          # the middle of the screen
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        set_titlebar(self)
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()

    # ---- helpers
    def _d_text(self):
        """The pin as text, e.g. "58 mm pin" or "Heart pin, 53 × 57.5 mm"."""
        fw, fh = self.pin["fw"], self.pin["fh"]
        if self.shape == "Round":
            return f"{fw:g} mm pin"
        return f"{self.shape} pin, {fw:g} × {fh:g} mm"

    def _shape_pts(self, finished=False):
        """The pin's outline in picture-area pixels: the paper shape (``finished`` False) or the
        smaller finished face inside it.
        """
        sx, sy = self.vw / self.d, self.vh / self.dh
        w, h = (self.pin["fw"], self.pin["fh"]) if finished else (self.d, self.dh)
        mx, my = self.vx0 + self.vw / 2, self.vy0 + self.vh / 2
        return [(mx + x * sx, my + y * sy) for x, y in shapes.outline(self.shape, w, h)]

    def _shape_mask(self, finished=False):
        """A mask of the pin's shape (or of its finished face). Used to light up the part of
        the image that stays visible.
        """
        s = 2  # supersample for smooth edges
        m = Image.new("L", (self.cw * s, self.ch * s), 0)
        ImageDraw.Draw(m).polygon([(x * s, y * s) for x, y in self._shape_pts(finished)],
                                  fill=255)
        return m.resize((self.cw, self.ch), Image.LANCZOS)

    @staticmethod
    def _chord(pts, at, vertical):
        """Where the line x = ``at`` (or y = ``at``) crosses the outline: its lowest and highest
        crossing, or None.
        """
        hits, n = [], len(pts)
        for i in range(n):
            (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
            a1, a2, b1, b2 = (x1, x2, y1, y2) if vertical else (y1, y2, x1, x2)
            if (a1 - at) * (a2 - at) <= 0 and a1 != a2:
                hits.append(b1 + (b2 - b1) * (at - a1) / (a2 - a1))
        return (min(hits), max(hits)) if hits else None

    def _layout(self):
        """Work out where the pin sits for the current picture-area size, rebuild the
        dimming mask and redraw the outlines. Runs at start-up and after a window resize.
        """
        cw, ch = self.cw, self.ch
        self.vw = max(120, int(min(cw * self.FILL, ch * self.FILL * self.aspect)))
        self.vh = self.vw / self.aspect
        self.vx0, self.vy0 = (cw - self.vw) / 2, (ch - self.vh) / 2
        face = self.pin["fw"] < self.d - 0.01 and self.pin["fh"] < self.dh - 0.01

        # One mask says how strongly each pixel is dimmed: 0 inside the visible area, a
        # little in the ring that folds behind the pin, a lot outside the pin. That makes
        # drawing a frame a single blend.
        size = (cw, ch)
        cut = self._shape_mask(False)
        safe = self._shape_mask(True) if face else cut
        ring = Image.composite(Image.new("L", size, self.FOLD_A),
                               Image.new("L", size, self.OUT_A), cut)
        self.alpha = Image.composite(Image.new("L", size, 0), ring, safe)
        self.dim = Image.new("RGB", size, T.CROP_DIM)

        self.cv.delete("all")
        self._img_item = self.cv.create_image(0, 0, anchor="nw")
        outer = self._shape_pts(False)
        mx, my = self.vx0 + self.vw / 2, self.vy0 + self.vh / 2

        # thirds + centre guides, only shown while you are moving things
        self._guides = []
        for t in (-self.vw / 6, self.vw / 6):
            c = self._chord(outer, mx + t, True)
            if c:
                self._guides.append(self.cv.create_line(mx + t, c[0], mx + t, c[1]))
        for t in (-self.vh / 6, self.vh / 6):
            c = self._chord(outer, my + t, False)
            if c:
                self._guides.append(self.cv.create_line(c[0], my + t, c[1], my + t))
        self._guides.append(self.cv.create_line(mx - 9, my, mx + 9, my, width=2))
        self._guides.append(self.cv.create_line(mx, my - 9, mx, my + 9, width=2))
        for g in self._guides:
            self.cv.itemconfigure(g, fill="#FFFFFF", state="hidden")
        for g in self._guides[:-2]:
            self.cv.itemconfigure(g, dash=(3, 4))

        flat = [v for p in outer for v in p]
        self.cv.create_polygon(flat, outline=T.CROP_HALO, width=5, fill="")  # readable on any image
        self.cv.create_polygon(flat, outline=T.CROP_LINE, width=2, fill="")
        if face:
            inner = [v for p in self._shape_pts(True) for v in p]
            self.cv.create_polygon(inner, outline="#000000", width=3, dash=(6, 4), fill="")
            self.cv.create_polygon(inner, outline="#FFE2C4", width=1, dash=(6, 4), fill="")

    def _on_canvas_resize(self, e):
        """The window was resized: lay the pin out again once the resizing settles."""
        if (e.width, e.height) == (self.cw, self.ch) or e.width < 50 or e.height < 50:
            return
        self.cw, self.ch = e.width, e.height
        if self._cfg_job is not None:
            self.after_cancel(self._cfg_job)
        self._cfg_job = self.after(30, self._relayout)

    def _relayout(self):
        """Rebuild the pin layout and redraw after a resize."""
        self._cfg_job = None
        self._layout()
        self.update_view(fast=False)

    def _key(self, fn):
        """Wrap a keyboard shortcut so it is ignored while a text box has the focus."""
        def handler(_e):
            try:
                if isinstance(self.focus_get(), (ttk.Spinbox, ttk.Entry, tk.Entry)):
                    return None
            except KeyError:        # tkinter can't name some pop-up widgets
                pass
            fn()
            return "break"
        return handler

    @property
    def zoom(self):
        """The current zoom factor. (The slider stores its logarithm so that zooming feels
        even.)
        """
        return math.exp(self.v_zoom.get())

    def _clamp_zoom(self, z):
        """Keep a zoom factor inside the allowed range."""
        return min(self.zmax, max(self.zmin, z))

    def _zoom_to(self, z, anchor=(0.0, 0.0)):
        """Set the zoom so that the picture point under ``anchor`` (pixels from the pin
        centre) stays where it is on screen, like zooming a map under the cursor.
        """
        z = self._clamp_zoom(z)
        img = self.src.small
        iw, ih = img.size
        b = base_crop(img.size, self.aspect)
        dk = b / self.zoom / self.vw - b / z / self.vw        # change in source px per pixel
        t = math.radians(self.v_angle.get())
        cs, sn = math.cos(t), math.sin(t)
        u, v = anchor
        self.cx = min(1.0, max(0.0, self.cx + dk * (cs * u + sn * v) / iw))
        self.cy = min(1.0, max(0.0, self.cy + dk * (-sn * u + cs * v) / ih))
        self.v_zoom.set(math.log(z))

    def _animate_to(self, z, anchor=(0.0, 0.0)):
        """Ease the zoom towards ``z`` over a few frames instead of jumping."""
        self._z_target = self._clamp_zoom(z)
        self._anchor = anchor
        if self._anim_job is None:
            self._step_zoom()

    def _step_zoom(self):
        """One frame of the zoom easing: close 40% of the remaining (logarithmic) gap."""
        self._anim_job = None
        if self._z_target is None:
            return
        gap = math.log(self._z_target) - self.v_zoom.get()
        if abs(gap) < 0.004:
            z, self._z_target = self._z_target, None
        else:
            z = math.exp(self.v_zoom.get() + gap * 0.4)
        self._zoom_to(z, self._anchor)
        if self._z_target is not None:
            self._anim_job = self.after(16, self._step_zoom)

    def _stop_anim(self):
        """Cancel any zoom easing (the person grabbed the slider)."""
        self._z_target = None
        if self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None

    def zoom_by(self, f, anchor=(0.0, 0.0)):
        """Multiply the zoom by ``f`` (with easing), staying within the allowed range."""
        base = self._z_target if self._z_target is not None else self.zoom
        self._animate_to(base * f, anchor)

    def _wheel(self, e, direction):
        """Mouse wheel: zoom in or out around the cursor."""
        self._show_guides()
        self.zoom_by(self.WHEEL_STEP ** direction,
                     (e.x - self.cw / 2, e.y - self.ch / 2))

    def on_wheel(self, e):
        """Wheel event handler (``e.delta`` > 0 zooms in)."""
        self._wheel(e, 1 if e.delta > 0 else -1)

    def rotate_by(self, deg):
        """Turn the image by ``deg`` degrees, wrapping around so the angle stays between -180
        and 180.
        """
        a = self.v_angle.get() + deg
        self.v_angle.set(((a + 180) % 360) - 180)

    def _recentre(self):
        """Put the middle of the picture under the middle of the pin."""
        self.cx = self.cy = 0.5

    def fill(self):
        """Zoom so the picture just covers the pin, centred."""
        self._recentre()
        self._animate_to(1.0)

    def fit(self):
        """Zoom out so the whole picture sits inside the pin, centred."""
        self._recentre()
        self._animate_to(self.fit_zoom)

    def _toggle_fit(self, _e=None):
        """Double-click: switch between "fill the pin" and "fit the whole picture"."""
        if abs(self.zoom - 1.0) < 0.03 and self.fit_zoom < 0.97:
            self.fit()
        else:
            self.fill()

    def reset(self):
        """Back to the starting view: centred, upright, zoom 100%."""
        self._stop_anim()
        self._recentre()
        self.v_angle.set(0.0)
        self.v_zoom.set(0.0)

    def _show_guides(self):
        """Show the thirds / centre guides and hide them again shortly after the last move."""
        for g in self._guides:
            self.cv.itemconfigure(g, state="normal")
        if self._guide_job is not None:
            self.after_cancel(self._guide_job)
        self._guide_job = self.after(700, self._hide_guides)

    def _hide_guides(self):
        """Hide the guides."""
        self._guide_job = None
        for g in self._guides:
            self.cv.itemconfigure(g, state="hidden")

    def flip_h(self):
        """Mirror the picture left to right. What you see is exactly the old view, mirrored:
        the centre moves to the other side and the turn angle reverses.
        """
        self._stop_anim()
        self.flipped = not self.flipped
        self.cx = 1.0 - self.cx
        a = -self.v_angle.get()
        self.v_angle.set(((a + 180) % 360) - 180 if a != 180 else 180)   # triggers the redraw
        self.update_view()

    def on_press(self, e):
        """Remember where a drag started."""
        self._last = (e.x, e.y)
        self.cv.focus_set()
        self._show_guides()

    def on_drag(self, e):
        """Dragging moves the image underneath the (fixed) pin circle."""
        if self._last is None:
            return
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self._last = (e.x, e.y)
        self._pan(dx, dy)

    def _pan(self, dx, dy):
        """Move the picture by (dx, dy) screen pixels under the pin."""
        img = self.src.small
        iw, ih = img.size
        # k = source pixels per screen pixel. The sine / cosine turn a mouse move into a
        # move across the (possibly rotated) image.
        k = base_crop(img.size, self.aspect) / self.zoom / self.vw
        t = math.radians(self.v_angle.get())
        cs, sn = math.cos(t), math.sin(t)
        # moving the picture with the mouse = moving the crop centre the other way
        self.cx = min(1.0, max(0.0, self.cx - k * (cs * dx + sn * dy) / iw))
        self.cy = min(1.0, max(0.0, self.cy - k * (-sn * dx + cs * dy) / ih))
        self._show_guides()
        self.update_view()

    def update_view(self, fast=True):
        """Redraw the image and refresh the zoom, rotation and sharpness labels. ``fast``
        uses a cheap filter (while moving); a full-quality redraw follows a moment later.
        """
        zoom, angle = self.zoom, self.v_angle.get()
        self.zoom_lbl.config(text=f"{zoom * 100:.0f}%")
        self.angle_lbl.config(text=f"{angle:.0f}°")

        ppi = ppi_for(self.src.full.size, zoom, self.d, self.aspect)
        if ppi >= 300:
            self.q_pill.config(text=f"{ppi:.0f} dpi · Sharp", fg=T.TEAL)
        elif ppi >= LOW_PPI:
            self.q_pill.config(text=f"{ppi:.0f} dpi · Fine", fg=T.TEXT)
        else:
            self.q_pill.config(text=f"{ppi:.0f} dpi · Low, may print soft", fg=T.WARN)

        img = self.src.flipped(self.src.small) if self.flipped else self.src.small
        iw, ih = img.size
        k = base_crop(img.size, self.aspect) / zoom / self.vw
        bright = render_transform(img, self.cw, self.ch, k, self.cx * iw, self.cy * ih,
                                  angle, self._cache,
                                  resample=Image.BILINEAR if fast else Image.BICUBIC,
                                  fill=self.src.bg)
        self._plain = bright
        if self.v_ring.get():
            bright = self._with_ring(bright)
        final = Image.composite(self.dim, bright, self.alpha)
        self._image = ImageTk.PhotoImage(final)
        self.cv.itemconfigure(self._img_item, image=self._image)
        if self._hq_job is not None:
            self.after_cancel(self._hq_job)
            self._hq_job = None
        if fast:
            self._hq_job = self.after(160, self._render_sharp)

    # ---- the ring -----------------------------------------------------------
    def _ring_mm(self):
        """The thickness now, held inside the allowed range."""
        return ring_mod.clamp(self.v_ring_mm.get(), self.pin["fw"], self.pin["fh"])

    def cur_ring(self):
        """The ring as it is now."""
        return ring_mod.Ring(round(self._ring_mm(), 2), tuple(self.ring_col),
                             self.ring_material, self.ring_image, self.ring_scale)

    def _with_ring(self, img):
        """``img`` (the picture area) with the ring painted over it."""
        mx, my = self.vx0 + self.vw / 2, self.vy0 + self.vh / 2
        surface, inside = ring_mod.layer(
            self.cur_ring(), self.shape, self.pin["fw"], self.pin["fh"], (self.cw, self.ch),
            self.vw / self.d, self.vh / self.dh, mx, my)
        return Image.composite(img.convert("RGB"), surface, inside)

    def view_picture(self):
        """What is showing on the pin right now (without the ring), for previews."""
        if self._plain is None:
            return None
        box = (int(self.vx0), int(self.vy0), int(self.vx0 + self.vw), int(self.vy0 + self.vh))
        return self._plain.crop(box).convert("RGB")

    def palette(self):
        """The main colours of what shows on the pin (best ring colour first)."""
        if not self._palette:
            pic = self.view_picture()
            if pic is not None:
                self._palette = ring_mod.dominant_colours(pic)
        return self._palette

    def _ring_show(self):
        """Show the style button and a short summary while the ring is on, a hint while off."""
        on = self.v_ring.get()
        if on:
            self.ring_hint.pack_forget()
            self.ring_lbl.config(text=self._summary())
            self.ring_lbl.pack(side="left")
            self.ring_btn.pack(side="left", padx=(12, 0))
        else:
            self.ring_lbl.pack_forget()
            self.ring_btn.pack_forget()
            self.ring_hint.pack(side="left")

    def _summary(self):
        if self.ring_image:
            return f"Your pattern · {self._ring_mm():.1f} mm"
        return f"{ring_mod.MATERIAL_NAMES.get(self.ring_material, '')} · {self._ring_mm():.1f} mm"

    def _ring_slid(self):
        self.ring_lbl.config(text=self._summary()) if self.v_ring.get() else None
        self.update_view()
        if self.studio is not None:
            self.studio.sync()

    def _ring_toggled(self):
        """The switch was clicked. Switching on picks a colour that suits the picture and opens
        the Ring Studio; switching off closes it.
        """
        if self.v_ring.get():
            self.match_picture(first=True)
            self.studio_open()
        else:
            self.studio_close()
        self._ring_show()
        self.update_view(fast=False)

    def match_picture(self, first=False):
        """Use the colour that suits the picture best, in the Gloss material."""
        self._palette = []
        col = (self.palette() or [(128, 128, 128)])[0]
        self.ring_change(col=col, **({"material": "glossy", "image": None} if first else {}))

    def ring_change(self, _theme=None, **kw):
        """Change part of the ring (material=, col=, image=, scale=, mm=) and show it. Tweaking
        anything by hand ends the "current style" mark.
        """
        self.theme_id = _theme
        if "col" in kw:
            self.ring_col = tuple(kw["col"])
        if "material" in kw:
            self.ring_material = kw["material"]
        if "image" in kw:
            self.ring_image = kw["image"]
        if "scale" in kw:
            self.ring_scale = float(kw["scale"])
        if "mm" in kw:
            self.v_ring_mm.set(ring_mod.clamp(kw["mm"], self.pin["fw"], self.pin["fh"]))
        if not self.v_ring.get():
            self.v_ring.set(True)
        self._ring_show()
        self.update_view()
        if self.studio is not None:
            self.studio.sync()

    def apply_theme(self, i):
        """One-tap style: material, colour and thickness together."""
        _cat, _name, mat, col, share = ring_mod.THEMES[i]
        self.ring_change(_theme=i, material=mat, col=col, image=None,
                         mm=ring_mod.default_mm(self.pin["fw"], self.pin["fh"], share))

    def ring_off(self):
        """Remove the ring."""
        self.v_ring.set(False)
        self.studio_close()
        self._ring_show()
        self.update_view(fast=False)

    def studio_open(self):
        """Show the Ring Studio beside the picture (the window grows to make room)."""
        if self.studio is None:
            self.studio = RingStudio(self, self)
        if not self.studio.winfo_ismapped():
            self.studio.pack(side="right", fill="y", padx=(0, 20), pady=(16, 16),
                             before=self._head)
            self.update_idletasks()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = self.winfo_width(), self.winfo_height()
            nw = min(w + RingStudio.W + 20, sw - 40)
            nh = min(max(h, 780), sh - 110)
            self._grew = nw - w
            x = max(0, min(self.winfo_x(), sw - nw - 10))
            y = max(0, min(self.winfo_y(), sh - nh - 60))
            self.geometry(f"{nw}x{nh}+{x}+{y}")
        self.studio.refresh()

    def studio_close(self):
        """Hide the Ring Studio and give the window its width back."""
        if self.studio is not None and self.studio.winfo_ismapped():
            self.studio.pack_forget()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"{max(620, w - self._grew)}x{h}+{self.winfo_x()}+{self.winfo_y()}")
            self._grew = 0

    def _escape(self, _e=None):
        """Escape closes the Ring Studio first, then the window."""
        if self.studio is not None and self.studio.winfo_ismapped():
            self.studio_close()
        else:
            self.destroy()

    def _render_sharp(self):
        """Redraw at full quality once the picture has stopped moving."""
        self._hq_job = None
        self.update_view(fast=False)

    def on_stop(self):
        """End a multi-image batch: nothing more will be cropped."""
        self.stop = True
        self.destroy()

    def destroy(self):
        """Close the window, cancelling any redraws that were still waiting."""
        for job in (self._hq_job, self._cfg_job, self._anim_job, self._guide_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._hq_job = self._cfg_job = self._anim_job = self._guide_job = None
        if self.studio is not None and self.studio._job is not None:
            try:
                self.studio.after_cancel(self.studio._job)
            except tk.TclError:
                pass
        super().destroy()

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
                    f"Squeak! You asked for {copies} copies but only {free} spot"
                    f"{' is' if free == 1 else 's are'} free.\n\n"
                    f"Is it okay if I only add {free}?", parent=self,
                    ok="Okay, add them", cancel="Go back"):
                return
        copies = max(1, min(self.max_copies, copies)) if self.max_copies > 0 else 1
        ring = self.cur_ring() if self.v_ring.get() else None
        self.result = (self.zoom, self.cx, self.cy, self.v_angle.get(), copies,
                       self.flipped, ring)
        self.destroy()
