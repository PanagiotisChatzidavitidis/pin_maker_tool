"""A quick, cute loading screen shown while the theme changes.

Switching themes means rebuilding every screen. Instead of letting that show, a plain cover in the
new theme's colours goes over the window first (Ozzie hops, three dots bounce), the screens are
rebuilt underneath it, and the cover is taken away once everything is settled.
"""

import math
import time
import tkinter as tk

from . import mascot
from . import theme as T

MIN_SHOW_MS = 420           # long enough to read as a deliberate "one moment", not a flash
FRAME_MS = 33


class ThemeCover:
    """Covers the whole window. Make it to show it; close() takes it away."""

    def __init__(self, app, theme_name):
        pal = T.THEMES[theme_name]
        self.app, self.job, self.closed = app, None, False
        self.font = (getattr(app, "base_font", None) or ("Helvetica",))[0]
        bg, text, muted = pal["BG"], pal["TEXT"], pal["MUTED"]
        accent = pal.get("TEAL", text)
        self.cv = tk.Canvas(app, bg=bg, highlightthickness=0, bd=0, cursor="watch")
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self.cv)
        self._logo = None
        try:
            self._logo = mascot.photo(mascot.current, 120)
        except Exception:  # noqa: BLE001  (no picture: the text alone is fine)
            pass
        self.cv.bind("<Configure>", lambda e: self._frame())
        self._colours = (text, muted, accent)
        self.t0 = time.monotonic()
        self._frame()
        app.update_idletasks()
        app.update()                         # make sure it is really on screen before work starts

    def lift(self):
        """Keep it above anything built while it is showing."""
        if not self.closed:
            tk.Misc.lift(self.cv)

    def _frame(self):
        """Draw one frame: the mascot hopping, a label and three bouncing dots."""
        self.job = None
        if self.closed:
            return
        cv = self.cv
        text, muted, accent = self._colours
        w, h = max(cv.winfo_width(), 200), max(cv.winfo_height(), 200)
        t = time.monotonic() - self.t0
        cx, cy = w / 2, h / 2
        cv.delete("all")
        hop = abs(math.sin(t * 5.5)) * 16
        if self._logo is not None:
            cv.create_image(cx, cy - 36 - hop, image=self._logo)
        cv.create_text(cx, cy + 50, text="Changing theme", fill=text,
                       font=(self.font, 15, "bold"))
        for i in range(3):
            up = max(0.0, math.sin(t * 7 - i * 0.9)) * 7
            x = cx - 18 + i * 18
            cv.create_oval(x - 4, cy + 80 - up - 4, x + 4, cy + 80 - up + 4,
                           fill=accent if i == 1 else muted, outline="")
        self.job = self.app.after(FRAME_MS, self._frame)

    def close(self, then=None):
        """Take the cover away (once it has been up long enough), then call ``then``."""
        left = MIN_SHOW_MS - (time.monotonic() - self.t0) * 1000
        if left > 0:
            self.app.after(int(left), lambda: self.close(then))
            return
        self.closed = True
        if self.job is not None:
            try:
                self.app.after_cancel(self.job)
            except tk.TclError:
                pass
        try:
            self.cv.destroy()
        except tk.TclError:
            pass
        if then:
            then()
