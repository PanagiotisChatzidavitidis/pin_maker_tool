"""The guided tour: the mascot points at parts of the screen one by one and says what they do.

A tour is a list of steps. Each step has a title, a text and the part of the screen it is
about. While a tour runs, a soft glowing frame glides to that part and a card with the mascot
slides next to it. Everything else on screen is locked until the tour is skipped or finished,
so nothing gets clicked by accident. The two tours (the start screen and the editor) are
shown once, the first time. They can be switched off for good and played again from Options.
"""

import math
import time
import tkinter as tk
from tkinter import ttk

from . import mascot, theme as T
from .dnd import DND_FILES
from .icons import load_logo
from .widgets import Toggle
from ..constants import MOD_LABEL

# ---- the steps --------------------------------------------------------------------------
# (title, text, what to point at). The text may use {n} (the mascot's name), {mod} (Ctrl or
# Cmd) and {drop}. The target is a function that gets the app and returns a widget, a list of
# widgets (the frame goes around all of them) or None for a step with nothing to point at.
HOME_STEPS = [
    ("Hi, I'm {n}!",
     "Welcome to Ozzie's Pin Studio! I'm your guide, and I'll show you around in about a "
     "minute. Together we'll turn your favourite pictures into round pin-badge art, ready to "
     "print on one sheet.\n\nPress Next (or the right arrow key) to begin. You can skip "
     "whenever you like. I won't be offended. Much.",
     None),
    ("Start a new canvas",
     "A canvas is one printable sheet of pins. Click New canvas, give it a name, and we're "
     "off! I'll keep a safety copy of your work every few seconds, so nothing gets lost.",
     lambda a: a.home.btn_new),
    ("Open one you already have",
     "Got a canvas file from a friend, or saved somewhere else? Browse for a canvas opens "
     "it. Canvases are saved as .pinproj files.",
     lambda a: a.home.btn_browse),
    ("Your canvases live here",
     "Every canvas you make shows up as a card in this grid. Click a card to open it. The "
     "first tile starts a new canvas too. Delete removes one, but I always ask first, and "
     "your pictures are never touched.",
     lambda a: a.home.body),
    ("Find things fast",
     "Lots of canvases? Type in Search to narrow them down, or use Sort by to put them in "
     "the order you like, for example by when you edited or opened them.",
     lambda a: a.home.search_row),
    ("Make it yours",
     "Options is where you pick a theme (there are lots of cosy ones), switch between full "
     "screen and windowed, and choose which of us guides you: Ozzie, Mr Ozzie or Ms Ozzie. "
     "You can also bring this tour back any time. About shows the version and who drew me!",
     lambda a: a.home.more_row),
    ("Ready when you are!",
     "That's the start screen! Click New canvas and I'll show you the editor too.\n\nIf you'd "
     "rather not see tips, switch on \"Don't show tips again\" below, or turn them off in "
     "Options, under Tutorial.",
     None),
]

EDITOR_STEPS = [
    ("This is the editor!",
     "Here's where your sheet comes together. It only takes three steps: pick the paper, "
     "pick the pin size and add your pictures. Let me show you where everything is.",
     None),
    ("1 · Pick your paper",
     "Choose the sheet you'll print on. A4 is the usual one, and a custom size lets you "
     "type your own width and height in millimetres. The sheet on the right changes "
     "straight away.",
     lambda a: a.card_paper),
    ("2 · Pick your pin size",
     "Choose the size of your badge, like 32 mm or 44 mm. The circles are packed in a "
     "honeycomb pattern, so as many as possible fit and no paper is wasted. How many fit "
     "updates by itself.",
     lambda a: a.card_pin),
    ("3 · Add your pictures",
     "Click a circle on the sheet to add a picture. Pick several files at once to fill lots "
     "of circles in one go{drop}. Clear all empties the whole sheet, and Undo can bring it "
     "back.",
     lambda a: a.card_images),
    ("Your sheet",
     "This is your sheet, just as it will print. After you choose a picture, a little crop "
     "window opens: drag to position it, scroll to zoom and rotate it until it's perfect.\n\n"
     "Drag a finished pin onto an empty circle to move it, or onto another pin to swap them. "
     "Press Delete while pointing at a pin to clear it.",
     lambda a: a.cv),
    ("Keep an eye on progress",
     "These cards show your paper size, how many pins fit on one sheet and how many circles "
     "you've filled so far. The thin bar fills up as you go, and I'll warn you if a picture "
     "is too small and might print blurry.",
     lambda a: a.stat_row),
    ("Zoom in for a closer look",
     "Busy sheet? Hold {mod} and scroll to zoom in on the spot under your mouse, or use the "
     "slider and the + and − buttons. Zoomed in, scroll to slide around, or hold {mod} (or "
     "Space) and drag. Fit puts the whole sheet back in view.",
     lambda a: a.zoom_row),
    ("Oops? No problem!",
     "Undo and Redo ({mod}+Z and {mod}+Y) take back or bring back almost anything. I keep a "
     "safety copy while you work, but Save ({mod}+S) writes your canvas file for sure.",
     lambda a: [a.btn_undo, a.btn_redo, a.nav_row]),
    ("Ready to print?",
     "Export PDF makes a file you can print anywhere, and Print sends the sheet straight to "
     "your printer.\n\nTip: print at 100% (\"Actual size\"), never \"Fit to page\", so the "
     "pins come out exactly the size you chose.",
     lambda a: a.export_row),
    ("Back to the menu",
     "Back to menu takes you to all your canvases ({mod}+H). I'll ask first if there's "
     "something you haven't saved yet.",
     lambda a: a.btn_back),
    ("You did it!",
     "That's everything! You can watch this tutorial again any time from Options, under "
     "Tutorial.\n\nNow go make something adorable!",
     None),
]


