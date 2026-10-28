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


class FlatSlider(tk.Canvas):
    """A slim rounded slider bound to a DoubleVar: a rounded track, a teal fill and a round
    knob. Clicking the track jumps there, dragging follows the mouse and the wheel nudges it.

    ``origin`` is the value the teal fill grows from (the left end by default; 0 makes a
    centred slider for rotation). ``snaps`` are values the knob sticks to when it is dragged
    within ``snap_tol`` of them; small ticks mark them. ``command`` runs only when the person
    moves the slider, not when the variable is changed from code.
    """
    H = 28
    PAD = 12          # room for the knob at each end
    TRACK = 6
    KNOB = 9          # knob radius

    def __init__(self, parent, variable, from_, to, origin=None, snaps=(), snap_tol=0.0,
                 command=None, bg=None):
        """``variable`` is a tk.DoubleVar; ``from_`` / ``to`` are the value range."""
        super().__init__(parent, height=self.H, bg=bg or T.CARD, highlightthickness=0,
                         cursor="hand2")
        self.var, self.lo, self.hi = variable, from_, to
        self.origin = from_ if origin is None else origin
        self.snaps, self.snap_tol, self.command = tuple(snaps), snap_tol, command
        self._hover = self._drag = False
        self._tid = variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<MouseWheel>", lambda e: self._nudge(1 if e.delta > 0 else -1))
        self.bind("<Button-4>", lambda e: self._nudge(1))
        self.bind("<Button-5>", lambda e: self._nudge(-1))
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, e):
        """Stop listening to the variable once the slider has been destroyed."""
        if e.widget is self:
            try:
                self.var.trace_remove("write", self._tid)
            except (tk.TclError, ValueError):
                pass

    def _x_of(self, value):
        """Pixel position of a value along the track."""
        span = max(1, self.winfo_width() - 2 * self.PAD)
        return self.PAD + span * (value - self.lo) / (self.hi - self.lo)

    def _value_at(self, x):
        """The slider value for a pixel position (snapped to a tick when close to one)."""
        span = max(1, self.winfo_width() - 2 * self.PAD)
        v = self.lo + (self.hi - self.lo) * (x - self.PAD) / span
        v = min(self.hi, max(self.lo, v))
        for s in self.snaps:
            if abs(v - s) <= self.snap_tol:
                return s
        return v

    def _user_set(self, value):
        """Change the value because the person moved the slider."""
        if self.command:
            self.command()
        self.var.set(value)

    def _press(self, e):
        """Jump to the clicked spot and start a drag."""
        self._drag = True
        self._user_set(self._value_at(e.x))
        self._draw()

    def _move(self, e):
        """Follow the mouse while it is held down."""
        if self._drag:
            self._user_set(self._value_at(e.x))

    def _release(self, _e):
        """End the drag."""
        self._drag = False
        self._draw()

    def _set_hover(self, on):
        """Make the knob a little bigger while the mouse is over the slider."""
        self._hover = on
        self._draw()

    def _nudge(self, direction):
        """Mouse wheel: move by 2% of the range."""
        step = (self.hi - self.lo) * 0.02 * direction
        self._user_set(min(self.hi, max(self.lo, self.var.get() + step)))

    def _draw(self):
        """Paint the track, ticks, teal fill and knob for the current value."""
        try:
            value = float(self.var.get())
            self.delete("all")
        except (tk.TclError, ValueError):
            return
        w, cy = self.winfo_width(), self.H / 2
        if w < 2 * self.PAD + 4:
            return
        self.create_line(self.PAD, cy, w - self.PAD, cy, width=self.TRACK, capstyle="round",
                         fill=T.BORDER)
        for s in self.snaps:
            x = self._x_of(s)
            self.create_line(x, cy - 8, x, cy - 5, width=2, fill=T.MUTED)
        x0, x1 = sorted((self._x_of(self.origin), self._x_of(value)))
        if x1 - x0 > 0.5:
            self.create_line(x0, cy, x1, cy, width=self.TRACK, capstyle="round", fill=T.TEAL)
        r = self.KNOB + (2 if self._hover or self._drag else 0)
        kx = self._x_of(value)
        self.create_oval(kx - r, cy - r + 1.5, kx + r, cy + r + 1.5, fill=T.SHADOW_A,
                         outline="")                               # soft drop shadow
        self.create_oval(kx - r, cy - r, kx + r, cy + r, fill="white", outline=T.TEAL, width=2)


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
