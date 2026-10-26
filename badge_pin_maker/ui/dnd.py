"""Optional drag and drop of image files onto the sheet.

It needs the "tkinterdnd2" package. Without it the app uses a normal window and everything
else still works.
"""

import tkinter as tk


def _detect_dnd():
    """Use tkinterdnd2 for drag and drop when it is installed and working."""
    try:
        from tkinterdnd2 import TkinterDnD, DND_FILES
        probe = TkinterDnD.Tk()
        probe.withdraw()
        probe.destroy()
        return TkinterDnD.Tk, DND_FILES
    except Exception:  # noqa: BLE001
        return tk.Tk, None


RootBase, DND_FILES = _detect_dnd()