def _union(widgets):
    """The box around some widgets, in the app window's own coordinates, or None."""
    boxes = []
    for w in widgets:
        try:
            if w.winfo_ismapped() and w.winfo_width() > 1:
                x, y = w.winfo_rootx(), w.winfo_rooty()
                boxes.append((x, y, x + w.winfo_width(), y + w.winfo_height()))
        except tk.TclError:
            pass
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


class Tour:
    """One running tour. Make it with the steps and it starts at once; close() ends it."""
    CARD_W = 450
    RING = 3                 # thickness of the frame around the target
    GAP = 18                 # space between the target and the card
    FRAMES = 11              # frames in a glide (about a sixth of a second)

    def __init__(self, app, name, steps):
        """Build the glowing frame and the card, lock the rest of the window and show step 1."""
        self.app, self.name, self.steps = app, name, steps
        self.i, self.closed = 0, False
        self._ring_box = None            # where the frame is now (x0, y0, x1, y1)
        self._card_xy = None             # where the card is now
        self._glide_job = self._pulse_job = self._hop_job = self._conf_job = None
        self._dy = 0
        fam = app.base_font[0]
        self.words = {"n": mascot.INFO[mascot.current][0], "mod": MOD_LABEL,
                      "drop": ", or drop image files straight onto the sheet" if DND_FILES
                              else ""}
        self.v_never = tk.BooleanVar(value=False)

        self._ring = [tk.Frame(app, bg=T.TEAL) for _ in range(4)]
        self.card = tk.Frame(app, bg=T.TEAL)                       # a 2px border around it
        body = tk.Frame(self.card, bg=T.CARD)
        body.pack(padx=2, pady=2)

        top = tk.Frame(body, bg=T.CARD)
        top.pack(fill="x", padx=18, pady=(16, 8))
        self._logo = load_logo(72)
        self._mascot = tk.Canvas(top, width=82, height=90, bg=T.CARD, highlightthickness=0)
        self._mimg = self._mascot.create_image(41, 52, image=self._logo)
        self._mascot.pack(side="left", anchor="n", padx=(0, 14))
        col = tk.Frame(top, bg=T.CARD)
        col.pack(side="left", fill="both", expand=True)
        self.title = tk.Label(col, bg=T.CARD, fg=T.PETROL, anchor="w", justify="left",
                              font=("Georgia", 14, "bold"))
        self.title.pack(fill="x")
        self.text = tk.Label(col, bg=T.CARD, fg=T.TEXT, anchor="nw", justify="left",
                             font=(fam, 10), wraplength=self.CARD_W - 150)
        self.text.pack(fill="x", pady=(6, 0))

        nav = tk.Frame(body, bg=T.CARD)
        nav.pack(fill="x", padx=18, pady=(4, 8))
        self.dots = tk.Canvas(nav, width=len(steps) * 14, height=12, bg=T.CARD,
                              highlightthickness=0)
        self.dots.pack(side="left")
        self.count = tk.Label(nav, bg=T.CARD, fg=T.MUTED, font=(fam, 9))
        self.count.pack(side="left", padx=(6, 0))
        self.btn_next = ttk.Button(nav, style="Accent.TButton", command=self.next)
        self.btn_next.pack(side="right")
        self.btn_back = ttk.Button(nav, text="Back", style="Soft.TButton", command=self.back)
        self.btn_back.pack(side="right", padx=(0, 8))

        tk.Frame(body, bg=T.BORDER, height=1).pack(fill="x")
        low = tk.Frame(body, bg=T.CARD)
        low.pack(fill="x", padx=18, pady=(8, 10))
        skip = tk.Label(low, text="Skip tour", bg=T.CARD, fg=T.MUTED, cursor="hand2",
                        font=(fam, 9, "underline"))
        skip.pack(side="left")
        skip.bind("<Button-1>", lambda e: self.close())
        skip.bind("<Enter>", lambda e: skip.config(fg=T.TEAL))
        skip.bind("<Leave>", lambda e: skip.config(fg=T.MUTED))
        Toggle(low, self.v_never, bg=T.CARD).pack(side="right")
        tk.Label(low, text="Don't show tips again", bg=T.CARD, fg=T.MUTED,
                 font=(fam, 9)).pack(side="right", padx=(0, 8))

        for key in ("<Return>", "<Right>", "<space>"):
            self.card.bind(key, lambda e: self.next())
        self.card.bind("<Left>", lambda e: self.back())
        self.card.bind("<Escape>", lambda e: self.close())
        app.bind("<Configure>", self._window_changed, add="+")    # (ignored once closed)
        try:
            self.card.grab_set()                  # the rest of the window can't be clicked
        except tk.TclError:
            pass
        self.card.focus_set()
        self._go(0)
        self._pulse()

    # ---- moving between steps ----------------------------------------------------------
    def next(self):
        """The next step, or finish after the last one."""
        if self.i >= len(self.steps) - 1:
            self.close()
        else:
            self._go(self.i + 1)

    def back(self):
        """The step before."""
        if self.i > 0:
            self._go(self.i - 1)

    def _go(self, i, instant=False):
        """Show step ``i``: new words, then the frame and the card glide to their new places."""
        if self.closed:
            return
        self.i = i
        title, text, target = self.steps[i]
        self.title.config(text=title.format(**self.words))
        self.text.config(text=text.format(**self.words))
        last, first = i == len(self.steps) - 1, i == 0
        self.btn_next.config(text="Done!" if last else ("Show me around" if first else "Next"))
        self.btn_back.pack_forget()                  # Back is hidden on the first step
        self.btn_next.pack_forget()
        self.btn_next.pack(side="right")
        if not first:
            self.btn_back.pack(side="right", padx=(0, 8))
        self.count.config(text=f"{i + 1} of {len(self.steps)}")
        self._draw_dots()

        widgets = target(self.app) if target else None
        if widgets is not None and not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        box = _union(widgets) if widgets else None
        if box:
            ox, oy = self.app.winfo_rootx(), self.app.winfo_rooty()
            box = (box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy)
        self.card.update_idletasks()
        xy = self._card_spot(box, self.card.winfo_reqwidth(), self.card.winfo_reqheight())
        self._move_to(box, xy, instant)
        if not instant:
            self._hop()

    def _draw_dots(self):
        """One dot per step; the current one is a longer, filled pill."""
        d = self.dots
        d.delete("all")
        x = 2
        for k in range(len(self.steps)):
            if k == self.i:
                d.create_oval(x, 2, x + 8, 10, fill=T.TEAL, outline=T.TEAL)
                d.create_oval(x + 6, 2, x + 14, 10, fill=T.TEAL, outline=T.TEAL)
                d.create_rectangle(x + 4, 2, x + 10, 10, fill=T.TEAL, outline=T.TEAL)
                x += 18
            else:
                done = k < self.i
                d.create_oval(x, 3, x + 6, 9, fill=T.TEAL if done else T.BORDER,
                              outline=T.TEAL if done else T.BORDER)
                x += 11
        d.config(width=x + 2)

    # ---- where things go ---------------------------------------------------------------
    def _card_spot(self, box, bw, bh):
        """Where the card goes: beside the target if there is room (right, left, below, then
        above), inside a big target, or in the middle of the window when there is no target.
        """
        W, H = self.app.winfo_width(), self.app.winfo_height()
        m = 12

        def clamp(v, lo, hi):
            return max(lo, min(v, hi))

        if box is None:
            return ((W - bw) // 2, (H - bh) // 2)
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        g = self.GAP
        if x1 + g + bw <= W - m:
            return (x1 + g, clamp(cy - bh // 2, m, H - bh - m))
        if x0 - g - bw >= m:
            return (x0 - g - bw, clamp(cy - bh // 2, m, H - bh - m))
        if y1 + g + bh <= H - m:
            return (clamp(cx - bw // 2, m, W - bw - m), y1 + g)
        if y0 - g - bh >= m:
            return (clamp(cx - bw // 2, m, W - bw - m), y0 - g - bh)
        # a big target (like the sheet): the card sits inside it, in its lower middle
        return (clamp(cx - bw // 2, m, W - bw - m), clamp(y1 - bh - 24, m, H - bh - m))

    def _place_ring(self, box):
        """Put the four bars of the frame around ``box`` (or hide them for no target)."""
        if box is None:
            for bar in self._ring:
                bar.place_forget()
            return
        x0, y0, x1, y1 = (int(v) for v in box)
        p, t = 4, self.RING
        x0, y0, x1, y1 = x0 - p, y0 - p, x1 + p, y1 + p
        w, h = x1 - x0, y1 - y0
        top, bottom, left, right = self._ring
        top.place(x=x0, y=y0, width=w, height=t)
        bottom.place(x=x0, y=y1 - t, width=w, height=t)
        left.place(x=x0, y=y0, width=t, height=h)
        right.place(x=x1 - t, y=y0, width=t, height=h)
        for bar in self._ring:
            bar.lift()
        self.card.lift()

    def _move_to(self, box, xy, instant=False):
        """Glide the frame and the card to their new places in a few eased frames."""
        if self._glide_job is not None:
            self.app.after_cancel(self._glide_job)
            self._glide_job = None
        start_box, start_xy = self._ring_box, self._card_xy
        if box is not None and start_box is None:             # the frame zooms in from outside
            x0, y0, x1, y1 = box
            start_box = (x0 - 40, y0 - 40, x1 + 40, y1 + 40)
        if start_xy is None:
            start_xy = (xy[0], xy[1] + 24)                    # the card floats up into place
        if instant:
            self._ring_box, self._card_xy = box, xy
            self._place_ring(box)
            self.card.place(x=xy[0], y=xy[1])
            self.card.lift()
            return

        def lerp(a, b, t):
            return a + (b - a) * t

        def frame(k):
            self._glide_job = None
            if self.closed:
                return
            t = k / self.FRAMES
            e = t * t * (3 - 2 * t)                            # smoothstep
            self._card_xy = (lerp(start_xy[0], xy[0], e), lerp(start_xy[1], xy[1], e))
            self.card.place(x=int(self._card_xy[0]), y=int(self._card_xy[1]))
            if box is not None and start_box is not None:
                self._ring_box = tuple(lerp(a, b, e) for a, b in zip(start_box, box))
            else:
                self._ring_box = box
            self._place_ring(self._ring_box)
            self.card.lift()
            if k < self.FRAMES:
                self._glide_job = self.app.after(16, frame, k + 1)
            else:
                self._ring_box, self._card_xy = box, xy

        frame(0)

    def _window_changed(self, event):
        """The window was resized: put the frame and the card back where they belong."""
        if event.widget is not self.app or self.closed:
            return
        if self._conf_job is not None:
            self.app.after_cancel(self._conf_job)
        self._conf_job = self.app.after(120, lambda: self._go(self.i, instant=True))

    # ---- small animations --------------------------------------------------------------
    def _hop(self, k=0):
        """The mascot's little hop at every new step."""
        hops = (0, -8, -12, -7, 0, -3, 0)
        if self._hop_job is not None:
            self.app.after_cancel(self._hop_job)
            self._hop_job = None
        if k >= len(hops) or self.closed:
            return
        try:
            self._mascot.move(self._mimg, 0, hops[k] - self._dy)
        except tk.TclError:
            return
        self._dy = hops[k]
        self._hop_job = self.app.after(60, self._hop, k + 1)

    def _pulse(self):
        """The frame breathes gently: its colour drifts a little towards the card colour."""
        if self.closed:
            return
        t = 0.5 - 0.5 * math.cos(time.monotonic() * 2 * math.pi / 1.8)
        col = T._mix(T.TEAL, T.CARD, 0.45 * t)
        for bar in self._ring:
            bar.config(bg=col)
        self._pulse_job = self.app.after(60, self._pulse)

    # ---- the end -----------------------------------------------------------------------
    def close(self, mark=True):
        """End the tour. With ``mark`` the app remembers this tour as seen (and, if the person
        asked for it, switches tips off for good).
        """
        if self.closed:
            return
        self.closed = True
        for job in (self._glide_job, self._pulse_job, self._hop_job, self._conf_job):
            if job is not None:
                try:
                    self.app.after_cancel(job)
                except tk.TclError:
                    pass
        try:
            self.card.grab_release()
        except tk.TclError:
            pass
        for w in (*self._ring, self.card):
            try:
                w.destroy()
            except tk.TclError:
                pass
        app = self.app
        if app.tour is self:
            app.tour = None
        if mark:
            app.tour_finished(self.name, never=self.v_never.get())
        try:
            app.focus_set()
        except tk.TclError:
            pass
