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
# What Ozzie says while the window changes size.
FULLSCREEN_MESSAGES = (
    "Stretching out to fill your whole screen!",
    "Making everything big and roomy...",
    "Full screen, coming right up!",
)
WINDOWED_MESSAGES = (
    "Tucking everything into a cosy little window!",
    "Shrinking down nice and snug...",
    "Back to a window, one moment!",
)
MIN_SHOW_MS = int(os.environ.get("OZZIE_COVER_MS", 900))   # long enough to read the message
FRAME_MS = 33


_TURN_STEPS = 12                      # pictures in one full turn of the pointer
_TURN_JIFFIES = 4                     # how long each lasts, in 1/60 s (so a turn is 0.8 s)


def _cur_bytes(frame, n):
    """One pointer picture as the bytes of a .cur file: 32-bit pixels, bottom row first, then an
    all-zero mask (the see-through parts come from the alpha channel). Hot spot: the middle.
    """
    px = bytearray()
    for y in range(n - 1, -1, -1):
        for x in range(n):
            r_, g, b_, a_ = frame.getpixel((x, y))
            px += bytes((b_, g, r_, a_))
    data = struct.pack("<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    data += px + bytes(((n + 31) // 32 * 4) * n)
    head = struct.pack("<HHH", 0, 2, 1) + struct.pack(
        "<BBBBHHII", n, n, 0, 0, n // 2, n // 2, len(data), 22)
    return head + data


def _ani_bytes(frames, n):
    """The bytes of an animated pointer (.ani): a RIFF file with a header, then every picture."""
    def chunk(tag, body):
        return tag + struct.pack("<I", len(body)) + body + (b"\0" if len(body) % 2 else b"")
    anih = struct.pack("<IIIIIIIII", 36, len(frames), len(frames), n, n, 32, 1,
                       _TURN_JIFFIES, 1)                  # flag 1: the pictures are .cur data
    fram = b"fram" + b"".join(chunk(b"icon", _cur_bytes(f, n)) for f in frames)
    body = b"ACON" + chunk(b"anih", anih) + chunk(b"LIST", fram)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _cursor(theme_name, accent):
    """A mouse pointer for the loading screen (Windows only, else None): a loading circle in
    the theme's colour that turns round. Written once per theme as an animated .ani file.
    """
    if platform.system() != "Windows":
        return None
    path = os.path.join(tempfile.gettempdir(), f"ozzie_spin_{theme_name}.ani")
    if not os.path.exists(path):
        try:
            n, k = 32, 4
            box = (14, 14, n * k - 15, n * k - 15)
            rgb = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
            frames = []
            for i in range(_TURN_STEPS):
                im = Image.new("RGBA", (n * k, n * k), (0, 0, 0, 0))
                track = Image.new("RGBA", im.size, (0, 0, 0, 0))
                ImageDraw.Draw(track).ellipse(box, outline=rgb + (70,), width=16)
                im.alpha_composite(track)
                start = -70 + i * (360 // _TURN_STEPS)       # the bright arc moves round the ring
                ImageDraw.Draw(im).arc(box, start, start + 200, fill=rgb + (255,), width=16)
                frames.append(im.resize((n, n), Image.LANCZOS))
            with open(path, "wb") as f:
                f.write(_ani_bytes(frames, n))
        except Exception:  # noqa: BLE001
            return None
    return "@" + path.replace("\\", "/")


class ThemeCover:
    """Covers a whole window (the app by default, or e.g. the Options window). Make it to show
    it; close() takes it away.
    """

    def __init__(self, app, theme_name, parent=None, messages=None):
        pal = T.THEMES[theme_name]
        self.app, self.job, self.closed = app, None, False
        parent = parent or app
        self.font = (getattr(app, "base_font", None) or ("Helvetica",))[0]
        bg, text, muted = pal["BG"], pal["TEXT"], pal["MUTED"]
        accent = pal.get("TEAL", text)
        self.cv = self._canvas(parent, bg)
        title = T.THEME_INFO.get(theme_name, (theme_name,))[0]
        self.message = random.choice(messages or MESSAGES).format(theme=title)
        cur = _cursor(theme_name, accent)
        if cur:
            try:
                self.cv.configure(cursor=cur)
            except tk.TclError:
                pass                              # keep the ordinary busy pointer
        self.cv.delete("all")
        self._logo = None
        self._big = parent is app
        try:
            self._logo = mascot.photo(mascot.current, 120 if parent is app else 84)
        except Exception:  # noqa: BLE001  (no picture: the text alone is fine)
            pass
        self.cv._owner = self
        self._colours = (text, muted, accent)
        self.t0 = time.monotonic()
        self._frame()                           # the first picture is drawn before it is shown
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self.cv)
        parent.update_idletasks()
        parent.update()                         # make sure it is really on screen before work starts

    @staticmethod
    def _canvas(parent, bg):
        """The window's cover canvas. It is made once and parked (1 pixel, behind everything)
        between uses, so showing it never creates a new native window, which is what flashed
        white for a moment on Windows.
        """
        cv = getattr(parent, "_cover_cv", None)
        try:
            alive = cv is not None and cv.winfo_exists()
        except tk.TclError:
            alive = False
        if not alive:
            cv = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0, cursor="watch")
            cv._owner = None
            cv.bind("<Configure>", lambda e: cv._owner and cv._owner._frame())
            parent._cover_cv = cv
        cv.configure(bg=bg)
        return cv

    @staticmethod
    def warm(parent):
        """Make the parked canvas ahead of time (call once the window is on screen)."""
        try:
            cv = ThemeCover._canvas(parent, T.BG)
            cv.place(x=0, y=0, width=1, height=1, relwidth=0, relheight=0)
            tk.Misc.lower(cv)
        except tk.TclError:
            pass

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
            self.cv.delete("all")
            self.cv._owner = None
            self.cv.place(x=0, y=0, width=1, height=1, relwidth=0, relheight=0)       # park it, ready for next time
            tk.Misc.lower(self.cv)
        except tk.TclError:
            pass
        if then:
            then()
