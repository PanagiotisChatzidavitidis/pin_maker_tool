"""Colours and ttk styling, with a light and a dark look.

The colour names (BG, TEAL, ...) are plain variables in this module. apply_theme() replaces
their values with the chosen theme, and the rest of the UI reads them as T.BG, T.TEAL, ...
at the moment it draws something. After a theme switch the screens are rebuilt so every
widget picks up the new colours.
"""

import platform
import tkinter as tk
from tkinter import ttk


THEMES = {
    # lo-fi cosy daylight
    "light": dict(
        PETROL="#005F73", TEAL="#008080", TEAL_HOVER="#1A9696", TEAL_DARK="#006767",
        SAND="#EACDB2", SAND_HOVER="#E2C3A4", SAND_PRESS="#D6B391",
        ORCHID="#BB76A3", PLUM="#7A5677", WARN="#C9772B",
        # sheet highlights: hovered circle, selected circle, border of the Clear/Modify box
        HOVER_RING="#BB76A3", SELECT_RING="#7A5677", POPUP_EDGE="#7A5677",
        BG="#F6EADD", CARD="#FCF6EE", BORDER="#E3C9AE", TEXT="#2C4651", MUTED="#80787A",
        BLUSH="#E4D1D9", SHADOW_A="#D8C3CD", SHADOW="#CDB2C0", SHADOW_C="#BFA0B2",
        FIELD="white", HOVER="#F3E4D2",
        # sheet preview
        PAPER="white", PAPER_EDGE="#D9C6CF", EMPTY_FILL="#FDF8FB", EMPTY_LINE="#D7B0CA",
        EMPTY_PLUS="#CF9BBB", PIN_EDGE="#6B5666", TICK="#2C4651", GUIDE="#FFFFFF",
        ERR="#E06666",
        # crop window: colour the image fades to outside the pin, and the pin outline
        CROP_DIM=(243, 231, 218), CROP_LINE="#2C4651", CROP_HALO="#FFFFFF"),
    # lo-fi night: deep petrol-slate surfaces, warm sand text, brighter accents
    "dark": dict(
        PETROL="#8FD3D6", TEAL="#2B9A9A", TEAL_HOVER="#3AB0B0", TEAL_DARK="#217878",
        SAND="#33494F", SAND_HOVER="#3A535B", SAND_PRESS="#3F5A62",
        ORCHID="#D08BBB", PLUM="#B98AB5", WARN="#E8A15A",
        HOVER_RING="#3AB0B0", SELECT_RING="#8FD3D6", POPUP_EDGE="#3AB0B0",
        BG="#182329", CARD="#223139", BORDER="#33474F", TEXT="#EADFD2", MUTED="#93A3A6",
        BLUSH="#121B20", SHADOW_A="#161F25", SHADOW="#10181D", SHADOW_C="#0B1216",
        FIELD="#2C3F48", HOVER="#2B3D46",
        # sheet preview
        PAPER="#223139", PAPER_EDGE="#3F5A62", EMPTY_FILL="#2B3E47", EMPTY_LINE="#587480",
        EMPTY_PLUS="#8FB0B8", PIN_EDGE="#EADFD2", TICK="#C9BBAA", GUIDE="#FFE2C4",
        ERR="#E8A15A",
        CROP_DIM=(18, 27, 32), CROP_LINE="#FFFFFF", CROP_HALO="#121B20"),
}


def apply_theme(name):
    """Switch the colour names in this module to the "light" or "dark" set. Unknown names fall
    back to light.
    """
    name = name if name in THEMES else "light"
    globals().update(THEMES[name])
    globals()["THEME_NAME"] = name


apply_theme("light")


