"""Rounded, smooth buttons with little line icons, for the crop window.

``Btn`` is a canvas button: a soft rounded plate that lightens on hover and darkens on press,
with an optional icon and label. Kinds: ``soft`` (the everyday one), ``accent`` (the main action),
``ghost`` (outlined). With only an icon it is a square. The plates and icons are painted with
Pillow at 4x (see ``smooth``) so the edges are clean, and are cached per colour and size.
"""

import math
import tkinter as tk
from tkinter import font as tkfont

from . import smooth
from . import theme as T

ICON = 18


def _arc_points(cx, cy, r, a0, a1, mirror=False):
    n = max(8, int(abs(a1 - a0) / 10))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        x = cx + r * math.cos(a) * (-1 if mirror else 1)
        pts.append((x, cy + r * math.sin(a)))
    return pts


def _turn(d, k, size, colour, mirror, sweep=270):
    """A circular arrow: clockwise normally, anticlockwise when ``mirror``."""
    m = size / 2
    r = size * 0.31
    a0 = 215
    a1 = a0 + sweep
    pts = _arc_points(m, m, r, a0, a1, mirror)
    smooth._line(d, k, pts, colour, 1.8)
    # the arrow head at the end of the arc, pointing along it
    ex, ey = pts[-1]
    (px, py) = pts[-2]
    tx, ty = ex - px, ey - py
    ln = math.hypot(tx, ty) or 1
    tx, ty = tx / ln, ty / ln
    nx, ny = -ty, tx
    tip = (ex + tx * 4.2, ey + ty * 4.2)
    a = (ex + nx * 3.6, ey + ny * 3.6)
    b = (ex - nx * 3.6, ey - ny * 3.6)
    d.polygon([(tip[0] * k, tip[1] * k), (a[0] * k, a[1] * k), (b[0] * k, b[1] * k)],
              fill=colour)


def icon(name, colour, bg, size=ICON):
    """A small line icon in ``colour`` on ``bg``."""
    key = ("btnicon", name, colour, bg, size)

    def paint(d, k):
        m = size / 2
        if name == "minus":
            smooth._line(d, k, [(m - 5, m), (m + 5, m)], colour, 2)
        elif name == "plus":
            smooth._line(d, k, [(m - 5, m), (m + 5, m)], colour, 2)
            smooth._line(d, k, [(m, m - 5), (m, m + 5)], colour, 2)
        elif name == "rot_r":
            _turn(d, k, size, colour, False)
        elif name == "rot_l":
            _turn(d, k, size, colour, True)
        elif name == "reset":
            _turn(d, k, size, colour, True, 300)
        elif name == "flip":
            smooth._line(d, k, [(m, 2.5), (m, size - 2.5)], colour, 1.4)
            d.polygon([(2 * k, (size - 4) * k), ((m - 2.5) * k, (size - 4) * k),
                       ((m - 2.5) * k, 4 * k)], fill=colour)
            d.polygon([((size - 2) * k, (size - 4) * k), ((m + 2.5) * k, (size - 4) * k),
                       ((m + 2.5) * k, 4 * k)], outline=colour, width=round(1.4 * k))
        elif name == "fill":                  # the picture covers the whole frame
            d.rounded_rectangle([3 * k, 3 * k, (size - 3) * k, (size - 3) * k], radius=3 * k,
                                fill=colour)
        elif name == "fit":                   # the whole picture sits inside the frame
            d.rounded_rectangle([2.5 * k, 2.5 * k, (size - 2.5) * k, (size - 2.5) * k],
                                radius=3 * k, outline=colour, width=round(1.6 * k))
            d.rounded_rectangle([6 * k, 6 * k, (size - 6) * k, (size - 6) * k], radius=1.5 * k,
                                fill=colour)
        elif name == "image":
            d.rounded_rectangle([2.5 * k, 3.5 * k, (size - 2.5) * k, (size - 3.5) * k],
                                radius=3 * k, outline=colour, width=round(1.6 * k))
            smooth._oval(d, k, size * 0.66, size * 0.38, 1.9, colour)
            d.polygon([(4.5 * k, (size - 5.5) * k), (size * 0.4 * k, size * 0.5 * k),
                       (size * 0.58 * k, (size - 5.5) * k)], fill=colour)
        elif name == "palette":
            smooth._oval(d, k, m, m, size * 0.4, bg, outline=colour, width=1.6)
            for dx, dy in ((-3.5, -2), (0, -4), (3.5, -2)):
                smooth._oval(d, k, m + dx, m + dy, 1.3, colour)
    return smooth._make(key, size, size, bg, paint)


