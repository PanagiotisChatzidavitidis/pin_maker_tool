"""Small reusable pieces of the crop window's side pages: a grid of captioned previews
(``Tiles``) and rows of round colour swatches (``Swatches``).
"""

import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from .. import ring as ring_mod
from . import theme as T
from .ring_picker import _disc


class Tiles(tk.Frame):
    """A grid of previews with a caption each; one can be marked as the current one."""

    def __init__(self, parent, items, cols, thumb, on_pick, bold_first=False):
        super().__init__(parent, bg=T.CARD)
        self.on_pick, self.thumb = on_pick, thumb
        self._cells, self._imgs, self._current = {}, {}, None
        for n, (ident, label) in enumerate(items):
            cell = tk.Frame(self, bg=T.CARD, highlightthickness=2, highlightbackground=T.CARD,
                            width=thumb + 16, height=thumb + 32, cursor="hand2")
            cell.grid(row=n // cols, column=n % cols, padx=3, pady=3)
            cell.pack_propagate(False)
            pic = tk.Label(cell, bg=T.CARD, bd=0, width=thumb, height=thumb)
            pic.pack(pady=(4, 0))
            first = bold_first and n == 0
            cap = tk.Label(cell, text=label, bg=T.CARD, cursor="hand2",
                           fg=T.TEAL if first else T.TEXT,
                           font=("TkDefaultFont", 8, "bold" if first else "normal"))
            cap.pack(pady=(1, 2))
            for w in (cell, pic, cap):
                w.bind("<Button-1>", lambda e, i=ident: self.on_pick(i))
                w.bind("<Enter>", lambda e, i=ident: self._hover(i, True))
                w.bind("<Leave>", lambda e, i=ident: self._hover(i, False))
            self._cells[ident] = (cell, pic)

    def set_image(self, ident, img):
        ph = ImageTk.PhotoImage(img)
        self._imgs[ident] = ph
        self._cells[ident][1].config(image=ph, width=self.thumb, height=self.thumb)

    def select(self, ident):
        self._current = ident
        for i, (cell, _p) in self._cells.items():
            cell.config(highlightbackground=T.TEAL if i == ident else T.CARD)

    def _hover(self, ident, inside):
        if ident != self._current:
            self._cells[ident][0].config(highlightbackground=T.BORDER if inside else T.CARD)


class Swatches(tk.Frame):
    """Rows of round colours with a small name under each. The chosen one gets a teal rim."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.CARD)
        self._key = None

    def show(self, rows, current, on_pick):
        key = (tuple((t, tuple(s)) for t, s in rows), tuple(current))
        if key == self._key:
            return
        self._key = key
        for c in self.winfo_children():
            c.destroy()
        for title, swatches in rows:
            if title:
                tk.Label(self, text=title, bg=T.CARD, fg=T.MUTED, anchor="w",
                         font=("TkDefaultFont", 8)).pack(fill="x", pady=(6, 2))
            row = tk.Frame(self, bg=T.CARD)
            row.pack(fill="x")
            for name, col in swatches:
                on = tuple(col) == tuple(current)
                img = _disc(30, ring_mod.to_hex(col), T.TEAL if on else T.BORDER, 3 if on else 1)
                cell = tk.Frame(row, bg=T.CARD, cursor="hand2")
                cell.pack(side="left", padx=(0, 6))
                lab = tk.Label(cell, image=img, bg=T.CARD, bd=0)
                lab.image = img
                lab.pack()
                cap = tk.Label(cell, text=name, bg=T.CARD, fg=T.TEXT if on else T.MUTED,
                               font=("TkDefaultFont", 7), width=7)
                cap.pack()
                for w in (cell, lab, cap):
                    w.bind("<Button-1>", lambda e, c=col: on_pick(c))


class ScrollPage(tk.Frame):
    """A page that scrolls when its content is taller than the space (mouse wheel or bar).
    Put the content in ``.inner``; call ``bind_wheel()`` once it is built."""

    def __init__(self, parent, bg=None):
        super().__init__(parent, bg=bg or T.CARD)
        self.cv = tk.Canvas(self, bg=bg or T.CARD, highlightthickness=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=bg or T.CARD)
        self._win = self.cv.create_window(0, 0, anchor="nw", window=self.inner)
        self.inner.bind("<Configure>", lambda e: self._fit())
        self.cv.bind("<Configure>", self._resized)
        self._bar = False

    def _resized(self, e):
        self.cv.itemconfigure(self._win, width=e.width)
        self._fit()

    def _fit(self):
        self.cv.configure(scrollregion=self.cv.bbox("all"))
        need = self.inner.winfo_reqheight() > self.cv.winfo_height() > 1
        if need and not self._bar:
            self.sb.pack(side="right", fill="y")
            self._bar = True
        elif not need and self._bar:
            self.sb.pack_forget()
            self._bar = False
            self.cv.yview_moveto(0)

    def bind_wheel(self, widget=None):
        widget = widget or self.inner
        widget.bind("<MouseWheel>", self._wheel, add="+")
        widget.bind("<Button-4>", lambda e: self._scroll(-2), add="+")
        widget.bind("<Button-5>", lambda e: self._scroll(2), add="+")
        for child in widget.winfo_children():
            self.bind_wheel(child)

    def _scroll(self, n):
        if self._bar:
            self.cv.yview_scroll(n, "units")

    def _wheel(self, e):
        self._scroll(-2 if e.delta > 0 else 2)
        return "break" if self._bar else None
