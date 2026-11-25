"""The "see it for real" window: the finished pin set down in a small photo-like scene next to
everyday things of known size (a coin, a bank card, a pencil, a paper clip, a jeans button), at
its true size in millimetres. Three scenes, an optional 10 cm ruler, "real size" (1 mm on the
picture is 1 mm on your screen, as far as the screen reports it) and a button to save the image.
"""

import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageTk

from .. import scene
from ..imaging import render_art
from . import theme as T
from .buttons import Btn
from .tabs import PillTabs

# what is in each scene, for the caption
PROPS = {
    "desk": "coin 23 mm  ·  bank card 85.6 × 54 mm  ·  pencil 7 mm wide",
    "denim": "jeans button 17 mm  ·  rivet 9 mm  ·  stitching 3 mm",
    "canvas": "coin 23 mm  ·  paper clip 33 mm  ·  webbing strap 34 mm",
}


class PreviewDialog(tk.Toplevel):
    """``art`` is the pin's ``Art``; ``pin`` the sheet's pin parameters (shape, sizes)."""

    def __init__(self, parent, art, pin):
        super().__init__(parent)
        self.title("Preview your pin")
        self.configure(bg=T.BG)
        self.transient(parent)
        self.art, self.pin = art, pin
        self.v_scene = tk.StringVar(value="desk")
        self.ruler = False
        self.real = False
        self._cache = {}
        self._face = None
        self._shown = None            # the PhotoImage on the canvas
        self._job = None

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1280, int(sw * 0.86)), min(900, int(sh * 0.88))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(720, 520)

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(side="top", fill="x", padx=20, pady=(16, 10))
        self.tabs = PillTabs(bar, self.v_scene, list(scene.SCENES), command=self._scene,
                             bg=T.BG)
        self.tabs.pack(side="left")
        self.tabs.configure(width=330)
        right = tk.Frame(bar, bg=T.BG)
        right.pack(side="right")
        self.b_real = Btn(right, "Real size", self._toggle_real, kind="ghost", bg=T.BG,
                          icon="fit")
        self.b_real.pack(side="left", padx=4)
        self.b_ruler = Btn(right, "Ruler", self._toggle_ruler, kind="ghost", bg=T.BG)
        self.b_ruler.pack(side="left", padx=4)
        Btn(right, "Save image", self._save, bg=T.BG, icon="image").pack(side="left", padx=4)
        Btn(right, "Close", self.destroy, kind="accent", bg=T.BG).pack(side="left", padx=(4, 0))

        self.info = tk.Label(self, bg=T.BG, fg=T.MUTED, font=("TkDefaultFont", 9), anchor="w",
                             justify="left")
        self.info.pack(side="bottom", fill="x", padx=22, pady=(8, 14))
        self.cv = tk.Canvas(self, bg=T.BG, highlightthickness=0)
        self.cv.pack(side="top", fill="both", expand=True, padx=20)
        self.cv.bind("<Configure>", lambda e: self._soon())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("1", lambda e: self._pick("desk"))
        self.bind("2", lambda e: self._pick("denim"))
        self.bind("3", lambda e: self._pick("canvas"))
        self.bind("r", lambda e: self._toggle_ruler())

        self.cv.create_text(20, 20, text="Setting the scene…", anchor="nw", fill=T.MUTED,
                            font=("TkDefaultFont", 11), tags="wait")
        self.after(40, self._build)
        self.focus_set()

    # ---- building the picture ----------------------------------------------------------
    def _build(self):
        """Render the pin once at scene resolution, then show the first scene."""
        p = self.pin
        self.config(cursor="watch")
        self.update_idletasks()
        self._face = render_art(self.art, p["w"], scene.PX, h_mm=p["h"],
                                face=(p["shape"], p["fw"], p["fh"]))
        self.config(cursor="")
        self.cv.delete("wait")
        self._soon(0)

    def _composed(self):
        """The current scene as a full-size image (cached per scene and ruler)."""
        key = (self.v_scene.get(), self.ruler)
        if key not in self._cache:
            if len(self._cache) > 5:
                self._cache.clear()
            p = self.pin
            self._cache[key] = scene.compose(key[0], self._face, p["shape"], p["fw"], p["fh"],
                                             self.ruler)
        return self._cache[key]

    # ---- showing it --------------------------------------------------------------------
    def _soon(self, ms=90):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(ms, self._show)

    def _scale(self, cw, ch):
        """(display scale, True when it is real size)."""
        W, H = scene.SIZE
        fit = min(cw / W, ch / H)
        if self.real:
            true = self.winfo_fpixels("1m") / scene.PX        # screen pixels per scene pixel
            if true * W <= cw and true * H <= ch:
                return true, True
        return fit, False

    def _show(self):
        self._job = None
        if self._face is None:
            return
        cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
        if cw < 50 or ch < 50:
            return
        img = self._composed()
        k, real = self._scale(cw, ch)
        W, H = scene.SIZE
        size = (max(1, round(W * k)), max(1, round(H * k)))
        pic = img.resize(size, Image.LANCZOS)
        # rounded corners, in the window colour
        r = 18
        m = Image.new("L", (size[0] * 3, size[1] * 3), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] * 3 - 1, size[1] * 3 - 1],
                                            radius=r * 3, fill=255)
        pic = Image.composite(pic, Image.new("RGB", size, T.BG), m.resize(size, Image.LANCZOS))
        self._shown = ImageTk.PhotoImage(pic)
        self.cv.delete("all")
        self.cv.create_image(cw // 2, ch // 2, image=self._shown)
        p = self.pin
        fw, fh = p["fw"], p["fh"]
        size_txt = f"{fw:g} mm" if abs(fw - fh) < 0.05 else f"{fw:g} × {fh:g} mm"
        if self.real:
            note = ("Shown at real size: 1 mm here is 1 mm on your screen." if real else
                    "Real size needs a bigger window, so it is shown to fit.")
        else:
            note = "Scaled to fit the window. Tap Real size to see it as large as it will be."
        self.info.config(text=f"Your pin: {size_txt}   |   {PROPS[self.v_scene.get()]}\n{note}")
        for b, on in ((self.b_real, self.real), (self.b_ruler, self.ruler)):
            b.configure(kind="accent" if on else "ghost")

    # ---- controls ----------------------------------------------------------------------
    def _scene(self):
        self._soon(0)

    def _pick(self, name):
        self.v_scene.set(name)
        self._soon(0)

    def _toggle_real(self):
        self.real = not self.real
        self._soon(0)

    def _toggle_ruler(self):
        self.ruler = not self.ruler
        self._soon(0)

    def _save(self):
        if self._face is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Save the preview", defaultextension=".png",
            initialfile=f"pin-preview-{self.v_scene.get()}.png",
            filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg")])
        if not path:
            return
        try:
            self._composed().save(path, quality=95)
        except OSError as e:
            messagebox.showerror("Could not save", str(e), parent=self)
