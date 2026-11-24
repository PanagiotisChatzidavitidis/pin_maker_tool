"""The Filter page of the crop window's side panel.

A filter is optional. At the top: the on / off card and, once a filter is on, its intensity
and a "hold to compare" button that shows the untouched picture while pressed. Below: looks
chosen for this picture, then every look in groups. Every tile is a live preview on the pin's
own picture at the strength it would get. The panel only edits the crop window's filter state
(``dlg.filter_set`` / ``dlg.filter_change``).
"""

import tkinter as tk
from tkinter import ttk

from .. import filters as filters_mod
from . import theme as T
from .buttons import Btn
from .ring_card import FilterCard
from .tiles import ScrollPage, Tiles
from .widgets import FlatSlider

BIG, SMALL = 68, 64      # preview sizes in pixels


class FilterStudio(tk.Frame):
    """``dlg`` is the crop window."""

    def __init__(self, parent, dlg):
        super().__init__(parent, bg=T.CARD)
        self.dlg = dlg
        self._job = None
        self._tkeys = {}
        self._shown = None

        self.card = FilterCard(self, dlg)
        self.card.pack(side="top", fill="x", padx=18, pady=(10, 2))

        # intensity + compare stay pinned under the card (only while a filter is on)
        self.bar = tk.Frame(self, bg=T.CARD)
        ttk.Label(self.bar, text="Intensity", style="Card.TLabel").grid(row=0, column=0,
                                                                     sticky="w")
        self.pct = ttk.Label(self.bar, text="", style="Value.TLabel", anchor="e")
        self.pct.grid(row=0, column=2, sticky="e")
        self.slider = FlatSlider(self.bar, dlg.v_f_amount, 0.05, 1.0, origin=0.05,
                                 command=lambda: self.after_idle(self._slid))
        self.slider.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.bar.columnconfigure(1, weight=1)
        self.cmp = Btn(self.bar, "Hold to compare", icon="compare", height=34)
        self.cmp.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.cmp.bind("<ButtonPress-1>", lambda e: dlg.compare(True), add="+")
        self.cmp.bind("<ButtonRelease-1>", lambda e: dlg.compare(False), add="+")
        self.cmp.bind("<Leave>", lambda e: dlg.compare(False), add="+")

        self.page = ScrollPage(self)
        self.page.pack(side="top", fill="both", expand=True)
        body = self.page.inner
        self.tiles = {}                      # section -> Tiles

        def section(title, hint=None):
            tk.Label(body, text=title.upper(), bg=T.CARD, fg=T.MUTED,
                     font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
            if hint:
                tk.Label(body, text=hint, bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8),
                         wraplength=340, justify="left").pack(anchor="w", padx=18, pady=(0, 4))
            else:
                tk.Frame(body, bg=T.CARD, height=4).pack()

        section("Made for your picture", "Picked from its light and colour.")
        self.picks = None                    # built once the picture is there
        self.picks_box = tk.Frame(body, bg=T.CARD)
        self.picks_box.pack(anchor="w", padx=12)
        for group in filters_mod.GROUPS:
            section(group)
            t = Tiles(body, filters_mod.in_group(group), 4, SMALL, self._pick)
            t.pack(anchor="w", padx=12)
            self.tiles[group] = t
        tk.Label(body, text="Every look keeps shadows and highlights inside what paper can "
                            "hold. Screens glow, paper does not: Pop adds a little back.",
                 bg=T.CARD, fg=T.MUTED, font=("TkDefaultFont", 8), wraplength=340,
                 justify="left").pack(anchor="w", padx=18, pady=(18, 24))
        self.page.bind_wheel()

    # ---- actions -----------------------------------------------------------------
    def _pick(self, ident):
        self.dlg.filter_set(None if ident == "_none" else ident)

    def _slid(self):
        self.dlg.filter_change(self.dlg.v_f_amount.get())

    # ---- keeping the panel in step with the filter -------------------------------
    def refresh(self):
        """The page was just opened: draw everything afresh."""
        self._tkeys = {}
        self.sync()
        self.soon(0)

    def sync(self):
        d = self.dlg
        self.card.refresh()
        f = d.cur_filter()
        if (f is not None) != self._shown:
            self._shown = f is not None
            if f is not None:
                self.bar.pack(side="top", fill="x", padx=18, pady=(8, 4), after=self.card)
            else:
                self.bar.pack_forget()
        if f is not None:
            if abs(d.v_f_amount.get() - f.amount) > 1e-6:
                d.v_f_amount.set(f.amount)
            self.pct.config(text=f"{round(f.amount * 100)}%")
        name = f.name if f else "_none"
        for t in self.tiles.values():
            t.select(name)
        if self.picks:
            self.picks.select(name)
        self.soon()

    def soon(self, ms=150):
        """Redraw the previews shortly (so dragging stays smooth)."""
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(ms, self._thumbs)

    def _thumbs(self):
        """Draw every look on the pin's own picture. Only what changed is redrawn."""
        self._job = None
        d = self.dlg
        src = d.view_picture(raw=True)
        if src is None or not self.winfo_ismapped():
            if d.v_tab.get() == "filter":
                self._job = self.after(200, self._thumbs)      # not on screen yet
            return
        recs = d.filter_picks()
        if self.picks is None and recs:
            items = [(n, filters_mod.NAMES[n]) for n, _a in recs] + [("_none", "Original")]
            self.picks = Tiles(self.picks_box, items, 4, BIG, self._pick, bold_first=True)
            self.picks.pack()
            self.page.bind_wheel(self.picks_box)
            self.picks.select(d.f_name or "_none")
        vk = (round(d.cx, 3), round(d.cy, 3), round(d.zoom, 3), round(d.v_angle.get()),
              d.flipped, d.f_amount if d._f_touched else None)
        if self._tkeys.get("all") == vk:
            return
        self._tkeys["all"] = vk
        if self.picks is not None:
            for n, _a in recs:
                self.picks.set_image(n, d.thumb(filters_mod.apply(
                    src, (n, d.amount_for(n))), BIG))
            self.picks.set_image("_none", d.thumb(src, BIG))
        for group, t in self.tiles.items():
            for n, _label in filters_mod.in_group(group):
                t.set_image(n, d.thumb(filters_mod.apply(src, (n, d.amount_for(n))), SMALL))
