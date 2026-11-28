"""Pick the pins for a bundle picture: tick at least one (up to ten), then Proceed.

Nothing is ticked to begin with. Proceed opens the results window, which shows a loading
screen while the bundle and a close-up of each pin are prepared.
"""

import tkinter as tk

from PIL import Image, ImageTk

from .. import envs, ring as ring_mod
from ..imaging import render_art
from . import theme as T
from .buttons import Btn
from .screens import Screen

CHIP = 72


class PreviewSetup(Screen):
    """The "Preview pins" page where the bundle's pins are picked."""

    def __init__(self, host, pool, pin):
        super().__init__(host)
        self.parent, self.pool, self.pin = host, list(pool), pin
        self.sel, self._imgs, self._rows = [], [], []

        self.return_bar("Preview pins", f"Pick the pins for the bundle: at least one, up to {envs.MAX_PINS}.")

        foot = tk.Frame(self, bg=T.BG)
        foot.pack(side="bottom", fill="x", padx=28, pady=(8, 20))
        self.go = Btn(foot, "Proceed", self._proceed, kind="soft", bg=T.BG, icon="eye")
        self.go.pack(side="right")
        self.note = tk.Label(foot, bg=T.BG, fg=T.MUTED, anchor="w")
        self.note.pack(side="left")

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(side="top", fill="x", padx=28, pady=(12, 8))
        Btn(bar, "Select all", self._all, kind="ghost", bg=T.BG, height=30).pack(side="left")
        Btn(bar, "Clear", self._none, kind="ghost", bg=T.BG, height=30).pack(side="left", padx=6)
        self.count = tk.Label(bar, bg=T.BG, fg=T.MUTED)
        self.count.pack(side="right")

        box = tk.Frame(self, bg=T.BORDER)
        box.pack(fill="both", expand=True, padx=28)
        self.cv = tk.Canvas(box, bg=T.CARD, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True, padx=1, pady=1)
        self.inner = tk.Frame(self.cv, bg=T.CARD)
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self._wheel(self.cv)
        self._build()
        self._refresh()
        self.focus_set()

    def _wheel(self, w):
        w.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        w.bind("<Button-4>", lambda e: self.cv.yview_scroll(-1, "units"))
        w.bind("<Button-5>", lambda e: self.cv.yview_scroll(1, "units"))

    def _bind_all(self, widget, fn):
        widget.bind("<Button-1>", lambda e: fn())
        self._wheel(widget)
        for c in widget.winfo_children():
            self._bind_all(c, fn)

    def _chip(self, art, size=CHIP):
        p = self.pin
        k = size / max(p["fw"], p["fh"])
        try:
            face = render_art(art, p["w"], k, h_mm=p["h"], face=(p["shape"], p["fw"], p["fh"]))
            W, H = max(8, int(p["fw"] * k)), max(8, int(p["fh"] * k))
            base = Image.new("RGB", (W, H), (255, 255, 255))
            base.paste(face.convert("RGB"), (W // 2 - face.width // 2, H // 2 - face.height // 2))
            m = ring_mod.mask(p["shape"], p["fw"], p["fh"], 0, (W, H), k, k, W / 2, H / 2, 3)
            out = Image.new("RGB", (size, size), T.CARD)
            out.paste(base, ((size - W) // 2, (size - H) // 2), m)
            return ImageTk.PhotoImage(out)
        except Exception:
            return ImageTk.PhotoImage(Image.new("RGB", (size, size), T.CARD))

    def _build(self):
        cols = 5
        for i, (label, art) in enumerate(self.pool):
            img = self._chip(art)
            self._imgs.append(img)
            f = tk.Frame(self.inner, bg=T.CARD, highlightthickness=3, highlightbackground=T.CARD, cursor="hand2")
            f.grid(row=i // cols, column=i % cols, padx=8, pady=8)
            tk.Label(f, image=img, bg=T.CARD, bd=0).pack(padx=8, pady=(8, 2))
            tk.Label(f, text=label, bg=T.CARD, fg=T.TEXT).pack(pady=(0, 8))
            self._bind_all(f, lambda i=i: self._toggle(i))
            self._rows.append(f)

    def _flash(self, text):
        self.note.configure(text=text)
        self.after(3500, lambda: self.note.winfo_exists() and self.note.configure(text=""))

    def _toggle(self, i):
        if i in self.sel:
            self.sel.remove(i)
        elif len(self.sel) >= envs.MAX_PINS:
            return self._flash(f"A picture holds up to {envs.MAX_PINS} pins.")
        else:
            self.sel = sorted(self.sel + [i])
        self._refresh()

    def _all(self):
        self.sel = list(range(min(len(self.pool), envs.MAX_PINS)))
        if len(self.pool) > envs.MAX_PINS:
            self._flash(f"The first {envs.MAX_PINS} are ticked: the most one picture holds.")
        self._refresh()

    def _none(self):
        self.sel = []
        self._refresh()

    def _refresh(self):
        for i, f in enumerate(self._rows):
            f.configure(highlightbackground=T.TEAL if i in self.sel else T.CARD)
        self.count.configure(text=f"{len(self.sel)} of {envs.MAX_PINS}")
        self.go.configure(kind="accent" if self.sel else "soft")

    def _proceed(self):
        if not self.sel:
            return self._flash("Pick at least one pin to continue.")
        from .preview_dialog import PreviewDialog
        host, pool, sel, pin = self.host, self.pool, list(self.sel), self.pin
        self.destroy()
        host._screen = None
        Screen.open(host, PreviewDialog, pool, sel, pin)
