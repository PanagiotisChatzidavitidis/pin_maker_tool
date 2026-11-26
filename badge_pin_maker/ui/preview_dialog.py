"""The preview studio: show finished pins as a customer would see them, ready for a shop listing.

Pick an environment (modern desk, school desk, backpack, fridge magnets, keychains on a coffee
table, bottle openers on a party table), tick up to ten pins, and get a bundle picture with all
of them plus a close-up of each one. Every picture can be saved or printed on its own, or all
together. Pins are drawn at their real size; they shrink only when ten big ones would not fit
(and the caption then says so).

``PreviewDialog(parent, pool, selected, pin)``: ``pool`` is [(label, Art)] (every pin that could
be shown), ``selected`` the indexes into it that start ticked, ``pin`` the sheet's parameters.
"""

import io
import os
import re
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

from .. import envs, ring as ring_mod
from ..imaging import render_art
from ..system_actions import print_pdf, reveal_folder
from . import smooth, theme as T
from .buttons import Btn
from .widgets import Dropdown

SIZES = (("Web  (1600 px)", 1600), ("HD  (2400 px)", 2400), ("Print  (3000 px)", 3000))
THUMB = (118, 79)                      # a film-strip picture, in pixels


def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "pins"


class PreviewDialog(tk.Toplevel):
    def __init__(self, parent, pool, selected, pin, title=""):
        super().__init__(parent)
        self.title("Preview")
        self.configure(bg=T.BG)
        self.transient(parent)
        self.pool, self.pin = list(pool), pin
        self.sel = sorted(set(i for i in selected if 0 <= i < len(self.pool)))[:envs.MAX_PINS] \
            or [0]
        self.view = "bundle"                       # "bundle" or the index within self.sel
        self.ruler = self.details = self.real = False
        self.labels = {lab: key for key, lab, _ in envs.ENVS}
        self.v_env = tk.StringVar(value=envs.LABELS["desk"])
        self.v_title = tk.StringVar(value=title)
        self.v_size = tk.IntVar(value=2400)
        self._faces, self._bases, self._thumbs, self._pool_imgs = {}, {}, {}, []
        self._shown, self._job, self._tjob, self._gen = None, None, None, 0
        self._strip_imgs = []

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1380, int(sw * 0.92)), min(940, int(sh * 0.92))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(900, 600)

        # ---- top bar: environment, title, then the tools --------------------------------
        bar = tk.Frame(self, bg=T.BG)
        bar.pack(side="top", fill="x", padx=20, pady=(16, 10))
        self.dd = Dropdown(bar, self.v_env, [lab for _, lab, _ in envs.ENVS], width=300,
                           icon="shapes", outer=T.BG, align="left")
        self.dd.pack(side="left")
        self.ent = ttk.Entry(bar, textvariable=self.v_title, width=24)
        self.ent.pack(side="left", padx=(14, 0), ipady=5)
        tk.Label(bar, text="caption title", bg=T.BG, fg=T.MUTED).pack(side="left", padx=(6, 0))
        right = tk.Frame(bar, bg=T.BG)
        right.pack(side="right")
        self.b_details = Btn(right, "Details", self._toggle_details, kind="ghost", bg=T.BG)
        self.b_ruler = Btn(right, "Ruler", self._toggle_ruler, kind="ghost", bg=T.BG)
        self.b_real = Btn(right, "Real size", self._toggle_real, kind="ghost", bg=T.BG, icon="fit")
        self.b_save = Btn(right, "Save", lambda: self._menu(self.b_save, self.m_save), bg=T.BG,
                          icon="image")
        self.b_print = Btn(right, "Print", lambda: self._menu(self.b_print, self.m_print),
                           bg=T.BG)
        for b in (self.b_details, self.b_ruler, self.b_real, self.b_save, self.b_print):
            b.pack(side="left", padx=3)
        Btn(right, "Close", self.destroy, kind="accent", bg=T.BG).pack(side="left", padx=(6, 0))

        self.m_save = tk.Menu(self, tearoff=0)
        self.m_save.add_command(label="This picture…", command=lambda: self._save(False))
        self.m_save.add_command(label="All pictures (to a folder)…", command=lambda: self._save(True))
        self.m_save.add_separator()
        for lab, v in SIZES:
            self.m_save.add_radiobutton(label=lab, variable=self.v_size, value=v)
        self.m_print = tk.Menu(self, tearoff=0)
        self.m_print.add_command(label="This picture", command=lambda: self._print(False))
        self.m_print.add_command(label="All pictures (one per page)", command=lambda: self._print(True))

        # ---- bottom: a caption ------------------------------------------------------------
        self.info = tk.Label(self, bg=T.BG, fg=T.MUTED, font=("TkDefaultFont", 9), anchor="w",
                             justify="left")
        self.info.pack(side="bottom", fill="x", padx=22, pady=(4, 12))

        # ---- left: the pins ------------------------------------------------------------------
        left = tk.Frame(self, bg=T.BG, width=250)
        left.pack(side="left", fill="y", padx=(20, 0), pady=(0, 6))
        left.pack_propagate(False)
        head = tk.Frame(left, bg=T.BG)
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Pins in the picture", bg=T.BG, fg=T.TEXT,
                 font=("TkDefaultFont", 10, "bold")).pack(side="left")
        self.count = tk.Label(head, bg=T.BG, fg=T.MUTED)
        self.count.pack(side="right")
        tools = tk.Frame(left, bg=T.BG)
        tools.pack(fill="x", pady=(0, 6))
        Btn(tools, "Select all", self._all, kind="ghost", bg=T.BG, height=30).pack(side="left")
        Btn(tools, "Only first", self._first, kind="ghost", bg=T.BG, height=30).pack(side="left", padx=6)
        self.note = tk.Label(left, bg=T.BG, fg=T.MUTED, font=("TkDefaultFont", 9), anchor="w",
                             wraplength=240, justify="left")
        self.note.pack(side="bottom", fill="x", pady=(6, 0))
        box = tk.Frame(left, bg=T.BORDER)
        box.pack(fill="both", expand=True)
        self.pcv = tk.Canvas(box, bg=T.CARD, highlightthickness=0, bd=0)
        self.pcv.pack(fill="both", expand=True, padx=1, pady=1)
        self.rows_f = tk.Frame(self.pcv, bg=T.CARD)
        self._rows_id = self.pcv.create_window(0, 0, window=self.rows_f, anchor="nw")
        self.pcv.bind("<Configure>", lambda e: self.pcv.itemconfigure(self._rows_id, width=e.width))
        self.rows_f.bind("<Configure>", lambda e: self.pcv.configure(scrollregion=self.pcv.bbox("all")))
        self.pcv.bind("<MouseWheel>", lambda e: self.pcv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.pcv.bind("<Button-4>", lambda e: self.pcv.yview_scroll(-1, "units"))
        self.pcv.bind("<Button-5>", lambda e: self.pcv.yview_scroll(1, "units"))
        self.rows = []

        # ---- centre: the picture and the film strip --------------------------------------
        mid = tk.Frame(self, bg=T.BG)
        mid.pack(side="left", fill="both", expand=True, padx=(16, 20))
        self.strip = tk.Canvas(mid, bg=T.BG, height=THUMB[1] + 28, highlightthickness=0)
        self.strip.pack(side="bottom", fill="x", pady=(8, 0))
        self.cv = tk.Canvas(mid, bg=T.BG, highlightthickness=0)
        self.cv.pack(side="top", fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self._soon())
        self.strip.bind("<MouseWheel>", lambda e: self.strip.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.strip.bind("<Button-4>", lambda e: self.strip.xview_scroll(-1, "units"))
        self.strip.bind("<Button-5>", lambda e: self.strip.xview_scroll(1, "units"))

        self.bind("<Escape>", lambda e: self.destroy())
        for i, (key, _, _) in enumerate(envs.ENVS):
            self.bind(str(i + 1), self._typed(lambda k=key: self._pick_env(k)))
        self.bind("<Left>", self._typed(lambda: self._step(-1)))
        self.bind("<Right>", self._typed(lambda: self._step(1)))
        self.bind("r", self._typed(self._toggle_ruler))
        self.v_env.trace_add("write", lambda *_: self._changed())
        self.v_title.trace_add("write", lambda *_: self._soon(250))

        self._build_rows()
        self._sync_rows()
        self.cv.create_text(20, 20, text="Setting the scene…", anchor="nw", fill=T.MUTED,
                            font=("TkDefaultFont", 11), tags="wait")
        self._soon(60)
        self.focus_set()

    # ---- helpers ---------------------------------------------------------------------------
    @property
    def env(self):
        return self.labels[self.v_env.get()]

    def _typed(self, fn):
        """A key binding that does nothing while a text box has the keyboard."""
        def run(e):
            if isinstance(self.focus_get(), (ttk.Entry, tk.Entry)):
                return
            fn()
        return run

    def _menu(self, btn, menu):
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height() + 4)

    def _size_txt(self):
        fw, fh = self.pin["fw"], self.pin["fh"]
        txt = f"{fw:g} mm" if abs(fw - fh) < 0.05 else f"{fw:g} × {fh:g} mm"
        return f"{txt} {self.pin['shape'].lower()}"

    # ---- the pin list -----------------------------------------------------------------------
    def _chip(self, art, size=52):
        """A small picture of the pin for the list."""
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

    def _build_rows(self):
        for i, (label, art) in enumerate(self.pool):
            img = self._chip(art)
            self._pool_imgs.append(img)
            row = tk.Frame(self.rows_f, bg=T.CARD, highlightthickness=2,
                           highlightbackground=T.CARD, cursor="hand2")
            row.pack(fill="x", padx=6, pady=(6 if i == 0 else 2, 2))
            pic = tk.Label(row, image=img, bg=T.CARD, bd=0)
            pic.pack(side="left", padx=(6, 8), pady=4)
            tick = tk.Label(row, bg=T.CARD, bd=0)
            tick.pack(side="right", padx=8)
            txt = tk.Label(row, text=label, bg=T.CARD, fg=T.TEXT, anchor="w")
            txt.pack(side="left", fill="x", expand=True)
            for w in (row, pic, txt, tick):
                w.bind("<Button-1>", lambda e, i=i: self._toggle(i))
                w.bind("<MouseWheel>", lambda e: self.pcv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
                w.bind("<Button-4>", lambda e: self.pcv.yview_scroll(-1, "units"))
                w.bind("<Button-5>", lambda e: self.pcv.yview_scroll(1, "units"))
            self.rows.append((row, tick))
        self._ticks = (smooth.nav_icon("check", T.TEAL, T.CARD, 18),
                       smooth.nav_icon("check", T.CARD, T.CARD, 18))

    def _sync_rows(self):
        for i, (row, tick) in enumerate(self.rows):
            on = i in self.sel
            row.configure(highlightbackground=T.TEAL if on else T.CARD)
            tick.configure(image=self._ticks[0 if on else 1])
        self.count.configure(text=f"{len(self.sel)} of {envs.MAX_PINS}")

    def _flash(self, text):
        self.note.configure(text=text)
        self.after(3200, lambda: self.note.winfo_exists() and self.note.configure(text=""))

    def _toggle(self, i):
        if i in self.sel:
            if len(self.sel) == 1:
                return self._flash("Keep at least one pin in the picture.")
            self.sel.remove(i)
        else:
            if len(self.sel) >= envs.MAX_PINS:
                return self._flash(f"A picture holds up to {envs.MAX_PINS} pins. "
                                   "Untick one to add another.")
            self.sel = sorted(self.sel + [i])
        self._selection_changed()

    def _all(self):
        self.sel = list(range(min(len(self.pool), envs.MAX_PINS)))
        if len(self.pool) > envs.MAX_PINS:
            self._flash(f"The first {envs.MAX_PINS} are ticked: that is the most one picture holds.")
        self._selection_changed()

    def _first(self):
        self.sel = [self.sel[0]]
        self._selection_changed()

    def _selection_changed(self):
        if self.view != "bundle" and self.view >= len(self.sel):
            self.view = "bundle"
        self._sync_rows()
        self._changed()

    def _changed(self):
        """Something that changes the pictures themselves: start over."""
        self._gen += 1
        self._bases.clear()
        self._soon(30)

    # ---- the pictures ---------------------------------------------------------------------
    def _face(self, i, px):
        key = (i, round(px, 3))
        if key not in self._faces:
            if len(self._faces) > 24:
                self._faces.clear()
            p = self.pin
            self._faces[key] = render_art(self.pool[i][1], p["w"], px, h_mm=p["h"],
                                          face=(p["shape"], p["fw"], p["fh"]))
        return self._faces[key]

    def _window(self):
        return envs.window_mm(self.pin, envs.KINDS[self.env])

    def _base(self, view):
        """The picture for ``view`` with no caption: (image, scale)."""
        key = (self.env, tuple(self.sel), self.ruler, view)
        if key not in self._bases:
            if len(self._bases) > 4:
                self._bases.pop(next(iter(self._bases)))
            if view == "bundle":
                faces = [self._face(i, envs.BUNDLE_PX) for i in self.sel]
                self._bases[key] = envs.bundle(self.env, faces, self.pin, self.ruler)
            else:
                w = self._window()
                px = envs.LONG_PX / w
                self._bases[key] = envs.close_up(self.env, self._face(self.sel[view], px), self.pin,
                                                 px, w, self.ruler)
        return self._bases[key]

    def _caption_lines(self, view, scale):
        n = len(self.sel)
        if view == "bundle":
            lines = [f"{n} {envs.NOUN[envs.KINDS[self.env]]}" if n > 1 else
                     f"1 {envs.NOUN[envs.KINDS[self.env]]}".rstrip("s"), self._size_txt()]
        else:
            lines = [self.pool[self.sel[view]][0], self._size_txt()]
        if scale < 0.995:
            lines.append(f"shown at {round(scale * 100)}% size")
        else:
            lines.append("true to size")
        return lines

    def _final(self, view):
        """The picture as saved / printed: with the caption band when Details is on."""
        img, s = self._base(view)
        if self.details:
            img = envs.footer(img, self.v_title.get().strip(), self._caption_lines(view, s),
                              img.width / envs.W_MM)
        return img

    def _views(self):
        return ["bundle"] + list(range(len(self.sel)))

    def _vname(self, view):
        return "Bundle" if view == "bundle" else f"Pin {view + 1}"

    # ---- showing it ---------------------------------------------------------------------
    def _soon(self, ms=90):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(ms, self._show)

    def _screen_scale(self, img, cw, ch):
        """(display scale, True when it is real size)."""
        fit = min(cw / img.width, ch / img.height)
        if self.real:
            px = envs.BUNDLE_PX if self.view == "bundle" else envs.LONG_PX / self._window()
            true = self.winfo_fpixels("1m") / px
            if true * img.width <= cw and true * img.height <= ch:
                return true, True
        return fit, False

    def _show(self):
        self._job = None
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        if cw < 60 or ch < 60:
            return
        if (self.env, tuple(self.sel), self.ruler, self.view) not in self._bases:
            self.config(cursor="watch")
            self.cv.delete("all")
            self.cv.create_text(cw // 2, ch // 2, text="Setting the scene…", fill=T.MUTED,
                                font=("TkDefaultFont", 11))
            self.update_idletasks()
        try:
            img = self._final(self.view)
            scale = self._base(self.view)[1]
        finally:
            self.config(cursor="")
        k, real = self._screen_scale(img, cw, ch)
        size = (max(1, round(img.width * k)), max(1, round(img.height * k)))
        pic = img.resize(size, Image.LANCZOS)
        r, ss = 16, 3
        m = Image.new("L", (size[0] * ss, size[1] * ss), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] * ss - 1, size[1] * ss - 1], radius=r * ss, fill=255)
        pic = Image.composite(pic, Image.new("RGB", size, T.BG), m.resize(size, Image.LANCZOS))
        self._shown = ImageTk.PhotoImage(pic)
        self.cv.delete("all")
        self.cv.create_image(cw // 2, ch // 2, image=self._shown)
        kind = envs.KINDS[self.env]
        what = (f"{len(self.sel)} {envs.NOUN[kind]} together" if self.view == "bundle"
                else f"close-up of {self.pool[self.sel[self.view]][0]}")
        scale_txt = ("true to size" if scale >= 0.995 else
                     f"{len(self.sel)} large pins do not fit at real size, so they are shown at "
                     f"{round(scale * 100)}%")
        if self.real:
            tip = ("Real size: 1 mm here is 1 mm on your screen." if real else
                   "Real size needs a bigger window, so it is shown to fit.")
        else:
            tip = "Arrow keys switch pictures. 1-6 switch environments."
        self.info.configure(text=f"{envs.LABELS[self.env]}  ·  {what}  ·  {self._size_txt()}, "
                                 f"{scale_txt}\n{tip}")
        for b, on in ((self.b_details, self.details), (self.b_ruler, self.ruler),
                      (self.b_real, self.real)):
            b.configure(kind="accent" if on else "ghost")
        self._draw_strip()
        self._start_thumbs()

    # ---- the film strip ---------------------------------------------------------------------
    def _tkey(self, view):
        return (self.env, tuple(self.sel), self.ruler, view)

    def _draw_strip(self):
        self.strip.delete("all")
        self._strip_imgs = []
        x = 4
        for view in self._views():
            t = self._thumbs.get(self._tkey(view))
            on = view == self.view
            w, h = THUMB
            rim = Image.new("RGB", (w + 8, h + 8), T.BG)
            d = ImageDraw.Draw(rim)
            if on:
                d.rounded_rectangle([0, 0, w + 7, h + 7], radius=12, outline=T.TEAL, width=3)
            if t is not None:
                m = Image.new("L", (w * 3, h * 3), 0)
                ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 3 - 1, h * 3 - 1], radius=24, fill=255)
                rim.paste(t, (4, 4), m.resize((w, h), Image.LANCZOS))
            else:
                d.rounded_rectangle([4, 4, w + 3, h + 3], radius=8, fill=T.SAND)
            tk_img = ImageTk.PhotoImage(rim)
            self._strip_imgs.append(tk_img)
            item = self.strip.create_image(x, 0, image=tk_img, anchor="nw", tags=("t",))
            lab = self.strip.create_text(x + (w + 8) // 2, h + 18, text=self._vname(view),
                                         fill=T.TEXT if on else T.MUTED,
                                         font=("TkDefaultFont", 9, "bold" if on else "normal"))
            for it in (item, lab):
                self.strip.tag_bind(it, "<Button-1>", lambda e, v=view: self._go(v))
                self.strip.configure(cursor="hand2")
            x += w + 16
        self.strip.configure(scrollregion=(0, 0, x, THUMB[1] + 28))

    def _start_thumbs(self):
        if self._tjob is not None:
            self.after_cancel(self._tjob)
        self._tjob = self.after(60, self._next_thumb, self._gen)

    def _next_thumb(self, gen):
        """Make the missing film-strip pictures one at a time, so the window stays usable."""
        self._tjob = None
        if gen != self._gen or not self.winfo_exists():
            return
        for view in self._views():
            key = self._tkey(view)
            if key in self._thumbs:
                continue
            img = self._base(view)[0]
            self._thumbs[key] = img.resize(THUMB, Image.LANCZOS)
            self._draw_strip()
            self._tjob = self.after(50, self._next_thumb, gen)
            return

    def _go(self, view):
        self.view = view
        self._soon(0)

    def _step(self, d):
        views = self._views()
        self._go(views[(views.index(self.view) + d) % len(views)])

    # ---- controls -------------------------------------------------------------------------
    def _pick_env(self, key):
        self.v_env.set(envs.LABELS[key])

    def _toggle_details(self):
        self.details = not self.details
        self._soon(0)

    def _toggle_ruler(self):
        self.ruler = not self.ruler
        self._gen += 1
        self._soon(0)

    def _toggle_real(self):
        self.real = not self.real
        self._soon(0)

    # ---- saving and printing ----------------------------------------------------------------
    def _export(self, view):
        img = self._final(view)
        long_edge = self.v_size.get()
        if img.width != long_edge:
            img = img.resize((long_edge, round(img.height * long_edge / img.width)), Image.LANCZOS)
        return img

    def _stem(self):
        return _slug(self.v_title.get() or "pins") + "-" + self.env

    def _fname(self, view):
        return self._stem() + ("-bundle" if view == "bundle" else f"-pin{view + 1}")

    def _save(self, everything):
        try:
            if not everything:
                path = filedialog.asksaveasfilename(
                    parent=self, title="Save this picture", defaultextension=".png",
                    initialfile=self._fname(self.view) + ".png",
                    filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg")])
                if path:
                    self._write(self._export(self.view), path)
                return
            folder = filedialog.askdirectory(parent=self, title="Save all pictures in…")
            if not folder:
                return
            self.config(cursor="watch")
            self.update_idletasks()
            for view in self._views():
                self._write(self._export(view), os.path.join(folder, self._fname(view) + ".png"))
            self.config(cursor="")
            self._flash(f"Saved {len(self._views())} pictures.")
            reveal_folder(folder)
        except OSError as e:
            self.config(cursor="")
            messagebox.showerror("Could not save", str(e), parent=self)

    @staticmethod
    def _write(img, path):
        img.save(path, quality=95)

    def _print(self, everything):
        """One picture per landscape A4 page, through the system's printing."""
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
        views = self._views() if everything else [self.view]
        fd, path = tempfile.mkstemp(suffix=".pdf", prefix="pin-preview-")
        os.close(fd)
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            pw, ph = landscape(A4)
            c = canvas.Canvas(path, pagesize=(pw, ph))
            m = 28
            for view in views:
                img = self._final(view).convert("RGB")
                k = min((pw - 2 * m) / img.width, (ph - 2 * m) / img.height)
                w, h = img.width * k, img.height * k
                buf = io.BytesIO()
                img.resize((2000, round(2000 * img.height / img.width)), Image.LANCZOS).save(
                    buf, "JPEG", quality=90)
                buf.seek(0)
                c.drawImage(ImageReader(buf), (pw - w) / 2, (ph - h) / 2, w, h)
                c.showPage()
            c.save()
            self.config(cursor="")
            print_pdf(path)
            self._flash(f"Sent {len(views)} page{'s' if len(views) > 1 else ''} to the printer.")
        except OSError as e:
            self.config(cursor="")
            messagebox.showerror("Could not print", str(e), parent=self)
