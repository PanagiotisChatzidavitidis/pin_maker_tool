"""The Options window: every setting of the app in one place.

It is opened from the Options button on the start screen and in the editor. It holds the
display mode (full screen or windowed), the light and dark themes, the tutorial and the
canvases folder, and a button that puts everything back to its default.
"""

import tkinter as tk
from tkinter import ttk

from . import mascot, smooth, theme as T
from .cover import FULLSCREEN_MESSAGES, WINDOWED_MESSAGES, ThemeCover
from .dialogs import keep_titlebar, messagebox, set_titlebar, set_window_icon
from ..system_actions import reveal_folder
from .widgets import MascotTile, Segmented, ThemeTile


class OptionsDialog(tk.Toplevel):
    """A modal window with the app's options. Changes apply straight away, so the only
    buttons are Restore defaults and Return (which closes the window).
    """
    def __init__(self, app):
        """Build the window, centre it over the app and show it."""
        super().__init__(app)
        self.withdraw()                      # build off-screen, then show centred
        self.app = app
        self._cover = None
        self.title("Options")
        self.resizable(False, False)
        set_window_icon(self)
        try:
            if app.winfo_viewable():
                self.transient(app)
        except tk.TclError:
            pass
        self._build()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.destroy())

        ThemeCover.warm(self)
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = app.winfo_rootx() + (app.winfo_width() - w) // 2
        y = app.winfo_rooty() + (app.winfo_height() - h) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        set_titlebar(self)
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()

    def _build(self):
        """Fill the window with the current theme's colours. It is called again after a theme
        change, so the window itself changes colour too.

        Layout: a header with the logo, then two columns: Display and Canvases folder on the
        left, the Themes on the right, and a footer bar with Restore defaults and Return.
        """
        keep = getattr(self, "_cover_cv", None)             # the loading cover stays
        for child in self.winfo_children():
            if child is not keep:
                child.destroy()
        self.configure(bg=T.BG)
        app = self.app
        fam = app.base_font[0]
        self._mode_imgs = []                                   # keep the icons alive

        # ---- header: the mascot on a soft plate, a big title and a friendly line
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=30, pady=(16, 12))
        self._logo = smooth.hero_logo(68, T._mix(T.BG, T.TEAL, 0.16), T.BG)
        self._logo_lbl = tk.Label(head, image=self._logo, bg=T.BG, bd=0)
        self._logo_lbl.pack(side="left", padx=(0, 16))
        titles = tk.Frame(head, bg=T.BG)
        titles.pack(side="left")
        tk.Label(titles, text="Options", bg=T.BG, fg=T.PETROL,
                 font=("Georgia", 22, "bold")).pack(anchor="w")
        ttk.Label(titles, text="Make the app feel like yours. Changes apply right away.",
                  style="Hint.TLabel").pack(anchor="w", pady=(2, 0))
        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=30, pady=(14, 14))
        left = tk.Frame(body, bg=T.BG)
        left.pack(side="left", fill="y", anchor="n")
        tk.Frame(left, bg=T.BG, width=330, height=1).pack()          # the column's width
        right = tk.Frame(body, bg=T.BG)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0), anchor="n")

        # ---- left: the mascot
        f = self._card(left, "face", "Mascot", pady=(0, 14))
        row = tk.Frame(f, bg=T.CARD)
        row.pack(anchor="w")
        self._mascot_tiles = {}
        for i, (mid, (name, _note)) in enumerate(mascot.INFO.items()):
            tile = MascotTile(row, mid, name, mid == mascot.current,
                              lambda m=mid: self._mascot_picked(m), fam)
            tile.pack(side="left", padx=(0, 8) if i < 2 else 0)
            self._mascot_tiles[mid] = tile
        self._mascot_note = ttk.Label(f, text=mascot.INFO[mascot.current][1],
                                      style="Muted.TLabel")
        self._mascot_note.pack(anchor="w", pady=(10, 0))

        # ---- left: display
        f = self._card(left, "monitor", "Display", pady=(0, 14))
        self._setting(f, "Window", "Press F11 at any time to switch.")
        Segmented(f, app.v_window, [("fullscreen", "Full screen"), ("windowed", "Windowed")],
                  command=self._mode_changed).pack(fill="x", pady=(8, 0))

        # ---- left: the tutorial
        f = self._card(left, "play", "Tutorial", pady=(0, 0))
        ttk.Label(f, text=f"Want a hand? {mascot.INFO[mascot.current][0]} shows you around "
                          "the start screen and the editor.", style="Muted.TLabel", justify="left",
                  wraplength=300).pack(anchor="w")
        ttk.Button(f, text="Watch the tutorial again", style="Ghost.TButton",
                   command=self._replay).pack(fill="x", pady=(12, 0))

        # ---- right: themes, a light column and a dark column of preview tiles
        f = self._card(right, "palette", "Themes", pady=(0, 0))
        ttk.Label(f, text="Pick a theme to use it. A light theme gives the light look, a dark "
                          "one the dark look.", style="Muted.TLabel", justify="left",
                  wraplength=2 * ThemeTile.W).pack(anchor="w", pady=(0, 12))
        cols = tk.Frame(f, bg=T.CARD)
        cols.pack(fill="x")
        for c, (mode, label) in enumerate((("light", "LIGHT"), ("dark", "DARK"))):
            col = tk.Frame(cols, bg=T.CARD)
            col.grid(row=0, column=c, sticky="n", padx=(0, 14) if c == 0 else 0)
            hd = tk.Frame(col, bg=T.CARD)
            hd.pack(fill="x", pady=(0, 8))
            img = smooth.mode_icon(mode, T.ORCHID if mode == "light" else T.TEAL, T.CARD)
            self._mode_imgs.append(img)
            tk.Label(hd, image=img, bg=T.CARD, bd=0).pack(side="left")
            ttk.Label(hd, text=label, style="Section.TLabel").pack(side="left", padx=(6, 0))
            tk.Frame(hd, bg=T.BORDER, height=1).pack(side="left", fill="x", expand=True,
                                                     padx=(10, 0))
            for theme_id in T.THEME_ORDER[mode]:
                title, note = T.THEME_INFO[theme_id]
                # the tile that is in use right now gets the tick
                in_use = theme_id == app.current_theme()
                tile = ThemeTile(col, T.THEMES[theme_id], title, note, in_use,
                                 lambda t=theme_id: self._theme_picked(t), fam, bg=T.CARD)
                tile.pack(pady=(0, 4))

        # ---- right: canvases folder, under the themes
        f = self._card(right, "folder", "Your files", pady=(12, 0))
        self.folder_lbl = self._folder_row(
            f, "Canvases", "Your saved sheets", app.canvases_dir(), change=self._change_folder)
        tk.Frame(f, bg=T.BORDER, height=1).pack(fill="x", pady=10)
        self.pdf_lbl = self._folder_row(
            f, "PDFs", "Sheets you export for printing", app._dir("export_dir"),
            change=self._change_pdf_folder)

        # ---- footer bar
        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")
        foot = tk.Frame(self, bg=T.CARD)
        foot.pack(fill="x")
        inner = tk.Frame(foot, bg=T.CARD)
        inner.pack(fill="x", padx=30, pady=10)
        ttk.Button(inner, text="Return", style="Accent.TButton",
                   command=self.destroy).pack(side="right")
        ttk.Button(inner, text="Restore defaults", style="Soft.TButton",
                   command=self._restore).pack(side="left")

    def _replay(self):
        """Close Options and let the mascot give the tour again."""
        self.destroy()
        self.app.replay_guide()

    def _mascot_picked(self, mid):
        """A mascot card was clicked: switch to it (the card hops to say hello)."""
        if mid != mascot.current:
            self.app.choose_mascot(mid)
            self._logo = self.app.toasts.logo()
            self._logo_lbl.config(image=self._logo)
            for m, tile in self._mascot_tiles.items():
                tile.set_selected(m == mid)
            self._mascot_note.config(text=mascot.INFO[mid][1])
        self._mascot_tiles[mid].hop()

    def _setting(self, parent, title, note, wrap=300, side=None):
        """A setting's name in bold with a muted explanation under it (inside a card)."""
        box = tk.Frame(parent, bg=T.CARD)
        box.pack(anchor="w", **({"side": side} if side else {}))
        tk.Label(box, text=title, bg=T.CARD, fg=T.TEXT,
                 font=(self.app.base_font[0], 10, "bold")).pack(anchor="w")
        ttk.Label(box, text=note, style="Muted.TLabel", justify="left",
                  wraplength=wrap).pack(anchor="w", pady=(2, 0))

    def _mode_changed(self):
        """Full screen / Windowed was picked."""
        full = self.v_mode_full()
        if full != self.app._is_full and not self.app._morph and not self._cover:
            self._cover = ThemeCover(self.app, T.THEME_NAME, parent=self,
                                     messages=FULLSCREEN_MESSAGES if full else WINDOWED_MESSAGES)
            self.after(450, self._mode_cover_done)
        set_titlebar(self, force=True)              # dark/light bar before the change...
        self.app.set_fullscreen(full)
        keep_titlebar(self)                         # ...and again while the window settles

    def v_mode_full(self):
        """True if the Window switch is on "Full screen"."""
        return self.app.v_window.get() == "fullscreen"

    def _mode_cover_done(self):
        """Take this window's loading screen away (it waits out its minimum time first)."""
        if self._cover:
            cover, self._cover = self._cover, None
            cover.close()

    def _theme_picked(self, theme_id):
        """A theme tile was clicked: use that theme."""
        if theme_id == self.app.current_theme():
            return
        if not (self._cover and not self._cover.closed):
            self._cover = ThemeCover(self.app, theme_id, parent=self)   # hides the rebuild
        self.app.choose_theme(theme_id, done=self._rebuild)

    def _rebuild(self):
        """Redraw this window in the new theme (unless it was closed meanwhile)."""
        if not self.winfo_exists():
            return
        self._build()
        set_titlebar(self, force=True)
        keep_titlebar(self, (60, 200, 450, 800))
        if self._cover:
            self._cover.lift()
            self._cover.close()
            self._cover = None

    def _restore(self):
        """Ask first, then put every option back to its default."""
        if not messagebox.askyesno(
                "Restore defaults",
                "Put every option back to its default?\n\nThis resets the window mode, "
                "the theme and the canvases folder. Your canvases are not touched.",
                parent=self, yes="Restore", no="Keep my options"):
            return
        self.app.restore_defaults(done=self._rebuild)

    def _card(self, parent, icon, title, pady=(0, 10)):
        """A bordered card whose heading has a small line icon. Returns the inside frame."""
        outer = tk.Frame(parent, bg=T.BORDER)
        outer.pack(fill="x", pady=pady)
        inner = tk.Frame(outer, bg=T.CARD, padx=16, pady=11)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(inner, bg=T.CARD)
        head.pack(fill="x", pady=(0, 8))
        img = smooth.nav_icon(icon, T.TEAL, T.CARD, 20)
        self._mode_imgs.append(img)
        tk.Label(head, image=img, bg=T.CARD, bd=0).pack(side="left", padx=(0, 8))
        tk.Label(head, text=title, bg=T.CARD, fg=T.TEXT,
                 font=(self.app.base_font[0], 11, "bold")).pack(side="left")
        return inner

    def _folder_row(self, parent, title, note, path, change):
        """A folder: a name with a short note, its path in a field, and Open and Change
        buttons. Returns the label that shows the path.
        """
        fam = self.app.base_font[0]
        box = tk.Frame(parent, bg=T.CARD)
        box.pack(fill="x")
        head = tk.Frame(box, bg=T.CARD)
        head.pack(fill="x")
        names = tk.Frame(head, bg=T.CARD)
        names.pack(side="left")
        tk.Label(names, text=title, bg=T.CARD, fg=T.TEXT, font=(fam, 10, "bold")).pack(anchor="w")
        tk.Label(names, text=note, bg=T.CARD, fg=T.MUTED, font=(fam, 9)).pack(anchor="w")
        ttk.Button(head, text="Change…", style="Ghost.TButton",
                   command=change).pack(side="right", padx=(8, 0))
        ttk.Button(head, text="Open", style="Ghost.TButton",
                   command=lambda: reveal_folder(lbl.cget("text"))).pack(side="right")
        edge = tk.Frame(box, bg=T.BORDER)
        edge.pack(fill="x", pady=(8, 0))
        lbl = tk.Label(edge, text=path, bg=T.FIELD, fg=T.TEXT, font=(fam, 9), anchor="w",
                       justify="left", wraplength=500, padx=10, pady=7)
        lbl.pack(fill="x", padx=1, pady=1)
        return lbl

    def _change_folder(self):
        """Pick another canvases folder."""
        if self.app.choose_canvases_folder(parent=self):
            self.folder_lbl.config(text=self.app.canvases_dir())

    def _change_pdf_folder(self):
        """Pick another folder for exported PDFs."""
        if self.app.choose_pdf_folder(parent=self):
            self.pdf_lbl.config(text=self.app._dir("export_dir"))
