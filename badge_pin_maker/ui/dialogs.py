"""Message boxes in the app's own style.

The system message boxes always look light, even in dark mode, so the app uses these
instead. "messagebox" mirrors the function names of tkinter.messagebox (askyesno, showinfo,
...), so the calls read the same way.
"""

import platform
import tkinter as tk
from tkinter import ttk

from ..paths import asset_path
from . import theme as T
from .icons import load_logo
from .widgets import round_rect


def set_window_icon(win):
    """Use the app icon in a window's title bar instead of the default Tk feather."""
    try:
        if platform.system() == "Windows":
            win.iconbitmap(asset_path("icon.ico"))
    except tk.TclError:
        pass


def set_titlebar(win):
    """Match the Windows title bar to the current theme (does nothing elsewhere)."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1 if T.IS_DARK else 0)
        for attr in (20, 19):    # 20 = Windows 11 / 10 20H1+, 19 = older Windows 10
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:  # noqa: BLE001
        pass


class ThemedDialog(tk.Toplevel):
    """Small modal window: icon + message (+ optional text field) + buttons.
    result = the value of the button pressed (or the typed text for a text dialog)."""
    def __init__(self, parent, title, message, kind="info",
                 buttons=(("OK", True, "Accent.TButton"),), default=True, cancel=None,
                 entry=None):
        """Build the dialog off-screen, centre it over its parent, then show it modally."""
        super().__init__(parent)
        self.withdraw()                      # build off-screen, then show centred
        self.configure(bg=T.BG)
        self.title(title)
        self.resizable(False, False)
        set_window_icon(self)
        try:
            if parent is not None and parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass
        self.result = cancel
        self._default, self._cancel = default, cancel
        self._var = tk.StringVar(value=entry) if entry is not None else None

        body = ttk.Frame(self, style="Card.TFrame", padding=(20, 22, 24, 16))
        body.pack(fill="both", expand=True)

        # the hamster (does a little hop when the window opens)
        self._logo = load_logo(52)
        self._mascot = tk.Canvas(body, width=60, height=66, bg=T.CARD, highlightthickness=0)
        self._mimg = self._mascot.create_image(30, 36, image=self._logo)
        self._mascot.pack(side="left", anchor="s")
        self._anim = None

        # speech bubble: rounded box with a small tail pointing at the hamster
        TAIL, TEXT_W, PX, PY = 12, 330, 16, 12
        bub = tk.Canvas(body, bg=T.CARD, highlightthickness=0)
        txt = bub.create_text(0, 0, text=message, anchor="nw", width=TEXT_W, fill=T.TEXT,
                              font="TkDefaultFont", justify="left")
        bx0, by0, bx1, by1 = bub.bbox(txt)
        text_h = by1 - by0
        inner_w = max(bx1 - bx0, TEXT_W if self._var is not None else 0)
        bub.move(txt, TAIL + 2 + PX - bx0, PY + 1 - by0)
        box_h = text_h + 2 * PY + (40 if self._var is not None else 0)
        W, H = TAIL + inner_w + 2 * PX + 3, box_h + 2
        bub.config(width=W, height=H)
        if self._var is not None:
            ent = ttk.Entry(bub, textvariable=self._var)
            bub.create_window(TAIL + 2 + PX, PY + 1 + text_h + 12, anchor="nw",
                              window=ent, width=inner_w)
            ent.focus_set()
            ent.selection_range(0, "end")
        round_rect(bub, TAIL + 1, 1, W - 2, H - 2, 14, fill=T.HOVER, outline=T.TEAL, width=2,
                   tags="bubble")
        cy = min(max(20, H - 30), H - 16)                       # tail sits level with the hamster
        bub.create_polygon(TAIL + 1, cy - 9, 1, cy, TAIL + 1, cy + 9, fill=T.HOVER,
                           outline=T.TEAL, width=2, tags="bubble")
        bub.create_line(TAIL + 1, cy - 7, TAIL + 1, cy + 7, fill=T.HOVER, width=4, tags="bubble")
        bub.tag_lower("bubble")                                 # shapes behind the text
        bub.pack(side="left", anchor="s", padx=(2, 0))

        tk.Frame(self, bg=T.BORDER, height=1).pack(fill="x")
        foot = ttk.Frame(self, padding=(16, 12))
        foot.pack(fill="x")
        for label, value, style in reversed(buttons):   # buttons are given left to right
            ttk.Button(foot, text=label, style=style,
                       command=lambda v=value: self._done(v)).pack(side="right", padx=(8, 0))

        self.bind("<Return>", lambda e: self._done(self._default))
        self.bind("<Escape>", lambda e: self._done(self._cancel))
        self.protocol("WM_DELETE_WINDOW", lambda: self._done(self._cancel))

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
        self._bounce()

    def _bounce(self, step=0):
        """The mascot's little hop when the dialog opens (one animation frame per call)."""
        hops = (0, -9, 0, -5, 0, -2, 0)
        if step >= len(hops):
            self._anim = None
            return
        try:
            self._mascot.coords(self._mimg, 30, 36 + hops[step])
        except tk.TclError:
            return
        self._anim = self.after(70, self._bounce, step + 1)

    def _done(self, value):
        """Remember which button was pressed (or the typed text) and close the dialog."""
        if self._anim is not None:
            self.after_cancel(self._anim)
            self._anim = None
        if value is True and self._var is not None:
            value = self._var.get()
        self.result = value
        self.destroy()


