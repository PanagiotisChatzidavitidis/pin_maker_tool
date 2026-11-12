"""Smooth (anti-aliased) little pictures for the interface.

Tk draws its own circles, arcs and rounded corners with jagged edges. The shapes that show
up in close-up (theme tiles, the sun / moon icons, the undo / redo arrows, the on / off switch)
are therefore painted here with Pillow at four times the size and shrunk down, then shown as
images. They are cached by their colours, so changing theme just paints new ones.
"""

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from . import mascot

SS = 4                                   # paint at 4x, then shrink
_cache = {}
_cache_root = None                         # the Tk root the cached images belong to


def _make(key, w, h, bg, paint, post=None):
    """The cached PhotoImage for ``key``, painted by ``paint(draw, k)`` on first use. ``k`` is
    the factor to multiply coordinates by; ``bg`` fills the picture first (the colour of what
    it sits on, so the soft edges blend in).
    """
    global _cache_root
    if _cache_root is not tk._default_root:      # a new window: images of the old one are void
        _cache.clear()
        _cache_root = tk._default_root
    ph = _cache.get(key)
    if ph is None:
        if len(_cache) > 400:
            _cache.clear()
        big = Image.new("RGB", (w * SS, h * SS), bg)
        paint(ImageDraw.Draw(big), SS)
        if post:
            big = post(big)
        ph = _cache[key] = ImageTk.PhotoImage(big.resize((w, h), Image.LANCZOS))
    return ph


def _oval(d, k, cx, cy, r, fill, outline=None, width=1):
    """A filled circle of radius ``r`` centred at (cx, cy), with an optional outline drawn
    inside its edge.
    """
    box = [(cx - r) * k, (cy - r) * k, (cx + r) * k - 1, (cy + r) * k - 1]
    d.ellipse(box, fill=fill, outline=outline, width=round(width * k) if outline else 0)


