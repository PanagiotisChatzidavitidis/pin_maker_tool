"""Ozzie's little pin size guide: a pop-up sheet that explains finished pin size versus the
paper circle you print and cut, with every size listed.
"""

import tkinter as tk
from tkinter import ttk

from ..constants import EXTRA_EDGE, PIN_SIZES
from . import smooth, theme as T
from .dialogs import set_titlebar, set_window_icon
from .icons import load_logo
from .widgets import round_rect

BIGGEST = max(v[2] for v in PIN_SIZES.values() if v)      # the largest paper circle (mm)


def _rings(size, outer_mm, inner_mm, bg, dotted=False, ref=None):
    """A round picture of a pin: the paper circle with the finished pin's face inside it. The
    two circles are drawn to scale against each other, and (with ``ref``) the paper circle is
    drawn to scale against a ``ref`` mm one that would fill the whole picture.
    """
    ref = ref or outer_mm
    key = ("guide-rings", size, outer_mm, inner_mm, bg, dotted, ref, T.TEAL, T.CARD)
    cut_c = T._mix(T.CARD, T.TEAL, 0.38)

    def paint(d, k):
        m = size / 2
        big = (m - 1) * outer_mm / ref
        smooth._oval(d, k, m, m, big, cut_c, outline=T.TEAL, width=1.4)
        r = big * inner_mm / outer_mm
        smooth._oval(d, k, m, m, r, T.CARD)
        if dotted:                                   # the front face, as a dotted ring
            import math
            n = 28
            for i in range(n):
                a = 2 * math.pi * i / n
                smooth._oval(d, k, m + r * math.cos(a), m + r * math.sin(a), 0.9, T.TEAL)
        else:
            smooth._oval(d, k, m, m, r, T.CARD, outline=T.TEAL, width=1.2)
    return smooth._make(key, size, size, bg, paint)


