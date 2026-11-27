"""The first screen of the shop preview: what to show, which pins, and where.

1. Pick what the pins are sold as: a pin, a magnet, a bottle opener or a keychain.
2. Tick the pins (up to ten) that go in the pictures.
3. Pick a scene that suits that product. Only scenes that make sense are offered.

"Proceed" opens the results window, which shows a loading screen while all the pictures
(the bundle and a close-up of each pin) are prepared.
"""

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from .. import envs, ring as ring_mod
from ..imaging import render_art
from . import smooth, theme as T
from .buttons import Btn

CARD_W, CARD_H = 224, 150
CHIP = 54


class PreviewSetup(tk.Toplevel):
    def __init__(self, parent, pool, selected, pin, type_="pin", env=None, title=""):
        super().__init__(parent)
        self.title("Shop pictures")
        self.configure(bg=T.BG)
        self.transient(parent)
        self.parent, self.pool, self.pin, self.caption = parent, list(pool), pin, title
        self.sel = sorted(set(i for i in selected if 0 <= i < len(self.pool)))[:envs.MAX_PINS] or [0]
        self.type = type_
        self.env = env if env in envs.BY_TYPE[type_] else envs.BY_TYPE[type_][0]
        self._imgs = []                                   # keep the pictures alive
        self._env_thumbs = {}
        self._type_cards, self._env_cards, self._rows = {}, {}, []

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1180, int(sw * 0.94)), min(780, int(sh * 0.92))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(900, 600)

        # ---- header and footer ---------------------------------------------------------------
        head = tk.Frame(self, bg=T.BG)
        head.pack(side="top", fill="x", padx=28, pady=(22, 6))
        tk.Label(head, text="Create shop pictures", bg=T.BG, fg=T.TEXT,
                 font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        tk.Label(head, text="Choose the product, the pins and a scene. Every picture is ready to "
                            "use in a shop listing.", bg=T.BG, fg=T.MUTED).pack(anchor="w", pady=(2, 0))
        foot = tk.Frame(self, bg=T.BG)
        foot.pack(side="bottom", fill="x", padx=28, pady=(8, 20))
        self.go = Btn(foot, "Proceed", self._proceed, kind="accent", bg=T.BG, icon="eye")
        self.go.pack(side="right")
        Btn(foot, "Cancel", self.destroy, kind="ghost", bg=T.BG).pack(side="right", padx=8)
        self.summary = tk.Label(foot, bg=T.BG, fg=T.MUTED, anchor="w")
        self.summary.pack(side="left")

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=28, pady=(8, 0))
        left = tk.Frame(body, bg=T.BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=T.BG, width=340)
        right.pack(side="right", fill="y", padx=(24, 0))
        right.pack_propagate(False)

        self._section(left, "1", "What are you showing?")
        grid = tk.Frame(left, bg=T.BG)
        grid.pack(fill="x", pady=(8, 16))
        for i, (key, lab, note) in enumerate(envs.TYPES):
            self._type_card(grid, key, lab, note).grid(row=i // 2, column=i % 2, padx=(0, 12), pady=(0, 12),
                                                       sticky="nsew")
        self._section(left, "3", "Where should it be shown?")
        self.env_box = tk.Frame(left, bg=T.BG)
        self.env_box.pack(fill="x", pady=(8, 0))

        self._section(right, "2", "Which pins?")
        bar = tk.Frame(right, bg=T.BG)
        bar.pack(fill="x", pady=(6, 6))
        self.count = tk.Label(bar, bg=T.BG, fg=T.MUTED)
        self.count.pack(side="right")
        Btn(bar, "All", self._all, kind="ghost", bg=T.BG, height=30).pack(side="left")
        Btn(bar, "None", self._none, kind="ghost", bg=T.BG, height=30).pack(side="left", padx=6)
        self.note = tk.Label(right, bg=T.BG, fg=T.MUTED, anchor="w", wraplength=330, justify="left")
        self.note.pack(side="bottom", fill="x", pady=(6, 0))
        box = tk.Frame(right, bg=T.BORDER)
        box.pack(fill="both", expand=True)
        self.cv = tk.Canvas(box, bg=T.CARD, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True, padx=1, pady=1)
        self.inner = tk.Frame(self.cv, bg=T.CARD)
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self._wheel(self.cv)

        self._build_pins()
        self._show_envs()
        self._refresh()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._proceed())
        self.after(30, self._type_thumbs)
        self.focus_set()

    # ---- pieces -------------------------------------------------------------------------------
    def _section(self, parent, num, text):
        row = tk.Frame(parent, bg=T.BG)
        row.pack(fill="x")
        tk.Label(row, text=num, bg=T.TEAL, fg="white", width=2, font=("TkDefaultFont", 10, "bold")).pack(side="left")
        tk.Label(row, text=text, bg=T.BG, fg=T.TEXT, font=("TkDefaultFont", 12, "bold")).pack(side="left", padx=10)

    def _wheel(self, w):
        w.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        w.bind("<Button-4>", lambda e: self.cv.yview_scroll(-1, "units"))
        w.bind("<Button-5>", lambda e: self.cv.yview_scroll(1, "units"))

    def _card(self, parent, on_click):
        f = tk.Frame(parent, bg=T.CARD, highlightthickness=2, highlightbackground=T.BORDER, cursor="hand2")
        return f

    def _bind_all(self, widget, fn):
        widget.bind("<Button-1>", lambda e: fn())
        for c in widget.winfo_children():
            self._bind_all(c, fn)

    def _type_card(self, parent, key, label, note):
        f = self._card(parent, None)
        pic = tk.Label(f, bg=T.CARD, bd=0)
        pic.pack(side="left", padx=(10, 8), pady=10)
        col = tk.Frame(f, bg=T.CARD)
        col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(col, text=label, bg=T.CARD, fg=T.TEXT, font=("TkDefaultFont", 11, "bold"), anchor="w").pack(fill="x", pady=(12, 2))
        tk.Label(col, text=note, bg=T.CARD, fg=T.MUTED, anchor="w", justify="left", wraplength=150).pack(fill="x")
        self._type_cards[key] = (f, pic)
        self._bind_all(f, lambda k=key: self._set_type(k))
        return f

    def _chip(self, art, size=CHIP):
        p = self.pin
        k = size / max(p["fw"], p["fh"])
        try:
            face = render_art(art, p["w"], k, h_mm=p["h"], face=(p["shape"], p["fw"], p["fh"]))
            W, H = max(8, int(p["fw"] * k)), max(8, int(p["fh"] * k))
            base = Image.new("RGB", (W, H), (255, 255, 255))
            base.paste(face.convert("RGB"), (W // 2 - face.width // 2, H // 2 - face.height // 2))
            m = ring_mod.mask(p["shape"], p["fw"], p["fh"], 0, (W, H), k, k, W / 2, H / 2, 3)
            out = Image.new("RGB", (size, size), T.CARD)
            out.paste(base, ((size - W) // 2, (size - H) // 2), m)
            return ImageTk.PhotoImage(out)
        except Exception:
            return ImageTk.PhotoImage(Image.new("RGB", (size, size), T.CARD))

    def _build_pins(self):
        cols = 3
        for i, (label, art) in enumerate(self.pool):
            img = self._chip(art)
            self._imgs.append(img)
            f = tk.Frame(self.inner, bg=T.CARD, highlightthickness=2, highlightbackground=T.CARD, cursor="hand2")
            f.grid(row=i // cols, column=i % cols, padx=6, pady=6)
            tk.Label(f, image=img, bg=T.CARD, bd=0).pack(padx=6, pady=(6, 0))
            tk.Label(f, text=label, bg=T.CARD, fg=T.TEXT).pack(pady=(0, 6))
            self._bind_all(f, lambda i=i: self._toggle(i))
            self._wheel(f)
            for c in f.winfo_children():
                self._wheel(c)
            self._rows.append(f)

    # ---- the thumbnails -------------------------------------------------------------------------
    def _type_thumbs(self):
        """A small picture of each product made from the first ticked pin."""
        p = self.pin
        px = 3.4
        try:
            face = render_art(self.pool[self.sel[0]][1], p["w"], px, h_mm=p["h"], face=(p["shape"], p["fw"], p["fh"]))
            with envs.at_px(px):
                for key, _, _ in envs.TYPES:
                    kind = envs.kind_for(key, "studio")
                    if key in ("opener",):
                        spr, _a = envs.unit(kind, face, p["shape"], p["fw"], p["fh"], back=True)
                    else:
                        spr, _a = envs.unit(kind, face, p["shape"], p["fw"], p["fh"])
                    size = (112, 112)
                    k = min(size[0] * 0.9 / spr.width, size[1] * 0.9 / spr.height)
                    spr = spr.resize((max(1, int(spr.width * k)), max(1, int(spr.height * k))), Image.LANCZOS)
                    bg = Image.new("RGB", size, (240, 240, 238))
                    sh = Image.new("RGBA", size, (0, 0, 0, 0))
                    x, y = (size[0] - spr.width) // 2, (size[1] - spr.height) // 2
                    a = spr.getchannel("A").point(lambda v: v // 3)
                    bg.paste(Image.new("RGB", spr.size, (40, 40, 46)), (x + 2, y + 3), a)
                    bg.paste(spr.convert("RGB"), (x, y), spr.getchannel("A"))
                    img = ImageTk.PhotoImage(bg)
                    self._imgs.append(img)
                    self._type_cards[key][1].configure(image=img)
        except Exception:
            pass

    def _env_thumb(self, env):
        if env not in self._env_thumbs:
            try:
                img = envs.backdrop(env, envs.W_MM, False, envs.SCREEN_PX).resize((CARD_W, int(CARD_W * 2 / 3)), Image.LANCZOS)
                m = Image.new("L", (img.width * 3, img.height * 3), 0)
                ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width * 3 - 1, img.height * 3 - 1], radius=30, fill=255)
                out = Image.new("RGB", img.size, T.CARD)
                out.paste(img, (0, 0), m.resize(img.size, Image.LANCZOS))
                self._env_thumbs[env] = ImageTk.PhotoImage(out)
            except Exception:
                self._env_thumbs[env] = ImageTk.PhotoImage(Image.new("RGB", (CARD_W, int(CARD_W * 2 / 3)), T.SAND))
        return self._env_thumbs[env]

    def _show_envs(self):
        for w in self.env_box.winfo_children():
            w.destroy()
        self._env_cards.clear()
        keys = envs.BY_TYPE[self.type]
        for i, key in enumerate(keys):
            f = self._card(self.env_box, None)
            f.grid(row=i // 2, column=i % 2, padx=(0, 12), pady=(0, 12), sticky="nw")
            holder = tk.Label(f, bg=T.CARD, bd=0, width=CARD_W // 7, height=CARD_H // 16)
            holder.pack(padx=8, pady=(8, 4))
            tk.Label(f, text=envs.LABELS[key], bg=T.CARD, fg=T.TEXT, font=("TkDefaultFont", 11, "bold"),
                     anchor="w").pack(fill="x", padx=10)
            tk.Label(f, text=envs.NOTES[key], bg=T.CARD, fg=T.MUTED, anchor="w", justify="left",
                     wraplength=CARD_W - 8).pack(fill="x", padx=10, pady=(0, 10))
            self._env_cards[key] = (f, holder)
            self._bind_all(f, lambda k=key: self._set_env(k))
        self.after(20, self._fill_env_thumbs, list(keys))
        self._refresh()

    def _fill_env_thumbs(self, keys):
        """Draw the scene pictures one at a time so the screen stays responsive."""
        if not keys or not self.winfo_exists():
            return
        key = keys.pop(0)
        if key in self._env_cards:
            holder = self._env_cards[key][1]
            if holder.winfo_exists():
                holder.configure(image=self._env_thumb(key), width=0, height=0)
        self.after(15, self._fill_env_thumbs, keys)

    # ---- choices ----------------------------------------------------------------------------------
    def _set_type(self, key):
        if key == self.type:
            return
        self.type = key
        if self.env not in envs.BY_TYPE[key]:
            self.env = envs.BY_TYPE[key][0]
        self._show_envs()

    def _set_env(self, key):
        self.env = key
        self._refresh()

    def _toggle(self, i):
        if i in self.sel:
            if len(self.sel) == 1:
                return self._flash("Keep at least one pin ticked.")
            self.sel.remove(i)
        else:
            if len(self.sel) >= envs.MAX_PINS:
                return self._flash(f"A picture holds up to {envs.MAX_PINS} pins. Untick one to add another.")
            self.sel = sorted(self.sel + [i])
        self._refresh()

    def _all(self):
        self.sel = list(range(min(len(self.pool), envs.MAX_PINS)))
        if len(self.pool) > envs.MAX_PINS:
            self._flash(f"The first {envs.MAX_PINS} are ticked: the most one picture holds.")
        self._refresh()

    def _none(self):
        self.sel = self.sel[:1]
        self._refresh()

    def _flash(self, text):
        self.note.configure(text=text)
        self.after(3500, lambda: self.note.winfo_exists() and self.note.configure(text=""))

    def _refresh(self):
        for key, (f, _) in self._type_cards.items():
            f.configure(highlightbackground=T.TEAL if key == self.type else T.BORDER)
        for key, (f, _) in self._env_cards.items():
            f.configure(highlightbackground=T.TEAL if key == self.env else T.BORDER)
        for i, f in enumerate(self._rows):
            f.configure(highlightbackground=T.TEAL if i in self.sel else T.CARD)
        self.count.configure(text=f"{len(self.sel)} of {envs.MAX_PINS}")
        n = len(self.sel)
        self.summary.configure(
            text=f"{n} {'pin' if n == 1 else 'pins'}  ·  {envs.TYPE_LABEL[self.type]}  ·  {envs.LABELS[self.env]}")

    def _proceed(self):
        from .preview_dialog import PreviewDialog
        parent, args = self.parent, (self.pool, list(self.sel), self.pin, self.type, self.env, self.caption)
        self.destroy()
        PreviewDialog(parent, *args)
