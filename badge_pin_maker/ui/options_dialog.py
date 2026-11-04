"""The Options window: every setting of the app in one place.

It is opened from the Options button on the start screen and in the editor. It holds the
display mode (full screen or windowed), smooth animations, the light and dark themes and the
canvases folder, and a button that puts everything back to its default.
"""

import tkinter as tk
from tkinter import ttk

from . import theme as T
from .dialogs import messagebox, set_titlebar, set_window_icon
from .widgets import Segmented, ThemeTile, Toggle, make_card


def _draw_mode_icon(cv, mode):
    """A tiny sun (light) or moon (dark) in the colours of the theme in use."""
    col = T.ORCHID if mode == "light" else T.TEAL
    if mode == "light":
        cv.create_oval(5, 5, 13, 13, fill=col, outline=col)
        for dx, dy in ((9, 1), (9, 17), (1, 9), (17, 9), (3, 3), (15, 3), (3, 15), (15, 15)):
            x, y = 9 + (dx - 9) * 0.8, 9 + (dy - 9) * 0.8
            cv.create_line(9 + (dx - 9) * 0.62, 9 + (dy - 9) * 0.62, x, y, fill=col, width=1.5)
    else:
        cv.create_oval(3, 3, 15, 15, fill=col, outline=col)
        cv.create_oval(7, 1, 18, 12, fill=T.CARD, outline=T.CARD)


class OptionsDialog(tk.Toplevel):
    """A modal window with the app's options. Changes apply straight away, so the only
    buttons are Restore defaults and Return (which closes the window).
    """
    def __init__(self, app):
        """Build the window, centre it over the app and show it."""
        super().__init__(app)
        self.withdraw()                      # build off-screen, then show centred
        self.app = app
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
        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=T.BG)
        app = self.app
        fam = app.base_font[0]

        # ---- header
        head = tk.Frame(self, bg=T.BG)
        head.pack(fill="x", padx=28, pady=(22, 16))
        self._logo = app.toasts.logo()
        tk.Label(head, image=self._logo, bg=T.BG).pack(side="left", padx=(0, 14))
        titles = tk.Frame(head, bg=T.BG)
        titles.pack(side="left")
        ttk.Label(titles, text="Options", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Make the app feel like yours. Changes apply right away.",
                  style="Hint.TLabel").pack(anchor="w", pady=(2, 0))
        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(18, 20))
        left = tk.Frame(body, bg=T.BG)
        left.pack(side="left", fill="y", anchor="n")
        tk.Frame(left, bg=T.BG, width=330, height=1).pack()          # the column's width
        right = tk.Frame(body, bg=T.BG)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0), anchor="n")

        # ---- left: display
        f = make_card(left, "Display", pady=(0, 14))
        self._setting(f, "Window", "Press F11 at any time to switch.")
        Segmented(f, app.v_window, [("fullscreen", "Full screen"), ("windowed", "Windowed")],
                  command=self._mode_changed).pack(fill="x", pady=(8, 0))
        tk.Frame(f, bg=T.BORDER, height=1).pack(fill="x", pady=14)
        row = tk.Frame(f, bg=T.CARD)
        row.pack(fill="x")
        Toggle(row, app.v_anim, command=app.animations_changed, bg=T.CARD).pack(side="right")
        self._setting(row, "Smooth animations", "Pins glide when swapped and fade away "
                      "when cleared.", wrap=220, side="left")

        # ---- left: canvases folder
        f = make_card(left, "Canvases folder", pady=(0, 0))
        edge = tk.Frame(f, bg=T.BORDER)
        edge.pack(fill="x")
        self.folder_lbl = tk.Label(edge, text=app.canvases_dir(), bg=T.FIELD, fg=T.TEXT,
                                   font=(fam, 9), anchor="w", justify="left", wraplength=290,
                                   padx=10, pady=8)
        self.folder_lbl.pack(fill="x", padx=1, pady=1)
        ttk.Button(f, text="Change folder…", style="Ghost.TButton",
                   command=self._change_folder).pack(anchor="e", pady=(10, 0))

        # ---- right: themes, a light column and a dark column of preview tiles
        f = make_card(right, "Themes", pady=(0, 0))
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
            icon = tk.Canvas(hd, width=18, height=18, bg=T.CARD, highlightthickness=0)
            icon.pack(side="left")
            _draw_mode_icon(icon, mode)
            ttk.Label(hd, text=label, style="Section.TLabel").pack(side="left", padx=(6, 0))
            tk.Frame(hd, bg=T.BORDER, height=1).pack(side="left", fill="x", expand=True,
                                                     padx=(10, 0))
            for theme_id in T.THEME_ORDER[mode]:
                title, note = T.THEME_INFO[theme_id]
                # the tile that is in use right now gets the tick
                in_use = theme_id == app.current_theme()
                tile = ThemeTile(col, T.THEMES[theme_id], title, note, in_use,
                                 lambda t=theme_id: self._theme_picked(t), fam, bg=T.CARD)
                tile.pack(pady=(0, 5))

        # ---- footer bar
        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")
        foot = tk.Frame(self, bg=T.CARD)
        foot.pack(fill="x")
        inner = tk.Frame(foot, bg=T.CARD)
        inner.pack(fill="x", padx=28, pady=12)
        ttk.Button(inner, text="Return", style="Accent.TButton",
                   command=self.destroy).pack(side="right")
        ttk.Button(inner, text="Restore defaults", style="Soft.TButton",
                   command=self._restore).pack(side="left")

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
        self.app.set_fullscreen(self.app.v_window.get() == "fullscreen")

    def _theme_picked(self, theme_id):
        """A theme tile was clicked: use that theme."""
        if theme_id == self.app.current_theme():
            return
        self.app.choose_theme(theme_id)
        self.after_idle(self._rebuild)

    def _rebuild(self):
        """Redraw this window in the new theme."""
        self._build()
        set_titlebar(self)

    def _restore(self):
        """Ask first, then put every option back to its default."""
        if not messagebox.askyesno(
                "Restore defaults",
                "Put every option back to its default?\n\nThis resets the window mode, "
                "the theme and the canvases folder. Your canvases are not touched.",
                parent=self, yes="Restore", no="Keep my options"):
            return
        self.app.restore_defaults()
        self.after_idle(self._rebuild)

    def _change_folder(self):
        """Pick another canvases folder."""
        if self.app.choose_canvases_folder(parent=self):
            self.folder_lbl.config(text=self.app.canvases_dir())
