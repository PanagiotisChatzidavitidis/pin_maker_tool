"""The tab bar at the top of the crop window's side panel: a rounded track with a pill under
the chosen tab. A tab for an optional setting (Filter, Ring) shows a small glowing dot while
that setting is in use, so you can see at a glance what is switched on.
"""

import tkinter as tk
import tkinter.font as tkfont

from . import smooth
from . import theme as T


def _dot(size, core, halo, bg):
    """A small round dot with a soft halo."""
    key = ("tabdot", size, core, halo, bg)

    def paint(d, k):
        c = size * k / 2
        d.ellipse([0, 0, size * k - 1, size * k - 1], fill=halo)
        r = size * 0.27 * k
        d.ellipse([c - r, c - r, c + r, c + r], fill=core)
    return smooth._make(key, size, size, bg, paint)


class PillTabs(tk.Canvas):
    """``options`` is [(value, label)]; the chosen value lives in the StringVar ``variable``.
    ``command`` runs after a tab is picked. ``set_badge(value, on)`` shows / hides the dot."""
    H = 44

    def __init__(self, parent, variable, options, command=None, bg=None):
        super().__init__(parent, height=self.H, bg=bg or T.CARD, highlightthickness=0, bd=0)
        self.var, self.command, self.options = variable, command, list(options)
        self._badges = {}
        self._hover = None
        self._imgs = []
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", self._move)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self._tid = variable.trace_add("write", lambda *_: self._paint())
        self.bind("<Destroy>", self._gone)

    def _gone(self, e):
        if e.widget is self:
            try:
                self.var.trace_remove("write", self._tid)
            except (tk.TclError, ValueError):
                pass

    def set_badge(self, value, on):
        if self._badges.get(value, False) != bool(on):
            self._badges[value] = bool(on)
            self._paint()

    def _slot(self, x):
        w = max(1, self.winfo_width() - 8)
        return self.options[max(0, min(len(self.options) - 1, int((x - 4) / w * len(self.options))))][0]

    def _click(self, e):
        v = self._slot(e.x)
        if v != self.var.get():
            self.var.set(v)
            if self.command:
                self.command()

    def _move(self, e):
        self._set_hover(self._slot(e.x))

    def _set_hover(self, v):
        if v != self._hover:
            self._hover = v
            self._paint()

    def _paint(self):
        w, h = self.winfo_width(), self.H
        if w < 40:
            return
        self.delete("all")
        track = T._mix(T.CARD, T.SAND, 0.7)
        plate = smooth.plate(w, h, T.CARD, track, track, 1, radius=h / 2.4)
        self.create_image(0, 0, anchor="nw", image=plate)
        self._imgs = [plate]
        n = len(self.options)
        seg = (w - 8) / n
        cur = self.var.get()
        for i, (value, label) in enumerate(self.options):
            x0 = 4 + i * seg
            on = value == cur
            if on:
                pw, ph = round(seg), h - 8
                pill = smooth.plate(pw, ph, track, T.TEAL, T.TEAL, 1, radius=ph / 2.3)
                self.create_image(round(x0), 4, anchor="nw", image=pill)
                self._imgs.append(pill)
            elif value == self._hover:
                pw, ph = round(seg), h - 8
                pill = smooth.plate(pw, ph, track, T._mix(track, T.CARD, 0.55),
                                    T._mix(track, T.CARD, 0.55), 1, radius=ph / 2.3)
                self.create_image(round(x0), 4, anchor="nw", image=pill)
                self._imgs.append(pill)
            ink = T.ON_PRIMARY if on else T.TEXT
            font = ("TkDefaultFont", 10, "bold" if on else "normal")
            cx = x0 + seg / 2
            badge = self._badges.get(value, False)
            tw = tkfont.Font(font=font).measure(label)
            if badge:
                cx -= 8
            self.create_text(cx, h / 2, text=label, fill=ink, font=font)
            if badge:
                halo = T._mix(T.TEAL, "#FFFFFF", 0.35) if on else T._mix(track, T.TEAL, 0.35)
                core = "#FFFFFF" if on else T.TEAL
                dot = _dot(14, core, halo, T.TEAL if on else track)
                self.create_image(cx + tw / 2 + 11, h / 2, image=dot)
                self._imgs.append(dot)
