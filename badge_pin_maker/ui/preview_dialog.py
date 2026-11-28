"""The shop pictures window: the bundle and a close-up of every pin, ready to save or print.

It opens straight onto a loading screen while the whole set is prepared (the scene, then one
close-up per pin), so afterwards flicking between pictures is instant. The pictures are drawn
in a background thread so the window never freezes; saving and printing re-draw at full size the
same way. The product type and pins are chosen on the setup screen (``PreviewSetup``); here the
scene can still be switched, a caption added, and a ruler or real-size view turned on.

``PreviewDialog(parent, pool, sel, pin, type_, env, title)``: ``pool`` is [(label, Art)] for the
pins on the sheet, ``sel`` the indexes in use, ``pin`` the sheet's parameters.
"""

import io
import os
import queue
import re
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

from .. import envs
from ..imaging import render_art
from ..system_actions import print_pdf, reveal_folder
from . import theme as T
from .buttons import Btn
from .screens import Screen

SIZES = (("Web  (1600 px)", 1600), ("HD  (2400 px)", 2400), ("Print  (3000 px)", 3000))
THUMB = (118, 79)                      # a film-strip picture, in pixels


def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "pins"


class _Loading(tk.Frame):
    """A loading screen laid over the picture: a spinner, a title, a status line and a bar."""

    def __init__(self, parent):
        super().__init__(parent, bg=T.BG)
        box = tk.Frame(self, bg=T.BG)
        box.place(relx=0.5, rely=0.46, anchor="center")
        self.spin = tk.Canvas(box, width=64, height=64, bg=T.BG, highlightthickness=0)
        self.spin.pack()
        self.title = tk.Label(box, bg=T.BG, fg=T.TEXT, font=("TkDefaultFont", 14, "bold"))
        self.title.pack(pady=(12, 2))
        self.status = tk.Label(box, bg=T.BG, fg=T.MUTED)
        self.status.pack()
        self.bar = tk.Canvas(box, width=360, height=12, bg=T.BG, highlightthickness=0)
        self.bar.pack(pady=(14, 0))
        self._angle, self._job, self._frac = 0, None, 0.0

    def start(self, title, status=""):
        self.title.configure(text=title)
        self.status.configure(text=status)
        self.set(0.0)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        if self._job is None:
            self._tick()

    def set(self, frac, status=None):
        self._frac = max(0.0, min(1.0, frac))
        if status is not None:
            self.status.configure(text=status)
        self.bar.delete("all")
        self.bar.create_line(6, 6, 354, 6, width=8, capstyle="round", fill=T.BORDER)
        if self._frac > 0.01:
            self.bar.create_line(6, 6, 6 + 348 * self._frac, 6, width=8, capstyle="round", fill=T.TEAL)

    def stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self.place_forget()

    def _tick(self):
        self._angle = (self._angle + 14) % 360
        self.spin.delete("all")
        self.spin.create_oval(8, 8, 56, 56, outline=T.BORDER, width=5)
        self.spin.create_arc(8, 8, 56, 56, start=self._angle, extent=100, style="arc", outline=T.TEAL, width=5)
        self._job = self.after(40, self._tick)


