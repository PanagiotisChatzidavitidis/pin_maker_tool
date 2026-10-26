"""Badge Pin Maker: the main window, where everything comes together.

How the app is used
  1. Pick a paper size and a pin size; the sheet is laid out automatically.
  2. Click a circle (or drop image files onto the sheet) to add photos, then
     position / zoom / rotate each photo under the pin shape.
  3. Export a PDF or print directly. Empty circles print blank.
  4. Projects are saved as .pinproj files in your projects folder, so you can
     reopen and edit them later.

Shortcuts:  Ctrl+N new   Ctrl+O browse   Ctrl+S save   Ctrl+Shift+S save as
            Ctrl+H projects home   Ctrl+E export PDF   Ctrl+P print
            Ctrl+Z undo   Ctrl+Y redo
            Delete  clear the circle under the mouse
(On macOS use Cmd instead of Ctrl.)

How this file is organised
  BadgeApp is one class, written in sections: start-up and screens, building the editor,
  settings and status bar, undo, slots (clicks, popup, adding photos), drawing the sheet,
  projects (save / load) and finally export / print. The maths lives in layout.py and
  imaging.py; the other windows live in their own files next to this one.
"""

import glob
import json
import os
import re
import tempfile
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageDraw, ImageTk

from ..constants import (BADGE_GAP, EXPORT_DPI, IMG_EXTS, LOW_PPI, MOD, MOD_LABEL,
                         PAGE_MARGIN, PAPER_SIZES, PIN_SIZES, PROJECT_EXT, SAFE_INSET)
from ..imaging import Art, load_source, render_art
from ..layout import compute_layout, fill_order, first_free
from ..pdf_export import build_pdf
from ..project_files import read_project_info
from ..settings import default_projects_dir, load_settings, save_settings
from ..system_actions import print_pdf
from . import theme as T
from .crop_dialog import CropDialog
from .dialogs import messagebox, set_titlebar, set_window_icon
from .dnd import DND_FILES, RootBase
from .home_screen import HomeScreen
from .widgets import StatTile, Toggle, make_card


