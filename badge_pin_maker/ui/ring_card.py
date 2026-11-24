"""The Ring and Filter rows of the crop window: a rounded card with a little icon, a title and
summary, and the on / off switch. Used on the Frame page (tap the card to open its page) and
at the top of the Ring and Filter pages.
"""

import tkinter as tk

from .. import filters as filters_mod
from .. import ring as ring_mod
from . import smooth
from . import theme as T


def _icon(size, colour, edge, fill, bg):
    """A small ring: a coloured band round an empty middle (just an outline while off)."""
    key = ("ringicon", size, colour, edge, fill, bg)

    def paint(d, k):
        s = size * k
        if colour is None:
            d.ellipse([2 * k, 2 * k, s - 2 * k, s - 2 * k], outline=edge, width=round(2 * k))
            return
        d.ellipse([1 * k, 1 * k, s - 1 * k - 1, s - 1 * k - 1], fill=colour)
        r = size * 0.29 * k
        d.ellipse([s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r], fill=fill)
    return smooth._make(key, size, size, bg, paint)


def _filter_icon(size, on, edge, fill, bg):
    """Three overlapping discs (colours mixing); an outline while the filter is off."""
    key = ("filtericon", size, on, edge, fill, bg)

    def paint(d, k):
        s = size * k
        r = size * 0.27 * k
        pts = ((s * 0.38, s * 0.40), (s * 0.62, s * 0.40), (s * 0.5, s * 0.63))
        cols = ((255, 120, 150), (255, 200, 80), (90, 170, 255))
        for (x, y), c in zip(pts, cols):
            box = [x - r, y - r, x + r, y + r]
            if on:
                d.ellipse(box, fill=c)
            else:
                d.ellipse(box, outline=edge, width=round(1.6 * k))
    return smooth._make(key, size, size, bg, paint)


class FeatureCard(tk.Canvas):
    """A switch card. Subclasses say what it is: ``title``, ``summary()``, ``is_on()``,
    ``toggle()`` and ``icon(fill)``. ``on_open`` (optional) runs when the card itself, not the
    switch, is clicked."""
    H = 68
    title = ""
    open_label = "Style ›"

    def __init__(self, parent, dlg, on_open=None):
        super().__init__(parent, height=self.H, bg=T.CARD, highlightthickness=0, bd=0,
                         cursor="hand2" if on_open else "")
        self.dlg, self.on_open = dlg, on_open
        self._hover = False
        self._imgs = []
        self._sw = (0, 0, 0, 0)               # where the switch is, for hit-testing clicks
        self.bind("<Configure>", lambda e: self.refresh())
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    # ---- what a card is (overridden)
    def is_on(self):
        return False

    def toggle(self):
        pass

    def summary(self):
        return ""

    def icon(self, fill):
        return None

    # ---- drawing
    def _set_hover(self, on):
        self._hover = on and self.on_open is not None
        self.refresh()

    def _click(self, e):
        x0, y0, x1, y1 = self._sw
        if x0 <= e.x <= x1 and y0 <= e.y <= y1:
            self.toggle()
        elif self.on_open:
            self.on_open()

    def refresh(self):
        """Repaint for the current width and state."""
        w, h = max(200, self.winfo_width()), self.H
        on = self.is_on()
        self.delete("all")
        fill = T._mix(T.CARD, T.SAND, 0.45)
        edge = T._mix(T.BORDER, T.TEAL, 0.55) if self._hover else T.BORDER
        plate = smooth.plate(w, h, T.CARD, fill, edge, 1, radius=16)
        self.create_image(0, 0, anchor="nw", image=plate)
        icon = self.icon(fill)
        self.create_image(16, (h - 40) // 2, anchor="nw", image=icon)
        self._imgs = [plate, icon]
        self.create_text(68, h / 2 - 11, text=self.title, anchor="w", fill=T.TEXT,
                         font=("TkDefaultFont", 11, "bold"))
        self.create_text(68, h / 2 + 11, text=self.summary(), anchor="w", fill=T.MUTED,
                         font=("TkDefaultFont", 9))
        sw = smooth.switch(44, 24, on, T.TEAL if on else T.SAND_PRESS, "#FFFFFF", fill)
        sx, sy = w - 16 - 44, (h - 24) // 2
        self.create_image(sx, sy, anchor="nw", image=sw)
        self._imgs.append(sw)
        self._sw = (sx - 6, 0, w, h)
        if self.on_open and on:
            self.create_text(sx - 12, h / 2, text=self.open_label, anchor="e", fill=T.TEAL,
                             font=("TkDefaultFont", 9, "bold"))


class RingCard(FeatureCard):
    title = "Ring"

    def is_on(self):
        return bool(self.dlg.v_ring.get())

    def toggle(self):
        self.dlg.v_ring.set(not self.dlg.v_ring.get())
        self.dlg._ring_toggled()

    def summary(self):
        d = self.dlg
        if not self.is_on():
            return "Add a border inside the edge"
        return f"{ring_mod.STYLE_NAMES.get(d.cur_ring().style, '')}  ·  {d._ring_mm():.1f} mm"

    def icon(self, fill):
        d = self.dlg
        return _icon(40, ring_mod.to_hex(d.ring_col) if self.is_on() else None, T.MUTED, fill,
                     fill)


class FilterCard(FeatureCard):
    title = "Filter"

    def is_on(self):
        return self.dlg.cur_filter() is not None

    def toggle(self):
        self.dlg.filter_toggle()

    def summary(self):
        f = self.dlg.cur_filter()
        if f is None:
            return "Optional colour look for print"
        return f"{filters_mod.label(f)}  ·  {round(f.amount * 100)}%"

    def icon(self, fill):
        return _filter_icon(40, self.is_on(), T.MUTED, fill, fill)