class PreviewDialog(Screen):
    """The \"Preview pins\" page: one pin, or the bundle and a close-up of each pin."""

    def __init__(self, parent, pool, sel, pin, single=False):
        super().__init__(parent)
        self.parent, self.pool, self.pin, self.type, self.single = parent, list(pool), pin, "pin", single
        self.sel = list(sel)[:envs.MAX_PINS] or [0]
        self.env = "studio"
        self.view = 0 if single else "bundle"
        self.ruler = self.details = self.real = False
        self.v_title = tk.StringVar(value="")
        self.v_size = tk.IntVar(value=2400)
        self._faces, self._set, self._thumbs = {}, {}, {}
        self._shown, self._job, self._busy, self._again = None, None, False, False
        self._strip_imgs, self._scale = [], 1.0

        # ---- top bar: Return, the title, and Save / Print ----------------------------------------
        def extras(right):
            self.m_save = tk.Menu(self, tearoff=0)
            self.m_save.add_command(label="This picture…", command=lambda: self._save(False))
            self.m_save.add_command(label="All pictures (to a folder)…", command=lambda: self._save(True))
            self.m_print = tk.Menu(self, tearoff=0)
            self.m_print.add_command(label="This picture", command=lambda: self._print(False))
            self.m_print.add_command(label="All pictures (one per page)", command=lambda: self._print(True))
            if single:
                Btn(right, "Save image", lambda: self._save(False), bg=T.BG, icon="image").pack(side="left", padx=3)
            else:
                self.b_save = Btn(right, "Save", lambda: self._menu(self.b_save, self.m_save), bg=T.BG, icon="image")
                self.b_print = Btn(right, "Print", lambda: self._menu(self.b_print, self.m_print), bg=T.BG)
                self.b_save.pack(side="left", padx=3)
                self.b_print.pack(side="left", padx=3)
        self.return_bar("Preview pins", "One pin" if single else "Your pins as a bundle", right=extras, pad=20)

        self.info = tk.Label(self, bg=T.BG, fg=T.MUTED, anchor="w", justify="left")
        self.info.pack(side="bottom", fill="x", padx=22, pady=(4, 12))

        mid = tk.Frame(self, bg=T.BG)
        mid.pack(side="top", fill="both", expand=True, padx=20)
        self.strip = tk.Canvas(mid, bg=T.BG, height=THUMB[1] + 28, highlightthickness=0)
        if not single:
            self.strip.pack(side="bottom", fill="x", pady=(8, 0))
        stage = tk.Frame(mid, bg=T.BG)
        stage.pack(side="top", fill="both", expand=True)
        self.cv = tk.Canvas(stage, bg=T.BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self._soon())
        self.loading = _Loading(stage)
        self.strip.bind("<MouseWheel>", lambda e: self.strip.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.strip.bind("<Button-4>", lambda e: self.strip.xview_scroll(-1, "units"))
        self.strip.bind("<Button-5>", lambda e: self.strip.xview_scroll(1, "units"))

        self.bind("<Left>", self._typed(lambda: self._step(-1)))
        self.bind("<Right>", self._typed(lambda: self._step(1)))
        self.after(80, self._prepare)
        self.focus_set()

    def on_close(self):
        """Stop the loading spinner and any redraw that is waiting."""
        self.loading.stop()
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    # ---- helpers ---------------------------------------------------------------------------
    @property
    def kind(self):
        return envs.kind_for(self.type, self.env)

    def _typed(self, fn):
        def run(e):
            if not isinstance(self.focus_get(), (ttk.Entry, tk.Entry)):
                fn()
        return run

    def _menu(self, btn, menu):
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height() + 4)

    def _size_txt(self):
        fw, fh = self.pin["fw"], self.pin["fh"]
        txt = f"{fw:g} mm" if abs(fw - fh) < 0.05 else f"{fw:g} × {fh:g} mm"
        return f"{txt} {self.pin['shape'].lower()}"

    def _views(self):
        return [0] if self.single else ["bundle"] + list(range(len(self.sel)))

    def _vname(self, view):
        return "Bundle" if view == "bundle" else f"Pin {view + 1}"

    def _fname(self, view):
        return _slug(self.v_title.get() or "pins") + "-" + self.env + ("-bundle" if view == "bundle" else f"-pin{view + 1}")

    # ---- drawing the pictures (these run in a worker thread) -------------------------------------
    def _face(self, i, px):
        key = (i, round(px, 3))
        if key not in self._faces:
            if len(self._faces) > 24:
                self._faces.clear()
            p = self.pin
            self._faces[key] = render_art(self.pool[i][1], p["w"], px, h_mm=p["h"], face=(p["shape"], p["fw"], p["fh"]))
        return self._faces[key]

    def _render(self, views, env, ruler, long_px, step=None, first=0):
        """Draw ``views`` ('bundle' and / or pin numbers) in ``env``: {view: (RGB image, scale)}."""
        kind, out = envs.kind_for(self.type, env), {}
        for n, view in enumerate(views):
            if step:
                step(first + n, "Setting the scene…" if view == "bundle" else f"Close-up {view + 1} of {len(self.sel)}…")
            if view == "bundle":
                px = long_px / envs.W_MM
                out[view] = envs.bundle(env, kind, [self._face(i, px) for i in self.sel], self.pin, ruler, long_px)
            else:
                w = envs.window_mm(self.pin, kind)
                out[view] = envs.close_up(env, kind, self._face(self.sel[view], long_px / w), self.pin, w, ruler, long_px)
        return out

    def _captioned(self, img, scale, view, ctx):
        """The picture with its caption band, when the caption is on."""
        if not ctx["details"]:
            return img
        n = len(self.sel)
        noun = envs.NOUN[ctx["kind"]]
        lines = [f"{n} {noun}" if (view == "bundle" and n > 1) else
                 (f"1 {noun}".rstrip("s") if view == "bundle" else self.pool[self.sel[view]][0]), ctx["size"]]
        lines.append("true to size" if scale >= 0.995 else f"shown at {round(scale * 100)}% size")
        return envs.footer(img, ctx["title"], lines, img.width / envs.W_MM)

    def _ctx(self):
        return dict(details=self.details, title=self.v_title.get().strip(), kind=self.kind, size=self._size_txt())

    # ---- running work with a loading screen ------------------------------------------------------
    def _job_run(self, title, steps, work, done):
        """Run ``work(step)`` in a thread behind the loading screen, then ``done(result)`` here."""
        self._busy = True
        self.loading.start(title, "Starting…")
        q = queue.Queue()

        def step(i, text):
            q.put(("p", i, text))

        def run():
            try:
                q.put(("d", work(step)))
            except Exception as e:                       # shown to the person, not lost in the thread
                q.put(("e", e))
        threading.Thread(target=run, daemon=True).start()
        self._poll(q, max(1, steps), done)

    def _poll(self, q, steps, done):
        if not self.winfo_exists():
            return
        end = None
        try:
            while True:
                msg = q.get_nowait()
                if msg[0] == "p":
                    self.loading.set(msg[1] / steps, msg[2])
                else:
                    end = msg
        except queue.Empty:
            pass
        if end is None:
            self.after(50, self._poll, q, steps, done)
            return
        self._busy = False
        self.loading.stop()
        if end[0] == "e":
            messagebox.showerror("Something went wrong", str(end[1]), parent=self)
        else:
            done(end[1])
        if self._again:
            self._again = False
            self._prepare()

    def _prepare(self):
        """Draw the whole set for the current scene: the bundle, then each close-up."""
        if self._busy:
            self._again = True
            return
        env, ruler, n = self.env, self.ruler, len(self.sel)
        self._job_run("Preparing your picture" + ("" if self.single else "s"), n + 1,
                      lambda step: self._render(self._views(), env, ruler, envs.SCREEN_PX, step),
                      lambda res: self._prepared(res))

    def _prepared(self, res):
        self._set = res
        self._thumbs = {v: im.resize(THUMB, Image.LANCZOS) for v, (im, _s) in res.items()}
        if self.view != "bundle" and self.view >= len(self.sel):
            self.view = "bundle"
        self._soon(0)

    # ---- showing it -------------------------------------------------------------------------------
    def _soon(self, ms=60):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(ms, self._show)

    def _screen_scale(self, img, cw, ch):
        fit = min(cw / img.width, ch / img.height)
        if self.real:
            px = envs.SCREEN_PX / (envs.W_MM if self.view == "bundle" else envs.window_mm(self.pin, self.kind))
            true = self.winfo_fpixels("1m") / px
            if true * img.width <= cw and true * img.height <= ch:
                return true, True
        return fit, False

    def _show(self):
        self._job = None
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        if cw < 60 or ch < 60 or self.view not in self._set:
            return
        base, scale = self._set[self.view]
        img = self._captioned(base, scale, self.view, self._ctx())
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
        n = len(self.sel)
        what = (f"{n} pin{'s' if n != 1 else ''} together" if self.view == "bundle" else self.pool[self.sel[self.view]][0])
        self.info.configure(text=f"{what}  ·  {self._size_txt()}" +
                            ("" if scale >= 0.995 else f"  ·  shown at {round(scale * 100)}% so they all fit"))
        if not self.single:
            self._draw_strip()

    def _draw_strip(self):
        self.strip.delete("all")
        self._strip_imgs = []
        x = 4
        w, h = THUMB
        for view in self._views():
            t = self._thumbs.get(view)
            on = view == self.view
            rim = Image.new("RGB", (w + 8, h + 8), T.BG)
            d = ImageDraw.Draw(rim)
            if on:
                d.rounded_rectangle([0, 0, w + 7, h + 7], radius=12, outline=T.TEAL, width=3)
            if t is not None:
                m = Image.new("L", (w * 3, h * 3), 0)
                ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 3 - 1, h * 3 - 1], radius=24, fill=255)
                rim.paste(t, (4, 4), m.resize((w, h), Image.LANCZOS))
            tk_img = ImageTk.PhotoImage(rim)
            self._strip_imgs.append(tk_img)
            item = self.strip.create_image(x, 0, image=tk_img, anchor="nw")
            lab = self.strip.create_text(x + (w + 8) // 2, h + 18, text=self._vname(view), fill=T.TEXT if on else T.MUTED,
                                         font=("TkDefaultFont", 9, "bold" if on else "normal"))
            for it in (item, lab):
                self.strip.tag_bind(it, "<Button-1>", lambda e, v=view: self._go(v))
            x += w + 16
        self.strip.configure(scrollregion=(0, 0, x, h + 28), cursor="hand2")

    def _go(self, view):
        if self._busy:
            return
        self.view = view
        self._soon(0)

    def _step(self, d):
        views = self._views()
        self._go(views[(views.index(self.view) + d) % len(views)])

    # ---- controls ---------------------------------------------------------------------------------
    # ---- saving and printing ----------------------------------------------------------------------
    def _export_views(self, everything):
        return self._views() if everything else [self.view]

    def _save(self, everything):
        if self._busy:
            return
        views = self._export_views(everything)
        if everything:
            target = filedialog.askdirectory(parent=self, title="Save all pictures in…")
        else:
            target = filedialog.asksaveasfilename(
                parent=self, title="Save this picture", defaultextension=".png", initialfile=self._fname(views[0]) + ".png",
                filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg")])
        if not target:
            return
        env, ruler, long_px, ctx = self.env, self.ruler, self.v_size.get(), self._ctx()
        names = {v: self._fname(v) + ".png" for v in views}

        def work(step):
            done = self._render(views, env, ruler, long_px,
                                lambda i, t: step(i, f"Drawing at {long_px} px: {t}"))
            paths = []
            for n, v in enumerate(views):
                img, s = done[v]
                step(len(views) + n, "Saving…")
                path = os.path.join(target, names[v]) if everything else target
                self._captioned(img, s, v, ctx).save(path, quality=95)
                paths.append(path)
            return paths

        def finished(paths):
            self.info.configure(text=f"Saved {len(paths)} picture{'s' if len(paths) != 1 else ''}.")
            if everything:
                reveal_folder(target)

        self._job_run("Saving full-size pictures", 2 * len(views), work, finished)

    def _print(self, everything):
        """One picture per landscape A4 page, through the system's printing."""
        if self._busy:
            return
        views = self._export_views(everything)
        env, ruler, ctx = self.env, self.ruler, self._ctx()

        def work(step):
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
            done = self._render(views, env, ruler, 2000, lambda i, t: step(i, t))
            fd, path = tempfile.mkstemp(suffix=".pdf", prefix="pin-pictures-")
            os.close(fd)
            pw, ph = landscape(A4)
            c, m = canvas.Canvas(path, pagesize=(pw, ph)), 28
            for n, v in enumerate(views):
                step(len(views) + n, "Making the pages…")
                img = self._captioned(done[v][0], done[v][1], v, ctx).convert("RGB")
                k = min((pw - 2 * m) / img.width, (ph - 2 * m) / img.height)
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=90)
                buf.seek(0)
                c.drawImage(ImageReader(buf), (pw - img.width * k) / 2, (ph - img.height * k) / 2, img.width * k, img.height * k)
                c.showPage()
            c.save()
            return path

        def finished(path):
            print_pdf(path)
            self.info.configure(text=f"Sent {len(views)} page{'s' if len(views) != 1 else ''} to the printer.")

        self._job_run("Preparing the pages", 2 * len(views), work, finished)