class Btn(tk.Canvas):
    """A rounded button. ``icon`` is one of the names above; ``width`` / ``height`` in pixels
    (by default it fits its label and stretches when packed or gridded with fill)."""
    H = 38
    KINDS = {                      # fill, hover, press, text, edge
        "soft": ("SAND", "SAND_HOVER", "SAND_PRESS", "TEXT", None),
        "accent": ("TEAL", "TEAL_HOVER", "TEAL_DARK", "ON_PRIMARY", None),
        "ghost": ("CARD", "HOVER", "SAND", "TEXT", "BORDER"),
    }

    def __init__(self, parent, text="", command=None, kind="soft", icon=None, width=None,
                 height=None, bg=None, **kw):
        self.text, self.command, self.kind, self.icon = text, command, kind, icon
        self._bold = kind == "accent"
        f = tkfont.nametofont("TkDefaultFont").copy()
        f.configure(weight="bold" if self._bold else "normal")
        self._font = f
        h = height or self.H
        need = 2 * 16 + (ICON if icon else 0) + (8 if icon and text else 0) + (
            f.measure(text) if text else 0)
        w = width or (h if icon and not text else max(need, 56))
        super().__init__(parent, width=w, height=h, bg=bg or T.CARD, highlightthickness=0,
                         bd=0, cursor="hand2", **kw)
        self._state, self._imgs, self._enabled = "normal", [], True
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Enter>", lambda e: self._set("hover"))
        self.bind("<Leave>", lambda e: self._set("normal"))
        self.bind("<ButtonPress-1>", lambda e: self._set("press"))
        self.bind("<ButtonRelease-1>", self._release)

    def _set(self, state):
        if self._enabled and state != self._state:
            self._state = state
            self._paint()

    def _release(self, e):
        if not self._enabled:
            return
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        self._set("hover" if inside else "normal")
        if inside and self.command:
            self.command()

    def invoke(self):
        if self._enabled and self.command:
            self.command()

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        repaint = False
        for name in ("text", "icon", "command", "kind"):
            if name in kw:
                setattr(self, name, kw.pop(name))
                repaint = True
        if "state" in kw:
            self._enabled = kw.pop("state") != "disabled"
            self._state = "normal"
            repaint = True
        if kw:
            super().configure(**kw)
        if repaint:
            self._paint()

    config = configure

    def _paint(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8:
            return
        fill_k, hover_k, press_k, text_k, edge_k = self.KINDS[self.kind]
        fill = getattr(T, {"normal": fill_k, "hover": hover_k, "press": press_k}[self._state])
        ink = getattr(T, text_k)
        if not self._enabled:
            ink = T.MUTED
        edge = getattr(T, edge_k) if edge_k else fill
        if edge_k and self._state != "normal" and self._enabled:
            edge = T.TEAL
        parent_bg = self.cget("bg")
        plate = smooth.plate(w, h, parent_bg, fill, edge, 1, radius=min(14, h / 2.6))
        self.delete("all")
        self._imgs = [plate]
        self.create_image(0, 0, anchor="nw", image=plate)
        tw = self._font.measure(self.text) if self.text else 0
        iw = ICON if self.icon else 0
        total = iw + (8 if iw and tw else 0) + tw
        x = (w - total) / 2 + (1 if self._state == "press" else 0)
        y = h / 2 + (1 if self._state == "press" else 0)
        if self.icon:
            im = icon(self.icon, ink, fill)
            self._imgs.append(im)
            self.create_image(x, y - ICON / 2, anchor="nw", image=im)
            x += iw + (8 if tw else 0)
        if self.text:
            self.create_text(x, y, text=self.text, anchor="w", fill=ink, font=self._font)