def setup_style(root):
    """Configure every ttk style (buttons, labels, fields, scrollbars...) from the current
    colours. Returns the base font as (family, size).
    """
    root.configure(bg=BG)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    base = ("Segoe UI", 10) if platform.system() == "Windows" else (
        ("Helvetica Neue", 11) if platform.system() == "Darwin" else ("DejaVu Sans", 10))
    st.configure(".", background=BG, foreground=TEXT, font=base)
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=CARD)
    st.configure("Card.TLabel", background=CARD, foreground=TEXT)
    st.configure("Muted.TLabel", background=CARD, foreground=MUTED)
    st.configure("CardTitle.TLabel", background=CARD, foreground=PETROL,
                 font=("Georgia", 12, "bold"))
    st.configure("Title.TLabel", background=BG, foreground=PETROL, font=("Georgia", 20, "bold"))
    st.configure("Hint.TLabel", background=BG, foreground=MUTED)
    st.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, focuscolor=CARD)
    st.map("Card.TCheckbutton", background=[("active", CARD)],
           indicatorcolor=[("selected", TEAL)])
    st.configure("Accent.TButton", background=TEAL, foreground="white", padding=(16, 9),
                 borderwidth=0, focusthickness=0, focuscolor=TEAL, font=(base[0], 10, "bold"))
    st.map("Accent.TButton", background=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)])
    st.configure("Soft.TButton", background=SAND, foreground=TEXT, padding=(12, 7),
                 borderwidth=0, focusthickness=0, focuscolor=SAND)
    st.map("Soft.TButton", background=[("pressed", SAND_PRESS), ("active", SAND_HOVER)])
    st.configure("Hero.TLabel", background=CARD, foreground=PETROL, font=("Georgia", 19, "bold"))
    st.configure("Page.TLabel", background=BG, foreground=PETROL, font=("Georgia", 24, "bold"))
    st.configure("Section.TLabel", background=CARD, foreground=MUTED, font=(base[0], 8, "bold"))
    st.configure("Hero.TButton", background=TEAL, foreground="white", padding=(16, 13),
                 borderwidth=0, focusthickness=0, focuscolor=TEAL, font=(base[0], 11, "bold"))
    st.map("Hero.TButton", background=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)])
    st.configure("Ghost.TButton", background=CARD, foreground=TEXT, padding=(12, 9),
                 borderwidth=1, bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD,
                 focusthickness=0, focuscolor=CARD)
    st.map("Ghost.TButton", background=[("pressed", HOVER), ("active", HOVER)],
           bordercolor=[("active", TEAL), ("pressed", TEAL)],
           lightcolor=[("active", HOVER), ("pressed", HOVER)],
           darkcolor=[("active", HOVER), ("pressed", HOVER)])
    st.configure("Horizontal.TScale", background=TEAL, troughcolor=BORDER, bordercolor=BORDER,
                 lightcolor=TEAL, darkcolor=TEAL)
    st.map("Horizontal.TScale",
           background=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)],
           lightcolor=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)],
           darkcolor=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)])
    st.configure("Teal.Horizontal.TProgressbar", troughcolor=BORDER, background=TEAL,
                 bordercolor=BG, lightcolor=TEAL, darkcolor=TEAL, thickness=6)
    # clam draws bevelled borders with light/dark edge colours (white/grey by default,
    # which glows in dark mode), so every field gets a themed edge and a teal focus ring.
    edge = dict(bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    focus = dict(bordercolor=[("focus", TEAL), ("active", TEAL)],
                 lightcolor=[("focus", TEAL)], darkcolor=[("focus", TEAL)])
    sel = dict(selectbackground=TEAL, selectforeground="white")
    st.configure("TCombobox", fieldbackground=FIELD, background=SAND, arrowcolor=TEAL,
                 padding=4, foreground=TEXT, **edge, **sel)
    st.map("TCombobox", fieldbackground=[("readonly", FIELD)],
           foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)],
           background=[("pressed", SAND_PRESS), ("active", SAND_HOVER)], **focus)
    st.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, padding=3,
                 insertcolor=TEXT, **edge, **sel)
    st.map("TEntry", **focus)
    st.configure("TSpinbox", fieldbackground=FIELD, foreground=TEXT, background=SAND,
                 arrowcolor=TEAL, insertcolor=TEXT, **edge, **sel)
    st.map("TSpinbox", background=[("pressed", SAND_PRESS), ("active", SAND_HOVER)], **focus)
    st.configure("Vertical.TScrollbar", background=SAND, troughcolor=BG, bordercolor=BG,
                 lightcolor=SAND, darkcolor=SAND, arrowcolor=TEXT)
    st.map("Vertical.TScrollbar", background=[("pressed", SAND_PRESS), ("active", SAND_HOVER)])
    root.option_add("*TCombobox*Listbox.selectBackground", TEAL)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    return base
