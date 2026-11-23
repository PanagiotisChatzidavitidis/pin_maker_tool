"""The Ring page of the crop window's side panel.

Top to bottom: the ring switch, rings recommended for this very picture (live previews, one tap),
the eight print-ready styles, colours (taken from the picture, plus classics and foils), thickness
and, for your own pattern, the image. Everything shows live on the pin beside it. The panel only
edits the crop window's ring state (``dlg.ring_change`` / ``dlg.apply_pick``).
"""

import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from .. import ring as ring_mod
from ..constants import IMG_EXTS
from . import theme as T
from .buttons import Btn
from .ring_card import RingCard
from .ring_picker import RingPicker, _disc
from .widgets import FlatSlider, Segmented

PICK_THUMB = 88         # a recommendation's preview, in pixels
STYLE_THUMB = 66        # a style's preview


class _Tiles(tk.Frame):
    """A grid of previews with a caption each; one can be marked as the current one."""

    def __init__(self, parent, items, cols, thumb, on_pick, bold_first=False):
        super().__init__(parent, bg=T.CARD)
        self.on_pick, self.thumb = on_pick, thumb
        self._cells, self._imgs, self._current = {}, {}, None
        for n, (ident, label) in enumerate(items):
            cell = tk.Frame(self, bg=T.CARD, highlightthickness=2, highlightbackground=T.CARD,
                            width=thumb + 16, height=thumb + 32, cursor="hand2")
            cell.grid(row=n // cols, column=n % cols, padx=3, pady=3)
            cell.pack_propagate(False)
            pic = tk.Label(cell, bg=T.CARD, bd=0, width=thumb, height=thumb)
            pic.pack(pady=(4, 0))
            first = bold_first and n == 0
            cap = tk.Label(cell, text=label, bg=T.CARD, cursor="hand2",
                           fg=T.TEAL if first else T.TEXT,
                           font=("TkDefaultFont", 8, "bold" if first else "normal"))
            cap.pack(pady=(1, 2))
            for w in (cell, pic, cap):
                w.bind("<Button-1>", lambda e, i=ident: self.on_pick(i))
                w.bind("<Enter>", lambda e, i=ident: self._hover(i, True))
                w.bind("<Leave>", lambda e, i=ident: self._hover(i, False))
            self._cells[ident] = (cell, pic)

    def set_image(self, ident, img):
        ph = ImageTk.PhotoImage(img)
        self._imgs[ident] = ph
        self._cells[ident][1].config(image=ph, width=self.thumb, height=self.thumb)

    def select(self, ident):
        self._current = ident
        for i, (cell, _p) in self._cells.items():
            cell.config(highlightbackground=T.TEAL if i == ident else T.CARD)

    def _hover(self, ident, inside):
        if ident != self._current:
            self._cells[ident][0].config(highlightbackground=T.BORDER if inside else T.CARD)


class _Swatches(tk.Frame):
    """Rows of round colours with a small name under each. The chosen one gets a teal rim."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.CARD)
        self._key = None

    def show(self, rows, current, on_pick):
        key = (tuple((t, tuple(s)) for t, s in rows), tuple(current))
        if key == self._key:
            return
        self._key = key
        for c in self.winfo_children():
            c.destroy()
        for title, swatches in rows:
            if title:
                tk.Label(self, text=title, bg=T.CARD, fg=T.MUTED, anchor="w",
                         font=("TkDefaultFont", 8)).pack(fill="x", pady=(6, 2))
            row = tk.Frame(self, bg=T.CARD)
            row.pack(fill="x")
            for name, col in swatches:
                on = tuple(col) == tuple(current)
                img = _disc(30, ring_mod.to_hex(col), T.TEAL if on else T.BORDER, 3 if on else 1)
                cell = tk.Frame(row, bg=T.CARD, cursor="hand2")
                cell.pack(side="left", padx=(0, 6))
                lab = tk.Label(cell, image=img, bg=T.CARD, bd=0)
                lab.image = img
                lab.pack()
                cap = tk.Label(cell, text=name, bg=T.CARD, fg=T.TEXT if on else T.MUTED,
                               font=("TkDefaultFont", 7), width=7)
                cap.pack()
                for w in (cell, lab, cap):
                    w.bind("<Button-1>", lambda e, c=col: on_pick(c))


class RingStudio(tk.Frame):
    """``dlg`` is the crop window."""

    def __init__(self, parent, dlg):
        super().__init__(parent, bg=T.CARD)
        self.dlg = dlg
        self._job = None
        self._shown = None
        self._tkeys = {}
        self.target = tk.StringVar(value="main")
        self.preset = tk.StringVar(value="")

        self.card = RingCard(self, dlg)
        self.card.pack(side="top", fill="x", padx=18, pady=(10, 2))

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

        # ---- sections (packed in order by _relayout)
        self.s_picks = self._section("Made for your picture",
                                     "Tap one. Every pick is print-tested.")
        self.picks_box = tk.Frame(self.s_picks, bg=T.CARD)
        self.picks_box.pack(anchor="w", padx=12)
        self.picks_tiles = None

        self.s_style = self._section("Style")
        self.style_tiles = _Tiles(self.s_style, list(ring_mod.STYLES), 4, STYLE_THUMB,
                                  self._style)
        self.style_tiles.pack(anchor="w", padx=12)

        self.s_colour = self._section("Colour")
        self.target_seg = Segmented(self.s_colour, self.target,
                                    [("main", "Main"), ("accent", "Accent")],
                                    command=self.sync, bg=T.CARD)
        self.swatches = _Swatches(self.s_colour)
        self.swatches.pack(fill="x", padx=18)
        self.more_btn = Btn(self.s_colour, "Custom colour", self._toggle_picker, icon="palette",
                        height=34)
        self.more_btn.pack(anchor="w", padx=18, pady=(10, 0))
        self.picker = None
        self._picker_open = False

        self.s_thick = self._section("Thickness")
        self.preset_seg = Segmented(self.s_thick, self.preset,
                                    [("0", "Thin"), ("1", "Medium"), ("2", "Bold")],
                                    command=self._preset, bg=T.CARD)
        self.preset_seg.pack(fill="x", padx=18)
        row = tk.Frame(self.s_thick, bg=T.CARD)
        row.pack(fill="x", padx=18, pady=(6, 0))
        lo, hi = dlg.ring_limits()
        self.slider = FlatSlider(row, dlg.v_ring_mm, lo, hi)
        self.slider.pack(side="left", fill="x", expand=True)
        self.mm_lbl = ttk.Label(row, text="", style="Value.TLabel", width=7, anchor="e")
        self.mm_lbl.pack(side="right")
        self.limit_lbl = ttk.Label(self.s_thick, text="", style="Muted.TLabel")
        self.limit_lbl.pack(anchor="w", padx=18)

        self.s_pat = self._section("Your pattern")
        prow = tk.Frame(self.s_pat, bg=T.CARD)
        prow.pack(fill="x", padx=18)
        self.choose_btn = Btn(prow, "Choose image…", self._choose_image, icon="image", height=34)
        self.choose_btn.pack(side="left")
        Btn(prow, "Reset", lambda: dlg.ring_change(reset_pattern=True), icon="reset",
            height=34).pack(side="right")
        self.pat_lbl = ttk.Label(self.s_pat, text="", style="Muted.TLabel", wraplength=340,
                                 justify="left")
        self.pat_lbl.pack(anchor="w", padx=18, pady=(6, 0))
        self.mode = tk.StringVar(value="tile")
        tk.Label(self.s_pat, text="Layout", bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8)
                 ).pack(anchor="w", padx=18, pady=(10, 2))
        Segmented(self.s_pat, self.mode, list(ring_mod.PATTERN_MODES),
                  command=lambda: dlg.ring_change(mode=self.mode.get()), bg=T.CARD
                  ).pack(fill="x", padx=18)
        # name, key, range, how the value is shown
        self._pvars = {}
        for name, k, lo, hi, fmt, origin in (
                ("Size", "scale", 0.08, 0.8, lambda v: f"{v * 100:.0f}%", None),
                ("Move across", "ox", -0.5, 0.5, lambda v: f"{v * 100:+.0f}%", 0.0),
                ("Move down", "oy", -0.5, 0.5, lambda v: f"{v * 100:+.0f}%", 0.0),
                ("Turn", "rot", -180, 180, lambda v: f"{v:+.0f}°", 0.0),
                ("Tint", "tint", 0.0, 0.8, lambda v: f"{v * 100:.0f}%", None)):
            row = tk.Frame(self.s_pat, bg=T.CARD)
            row.pack(fill="x", padx=18, pady=(8, 0))
            ttk.Label(row, text=name, style="Card.TLabel", width=11).pack(side="left")
            var = tk.DoubleVar(value=0.0)
            lbl = ttk.Label(row, text="", style="Value.TLabel", width=6, anchor="e")
            lbl.pack(side="right")
            FlatSlider(row, var, lo, hi, origin=origin, snaps=(0.0,) if origin == 0.0 else (),
                       snap_tol=(hi - lo) * 0.02,
                       command=lambda: self.after_idle(self._pat_slid)
                       ).pack(side="left", fill="x", expand=True, padx=(4, 6))
            self._pvars[k] = (var, lbl, fmt)
        ttk.Label(self.s_pat, text="Tint blends the pattern toward the ring colour below.",
                  style="Muted.TLabel").pack(anchor="w", padx=18, pady=(8, 0))

        tk.Frame(self.inner, bg=T.CARD, height=24).pack(side="bottom")
        self._bind_wheel(self.cv)
        self._bind_wheel(self.inner)

    # ---- structure ---------------------------------------------------------------
    def _section(self, title, hint=None):
        f = tk.Frame(self.inner, bg=T.CARD)
        tk.Label(f, text=title.upper(), bg=T.CARD, fg=T.MUTED,
                 font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        if hint:
            tk.Label(f, text=hint, bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8)
                     ).pack(anchor="w", padx=18, pady=(0, 4))
        else:
            tk.Frame(f, bg=T.CARD, height=4).pack()
        return f

    def _relayout(self):
        """Show the sections that make sense for the ring now."""
        d = self.dlg
        on, style = bool(d.v_ring.get()), d.ring_style
        two = style in ring_mod.TWO_COLOUR
        want = (on, style == "pattern", two, style == "foil")
        if want == self._shown:
            return
        self._shown = want
        for s in (self.s_picks, self.s_style, self.s_colour, self.s_thick, self.s_pat):
            s.pack_forget()
        self.s_picks.pack(fill="x")
        if on:
            self.s_style.pack(fill="x")
            if style == "pattern":
                self.s_pat.pack(fill="x")
            self.s_colour.pack(fill="x")
            self.s_thick.pack(fill="x")
        if two:
            self.target_seg.pack(fill="x", padx=18, before=self.swatches)
        else:
            self.target_seg.pack_forget()
            self.target.set("main")
        self.more_btn.pack_forget()
        if style != "foil":
            self.more_btn.pack(anchor="w", padx=18, pady=(10, 0))
        if self.picker is not None and (style == "foil" or not self._picker_open):
            self.picker.pack_forget()

    def _bind_wheel(self, widget):
        widget.bind("<MouseWheel>", self._wheel, add="+")
        widget.bind("<Button-4>", lambda e: self.cv.yview_scroll(-2, "units"), add="+")
        widget.bind("<Button-5>", lambda e: self.cv.yview_scroll(2, "units"), add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _wheel(self, e):
        self.cv.yview_scroll(-2 if e.delta > 0 else 2, "units")
        return "break"

    # ---- actions -----------------------------------------------------------------
    def _style(self, ident):
        d = self.dlg
        if ident == "pattern":
            if not d.ring_image:
                return self._choose_image()
            return d.ring_change(style="pattern")
        kw = {"style": ident}
        foils = [c for _n, c in ring_mod.FOILS]
        if ident == "foil" and tuple(d.ring_col) not in foils:
            kw["col"] = foils[0]
        elif ident != "foil" and tuple(d.ring_col) in foils:
            kw["col"] = (d.palette() or [(128, 128, 128)])[0]
        d.ring_change(**kw)

    def _choose_image(self):
        path = filedialog.askopenfilename(
            parent=self.dlg, title="Choose a pattern image",
            filetypes=[("Images", " ".join(f"*{e}" for e in IMG_EXTS)), ("All files", "*.*")])
        if path:
            self.dlg.ring_change(style="pattern", image=path)

    def _colour(self, col):
        d = self.dlg
        if self.target.get() == "accent" and d.ring_style in ring_mod.TWO_COLOUR:
            d.ring_change(col2=col)
        else:
            d.ring_change(col=col)

    def _auto_accent(self, _col=None):
        self.dlg.ring_change(col2=None)

    def _pat_slid(self):
        """A pattern slider moved: send every pattern value to the ring."""
        self.dlg.ring_change(**{k: v[0].get() for k, v in self._pvars.items()})

    def _preset(self):
        d = self.dlg
        mm = ring_mod.presets(d.pin["fw"], d.pin["fh"], d.ring_style)[int(self.preset.get())]
        d.ring_change(mm=mm)

    def _toggle_picker(self):
        d = self.dlg
        self._picker_open = not self._picker_open
        if self._picker_open:
            if self.picker is None:
                self.picker = RingPicker(self.s_colour, self._target_col(), None, self._colour)
                self._bind_wheel(self.picker)
            self.picker.set_colour(self._target_col())
            self.picker.pack(padx=18, pady=(8, 0), anchor="w")
        elif self.picker is not None:
            self.picker.pack_forget()
        self.more_btn.config(text="Hide custom colour" if self._picker_open else "Custom colour")

    def _target_col(self):
        d = self.dlg
        if self.target.get() == "accent" and d.ring_style in ring_mod.TWO_COLOUR:
            return d.ring_col2 or ring_mod.accent(d.cur_ring())
        return d.ring_col

    # ---- keeping the panel in step with the ring ---------------------------------
    def refresh(self):
        """The page was just opened: draw everything afresh."""
        self._tkeys = {}
        self._shown = None
        self.sync()
        self.soon(0)

    def sync(self):
        d = self.dlg
        self.card.refresh()
        self._relayout()
        lo, hi = d.ring_limits()
        self.slider.set_range(lo, hi)
        mm = d._ring_mm()
        self.mm_lbl.config(text=f"{mm:.1f} mm")
        self.limit_lbl.config(text=f"Best between {lo:.1f} and {hi:.1f} mm for this pin"
                              if d.ring_style in ring_mod.THICKER else
                              f"Allowed {lo:.1f} to {hi:.1f} mm so it prints cleanly")
        pres = ring_mod.presets(d.pin["fw"], d.pin["fh"], d.ring_style)
        near = [i for i, p in enumerate(pres) if abs(p - mm) < 0.06]
        self.preset.set(str(near[0]) if near else "")
        if d.v_ring.get():
            self.style_tiles.select(d.ring_style if d.ring_style != "pattern" or d.ring_image
                                    else None)
        self.picks_tiles and self.picks_tiles.select(d.pick_id)
        self._sync_colours()
        if d.ring_style == "pattern":
            ppi = ring_mod.pattern_ppi(d.cur_ring(), d.pin["fw"], d.pin["fh"])
            if ppi:
                self.pat_lbl.config(text=f"{ppi:.0f} dpi  ·  " + (
                    "may print soft, try a bigger image" if ppi < 150 else "sharp for print"))
            else:
                self.pat_lbl.config(text="Pick a picture to run around the edge.")
            self.choose_btn.config(text="Replace image…" if d.ring_image else "Choose image…")
            vals = dict(d.ring_pat, scale=d.ring_scale)
            for k, (var, lbl, fmt) in self._pvars.items():
                if abs(var.get() - vals[k]) > 1e-9:
                    var.set(vals[k])
                lbl.config(text=fmt(vals[k]))
            self.mode.set(d.ring_pat["mode"])
        self.soon()

    def _sync_colours(self):
        d = self.dlg
        if not d.v_ring.get():
            return
        accent = self.target.get() == "accent" and d.ring_style in ring_mod.TWO_COLOUR
        cur = self._target_col()
        pic = d.view_picture()
        if d.ring_style == "foil":
            rows = [("Metals", list(ring_mod.FOILS))]
        else:
            mine, classics = ring_mod.colourways(pic) if pic is not None else ([], [])
            rows = []
            if accent:
                auto = ring_mod.accent_for(d.ring_style, d.ring_col)
                rows.append(("Automatic", [("Auto", auto)]))
            rows += [("From your picture", mine[:6]), ("Classics", classics)]
        if accent and d.ring_col2 is None:
            cur = ring_mod.accent_for(d.ring_style, d.ring_col)
        self.swatches.show(rows, cur, self._colour)
        self._bind_wheel(self.swatches)
        if accent:       # the "Auto" swatch must clear the chosen accent
            auto_cell = self.swatches.winfo_children()[1].winfo_children()[0]
            for w in (auto_cell, *auto_cell.winfo_children()):
                w.bind("<Button-1>", self._auto_accent)
        if self.picker is not None and self._picker_open:
            self.picker.set_colour(cur)

    def soon(self, ms=150):
        """Redraw the previews shortly (so dragging stays smooth)."""
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(ms, self._thumbs)

    @staticmethod
    def _view_key(d):
        return (round(d.cx, 3), round(d.cy, 3), round(d.zoom, 3), round(d.v_angle.get()),
                d.flipped)

    def _thumbs(self):
        """Draw the recommendations and styles on the pin's own picture. Only what changed is
        redrawn, so choosing things does not flicker.
        """
        self._job = None
        d = self.dlg
        src = d.view_picture()
        if src is None or not self.winfo_ismapped():
            if self.dlg.v_tab.get() == "ring":
                self._job = self.after(200, self._thumbs)      # not on screen yet: try again
            return
        picks = d.picks()
        if self.picks_tiles is None and picks:
            self.picks_tiles = _Tiles(
                self.picks_box, [(i, p[0]) for i, p in enumerate(picks)],
                3, PICK_THUMB, d.apply_pick, bold_first=True)
            self.picks_tiles.pack()
            self._bind_wheel(self.picks_tiles)
            self.picks_tiles.select(d.pick_id)
        fw, fh, w, h = d.pin["fw"], d.pin["fh"], d.d, d.dh
        vk = self._view_key(d)

        def thumb(ring, size):
            k = size / max(w, h)
            tw, th = max(8, round(w * k)), max(8, round(h * k))
            base = src.resize((tw * 2, th * 2), Image.BILINEAR)
            outline = ring_mod.mask(d.shape, w, h, 0, (tw * 2, th * 2), tw * 2 / w,
                                    th * 2 / h, tw, th)
            im = ring_mod.apply(base, ring, d.shape, fw, fh, w, h) if ring else base
            card = Image.new("RGB", im.size, T.CARD)
            card.paste(im, (0, 0), outline)
            canvas = Image.new("RGB", (size * 2, size * 2), T.CARD)
            canvas.paste(card, ((size * 2 - card.size[0]) // 2, (size * 2 - card.size[1]) // 2))
            return canvas.resize((size, size), Image.LANCZOS)

        if self.picks_tiles is not None:
            key = (vk, tuple(ring_mod.key(p[1]) for p in picks))
            if self._tkeys.get("picks") != key:
                self._tkeys["picks"] = key
                for i, (_n, ring) in enumerate(picks):
                    self.picks_tiles.set_image(i, thumb(ring, PICK_THUMB))
        if d.v_ring.get():
            col, col2 = tuple(d.ring_col), d.ring_col2
            foils = [c for _n, c in ring_mod.FOILS]
            key = (vk, col, col2, d.ring_image, round(d.ring_scale, 2), tuple(d.ring_pat.values()))
            if self._tkeys.get("styles") != key:
                self._tkeys["styles"] = key
                for ident, _label in ring_mod.STYLES:
                    if ident == "pattern" and not d.ring_image:
                        im = thumb(None, STYLE_THUMB)
                        self.style_tiles.set_image(ident, im)
                        continue
                    c = foils[0] if ident == "foil" and col not in foils else (
                        col if not (ident != "foil" and col in foils) else
                        (d.palette() or [col])[0])
                    ring = ring_mod.Ring(ring_mod.default_mm(fw, fh, 1.2, ident), c, ident,
                                         d.ring_image, d.ring_scale, col2, **d.ring_pat)
                    self.style_tiles.set_image(ident, thumb(ring, STYLE_THUMB))