class BadgeApp(RootBase):
    """The main window. It owns the project state (photo placements, undo history, settings)
    and switches between the start screen and the editor.
    """
    def __init__(self):
        """Load the saved settings, set up the theme and the variables, build both screens and
        show the start screen.
        """
        super().__init__()
        # ---- start-up: saved settings, window ----
        self.settings = load_settings()
        self._loading = True
        self.screen = "home"

        self.title("Badge Pin Maker")
        set_window_icon(self)
        geo = self.settings.get("size")
        if not (isinstance(geo, str) and re.fullmatch(r"\d{3,4}x\d{3,4}", geo)):
            geo = "1220x820"
        self.geometry(geo)
        self.minsize(1020, 720)

        # ---- theme and fonts (the theme must be applied before the styles are set up) ----
        s = self.settings
        theme = s.get("theme") if s.get("theme") in T.THEMES else "light"
        T.apply_theme(theme)                       # must come before setup_style
        self.base_font = T.setup_style(self)
        self.v_dark = tk.BooleanVar(value=(theme == "dark"))
        self.editor = tk.Frame(self, bg=T.BG)

        # ---- the project in memory ----
        self.slots = {}          # slot index -> Art
        self.layout = None
        self.geo = None          # (scale, ox, oy, params)
        self.hover = None
        self.selected = None
        self.popup = None
        self._photo_cache = {}
        self._after = None
        self._status_after = None
        self._undo, self._redo = [], []
        self.project_path = None
        self.dirty = False

        # ---- the settings boxes, restored from last time ----
        paper = s.get("paper") if s.get("paper") in PAPER_SIZES else "A4"
        pin = s.get("pin") if s.get("pin") in PIN_SIZES else "32 mm pin"
        self.v_paper = tk.StringVar(value=paper)
        self.v_pw = tk.StringVar(value=str(s.get("pw", "210")))
        self.v_ph = tk.StringVar(value=str(s.get("ph", "297")))
        self.v_pin = tk.StringVar(value=pin)
        self.v_d = tk.StringVar(value=str(s.get("d", "32")))
        self.v_guides = tk.BooleanVar(value=bool(s.get("guides", True)))

        # ---- build the screens and connect the events ----
        self._build_ui()
        self.home = HomeScreen(self)
        self._bind_shortcuts()
        for v in (self.v_paper, self.v_pw, self.v_ph, self.v_pin, self.v_d, self.v_guides):
            v.trace_add("write", self._on_setting)
        self.v_paper.trace_add("write", lambda *_: self._paper_changed())
        self.v_pin.trace_add("write", lambda *_: self._pin_changed())
        self._paper_changed()
        self._pin_changed()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._loading = False
        self.set_status()
        self._show("home")
        self.after_idle(lambda: set_titlebar(self))

    # ---- shortcuts (no menu bar; the buttons cover everything) -------------
    def _bind_shortcuts(self):
        """Keyboard shortcuts. The Command key is used on macOS, Control elsewhere. Some work
        on the start screen too, the rest only in the editor.
        """
        def handler(fn, home_ok=False):
            def run(e):
                if home_ok or self.screen == "editor":
                    fn()
                return "break"
            return run
        table = [("n", self.new_project, True), ("o", self.open_project, True),
                 ("s", self.save_project, False), ("Shift-S", self.save_project_as, False),
                 ("e", self.export_pdf, False), ("p", self.print_now, False),
                 ("z", self.undo, False), ("y", self.redo, False),
                 ("Shift-Z", self.redo, False), ("h", self.go_home, False)]
        for key, fn, home_ok in table:
            self.bind(f"<{MOD}-{key}>", handler(fn, home_ok))
            if len(key) == 1:
                self.bind(f"<{MOD}-{key.upper()}>", handler(fn, home_ok))
        self.bind("<Delete>", self.delete_selected)
        self.bind("<Escape>", lambda e: self.close_popup())

    # ---- screens / theme / projects folder ---------------------------------
    def _show(self, name):
        """Switch between the "home" and "editor" screens."""
        self.screen = name
        self.home.pack_forget()
        self.editor.pack_forget()
        if name == "home":
            self.title("Badge Pin Maker")
            self.home.refresh()
            self.home.pack(fill="both", expand=True)
        else:
            self._update_title()
            self.editor.pack(fill="both", expand=True)
            self.schedule_redraw()
            self.set_status()

    def go_home(self):
        """Back to the start screen (asking first if there are unsaved changes)."""
        if self.screen == "home" or not self._confirm_discard():
            return
        self.close_popup()
        self.slots.clear()
        self._undo.clear()
        self._redo.clear()
        self.project_path = None
        self.dirty = False
        self._show("home")

    def toggle_theme(self):
        """Called by the dark-mode switch: apply the theme, remember it and rebuild the
        screens.
        """
        name = "dark" if self.v_dark.get() else "light"
        T.apply_theme(name)
        self.settings["theme"] = name
        save_settings(self.settings)
        self.base_font = T.setup_style(self)
        self.after_idle(self._rebuild_ui)        # don't destroy the widget that fired us

    def _rebuild_ui(self):
        """Throw the old widgets away and build them again, so every widget picks up the new
        colours.
        """
        showing = self.screen
        self.close_popup()
        self.home.destroy()
        self.editor.destroy()
        self.editor = tk.Frame(self, bg=T.BG)
        self._build_ui()
        self._paper_changed()
        self._pin_changed()
        self.home = HomeScreen(self)
        self._show(showing)
        set_titlebar(self)

    def projects_dir(self):
        """The folder projects are kept in. It is created if needed, with the home folder as a
        fallback.
        """
        d = self.settings.get("projects_dir") or default_projects_dir()
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            d = os.path.expanduser("~")
        return d

    def set_projects_dir(self, d):
        """Remember a new projects folder."""
        self.settings["projects_dir"] = d
        save_settings(self.settings)

    def scan_projects(self):
        """Every project in the projects folder, newest first."""
        pattern = os.path.join(glob.escape(self.projects_dir()), "*" + PROJECT_EXT)
        items = [i for i in map(read_project_info, glob.glob(pattern)) if i]
        return sorted(items, key=lambda i: i["mtime"], reverse=True)

    def _unique_project_path(self, name):
        """A file path for a new project called ``name`` that doesn't overwrite another one
        ("My pins 2", ...). Characters Windows doesn't allow in file names are removed.
        """
        stem = re.sub(r'[\\/:*?"<>|]+', "", name).strip().rstrip(".") or "Untitled"
        base = self.projects_dir()
        path, n = os.path.join(base, stem + PROJECT_EXT), 2
        while os.path.exists(path):
            path = os.path.join(base, f"{stem} {n}{PROJECT_EXT}")
            n += 1
        return path

    def _suggest_name(self, base="My pins"):
        """'My pins', or 'My pins 2', 'My pins 3'... when that name is already taken."""
        n, name = 2, base
        while os.path.exists(os.path.join(self.projects_dir(), name + PROJECT_EXT)):
            name = f"{base} {n}"
            n += 1
        return name

    def open_path(self, path):
        """Open a project chosen from the list on the start screen."""
        if self._load_from(path):
            self._show("editor")

    # ---- UI --------------------------------------------------------------
    def _build_ui(self):
        """Build the editor: settings cards on the left, stat tiles and the sheet preview on
        the right, status bar along the bottom.
        """
        host = self.editor
        # status bar first so it claims the bottom edge
        status = tk.Frame(host, bg=T.CARD)
        status.pack(side="bottom", fill="x")
        tk.Frame(host, bg=T.BORDER, height=1).pack(side="bottom", fill="x")
        self.status_lbl = tk.Label(status, bg=T.CARD, fg=T.MUTED, anchor="w", padx=14, pady=6,
                                   font=(self.base_font[0], 9))
        self.status_lbl.pack(side="left")
        tk.Label(status, bg=T.CARD, fg=T.MUTED, padx=14, font=(self.base_font[0], 9),
                 text=f"{MOD_LABEL}+Z undo  ·  {MOD_LABEL}+S save  ·  {MOD_LABEL}+H projects"
                 ).pack(side="right")
        self.export_bar = ttk.Progressbar(status, length=160, mode="determinate",
                                          style="Teal.Horizontal.TProgressbar")

        left = ttk.Frame(host, padding=(18, 16, 8, 16))
        left.pack(side="left", fill="y")
        right = ttk.Frame(host, padding=(8, 16, 18, 16))
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Badge Pin Maker", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        nav = ttk.Frame(left)
        nav.pack(fill="x", pady=(0, 14))
        ttk.Button(nav, text="← Projects", style="Soft.TButton",
                   command=self.go_home).pack(side="left", expand=True, fill="x")
        ttk.Button(nav, text="Save", style="Soft.TButton",
                   command=self.save_project).pack(side="left", expand=True, fill="x", padx=(8, 0))

        f = make_card(left, "1 · Paper size")
        ttk.Combobox(f, textvariable=self.v_paper, values=list(PAPER_SIZES),
                     state="readonly", width=30).pack(fill="x")
        self.paper_custom = ttk.Frame(f, style="Card.TFrame")
        for lbl, var in (("W", self.v_pw), ("H", self.v_ph)):
            ttk.Label(self.paper_custom, text=lbl, style="Card.TLabel").pack(side="left")
            ttk.Entry(self.paper_custom, textvariable=var, width=6).pack(side="left", padx=4)
        ttk.Label(self.paper_custom, text="mm", style="Muted.TLabel").pack(side="left")

        f = make_card(left, "2 · Pin size")
        ttk.Combobox(f, textvariable=self.v_pin, values=list(PIN_SIZES),
                     state="readonly", width=30).pack(fill="x")
        self.pin_custom = ttk.Frame(f, style="Card.TFrame")
        ttk.Label(self.pin_custom, text="Diameter", style="Card.TLabel").pack(side="left")
        ttk.Entry(self.pin_custom, textvariable=self.v_d, width=6).pack(side="left", padx=4)
        ttk.Label(self.pin_custom, text="mm", style="Muted.TLabel").pack(side="left")
        self.pin_note = ttk.Label(f, style="Muted.TLabel")
        self.pin_note.pack(anchor="w", pady=(6, 0))

        f = make_card(left, "3 · Photos")
        tip = "Click a circle to add photos. Select several files to fill many circles at once."
        if DND_FILES:
            tip += " You can also drop image files onto the sheet."
        ttk.Label(f, style="Muted.TLabel", justify="left", wraplength=250,
                  text=tip).pack(anchor="w")
        ttk.Button(f, text="Clear all", style="Soft.TButton",
                   command=self.clear_all).pack(anchor="w", pady=(8, 0))

        f = make_card(left, "Display")
        for label, var, cmd in (("Safe-area guide", self.v_guides, None),
                                ("Dark mode", self.v_dark, self.toggle_theme)):
            r = ttk.Frame(f, style="Card.TFrame")
            r.pack(fill="x", pady=3)
            ttk.Label(r, text=label, style="Card.TLabel").pack(side="left")
            Toggle(r, var, command=cmd, bg=T.CARD).pack(side="right")
        a = ttk.Frame(left)
        a.pack(fill="x")
        ttk.Button(a, text="Export PDF", style="Accent.TButton",
                   command=self.export_pdf).pack(side="left", expand=True, fill="x")
        ttk.Button(a, text="Print", style="Accent.TButton",
                   command=self.print_now).pack(side="left", expand=True, fill="x", padx=(8, 0))

        # ---- right: stat tiles + sheet preview
        hdr = ttk.Frame(right)
        hdr.pack(fill="x")
        for c in range(4):
            hdr.columnconfigure(c, weight=1, uniform="tiles")
        self.t_sheet = StatTile(hdr, self.base_font[0])
        self.t_layout = StatTile(hdr, self.base_font[0])
        self.t_pins = StatTile(hdr, self.base_font[0])
        self.t_filled = StatTile(hdr, self.base_font[0])
        for c, tile in enumerate((self.t_sheet, self.t_layout, self.t_pins, self.t_filled)):
            tile.grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else 8, 0))
        self.fill_bar = ttk.Progressbar(right, mode="determinate",
                                        style="Teal.Horizontal.TProgressbar")
        self.fill_bar.pack(fill="x", pady=(10, 10))

        self.cv = tk.Canvas(right, bg=T.BLUSH, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.schedule_redraw())
        self.cv.bind("<Button-1>", self.on_click)
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<Leave>", lambda e: self._set_hover(None))
        if DND_FILES:
            self.cv.drop_target_register(DND_FILES)
            self.cv.dnd_bind("<<Drop>>", self.on_drop)

    # ---- status bar -----------------------------------------------------------
    def _idle_text(self):
        """The status bar's resting hint."""
        t = "Click a circle to add photos"
        if DND_FILES:
            t += "  ·  or drop image files onto the sheet"
        return t

    def set_status(self, text=None, hold=4000):
        """Show a message in the status bar. After ``hold`` milliseconds it goes back to the
        hint (0 keeps the message).
        """
        if self._status_after:
            self.after_cancel(self._status_after)
            self._status_after = None
        self.status_lbl.config(text=text or self._idle_text())
        if text and hold:
            self._status_after = self.after(hold, self._clear_status)

    def _clear_status(self):
        """Go back to the resting hint."""
        self._status_after = None
        self.set_status()

    # ---- settings helpers ---------------------------------------------------
    @staticmethod
    def _num(var, default):
        """Read a number from a text field. A comma counts as the decimal mark, and anything
        that isn't a number gives ``default``.
        """
        try:
            return float(str(var.get()).replace(",", "."))
        except (ValueError, tk.TclError):
            return default

    def _on_setting(self, *_):
        """A setting changed: redraw the sheet and mark the project as having unsaved changes.
        """
        self.schedule_redraw()
        if not self._loading:
            self._mark_dirty()

    def _paper_changed(self):
        """Show the width / height boxes only for "Custom..." paper. For a standard size, fill
        them in from the table.
        """
        dims = PAPER_SIZES.get(self.v_paper.get())
        if dims is None:
            self.paper_custom.pack(anchor="w", pady=(8, 0))
        else:
            self.paper_custom.pack_forget()
            self.v_pw.set(f"{dims[0]:g}")
            self.v_ph.set(f"{dims[1]:g}")

    def _pin_changed(self):
        """Show the diameter box only for "Custom..." pins. For a standard size, fill it in and
        show that size's caption.
        """
        data = PIN_SIZES.get(self.v_pin.get())
        if data is None:
            self.pin_custom.pack(anchor="w", pady=(8, 0))
            self.pin_note.config(text="Enter the cut diameter of your pin.")
        else:
            self.pin_custom.pack_forget()
            self.v_d.set(str(data[0]))
            self.pin_note.config(text=data[1])

    def _params(self):
        """Paper width / height and pin diameter in mm, with sensible minimums so a typo can't
        break the layout.
        """
        return dict(pw=max(10.0, self._num(self.v_pw, 210)),
                    ph=max(10.0, self._num(self.v_ph, 297)),
                    d=max(1.0, self._num(self.v_d, 32)))

    def compute(self):
        """Work out the layout for the current settings. Returns the parameters that were used.
        """
        p = self._params()
        self.layout = compute_layout(p["pw"], p["ph"], p["d"], PAGE_MARGIN, BADGE_GAP)
        return p

    def _store_settings(self):
        """Save the current choices and the window size, so the next start looks the same.
        """
        self.settings.update(
            paper=self.v_paper.get(), pw=self.v_pw.get(), ph=self.v_ph.get(),
            pin=self.v_pin.get(), d=self.v_d.get(), guides=bool(self.v_guides.get()),
            size=f"{self.winfo_width()}x{self.winfo_height()}")
        save_settings(self.settings)

    def _dir(self, key):
        """The folder last used for ``key`` ("photo_dir" or "export_dir") if it still exists,
        otherwise the home folder.
        """
        d = self.settings.get(key)
        return d if d and os.path.isdir(d) else os.path.expanduser("~")

    # ---- undo / dirty state -------------------------------------------------
    def _update_title(self):
        """Window title: the project name, with a * when there are unsaved changes."""
        if self.screen == "home":
            self.title("Badge Pin Maker")
            return
        name = os.path.basename(self.project_path) if self.project_path else "Untitled"
        self.title(f"{name}{'*' if self.dirty else ''} — Badge Pin Maker")

    def _mark_dirty(self):
        """Note that the project has unsaved changes."""
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _mark_clean(self):
        """Note that the project was just saved."""
        self.dirty = False
        self._update_title()

    def _snapshot(self):
        """A copy of every photo placement, for undo / redo."""
        return {i: a.copy() for i, a in self.slots.items()}

    def _push_undo(self):
        """Call this right before changing anything. It remembers the current state (up to 60
        steps) and marks the project as changed.
        """
        self._undo.append(self._snapshot())
        del self._undo[:-60]
        self._redo.clear()
        self._mark_dirty()

    def undo(self):
        """Go back one step."""
        if not self._undo:
            self.set_status("Nothing to undo")
            return
        self.close_popup()
        self._redo.append(self._snapshot())
        self.slots = self._undo.pop()
        self._mark_dirty()
        self.schedule_redraw()
        self.set_status("Undone")

    def redo(self):
        """Repeat a step that was undone."""
        if not self._redo:
            self.set_status("Nothing to redo")
            return
        self.close_popup()
        self._undo.append(self._snapshot())
        self.slots = self._redo.pop()
        self._mark_dirty()
        self.schedule_redraw()
        self.set_status("Redone")

    # ---- slots -------------------------------------------------------------
    def _n(self):
        """How many circles fit on the current sheet."""
        return len(self.layout["points"]) if self.layout else 0

    def _filled(self):
        """How many of those circles have a photo."""
        n = self._n()
        return sum(1 for i in self.slots if i < n)

    def hit(self, x, y):
        """Which circle is under the point (x, y) in canvas pixels? None if there isn't one.
        """
        if not self.layout or not self.geo:
            return None
        s, ox, oy, p = self.geo
        mx, my = (x - ox) / s, (y - oy) / s
        for i, (cx, cy) in enumerate(self.layout["points"]):
            if (mx - cx) ** 2 + (my - cy) ** 2 <= (p["d"] / 2) ** 2:
                return i
        return None

    def on_click(self, e):
        """Click on an empty circle: add photos. Click on a filled one: show the Clear / Modify
        box.
        """
        self.close_popup()
        idx = self.hit(e.x, e.y)
        if idx is None:
            return
        if idx in self.slots:
            self.show_popup(idx)
        else:
            self.choose_photos(idx)

    def delete_selected(self, event=None):
        """Delete key: clear the circle under the mouse (or the selected one), unless the user
        is typing in a text field.
        """
        try:
            if isinstance(self.focus_get(), (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox)):
                return
        except (KeyError, tk.TclError):
            pass
        idx = self.hover if self.hover in self.slots else self.selected
        if idx is not None and idx in self.slots:
            self.close_popup()
            self.clear_slot(idx)

    # ---- floating Clear / Modify buttons ------------------------------------
    def show_popup(self, idx):
        """Show the little Clear / Modify box next to circle ``idx``."""
        self.close_popup()
        self.selected = idx
        s, ox, oy, p = self.geo
        cx, cy = self.layout["points"][idx]
        x, y, w = ox + cx * s, oy + cy * s, p["d"] * s

        # highlight the selected circle
        self.cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2,
                            outline=T.SELECT_RING, width=3, tags="selected")

        frame = tk.Frame(self.cv, bg=T.POPUP_EDGE)
        inner = ttk.Frame(frame, style="Card.TFrame", padding=(8, 8))
        inner.pack(padx=1, pady=1)
        ttk.Button(inner, text="Clear", style="Soft.TButton",
                   command=lambda: self._popup_action(self.clear_slot, idx)).pack(side="left")
        ttk.Button(inner, text="Modify", style="Accent.TButton",
                   command=lambda: self._popup_action(self.modify_slot, idx)).pack(
            side="left", padx=(8, 0))
        frame.update_idletasks()
        pw, ph = frame.winfo_reqwidth(), frame.winfo_reqheight()
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        px = min(max(x - pw / 2, 6), max(6, cw - pw - 6))
        py = y - w / 2 - ph - 8                    # above the circle...
        if py < 6:
            py = y + w / 2 + 8                     # ...or below if there's no room
        py = min(py, max(6, ch - ph - 6))
        self.popup = frame
        self.cv.create_window(px, py, anchor="nw", window=frame, tags="popup")

    def close_popup(self):
        """Remove the popup and the selection ring, if there are any."""
        if self.popup is not None:
            self.cv.delete("popup")
            self.popup.destroy()
            self.popup = None
        self.cv.delete("selected")
        self.selected = None

    def _popup_action(self, fn, idx):
        """Close the popup, then run the action that was chosen."""
        self.close_popup()
        fn(idx)

    # ---- adding photos ------------------------------------------------------
    def choose_photos(self, start=None):
        """Open the file picker (several files allowed) and add what was chosen, starting at
        circle ``start``.
        """
        paths = filedialog.askopenfilenames(
            title="Choose photos", initialdir=self._dir("photo_dir"),
            filetypes=[("Images", " ".join(f"*{e}" for e in IMG_EXTS)), ("All files", "*.*")])
        if not paths:
            return
        paths = list(self.tk.splitlist(paths))
        self.settings["photo_dir"] = os.path.dirname(paths[0])
        self.add_photos(paths, start)

    def on_drop(self, event):
        """Image files were dropped onto the sheet: add them, starting at the circle they
        landed on.
        """
        paths = list(self.tk.splitlist(event.data))
        x = event.x_root - self.cv.winfo_rootx()
        y = event.y_root - self.cv.winfo_rooty()
        self.close_popup()
        self.add_photos(paths, self.hit(x, y))

    def add_photos(self, paths, start=None):
        """Crop each photo in turn and place it on the next free circles."""
        paths = [p for p in paths if p.lower().endswith(IMG_EXTS)]
        if not paths:
            self.set_status("No image files found")
            return
        p = self._params()
        n = self._n()
        free_now = n - sum(1 for k in self.slots if k < n)
        if free_now <= 0:
            messagebox.showinfo(
                "The sheet is full!",
                "Every circle is taken, I looked everywhere!\n\nClear a circle, or pick a "
                "different paper or pin size.")
            return
        if len(paths) > free_now:
            if not messagebox.askokcancel(
                    "Squeak! Too many photos",
                    f"You picked {len(paths)} photos but only {free_now} circle"
                    f"{' is' if free_now == 1 else 's are'} free.\n\n"
                    f"Is it okay if I only add the first {free_now}?",
                    ok="Okay, add them", cancel="Go back"):
                return
            paths = paths[:free_now]
        pushed = False
        placed = 0
        total = len(paths)
        # Crop the photos one at a time. The first goes on the circle that was clicked, the
        # following ones on the next free circles in reading order.
        for j, path in enumerate(paths, 1):
            occupied = {k for k in self.slots if k < n}
            free = n - len(occupied)
            if free <= 0:
                left = total - j + 1
                messagebox.showinfo(
                    "The sheet is full!",
                    f"Oh no, the sheet got full! {left} photo"
                    f"{'s' if left != 1 else ''} didn't fit.")
                break
            try:
                source = load_source(path)
            except Exception as ex:  # noqa: BLE001
                messagebox.showerror(
                    "Hmm, I can't read that",
                    f"I couldn't open this picture:\n{os.path.basename(path)}\n\n{ex}")
                continue
            title = f"Crop photo {j} of {total}" if total > 1 else "Crop photo"
            dlg = CropDialog(self, source, p["d"], max_copies=free, title=title,
                             batch=(j, total))
            self.wait_window(dlg)
            if dlg.stop:
                break
            if dlg.result is None:
                continue
            zoom, cx, cy, angle, copies = dlg.result
            if start is not None and start not in occupied:
                s, start = start, None
            else:
                s = first_free(n, occupied)
            # One undo step for the whole batch, no matter how many photos were added.
            if not pushed:
                self._push_undo()
                pushed = True
            for i in fill_order(n, occupied, s, copies):
                self.slots[i] = Art(source, zoom, cx, cy, angle)
            placed += copies
            self.redraw()
        if placed:
            self.set_status(f"Added {placed} pin{'s' if placed != 1 else ''}")

    def modify_slot(self, idx):
        """Re-open the crop window for a photo that is already on the sheet."""
        art = self.slots.get(idx)
        if art is None:
            return
        p = self._params()
        dlg = CropDialog(self, art.source, p["d"], max_copies=0, art=art, title="Modify crop")
        self.wait_window(dlg)
        if dlg.result is not None:
            self._push_undo()
            art.zoom, art.cx, art.cy, art.angle = dlg.result[:4]
            self.schedule_redraw()

    def clear_slot(self, idx):
        """Remove the photo from one circle (can be undone)."""
        if idx in self.slots:
            self._push_undo()
            del self.slots[idx]
            self.schedule_redraw()

    def clear_all(self):
        """Remove every photo (can be undone)."""
        if self._filled():
            self.close_popup()
            self._push_undo()
            self.slots.clear()
            self.schedule_redraw()
            self.set_status(f"Cleared all photos — {MOD_LABEL}+Z to undo")

    # ---- drawing -----------------------------------------------------------
    def schedule_redraw(self):
        """Redraw soon, not right now. Several quick changes in a row (like dragging a slider)
        then cause just one redraw.
        """
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(50, self.redraw)

    def _preview_photo(self, art, p, s):
        """The round preview picture for one pin. Cached, because making it is the slow part of
        drawing the sheet.
        """
        key = (art.key(), round(p["d"], 2), round(s, 3))
        ph = self._photo_cache.get(key)
        if ph is None:
            if len(self._photo_cache) > 400:
                self._photo_cache.clear()
            im = render_art(art, p["d"], s, small=True).convert("RGBA")
            big = Image.new("L", (im.size[0] * 3, im.size[1] * 3), 0)
            ImageDraw.Draw(big).ellipse((0, 0, big.size[0] - 1, big.size[1] - 1), fill=255)
            im.putalpha(big.resize(im.size, Image.LANCZOS))
            ph = ImageTk.PhotoImage(im)
            self._photo_cache[key] = ph
        return ph

    def redraw(self):
        """Draw the whole sheet preview: paper, empty circles, photos, guides, crop ticks and
        low-resolution warnings.
        """
        if self._after:
            self.after_cancel(self._after)
        self._after = None
        self.close_popup()
        p = self.compute()
        L = self.layout
        W, H = L["page_w"], L["page_h"]
        cv = self.cv
        cv.delete("all")
        self.hover = None
        cw, ch = max(cv.winfo_width(), 50), max(cv.winfo_height(), 50)
        # Scale the sheet to fit the window (keeping its shape, with a 20 px margin all
        # round). s = screen pixels per mm; (ox, oy) = where the paper's corner lands.
        s = min((cw - 40) / W, (ch - 40) / H)
        ox, oy = (cw - W * s) / 2, (ch - H * s) / 2
        self.geo = (s, ox, oy, p)

        # A soft three-layer shadow behind the paper.
        for off, col in ((6, T.SHADOW_A), (4, T.SHADOW), (2, T.SHADOW_C)):
            cv.create_rectangle(ox + off, oy + off, ox + W * s + off, oy + H * s + off,
                                fill=col, outline="")
        cv.create_rectangle(ox, oy, ox + W * s, oy + H * s, fill=T.PAPER, outline=T.PAPER_EDGE)

        w = p["d"] * s
        ins = SAFE_INSET * s
        tick, off = min(2.0, BADGE_GAP * 0.6) * s, 0.4 * s
        guides = self.v_guides.get()
        low = 0
        for i, (cx, cy) in enumerate(L["points"]):
            x, y = ox + cx * s, oy + cy * s
            art = self.slots.get(i)
            # An empty circle: a dashed outline with a plus sign in the middle.
            if art is None:
                cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2,
                               outline=T.EMPTY_LINE, dash=(4, 4), fill=T.EMPTY_FILL)
                a = w * 0.10
                cv.create_line(x - a, y, x + a, y, fill=T.EMPTY_PLUS, width=2, capstyle="round")
                cv.create_line(x, y - a, x, y + a, fill=T.EMPTY_PLUS, width=2, capstyle="round")
                continue
            # A filled circle: the photo, its outline, the safe-area ring, then four crop
            # ticks.
            cv.create_image(x, y, image=self._preview_photo(art, p, s))
            cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2, outline=T.PIN_EDGE)
            if guides and w / 2 - ins > 1:
                cv.create_oval(x - w / 2 + ins, y - w / 2 + ins, x + w / 2 - ins,
                               y + w / 2 - ins, outline=T.GUIDE, dash=(3, 3))
            for (x1, y1, x2, y2) in ((x, y - w / 2 - off, x, y - w / 2 - off - tick),
                                      (x, y + w / 2 + off, x, y + w / 2 + off + tick),
                                      (x - w / 2 - off, y, x - w / 2 - off - tick, y),
                                      (x + w / 2 + off, y, x + w / 2 + off + tick, y)):
                cv.create_line(x1, y1, x2, y2, fill=T.TICK)
            # A small orange "!" in the corner of photos that would print soft.
            if art.ppi(p["d"]) < LOW_PPI:
                low += 1
                r = max(6, w * 0.09)
                bx, by = x + w * 0.34, y - w * 0.34
                cv.create_oval(bx - r, by - r, bx + r, by + r, fill=T.WARN, outline="white")
                cv.create_text(bx, by, text="!", fill="white",
                               font=(self.base_font[0], max(7, int(r * 1.2)), "bold"))

        n, filled = self._n(), self._filled()
        self._update_stats(L, n, filled, low)
        if n == 0:
            cv.create_text(cw / 2, ch / 2, fill=T.ERR,
                           text="Pin doesn't fit on this paper — choose a smaller size.")

    def _update_stats(self, L, n, filled, low):
        """Refresh the four tiles above the preview and the progress bar."""
        W, H = L["page_w"], L["page_h"]
        short = self.v_paper.get().split(" (")[0].replace("Custom...", "Custom")
        self.t_sheet.set(short, f"{W:g} × {H:g} mm · {L['orientation'].capitalize()}")
        if L["method"] == "staggered":
            self.t_layout.set("Staggered", "Honeycomb packing")
        else:
            self.t_layout.set("Grid", "Straight rows")
        self.t_pins.set(str(n), f"pin{'s' if n != 1 else ''} per sheet")
        if low:
            self.t_filled.set(str(filled), f"of {n} filled · {low} low-res", warn=True)
        else:
            self.t_filled.set(str(filled), f"of {n} filled")
        self.fill_bar.config(maximum=max(n, 1), value=filled)

    def on_motion(self, e):
        """Highlight the circle under the mouse."""
        self._set_hover(self.hit(e.x, e.y))

    def _set_hover(self, idx):
        """Move the hover ring and the status hint to circle ``idx`` (None = no circle). Does
        nothing if it hasn't changed.
        """
        if idx == self.hover:
            return
        self.hover = idx
        self.cv.delete("hover")
        self.cv.config(cursor="hand2" if idx is not None else "")
        if idx is None or not self.geo:
            if self._status_after is None:
                self.set_status()
            return
        self.status_lbl.config(
            text="Click to modify or clear" if idx in self.slots
            else "Click to add photos")
        s, ox, oy, p = self.geo
        cx, cy = self.layout["points"][idx]
        x, y, w = ox + cx * s, oy + cy * s, p["d"] * s
        self.cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2,
                            outline=T.HOVER_RING, width=3, tags="hover")

    # ---- projects ----------------------------------------------------------
    def _confirm_discard(self):
        """True when it is fine to replace/close the current sheet."""
        if not (self.dirty and self.slots):
            return True
        ans = messagebox.askyesnocancel(
            "Wait a second!",
            "Psst... you have unsaved changes.\n\nShall I save this project first?",
            yes="Save it", no="Don't save", cancel="Stay here")
        if ans is None:
            return False
        if ans:
            return self.save_project()
        return True

    def new_project(self):
        """Ask for a name, create an empty project file with it and open the editor."""
        if not self._confirm_discard():
            return
        name = messagebox.askstring("New project", "Yay, a new project! What shall we call it?",
                                    initialvalue=self._suggest_name(), parent=self)
        if not name or not name.strip():
            return
        self.close_popup()
        self.slots.clear()
        self._undo.clear()
        self._redo.clear()
        self.project_path = None
        if self._save_to(self._unique_project_path(name)):
            self._show("editor")
            self.set_status("New project")

    def save_project(self):
        """Save. If the project has no file yet, ask for a name first."""
        if not self.project_path:
            return self.save_project_as()
        return self._save_to(self.project_path)

    def save_project_as(self):
        """Save under a name chosen in a file dialog."""
        initial = (os.path.basename(self.project_path) if self.project_path
                   else "pins" + PROJECT_EXT)
        path = filedialog.asksaveasfilename(
            defaultextension=PROJECT_EXT, filetypes=[("Pin project", f"*{PROJECT_EXT}")],
            initialdir=self.projects_dir(), initialfile=initial, title="Save project")
        if not path:
            return False
        return self._save_to(path)

    def _save_to(self, path):
        """Write the project to ``path`` as JSON: the settings, the list of photo files and
        where each pin's photo sits. The photos themselves are not copied, only their
        locations. Returns True on success.
        """
        base = os.path.dirname(os.path.abspath(path))
        photos, index = [], {}
        # List each distinct photo once; the slots below refer to a photo by its number in
        # this list.
        for a in self.slots.values():
            sp = a.source.path
            if sp not in index:
                try:
                    rel = os.path.relpath(sp, base)
                except ValueError:
                    rel = ""
                index[sp] = len(photos)
                photos.append({"path": sp, "rel": rel})
        data = {
            "app": "badge-pin-maker", "version": 1,
            "paper": self.v_paper.get(), "paper_w": self.v_pw.get(), "paper_h": self.v_ph.get(),
            "pin": self.v_pin.get(), "diameter": self.v_d.get(),
            "guides": bool(self.v_guides.get()),
            "photos": photos,
            "slots": [{"slot": i, "photo": index[a.source.path], "zoom": a.zoom,
                       "cx": a.cx, "cy": a.cy, "angle": a.angle}
                      for i, a in sorted(self.slots.items())],
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as ex:
            messagebox.showerror("Oh no!", f"I couldn't save your project:\n{ex}")
            return False
        self.project_path = path
        self._mark_clean()
        self.set_status(f"Saved {os.path.basename(path)}")
        return True

    def open_project(self):
        """Browse for a project file anywhere on disk."""
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open project", initialdir=self.projects_dir(),
            filetypes=[("Pin project", f"*{PROJECT_EXT}"), ("All files", "*.*")])
        if path and self._load_from(path):
            self._show("editor")

    def _load_from(self, path):
        """Read a project file and rebuild the sheet from it. Each photo is looked for at its
        saved path, then relative to the project file, then next to it. Photos that can't be
        found leave their circles empty and are reported to the user. Returns True on
        success.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("app") != "badge-pin-maker":
                raise ValueError("This is not a Badge Pin Maker project.")
        except (OSError, ValueError) as ex:
            messagebox.showerror("Oh no!", f"I couldn't open that project:\n{ex}")
            return False
        base = os.path.dirname(os.path.abspath(path))

        sources, missing = [], []
        for ph in data.get("photos", []):
            orig = ph.get("path") or ""
            rel = ph.get("rel") or ""
            src = None
            for cand in (orig, os.path.join(base, rel) if rel else "",
                         os.path.join(base, os.path.basename(orig)) if orig else ""):
                if cand and os.path.isfile(cand):
                    try:
                        src = load_source(cand)
                        break
                    except Exception:  # noqa: BLE001
                        pass
            if src is None:
                missing.append(os.path.basename(orig) or "?")
            sources.append(src)

        slots = {}
        for sl in data.get("slots", []):
            try:
                src = sources[int(sl["photo"])]
                if src is None:
                    continue
                slots[int(sl["slot"])] = Art(src, float(sl.get("zoom", 1.0)),
                                             float(sl.get("cx", 0.5)), float(sl.get("cy", 0.5)),
                                             float(sl.get("angle", 0.0)))
            except (KeyError, ValueError, TypeError, IndexError):
                continue

        # Setting the boxes below would count as "changes", so switch that tracking off
        # while loading.
        self._loading = True
        self.close_popup()
        paper = data.get("paper")
        paper = paper if paper in PAPER_SIZES else "Custom..."
        self.v_paper.set(paper)
        if PAPER_SIZES[paper] is None:
            self.v_pw.set(str(data.get("paper_w", "210")))
            self.v_ph.set(str(data.get("paper_h", "297")))
        pin = data.get("pin")
        pin = pin if pin in PIN_SIZES else "Custom..."
        self.v_pin.set(pin)
        if PIN_SIZES[pin] is None:
            self.v_d.set(str(data.get("diameter", "32")))
        self.v_guides.set(bool(data.get("guides", True)))
        self.slots = slots
        self._undo.clear()
        self._redo.clear()
        self.project_path = path
        self._loading = False
        self._mark_clean()
        self.redraw()
        self.set_status(f"Opened {os.path.basename(path)}")
        if missing:
            messagebox.showwarning(
                "Where did they go?",
                "I looked everywhere but couldn't find these photos, so their circles "
                "are empty:\n\n"
                + "\n".join(missing[:10]) + ("\n…" if len(missing) > 10 else ""))
        return True

    def on_close(self):
        """The window's close button and the Exit button: offer to save, remember the settings,
        then quit.
        """
        if not self._confirm_discard():
            return
        self._store_settings()
        self.destroy()

    # ---- output ------------------------------------------------------------
    def _prepare_export(self):
        """Check that there is something to export and warn about low-resolution photos.
        Returns (params, filled circles), or None if the user backed out.
        """
        p = self.compute()
        n = self._n()
        active = {i: a for i, a in self.slots.items() if i < n}
        if not active:
            messagebox.showwarning("Nothing to print yet",
                                   "The sheet is empty! Add at least one photo first.")
            return None
        low = sum(1 for a in active.values() if a.ppi(p["d"]) < LOW_PPI)
        if low and not messagebox.askyesno(
                "These look a bit fuzzy",
                f"{low} pin{'s use' if low != 1 else ' uses'} a photo that will print below "
                f"{LOW_PPI} dpi and may look soft.\n\nDo you want to continue anyway?",
                yes="Continue", no="Go back"):
            return None
        return p, active

    def _progress(self, done, total):
        """Update the export progress bar."""
        self.export_bar.config(maximum=max(total, 1), value=done)
        self.update_idletasks()

    def _write_pdf(self, path, p, active):
        """Build the PDF while showing a progress bar and a busy cursor. Returns True on
        success.
        """
        self.set_status("Building PDF…", hold=0)
        self.export_bar.config(value=0)
        self.export_bar.pack(side="right", padx=(0, 8))
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            build_pdf(path, self.layout, p["d"], active, guides=self.v_guides.get(),
                      dpi=EXPORT_DPI, progress=self._progress)
            return True
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror("Oh no!", f"Something went wrong while making the PDF:\n{ex}")
            return False
        finally:
            self.export_bar.pack_forget()
            self.config(cursor="")
            self.set_status()

    def export_pdf(self):
        """Ask where to save, then export the sheet as a PDF."""
        prep = self._prepare_export()
        if not prep:
            return
        stem = os.path.splitext(os.path.basename(self.project_path))[0] if self.project_path else "pins"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialdir=self._dir("export_dir"), initialfile=f"{stem}.pdf",
            title="Export PDF")
        if not path:
            return
        self.settings["export_dir"] = os.path.dirname(path)
        if self._write_pdf(path, *prep):
            self.set_status(f"Exported {os.path.basename(path)}")

    def print_now(self):
        """Build a temporary PDF and send it to the printer."""
        prep = self._prepare_export()
        if not prep:
            return
        tmp = os.path.join(tempfile.gettempdir(), "pin_sheet.pdf")
        if not self._write_pdf(tmp, *prep):
            return
        try:
            print_pdf(tmp)
            self.set_status("Print job started")
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror("Oh no!", f"I couldn't start the print job:\n{ex}")


def main():
    """Open the app window and run until it is closed."""
    BadgeApp().mainloop()
