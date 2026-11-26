"""The window where you position an image under the pin shape."""

import math
import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

from .. import filters as filters_mod
from .. import ring as ring_mod
from .. import shapes
from ..constants import LOW_PPI
from ..imaging import Art, base_crop, ppi_for, render_transform
from . import smooth
from . import theme as T
from .dialogs import messagebox, set_titlebar, set_window_icon
from .buttons import Btn
from .filter_studio import FilterStudio
from .preview_dialog import PreviewDialog
from .ring_card import FilterCard, RingCard
from .ring_studio import RingStudio
from .tabs import PillTabs
from .tiles import ScrollPage
from .widgets import FlatSlider


_KEEP = object()        # "leave the current style alone"


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
    SIDE_W = 400                 # width of the side panel
    FIN_W, FIN_H, FIN_PIN = 168, 208, 124    # the floating "Final pin" card
    CORNER = 26                              # rounded corners of the picture stage
    last_ring = None
    last_filter = None             # (ring, pick) of the last crop, offered again next time

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
        had = ring_mod.as_ring(art.ring) if art else None
        self.ring_style = had.style if had and had.style in ring_mod.STYLE_NAMES else "solid"
        self.v_ring = tk.BooleanVar(value=bool(had))
        self.v_ring_mm = tk.DoubleVar(value=ring_mod.clamp(
            had.mm if had else ring_mod.default_mm(pin["fw"], pin["fh"]),
            pin["fw"], pin["fh"], self.ring_style))
        self.ring_col = tuple(had.col) if had else (128, 128, 128)
        self.ring_col2 = tuple(had.col2) if had and had.col2 else None   # None = automatic
        self.ring_image = had.image if had else None
        self.ring_scale = had.scale if had else 0.3
        # how the custom pattern image is laid out (see ring.Ring)
        self.ring_pat = dict(mode=had.mode, ox=had.ox, oy=had.oy, rot=had.rot,
                             tint=had.tint) if had else dict(mode="tile", ox=0.0, oy=0.0,
                                                             rot=0.0, tint=0.0)
        self.pick_id = None                  # which recommendation was tapped last (None once tweaked)
        self._picks = None
        self._stale = {"frame", "filter", "ring"}     # pages that need repainting
        # the filter (optional): name None = off
        had_f = filters_mod.as_filter(art.filter) if art else None
        self.f_name = had_f.name if had_f else None
        self.f_amount = had_f.amount if had_f else 0.7
        self._f_touched = bool(had_f)        # True once the intensity was set by hand
        self.v_f_amount = tk.DoubleVar(value=self.f_amount)
        self._compare = False                # True while "hold to compare" is pressed
        self._fpicks = None
        self._raw = None                     # the picture without filter or ring, as last drawn
        self.fstudio = None
        self._tmasks = {}
        self._palette = []
        self._plain = None                   # the picture without the ring, as last drawn
        self.studio = None                   # the Ring page (built with the side panel)
        self._ring_styled = bool(had)        # True once the ring has been styled
        self._bold = tkfont.nametofont("TkDefaultFont").copy()
        self._bold.configure(weight="bold")

        # picture area size and the fixed viewport (the pin) in the middle of it
        self.cw, self.ch = self.CW, self.CH

        # ---- the side panel (right): Frame / Ring tabs, and the buttons that finish the job
        side = tk.Frame(self, bg=T.BG)
        side.pack(side="right", fill="y", padx=(0, 20), pady=20)
        edge = tk.Frame(side, bg=T.BORDER)
        edge.pack(fill="both", expand=True)
        panel = tk.Frame(edge, bg=T.CARD, width=self.SIDE_W)
        panel.pack(fill="both", expand=True, padx=1, pady=1)
        panel.pack_propagate(False)

        self.v_tab = tk.StringVar(value="frame")
        self.tabs = PillTabs(panel, self.v_tab, [("frame", "Frame"), ("filter", "Filter"), ("ring", "Ring")],
                              command=self._tab_changed, bg=T.CARD)
        self.tabs.pack(fill="x", padx=18, pady=(18, 6))

        # the action bar is packed before the pages so it always stays visible
        act = tk.Frame(panel, bg=T.CARD)
        act.pack(side="bottom", fill="x", padx=18, pady=(8, 18))
        tk.Frame(panel, bg=T.BORDER, height=1).pack(side="bottom", fill="x")
        if max_copies > 0:
            crow = tk.Frame(act, bg=T.CARD)
            crow.pack(fill="x", pady=(0, 12))
            ttk.Label(crow, text="Copies", style="Card.TLabel").pack(side="left")
            ttk.Spinbox(crow, from_=1, to=max_copies, textvariable=self.v_copies,
                        width=5).pack(side="left", padx=8)
            ttk.Label(crow, text=f"of {max_copies} free spot{'s' if max_copies != 1 else ''}",
                      style="Muted.TLabel").pack(side="left")
        brow = tk.Frame(act, bg=T.CARD)
        brow.pack(fill="x")
        if batch and batch[1] > 1:
            Btn(brow, "Stop", self.on_stop, height=42).pack(side="left")
            Btn(brow, "Skip", self.destroy, height=42).pack(side="left", padx=(6, 0))
        else:
            Btn(brow, "Cancel", self.destroy, height=42).pack(side="left")
        Btn(brow, "Continue", self.on_ok, kind="accent", height=42
            ).pack(side="right", fill="x", expand=True, padx=(10, 0))

        pages = tk.Frame(panel, bg=T.CARD)
        pages.pack(side="top", fill="both", expand=True)

        # -- Frame page: zoom, rotate and the quick buttons
        self.page_frame = ScrollPage(pages)
        f = self.page_frame.inner
        self.zoom_lbl = self._section(f, "Zoom", "100%")
        zr = tk.Frame(f, bg=T.CARD)
        zr.pack(fill="x", padx=18)
        zr.columnconfigure(1, weight=1)
        Btn(zr, icon="minus", command=lambda: self.zoom_by(1 / self.WHEEL_STEP)
            ).grid(row=0, column=0)
        FlatSlider(zr, self.v_zoom, math.log(self.zmin), math.log(self.zmax),
                   origin=math.log(self.zmin), snaps=(0.0,), snap_tol=0.025,
                   command=self._stop_anim).grid(row=0, column=1, sticky="ew", padx=10)
        Btn(zr, icon="plus", command=lambda: self.zoom_by(self.WHEEL_STEP)
            ).grid(row=0, column=2)
        self.angle_lbl = self._section(f, "Rotate", "0°")
        rr = tk.Frame(f, bg=T.CARD)
        rr.pack(fill="x", padx=18)
        rr.columnconfigure(1, weight=1)
        Btn(rr, "90°", lambda: self.rotate_by(-90), icon="rot_l", width=78
            ).grid(row=0, column=0)
        FlatSlider(rr, self.v_angle, -180, 180, origin=0, snaps=(-180, -90, 0, 90, 180),
                   snap_tol=3).grid(row=0, column=1, sticky="ew", padx=10)
        Btn(rr, "90°", lambda: self.rotate_by(90), icon="rot_r", width=78
            ).grid(row=0, column=2)
        self._section(f, "Quick fixes")
        grid = tk.Frame(f, bg=T.CARD)
        grid.pack(fill="x", padx=18)
        grid.columnconfigure((0, 1), weight=1, uniform="quick")
        # "Fit" only differs from "Fill" when the picture is not the pin's shape; if they would
        # do the same thing it is greyed out instead of pretending to be a second choice
        self.btn_fit = Btn(grid, "Fit", self.fit, icon="fit")
        same = self.fit_zoom >= 0.97
        if same:
            self.btn_fit.configure(state="disabled")
        for n, (w, span) in enumerate((
                (Btn(grid, "Fill", self.fill, icon="fill"), 1), (self.btn_fit, 1),
                (Btn(grid, "Centre", self.centre, icon="centre"), 1),
                (Btn(grid, "Flip", self.flip_h, icon="flip"), 1),
                (Btn(grid, "Reset all", self.reset, icon="reset"), 2))):
            w.grid(row=n // 2, column=n % 2 if span == 1 else 0, columnspan=span,
                   sticky="ew", padx=3, pady=3)
        self.fit_note = tk.Label(
            f, text="Fit is off: your picture already matches the pin's shape, so Fill shows all of it."
            if same else "Fill covers the pin. Fit shows the whole picture inside it.",
            bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8), wraplength=self.SIDE_W - 50,
            justify="left")
        self.fit_note.pack(anchor="w", padx=18, pady=(4, 0))
        self._section(f, "Look")
        self.filter_card = FilterCard(f, self, on_open=lambda: self._open_tab("filter"))
        self.filter_card.open_label = "Looks ›"
        self.filter_card.pack(fill="x", padx=18)
        self.frame_card = RingCard(f, self, on_open=lambda: self._open_tab("ring"))
        self.frame_card.pack(fill="x", padx=18, pady=(8, 0))
        tk.Label(f, text="Tip: double-click the picture to switch between Fill and Fit.",
                 bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8), wraplength=self.SIDE_W - 50,
                 justify="left").pack(anchor="w", padx=18, pady=(14, 18))
        self.page_frame.bind_wheel()

        # -- Filter page
        self.fstudio = FilterStudio(pages, self)
        self.page_filter = self.fstudio

        # -- Ring page
        self.v_ring_mm.trace_add("write", lambda *_: self._ring_slid())
        self.studio = RingStudio(pages, self)
        self.page_ring = self.studio
        self.page_frame.pack(fill="both", expand=True)

        # ---- the main area (left): title, the picture and a hint line
        main = tk.Frame(self, bg=T.BG)
        main.pack(side="left", fill="both", expand=True, padx=(20, 14), pady=(16, 14))
        head = self._head = tk.Frame(main, bg=T.BG)
        head.pack(side="top", fill="x", pady=(0, 10))
        titles = ttk.Frame(head)
        titles.pack(side="left")
        ttk.Label(titles, text="Edit your pin", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(titles, text=f"{self._d_text()}  ·  the pin stays put, "
                               "the picture moves", style="Sub.TLabel").pack(anchor="w")
        self.q_pill = tk.Label(head, bg=T.CARD, fg=T.TEAL, font=self._bold, padx=12, pady=5,
                               highlightthickness=1, highlightbackground=T.BORDER)
        self.q_pill.pack(side="right")
        Btn(head, "Preview", self.preview, icon="eye", kind="ghost", bg=T.BG, height=34
            ).pack(side="right", padx=(0, 10))
        ttk.Label(main, style="Hint.TLabel", justify="left",
                  text="Drag to move  ·  scroll to zoom  ·  arrow keys nudge  ·  "
                       "bright = visible on the pin, shaded = folds behind"
                  ).pack(side="bottom", anchor="w", pady=(10, 0))
        self.mid = tk.Frame(main, bg=T.BG)
        self.mid.pack(side="top", fill="both", expand=True)
        stage = tk.Frame(self.mid, bg=T.BG)
        stage.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(stage, width=self.CW, height=self.CH, bg=T.BG,
                            highlightthickness=0, cursor="fleur")
        self.cv.pack(fill="both", expand=True)
        self._fin_img = []
        self._face_mask = None

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

        # fill the whole screen (maximised); F11 switches true full screen on and off
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.minsize(min(900, sw), min(620, sh))
        self.geometry(f"{sw}x{sh - 70}+0+0")
        self.bind("<F11>", self._toggle_fullscreen)
        set_titlebar(self)
        self.deiconify()
        self._maximise()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()
        self._badges()

    # ---- helpers
    def _section(self, parent, title, value=None):
        """A small upper-case section title with an optional value on its right. Returns the
        value label (or None)."""
        row = tk.Frame(parent, bg=T.CARD)
        row.pack(fill="x", padx=18, pady=(18, 6))
        tk.Label(row, text=title.upper(), bg=T.CARD, fg=T.MUTED,
                 font=("TkDefaultFont", 8, "bold")).pack(side="left")
        if value is None:
            return None
        lbl = ttk.Label(row, text=value, style="Value.TLabel", anchor="e")
        lbl.pack(side="right")
        return lbl

    def _open_tab(self, name):
        """Go to the Frame, Filter or Ring page."""
        self.v_tab.set(name)
        self._tab_changed()

    def _notify(self, *pages):
        """The one way a change (ring, filter) tells the pages about it: the page on screen is
        brought up to date now, the others are only marked stale and catch up when opened. This
        keeps the pages from repainting each other (and their previews) several times over.
        """
        self._stale |= set(pages)
        self._refresh_page()
        self._badges()

    def _sync_ring_ui(self):
        """The ring changed."""
        self._notify("frame", "ring")

    def _refresh_page(self):
        """Repaint the visible page if something changed since it was last painted."""
        want = self.v_tab.get()
        if want in self._stale:
            self._stale.discard(want)
            if want == "ring":
                self.studio.sync()
            elif want == "filter":
                self.fstudio.sync()
            else:
                self.frame_card.refresh()
                self.filter_card.refresh()

    def _badges(self):
        """A glowing dot on the Filter / Ring tabs while those are in use."""
        for name, on in (("filter", self.f_name is not None), ("ring", bool(self.v_ring.get()))):
            self.tabs.set_badge(name, on)

    def _tab_changed(self):
        """Show the Frame, Filter or Ring page."""
        want = self.v_tab.get()
        for name, page in (("frame", self.page_frame), ("filter", self.page_filter),
                           ("ring", self.page_ring)):
            if name == want:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        if want == "ring":
            self.refresh_picks()
            self._stale.discard("ring")
            self.studio.refresh()
        elif want == "filter":
            self._fpicks = None
            self._stale.discard("filter")
            self.fstudio.refresh()
        else:
            self._refresh_page()

    def _maximise(self):
        """Make the window fill the screen (where the system can)."""
        for attempt in (lambda: self.state("zoomed"),
                        lambda: self.attributes("-zoomed", True)):
            try:
                attempt()
                return
            except tk.TclError:
                continue

    def _toggle_fullscreen(self, _e=None):
        """F11: true full screen (no title bar) on and off."""
        try:
            self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        except tk.TclError:
            pass

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
        # rounded stage corners: painted in the page colour by the dimming layer itself
        k = 3
        rm = Image.new("L", (cw * k, ch * k), 0)
        ImageDraw.Draw(rm).rounded_rectangle([0, 0, cw * k - 1, ch * k - 1],
                                             radius=self.CORNER * k, fill=255)
        rm = rm.resize(size, Image.LANCZOS)
        self.alpha = Image.composite(self.alpha, Image.new("L", size, 255), rm)
        self.dim = Image.composite(self.dim, Image.new("RGB", size, T.BG), rm)
        # the finished face of the pin, cut out of the picture area (for the Final pin card)
        mx0, my0 = self.vx0 + self.vw / 2, self.vy0 + self.vh / 2
        self._face_box = (int(self.vx0), int(self.vy0), int(self.vx0 + self.vw),
                          int(self.vy0 + self.vh))
        full = ring_mod.mask(self.shape, self.pin["fw"], self.pin["fh"], 0, size,
                             self.vw / self.d, self.vh / self.dh, mx0, my0)
        self._face_mask = full.crop(self._face_box)
        self._fin_key = None

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

    def centre(self):
        """Move the picture so its middle is under the middle of the pin (zoom unchanged)."""
        self._stop_anim()
        self._recentre()
        self.update_view()

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
        self._raw = bright
        f = None if self._compare else self.cur_filter()
        if f is not None:
            bright = filters_mod.apply(bright, f)
        self._plain = bright
        if self.v_ring.get():
            bright = self._with_ring(bright)
        self._final_card(bright)
        if self.studio is not None and self.v_tab.get() == "ring":
            self.studio.soon()                  # the previews follow the picture
        elif self.fstudio is not None and self.v_tab.get() == "filter":
            self.fstudio.soon()
        final = Image.composite(self.dim, bright, self.alpha)
        self._image = ImageTk.PhotoImage(final)
        self.cv.itemconfigure(self._img_item, image=self._image)
        if self._hq_job is not None:
            self.after_cancel(self._hq_job)
            self._hq_job = None
        if fast:
            self._hq_job = self.after(160, self._render_sharp)

    def _final_card(self, picture):
        """Repaint the floating card with the pin as it will look when made."""
        if self._face_mask is None:
            return
        P = self.FIN_PIN
        box = self._face_box
        view = picture.convert("RGB").crop(box)
        k = P / max(view.size)
        sz = (max(8, round(view.size[0] * k)), max(8, round(view.size[1] * k)))
        mask = self._face_mask.resize(sz, Image.LANCZOS)
        face = Image.new("RGB", sz, T.CARD)
        face.paste(view.resize(sz, Image.BILINEAR), (0, 0), mask)
        W, H = self.FIN_W, self.FIN_H
        k4 = 3
        card = Image.new("RGBA", (W * k4, H * k4), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle(
            [0, 0, W * k4 - 1, H * k4 - 1], radius=22 * k4, fill=T.CARD, outline=T.BORDER,
            width=k4)
        card = card.resize((W, H), Image.LANCZOS)
        card.paste(face, ((W - sz[0]) // 2, (22 + H - 26 - sz[1]) // 2 + 4))
        ph = ImageTk.PhotoImage(card)
        x0, y0 = self.cv.winfo_width() - 18 - W, self.cv.winfo_height() - 18 - H
        self.cv.delete("fin")
        self.cv.create_image(x0, y0, anchor="nw", image=ph, tags="fin")
        self.cv.create_text(x0 + W / 2, y0 + 22, text="FINAL PIN", fill=T.MUTED,
                            font=("TkDefaultFont", 8, "bold"), tags="fin")
        self.cv.create_text(x0 + W / 2, y0 + H - 22, text=self._d_text(), fill=T.TEXT,
                            font=("TkDefaultFont", 9), tags="fin")
        self._fin_img = [ph]

    # ---- the ring -----------------------------------------------------------
    def _ring_mm(self):
        """The thickness now, held inside the allowed range."""
        return ring_mod.clamp(self.v_ring_mm.get(), self.pin["fw"], self.pin["fh"],
                              self.ring_style)

    def ring_limits(self):
        """(smallest, largest) thickness for the current style."""
        return ring_mod.limits(self.pin["fw"], self.pin["fh"], self.ring_style)

    def cur_ring(self):
        """The ring as it is now."""
        style = self.ring_style
        if style == "pattern" and not self.ring_image:
            style = "solid"
        return ring_mod.Ring(round(self._ring_mm(), 2), tuple(self.ring_col), style,
                             self.ring_image, self.ring_scale, self.ring_col2,
                             **self.ring_pat)

    def _with_ring(self, img):
        """``img`` (the picture area) with the ring painted over it."""
        mx, my = self.vx0 + self.vw / 2, self.vy0 + self.vh / 2
        surface, inside = ring_mod.layer(
            self.cur_ring(), self.shape, self.pin["fw"], self.pin["fh"], (self.cw, self.ch),
            self.vw / self.d, self.vh / self.dh, mx, my)
        return Image.composite(img.convert("RGB"), surface, inside)

    def view_picture(self, raw=False):
        """What is showing on the pin right now, for previews: with the filter but without the
        ring (``raw=True``: without the filter either).
        """
        pic = self._raw if raw else self._plain
        if pic is None:
            return None
        box = (int(self.vx0), int(self.vy0), int(self.vx0 + self.vw), int(self.vy0 + self.vh))
        return pic.crop(box).convert("RGB")

    def thumb(self, picture, size):
        """``picture`` (the pin's picture area) cut to the pin's shape, as a size x size preview
        on the panel colour.
        """
        w, h = self.d, self.dh
        k = size / max(w, h)
        tw, th = max(8, round(w * k)), max(8, round(h * k))
        mask = self._tmasks.get((tw, th))
        if mask is None:
            mask = self._tmasks[(tw, th)] = ring_mod.mask(
                self.shape, w, h, 0, (tw * 2, th * 2), tw * 2 / w, th * 2 / h, tw, th)
        base = picture.resize((tw * 2, th * 2), Image.BILINEAR)
        card = Image.new("RGB", base.size, T.CARD)
        card.paste(base, (0, 0), mask)
        canvas = Image.new("RGB", (size * 2, size * 2), T.CARD)
        canvas.paste(card, ((size * 2 - card.size[0]) // 2, (size * 2 - card.size[1]) // 2))
        return canvas.resize((size, size), Image.LANCZOS)

    def current_art(self):
        """An ``Art`` with everything as it is now (for the preview window)."""
        return Art(self.src, self.zoom, self.cx, self.cy, self.v_angle.get(), self.flipped,
                   self.cur_ring() if self.v_ring.get() else None, self.cur_filter())

    def preview(self):
        """Open the realistic scene window with the pin as designed so far."""
        PreviewDialog(self, [("This pin", self.current_art())], [0], self.pin)

    # ---- the filter ---------------------------------------------------------
    def cur_filter(self):
        """The filter as it is now (None when off)."""
        if self.f_name is None:
            return None
        return filters_mod.Filter(self.f_name, round(self.f_amount, 3))

    def amount_for(self, name):
        """The intensity a look gets when tapped: the one set by hand, else its own default."""
        return self.f_amount if self._f_touched else filters_mod.DEFAULTS[name]

    def filter_picks(self):
        """Looks that suit the picture now showing: [(id, amount)], best first."""
        if self._fpicks is None:
            pic = self.view_picture(raw=True)
            if pic is None:
                return []
            self._fpicks = filters_mod.recommend(pic)
        return self._fpicks

    def filter_set(self, name):
        """Use look ``name`` (None = no filter) at the right intensity."""
        self.f_name = name
        if name is not None:
            self.f_amount = self.amount_for(name)
            self.v_f_amount.set(self.f_amount)
        self._after_filter()

    def filter_change(self, amount):
        """The intensity slider moved."""
        if self.f_name is None:
            return
        self.f_amount = max(0.05, min(1.0, float(amount)))
        self._f_touched = True
        self._after_filter()

    def filter_toggle(self):
        """The filter switch: off, or on with the last used look (else the best pick)."""
        if self.f_name is not None:
            return self.filter_set(None)
        last = CropDialog.last_filter
        if last is not None:
            self._f_touched = True
            self.f_amount = last.amount
            self.filter_set(last.name)
            return
        picks = self.filter_picks()
        self.filter_set(picks[0][0] if picks else "pop")

    def compare(self, on):
        """Show the untouched picture while "hold to compare" is pressed."""
        if on != self._compare:
            self._compare = on
            self.update_view(fast=False)

    def _after_filter(self):
        """Show a filter change, and tell the ring (its colours come from the filtered picture)."""
        self._palette = []
        self._picks = None
        self.update_view()
        self._notify("frame", "filter", "ring")

    def palette(self):
        """The main colours of what shows on the pin (best ring colour first)."""
        if not self._palette:
            pic = self.view_picture()
            if pic is not None:
                self._palette = ring_mod.dominant_colours(pic)
        return self._palette

    def _ring_slid(self):
        """The thickness slider moved."""
        self.update_view()
        self._sync_ring_ui()

    def _ring_toggled(self):
        """The ring switch was clicked. Switching on picks a colour that suits the picture."""
        if self.v_ring.get() and not self._ring_styled:
            last = CropDialog.last_ring
            if last:                     # the same ring as the last pin: quick for a whole set
                r, pick = last
                keep = r.image if r.image and os.path.isfile(r.image) else None
                self.ring_change(_pick=pick, style=r.style if keep or r.style != "pattern"
                                 else "solid", col=r.col, col2=r.col2, image=keep,
                                 scale=r.scale, mm=r.mm, mode=r.mode, ox=r.ox, oy=r.oy,
                                 rot=r.rot, tint=r.tint)
            else:                        # the best recommendation for this picture
                self.apply_pick(0)
        self._sync_ring_ui()
        self.update_view(fast=False)

    def add_ring(self):
        """The "Add a ring" button: switch the ring on."""
        self.v_ring.set(True)
        self._ring_toggled()

    def picks(self):
        """The recommended rings for the picture now showing: [(label, Ring)], best first."""
        if self._picks is None:
            pic = self.view_picture()
            if pic is None:
                return []
            self._picks = ring_mod.recommend(pic, self.pin["fw"], self.pin["fh"])
        return self._picks

    def refresh_picks(self):
        """Forget the recommendations (the picture moved), so they are made afresh."""
        self._picks = None
        self._palette = []

    def apply_pick(self, i):
        """Use recommendation ``i`` (also switches the ring on)."""
        picks = self.picks()
        if not picks:
            return
        r = picks[i][1]
        self.ring_change(_pick=i, style=r.style, col=r.col, col2=r.col2, image=None, mm=r.mm)

    def ring_change(self, _pick=_KEEP, **kw):
        """Change part of the ring (style=, col=, col2=, image=, scale=, mm=) and show it. The
        recommendation that was tapped stays marked until something else is changed by hand.
        """
        if _pick is not _KEEP:
            self.pick_id = _pick
        elif kw.keys() - {"mm", "scale", "mode", "ox", "oy", "rot", "tint", "reset_pattern"}:
            self.pick_id = None
        if "style" in kw:
            self.ring_style = kw["style"]
        if "col" in kw:
            self.ring_col = tuple(kw["col"])
        if "col2" in kw:
            self.ring_col2 = tuple(kw["col2"]) if kw["col2"] else None
        if "image" in kw:
            self.ring_image = kw["image"]
        if "scale" in kw:
            self.ring_scale = float(kw["scale"])
        for k in ("mode", "ox", "oy", "rot", "tint"):
            if k in kw:
                self.ring_pat[k] = kw[k]
        if kw.get("reset_pattern"):
            self.ring_scale = 0.3
            self.ring_pat = dict(mode="tile", ox=0.0, oy=0.0, rot=0.0, tint=0.0)
        if "mm" in kw:
            self.v_ring_mm.set(ring_mod.clamp(kw["mm"], self.pin["fw"], self.pin["fh"],
                                              self.ring_style))
        elif "style" in kw:                  # keep the thickness inside the style's range
            self.v_ring_mm.set(self._ring_mm())
        self._ring_styled = True
        if not self.v_ring.get():
            self.v_ring.set(True)
        self.update_view()
        self._sync_ring_ui()

    def ring_off(self):
        """Remove the ring."""
        self.v_ring.set(False)
        self._ring_toggled()

    def _escape(self, _e=None):
        """Escape leaves true full screen first, then closes the window."""
        try:
            if self.attributes("-fullscreen"):
                self.attributes("-fullscreen", False)
                return
        except tk.TclError:
            pass
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
        if self.fstudio is not None and self.fstudio._job is not None:
            try:
                self.fstudio.after_cancel(self.fstudio._job)
            except tk.TclError:
                pass
            self.fstudio._job = None
        if self.studio is not None and self.studio._job is not None:
            try:
                self.studio.after_cancel(self.studio._job)
            except tk.TclError:
                pass
            self.studio._job = None
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
        if ring:
            CropDialog.last_ring = (ring, self.pick_id)
        filt = self.cur_filter()
        if filt:
            CropDialog.last_filter = filt
        self.result = (self.zoom, self.cx, self.cy, self.v_angle.get(), copies,
                       self.flipped, ring, filt)
        self.destroy()
