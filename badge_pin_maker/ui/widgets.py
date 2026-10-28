"""Small reusable interface pieces: cards, statistic tiles, the on/off switch and a rounded-
rectangle helper.
"""

import tkinter as tk
from tkinter import ttk

from . import theme as T


def make_card(parent, title, pady=(0, 10)):
    """A bordered card with an optional title. Returns the inner frame to put widgets in."""
    outer = tk.Frame(parent, bg=T.BORDER)
    outer.pack(fill="x", pady=pady)
    inner = ttk.Frame(outer, style="Card.TFrame", padding=(14, 10))
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    if title:
        ttk.Label(inner, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))
    return inner


class StatTile(tk.Frame):
    """A small card with a big value and a caption underneath."""
    def __init__(self, parent, font_family):
        """Build an empty tile; fill it with set()."""
        super().__init__(parent, bg=T.BORDER)
        inner = tk.Frame(self, bg=T.CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.value = tk.Label(inner, bg=T.CARD, fg=T.PETROL, anchor="w",
                              font=("Georgia", 20, "bold"))
        self.value.pack(fill="x", padx=14, pady=(9, 0))
        self.caption = tk.Label(inner, bg=T.CARD, fg=T.MUTED, anchor="w",
                                font=(font_family, 9))
        self.caption.pack(fill="x", padx=14, pady=(0, 10))

    def set(self, value, caption, warn=False):
        """Show ``value`` (big) and ``caption`` (small). ``warn`` colours the caption as a
        warning.
        """
        self.value.config(text=value)
        self.caption.config(text=caption, fg=T.WARN if warn else T.MUTED)


def round_rect(canvas, x0, y0, x1, y1, r, **kw):
    """Rounded rectangle on a canvas."""
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
           x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Toggle(tk.Canvas):
    """A small on/off pill switch bound to a BooleanVar (reads cleanly in both themes)."""
    W, H = 44, 24

    def __init__(self, parent, variable, command=None, bg=None):
        """``variable`` is a tk.BooleanVar. ``command`` (optional) runs after each click."""
        super().__init__(parent, width=self.W, height=self.H, bg=bg or T.CARD,
                         highlightthickness=0, cursor="hand2")
        self.var, self.command = variable, command
        self._tid = variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Button-1>", self._click)
        self.bind("<Destroy>", self._on_destroy)
        self._draw()

    def _on_destroy(self, e):
        """Stop listening to the variable once the switch has been destroyed."""
        if e.widget is self:
            try:
                self.var.trace_remove("write", self._tid)
            except (tk.TclError, ValueError):
                pass

    def _click(self, _e=None):
        """Flip the value when the switch is clicked."""
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def _draw(self):
        """Paint the pill and its sliding knob for the current on / off state."""
        try:
            on = bool(self.var.get())
            self.delete("all")
        except tk.TclError:
            return
        w, h = self.W, self.H
        col = T.TEAL if on else T.SAND_PRESS
        r = h / 2
        self.create_oval(0, 0, h, h, fill=col, outline=col)
        self.create_oval(w - h, 0, w, h, fill=col, outline=col)
        self.create_rectangle(r, 0, w - r, h, fill=col, outline=col)
        pad = 3
        x0 = w - h + pad if on else pad
        self.create_oval(x0, pad, x0 + h - 2 * pad, h - pad, fill="white", outline="")


class Segmented(tk.Frame):
    """A row of side-by-side choices where exactly one is selected (like "Full screen |
    Windowed"), bound to a StringVar."""
    def __init__(self, parent, variable, options, command=None, bg=None):
        """``options`` is a list of (value, label) pairs. ``command`` (optional) runs after the
        person picks one.
        """
        super().__init__(parent, bg=T.BORDER)
        self.var, self.command = variable, command
        self._labels = {}
        font = ttk.Style().lookup("TLabel", "font") or "TkDefaultFont"   # same font as the app
        for col, (value, text) in enumerate(options):
            lbl = tk.Label(self, text=text, padx=18, pady=8, cursor="hand2", bg=T.CARD,
                           font=font)
            lbl.grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            self.columnconfigure(col, weight=1, uniform="segments")
            lbl.bind("<Button-1>", lambda e, v=value: self._pick(v))
            lbl.bind("<Enter>", lambda e, v=value: self._paint(hover=v))
            lbl.bind("<Leave>", lambda e: self._paint())
            self._labels[value] = lbl
        self._tid = variable.trace_add("write", lambda *_: self._paint())
        self.bind("<Destroy>", self._on_destroy)
        self._paint()

    def _on_destroy(self, e):
        """Stop listening to the variable once the control has been destroyed."""
        if e.widget is self:
            try:
                self.var.trace_remove("write", self._tid)
            except (tk.TclError, ValueError):
                pass

    def _pick(self, value):
        """Select a choice."""
        self.var.set(value)
        if self.command:
            self.command()

    def _paint(self, hover=None):
        """Colour the selected choice teal and the others plain (a hovered one lightly
        highlighted).
        """
        try:
            current = self.var.get()
        except tk.TclError:
            return
        for value, lbl in self._labels.items():
            if value == current:
                lbl.config(bg=T.TEAL, fg="white")
            else:
                lbl.config(bg=T.HOVER if value == hover else T.CARD, fg=T.TEXT)
