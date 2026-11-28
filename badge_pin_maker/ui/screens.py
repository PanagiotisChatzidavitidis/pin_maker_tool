"""Full-page screens (Preview pins, Options) that sit on top of the page they were opened from.

A screen covers its host (the main window, or the crop window) completely, has a Return button in
its top-left corner, and when it closes the page underneath is simply uncovered: the start menu
or the project, whichever it was opened from.
"""

import tkinter as tk

from . import theme as T
from .buttons import Btn


class Screen(tk.Frame):
    """A page that fills its host. ``back()`` removes it and returns to whatever is below."""

    def __init__(self, host):
        super().__init__(host, bg=T.BG)
        self.host = host
        self.top = host.winfo_toplevel()
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()
        self.bind("<Escape>", lambda e: self.back())

    @staticmethod
    def open(host, cls, *args, **kw):
        """Open a screen on ``host`` unless one is already open there."""
        if getattr(host, "_screen", None) is not None and host._screen.winfo_exists():
            return host._screen
        scr = cls(host, *args, **kw)
        host._screen = scr
        return scr

    def return_bar(self, title, sub="", right=None, pad=28):
        """The strip at the top: Return on the left, the page title, and optional extras on
        the right (``right(frame)`` fills it). Returns the strip.
        """
        bar = tk.Frame(self, bg=T.BG)
        bar.pack(side="top", fill="x", padx=pad, pady=(18, 8))
        Btn(bar, "Return", self.back, kind="ghost", bg=T.BG, icon="back").pack(side="left")
        names = tk.Frame(bar, bg=T.BG)
        names.pack(side="left", padx=(18, 0))
        tk.Label(names, text=title, bg=T.BG, fg=T.TEXT, font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        if sub:
            tk.Label(names, text=sub, bg=T.BG, fg=T.MUTED).pack(anchor="w")
        if right:
            box = tk.Frame(bar, bg=T.BG)
            box.pack(side="right")
            right(box)
        tk.Frame(self, bg=T.BORDER, height=1).pack(side="top", fill="x")
        return bar

    def on_close(self):
        """Hook: stop timers or threads before the screen goes."""

    def back(self):
        """Return to the page this screen was opened from."""
        try:
            self.on_close()
            self.host._screen = None
        finally:
            self.destroy()
        try:
            self.host.focus_set()
        except tk.TclError:
            pass
        raiser = getattr(self.top, "toasts", None)
        if raiser is not None and self.host is self.top:
            raiser.raise_all()
