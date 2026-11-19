"""The Ring Studio: a side panel in the crop window for styling the ring.

From top to bottom: one-click styles, materials, colour (hue, lightness, picture colours),
thickness, and your own pattern image. Every change shows live on the pin next to it. The
panel only edits the crop window's ring state (``dlg.ring_change`` / ``dlg.apply_theme``).
"""

import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from .. import ring as ring_mod
from ..constants import IMG_EXTS
from . import theme as T
from .ring_picker import RingPicker
from .widgets import FlatSlider

THUMB = 56          # size of a style / material preview, in pixels


class _Chips(tk.Frame):
    """A grid of small previews with a caption each; one can be marked as the current one."""

    def __init__(self, parent, items, cols, on_pick):
        super().__init__(parent, bg=T.CARD)
        self.on_pick = on_pick
        self._cells = {}
        for n, (ident, label) in enumerate(items):
            cell = tk.Frame(self, bg=T.CARD, highlightthickness=2,
                            highlightbackground=T.CARD, cursor="hand2")
            cell.grid(row=n // cols, column=n % cols, padx=3, pady=3, sticky="n")
            pic = tk.Label(cell, bg=T.CARD, width=THUMB, height=THUMB, bd=0)
            pic.pack(padx=3, pady=(3, 0))
            cap = tk.Label(cell, text=label, bg=T.CARD, fg=T.TEXT, font=("TkDefaultFont", 8))
            cap.pack(pady=(0, 3))
            for w in (cell, pic, cap):
                w.bind("<Button-1>", lambda e, i=ident: self.on_pick(i))
            self._cells[ident] = (cell, pic)
        self._imgs = {}

    def set_image(self, ident, img):
        """Show ``img`` (a PIL image) as the preview of one chip."""
        ph = ImageTk.PhotoImage(img)
        self._imgs[ident] = ph
        cell, pic = self._cells[ident]
        pic.config(image=ph, width=THUMB, height=THUMB)

    def select(self, ident):
        """Outline one chip (None clears the outline)."""
        for i, (cell, _pic) in self._cells.items():
            cell.config(highlightbackground=T.TEAL if i == ident else T.CARD)


class RingStudio(tk.Frame):
    """The panel. ``dlg`` is the crop window it belongs to."""
    W = 352

    def __init__(self, parent, dlg):
        super().__init__(parent, bg=T.CARD, highlightthickness=1,
                         highlightbackground=T.BORDER)
        self.dlg = dlg
        self._job = None
        self.configure(width=self.W)
        self.pack_propagate(False)

        head = tk.Frame(self, bg=T.CARD)
        head.pack(side="top", fill="x", padx=14, pady=(12, 4))
        tk.Label(head, text="Ring style", bg=T.CARD, fg=T.PETROL,
                 font=("Georgia", 13, "bold")).pack(side="left")
        ttk.Button(head, text="Done", style="Accent.TButton", command=dlg.studio_close
                   ).pack(side="right")

        # the scrolling body
        body = tk.Frame(self, bg=T.CARD)
        body.pack(side="top", fill="both", expand=True)
        self.cv = tk.Canvas(body, bg=T.CARD, highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=T.CARD)
        self._win = self.cv.create_window(0, 0, anchor="nw", window=self.inner)
        self.inner.bind("<Configure>", lambda e: self.cv.configure(
            scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        for w in (self.cv, self.inner):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", lambda e: self.cv.yview_scroll(-2, "units"))
            w.bind("<Button-5>", lambda e: self.cv.yview_scroll(2, "units"))

        pad = dict(padx=14, fill="x")

        self._title("Styles", "One tap, then tweak anything below")
        self.styles = _Chips(self.inner, [(i, t[0]) for i, t in enumerate(ring_mod.THEMES)],
                             4, dlg.apply_theme)
        self.styles.pack(padx=8, anchor="w")

        self._title("Material")
        self.mats = _Chips(self.inner, list(ring_mod.MATERIALS), 4,
                           lambda m: dlg.ring_change(material=m, image=None))
        self.mats.pack(padx=8, anchor="w")

        self._title("Colour", "Drag the strips, or tap a colour from your picture")
        self.picker = RingPicker(self.inner, dlg.ring_col, dlg.palette(),
                                 lambda rgb: dlg.ring_change(col=rgb))
        self.picker.pack(padx=14, anchor="w")
        ttk.Button(self.inner, text="Match my picture", style="Soft.TButton",
                   command=dlg.match_picture).pack(padx=14, pady=(8, 0), anchor="w")

        self._title("Thickness")
        row = tk.Frame(self.inner, bg=T.CARD)
        row.pack(**pad)
        FlatSlider(row, dlg.v_ring_mm, dlg.r_lo, dlg.r_hi).pack(
            side="left", fill="x", expand=True)
        self.mm_lbl = ttk.Label(row, text="", style="Value.TLabel", width=7, anchor="e")
        self.mm_lbl.pack(side="right")

        self._title("Your own pattern", "Use any picture as the ring")
        prow = tk.Frame(self.inner, bg=T.CARD)
        prow.pack(**pad)
        ttk.Button(prow, text="Choose image…", style="Soft.TButton",
                   command=self._choose_image).pack(side="left")
        self.rm_btn = ttk.Button(prow, text="Remove", style="Soft.TButton",
                                 command=lambda: dlg.ring_change(image=None))
        self.pat_lbl = ttk.Label(self.inner, text="", style="Muted.TLabel")
        self.pat_lbl.pack(padx=14, pady=(6, 0), anchor="w")
        self.scale_row = tk.Frame(self.inner, bg=T.CARD)
        self.scale_var = tk.DoubleVar(value=dlg.ring_scale)
        ttk.Label(self.scale_row, text="Pattern size", style="Card.TLabel").pack(side="left")
        FlatSlider(self.scale_row, self.scale_var, 0.08, 0.8,
                   command=lambda: dlg.ring_change(scale=self.scale_var.get())
                   ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        tk.Frame(self.inner, bg=T.CARD, height=10).pack()
        ttk.Button(self.inner, text="Remove ring", style="Soft.TButton",
                   command=dlg.ring_off).pack(padx=14, pady=(4, 16), anchor="w")

    def _title(self, text, hint=""):
        f = tk.Frame(self.inner, bg=T.CARD)
        f.pack(fill="x", padx=14, pady=(14, 4))
        tk.Label(f, text=text, bg=T.CARD, fg=T.TEXT, font=("TkDefaultFont", 10, "bold")
                 ).pack(anchor="w")
        if hint:
            tk.Label(f, text=hint, bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8)
                     ).pack(anchor="w")

    def _wheel(self, e):
        self.cv.yview_scroll(-2 if e.delta > 0 else 2, "units")

    def _choose_image(self):
        path = filedialog.askopenfilename(
            parent=self.dlg, title="Choose a pattern image",
            filetypes=[("Images", " ".join(f"*{e}" for e in IMG_EXTS)), ("All files", "*.*")])
        if path:
            self.dlg.ring_change(image=path)

    # ---- keeping the panel in step with the ring ---------------------------------
    def sync(self):
        """Update the labels, the current marks and the previews (soon, so that dragging a
        slider stays smooth)."""
        d = self.dlg
        self.mm_lbl.config(text=f"{d._ring_mm():.1f} mm")
        self.picker.set_colour(d.ring_col)
        self.mats.select(None if d.ring_image else d.ring_material)
        self.styles.select(self._current_theme())
        if d.ring_image:
            ppi = ring_mod.pattern_ppi(d.cur_ring(), d.pin["fw"], d.pin["fh"])
            soft = ppi is not None and ppi < 150
            self.pat_lbl.config(
                text=(f"{ppi:.0f} dpi · " + ("may print soft, try a bigger image or size"
                                              if soft else "sharp")) if ppi else "")
            self.rm_btn.pack(side="left", padx=(8, 0))
            self.scale_row.pack(fill="x", padx=14, pady=(8, 0), after=self.pat_lbl)
        else:
            self.pat_lbl.config(text="")
            self.rm_btn.pack_forget()
            self.scale_row.pack_forget()
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(90, self._thumbs)

    def _current_theme(self):
        d = self.dlg
        if d.ring_image:
            return None
        for i, (_n, mat, col, _s) in enumerate(ring_mod.THEMES):
            col = col or (d.palette()[0] if d.palette() else None)
            if mat == d.ring_material and tuple(col or ()) == tuple(d.ring_col):
                return i
        return None

    def refresh(self):
        """Redraw everything (the panel was just opened)."""
        self.picker.set_palette(self.dlg.palette())
        self.sync()

    def _thumbs(self):
        """Draw each style and material on the pin's own picture."""
        self._job = None
        d = self.dlg
        src = d.view_picture()
        if src is None:
            return
        fw, fh, w, h = d.pin["fw"], d.pin["fh"], d.d, d.dh
        k = THUMB / max(w, h)
        tw, th = max(8, round(w * k)), max(8, round(h * k))
        base = src.resize((tw * 2, th * 2), Image.BILINEAR)
        lo, hi = ring_mod.limits(fw, fh)
        mm = min(hi, max(lo * 1.4, d._ring_mm() * 1.6))
        pal = d.palette()
        outline = ring_mod.mask(d.shape, w, h, 0, (tw * 2, th * 2), tw * 2 / w, th * 2 / h,
                                tw, th)

        def thumb(ring):
            im = ring_mod.apply(base, ring, d.shape, fw, fh, w, h)
            card = Image.new("RGB", im.size, T.CARD)
            card.paste(im, (0, 0), outline)
            canvas = Image.new("RGB", (THUMB * 2, THUMB * 2), T.CARD)
            canvas.paste(card, ((THUMB * 2 - card.size[0]) // 2,
                                (THUMB * 2 - card.size[1]) // 2))
            return canvas.resize((THUMB, THUMB), Image.LANCZOS)

        for i, (_n, mat, col, share) in enumerate(ring_mod.THEMES):
            col = col or (pal[0] if pal else (120, 120, 120))
            self.styles.set_image(i, thumb(ring_mod.Ring(
                min(hi, mm * share), col, mat)))
        for ident, _label in ring_mod.MATERIALS:
            self.mats.set_image(ident, thumb(ring_mod.Ring(mm, d.ring_col, ident)))