def _line(d, k, pts, fill, width):
    """A line through ``pts`` with round ends and joins."""
    flat = [(x * k, y * k) for x, y in pts]
    d.line(flat, fill=fill, width=round(width * k), joint="curve")
    r = width * k / 2
    for x, y in (flat[0], flat[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def tile_face(w, h, bg, fill, edge, edge_w, dots, dots_x, tick=None):
    """The face of a theme tile: a rounded card in ``fill`` with an ``edge`` outline, a row of
    colour dots ((fill, outline) pairs, the first centred on ``dots_x``) and, when the theme is
    in use, a round tick ``tick = (cx, circle colour, tick colour)``.
    """
    key = ("tile", w, h, bg, fill, edge, edge_w, tuple(dots), dots_x, tick)

    def paint(d, k):
        d.rounded_rectangle([2 * k, 2 * k, (w - 2) * k - 1, (h - 2) * k - 1], radius=12 * k,
                            fill=fill, outline=edge, width=round(edge_w * k))
        x = dots_x
        for col, line in dots:
            _oval(d, k, x, h / 2, 9, col, line, 1)
            x += 22
        if tick:
            cx, circle, mark = tick
            _oval(d, k, cx, h / 2, 10, circle)
            _line(d, k, [(cx - 5, h / 2), (cx - 1.5, h / 2 + 4), (cx + 5, h / 2 - 4)], mark, 2)
    return _make(key, w, h, bg, paint)


def mode_icon(kind, colour, bg, size=18):
    """A small sun ("light") or crescent moon ("dark") in ``colour`` on the colour ``bg``."""
    key = ("mode", kind, colour, bg, size)

    def paint(d, k):
        m = size / 2
        if kind == "light":
            _oval(d, k, m, m, size * 0.21, colour)
            for i in range(8):
                a = i * math.pi / 4
                c, s = math.cos(a), math.sin(a)
                _line(d, k, [(m + c * size * 0.34, m + s * size * 0.34),
                             (m + c * size * 0.47, m + s * size * 0.47)], colour, 1.5)
        else:
            _oval(d, k, m - 0.5, m + 0.5, size * 0.38, colour)
            _oval(d, k, m + size * 0.18, m - size * 0.14, size * 0.34, bg)
    return _make(key, size, size, bg, paint)


def arrow_icon(kind, fg, tile, edge, size=34):
    """A square tile (colour ``tile``, outline ``edge``) with a curved undo or redo arrow."""
    key = ("arrow", kind, fg, tile, edge, size)

    def paint(d, k):
        d.rectangle([0, 0, size * k - 1, size * k - 1], fill=tile, outline=edge, width=k)
        m = size / 2
        d.arc([(m - 8) * k, (m - 5) * k, (m + 8) * k, (m + 11) * k], 180, 360, fill=fg,
              width=round(2 * k))
        hx = m - 8 if kind == "undo" else m + 8
        _oval(d, k, m + (8 if kind == "undo" else -8), m + 3, 1, fg)        # round the free end
        d.polygon([((hx - 4.5) * k, (m + 3.5) * k), ((hx + 4.5) * k, (m + 3.5) * k),
                   (hx * k, (m + 9.5) * k)], fill=fg)
    return _make(key, size, size, tile, paint)


def switch(w, h, on, track, knob, bg):
    """The on / off pill switch."""
    key = ("switch", w, h, on, track, knob, bg)

    def paint(d, k):
        d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=h * k / 2, fill=track)
        pad = 3
        x0 = w - h + pad if on else pad
        _oval(d, k, x0 + (h - 2 * pad) / 2, h / 2, (h - 2 * pad) / 2, knob)
    return _make(key, w, h, bg, paint)


def plate(w, h, bg, fill, edge, edge_w, radius=14, badge=None):
    """A rounded plate (colour ``fill``, outline ``edge``) with an optional round tick badge
    ``badge = (cx, cy, circle colour, tick colour)`` for the item in use.
    """
    key = ("plate", w, h, bg, fill, edge, edge_w, radius, badge)

    def paint(d, k):
        d.rounded_rectangle([1.5 * k, 1.5 * k, (w - 1.5) * k - 1, (h - 1.5) * k - 1],
                            radius=radius * k, fill=fill, outline=edge, width=round(edge_w * k))
        if badge:
            cx, cy, circle, mark = badge
            _oval(d, k, cx, cy, 10, circle)
            _line(d, k, [(cx - 5, cy), (cx - 1.5, cy + 4), (cx + 5, cy - 4)], mark, 2)
    return _make(key, w, h, bg, paint)


def stat_icon(kind, colour, bg, size=22):
    """The little line icon on a statistic tile, in ``colour`` on ``bg``: a sheet of paper
    ("paper"), a ring with a dot ("pins") or a circled tick ("done").
    """
    key = ("stat", kind, colour, bg, size)

    def paint(d, k):
        m, w = size / 2, 1.7
        if kind == "paper":
            pts = [(m - 6, 2.5), (m + 2, 2.5), (m + 6.5, 7), (m + 6.5, size - 2.5),
                   (m - 6, size - 2.5), (m - 6, 2.5)]
            _line(d, k, pts, colour, w)
            _line(d, k, [(m - 2.5, m + 1), (m + 3, m + 1)], colour, w)
            _line(d, k, [(m - 2.5, m + 5), (m + 3, m + 5)], colour, w)
        elif kind == "pins":
            _oval(d, k, m, m, size * 0.42, bg, outline=colour, width=w)
            _oval(d, k, m, m, size * 0.2, colour)
        else:
            _oval(d, k, m, m, size * 0.42, bg, outline=colour, width=w)
            _line(d, k, [(m - 3.6, m + 0.2), (m - 0.9, m + 3), (m + 3.8, m - 2.8)], colour, w)
    return _make(key, size, size, bg, paint)


def plus_icon(colour, bg, size=84):
    """A ring with a plus in it, in ``colour`` on ``bg`` (the "New canvas" tile), drawn
    smoothly instead of with the canvas's jagged lines.
    """
    key = ("plus", colour, bg, size)

    def paint(d, k):
        m = size / 2
        _oval(d, k, m, m, size / 2 - 4, bg, outline=colour, width=2)
        r = size / 7 + 4
        _line(d, k, [(m - r, m), (m + r, m)], colour, 3)
        _line(d, k, [(m, m - r), (m, m + r)], colour, 3)
    return _make(key, size, size, bg, paint)


def nav_icon(kind, colour, bg, size=20):
    """A small line icon for a sidebar row: "folder", "sliders" (options), "info" or "exit"."""
    key = ("nav", kind, colour, bg, size)

    def paint(d, k):
        m, w = size / 2, 1.7
        if kind == "folder":
            _line(d, k, [(2.5, 6), (2.5, size - 4.5), (size - 2.5, size - 4.5), (size - 2.5, 7),
                         (m + 1, 7), (m - 1, 4.5), (2.5, 4.5), (2.5, 6)], colour, w)
        elif kind == "sliders":
            for y, x in ((5.5, m + 3), (m, m - 3), (size - 5.5, m + 1)):
                _line(d, k, [(2.5, y), (size - 2.5, y)], colour, w)
                _oval(d, k, x, y, 2.6, bg, outline=colour, width=w)
        elif kind == "info":
            _oval(d, k, m, m, size / 2 - 2, bg, outline=colour, width=w)
            _line(d, k, [(m, m - 0.5), (m, m + 3.8)], colour, w)
            _oval(d, k, m, m - 3.6, 1.1, colour)
        elif kind == "search":
            _oval(d, k, m - 1.5, m - 1.5, size / 2 - 4.5, bg, outline=colour, width=w)
            _line(d, k, [(m + 3.6, m + 3.6), (size - 3, size - 3)], colour, w)
        elif kind == "sort":
            for y, half in ((5.5, size / 2 - 3), (m, size / 2 - 5.5), (size - 5.5, size / 2 - 8)):
                _line(d, k, [(m - half, y), (m + half, y)], colour, w)
        elif kind == "chevron":
            _line(d, k, [(m - 3.8, m - 1.6), (m, m + 2.2), (m + 3.8, m - 1.6)], colour, w)
        elif kind == "check":
            _line(d, k, [(m - 4, m + 0.2), (m - 1.2, m + 3), (m + 4.2, m - 3)], colour, w + 0.3)
        elif kind == "close":
            _line(d, k, [(m - 3.2, m - 3.2), (m + 3.2, m + 3.2)], colour, w)
            _line(d, k, [(m + 3.2, m - 3.2), (m - 3.2, m + 3.2)], colour, w)
        elif kind == "monitor":
            d.rounded_rectangle([2.5 * k, 3.5 * k, (size - 2.5) * k, (size - 7) * k], radius=2.5 * k,
                                outline=colour, width=round(w * k))
            _line(d, k, [(m, size - 7), (m, size - 3.5)], colour, w)
            _line(d, k, [(m - 3.5, size - 3), (m + 3.5, size - 3)], colour, w)
        elif kind == "play":
            _oval(d, k, m, m, size / 2 - 2, bg, outline=colour, width=w)
            _line(d, k, [(m - 2, m - 3.5), (m + 3.5, m), (m - 2, m + 3.5), (m - 2, m - 3.5)],
                  colour, w)
        elif kind == "palette":
            _oval(d, k, m, m, size / 2 - 2, bg, outline=colour, width=w)
            for x, y in ((m - 3.2, m - 1.8), (m + 0.2, m - 3.6), (m + 3.4, m - 0.6),
                         (m - 1.2, m + 3.2)):
                _oval(d, k, x, y, 1.25, colour)
        elif kind == "face":
            _oval(d, k, m, m, size / 2 - 2, bg, outline=colour, width=w)
            _oval(d, k, m - 3, m - 1.5, 1.2, colour)
            _oval(d, k, m + 3, m - 1.5, 1.2, colour)
            _line(d, k, [(m - 3, m + 2.2), (m - 1.4, m + 3.6), (m + 1.4, m + 3.6),
                         (m + 3, m + 2.2)], colour, w)
        else:                                     # exit: a doorway with an arrow leaving it
            _line(d, k, [(8, 3), (3, 3), (3, size - 3), (8, size - 3)], colour, w)
            _line(d, k, [(8, m), (size - 3, m)], colour, w)
            _line(d, k, [(size - 7, m - 4), (size - 3, m), (size - 7, m + 4)], colour, w)
    return _make(key, size, size, bg, paint)


def hero_logo(size, plate, bg):
    """The mascot on a soft round plate (colour ``plate``, on ``bg``): the sidebar's header.
    Without the mascot pictures it is just the plate.
    """
    key = ("hero", mascot.current, size, plate, bg)

    def paint(d, k):
        _oval(d, k, size / 2, size / 2, size / 2 - 1, plate)

    def post(big):
        face = mascot.square(mascot.current, round(size * 0.8) * SS, pad=0.0)
        if face is not None:
            off = (big.width - face.width) // 2
            big = big.convert("RGBA")
            big.alpha_composite(face, (off, off + SS))
            big = big.convert("RGB")
        return big
    return _make(key, size, size, bg, paint, post)


def pill(w, h, fill, edge, bg, edge_w=1):
    """A fully rounded "pill" ``w`` x ``h``: ``fill`` with an ``edge`` outline, on ``bg``."""
    key = ("pill", w, h, fill, edge, bg, edge_w)

    def paint(d, k):
        d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=h * k / 2, fill=fill,
                            outline=edge, width=round(edge_w * k))
    return _make(key, w, h, bg, paint)
