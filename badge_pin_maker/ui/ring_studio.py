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
from .widgets import FlatSlider, Segmented, Toggle

THUMB = 56          # size of a style / material preview, in pixels


class _Chips(tk.Frame):
    """A grid of small previews with a caption each; one can be marked as the current one."""

    def __init__(self, parent, items, cols, on_pick):
        super().__init__(parent, bg=T.CARD)
        self.on_pick = on_pick
        self._cells = {}
        for n, (ident, label) in enumerate(items):
            cell = tk.Frame(self, bg=T.CARD, highlightthickness=2, width=THUMB + 22,
                            height=THUMB + 34, highlightbackground=T.CARD, cursor="hand2")
            cell.grid(row=n // cols, column=n % cols, padx=2, pady=2)
            cell.pack_propagate(False)
            pic = tk.Label(cell, bg=T.CARD, width=THUMB, height=THUMB, bd=0)
            pic.pack(pady=(4, 0))
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
    """The Ring page of the crop window's side panel. ``dlg`` is the crop window. While the
    ring is off it shows a short invitation; once it is on, the whole studio."""

    def __init__(self, parent, dlg):
        super().__init__(parent, bg=T.CARD)
        self.dlg = dlg
        self._job = None

        # ---- off: a friendly empty state
        self.empty = tk.Frame(self, bg=T.CARD)
        tk.Label(self.empty, text="Give your pin a border", bg=T.CARD, fg=T.PETROL,
                 font=("Georgia", 14, "bold")).pack(anchor="w", padx=18, pady=(26, 4))
        tk.Label(self.empty, bg=T.CARD, fg=T.MUTED, justify="left", wraplength=dlg.SIDE_W - 50,
                 text="A ring sits just inside the edge of the pin. Pick a style, a material "
                      "and a colour, or use one of your own pictures.").pack(
                          anchor="w", padx=18)
        ttk.Button(self.empty, text="Add a ring", style="Accent.TButton",
                   command=dlg.add_ring).pack(anchor="w", padx=18, pady=(16, 0))

        # ---- on: the header (switch + summary) and the scrolling body
        self.live = tk.Frame(self, bg=T.CARD)
        head = tk.Frame(self.live, bg=T.CARD)
        head.pack(side="top", fill="x", padx=18, pady=(10, 2))
        Toggle(head, dlg.v_ring, command=dlg._ring_toggled, bg=T.CARD).pack(side="left")
        tk.Label(head, text="Ring", bg=T.CARD, fg=T.TEXT,
                 font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=10)
        self.sum_lbl = ttk.Label(head, text="", style="Muted.TLabel")
        self.sum_lbl.pack(side="right")

        body = tk.Frame(self.live, bg=T.CARD)
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

        pad = dict(padx=18, fill="x")

        self._title("Style")
        self.cat = tk.StringVar(value=ring_mod.CATEGORIES[0])
        tabs = Segmented(self.inner, self.cat, [(c, c) for c in ring_mod.CATEGORIES],
                         command=self._tab, bg=T.CARD)
        tabs.pack(padx=18, fill="x")
        self.style_box = tk.Frame(self.inner, bg=T.CARD)
        self.style_box.pack(padx=14, pady=(8, 0), anchor="w")
        self.styles = {}
        for c in ring_mod.CATEGORIES:
            items = [(i, t[1]) for i, t in enumerate(ring_mod.THEMES) if t[0] == c]
            self.styles[c] = _Chips(self.style_box, items, 4, dlg.apply_theme)
        self.styles[self.cat.get()].pack()

        self._title("Material")
        self.mats = _Chips(self.inner, list(ring_mod.MATERIALS), 4,
                           lambda m: dlg.ring_change(material=m, image=None))
        self.mats.pack(padx=14, anchor="w")

        self._title("Colour")
        self.picker = RingPicker(self.inner, dlg.ring_col, dlg.palette(),
                                 lambda rgb: dlg.ring_change(col=rgb))
        self.picker.pack(padx=18, anchor="w")
        ttk.Button(self.inner, text="Match my picture", style="Soft.TButton",
                   command=dlg.match_picture).pack(padx=18, pady=(10, 0), anchor="w")

        self._title("Thickness")
        row = tk.Frame(self.inner, bg=T.CARD)
        row.pack(**pad)
        FlatSlider(row, dlg.v_ring_mm, dlg.r_lo, dlg.r_hi).pack(
            side="left", fill="x", expand=True)
        self.mm_lbl = ttk.Label(row, text="", style="Value.TLabel", width=7, anchor="e")
        self.mm_lbl.pack(side="right")

        self._title("Your own pattern")
        prow = tk.Frame(self.inner, bg=T.CARD)
        prow.pack(**pad)
        ttk.Button(prow, text="Choose image…", style="Soft.TButton",
                   command=self._choose_image).pack(side="left")
        self.rm_btn = ttk.Button(prow, text="Remove", style="Soft.TButton",
                                 command=lambda: dlg.ring_change(image=None))
        self.pat_lbl = ttk.Label(self.inner, text="", style="Muted.TLabel")
        self.pat_lbl.pack(padx=18, pady=(6, 0), anchor="w")
        self.scale_row = tk.Frame(self.inner, bg=T.CARD)
        self.scale_var = tk.DoubleVar(value=dlg.ring_scale)
        ttk.Label(self.scale_row, text="Pattern size", style="Card.TLabel").pack(side="left")
        FlatSlider(self.scale_row, self.scale_var, 0.08, 0.8,
                   command=lambda: dlg.ring_change(scale=self.scale_var.get())
                   ).pack(side="left", fill="x", expand=True, padx=(8, 0))
        tk.Frame(self.inner, bg=T.CARD, height=18).pack()
        self._bind_wheel(self.cv)
        self._show_state()

    def _title(self, text):
        """An upper-case section title."""
        f = tk.Frame(self.inner, bg=T.CARD)
        f.pack(fill="x", padx=18, pady=(18, 6))
        tk.Label(f, text=text.upper(), bg=T.CARD, fg=T.MUTED,
                 font=("TkDefaultFont", 8, "bold")).pack(anchor="w")

    def _show_state(self):
        """Show the studio while the ring is on, the invitation while it is off."""
        on = self.dlg.v_ring.get()
        if on:
            if not self.live.winfo_manager():
                self.empty.pack_forget()
                self.live.pack(fill="both", expand=True)
                self.picker.set_palette(self.dlg.palette())
                self._key = None
        else:
            self.live.pack_forget()
            self.empty.pack(fill="both", expand=True)

    def _bind_wheel(self, widget):
        """Let the mouse wheel scroll the panel from anywhere on it (chips, sliders and all)."""
        widget.bind("<MouseWheel>", self._wheel, add="+")
        widget.bind("<Button-4>", lambda e: self.cv.yview_scroll(-2, "units"), add="+")
        widget.bind("<Button-5>", lambda e: self.cv.yview_scroll(2, "units"), add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _wheel(self, e):
        self.cv.yview_scroll(-2 if e.delta > 0 else 2, "units")
        return "break"

    def _choose_image(self):
        path = filedialog.askopenfilename(
            parent=self.dlg, title="Choose a pattern image",
            filetypes=[("Images", " ".join(f"*{e}" for e in IMG_EXTS)), ("All files", "*.*")])
        if path:
            self.dlg.ring_change(image=path)

    # ---- keeping the panel in step with the ring ---------------------------------
    def _tab(self, *_):
        """Another style category was chosen."""
        for c, chips in self.styles.items():
            chips.pack_forget()
        self.styles[self.cat.get()].pack()
        self._thumbs(force=True)

    def sync(self):
        """Update the labels, the current mark and the previews (soon, so that dragging a
        slider stays smooth)."""
        d = self.dlg
        self._show_state()
        if not d.v_ring.get():
            return
        self.mm_lbl.config(text=f"{d._ring_mm():.1f} mm")
        mat = "Your pattern" if d.ring_image else ring_mod.MATERIAL_NAMES.get(d.ring_material, "")
        self.sum_lbl.config(text=f"{mat} · {d._ring_mm():.1f} mm")
        self.picker.set_colour(d.ring_col)
        # one mark at a time: the tapped style, else the material in use
        for chips in self.styles.values():
            chips.select(d.theme_id)
        self.mats.select(None if (d.ring_image or d.theme_id is not None) else d.ring_material)
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
        self._job = self.after(120, self._thumbs)

    def refresh(self):
        """Redraw everything (the page was just opened)."""
        d = self.dlg
        if d.theme_id is not None:
            self.cat.set(ring_mod.THEMES[d.theme_id][0])
            self._tab()
        self.picker.set_palette(d.palette())
        self._key = None
        self.sync()

    _key = None

    def _thumbs(self, force=False):
        """Draw the visible styles and the materials on the pin's own picture. Only redone when
        the picture, colour or thickness changed, so picking things does not flicker.
        """
        self._job = None
        d = self.dlg
        src = d.view_picture()
        if src is None or not self.winfo_ismapped():
            self._key = None
            return
        key = (d.ring_col, round(d._ring_mm(), 1), self.cat.get())
        if key == self._key and not force:
            return
        self._key = key
        fw, fh, w, h = d.pin["fw"], d.pin["fh"], d.d, d.dh
        k = THUMB / max(w, h)
        tw, th = max(8, round(w * k)), max(8, round(h * k))
        base = src.resize((tw * 2, th * 2), Image.BILINEAR)
        lo, hi = ring_mod.limits(fw, fh)
        mm = min(hi, max(lo * 1.4, d._ring_mm() * 1.6))
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

        for i, (cat, _n, mat, col, share) in enumerate(ring_mod.THEMES):
            if cat == self.cat.get():
                self.styles[cat].set_image(i, thumb(ring_mod.Ring(
                    min(hi, mm * share), col, mat)))
        for ident, _label in ring_mod.MATERIALS:
            self.mats.set_image(ident, thumb(ring_mod.Ring(mm, d.ring_col, ident)))
