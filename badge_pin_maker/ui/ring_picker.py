"""The little colour picker for a pin's ring.

``Swatch`` is a round colour button. Clicking it opens a ``RingPicker`` card above it: a hue
strip, a light-to-dark strip for the chosen hue, and a row of colours taken from the picture
(the first one is the automatic choice).
"""

import colorsys
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from .. import ring as ring_mod
from . import theme as T

SS = 4          # supersampling for smooth circles


def _disc(size, fill, outline, ring_w=2):
    """A smooth filled circle as an image (a Tk oval has jagged edges)."""
    big = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.ellipse((0, 0, size * SS - 1, size * SS - 1), fill=outline)
    pad = ring_w * SS
    d.ellipse((pad, pad, size * SS - 1 - pad, size * SS - 1 - pad), fill=fill)
    return ImageTk.PhotoImage(big.resize((size, size), Image.LANCZOS))


class RingPicker(tk.Frame):
    """The card. ``on_pick(rgb)`` runs on every change; ``on_close()`` when it should go."""
    W = 280
    BAR = 20

    def __init__(self, parent, colour, palette, on_pick, bg=None):
        super().__init__(parent, bg=bg or T.CARD)
        self.on_pick = on_pick
        r, g, b = (v / 255 for v in colour)
        self.h, self.l, self.s = colorsys.rgb_to_hls(r, g, b)
        self.s = max(self.s, 0.35)

        self.hue = tk.Canvas(self, width=self.W, height=self.BAR + 6, bg=T.CARD,
                             highlightthickness=0, cursor="hand2")
        self.hue.pack(pady=(6, 4))
        self.shade = tk.Canvas(self, width=self.W, height=self.BAR + 6, bg=T.CARD,
                               highlightthickness=0, cursor="hand2")
        self.shade.pack(pady=(0, 8))
        for cv, fn in ((self.hue, self._hue_at), (self.shade, self._shade_at)):
            cv.bind("<ButtonPress-1>", fn)
            cv.bind("<B1-Motion>", fn)

        tk.Label(self, text="From your picture", bg=T.CARD, fg=T.MUTED, anchor="w").pack(
            fill="x")
        self._row = tk.Frame(self, bg=T.CARD)
        self._row.pack(fill="x", pady=(6, 0))
        self.set_palette(palette)
        self._draw()

    def set_palette(self, palette):
        """Show these picture colours as one-click chips."""
        for c in self._row.winfo_children():
            c.destroy()
        for col in palette[:7]:
            img = _disc(28, ring_mod.to_hex(col), T.BORDER)
            c = tk.Label(self._row, image=img, bg=T.CARD, cursor="hand2", bd=0)
            c.image = img
            c.pack(side="left", padx=(0, 4))
            c.bind("<Button-1>", lambda e, col=col: self._chip(col))

    def set_colour(self, colour):
        """Move the strips to a colour chosen elsewhere (a style, say)."""
        self.h, self.l, self.s = colorsys.rgb_to_hls(*(v / 255 for v in colour))
        self.s = max(self.s, 0.35)
        self._draw()

    def _rgb(self):
        return tuple(round(v * 255) for v in colorsys.hls_to_rgb(self.h, self.l, self.s))

    def _strip(self, colours):
        """A smooth horizontal gradient image from a list of RGB tuples (one per pixel)."""
        im = Image.new("RGB", (self.W, self.BAR))
        d = ImageDraw.Draw(im)
        for x, c in enumerate(colours):
            d.line([(x, 0), (x, self.BAR)], fill=c)
        return ImageTk.PhotoImage(im)

    def _draw(self):
        """Repaint both strips and their knobs for the current colour."""
        hs = [tuple(round(v * 255) for v in colorsys.hls_to_rgb(x / (self.W - 1), 0.5, 0.75))
              for x in range(self.W)]
        ls = [tuple(round(v * 255) for v in colorsys.hls_to_rgb(
            self.h, 0.18 + 0.64 * x / (self.W - 1), self.s)) for x in range(self.W)]
        self._hi, self._si = self._strip(hs), self._strip(ls)
        for cv, img, pos in ((self.hue, self._hi, self.h * (self.W - 1)),
                             (self.shade, self._si,
                              (self.l - 0.18) / 0.64 * (self.W - 1))):
            cv.delete("all")
            cv.create_image(0, 3, anchor="nw", image=img)
            x = max(3, min(self.W - 3, pos))
            cv.create_rectangle(x - 3, 0, x + 3, self.BAR + 6, fill="white",
                                outline=T.TEAL, width=2)

    def _emit(self):
        self._draw()
        self.on_pick(self._rgb())

    def _hue_at(self, e):
        self.h = max(0.0, min(1.0, e.x / (self.W - 1)))
        self._emit()

    def _shade_at(self, e):
        self.l = 0.18 + 0.64 * max(0.0, min(1.0, e.x / (self.W - 1)))
        self._emit()

    def _chip(self, col):
        r, g, b = (v / 255 for v in col)
        self.h, self.l, self.s = colorsys.rgb_to_hls(r, g, b)
        self.s = max(self.s, 0.35)
        self._draw()
        self.on_pick(tuple(col))
