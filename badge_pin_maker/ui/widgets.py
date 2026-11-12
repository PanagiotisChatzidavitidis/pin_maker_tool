"""Small reusable interface pieces: cards, statistic tiles, the on/off switch and a rounded-
rectangle helper.
"""

import tkinter as tk
from tkinter import ttk

from . import smooth, theme as T


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
    """A slim statistic card: a small icon, a value (with an optional muted "/ total") and a
    caption beside it, and, for a tile with a bar, a thin progress strip along its bottom edge.
    """
    BAR_H = 3

    def __init__(self, parent, font_family, icon, label=None, bar=False):
        """Build an empty tile; fill it with set(). ``icon`` is a smooth.stat_icon kind."""
        super().__init__(parent, bg=T.BORDER)
        inner = tk.Frame(self, bg=T.CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self._bar = None
        if bar:
            self._frac, self._goal, self._job = 0.0, 0.0, None
            self._bar = tk.Canvas(inner, height=self.BAR_H, bg=T.CARD, highlightthickness=0)
            self._bar.pack(side="bottom", fill="x")
            self._bar.bind("<Configure>", lambda e: self._draw_bar())
        row = tk.Frame(inner, bg=T.CARD)
        row.pack(fill="x", padx=14, pady=8)
        self._icon = smooth.stat_icon(icon, T.TEAL, T.CARD)
        tk.Label(row, image=self._icon, bg=T.CARD).pack(side="left", padx=(0, 12))
        col = tk.Frame(row, bg=T.CARD)
        col.pack(side="left", fill="x", expand=True)
        top = tk.Frame(col, bg=T.CARD)
        top.pack(fill="x")
        self.value = tk.Label(top, bg=T.CARD, fg=T.PETROL, anchor="w",
                              font=("Georgia", 15, "bold"))
        self.value.pack(side="left")
        self.total = tk.Label(top, bg=T.CARD, fg=T.MUTED, anchor="w", font=(font_family, 10))
        self.total.pack(side="left", padx=(6, 0), pady=(3, 0))
        self.caption = tk.Label(col, bg=T.CARD, fg=T.MUTED, anchor="w", font=(font_family, 9))
        self.caption.pack(fill="x")

    def set(self, value, caption="", total=None, progress=None, warn=False):
        """Show ``value`` (big), an optional muted ``total`` after it, a ``caption`` under it
        and a ``progress`` bar position (0 to 1). ``warn`` colours the caption as a warning.
        """
        self.value.config(text=value)
        self.total.config(text="" if total is None else f"/ {total}")
        self.caption.config(text=caption, fg=T.WARN if warn else T.MUTED)
        if self._bar is not None and progress is not None:
            self._goal = max(0.0, min(1.0, progress))
            if self._job is None:
                self._job = self.after(0, self._glide)

    def _glide(self):
        """Ease the bar towards its new position over a few quick frames."""
        self._job = None
        gap = self._goal - self._frac
        self._frac = self._goal if abs(gap) < 0.004 else self._frac + gap * 0.3
        self._draw_bar()
        if self._frac != self._goal:
            self._job = self.after(16, self._glide)

    def _draw_bar(self):
        """Paint the track and the accent fill."""
        c, w = self._bar, self._bar.winfo_width()
        c.delete("all")
        if w < 4:
            return
        c.create_rectangle(0, 0, w, self.BAR_H, fill=T._mix(T.CARD, T.TEXT, 0.12), outline="")
        fw = int(w * self._frac)
        if fw > 0:
            c.create_rectangle(0, 0, fw, self.BAR_H, fill=T.TEAL, outline="")


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
        self._img = smooth.switch(self.W, self.H, on, T.TEAL if on else T.SAND_PRESS, "#FFFFFF",
                                  self.cget("bg"))
        self.create_image(0, 0, anchor="nw", image=self._img)


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
                lbl.config(bg=T.TEAL, fg=T.ON_PRIMARY)
            else:
                lbl.config(bg=T.HOVER if value == hover else T.CARD, fg=T.TEXT)


class ThemeTile(tk.Canvas):
    """A clickable card that previews one theme in its own colours: its background, its
    title and note, and four colour dots (surface, main, accent, text). The chosen theme
    gets a thick outline in its main colour and a tick.
    """
    W, H = 292, 44

    def __init__(self, parent, colours, title, note, selected, command, font_family, bg=None):
        """``colours`` is the theme's colour dict (see theme.THEMES). ``command`` runs when
        the tile is clicked.
        """
        super().__init__(parent, width=self.W, height=self.H, bg=bg or T.BG,
                         highlightthickness=0, cursor="hand2")
        self.c, self.title, self.note = colours, title, note
        self.selected, self.command, self.fam = selected, command, font_family
        self._hover = False
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def _set_hover(self, on):
        """Outline the tile lightly while the mouse is over it."""
        self._hover = on
        self._draw()

    def _draw(self):
        """Paint the tile."""
        c, w, h = self.c, self.W, self.H
        self.delete("all")
        if self.selected:
            edge, width = c["TEAL"], 3
        else:
            edge, width = (c["MUTED"] if self._hover else c["BORDER"]), 1
        # the card, the colour dots and the tick are one smooth picture; the words go on top
        x = w - 124
        dots = [(c[key], c["BORDER"] if key == "CARD" else c[key])
                for key in ("CARD", "TEAL", "ORCHID", "TEXT")]
        tick = (w - 24, c["TEAL"], c["ON_PRIMARY"]) if self.selected else None
        self._img = smooth.tile_face(w, h, self.cget("bg"), c["BG"], edge, width, dots, x, tick)
        self.create_image(0, 0, anchor="nw", image=self._img)
        self.create_text(18, 16, text=self.title, anchor="w", fill=c["TEXT"],
                         font=(self.fam, 11, "bold"))
        self.create_text(18, 31, text=self.note, anchor="w", fill=c["MUTED"],
                         font=(self.fam, 9))


class IconButton(tk.Canvas):
    """A small square button with a drawn icon ("undo" or "redo": a curved arrow). Drawn
    rather than typed, so it looks the same on every system and font. It can be greyed out
    with state(["disabled"]) / state(["!disabled"]), like a ttk button.
    """
    SIZE = 34

    def __init__(self, parent, kind, command, tip="", on_tip=None):
        """``kind`` is "undo" or "redo"; ``on_tip(text or None)`` is told when to show / hide
        the hint ``tip``.
        """
        super().__init__(parent, width=self.SIZE, height=self.SIZE, bg=T.BG,
                         highlightthickness=0, cursor="hand2")
        self.kind, self.command, self.tip, self.on_tip = kind, command, tip, on_tip
        self._disabled, self._hover, self._down = False, False, False
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def state(self, spec=None):
        """["disabled"] / ["!disabled"] changes the state; without an argument it returns the
        current flags (so "disabled" in btn.state() works).
        """
        if spec is None:
            return ("disabled",) if self._disabled else ()
        for s in spec:
            if s == "disabled":
                self._disabled = True
            elif s == "!disabled":
                self._disabled = False
        self.config(cursor="arrow" if self._disabled else "hand2")
        self._draw()

    def instate(self, spec):
        """True if the button is in the given state: ["disabled"] or ["!disabled"]."""
        return all(self._disabled if f == "disabled" else not self._disabled for f in spec)

    def invoke(self):
        """Press the button from code (does nothing while it is greyed out)."""
        if not self._disabled:
            self.command()

    def _set(self, hover=None, down=None):
        """Remember the mouse state, redraw, and show / hide the hint."""
        if hover is not None:
            self._hover = hover
            if self.on_tip:
                self.on_tip(self.tip if hover and not self._disabled else None)
        if down is not None:
            self._down = down
        self._draw()

    def _release(self, _e=None):
        """Mouse up: run the command if the button was pressed and is usable."""
        was, self._down = self._down, False
        self._draw()
        if was and self._hover and not self._disabled:
            self.command()

    def _draw(self):
        """Paint the tile and the arrow."""
        self.delete("all")
        bg = T.SAND_PRESS if (self._down and not self._disabled) else (
            T.SAND_HOVER if (self._hover and not self._disabled) else T.SAND)
        # greyed out = the text colour faded toward the tile, but still clearly visible
        fg = T._mix(T.TEXT, bg, 0.5) if self._disabled else T.TEXT
        self._img = smooth.arrow_icon(self.kind, fg, bg, T.BORDER, self.SIZE)
        self.create_image(0, 0, anchor="nw", image=self._img)


class MascotTile(tk.Canvas):
    """A card showing one mascot's portrait and name, for the Options window. The one in use
    has a coloured outline and a tick. Clicking runs ``command``; the portrait hops when it is
    picked.
    """
    W, H, PORTRAIT = 88, 116, 62

    def __init__(self, parent, mid, name, selected, command, fam):
        """``mid`` is the mascot's id, ``name`` what is written under it."""
        super().__init__(parent, width=self.W, height=self.H, bg=T.CARD, highlightthickness=0,
                         cursor="hand2")
        from . import mascot
        self.mid, self.name, self.selected, self.command, self.fam = mid, name, selected, command, fam
        self._hover, self._hop_job, self._dy = False, None, 0
        self._portrait = mascot.photo(mid, self.PORTRAIT)
        if self._portrait is None:                         # no picture file: the pin icon
            from .icons import load_logo
            self._portrait = load_logo(self.PORTRAIT)
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self._draw()

    def _set_hover(self, on):
        """Light up while the mouse is over the card."""
        self._hover = on
        self._draw()

    def set_selected(self, on):
        """Show (or take away) the outline and tick."""
        self.selected = on
        self._draw()

    def _draw(self):
        """Paint the plate, the portrait and the name."""
        self.delete("all")
        w, h = self.W, self.H
        edge = T.TEAL if self.selected else T.BORDER
        fill = T.HOVER if (self._hover and not self.selected) else T.BG
        badge = (w - 17, 17, T.TEAL, T.ON_PRIMARY) if self.selected else None
        self._plate = smooth.plate(w, h, T.CARD, fill, edge, 2 if self.selected else 1,
                                   badge=badge)
        self.create_image(0, 0, anchor="nw", image=self._plate)
        self._item = self.create_image(w / 2, 14 + self.PORTRAIT / 2 + self._dy,
                                       image=self._portrait)
        self.create_text(w / 2, h - 16, text=self.name, fill=T.PETROL if self.selected else T.TEXT,
                         font=("Georgia", 10, "bold"))

    def hop(self):
        """A little jump, to say hello."""
        if self._hop_job is not None:
            self.after_cancel(self._hop_job)
        steps = (0, -10, -14, -9, 0, -4, 0)

        def frame(i):
            self._hop_job = None
            if i >= len(steps):
                return
            try:
                self.move(self._item, 0, steps[i] - self._dy)
                self._dy = steps[i]
                self._hop_job = self.after(45, frame, i + 1)
            except tk.TclError:
                pass
        frame(0)


class _Pill(tk.Canvas):
    """A rounded pill-shaped control: a smooth background picture that changes with hover and
    focus, and room for icons and text on top. The base of the search field and sort menu.
    """
    H = 40

    def __init__(self, parent, width):
        super().__init__(parent, width=width, height=self.H, bg=T.BG, highlightthickness=0, bd=0)
        self.w, self.state = width, "rest"
        self._bg_img = None
        self._set_state("rest")

    def _set_state(self, state):
        """Redraw the pill for "rest", "hover" or "focus"."""
        self.state = state
        edge = {"rest": T.BORDER, "hover": T._mix(T.BORDER, T.TEAL, 0.5), "focus": T.TEAL}[state]
        self._bg_img = smooth.pill(self.w, self.H, T.CARD, edge, T.BG, 2 if state == "focus" else 1)
        if self.find_withtag("pillbg"):
            self.itemconfig("pillbg", image=self._bg_img)
        else:
            self.create_image(0, 0, image=self._bg_img, anchor="nw", tags="pillbg")
            self.tag_lower("pillbg")


class SearchField(_Pill):
    """A search box: a magnifier, the text you type (with a faint hint when empty) and a small
    cross to clear it. ``variable`` holds the text.
    """

    def __init__(self, parent, variable, hint="Search canvases", width=340, family="TkDefaultFont"):
        super().__init__(parent, width)
        self.var = variable
        self._icon = smooth.nav_icon("search", T.MUTED, T.CARD, 18)
        self.create_image(16, self.H // 2, image=self._icon, anchor="w")
        self.entry = tk.Entry(self, textvariable=variable, bd=0, relief="flat", bg=T.CARD,
                              fg=T.TEXT, insertbackground=T.TEXT, highlightthickness=0,
                              font=(family, 10), selectbackground=T._mix(T.CARD, T.TEAL, 0.4),
                              selectforeground=T.TEXT)
        self.create_window(44, self.H // 2, window=self.entry, anchor="w", width=width - 44 - 40,
                           height=22)
        self._hint = self.create_text(46, self.H // 2, text=hint, anchor="w", fill=T.MUTED,
                                      font=(family, 10))
        self._x_img = smooth.nav_icon("close", T.MUTED, T.CARD, 18)
        self._x_hover = smooth.nav_icon("close", T.TEAL, T.CARD, 18)
        self._x = self.create_image(width - 18, self.H // 2, image=self._x_img, tags="clear")
        self.tag_bind("clear", "<Button-1>", lambda e: (variable.set(""), self.entry.focus_set()))
        self.tag_bind("clear", "<Enter>", lambda e: (self.itemconfig(self._x, image=self._x_hover),
                                                     self.config(cursor="hand2")))
        self.tag_bind("clear", "<Leave>", lambda e: (self.itemconfig(self._x, image=self._x_img),
                                                     self.config(cursor="")))
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<Escape>", lambda e: (variable.set(""), "break")[1])
        self.entry.bind("<FocusIn>", lambda e: self._set_state("focus"))
        self.entry.bind("<FocusOut>", lambda e: self._set_state("rest"))
        for w in (self, self.entry):
            w.bind("<Enter>", lambda e: self.state == "rest" and self._set_state("hover"), add="+")
            w.bind("<Leave>", lambda e: self.state == "hover" and self._set_state("rest"), add="+")
        self._tid = variable.trace_add("write", lambda *_: self._sync())
        self.bind("<Destroy>", self._on_destroy)
        self._sync()

    def _sync(self):
        """Show the hint only when empty, and the clear cross only when there is text."""
        try:
            has = bool(self.var.get())
            self.itemconfig(self._hint, state="hidden" if has else "normal")
            self.itemconfig(self._x, state="normal" if has else "hidden")
        except tk.TclError:
            pass

    def _on_destroy(self, e):
        """Stop listening to the variable once this has been destroyed."""
        if e.widget is self:
            try:
                self.var.trace_remove("write", self._tid)
            except (tk.TclError, ValueError):
                pass


class SortMenu(_Pill):
    """A "Sort by" pill: an icon, the current choice and a chevron. Clicking opens a small
    rounded list of the choices (the current one ticked); picking one closes it.
    """

    def __init__(self, parent, variable, options, command=None, width=214, family="TkDefaultFont"):
        super().__init__(parent, width)
        self.var, self.options, self.command, self.family = variable, list(options), command, family
        self.popup = None
        self._imgs = {k: smooth.nav_icon(k, T.MUTED, T.CARD, 18) for k in ("sort", "chevron")}
        self.create_image(16, self.H // 2, image=self._imgs["sort"], anchor="w")
        self._text = self.create_text(44, self.H // 2, anchor="w", fill=T.TEXT, font=(family, 10))
        self.create_image(width - 20, self.H // 2, image=self._imgs["chevron"])
        self.config(cursor="hand2")
        self.bind("<Button-1>", lambda e: self.toggle())
        self.bind("<Enter>", lambda e: self.state == "rest" and self._set_state("hover"))
        self.bind("<Leave>", lambda e: self.state == "hover" and self._set_state("rest"))
        self._tid = variable.trace_add("write", lambda *_: self._sync())
        self.bind("<Destroy>", self._on_destroy)
        self._sync()

    def _sync(self):
        """Show what is chosen now."""
        try:
            self.itemconfig(self._text, text=self.var.get())
        except tk.TclError:
            pass

    def _on_destroy(self, e):
        """Close the list and stop listening when this goes away."""
        if e.widget is self:
            self.close()
            try:
                self.var.trace_remove("write", self._tid)
            except (tk.TclError, ValueError):
                pass

    def toggle(self):
        """Open the list, or close it if it is open."""
        if self.popup is not None:
            self.close()
        else:
            self.open()

    def open(self):
        """Show the choices in a small themed box just under the pill."""
        self._set_state("focus")
        pop = self.popup = tk.Toplevel(self)
        pop.withdraw()
        pop.overrideredirect(True)
        pop.configure(bg=T.BORDER)
        inner = tk.Frame(pop, bg=T.CARD)
        inner.pack(padx=1, pady=1)
        check = smooth.nav_icon("check", T.TEAL, T.CARD, 18)
        blank = smooth.nav_icon("check", T.CARD, T.CARD, 18)
        pop._imgs = [check, blank]
        rows = []
        for opt in self.options:
            row = tk.Frame(inner, bg=T.CARD, cursor="hand2")
            row.pack(fill="x", padx=6, pady=(6 if opt == self.options[0] else 0,
                                             6 if opt == self.options[-1] else 0))
            on = opt == self.var.get()
            icon = tk.Label(row, image=check if on else blank, bg=T.CARD, bd=0)
            icon.pack(side="left", padx=(8, 6), pady=7)
            text = tk.Label(row, text=opt, bg=T.CARD, fg=T.TEAL if on else T.TEXT, anchor="w",
                            font=(self.family, 10, "bold" if on else "normal"))
            text.pack(side="left", fill="x", expand=True, padx=(0, 16))
            rows.append((row, icon, text))
            for w in (row, icon, text):
                w.bind("<Button-1>", lambda e, o=opt: self._choose(o))
                w.bind("<Enter>", lambda e, r=row: self._tint(r, True))
                w.bind("<Leave>", lambda e, r=row: self._tint(r, False))
        pop._rows = rows
        pop.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width() - pop.winfo_reqwidth()
        y = self.winfo_rooty() + self.winfo_height() + 6
        pop.geometry(f"+{x}+{y}")
        pop.deiconify()
        pop.lift()
        pop.bind("<Escape>", lambda e: self.close())
        pop.bind("<FocusOut>", lambda e: self.after(80, self._lost_focus))
        pop.focus_force()

    def _tint(self, row, on):
        """Light up the row under the pointer."""
        if self.popup is None:
            return
        col = T.HOVER if on else T.CARD
        for r, icon, text in self.popup._rows:
            if r is row:
                for w in (r, icon, text):
                    w.config(bg=col)

    def _lost_focus(self):
        """Close the list when you click anywhere else."""
        try:
            if self.popup is not None and self.popup.focus_displayof() is None:
                self.close()
        except tk.TclError:
            self.close()

    def _choose(self, option):
        """A choice was clicked."""
        changed = option != self.var.get()
        self.var.set(option)
        self.close()
        if changed and self.command:
            self.command()

    def close(self):
        """Close the list (if open)."""
        pop, self.popup = self.popup, None
        if pop is not None:
            try:
                pop.destroy()
            except tk.TclError:
                pass
        try:
            self._set_state("rest")
        except tk.TclError:
            pass