class _ThemedMessageBox:
    """Drop-in for tkinter.messagebox (plus askstring) that follows the theme."""
    OK = ("Okay!", True, "Accent.TButton")
    CANCEL = ("Cancel", None, "Soft.TButton")

    def _run(self, parent, title, message, **kw):
        """Open a themed dialog over ``parent`` and wait for it. A modal window that was open
        before (like the crop window) gets its grab back afterwards.
        """
        root = parent or getattr(tk, "_default_root", None)
        if root is None:
            return None
        try:
            prev = root.grab_current()       # e.g. the crop window, so we can give it back
        except tk.TclError:
            prev = None
        dlg = ThemedDialog(root, title, message, **kw)
        dlg.wait_window()
        if prev is not None:
            try:
                prev.grab_set()
            except tk.TclError:
                pass
        return dlg.result

    def showinfo(self, title, message, parent=None, **kw):
        """Tell the user something; one Okay button."""
        self._run(parent, title, message, kind="info")

    def showwarning(self, title, message, parent=None, **kw):
        """Same as showinfo, for warnings."""
        self._run(parent, title, message, kind="warning")

    def showerror(self, title, message, parent=None, **kw):
        """Same as showinfo, for errors."""
        self._run(parent, title, message, kind="error")

    # yes= / no= / ok= / cancel= let a call word its buttons ("Save" / "Don't save"...)
    def askyesno(self, title, message, parent=None, icon="question",
                 yes="Yes", no="No", **kw):
        """True for the yes button, False otherwise."""
        return bool(self._run(
            parent, title, message, kind="warning" if icon == "warning" else "question",
            buttons=((no, False, "Soft.TButton"), (yes, True, "Accent.TButton")),
            default=True, cancel=False))

    def askokcancel(self, title, message, parent=None, ok="Okay!", cancel="Cancel", **kw):
        """True for the ok button, False otherwise."""
        return bool(self._run(
            parent, title, message, kind="question",
            buttons=((cancel, False, "Soft.TButton"), (ok, True, "Accent.TButton")),
            default=True, cancel=False))

    def askyesnocancel(self, title, message, parent=None, yes="Yes", no="No",
                       cancel="Cancel", **kw):
        """True (yes), False (no) or None (cancel)."""
        return self._run(
            parent, title, message, kind="question",
            buttons=((cancel, None, "Soft.TButton"), (no, False, "Soft.TButton"),
                     (yes, True, "Accent.TButton")), default=True, cancel=None)

    def askstring(self, title, prompt, initialvalue="", parent=None, **kw):
        """Ask for a line of text. Returns it, or None if the user cancels."""
        return self._run(parent, title, prompt, kind="question",
                         buttons=(self.CANCEL, self.OK), default=True, cancel=None,
                         entry=initialvalue)


messagebox = _ThemedMessageBox()
