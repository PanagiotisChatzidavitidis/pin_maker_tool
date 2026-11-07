"""A smooth change from one theme to another: every colour on screen drifts to its new value.

Nothing is covered or captured. The colours of the widgets already on screen (and of the
shapes drawn on canvases) are blended a little further towards the new theme on every frame,
and the ttk styles (buttons, fields, scrollbars) are re-made from the blended colours. After
the last frame the exact theme is applied and the screens are rebuilt, which now looks the
same as what is on screen, except that the small drawn icons take their final colour.
"""

import tkinter as tk
from tkinter import ttk

from . import theme as T

# widget options that hold a colour
WIDGET_COLOUR_OPTIONS = (
    "background", "foreground", "highlightbackground", "highlightcolor", "activebackground",
    "activeforeground", "selectbackground", "selectforeground", "insertbackground",
    "troughcolor", "disabledforeground", "readonlybackground",
)
# canvas item options that hold a colour
ITEM_COLOUR_OPTIONS = ("fill", "outline", "activefill", "activeoutline", "disabledfill",
                       "disabledoutline")


def _palette(name):
    """The colour names of a theme that are plain "#rrggbb" strings."""
    return {k: v.lower() for k, v in T.THEMES[name].items()
            if isinstance(v, str) and v.startswith("#") and len(v) == 7}


class ThemeMorph:
    """One running theme change. Make it and it starts; finish() jumps to the end."""
    FRAMES = 14
    FRAME_MS = 16

    def __init__(self, app, old_name, new_name, on_done):
        """Find every colour that belongs to the old theme and start blending it."""
        self.app, self.on_done = app, on_done
        self.old, self.new = _palette(old_name), _palette(new_name)
        self.new_name = new_name
        self.k, self.job, self.done = 0, None, False
        by_hex = {}
        for key, hexval in self.old.items():
            by_hex.setdefault(hexval, key)
        self.hex_keys = by_hex
        self.slots = []              # (widget, option, key)
        self.items = []              # (canvas, item id, option, key)
        self._collect(app)
        self._ttk_globals = {k: getattr(T, k) for k in self.old if hasattr(T, k)}
        self._step()

    # ---- finding the colours ---------------------------------------------------------
    def _key_of(self, value):
        """The theme colour name behind a colour value, or None."""
        try:
            return self.hex_keys.get(str(value).lower())
        except (TypeError, AttributeError):
            return None

    def _collect(self, widget):
        """Walk the widget tree (the app and any window open over it)."""
        if not isinstance(widget, ttk.Widget):          # ttk widgets follow their styles
            for opt in WIDGET_COLOUR_OPTIONS:
                try:
                    key = self._key_of(widget.cget(opt))
                except tk.TclError:
                    continue
                if key:
                    self.slots.append((widget, opt, key))
            if isinstance(widget, tk.Canvas):
                self._collect_items(widget)
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            self._collect(child)

    def _collect_items(self, cv):
        """The colours of everything drawn on a canvas."""
        for item in cv.find_all():
            for opt in ITEM_COLOUR_OPTIONS:
                try:
                    value = cv.itemcget(item, opt)
                except tk.TclError:
                    continue
                key = self._key_of(value) if value else None
                if key:
                    self.items.append((cv, item, opt, key))

    # ---- the animation ---------------------------------------------------------------
    def _blend(self, t):
        """Every colour name mapped to its blend between the old and the new theme."""
        return {k: T._mix(self.old[k], self.new.get(k, self.old[k]), t) for k in self.old}

    def _step(self):
        """Draw one frame, then schedule the next (or finish after the last)."""
        self.job = None
        if self.done:
            return
        self.k += 1
        t = self.k / self.FRAMES
        e = t * t * (3 - 2 * t)                          # smoothstep: gentle start and end
        col = self._blend(e)
        dead = False
        for widget, opt, key in self.slots:
            try:
                widget.configure(**{opt: col[key]})
            except tk.TclError:
                dead = True
        for cv, item, opt, key in self.items:
            try:
                cv.itemconfigure(item, **{opt: col[key]})
            except tk.TclError:
                dead = True
        self._restyle(col)
        if dead:
            self.slots = [s for s in self.slots if self._alive(s[0])]
            self.items = [i for i in self.items if self._alive(i[0])]
        if self.k >= self.FRAMES:
            self.finish()
        else:
            self.job = self.app.after(self.FRAME_MS, self._step)

    @staticmethod
    def _alive(widget):
        """True if the widget still exists."""
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _restyle(self, col):
        """Remake the ttk styles from the blended colours."""
        for key, value in col.items():
            if key in self._ttk_globals:
                setattr(T, key, value)
        try:
            T.setup_style(self.app)
        except tk.TclError:
            pass

    def finish(self):
        """Stop blending and hand over: the exact new theme is applied by the caller."""
        if self.done:
            return
        self.done = True
        if self.job is not None:
            try:
                self.app.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        for key, value in self._ttk_globals.items():          # put the real colours back
            setattr(T, key, value)
        self.on_done()
