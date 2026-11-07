"""The start screen: a sidebar with the main actions and a grid of saved canvases."""

import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from ..settings import save_settings
from ..system_actions import reveal_folder
from . import theme as T
from .dialogs import messagebox
from .icons import load_logo, make_icon, render_icon_image

# the choices of the "Sort by" box; the first one is the default
SORTS = ("Recently edited", "Recently opened", "Name A–Z", "Name Z–A", "Oldest first",
         "Most pins")


class HomeScreen(tk.Frame):
    """Start screen: sidebar (brand, actions, options, exit) + canvases list."""
    ICON = 84                   # round thumbnail on each card
    SIDE_W = 320
    CARD_MIN_W = 250            # cards are at least this wide; the grid fits as many as it can
    CARD_H = 218
    GAP = 18

    def __init__(self, app):
        """Build the sidebar (brand, actions, options) and the empty, scrollable canvas list.
        """
        super().__init__(app, bg=T.BG)
        self.app = app
        self._icons = {}                # (path, mtime, size) -> finished thumbnail
        self._pending = {}              # thumbnail key -> [(label, art)] still being made
        self.shown = []                 # names of the canvases listed, in order
        self._cards = []                # the card frames in the grid (the "New canvas" tile first)
        self._cols = 0                  # columns the grid currently has
        self._items = []                # every canvas found in the folder
        self._gen = 0                   # bumped on every redraw, so old thumbnail jobs stop
        self._search_job = None
        self._sb_on = False
        fam = app.base_font[0]
        self._placeholder = make_icon(None, self.ICON)       # shown until a thumbnail is ready
        sort = app.settings.get("sort")
        self.v_sort = tk.StringVar(value=sort if sort in SORTS else SORTS[0])
        self.v_search = tk.StringVar()

        # ---- sidebar -------------------------------------------------------
        side = tk.Frame(self, bg=T.CARD, width=self.SIDE_W)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Frame(self, bg=T.BORDER, width=1).pack(side="left", fill="y")
        pad = ttk.Frame(side, style="Card.TFrame", padding=(26, 28, 26, 24))
        pad.pack(fill="both", expand=True)

        brand = ttk.Frame(pad, style="Card.TFrame")
        brand.pack(fill="x")
        self._logo = load_logo(46)
        tk.Label(brand, image=self._logo, bg=T.CARD).pack(side="left", padx=(0, 12))
        names = ttk.Frame(brand, style="Card.TFrame")
        names.pack(side="left")
        ttk.Label(names, text="Ozzie's", style="Hero.TLabel").pack(anchor="w")
        ttk.Label(names, text="Pin Studio", style="Hero.TLabel").pack(anchor="w")
        ttk.Label(pad, text="Image sheets for your pin badges",
                  style="Muted.TLabel").pack(anchor="w", pady=(14, 22))

        self.btn_new = ttk.Button(pad, text="+  New canvas", style="Hero.TButton",
                                  command=app.new_canvas)
        self.btn_new.pack(fill="x")
        self.btn_browse = ttk.Button(pad, text="Browse for a canvas…", style="Ghost.TButton",
                                     command=app.open_canvas)
        self.btn_browse.pack(fill="x", pady=(10, 0))

        more = self.more_row = ttk.Frame(pad, style="Card.TFrame")
        more.pack(fill="x", pady=(10, 0))
        more.columnconfigure(0, weight=3, uniform="more")
        more.columnconfigure(1, weight=2, uniform="more")
        ttk.Button(more, text="Options", style="Ghost.TButton",
                   command=app.open_options).grid(row=0, column=0, sticky="ew")
        ttk.Button(more, text="About", style="Ghost.TButton",
                   command=app.open_about).grid(row=0, column=1, sticky="ew", padx=(10, 0))

        ttk.Button(pad, text="Exit", style="Ghost.TButton",
                   command=app.on_close).pack(side="bottom", fill="x")

        # ---- main area -----------------------------------------------------
        main = ttk.Frame(self, padding=(40, 32, 40, 0))
        main.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(main)
        top.pack(fill="x")
        ttk.Label(top, text="Your canvases", style="Page.TLabel").pack(side="left")
        ttk.Button(top, text="Open folder", style="Ghost.TButton",
                   command=lambda: reveal_folder(app.canvases_dir())).pack(side="right")
        self.count_lbl = ttk.Label(main, style="Hint.TLabel")
        self.count_lbl.pack(anchor="w", pady=(2, 0))

        bar = self.search_row = ttk.Frame(main)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Label(bar, text="Search", style="Hint.TLabel").pack(side="left", padx=(0, 8))
        entry = ttk.Entry(bar, textvariable=self.v_search, width=30)
        entry.pack(side="left")
        entry.bind("<Escape>", lambda e: (self.v_search.set(""), "break")[1])
        self.v_search.trace_add("write", lambda *_: self._search_changed())
        sort = ttk.Combobox(bar, textvariable=self.v_sort, values=SORTS, state="readonly",
                            width=16)
        sort.pack(side="right")
        ttk.Label(bar, text="Sort by", style="Hint.TLabel").pack(side="right", padx=(0, 8))
        sort.bind("<<ComboboxSelected>>", lambda e: self._sort_changed())

        body = self.body = ttk.Frame(main)
        body.pack(fill="both", expand=True, pady=(16, 0))
        self.cv = tk.Canvas(body, bg=T.BG, highlightthickness=0)
        self.sb = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=self._on_scroll)
        self.cv.pack(side="left", fill="both", expand=True)
        self.list = tk.Frame(self.cv, bg=T.BG)
        # the list is a gap wider than the window and shifted left by half of it, so the equal
        # half-gap margins around every card hang outside the visible area
        self._win = self.cv.create_window(-self.GAP // 2, 0, anchor="nw", window=self.list)
        self.list.bind("<Configure>", lambda e: self._fit_scrollregion())
        self.cv.bind("<Configure>", self._canvas_resized)
        self._fam = fam
        # bind_all (without add=) so a rebuilt HomeScreen replaces the old handler
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._on_wheel)

    def _fit_scrollregion(self):
        """The scrollable area is never smaller than the window, so a short list can't be
        dragged up and away, leaving blank space.
        """
        h = max(self.list.winfo_reqheight(), self.cv.winfo_height())
        self.cv.configure(scrollregion=(0, 0, max(1, self.cv.winfo_width()), h))

    def _canvas_resized(self, e):
        """The window changed size: stretch the list and re-flow the cards."""
        self.cv.itemconfigure(self._win, width=e.width + self.GAP)
        self._layout()
        self._fit_scrollregion()

    def _on_scroll(self, lo, hi):
        """Show the scrollbar only when the list is taller than the window."""
        self.sb.set(lo, hi)
        need = float(lo) > 0.0 or float(hi) < 1.0
        if need and not self._sb_on:
            self._sb_on = True
            self.sb.pack(side="right", fill="y", before=self.cv)
        elif not need and self._sb_on:
            self._sb_on = False
            self.sb.pack_forget()

    def _on_wheel(self, e):
        """Scroll the list with the mouse wheel. Windows and macOS report ``delta``; Linux
        sends buttons 4 and 5.
        """
        try:
            if not self.winfo_ismapped():
                return
            if e.num == 4:
                step = -1
            elif e.num == 5:
                step = 1
            else:
                step = -1 if e.delta > 0 else 1
            lo, hi = self.cv.yview()
            if lo <= 0.0 and hi >= 1.0:           # everything fits: nothing to scroll
                return
            self.cv.yview_scroll(step * 2, "units")
        except tk.TclError:
            pass

    def refresh(self):
        """Look at the canvases folder again and redraw the list."""
        self._items = self.app.scan_canvases()
        self._render()

    def _search_changed(self):
        """The search text changed: redraw shortly after the last keystroke."""
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(150, self._render)

    def _sort_changed(self):
        """A different sort order was chosen: remember it and redraw."""
        self.app.settings["sort"] = self.v_sort.get()
        save_settings(self.app.settings)
        self._render()

    def _sorted(self, items):
        """``items`` in the order chosen in the "Sort by" box."""
        how = self.v_sort.get()
        if how == "Name A–Z":
            return sorted(items, key=lambda i: i["name"].casefold())
        if how == "Name Z–A":
            return sorted(items, key=lambda i: i["name"].casefold(), reverse=True)
        if how == "Oldest first":
            return sorted(items, key=lambda i: i["mtime"])
        if how == "Most pins":
            return sorted(items, key=lambda i: (-i["pins"], i["name"].casefold()))
        if how == "Recently opened":
            order = {os.path.normcase(p): n for n, p in enumerate(self.app.recent_paths())}
            return sorted(items, key=lambda i: (
                order.get(os.path.normcase(os.path.abspath(i["path"])), len(order)),
                -i["mtime"]))
        return sorted(items, key=lambda i: i["mtime"], reverse=True)      # recently edited

    def _render(self):
        """Draw the list: the search filter and sort order applied, a "Jump back in" row of
        recent canvases, and the cards. Thumbnails are filled in afterwards, in the
        background.
        """
        if self._search_job is not None:          # a queued redraw would only repeat this one
            self.after_cancel(self._search_job)
            self._search_job = None
        self._gen += 1
        self._pending = {}
        self.shown = []
        self._cards, self._cols = [], 0
        for w in self.list.winfo_children():
            w.destroy()
        query = self.v_search.get().strip().casefold()
        total = len(self._items)
        items = [i for i in self._items
                 if not query or query in f"{i['name']} {i['paper']} {i['pin']}".casefold()]
        noun = "canvas" if total == 1 else "canvases"
        if query:
            self.count_lbl.config(text=f"{len(items)} of {total} {noun}")
        else:
            self.count_lbl.config(text=f"{total} {noun}")
        if not total:
            self._empty_state("No canvases yet", "Create your first sheet and it will show up "
                              "here.", button=True)
        elif not items:
            self._empty_state("Nothing found", f"No canvas matches “{self.v_search.get().strip()}”.")
        else:
            self.grid_host = tk.Frame(self.list, bg=T.BG)
            self.grid_host.pack(fill="x", pady=(2, 0))
            if not query:
                self._cards.append(self._new_tile())
            for info in self._sorted(items):
                self.shown.append(info["name"])
                self._cards.append(self._card(info))
            self._layout(force=True)
        self.update_idletasks()
        self._fit_scrollregion()
        self.cv.yview_moveto(0)
        self._start_thumbs()

    def _empty_state(self, title, text, button=False):
        """The friendly message shown when there is nothing to list."""
        box = tk.Frame(self.list, bg=T.BG)
        box.pack(fill="x", pady=(70, 0))
        self._empty_icon = load_logo(96)
        tk.Label(box, image=self._empty_icon, bg=T.BG).pack()
        tk.Label(box, text=title, bg=T.BG, fg=T.PETROL,
                 font=("Georgia", 18, "bold")).pack(pady=(16, 4))
        tk.Label(box, text=text, bg=T.BG, fg=T.MUTED, font=(self._fam, 10)).pack()
        if button:
            ttk.Button(box, text="+  New canvas", style="Hero.TButton",
                       command=self.app.new_canvas).pack(pady=(18, 0))
        else:
            ttk.Button(box, text="Clear search", style="Ghost.TButton",
                       command=lambda: self.v_search.set("")).pack(pady=(18, 0))

    # ---- thumbnails: made in a background thread so the list appears at once
    def _thumb(self, parent, info, bg):
        """A label with the canvas's round thumbnail. It shows a placeholder first if the
        real picture still has to be made.
        """
        key = (info["path"], info["mtime"], self.ICON)
        photo = self._icons.get(key)
        lbl = tk.Label(parent, bg=bg)
        if photo is None and info["art"] is None:
            photo = self._icons[key] = make_icon(None, self.ICON)
        if photo is not None:
            lbl.config(image=photo)
        else:
            lbl.config(image=self._placeholder)
            self._pending.setdefault(key, []).append((lbl, info["art"]))
        return lbl

    def _start_thumbs(self):
        """Make the missing thumbnails one by one in a thread; the main thread picks them up
        and puts them in place as they arrive.
        """
        if not self._pending:
            return
        gen, jobs = self._gen, {k: v[0][1] for k, v in self._pending.items()}
        ready = queue.Queue()

        def work():
            for key, art in jobs.items():
                if gen != self._gen:
                    return
                try:
                    ready.put((key, render_icon_image(art, self.ICON)))
                except Exception:  # noqa: BLE001 - a broken picture just keeps the placeholder
                    ready.put((key, None))

        threading.Thread(target=work, daemon=True).start()
        self._poll_thumbs(ready, gen, len(jobs))

    def _poll_thumbs(self, ready, gen, left):
        """Collect finished thumbnails (main thread only: Tk images are made here)."""
        if gen != self._gen:
            return
        while left:
            try:
                key, im = ready.get_nowait()
            except queue.Empty:
                break
            left -= 1
            if im is None:
                continue
            photo = self._icons[key] = ImageTk.PhotoImage(im)
            for lbl, _art in self._pending.get(key, []):
                try:
                    lbl.config(image=photo)
                except tk.TclError:
                    pass
        if left:
            self.after(30, self._poll_thumbs, ready, gen, left)

    # ---- the card grid
    def _layout(self, force=False):
        """Flow the cards into as many equal columns as fit the window."""
        if not self._cards:
            return
        width = max(self.cv.winfo_width(), 1)
        cols = max(1, (width + self.GAP) // (self.CARD_MIN_W + self.GAP))
        if cols == self._cols and not force:
            return
        host = self.grid_host
        for c in range(max(cols, self._cols)):
            host.columnconfigure(c, weight=1 if c < cols else 0,
                                 uniform="cards" if c < cols else "")
        for n, card in enumerate(self._cards):
            r, c = divmod(n, cols)
            card.grid(row=r, column=c, sticky="nsew",
                      padx=self.GAP // 2,
                      pady=(0, self.GAP))
        self._cols = cols

    def _shell(self, bg):
        """An empty fixed-size card: a 1px border frame (lights up on hover) around the body."""
        outer = tk.Frame(self.grid_host, bg=T.BORDER, height=self.CARD_H)
        outer.pack_propagate(False)
        card = tk.Frame(outer, bg=bg)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        return outer, card

    def _new_tile(self):
        """The first tile of the grid: a gentle "start a new canvas" invitation."""
        outer, card = self._shell(T.BG)
        S = self.ICON
        plus = tk.Canvas(card, width=S, height=S, bg=T.BG, highlightthickness=0)
        plus.create_oval(4, 4, S - 4, S - 4, outline=T.TEAL, width=2)
        m, r = S // 2, S // 7 + 4
        plus.create_line(m - r, m, m + r, m, fill=T.TEAL, width=3, capstyle="round")
        plus.create_line(m, m - r, m, m + r, fill=T.TEAL, width=3, capstyle="round")
        plus.pack(pady=(28, 12))
        name = tk.Label(card, text="New canvas", bg=T.BG, fg=T.TEAL,
                        font=("Georgia", 13, "bold"))
        name.pack()
        sub = tk.Label(card, text="Start a fresh sheet", bg=T.BG, fg=T.MUTED,
                       font=(self._fam, 9))
        sub.pack(pady=(2, 0))
        self._make_clickable(outer, (card, plus, name, sub), self.app.new_canvas, rest=T.BG)
        return outer

    def _card(self, info):
        """One canvas card: round thumbnail, name, details, date and a Delete link.
        Clicking the card opens the canvas.
        """
        fam = self._fam
        outer, card = self._shell(T.CARD)

        foot = tk.Frame(card, bg=T.CARD)
        foot.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        when = time.strftime("%d %b %Y", time.localtime(info["mtime"]))
        date = tk.Label(foot, text=when, bg=T.CARD, fg=T.MUTED, font=(fam, 9))
        date.pack(side="left")
        dele = tk.Label(foot, text="Delete", bg=T.CARD, fg=T.MUTED, cursor="hand2",
                        font=(fam, 9, "underline"))
        dele.pack(side="right")
        dele.bind("<Button-1>", lambda e, i=info: self.delete(i))
        dele.bind("<Enter>", lambda e: dele.config(fg=T.WARN))
        dele.bind("<Leave>", lambda e: dele.config(fg=T.MUTED))

        icon = self._thumb(card, info, T.CARD)
        icon.pack(pady=(24, 10))
        title = info["name"] if len(info["name"]) <= 22 else info["name"][:21].rstrip() + "…"
        name = tk.Label(card, text=title, bg=T.CARD, fg=T.PETROL, font=("Georgia", 13, "bold"))
        name.pack()
        n = info["pins"]
        sub = tk.Label(card, bg=T.CARD, fg=T.MUTED, font=(fam, 9),
                       text=f"{info['paper']}  ·  {info['pin']}  ·  {n} pin{'s' if n != 1 else ''}")
        sub.pack(pady=(3, 0))

        self._make_clickable(outer, (card, icon, name, sub, foot, date, dele),
                             lambda p=info["path"]: self.app.open_path(p), skip=(dele,))
        return outer

    def _make_clickable(self, outer, widgets, action, skip=(), rest=None):
        """Make a card run ``action`` when clicked. Hovering fades its background and border
        towards the theme's hover colours (and back), a few quick frames, nothing flashy.
        ``rest`` is the card's normal colour (the theme's card colour unless given); colours
        are read when the card is used, so they always match the current theme.
        """
        state = {"t": 0.0, "goal": 0.0, "job": None}
        STEPS, MS = 7, 16

        def paint(t):
            base = rest or T.CARD
            try:
                outer.config(bg=T._mix(T.BORDER, T.TEAL, t))
                col = T._mix(base, T.HOVER, t)
                for w in widgets:
                    w.config(bg=col)
            except tk.TclError:                  # the card was destroyed mid-fade
                state["job"] = None
                return False
            return True

        def step():
            state["job"] = None
            d = 1.0 / STEPS
            if state["t"] < state["goal"]:
                state["t"] = min(state["goal"], state["t"] + d)
            else:
                state["t"] = max(state["goal"], state["t"] - d)
            ease = state["t"] * state["t"] * (3 - 2 * state["t"])       # smoothstep
            if paint(ease) and state["t"] != state["goal"]:
                state["job"] = outer.after(MS, step)

        def go(goal):
            state["goal"] = goal
            if state["job"] is None:
                state["job"] = outer.after(0, step)

        def leave(_e):
            try:
                x, y = outer.winfo_pointerxy()
                under = outer.winfo_containing(x, y)
            except (tk.TclError, KeyError):
                under = None
            if under is None or not (under == outer or str(under).startswith(str(outer) + ".")):
                go(0.0)

        for w in widgets:
            w.bind("<Enter>", lambda e: go(1.0), add="+")
            w.bind("<Leave>", leave, add="+")
            if w not in skip:
                w.config(cursor="hand2")
                w.bind("<Button-1>", lambda e: action())

    def delete(self, info):
        """Ask first, then remove the canvas file. The images are never touched."""
        if not messagebox.askyesno(
                "Delete canvas?",
                f"Do you really want me to delete “{info['name']}”?\n\n"
                "Only the canvas file goes away. Your images stay safe, I promise!",
                icon="warning", parent=self.app, yes="Delete it", no="Keep it"):
            return
        try:
            os.remove(info["path"])
        except OSError as ex:
            messagebox.showerror("Oh no!", f"I couldn't delete that canvas:\n{ex}")
            self.refresh()
            return
        self.app.forget_recent(info["path"])
        self.refresh()
        self.app.toasts.show("deleted", name=info["name"])
