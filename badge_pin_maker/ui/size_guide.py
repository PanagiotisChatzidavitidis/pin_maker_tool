"""Ozzie's little pin size guide: a pop-up sheet that explains finished pin size versus the
paper circle you print and cut, with every size listed.
"""

import math
import tkinter as tk
from tkinter import ttk

from .. import shapes
from ..constants import cut_dims, sizes_for
from . import smooth, theme as T
from .dialogs import set_titlebar, set_window_icon
from .icons import load_logo
from .widgets import round_rect


def _picture(size, shape, cut, face, ref, bg, dotted=False):
    """A round-cornered tile showing a pin: the paper shape ``cut`` (w, h in mm) with the
    finished face ``face`` inside it, drawn to scale against ``ref`` (the biggest paper shape
    that tile set must hold, so a row of them shows the real size differences).
    """
    key = ("guide-pic", size, shape, cut, face, ref, bg, dotted, T.TEAL, T.CARD)
    scale = (size - 3) / max(ref)
    cut_c = T._mix(T.CARD, T.TEAL, 0.38)

    def paint(d, k):
        m = size / 2
        for pts, fill, outline in ((shapes.outline(shape, *cut), cut_c, T.TEAL),
                                   (shapes.outline(shape, *face), T.CARD, None)):
            xy = [((m + x * scale) * k, (m + y * scale) * k) for x, y in pts]
            if fill is not None:
                d.polygon(xy, fill=fill)
            if outline:
                d.line(xy + [xy[0]], fill=outline, width=max(1, round(1.4 * k)))
        if dotted:                                   # the front face, as a dotted ring
            pts = shapes.outline(shape, *face)
            xy = [((m + x * scale) * k, (m + y * scale) * k) for x, y in pts]
            xy.append(xy[0])
            dash, on = 0.0, True
            for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
                seg = math.hypot(x2 - x1, y2 - y1)
                if on:
                    d.line([(x1, y1), (x2, y2)], fill=T.TEAL, width=max(1, round(1.2 * k)))
                dash += seg
                if dash > 3.2 * k:
                    dash, on = 0.0, not on
        else:
            xy = [((m + x * scale) * k, (m + y * scale) * k)
                  for x, y in shapes.outline(shape, *face)]
            d.line(xy + [xy[0]], fill=T.TEAL, width=max(1, round(1.2 * k)))
    return smooth._make(key, size, size, bg, paint)


class SizeGuide(tk.Toplevel):
    """The guide window for one pin ``shape``. ``current`` is the size picked now (it is
    highlighted in the table).
    """

    def __init__(self, parent, shape="Round", current=None):
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
        table = {k: v for k, v in sizes_for(shape).items() if v is not None}
        rows = []                       # (key, name, finished text, cut text, face, cut dims)
        for key, v in table.items():
            name = key.split(" – ", 1)[-1]
            if shape == "Round":
                fw, fh, published = v[0], v[0], True
            else:
                fw, fh, published = v[0], v[1], bool(v[3])
            cw, ch = cut_dims(shape, fw, fh)
            if shape == "Round":
                fin, cut = f"{fw:g} mm", f"{cw:g} mm"
            else:
                fin = f"{fw:g} × {fh:g} mm"
                cut = f"{'' if published else '~ '}{cw:.1f} × {ch:.1f} mm".replace(".0 ", " ")
            rows.append((key, name, fin, cut, (fw, fh), (cw, ch), published))
        ref = (max(r[5][0] for r in rows), max(r[5][1] for r in rows))
        noun = "circle" if shape == "Round" else f"{shape.lower()}"

        body = ttk.Frame(self, style="Card.TFrame", padding=(24, 16, 24, 12))
        body.pack(fill="both", expand=True)

        # ---- Ozzie and what he says
        top = tk.Frame(body, bg=T.CARD)
        top.pack(fill="x")
        self._logo = load_logo(76)
        tk.Label(top, image=self._logo, bg=T.CARD).pack(side="left", anchor="s")
        self._bubble(top, "Squeak! Welcome to my size guide! Pick the shape and how big you "
                          f"want your finished pin, and I'll print the right paper {noun} "
                          "for you.")

        # ---- picture + the three ideas
        mid = tk.Frame(body, bg=T.CARD)
        mid.pack(fill="x", pady=(12, 2))
        sample = rows[min(1, len(rows) - 1)]
        pic = _picture(132, shape, sample[5], sample[4], sample[5], T.CARD, dotted=True)
        self._keep.append(pic)
        tk.Label(mid, image=pic, bg=T.CARD).pack(side="left", anchor="n", padx=(0, 18))
        steps = tk.Frame(mid, bg=T.CARD)
        steps.pack(side="left", fill="x", expand=True)
        for n, head, text in (
                ("1", "Finished pin", "The shiny front that everyone sees. This is the size "
                                      "you pick."),
                ("2", "Paper shape", f"A bit bigger! The extra edge of the {noun} wraps round "
                                     "the side and tucks in behind."),
                ("3", "Print and cut", "Cut along the solid line. Keep the important bits of "
                                       "your picture inside the dotted line.")):
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
        table_f = tk.Frame(body, bg=T.CARD)
        table_f.pack(fill="x")
        table_f.columnconfigure(1, weight=1)
        for c, (txt, anchor) in enumerate((("", "w"), (shape, "w"), ("Finished pin", "e"),
                                           ("Print and cut", "e"))):
            tk.Label(table_f, text=txt, bg=T.CARD, fg=T.MUTED, anchor=anchor,
                     font=(fam, 9)).grid(row=0, column=c, sticky="ew", padx=6)
        approx = False
        for r, (key, name, fin, cut, face, cutd, published) in enumerate(rows, start=1):
            approx = approx or not published
            on = key == current
            bg = T.HOVER if on else T.CARD
            fg = T.TEAL if on else T.TEXT
            weight = "bold" if on else "normal"
            icon = _picture(32, shape, cutd, face, ref, bg)
            self._keep.append(icon)
            cells = [tk.Label(table_f, image=icon, bg=bg)]
            cells[0].grid(row=r, column=0, sticky="nsew")
            for c, (txt, anchor) in enumerate(((name, "w"), (fin, "e"), (cut, "e")), start=1):
                cells.append(tk.Label(table_f, text=txt, bg=bg, fg=fg, anchor=anchor,
                                      font=(fam, 10, weight)))
                cells[-1].grid(row=r, column=c, sticky="nsew", ipadx=6, ipady=5)
        r = len(rows) + 1
        tk.Label(table_f, text="✦", bg=T.CARD, fg=T.TEAL).grid(row=r, column=0)
        for c, (txt, anchor) in enumerate((("Chef's Special", "w"), ("your size", "e"),
                                           ("+ a wrap-around edge", "e")), start=1):
            tk.Label(table_f, text=txt, bg=T.CARD, fg=T.TEXT, anchor=anchor,
                     font=(fam, 10)).grid(row=r, column=c, sticky="nsew", ipadx=6, ipady=5)

        note = ("Tip: these sizes follow what pin-machine makers publish. Machines differ by "
                "a millimetre or two, so print one pin first!")
        if approx:
            note = ("~ means the maker doesn't publish the paper size, so I added the usual "
                    "wrap-around edge. " + note)
        tk.Label(body, bg=T.CARD, fg=T.MUTED, anchor="w", justify="left", wraplength=560,
                 font=(fam, 9), text=note).pack(fill="x", pady=(12, 0))

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
