"""The start screen: a sidebar with the main actions and the list of saved projects."""

import os
import time
import tkinter as tk
from tkinter import filedialog, ttk

from ..system_actions import reveal_folder
from . import theme as T
from .dialogs import messagebox
from .icons import load_logo, make_icon
from .widgets import Toggle


class HomeScreen(tk.Frame):
    """Start screen: sidebar (brand, actions, options, exit) + projects list."""
    ICON = 56
    SIDE_W = 320

    def __init__(self, app):
        """Build the sidebar (brand, actions, options) and the empty, scrollable project list.
        """
        super().__init__(app, bg=T.BG)
        self.app = app
        self._icons = {}
        self._sb_on = False
        fam = app.base_font[0]

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
        ttk.Label(names, text="Badge Pin", style="Hero.TLabel").pack(anchor="w")
        ttk.Label(names, text="Maker", style="Hero.TLabel").pack(anchor="w")
        ttk.Label(pad, text="Photo sheets for your pin badges",
                  style="Muted.TLabel").pack(anchor="w", pady=(14, 22))

        ttk.Button(pad, text="+  New project", style="Hero.TButton",
                   command=app.new_project).pack(fill="x")
        ttk.Button(pad, text="Browse for a project…", style="Ghost.TButton",
                   command=app.open_project).pack(fill="x", pady=(10, 0))

        ttk.Label(pad, text="OPTIONS", style="Section.TLabel").pack(anchor="w", pady=(34, 10))
        row = ttk.Frame(pad, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="Dark mode", style="Card.TLabel").pack(side="left")
        Toggle(row, app.v_dark, command=app.toggle_theme, bg=T.CARD).pack(side="right")

        ttk.Label(pad, text="Projects folder", style="Card.TLabel").pack(anchor="w", pady=(18, 0))
        self.folder_lbl = ttk.Label(pad, style="Muted.TLabel", justify="left",
                                    wraplength=self.SIDE_W - 60)
        self.folder_lbl.pack(anchor="w", pady=(2, 0))
        ttk.Button(pad, text="Change folder…", style="Ghost.TButton",
                   command=self.change_folder).pack(anchor="w", pady=(10, 0))

        ttk.Button(pad, text="Exit", style="Ghost.TButton",
                   command=app.on_close).pack(side="bottom", fill="x")

        # ---- main area -----------------------------------------------------
        main = ttk.Frame(self, padding=(34, 28, 34, 28))
        main.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(main)
        top.pack(fill="x")
        ttk.Label(top, text="Your projects", style="Page.TLabel").pack(side="left")
        ttk.Button(top, text="Open folder", style="Ghost.TButton",
                   command=lambda: reveal_folder(app.projects_dir())).pack(side="right")
        self.count_lbl = ttk.Label(main, style="Hint.TLabel")
        self.count_lbl.pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(main)
        body.pack(fill="both", expand=True, pady=(16, 0))
        self.cv = tk.Canvas(body, bg=T.BG, highlightthickness=0)
        self.sb = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=self._on_scroll)
        self.cv.pack(side="left", fill="both", expand=True)
        self.list = tk.Frame(self.cv, bg=T.BG)
        self._win = self.cv.create_window(0, 0, anchor="nw", window=self.list)
        self.list.bind("<Configure>",
                       lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        self._fam = fam
        # bind_all (without add=) so a rebuilt HomeScreen replaces the old handler
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._on_wheel)

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
            self.cv.yview_scroll(step, "units")
        except tk.TclError:
            pass

    def refresh(self):
        """Look at the projects folder again and redraw the list (or the "No projects yet"
        message).
        """
        self.folder_lbl.config(text=self.app.projects_dir())
        for w in self.list.winfo_children():
            w.destroy()
        items = self.app.scan_projects()
        self.count_lbl.config(text=f"{len(items)} project{'s' if len(items) != 1 else ''}")
        if not items:
            box = tk.Frame(self.list, bg=T.BG)
            box.pack(fill="x", pady=(70, 0))
            self._empty_icon = load_logo(96)
            tk.Label(box, image=self._empty_icon, bg=T.BG).pack()
            tk.Label(box, text="No projects yet", bg=T.BG, fg=T.PETROL,
                     font=("Georgia", 18, "bold")).pack(pady=(16, 4))
            tk.Label(box, text="Create your first sheet and it will show up here.",
                     bg=T.BG, fg=T.MUTED, font=(self._fam, 10)).pack()
            ttk.Button(box, text="+  New project", style="Hero.TButton",
                       command=self.app.new_project).pack(pady=(18, 0))
            self.cv.yview_moveto(0)
            return
        for info in items:
            self._row(info)
        self.cv.yview_moveto(0)

    def _row(self, info):
        """One project card: thumbnail, name, details, date and a Delete link. Clicking the
        card opens the project.
        """
        fam = self._fam
        outer = tk.Frame(self.list, bg=T.BORDER)          # 1px border that lights up on hover
        outer.pack(fill="x", pady=(0, 10))
        card = tk.Frame(outer, bg=T.CARD)
        card.pack(fill="x", padx=1, pady=1)

        key = (info["path"], info["mtime"])
        if key not in self._icons:
            self._icons[key] = make_icon(info["art"], self.ICON)
        icon = tk.Label(card, image=self._icons[key], bg=T.CARD)
        icon.pack(side="left", padx=(16, 14), pady=12)

        right = tk.Frame(card, bg=T.CARD)
        right.pack(side="right", padx=16)
        when = time.strftime("%d %b %Y", time.localtime(info["mtime"]))
        date = tk.Label(right, text=f"Edited {when}", bg=T.CARD, fg=T.MUTED,
                        font=(fam, 9), anchor="e")
        date.pack(anchor="e")
        dele = tk.Label(right, text="Delete", bg=T.CARD, fg=T.MUTED, cursor="hand2",
                        font=(fam, 9, "underline"))
        dele.pack(anchor="e", pady=(4, 0))
        dele.bind("<Button-1>", lambda e, i=info: self.delete(i))
        dele.bind("<Enter>", lambda e: dele.config(fg=T.WARN))
        dele.bind("<Leave>", lambda e: dele.config(fg=T.MUTED))

        text = tk.Frame(card, bg=T.CARD)
        text.pack(side="left", fill="x", expand=True)
        name = tk.Label(text, text=info["name"], bg=T.CARD, fg=T.PETROL, anchor="w",
                        font=("Georgia", 14, "bold"))
        name.pack(fill="x")
        n = info["pins"]
        sub = tk.Label(text, bg=T.CARD, fg=T.MUTED, anchor="w", font=(fam, 9),
                       text=f"{info['paper']}  ·  {info['pin']}  ·  "
                            f"{n} pin{'s' if n != 1 else ''}")
        sub.pack(fill="x", pady=(2, 0))

        widgets = (card, icon, text, name, sub, right, date, dele)

        def paint(on):
            outer.config(bg=T.TEAL if on else T.BORDER)
            for w in widgets:
                w.config(bg=T.HOVER if on else T.CARD)

        def leave(_e):
            try:
                x, y = outer.winfo_pointerxy()
                under = outer.winfo_containing(x, y)
            except (tk.TclError, KeyError):
                under = None
            if under is None or not (under == outer or str(under).startswith(str(outer) + ".")):
                paint(False)

        for w in widgets:
            w.bind("<Enter>", lambda e: paint(True), add="+")
            w.bind("<Leave>", leave, add="+")
            if w is not dele:
                w.config(cursor="hand2")
                w.bind("<Button-1>", lambda e, p=info["path"]: self.app.open_path(p))

    def delete(self, info):
        """Ask first, then remove the project file. The photos are never touched."""
        if not messagebox.askyesno(
                "Delete project?",
                f"Do you really want me to delete “{info['name']}”?\n\n"
                "Only the project file goes away. Your photos stay safe, I promise!",
                icon="warning", parent=self.app, yes="Delete it", no="Keep it"):
            return
        try:
            os.remove(info["path"])
        except OSError as ex:
            messagebox.showerror("Oh no!", f"I couldn't delete that project:\n{ex}")
        self.refresh()

    def change_folder(self):
        """Let the user pick a different projects folder."""
        d = filedialog.askdirectory(title="Choose projects folder",
                                    initialdir=self.app.projects_dir())
        if d:
            self.app.set_projects_dir(d)
            self.refresh()