class SizeGuide(tk.Toplevel):
    """The guide window. ``current`` is the pin size picked now (it is highlighted)."""

    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.withdraw()
        self.title("Ozzie's size guide")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        set_window_icon(self)
        try:
            if parent is not None and parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass
        fam = "TkDefaultFont"
        self._keep = []
        body = ttk.Frame(self, style="Card.TFrame", padding=(24, 16, 24, 12))
        body.pack(fill="both", expand=True)

        # ---- Ozzie and what he says
        top = tk.Frame(body, bg=T.CARD)
        top.pack(fill="x")
        self._logo = load_logo(76)
        tk.Label(top, image=self._logo, bg=T.CARD).pack(side="left", anchor="s")
        self._bubble(top, "Squeak! Welcome to my size guide! Pick how big you want your "
                          "finished pin, and I'll print the right paper circle for you.")

        # ---- picture + the three ideas
        mid = tk.Frame(body, bg=T.CARD)
        mid.pack(fill="x", pady=(12, 2))
        pic = _rings(132, 100, 72, T.CARD, dotted=True)
        self._keep.append(pic)
        tk.Label(mid, image=pic, bg=T.CARD).pack(side="left", anchor="n", padx=(0, 18))
        steps = tk.Frame(mid, bg=T.CARD)
        steps.pack(side="left", fill="x", expand=True)
        for n, head, text in (
                ("1", "Finished pin", "The shiny front that everyone sees. This is the size "
                                      "you pick."),
                ("2", "Paper circle", "A bit bigger! The extra edge wraps round the side and "
                                      "tucks in behind."),
                ("3", "Print and cut", "Cut along the solid line. Keep the important bits of "
                                       "your picture inside the dotted ring.")):
            row = tk.Frame(steps, bg=T.CARD)
            row.pack(fill="x", pady=(0, 7))
            dot = tk.Canvas(row, width=24, height=24, bg=T.CARD, highlightthickness=0)
            dot.create_oval(1, 1, 23, 23, fill=T.TEAL, outline="")
            dot.create_text(12, 12, text=n, fill=T.ON_PRIMARY, font=(fam, 9, "bold"))
            dot.pack(side="left", anchor="n", padx=(0, 10))
            col = tk.Frame(row, bg=T.CARD)
            col.pack(side="left", fill="x", expand=True)
            tk.Label(col, text=head, bg=T.CARD, fg=T.PETROL, anchor="w",
                     font=(fam, 10, "bold")).pack(fill="x")
            tk.Label(col, text=text, bg=T.CARD, fg=T.TEXT, anchor="w", justify="left",
                     wraplength=330, font=(fam, 9)).pack(fill="x")

        # ---- the table of sizes
        tk.Frame(body, bg=T.BORDER, height=1).pack(fill="x", pady=(8, 8))
        table = tk.Frame(body, bg=T.CARD)
        table.pack(fill="x")
        table.columnconfigure(1, weight=1)
        for c, (txt, anchor) in enumerate((("", "w"), ("Pin", "w"), ("Finished pin", "e"),
                                           ("Print and cut", "e"))):
            tk.Label(table, text=txt, bg=T.CARD, fg=T.MUTED, anchor=anchor,
                     font=(fam, 9)).grid(row=0, column=c, sticky="ew", padx=6)
        for r, (key, data) in enumerate(PIN_SIZES.items(), start=1):
            on = key == current
            bg = T.HOVER if on else T.CARD
            fg = T.TEAL if on else T.TEXT
            weight = "bold" if on else "normal"
            if data is None:
                icon = None
                name, fin, cut = "Chef's Special", "your size", f"+ {EXTRA_EDGE:g} mm"
            else:
                icon = _rings(32, data[2], data[0], bg, ref=BIGGEST)
                name = key.split(" – ", 1)[-1]
                fin, cut = f"{data[0]} mm", f"{data[2]} mm"
            cells = []
            lab = tk.Label(table, image=icon, bg=bg) if icon else tk.Label(table, text="✦",
                                                                          bg=bg, fg=T.TEAL)
            lab.grid(row=r, column=0, sticky="nsew")
            if icon:
                self._keep.append(icon)
            cells.append(lab)
            for c, (txt, anchor) in enumerate(((name, "w"), (fin, "e"), (cut, "e")), start=1):
                cells.append(tk.Label(table, text=txt, bg=bg, fg=fg, anchor=anchor,
                                      font=(fam, 10, weight)))
                cells[-1].grid(row=r, column=c, sticky="nsew", ipadx=6, ipady=5)

        tk.Label(body, bg=T.CARD, fg=T.MUTED, anchor="w", justify="left", wraplength=560,
                 font=(fam, 9),
                 text="Tip: these paper sizes follow what pin-machine makers publish. "
                      "Machines differ by a millimetre or two, so print one pin first!"
                 ).pack(fill="x", pady=(12, 0))

        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")
        foot = ttk.Frame(self, padding=(16, 12))
        foot.pack(fill="x")
        ttk.Button(foot, text="Got it!", style="Accent.TButton",
                   command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        if parent is not None:
            x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        else:
            x, y = (self.winfo_screenwidth() - w) // 2, (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        set_titlebar(self)
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()

    def _bubble(self, parent, message):
        """Ozzie's speech bubble: a rounded box with a small tail pointing at him."""
        TAIL, TEXT_W, PX, PY = 12, 400, 16, 12
        bub = tk.Canvas(parent, bg=T.CARD, highlightthickness=0)
        txt = bub.create_text(0, 0, text=message, anchor="nw", width=TEXT_W, fill=T.TEXT,
                              font="TkDefaultFont", justify="left")
        bx0, by0, bx1, by1 = bub.bbox(txt)
        bub.move(txt, TAIL + 2 + PX - bx0, PY + 1 - by0)
        W, H = TAIL + (bx1 - bx0) + 2 * PX + 3, (by1 - by0) + 2 * PY + 2
        bub.config(width=W, height=H)
        round_rect(bub, TAIL + 1, 1, W - 2, H - 2, 14, fill=T.HOVER, outline=T.TEAL, width=2,
                   tags="bubble")
        cy = min(max(20, H - 30), H - 16)
        bub.create_polygon(TAIL + 1, cy - 9, 1, cy, TAIL + 1, cy + 9, fill=T.HOVER,
                           outline=T.TEAL, width=2, tags="bubble")
        bub.create_line(TAIL + 1, cy - 7, TAIL + 1, cy + 7, fill=T.HOVER, width=4, tags="bubble")
        bub.tag_lower("bubble")
        bub.pack(side="left", anchor="s", padx=(2, 0))
