"""Colours and ttk styling, with several light and dark themes.

The colour names (BG, TEAL, ...) are plain variables in this module. apply_theme() replaces
their values with the chosen theme, and the rest of the UI reads them as T.BG, T.TEAL, ...
at the moment it draws something. After a theme switch the screens are rebuilt so every
widget picks up the new colours.

A theme is a full set of colour names. The new themes are written as eight base colours in
_PALETTES; _build() works out the rest (hover shades, sheet shadows, ...) from them. The
original look is kept as "Classic".
"""

import platform
import tkinter as tk
from tkinter import ttk


DEFAULT_LIGHT = "oat_milk"
DEFAULT_DARK = "graphite_mint"


# ---- small colour helpers ------------------------------------------------------------
def _rgb(h):
    """"#RRGGBB" -> (r, g, b)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    """(r, g, b) -> "#RRGGBB" (values are rounded and kept within 0-255)."""
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def _mix(a, b, t):
    """The colour ``t`` (0 to 1) of the way from ``a`` to ``b``."""
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def _lum(h):
    """Relative luminance of a colour (0 black ... 1 white), as used for contrast ratios."""
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    """Contrast ratio between two colours (1 = identical, 21 = black on white)."""
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


WHITE, BLACK = "#FFFFFF", "#000000"


def _build(mode, bg, card, border, text, muted, pri, soft, acc):
    """Work out a complete theme from its eight base colours.

    bg / card / border / text / muted are the surfaces and text, pri is the main colour
    (buttons, sliders, headings), soft is the quiet button colour and acc is the accent
    (empty-circle outlines, the second colour).
    """
    dark = mode == "dark"
    # text on top of the main colour: white unless that would be hard to read
    ink = bg if dark else text
    on_pri = WHITE if _contrast(WHITE, pri) >= 3.0 else ink
    blush = _mix(bg, BLACK, 0.35) if dark else _mix(bg, border, 0.6)   # area behind the sheet
    paper = card if dark else WHITE
    return dict(
        MODE=mode,
        BG=bg, CARD=card, BORDER=border, TEXT=text, MUTED=muted,
        TEAL=pri, TEAL_HOVER=_mix(pri, WHITE, 0.14), TEAL_DARK=_mix(pri, BLACK, 0.2),
        ON_PRIMARY=on_pri,
        PETROL=_mix(pri, WHITE, 0.15) if dark else _mix(pri, text, 0.3),
        SAND=soft, SAND_HOVER=_mix(soft, text, 0.06), SAND_PRESS=_mix(soft, text, 0.14),
        ORCHID=acc, PLUM=_mix(acc, text, 0.35),
        WARN="#E8A15A" if dark else "#C9772B",
        HOVER_RING=pri, SELECT_RING=_mix(pri, WHITE if dark else text, 0.3), POPUP_EDGE=pri,
        BLUSH=blush,
        SHADOW_A=_mix(blush, BLACK, 0.25 if dark else 0.06),
        SHADOW=_mix(blush, BLACK, 0.4 if dark else 0.12),
        SHADOW_C=_mix(blush, BLACK, 0.55 if dark else 0.18),
        FIELD=_mix(card, text, 0.07) if dark else _mix(card, WHITE, 0.6),
        HOVER=_mix(card, soft, 0.7),
        PAPER=paper, PAPER_EDGE=border,
        EMPTY_FILL=_mix(paper, text, 0.04) if dark else _mix(paper, acc, 0.07),
        EMPTY_LINE=_mix(acc, paper, 0.35 if dark else 0.45),
        EMPTY_PLUS=_mix(acc, paper, 0.3 if dark else 0.35),
        PIN_EDGE=_mix(text, bg, 0.25), TICK=_mix(text, bg, 0.15),
        GUIDE=_mix(acc, WHITE, 0.55) if dark else WHITE,
        ERR="#F08A7A" if dark else "#D95C5C",
        # crop window: colour the image fades to outside the pin, and the pin outline
        CROP_DIM=_rgb(bg), CROP_LINE=WHITE if dark else text,
        CROP_HALO=_mix(bg, BLACK, 0.4) if dark else WHITE)


# The original lo-fi look, kept exactly as it was.
_CLASSIC = {
    # lo-fi cosy daylight
    "classic_light": dict(
        MODE="light", ON_PRIMARY="white",
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
    "classic_dark": dict(
        MODE="dark", ON_PRIMARY="white",
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

# id, title, one-line note, mode, then the eight base colours for _build():
#   bg, card, border, text, muted, primary, soft button, accent
_PALETTES = [
    ("cream_denim", "Cream & Denim", "Soft denim blue", "light",
     "#F6EFE0", "#FFFBF2", "#E6D9BF", "#2B3345", "#767162", "#3F5F8F", "#EBE3CE", "#D49A4A"),
    ("oat_milk", "Oat Milk", "Sage green · default", "light",
     "#F5EEDF", "#FFFAF0", "#E8DCC3", "#3A3126", "#7D7260", "#7E8F68", "#EAE2CB", "#C47F4F"),
    ("strawberry_cream", "Strawberry Cream", "Rosy pink", "light",
     "#FBEFE6", "#FFF9F3", "#EFD7C8", "#4A2F33", "#86696A", "#D0707F", "#F6DFD3", "#A58BC8"),
    ("carbon_blue", "Carbon Blue", "Electric blue", "dark",
     "#0B0D12", "#13161D", "#232833", "#EDEFF4", "#8B93A3", "#5B8CFF", "#1C212B", "#7DD3FC"),
    ("graphite_mint", "Graphite Mint", "Fresh mint · default", "dark",
     "#0E0F10", "#161819", "#26292B", "#EDEDEA", "#8E9290", "#4FD1A5", "#1F2223", "#F5C26B"),
    ("midnight_orchid", "Midnight Orchid", "Orchid pink", "dark",
     "#0F0B14", "#17121E", "#2A2236", "#F2ECF7", "#9A8FA8", "#E879B9", "#211A2B", "#A78BFA"),
]

THEMES = {}          # id -> every colour name
THEME_INFO = {}      # id -> (title, note)
THEME_ORDER = {"light": [], "dark": []}      # ids in the order the Options window lists them
for _id, _title, _note, _mode, *_base in _PALETTES:
    THEMES[_id] = _build(_mode, *_base)
    THEME_INFO[_id] = (_title, _note)
    THEME_ORDER[_mode].append(_id)
for _id, _title, _note in (("classic_light", "Classic Light", "Teal & sand"),
                           ("classic_dark", "Classic Dark", "Teal night")):
    THEMES[_id] = _CLASSIC[_id]
    THEME_INFO[_id] = (_title, _note)
    THEME_ORDER[_CLASSIC[_id]["MODE"]].append(_id)


def mode_of(name):
    """"light" or "dark" for a theme id. The old settings file only stored "light" / "dark",
    which still works here; anything unknown counts as light.
    """
    if name == "dark":
        return "dark"
    return THEMES[name]["MODE"] if name in THEMES else "light"


def resolve(name, mode):
    """``name`` if it is a theme of that ``mode``, otherwise the default theme for the mode."""
    if name in THEMES and THEMES[name]["MODE"] == mode:
        return name
    return DEFAULT_DARK if mode == "dark" else DEFAULT_LIGHT


def apply_theme(name):
    """Switch the colour names in this module to the theme ``name``. Unknown names (and the
    old "light") give the default light theme, the old "dark" the default dark one.
    """
    if name == "dark":
        name = DEFAULT_DARK
    if name not in THEMES:
        name = DEFAULT_LIGHT
    colours = dict(THEMES[name])
    globals().update({k: v for k, v in colours.items() if k != "MODE"})
    globals()["THEME_NAME"] = name
    globals()["IS_DARK"] = colours["MODE"] == "dark"


apply_theme(DEFAULT_LIGHT)


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
    st.configure("Heading.TLabel", background=BG, foreground=PETROL, font=("Georgia", 15, "bold"))
    st.configure("Sub.TLabel", background=BG, foreground=MUTED)
    st.configure("Value.TLabel", background=CARD, foreground=PETROL,
                 font=(base[0], 10, "bold"))
    # small square-ish button for the - / + and rotate steps
    st.configure("Tool.TButton", background=SAND, foreground=TEXT, padding=(0, 5),
                 borderwidth=0, focusthickness=0, focuscolor=SAND, font=(base[0], 11))
    st.map("Tool.TButton", background=[("pressed", SAND_PRESS), ("active", SAND_HOVER)])
    st.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, focuscolor=CARD)
    st.map("Card.TCheckbutton", background=[("active", CARD)],
           indicatorcolor=[("selected", TEAL)])
    st.configure("Accent.TButton", background=TEAL, foreground=ON_PRIMARY, padding=(16, 9),
                 borderwidth=0, focusthickness=0, focuscolor=TEAL, font=(base[0], 10, "bold"))
    st.map("Accent.TButton", background=[("pressed", TEAL_DARK), ("active", TEAL_HOVER)])
    st.configure("Soft.TButton", background=SAND, foreground=TEXT, padding=(12, 7),
                 borderwidth=0, focusthickness=0, focuscolor=SAND)
    st.map("Soft.TButton", background=[("pressed", SAND_PRESS), ("active", SAND_HOVER)])
    st.configure("Hero.TLabel", background=CARD, foreground=PETROL, font=("Georgia", 19, "bold"))
    st.configure("Page.TLabel", background=BG, foreground=PETROL, font=("Georgia", 24, "bold"))
    st.configure("Section.TLabel", background=CARD, foreground=MUTED, font=(base[0], 8, "bold"))
    st.configure("Hero.TButton", background=TEAL, foreground=ON_PRIMARY, padding=(16, 13),
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
    sel = dict(selectbackground=TEAL, selectforeground=ON_PRIMARY)
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
    root.option_add("*TCombobox*Listbox.selectForeground", ON_PRIMARY)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    return base
