"""A quick, cute loading screen shown while the theme changes.

Switching themes means rebuilding every screen. Instead of letting that show, a plain cover in the
new theme's colours goes over the window first (Ozzie hops, a ring of dots turns round him, and he says something cute), the screens are
rebuilt underneath it, and the cover is taken away once everything is settled.
"""

import math
import os
import platform
import random
import struct
import tempfile
import time
import tkinter as tk

from PIL import Image, ImageDraw

from . import mascot
from . import theme as T

# What Ozzie says while waiting: one of these is picked at random each time.
MESSAGES = (
    "One moment, dressing everything in {theme}!",
    "Hold tight, painting it all {theme} for you...",
    "Almost there, Ozzie is tidying up in {theme}!",
)
MIN_SHOW_MS = int(os.environ.get("OZZIE_COVER_MS", 900))   # long enough to read the message
FRAME_MS = 33


def _cursor(theme_name, accent):
    """A mouse pointer for the loading screen (Windows only, else None): a loading circle in
    the theme's colour. Written once per theme as a .cur file.
    """
    if platform.system() != "Windows":
        return None
    path = os.path.join(tempfile.gettempdir(), f"ozzie_ring_{theme_name}.cur")
    if not os.path.exists(path):
        try:
            n = 32
            im = Image.new("RGBA", (n * 4, n * 4), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            box = (14, 14, n * 4 - 15, n * 4 - 15)
            track = Image.new("RGBA", im.size, (0, 0, 0, 0))
            rgb = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
            ImageDraw.Draw(track).ellipse(box, outline=rgb + (70,), width=16)
            im.alpha_composite(track)
            d.arc(box, -70, 130, fill=rgb + (255,), width=16)       # the bright, turning part
            small = im.resize((n, n), Image.LANCZOS)
            # a classic bitmap cursor (works on every Windows): 32-bit pixels, bottom row first,
            # then an all-zero mask (the transparency comes from the alpha channel)
            px = bytearray()
            for y in range(n - 1, -1, -1):
                for x in range(n):
                    r_, g, b_, a_ = small.getpixel((x, y))
                    px += bytes((b_, g, r_, a_))
            data = struct.pack("<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0, 0, 0, 0, 0, 0)
            data += px + bytes(((n + 31) // 32 * 4) * n)
            head = struct.pack("<HHH", 0, 2, 1) + struct.pack(
                "<BBBBHHII", n, n, 0, 0, n // 2, n // 2, len(data), 22)
            with open(path, "wb") as f:
                f.write(head + data)
        except Exception:  # noqa: BLE001
            return None
    return "@" + path.replace("\\", "/")


class ThemeCover:
    """Covers a whole window (the app by default, or e.g. the Options window). Make it to show
    it; close() takes it away.
    """

    def __init__(self, app, theme_name, parent=None):
        pal = T.THEMES[theme_name]
        self.app, self.job, self.closed = app, None, False
        parent = parent or app
        self.font = (getattr(app, "base_font", None) or ("Helvetica",))[0]
        bg, text, muted = pal["BG"], pal["TEXT"], pal["MUTED"]
        accent = pal.get("TEAL", text)
        self.cv = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, cursor="watch")
        title = T.THEME_INFO.get(theme_name, (theme_name,))[0]
        self.message = random.choice(MESSAGES).format(theme=title)
        cur = _cursor(theme_name, accent)
        if cur:
            try:
                self.cv.configure(cursor=cur)
            except tk.TclError:
                pass                              # keep the ordinary busy pointer
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self.cv)
        self._logo = None
        self._big = parent is app
        try:
            self._logo = mascot.photo(mascot.current, 120 if parent is app else 84)
        except Exception:  # noqa: BLE001  (no picture: the text alone is fine)
            pass
        self.cv.bind("<Configure>", lambda e: self._frame())
        self._colours = (text, muted, accent)
        self.t0 = time.monotonic()
        self._frame()
        parent.update_idletasks()
        parent.update()                         # make sure it is really on screen before work starts

    def lift(self):
        """Keep it above anything built while it is showing."""
        if not self.closed:
            try:
                tk.Misc.lift(self.cv)
            except tk.TclError:
                self.closed = True

    def _frame(self):
        """Draw one frame: the mascot hopping, a label and three bouncing dots."""
        self.job = None
        if self.closed:
            return
        cv = self.cv
        text, muted, accent = self._colours
        try:
            w, h = max(cv.winfo_width(), 200), max(cv.winfo_height(), 200)
        except tk.TclError:                  # the window under it was closed
            self.closed = True
            return
        t = time.monotonic() - self.t0
        cx, cy = w / 2, h / 2
        cv.delete("all")
        hop = abs(math.sin(t * 5.5)) * 16
        if self._logo is not None:
            cv.create_image(cx, cy - 36 - hop, image=self._logo)
        cv.create_text(cx, cy + 56, text=self.message, fill=text, width=min(w - 40, 420),
                       justify="center", font=(self.font, 14, "bold"))
        # a ring of little dots turns round Ozzie; the head of the ring is brightest
        r = 74 if self._big else 56
        for i in range(8):
            a = t * 4.2 - i * (math.pi / 4)
            x, y = cx + math.cos(a) * r, cy - 36 + math.sin(a) * r
            size = 6.5 - i * 0.55
            cv.create_oval(x - size, y - size, x + size, y + size,
                           fill=accent if i < 3 else muted, outline="")
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
