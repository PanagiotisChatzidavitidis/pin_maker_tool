"""The Options window: every setting of the app in one place.

It is opened from the Options button on the start screen and in the editor. It currently
holds the display mode (full screen or windowed), dark mode and the canvases folder.
"""

import tkinter as tk
from tkinter import ttk

from . import theme as T
from .dialogs import set_titlebar, set_window_icon
from .widgets import Segmented, Toggle, make_card


class OptionsDialog(tk.Toplevel):
    """A small modal window with the app's options. Changes apply straight away, so there
    is only a Done button to close it.
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
        """Fill the window with the current theme's colours. It is called again after the
        dark-mode switch, so the window itself changes colour too.
        """
        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=T.BG)
        app = self.app

        body = ttk.Frame(self, padding=(24, 22, 24, 8))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Options", style="Title.TLabel").pack(anchor="w", pady=(0, 14))

        f = make_card(body, "Window")
        Segmented(f, app.v_window, [("fullscreen", "Full screen"), ("windowed", "Windowed")],
                  command=self._mode_changed).pack(fill="x")
        ttk.Label(f, text="Press F11 at any time to switch.",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

        f = make_card(body, "Appearance")
        row = ttk.Frame(f, style="Card.TFrame")
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Dark mode", style="Card.TLabel").pack(side="left")
        Toggle(row, app.v_dark, command=self._dark_changed, bg=T.CARD).pack(side="right")

        f = make_card(body, "Canvases folder")
        self.folder_lbl = ttk.Label(f, text=app.canvases_dir(), style="Muted.TLabel",
                                    justify="left", wraplength=360)
        self.folder_lbl.pack(anchor="w")
        ttk.Button(f, text="Change folder…", style="Ghost.TButton",
                   command=self._change_folder).pack(anchor="w", pady=(10, 0))

        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")
        foot = ttk.Frame(self, padding=(24, 12))
        foot.pack(fill="x")
        ttk.Button(foot, text="Done", style="Accent.TButton",
                   command=self.destroy).pack(side="right")
        ttk.Button(foot, text="Exit app", style="Soft.TButton",
                   command=self._exit_app).pack(side="left")

    def _mode_changed(self):
        """Full screen / Windowed was picked."""
        self.app.set_fullscreen(self.app.v_window.get() == "fullscreen")

    def _dark_changed(self):
        """The dark-mode switch was flipped. The app rebuilds its own screens; this window
        rebuilds itself right after (queued behind the app's rebuild).
        """
        self.app.toggle_theme()
        self.after_idle(self._rebuild)

    def _rebuild(self):
        """Redraw this window in the new theme."""
        self._build()
        set_titlebar(self)

    def _change_folder(self):
        """Pick another canvases folder."""
        if self.app.choose_canvases_folder(parent=self):
            self.folder_lbl.config(text=self.app.canvases_dir())

    def _exit_app(self):
        """Close this window and quit the app (it offers to save first if needed)."""
        self.destroy()
        self.app.on_close()
