"""The Help page: a cheat sheet of every keyboard shortcut and mouse action."""

import tkinter as tk

from . import theme as T
from .screens import Screen


def _groups(mod):
    return [
        ("Pins", [
            ("Click an empty circle", "Add images"),
            ("Click a pin", "Edit, Preview, Duplicate or Remove"),
            ("Drag a pin", "Move it, or swap with another"),
            ("Enter", "Edit (crop) the pin under the mouse"),
            ("P", "Preview the pin under the mouse"),
            (f"{mod}+C", "Copy the pin under the mouse"),
            (f"{mod}+V", "Paste into an empty circle"),
            (f"{mod}+D", "Duplicate into the next empty circle"),
            ("Delete", "Remove the pin under the mouse"),
        ]),
        ("Selecting several", [
            ("Select pins", "Tick pins with a click"),
            (f"{mod}+A", "Tick every pin"),
            ("Delete", "Remove all the ticked pins"),
            ("Esc", "Leave selecting"),
        ]),
        ("Canvas", [
            (f"{mod}+N", "New canvas"),
            (f"{mod}+O", "Open a canvas"),
            (f"{mod}+S", "Save"),
            (f"{mod}+Shift+S", "Save as…"),
            (f"{mod}+E", "Export PDF"),
            (f"{mod}+P", "Print"),
            (f"{mod}+H", "Back to the menu"),
        ]),
        ("Undo and view", [
            (f"{mod}+Z", "Undo"),
            (f"{mod}+Y  or  {mod}+Shift+Z", "Redo"),
            (f"{mod}+ + / −", "Zoom in / out"),
            (f"{mod}+0", "Fit the whole sheet"),
            ("Space + drag", "Slide the sheet around"),
            ("F11", "Full screen"),
            ("Esc", "Close a box or leave full screen"),
            ("F1", "Open this page"),
        ]),
    ]


class HelpScreen(Screen):
    """Shortcuts cheat sheet, opened from the Help button or F1."""

    def __init__(self, app):
        super().__init__(app)
        from .app import MOD_LABEL
        self.return_bar("Help", "Keyboard shortcuts and mouse actions")
        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=18)
        fam = app.base_font[0]
        for col in range(2):
            body.columnconfigure(col, weight=1, uniform="g")
        for n, (title, rows) in enumerate(_groups(MOD_LABEL)):
            edge = tk.Frame(body, bg=T.BORDER)
            edge.grid(row=n // 2, column=n % 2, sticky="new", padx=8, pady=8)
            card = tk.Frame(edge, bg=T.CARD)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(card, text=title, bg=T.CARD, fg=T.PETROL, anchor="w",
                     font=("Georgia", 13, "bold")).pack(fill="x", padx=16, pady=(12, 6))
            for keys, what in rows:
                r = tk.Frame(card, bg=T.CARD)
                r.pack(fill="x", padx=16, pady=2)
                tk.Label(r, text=keys, bg=T.SAND, fg=T.TEXT, padx=7, pady=1,
                         font=(fam, 9, "bold")).pack(side="left")
                tk.Label(r, text=what, bg=T.CARD, fg=T.MUTED, font=(fam, 10)).pack(
                    side="left", padx=10)
            tk.Frame(card, bg=T.CARD, height=8).pack()
        self.focus_set()
