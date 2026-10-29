"""The Options window: every setting of the app in one place.

It is opened from the Options button on the start screen and in the editor. It holds the
display mode (full screen or windowed), the light and dark themes, dark mode and the canvases
folder, and a button that puts everything back to its default.
"""

import tkinter as tk
from tkinter import ttk

from . import theme as T
from .dialogs import messagebox, set_titlebar, set_window_icon
from .widgets import Segmented, ThemeTile, Toggle, make_card


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
        """
        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=T.BG)
        app = self.app
        fam = app.base_font[0]

        body = ttk.Frame(self, padding=(24, 20, 24, 6))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Options", style="Title.TLabel").pack(anchor="w", pady=(0, 12))

        f = make_card(body, "Window", pady=(0, 8))
        Segmented(f, app.v_window, [("fullscreen", "Full screen"), ("windowed", "Windowed")],
                  command=self._mode_changed).pack(fill="x")
        ttk.Label(f, text="Press F11 at any time to switch.",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

        # ---- themes: a light column and a dark column of preview tiles
        f = make_card(body, "Themes", pady=(0, 8))
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Dark mode", style="Card.TLabel").pack(side="left")
        Toggle(row, app.v_dark, command=self._dark_changed, bg=T.CARD).pack(side="right")
        ttk.Label(f, text="Pick a theme to use it. The Dark mode switch flips between your "
                          "chosen light and dark theme.", style="Muted.TLabel",
                  justify="left", wraplength=2 * ThemeTile.W + 14).pack(anchor="w",
                                                                         pady=(0, 10))
        cols = ttk.Frame(f, style="Card.TFrame")
        cols.pack(fill="x")
        for c, (mode, label, chosen) in enumerate(
                (("light", "LIGHT THEMES", app.light_theme),
                 ("dark", "DARK THEMES", app.dark_theme))):
            col = ttk.Frame(cols, style="Card.TFrame")
            col.grid(row=0, column=c, sticky="n", padx=(0, 14) if c == 0 else 0)
            ttk.Label(col, text=label, style="Section.TLabel").pack(anchor="w", pady=(0, 6))
            for theme_id in T.THEME_ORDER[mode]:
                title, note = T.THEME_INFO[theme_id]
                # the tile that is in use right now gets the tick
                in_use = theme_id == app.current_theme()
                tile = ThemeTile(col, T.THEMES[theme_id], title, note, in_use,
                                 lambda t=theme_id: self._theme_picked(t), fam, bg=T.CARD)
                tile.pack(pady=(0, 6))

        # ---- canvases folder
        f = make_card(body, "Canvases folder", pady=(0, 6))
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="Change folder…", style="Ghost.TButton",
                   command=self._change_folder).pack(side="right", padx=(12, 0))
        self.folder_lbl = ttk.Label(row, text=app.canvases_dir(), style="Muted.TLabel",
                                    justify="left", wraplength=2 * ThemeTile.W - 90)
        self.folder_lbl.pack(side="left", fill="x", expand=True)

        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")
        foot = ttk.Frame(self, padding=(24, 12))
        foot.pack(fill="x")
        ttk.Button(foot, text="Return", style="Accent.TButton",
                   command=self.destroy).pack(side="right")
        ttk.Button(foot, text="Restore defaults", style="Soft.TButton",
                   command=self._restore).pack(side="left")

    def _mode_changed(self):
        """Full screen / Windowed was picked."""
        self.app.set_fullscreen(self.app.v_window.get() == "fullscreen")

    def _dark_changed(self):
        """The dark-mode switch was flipped. The app rebuilds its own screens; this window
        rebuilds itself right after (queued behind the app's rebuild).
        """
        self.app.toggle_theme()
        self.after_idle(self._rebuild)

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
