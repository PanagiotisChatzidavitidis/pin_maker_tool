"""Preview environments for the e-shop / bundle preview, drawn with Pillow only.

Six everyday settings, each showing the pins the way they would really be used:

    desk       Modern desk      flat pins on a felt desk mat
    school     School desk      flat pins on a lined notebook page
    backpack   Backpack         pins sewn / clipped onto ripstop fabric beside a zipper
    fridge     Fridge magnets   pins as magnets on brushed steel
    keychain   Coffee table     pins as keychains (eyelet, ring, ball chain, key ring)
    opener     Party table      pins as bottle openers beside beer bottles

A bundle picture is 420 x 280 mm (3:2) and holds up to ``MAX_PINS`` pins of one size at their
real size (they shrink only when they would not fit). A close-up is a tighter window on one
pin, at a higher pixel density. Everything is real-world millimetres; ``px`` is pixels per mm.
The look comes from ``scene`` (shadows, the pin dome and rim, grain), whose pixel density is
switched for the duration of each render.
"""

import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import ring as ring_mod
from . import scene as S

W_MM, H_MM = 420, 280                  # a bundle picture, in mm (3:2)
LONG_PX = 2520                         # every picture is this many pixels along its long edge
BUNDLE_PX = LONG_PX / W_MM             # 6 px per mm
MAX_PINS = 10
FOOT_MM = 20                           # the caption band under the picture ("Details")

# key, label, how the pin is presented
ENVS = (
    ("desk", "Modern desk", "flat"),
    ("school", "School desk", "flat"),
    ("backpack", "On a backpack", "fabric"),
    ("fridge", "Fridge magnets", "magnet"),
    ("keychain", "Keychains on a coffee table", "keychain"),
    ("opener", "Bottle openers on a party table", "opener"),
)
LABELS = {k: lab for k, lab, _ in ENVS}
KINDS = {k: kind for k, _, kind in ENVS}
NOUN = {"flat": "pins", "fabric": "pins", "magnet": "magnets", "keychain": "keychains",
        "opener": "bottle openers"}
# where the pins go (mm, in a 420 x 280 picture): left, top, right, bottom
STAGE = {"desk": (50, 86, 372, 252), "school": (78, 46, 342, 236),
         "backpack": (52, 84, 340, 252), "fridge": (36, 70, 340, 252),
         "keychain": (56, 34, 316, 248), "opener": (52, 120, 366, 256)}
# things in each scene that the pins must stay clear of (mm: left, top, right, bottom)
OBSTACLES = {
    "desk": [(0, 0, 150, 76), (150, 28, 285, 52), (298, 0, 420, 80)],
    "school": [(0, 0, 68, 280), (352, 0, 420, 280), (0, 0, 420, 24), (0, 254, 420, 280)],
    "backpack": [(0, 0, 420, 78), (344, 0, 420, 280)],
    "fridge": [(0, 0, 70, 62), (364, 0, 420, 280)],
    "keychain": [(326, 0, 420, 100), (200, 258, 300, 280)],
    "opener": [(0, 0, 420, 112), (0, 226, 50, 280), (380, 150, 420, 230)],
}
# how far each pin may be turned (degrees) and how much it may wander in its cell
TURN = {"flat": 9, "fabric": 4, "magnet": 6, "keychain": 14, "opener": 12}
SHADOWS = {
    "flat": ((0.5, 0.9, 1.0, 0.55), (1.8, 3.0, 4.5, 0.36)),
    "fabric": ((0.2, 0.4, 0.6, 0.62), (0.9, 1.5, 2.3, 0.38)),
    "magnet": ((0.3, 0.5, 0.5, 0.6), (1.0, 1.7, 2.3, 0.3)),
    "keychain": ((0.6, 1.0, 1.1, 0.5), (2.2, 3.4, 4.5, 0.32)),
    "opener": ((0.6, 1.0, 1.1, 0.5), (2.2, 3.4, 4.5, 0.32)),
}


class at_px:
    """``with at_px(6):`` makes every ``scene`` helper work at 6 pixels per millimetre."""

    def __init__(self, px):
        self.px = px

    def __enter__(self):
        self.old, S.PX = S.PX, self.px

    def __exit__(self, *exc):
        S.PX = self.old


# ---- small helpers -----------------------------------------------------------------------
def _nz(w, h, cw_mm, ch_mm, seed, px):
    """Smooth random texture whose cells are about cw_mm x ch_mm in size."""
    return S._noise(w, h, max(1, int(cw_mm * px)), max(1, int(ch_mm * px)), seed)


def _wood(w, h, px, dark, mid, light, seed=1, plank_mm=0, seam=(40, 24, 12)):
    n1, n2, n3 = _nz(w, h, 70, 0.7, seed, px), _nz(w, h, 30, 0.35, seed + 1, px), \
        _nz(w, h, 150, 9, seed + 2, px)
    bands = Image.blend(n1, n2, 0.5).point(lambda v: int(127 + 127 * math.sin(v / 255 * 22)))
    img = ImageOps.colorize(Image.blend(bands, n3, 0.45), dark, light, mid=mid)
    fine = _nz(w, h, 15, 0.12, seed + 3, px).filter(ImageFilter.GaussianBlur(0.6))
    img = ImageChops.multiply(img, ImageOps.colorize(fine, (226, 218, 208), (255, 255, 255)))
    if plank_mm:
        d = ImageDraw.Draw(img, "RGBA")
        y, i = plank_mm * px, 0
        while y < h:
            d.rectangle([0, y - 2, w, y + 1], fill=(*seam, 215))
            d.rectangle([0, y + 1, w, y + 3], fill=(255, 226, 180, 46))
            i += 1
            y += plank_mm * px
        # each plank has its own tone
        k, y = 0, 0
        while y < h:
            tone = ((255, 235, 200, 16), (0, 0, 0, 0), (50, 28, 10, 24))[k % 3]
            d.rectangle([0, y, w, y + plank_mm * px], fill=tone)
            k += 1
            y += plank_mm * px
    return img


def _shadow_under(img, mask, px, dx=1.5, dy=2.5, blur=4.0, op=0.35, col=(20, 14, 8)):
    """A soft drop shadow of ``mask`` (an 'L' image the size of img) onto img."""
    m = mask.filter(ImageFilter.GaussianBlur(blur * px)).point(lambda v: int(v * op))
    img.paste(Image.new("RGB", img.size, col), (round(dx * px), round(dy * px)), m)


def _round_mask(size, box, radius, ss=2):
    """An 'L' mask of a rounded rectangle ``box`` (pixels) on an image of ``size``."""
    m = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([v * ss for v in box], radius=radius * ss, fill=255)
    return m.resize(size, Image.LANCZOS)


def _col_profile(w, h, dark, mid, light, vertical=True, hi=0.3):
    """A cylinder's shading: dark edges, a bright stripe near ``hi`` (0-1) across the width."""
    n = w if vertical else h
    line = Image.new("L", (n, 1))
    for i in range(n):
        f = (i + 0.5) / n
        v = 0.30 + 0.70 * math.sin(math.pi * f) ** 0.8 + 0.5 * math.exp(-((f - hi) / 0.07) ** 2)
        line.putpixel((i, 0), max(0, min(255, int(v * 190))))
    g = line.resize((n, h)) if vertical else line.rotate(90, expand=True).resize((w, n))
    return ImageOps.colorize(g.resize((w, h)), dark, light, mid=mid)


# ---- objects -----------------------------------------------------------------------------
def mug(d=82):
    """A coffee mug seen from above: white ceramic, a dark coffee with a swirl, a handle."""
    px, ss = S.PX, 3
    size = (int((d + 34) * px), int((d + 6) * px))
    W, H = size[0] * ss, size[1] * ss
    cx, cy, r = (d / 2 + 3) * px * ss, H / 2, d / 2 * px * ss
    rgb = Image.new("RGB", (W, H), (0, 0, 0))
    a = Image.new("L", (W, H), 0)
    d_, da = ImageDraw.Draw(rgb), ImageDraw.Draw(a)
    hx0, hx1 = cx + r * 0.80, cx + r + 22 * px * ss
    for dd, col in ((d_, (236, 236, 238)), (da, 255)):
        dd.rounded_rectangle([hx0, cy - 12 * px * ss, hx1, cy + 12 * px * ss],
                             radius=11 * px * ss, fill=col)
    d_.rounded_rectangle([hx0 + 5 * px * ss, cy - 6.5 * px * ss, hx1 - 5.5 * px * ss,
                          cy + 6.5 * px * ss], radius=6 * px * ss, fill=(80, 82, 88))
    da.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    g = _diag_rgb(W, H, (176, 178, 186), (252, 252, 254))
    rgb.paste(g, (0, 0), Image.new("L", (W, H), 0).point(lambda v: 0))
    d_.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(240, 240, 242))
    d_.ellipse([cx - r * 0.93, cy - r * 0.93, cx + r * 0.93, cy + r * 0.93], fill=(206, 208, 214))
    ri = r * 0.86
    for i in range(24):
        t = i / 23
        rr = ri * (1 - t * 0.9)
        col = tuple(round(a_ + (b - a_) * t) for a_, b in zip((46, 26, 14), (176, 118, 64)))
        d_.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
    sw = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sw)
    for k, ang in enumerate((200, 250)):
        ds.arc([cx - ri * 0.62, cy - ri * 0.62, cx + ri * 0.62, cy + ri * 0.62], ang, ang + 150,
               fill=(244, 218, 178, 150), width=int(2.6 * px * ss))
    sw = sw.filter(ImageFilter.GaussianBlur(px * ss * 0.9))
    rgb.paste(sw, (0, 0), sw)
    d_.arc([cx - r * 0.96, cy - r * 0.96, cx + r * 0.96, cy + r * 0.96], 195, 285,
           fill=(255, 255, 255), width=int(1.6 * px * ss))
    d_.arc([cx - ri, cy - ri, cx + ri, cy + ri], 20, 100, fill=(24, 12, 6), width=int(px * ss))
    out = rgb.resize(size, Image.LANCZOS)
    out.putalpha(a.resize(size, Image.LANCZOS))
    return out


def _diag_rgb(w, h, c1, c2):
    return ImageOps.colorize(S._diag(w, h, flip=True), c1, c2)


def notebook(w_mm=148, h_mm=210, col=(36, 44, 58)):
    """A closed hardcover notebook with an elastic band and a faint embossed label."""
    px, ss = S.PX, 2
    w, h = int(w_mm * px), int(h_mm * px)
    base = ImageOps.colorize(S._diag(w * ss, h * ss), tuple(min(255, c + 22) for c in col),
                             tuple(max(0, c - 10) for c in col))
    d = ImageDraw.Draw(base, "RGBA")
    bx = int(w * ss * 0.84)
    d.rectangle([bx, 0, bx + 4 * px * ss, h * ss], fill=(12, 14, 18, 255))
    d.rectangle([bx, 0, bx + int(0.9 * px * ss), h * ss], fill=(255, 255, 255, 40))
    d.rounded_rectangle([w * ss * 0.2, h * ss * 0.12, w * ss * 0.62, h * ss * 0.12 + 3 * px * ss],
                        radius=px * ss, fill=(255, 255, 255, 46))
    d.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=int(3 * px * ss),
                        outline=(255, 255, 255, 60), width=ss * 2)
    d.rectangle([0, 0, 6 * px * ss, h * ss], fill=(0, 0, 0, 52))          # the spine
    out = S._grainy(base.resize((w, h), Image.LANCZOS), 6, 3)
    out.putalpha(_round_mask((w, h), (0, 0, w - 1, h - 1), 3 * px))
    return out


def pen(length=146, w_mm=10.0, col=(34, 38, 48)):
    """A ball-point pen lying flat: dark barrel, a silver clip and tip."""
    px, ss = S.PX, 3
    L, H = int(length * px), int(w_mm * px) + 2

    def paint(rgb, alpha, k):
        d, da = ImageDraw.Draw(rgb), ImageDraw.Draw(alpha)
        body = _col_profile(L * k, H * k, tuple(c // 3 for c in col), col,
                            tuple(min(255, c + 100) for c in col), vertical=False, hi=0.28)
        rgb.paste(body, (0, 0))
        da.rounded_rectangle([0, k, (L - 26 * px) * k, H * k - k], radius=H * k // 2, fill=255)
        tipx = (L - 26 * px) * k
        d.polygon([(tipx - 2 * k, k), (L * k - k, H * k / 2), (tipx - 2 * k, H * k - k)],
                  fill=(196, 200, 208))
        d.polygon([(tipx - 2 * k, k), (L * k - k, H * k / 2), (tipx - 2 * k, H * k / 2)],
                  fill=(238, 240, 246))
        da.polygon([(tipx - 2 * k, k), (L * k - k, H * k / 2), (tipx - 2 * k, H * k - k)], fill=255)
        d.rectangle([k * 18 * px, H * k * 0.30, k * 62 * px, H * k * 0.46], fill=(200, 204, 212))
        d.rectangle([k * 18 * px, H * k * 0.30, k * 62 * px, H * k * 0.34], fill=(250, 250, 255))
        d.rectangle([tipx - 5 * px * k, k, tipx - 2 * px * k, H * k - k], fill=(176, 180, 190))
    return S._sprite(L, H, paint, ss)


def ruler30(length=300, w_mm=32.0):
    """A yellow school ruler, in centimetres and millimetres."""
    px, ss = S.PX, 2
    w, h = int(length * px), int(w_mm * px)
    base = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=int(1.5 * px * ss),
                        fill=(244, 204, 74, 255), outline=(176, 134, 26, 255), width=ss * 2)
    d.rounded_rectangle([ss * 3, ss * 3, w * ss * 0.9, h * ss * 0.34], radius=int(px * ss),
                        fill=(255, 232, 150, 120))
    f = S._font(int(3.6 * px * ss))
    for mm in range(0, length - 4):
        x = (3 + mm) * px * ss
        ln = 8 if mm % 10 == 0 else 5.4 if mm % 5 == 0 else 3.2
        d.line([(x, 0), (x, ln * px * ss)], fill=(54, 40, 10, 255),
               width=max(1, int((0.30 if mm % 10 == 0 else 0.16) * px * ss)))
        if mm % 10 == 0 and mm:
            t = str(mm // 10)
            d.text((x - d.textlength(t, font=f) / 2, 8.6 * px * ss), t, font=f, fill=(54, 40, 10, 255))
    out = base.resize((w, h), Image.LANCZOS)
    return out


def eraser(w_mm=42, h_mm=19):
    """A white block eraser in a blue paper sleeve."""
    px, ss = S.PX, 3
    w, h = int(w_mm * px), int(h_mm * px)
    img = Image.new("RGB", (w * ss, h * ss), (246, 246, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([w * ss * 0.28, 0, w * ss * 0.86, h * ss], fill=(46, 96, 176))
    d.rectangle([w * ss * 0.28, 0, w * ss * 0.86, h * ss * 0.2], fill=(86, 134, 210))
    d.rectangle([w * ss * 0.34, h * ss * 0.4, w * ss * 0.80, h * ss * 0.62], fill=(236, 240, 250))
    d.rectangle([0, h * ss * 0.8, w * ss, h * ss], fill=(0, 0, 0))
    img = Image.blend(img, ImageOps.colorize(S._diag(w * ss, h * ss), (190, 190, 200), (255, 255, 255)), 0.28)
    out = S._grainy(img.resize((w, h), Image.LANCZOS), 4, 8)
    out.putalpha(_round_mask((w, h), (0, 0, w - 1, h - 1), 2 * px))
    return out


def paper_page(w_mm, h_mm, line_mm=8.0, margin_mm=30.0):
    """A page of lined notebook paper with a red margin line."""
    px, ss = S.PX, 1
    w, h = int(w_mm * px), int(h_mm * px)
    img = ImageOps.colorize(_nz(w, h, 120, 100, 71, px), (236, 236, 232), (252, 252, 250))
    d = ImageDraw.Draw(img)
    y = 22 * px
    while y < h - 6 * px:
        d.line([(0, y), (w, y)], fill=(154, 184, 220), width=max(1, int(0.22 * px)))
        y += line_mm * px
    d.line([(margin_mm * px, 0), (margin_mm * px, h)], fill=(226, 120, 118), width=max(1, int(0.3 * px)))
    d.line([(margin_mm * px + 1.1 * px, 0), (margin_mm * px + 1.1 * px, h)], fill=(226, 120, 118),
           width=max(1, int(0.2 * px)))
    for i in range(3):                                         # punched holes
        cy = h * (0.2 + 0.3 * i)
        r = 3.2 * px
        d.ellipse([9 * px - r, cy - r, 9 * px + r, cy + r], fill=(196, 196, 192))
        d.ellipse([9 * px - r + 1, cy - r + 1, 9 * px + r - 1, cy + r - 1], fill=(120, 108, 92))
    out = img.convert("RGBA")
    out.putalpha(Image.new("L", (w, h), 255))
    return out


def sticky_note(s_mm=76, col=(250, 222, 96)):
    """A yellow sticky note with a few hand-written lines."""
    px = S.PX
    s = int(s_mm * px)
    img = ImageOps.colorize(S._diag(s, s, flip=True), tuple(c - 22 for c in col), (255, 242, 150))
    d = ImageDraw.Draw(img)
    rng = random.Random(5)
    y = 14 * px
    for _ in range(5):
        x, n = 8 * px, rng.randint(3, 5)
        for __ in range(n):
            wd = rng.uniform(6, 14) * px
            d.line([(x, y), (x + wd, y + rng.uniform(-0.6, 0.6) * px)], fill=(74, 62, 54),
                   width=max(1, int(0.55 * px)))
            x += wd + 2.4 * px
            if x > s - 10 * px:
                break
        y += 9 * px
    out = img.convert("RGBA")
    out.putalpha(Image.new("L", (s, s), 255))
    return out


def bottle(scale=1.0, H=228, D=60):
    """A beer bottle standing up, seen from the front: amber glass with a cream label, a
    glint down one side, drops of condensation and a crown cap. ``scale`` < 1 puts it further
    away (it is drawn smaller)."""
    px, ss = S.PX, 3
    u = px * scale * ss
    W, HH = int((D + 8) * u), int((H + 4) * u)
    cx = W / 2
    r_body, r_neck = D / 2, 13.0

    def half(y_mm):                       # half-width (mm) at a height above the base
        if y_mm < 0 or y_mm > 224:
            return 0
        if y_mm < 112:
            return r_body - 6 * max(0, 1 - y_mm / 6) ** 2 if y_mm < 6 else r_body
        if y_mm < 152:
            t = (y_mm - 112) / 40
            t = t * t * (3 - 2 * t)
            return r_body + (r_neck - r_body) * t
        if y_mm < 208:
            return r_neck
        if y_mm < 216:
            return r_neck + 2.0
        return 14.4
    mask = Image.new("L", (W, HH), 0)
    flat = Image.new("RGB", (W, HH), (128, 66, 20))
    shade = Image.new("L", (W, HH), 0)
    base_prof = Image.new("L", (256, 1))
    for i in range(256):
        f = (i + 0.5) / 256
        v = 0.30 + 0.70 * math.sin(math.pi * f) ** 0.8 + 0.7 * math.exp(-((f - 0.25) / 0.05) ** 2) \
            + 0.18 * math.exp(-((f - 0.88) / 0.04) ** 2)
        base_prof.putpixel((i, 0), max(0, min(255, int(v * 170))))
    md = ImageDraw.Draw(mask)
    for y in range(HH):
        ymm = (HH - 1 - y) / u - 2
        hw = half(ymm) * u
        if hw < 1:
            continue
        x0, x1 = int(cx - hw), int(cx + hw)
        md.line([(x0, y), (x1, y)], fill=255)
        shade.paste(base_prof.resize((max(1, x1 - x0 + 1), 1), Image.BILINEAR), (x0, y))
    fd = ImageDraw.Draw(flat)
    def ypx(ymm):
        return HH - (ymm + 2) * u
    # thinner glass above the liquid, a pale cap seal, then the label
    fd.rectangle([0, 0, W, ypx(150)], fill=(168, 96, 34))
    fd.rectangle([0, ypx(224), W, ypx(212)], fill=(176, 104, 40))
    lab0, lab1 = ypx(98), ypx(44)
    fd.rectangle([cx - r_body - 1, lab0, cx + r_body + 1, lab1], fill=(238, 228, 200))
    fd.rectangle([cx - r_body - 1, lab0, cx + r_body + 1, lab0 + 6 * u], fill=(156, 38, 30))
    fd.rectangle([cx - r_body - 1, lab1 - 6 * u, cx + r_body + 1, lab1], fill=(156, 38, 30))
    my = (lab0 + lab1) / 2
    fd.ellipse([cx - 13 * u, my - 13 * u, cx + 13 * u, my + 13 * u], outline=(70, 46, 24), width=int(1.6 * u))
    fd.ellipse([cx - 6.5 * u, my - 6.5 * u, cx + 6.5 * u, my + 6.5 * u], fill=(190, 148, 66))
    for k in (-1, 1):
        fd.line([(cx + k * 16 * u, my), (cx + k * 24 * u, my)], fill=(70, 46, 24), width=int(1.4 * u))
    # the crown cap
    fd.rectangle([cx - 14.4 * u, ypx(224), cx + 14.4 * u, ypx(216)], fill=(214, 168, 70))
    for i in range(-7, 8):
        fd.line([(cx + i * 1.9 * u, ypx(224)), (cx + i * 1.9 * u, ypx(216))], fill=(150, 112, 38), width=max(1, int(0.5 * u)))
    glass = ImageChops.multiply(flat, ImageOps.colorize(shade, (24, 20, 18), (255, 255, 255)))
    # condensation
    drops = Image.new("RGBA", (W, HH), (0, 0, 0, 0))
    dd = ImageDraw.Draw(drops)
    rng = random.Random(41)
    for _ in range(70):
        y_mm = rng.uniform(4, 108)
        if 44 <= y_mm <= 98:
            continue
        x = cx + rng.uniform(-0.9, 0.9) * half(y_mm) * u
        rr = rng.uniform(0.5, 1.5) * u
        yy = ypx(y_mm)
        dd.ellipse([x - rr, yy - rr * 1.3, x + rr, yy + rr * 1.3], fill=(255, 240, 220, 70))
        dd.ellipse([x - rr * 0.5, yy - rr * 1.1, x, yy - rr * 0.3], fill=(255, 255, 255, 210))
        dd.arc([x - rr, yy - rr * 1.3, x + rr, yy + rr * 1.3], 20, 160, fill=(30, 14, 6, 150), width=max(1, int(0.3 * u)))
    glass = glass.convert("RGBA")
    glass.alpha_composite(drops)
    out = glass.convert("RGB").resize((W // ss, HH // ss), Image.LANCZOS)
    out.putalpha(mask.resize((W // ss, HH // ss), Image.LANCZOS))
    return out


def bottle_cap(d_mm=27):
    """A crown cap lying face up: a crimped gold edge and a printed top."""
    px, ss = S.PX, 4
    size = int(d_mm * px) + 4
    s = size * ss
    c, r = s / 2, d_mm * px * ss / 2
    rgb = Image.new("RGB", (s, s), (0, 0, 0))
    a = Image.new("L", (s, s), 0)
    pts = []
    for i in range(42):
        ang = math.tau * i / 42
        rr = r * (1.0 if i % 2 == 0 else 0.93)
        pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
    ImageDraw.Draw(a).polygon(pts, fill=255)
    g = ImageOps.colorize(S._diag(s, s, flip=True), (150, 110, 34), (252, 226, 140), mid=(206, 160, 70))
    rgb.paste(g, (0, 0))
    d = ImageDraw.Draw(rgb)
    d.ellipse([c - r * 0.74, c - r * 0.74, c + r * 0.74, c + r * 0.74], fill=(176, 36, 30))
    d.ellipse([c - r * 0.74, c - r * 0.74, c + r * 0.74, c + r * 0.74], outline=(240, 214, 120), width=int(r * 0.06))
    d.ellipse([c - r * 0.3, c - r * 0.3, c + r * 0.3, c + r * 0.3], fill=(244, 232, 200))
    d.polygon(pts, outline=(96, 68, 20))
    out = rgb.resize((size, size), Image.LANCZOS)
    out.putalpha(a.resize((size, size), Image.LANCZOS))
    return out


def lime_slice(d_mm=46):
    """A slice of lime from above."""
    px, ss = S.PX, 3
    size = int(d_mm * px) + 4
    s = size * ss
    c, r = s / 2, d_mm * px * ss / 2
    rgb = Image.new("RGB", (s, s), (0, 0, 0))
    a = Image.new("L", (s, s), 0)
    ImageDraw.Draw(a).ellipse([c - r, c - r, c + r, c + r], fill=255)
    d = ImageDraw.Draw(rgb)
    d.ellipse([c - r, c - r, c + r, c + r], fill=(70, 130, 36))
    d.ellipse([c - r * 0.92, c - r * 0.92, c + r * 0.92, c + r * 0.92], fill=(226, 238, 180))
    for i in range(8):
        ang = math.tau * i / 8 + 0.2
        d.polygon([(c + r * 0.1 * math.cos(ang), c + r * 0.1 * math.sin(ang)),
                   (c + r * 0.84 * math.cos(ang - 0.28), c + r * 0.84 * math.sin(ang - 0.28)),
                   (c + r * 0.84 * math.cos(ang + 0.28), c + r * 0.84 * math.sin(ang + 0.28))],
                  fill=(170, 206, 70))
    d.ellipse([c - r * 0.07, c - r * 0.07, c + r * 0.07, c + r * 0.07], fill=(240, 246, 214))
    out = rgb.resize((size, size), Image.LANCZOS)
    out.putalpha(a.resize((size, size), Image.LANCZOS))
    return out


def coaster(d_mm=96, col=(170, 128, 84)):
    """A round cork coaster."""
    px, ss = S.PX, 2
    size = int(d_mm * px)
    base = ImageOps.colorize(_nz(size * ss, size * ss, 1.2, 1.2, 81, px), tuple(c - 40 for c in col),
                             tuple(min(255, c + 36) for c in col))
    m = Image.new("L", base.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, size * ss - 1, size * ss - 1], fill=255)
    out = base.resize((size, size), Image.LANCZOS)
    out.putalpha(m.resize((size, size), Image.LANCZOS))
    return out


def hardcover_book(w_mm=170, h_mm=230, col=(44, 92, 96)):
    """A closed hardcover book: coloured cloth, a title block and a spine."""
    spr = notebook(w_mm, h_mm, col)
    px = S.PX
    d = ImageDraw.Draw(spr)
    d.rectangle([int(w_mm * px * 0.28), int(h_mm * px * 0.3), int(w_mm * px * 0.76),
                 int(h_mm * px * 0.3) + int(1.4 * px)], fill=(226, 206, 150))
    d.rectangle([int(w_mm * px * 0.28), int(h_mm * px * 0.3) + int(5 * px), int(w_mm * px * 0.6),
                 int(h_mm * px * 0.3) + int(6.2 * px)], fill=(226, 206, 150))
    return spr


# ---- surfaces and scenes -----------------------------------------------------------------
def _felt(w, h, px, col=(64, 68, 76)):
    n = _nz(w, h, 0.5, 0.5, 91, px)
    cloud = _nz(w, h, 120, 100, 92, px).filter(ImageFilter.GaussianBlur(20))
    img = ImageOps.colorize(n, tuple(c - 14 for c in col), tuple(c + 14 for c in col))
    return ImageChops.multiply(img, ImageOps.colorize(cloud, (214, 214, 214), (255, 255, 255)))


def _stitch_line(img, pts, col, px, length=3.0, gap=1.2):
    S._stitches(img, pts, length, gap, col)


def _paint_desk(W, H, px, close, dense):
    w, h = int(W * px), int(H * px)
    f = W / W_MM
    img = _wood(w, h, px, (178, 150, 112), (216, 192, 158), (240, 222, 192), seed=3)
    # a felt desk mat with stitched edges
    top = (70 if not close else 20) * f if not close else 22 * f
    mat = (int(26 * f * px), int(top * px), int((W_MM - 26) * f * px), int((H_MM - 10) * f * px) if not close
           else h + 40 * px)
    if close:
        mat = (-40 * px, int(26 * f * px), w + 40 * px, h + 40 * px)
    mm = _round_mask((w, h), mat, 8 * px)
    _shadow_under(img, mm, px, 1.2, 2.2, 3.5, 0.34)
    img.paste(_felt(w, h, px), (0, 0), mm)
    inner = (mat[0] + 3 * px, mat[1] + 3 * px, mat[2] - 3 * px, mat[3] - 3 * px)
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle(inner, radius=6 * px, outline=(36, 38, 44, 200), width=max(1, int(0.5 * px)))
    if not close:
        S._put(img, notebook(), 74 * px, -38 * px, -4)
        S._put(img, pen(), 214 * px, 40 * px, 4)
        S._put(img, mug(), 340 * px, 34 * px, 0)
    return S._vignette(img, 0.26)


def _paint_school(W, H, px, close, dense):
    w, h = int(W * px), int(H * px)
    f = W / W_MM
    # warm beige laminate with a speckle, like a classroom desk
    lam = ImageOps.colorize(_nz(w, h, 0.6, 0.6, 5, px), (206, 188, 156), (230, 214, 182))
    cloud = _nz(w, h, 200, 160, 6, px).filter(ImageFilter.GaussianBlur(30))
    img = ImageChops.multiply(lam, ImageOps.colorize(cloud, (226, 222, 214), (255, 255, 255)))
    if not close:
        # the notebook page sits slightly turned under the pins
        page = paper_page(284, 244)
        S._put(img, page, 210 * px, 140 * px, -1.2, ((0.3, 0.5, 0.6, 0.45), (1.2, 2.0, 3.0, 0.28)))
        S._put(img, S.pencil(), 215 * px, 14 * px, 0.8)
        S._put(img, ruler30(), 214 * px, 270 * px, 0)
        S._put(img, eraser(), 372 * px, 62 * px, 12)
        S._put(img, S.coin(), 384 * px, 218 * px, 0)
    else:
        page = paper_page(W + 40, H + 40)
        S._put(img, page, w / 2, h / 2, 0, ((0.3, 0.5, 0.6, 0.45), (1.2, 2.0, 3.0, 0.28)))
    return S._vignette(img, 0.24)


def _paint_backpack(W, H, px, close, dense):
    w, h = int(W * px), int(H * px)
    f = W / W_MM
    nz = _nz(w, h, 0.4, 0.4, 101, px)
    base = ImageOps.colorize(nz, (30, 52, 44), (48, 80, 66))
    # ripstop: a fine grid of heavier threads every 5 mm
    grid = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(grid)
    step = max(2, int(5 * px))
    for x in range(0, w, step):
        gd.line([(x, 0), (x, h)], fill=255, width=max(1, int(0.3 * px)))
    for y in range(0, h, step):
        gd.line([(0, y), (w, y)], fill=255, width=max(1, int(0.3 * px)))
    img = Image.composite(Image.new("RGB", (w, h), (74, 112, 94)), base, grid.point(lambda v: v // 6))
    cloud = _nz(w, h, 140, 110, 102, px).filter(ImageFilter.GaussianBlur(24))
    img = ImageChops.multiply(img, ImageOps.colorize(cloud, (206, 214, 210), (255, 255, 255)))
    zy = 34 * f
    # the pocket: a panel below the zipper with a stitched seam all round
    d = ImageDraw.Draw(img, "RGBA")
    tape = (int(-10 * px), int((zy - 7) * px), w + 10 * px, int((zy + 7) * px))
    d.rectangle(tape, fill=(22, 34, 30, 255))
    for yy in (zy - 7, zy + 7):
        d.line([(0, yy * px), (w, yy * px)], fill=(8, 12, 10, 200), width=max(1, int(0.5 * px)))
    # zipper teeth: alternating metal teeth along the centre line
    t, k = 0.0, 0
    while t * px < w:
        x = t * px
        yo = (-0.9 if k % 2 == 0 else 0.9) * px
        d.rounded_rectangle([x, zy * px + yo - 1.1 * px, x + 1.7 * px, zy * px + yo + 1.1 * px],
                            radius=int(0.5 * px), fill=(188, 192, 200, 255))
        d.line([(x, zy * px + yo - 1.0 * px), (x + 1.7 * px, zy * px + yo - 1.0 * px)],
               fill=(250, 252, 255, 220), width=max(1, int(0.3 * px)))
        t += 1.45
        k += 1
    S._stitches(img, ((-2, zy - 9.6), (W + 2, zy - 9.6)), 3.0, 1.0, (190, 196, 190))
    S._stitches(img, ((-2, zy + 9.6), (W + 2, zy + 9.6)), 3.0, 1.0, (190, 196, 190))
    # puller: a metal slider with a fabric tab
    sx = (330 if not close else 150) * f if not close else W * 0.78
    tab = Image.new("RGBA", (int(10 * px), int(34 * px)), (0, 0, 0, 0))
    td = ImageDraw.Draw(tab)
    td.rounded_rectangle([0, 0, tab.width - 1, tab.height - 1], radius=int(3 * px), fill=(18, 22, 20, 255))
    td.ellipse([tab.width / 2 - 1.8 * px, 3 * px, tab.width / 2 + 1.8 * px, 6.6 * px], fill=(70, 80, 76, 255))
    S._put(img, tab, sx * px, (zy + 20) * px, 3, ((0.4, 0.7, 0.8, 0.5), (1.4, 2.2, 3.0, 0.3)))
    slider = Image.new("RGBA", (int(13 * px), int(9 * px)), (0, 0, 0, 0))
    sd = ImageDraw.Draw(slider)
    sd.rounded_rectangle([0, 0, slider.width - 1, slider.height - 1], radius=int(2 * px), fill=(176, 180, 188, 255))
    sd.rounded_rectangle([int(px), int(px), slider.width - 1 - int(px), int(2.4 * px)], radius=int(px), fill=(246, 248, 252, 255))
    S._put(img, slider, sx * px, zy * px, 0, ((0.4, 0.7, 0.8, 0.5), (1.2, 2.0, 2.6, 0.3)))
    if not close:
        # side-pocket webbing with box stitching on the right
        strap = Image.new("RGBA", (int(28 * px), h), (0, 0, 0, 0))
        sn = _nz(strap.width, h, 0.5, 5, 103, px)
        strap.paste(ImageOps.colorize(sn, (20, 28, 26), (44, 58, 52)), (0, 0))
        S._put(img, strap, (W_MM - 14) * px, h / 2, 0, ((0.4, 0.6, 0.8, 0.45), (1.2, 1.8, 2.6, 0.25)))
        for x in (W_MM - 26, W_MM - 2):
            S._stitches(img, ((x, 20), (x, H_MM + 2)), 3.2, 1.2, (210, 214, 206))
    return S._vignette(img, 0.3)


def _paint_fridge(W, H, px, close, dense):
    w, h = int(W * px), int(H * px)
    f = W / W_MM
    streak = _nz(w, h, 0.22, 140, 111, px)
    broad = _nz(w, h, 70, 220, 112, px).filter(ImageFilter.GaussianBlur(6))
    tone = Image.blend(streak, broad, 0.35)
    img = ImageOps.colorize(tone, (156, 160, 168), (226, 230, 234), mid=(192, 196, 202))
    sheen = ImageOps.colorize(S._diag(w, h, flip=True).filter(ImageFilter.GaussianBlur(40)), (206, 208, 214),
                              (255, 255, 255))
    img = ImageChops.multiply(img, sheen)
    hx = (W_MM - 44) * f if not close else W - 32
    hw, hy0, hy1 = 22, -4, H + 4
    if not close:
        # a paper note held by a plain magnet, and a take-away menu
        S._put(img, sticky_note(60, (170, 214, 240)), 36 * px, 28 * px, -7)
    # the handle: a brushed bar on two brackets
    hh = int((hy1 - hy0) * px)
    bar = _col_profile(int(hw * px), hh, (92, 96, 104), (178, 182, 190), (250, 252, 255), vertical=True, hi=0.26)
    bar = bar.convert("RGBA")
    bar.putalpha(_round_mask(bar.size, (0, 0, bar.width - 1, bar.height - 1), 9 * px))
    for yy in (0.1, 0.9):
        br = Image.new("RGBA", (int((hw + 14) * px), int(10 * px)), (0, 0, 0, 0))
        ImageDraw.Draw(br).rounded_rectangle([0, 0, br.width - 1, br.height - 1], radius=int(3 * px),
                                             fill=(120, 124, 132, 255))
        S._put(img, br, (hx + hw / 2) * px, hh * yy + hy0 * px, 0, ((0.4, 0.7, 0.9, 0.4),))
    S._put(img, bar, (hx + hw / 2) * px, hh / 2 + hy0 * px, 0, ((1.0, 1.6, 1.6, 0.4), (4.0, 5.0, 6.0, 0.3)))
    # a faint door seam
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([int((hx - 26) * px), 0, int((hx - 25) * px), h], fill=(60, 64, 72, 70))
    return S._vignette(img, 0.2)


def _paint_keychain(W, H, px, close, dense):
    w, h = int(W * px), int(H * px)
    f = W / W_MM
    img = _wood(w, h, px, (46, 28, 18), (86, 56, 36), (128, 90, 62), seed=13, plank_mm=int(88 * 1.0) if not close else 0,
                seam=(14, 8, 4))
    if not close:
        S._put(img, coaster(), 376 * px, 44 * px, 0, ((0.4, 0.6, 0.8, 0.5), (1.4, 2.2, 3.0, 0.3)))
        S._put(img, mug(78), 376 * px, 44 * px, 0, ((0.8, 1.2, 1.4, 0.5), (2.6, 3.6, 5.0, 0.32)))
        S._put(img, pen(), 250 * px, 266 * px, -3)
    return S._vignette(img, 0.3)


def _reflect(img, spr, cx_px, base_px, fade=0.22, depth_mm=40):
    """A faint mirror image of ``spr`` (standing with its foot at base_px) on a polished table."""
    px = S.PX
    flip = spr.transpose(Image.FLIP_TOP_BOTTOM)
    h = min(flip.height, int(depth_mm * px))
    flip = flip.crop((0, 0, flip.width, h))
    ramp = Image.linear_gradient("L").rotate(180).resize((flip.width, h)).point(lambda v: int(v * fade))
    a = ImageChops.multiply(flip.getchannel("A"), ramp)
    img.paste(flip.convert("RGB"), (int(cx_px - flip.width / 2), int(base_px)), a.filter(ImageFilter.GaussianBlur(1.2)))


def _paint_opener(W, H, px, close, dense):
    w, h = int(W * px), int(H * px)
    f = W / W_MM
    img = _wood(w, h, px, (56, 38, 28), (98, 68, 48), (140, 102, 72), seed=17, plank_mm=94 if not close else 0,
                seam=(12, 8, 5))
    img = ImageChops.multiply(img, ImageOps.colorize(S._diag(w, h, flip=True), (214, 198, 180), (255, 246, 234)))
    if not close:
        edge = 104                                           # the back edge of the table, in mm
        wall = ImageOps.colorize(Image.linear_gradient("L").resize((w, int(edge * px))),
                                 (22, 15, 12), (54, 38, 28))
        bk = Image.new("RGBA", wall.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(bk)
        rng = random.Random(23)
        for _ in range(26):
            r = rng.uniform(5, 15) * px
            x, y = rng.uniform(0.02, 0.99) * w, rng.uniform(0.05, 0.92) * wall.height
            bd.ellipse([x - r, y - r, x + r, y + r],
                       fill=(255, rng.randint(170, 214), rng.randint(84, 140), rng.randint(26, 70)))
        bk = bk.filter(ImageFilter.GaussianBlur(px * 2.2))
        wall.paste(bk, (0, 0), bk)
        img.paste(wall, (0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        # the table's back edge: a lit lip and a shadow falling onto the wood
        lip = int(edge * px)
        d.rectangle([0, lip - int(1.2 * px), w, lip], fill=(150, 112, 78, 255))
        shd = Image.linear_gradient("L").resize((w, int(14 * px))).point(lambda v: int((255 - v) * 0.55))
        img.paste(Image.new("RGB", shd.size, (14, 8, 4)), (0, lip), shd)
        base = (edge + 7) * px
        spr = bottle(0.42)
        for x, ang in ((70, 0), (130, 0), (344, 0)):
            _reflect(img, spr, x * px, base)
            S._put(img, spr, x * px, base - spr.height / 2, 0, ((0.4, 0.8, 1.2, 0.5), (2.4, 1.6, 4.0, 0.34)))
        S._put(img, bottle_cap(), 392 * px, 168 * px, 20, ((0.4, 0.6, 0.6, 0.5), (1.2, 1.8, 2.0, 0.3)))
        S._put(img, bottle_cap(), 396 * px, 214 * px, -30, ((0.4, 0.6, 0.6, 0.5), (1.2, 1.8, 2.0, 0.3)))
        S._put(img, lime_slice(), 22 * px, 244 * px, 0)
    tint = Image.new("RGB", (w, h), (255, 214, 160))
    img = Image.blend(img, ImageChops.multiply(img, tint), 0.2)
    return S._vignette(img, 0.42)


PAINT = {"desk": _paint_desk, "school": _paint_school, "backpack": _paint_backpack,
         "fridge": _paint_fridge, "keychain": _paint_keychain, "opener": _paint_opener}


@lru_cache(maxsize=6)
def backdrop(env, w_mm=W_MM, dense=False):
    """The empty scene for ``env`` as an RGB picture ``LONG_PX`` wide (cached). A close-up is a
    smaller ``w_mm`` window drawn at a higher pixel density."""
    h_mm = w_mm * 2 / 3
    px = LONG_PX / w_mm
    close = w_mm != W_MM
    with at_px(px):
        img = PAINT[env](w_mm, h_mm, px, close, dense)
    return _photo(img, env, px, close)


def _photo(img, env, px, close):
    """Make the painting read as a photograph: a shallow depth of field (everything away from
    where the pins go is slightly soft), a gentle warm grade and a little bloom in the lights."""
    w, h = img.size
    soft = img.filter(ImageFilter.GaussianBlur(0.75 * px))
    if close:
        m = Image.radial_gradient("L").resize((w, h), Image.BICUBIC).point(lambda v: max(0, min(255, (v - 120) * 2)))
    else:
        x0, y0, x1, y1 = STAGE[env]
        m = Image.new("L", (w, h), 255)
        ImageDraw.Draw(m).rectangle([(x0 - 6) * px, (y0 - 6) * px, (x1 + 6) * px, (y1 + 6) * px], fill=0)
        m = m.filter(ImageFilter.GaussianBlur(9 * px))
    img = Image.composite(soft, img, m)
    glow = img.filter(ImageFilter.GaussianBlur(6 * px)).point(lambda v: max(0, v - 170) * 3)
    img = ImageChops.screen(img, glow.point(lambda v: v // 6))
    warm = Image.new("RGB", (w, h), (255, 246, 232))
    return Image.blend(img, ImageChops.multiply(img, warm), 0.5)


# ---- the pin, as it is presented in each environment --------------------------------------
def _metal_dot(d, cx, cy, r, ss, dark=(98, 100, 108), light=(244, 246, 250)):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dark)
    d.ellipse([cx - r * 0.82, cy - r * 0.82, cx + r * 0.5, cy + r * 0.5], fill=(190, 194, 202))
    d.ellipse([cx - r * 0.62, cy - r * 0.66, cx - r * 0.1, cy - r * 0.2], fill=light)


def _ring(d, box, wire, ss):
    cx0, cy0, cx1, cy1 = box
    d.ellipse(box, outline=(84, 88, 96), width=wire + ss)
    d.ellipse(box, outline=(196, 200, 208), width=wire)
    d.arc([cx0 + wire * 0.3, cy0 + wire * 0.3, cx1 - wire * 0.3, cy1 - wire * 0.3], 200, 280,
          fill=(255, 255, 255), width=max(1, wire // 2))


def keychain_unit(base, fw, fh):
    """Pin plus eyelet, split ring, ball chain and key ring. Returns (RGBA, (ax, ay)): the
    picture and where the middle of the pin is in it."""
    px, ss = S.PX, 3
    W, H = base.size
    top = int((5.5 + 7 + 17 + 19) * px)
    w = max(W, int(28 * px))
    out = Image.new("RGBA", (w * ss, (H + top) * ss), (0, 0, 0, 0))
    ox = (w - W) // 2
    rgb = Image.new("RGB", out.size, (0, 0, 0))
    a = Image.new("L", out.size, 0)
    d, da = ImageDraw.Draw(rgb), ImageDraw.Draw(a)
    cx = w * ss / 2
    pin_top = top * ss
    # eyelet tab
    tw, th = min(10, max(6, fw * 0.24)) * px * ss, 8 * px * ss
    ty0 = pin_top - 5.6 * px * ss
    for dd, col in ((d, (150, 154, 162)), (da, 255)):
        dd.rounded_rectangle([cx - tw / 2, ty0, cx + tw / 2, ty0 + th], radius=tw / 2, fill=col)
    d.rounded_rectangle([cx - tw / 2 + ss, ty0 + ss, cx + tw / 2 - ss, ty0 + th * 0.6], radius=tw / 2,
                        fill=(214, 218, 226))
    d.ellipse([cx - 1.4 * px * ss, ty0 + 1.2 * px * ss, cx + 1.4 * px * ss, ty0 + 3.8 * px * ss], fill=(40, 40, 46))
    # split ring through the hole
    rw = max(3, int(0.9 * px * ss))
    rb = [cx - 4.6 * px * ss, ty0 - 7 * px * ss, cx + 4.6 * px * ss, ty0 + 5 * px * ss]
    _ring(d, rb, rw, ss)
    ImageDraw.Draw(a).ellipse(rb, outline=255, width=rw + ss)
    # the ball chain, a little wavy
    y, n = ty0 - 6.5 * px * ss, 0
    br = 1.25 * px * ss
    while y > (top - 5.5 - 7 - 17) * px * ss + 2 * px * ss:
        x = cx + math.sin(n * 0.35) * 0.6 * px * ss
        _metal_dot(d, x, y, br, ss)
        da.ellipse([x - br, y - br, x + br, y + br], fill=255)
        y -= br * 1.7
        n += 1
    # a connector and the key ring
    ky = y - 2 * px * ss
    d.rounded_rectangle([cx - 2 * px * ss, ky - 2.4 * px * ss, cx + 2 * px * ss, ky + 1.4 * px * ss], radius=px * ss,
                        fill=(190, 194, 202))
    da.rounded_rectangle([cx - 2 * px * ss, ky - 2.4 * px * ss, cx + 2 * px * ss, ky + 1.4 * px * ss], radius=px * ss,
                         fill=255)
    kr = 9 * px * ss
    kb = [cx - kr, ky - 2 * kr + 1 * px * ss, cx + kr, ky + 1 * px * ss]
    _ring(d, kb, int(1.5 * px * ss), ss)
    ImageDraw.Draw(a).ellipse(kb, outline=255, width=int(1.5 * px * ss) + ss)
    rgb = rgb.resize((w, H + top), Image.LANCZOS)
    a = a.resize((w, H + top), Image.LANCZOS)
    rgb.putalpha(a)
    out = rgb
    out.alpha_composite(base, (ox, top))
    return out, (w / 2, top + H / 2)


def opener_front(base, fw, fh):
    """A pin with an eyelet and one key ring, the way a bottle opener badge hangs."""
    px, ss = S.PX, 3
    W, H = base.size
    top = int(19 * px)
    w = max(W, int(18 * px))
    full = (w * ss, (H + top) * ss)
    rgb = Image.new("RGB", full, (0, 0, 0))
    a = Image.new("L", full, 0)
    d, da = ImageDraw.Draw(rgb), ImageDraw.Draw(a)
    cx = w * ss / 2
    tw, th = min(10, max(6, fw * 0.22)) * px * ss, 8 * px * ss
    ty0 = top * ss - 5.6 * px * ss
    for dd, col in ((d, (150, 154, 162)), (da, 255)):
        dd.rounded_rectangle([cx - tw / 2, ty0, cx + tw / 2, ty0 + th], radius=tw / 2, fill=col)
    d.rounded_rectangle([cx - tw / 2 + ss, ty0 + ss, cx + tw / 2 - ss, ty0 + th * 0.6], radius=tw / 2, fill=(214, 218, 226))
    d.ellipse([cx - 1.4 * px * ss, ty0 + 1.2 * px * ss, cx + 1.4 * px * ss, ty0 + 3.8 * px * ss], fill=(40, 40, 46))
    wire = max(3, int(1.2 * px * ss))
    rb = [cx - 7 * px * ss, ty0 - 11 * px * ss, cx + 7 * px * ss, ty0 + 4 * px * ss]
    _ring(d, rb, wire, ss)
    ImageDraw.Draw(a).ellipse(rb, outline=255, width=wire + ss)
    rgb = rgb.resize((w, H + top), Image.LANCZOS)
    a = a.resize((w, H + top), Image.LANCZOS)
    rgb.putalpha(a)
    rgb.alpha_composite(base, ((w - W) // 2, top))
    return rgb, (w / 2, top + H / 2)


def back_unit(shape, fw, fh):
    """The back of a bottle opener pin: polished steel with the opening cut through it (so the
    table shows through). No chain."""
    px, ss = S.PX, 3
    pad = 6
    W, H = int(fw * px) + 2 * pad, int(fh * px) + 2 * pad
    mask = ring_mod.mask(shape, fw, fh, 0, (W, H), px, px, W / 2, H / 2, 3)
    metal = ImageOps.colorize(S._diag(W, H, flip=True), (168, 172, 180), (252, 252, 255), mid=(214, 218, 226))
    metal = ImageChops.multiply(metal, ImageOps.colorize(_nz(W, H, 6, 6, 61, px), (232, 232, 234), (255, 255, 255)))
    art = metal.copy()
    rim = max(2, int(0.7 * px))
    inner = mask.filter(ImageFilter.MinFilter(2 * rim + 1))
    art.paste(ImageOps.colorize(S._diag(W, H, flip=False), (120, 124, 132), (236, 238, 244)), (0, 0),
              ImageChops.subtract(mask, inner))
    # the opening: a rounded slot with a hump on its top edge, as on a real opener
    hole = Image.new("L", (W * ss, H * ss), 0)
    hd = ImageDraw.Draw(hole)
    u = min(fw, fh) * px * ss
    cx, cy = W * ss / 2, H * ss / 2 + 0.03 * u
    hd.rounded_rectangle([cx - 0.27 * u, cy - 0.12 * u, cx + 0.27 * u, cy + 0.17 * u], radius=0.07 * u, fill=255)
    hd.pieslice([cx - 0.16 * u, cy - 0.27 * u, cx + 0.16 * u, cy + 0.05 * u], 180, 360, fill=255)
    hole = hole.resize((W, H), Image.LANCZOS)
    wall = ImageChops.subtract(hole.filter(ImageFilter.MaxFilter(2 * max(1, int(0.5 * px)) + 1)), hole)
    art.paste(Image.new("RGB", (W, H), (98, 102, 110)), (0, 0), wall)
    lit = ImageChops.subtract(ImageChops.offset(hole, int(0.7 * px), int(0.9 * px)), hole)
    art.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), ImageChops.multiply(lit, mask))
    glint = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glint).polygon([(0, H * 0.2), (W * 0.5, 0), (W * 0.7, 0), (0, H * 0.62)], fill=70)
    art = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), art, glint.filter(ImageFilter.GaussianBlur(px * 2)))
    alpha = ImageChops.subtract(mask, hole)
    art.putalpha(alpha)
    return art, (W / 2, H / 2)


def unit(kind, face, shape, fw, fh):
    """The finished object for one pin in the environment's style: (RGBA, anchor)."""
    base = S.pin_sprite(face, shape, fw, fh)
    if kind == "keychain":
        return keychain_unit(base, fw, fh)
    if kind == "opener":
        return opener_front(base, fw, fh)
    return base, (base.width / 2, base.height / 2)


def _centred(spr, anchor):
    """Pad ``spr`` so ``anchor`` is its middle (so it turns about the pin, not the corner)."""
    ax, ay = anchor
    w, h = spr.size
    W2, H2 = int(2 * max(ax, w - ax)) + 2, int(2 * max(ay, h - ay)) + 2
    out = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    out.paste(spr, (int(W2 / 2 - ax), int(H2 / 2 - ay)))
    return out


# ---- layout ------------------------------------------------------------------------------
def layout(n, stage, foot, turn, seed=7, gap=1.12):
    """Where n objects of footprint ``foot`` (w, h in mm) go in ``stage`` (l, t, r, b).
    Returns ([(x, y, angle)], scale): scale is 1 when they all fit at real size."""
    x0, y0, x1, y1 = stage
    sw, sh = x1 - x0, y1 - y0
    bw, bh = foot
    best = None
    for c in range(1, n + 1):
        r = math.ceil(n / c)
        s = min(1.0, sw / (c * bw * gap), sh / (r * bh * gap))
        score = (round(s, 3), -(c * r - n), -abs((c * bw) / (r * bh) - sw / sh))
        if best is None or score > best[0]:
            best = (score, c, r, s)
    _, c, r, s = best
    rng = random.Random(seed * 100 + n)
    out = []
    cw, ch = sw / c, sh / r
    for i in range(n):
        row, col = divmod(i, c)
        count = c if row < r - 1 else n - (r - 1) * c
        left = x0 + (sw - count * cw) / 2
        cx, cy = left + (col + 0.5) * cw, y0 + (row + 0.5) * ch
        room_x, room_y = max(0, cw - bw * s * gap) * 0.32, max(0, ch - bh * s * gap) * 0.32
        out.append((cx + rng.uniform(-room_x, room_x), cy + rng.uniform(-room_y, room_y),
                    rng.uniform(-turn, turn)))
    return out, s


def _scaled(spr, s):
    if s >= 0.999:
        return spr
    return spr.resize((max(1, round(spr.width * s)), max(1, round(spr.height * s))), Image.LANCZOS)


def ruler_strip(img, px, mm_len=100, at=None):
    """A ruler along the bottom edge: ``mm_len`` millimetres, ticks each mm."""
    ss = 2
    w, h = int((mm_len + 4) * px), int(15 * px)
    r = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(r)
    d.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=int(1.2 * px * ss),
                        fill=(250, 246, 232, 230), outline=(120, 108, 84, 235), width=ss * 2)
    f = S._font(int(3.2 * px * ss))
    for mm in range(0, mm_len + 1):
        x = (2 + mm) * px * ss
        ln = 7 if mm % 10 == 0 else 4.6 if mm % 5 == 0 else 2.6
        d.line([(x, 0), (x, ln * px * ss)], fill=(60, 52, 40, 255),
               width=max(1, int((0.16 if mm % 5 else 0.26) * px * ss)))
        if mm % 10 == 0:
            t = str(mm // 10)
            d.text((x - d.textlength(t, font=f) / 2, 7.6 * px * ss), t, font=f, fill=(60, 52, 40, 255))
    d.text(((mm_len - 12) * px * ss, 10.2 * px * ss), "cm", font=S._font(int(2.8 * px * ss)), fill=(60, 52, 40, 255))
    r = r.resize((w, h), Image.LANCZOS)
    x0, y0 = at if at else (int(12 * px), int(img.height - 22 * px))
    sh = r.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: v // 3)
    img.paste(Image.new("RGB", r.size, (20, 14, 8)), (x0 + 3, y0 + 5), sh)
    img.paste(r.convert("RGB"), (x0, y0), r.getchannel("A"))


# ---- the pictures ------------------------------------------------------------------------
def kind_of(env):
    return KINDS[env]


def bundle(env, faces, pin, ruler=False, return_spots=False):
    """The bundle picture: all ``faces`` (one per pin, rendered at ``BUNDLE_PX``) in ``env``.
    Returns (RGB image, scale) where scale < 1 means the pins were shrunk to fit. Bottle
    openers get one extra object: the back of the first pin, with its opening."""
    px, kind = BUNDLE_PX, KINDS[env]
    with at_px(px):
        img = backdrop(env, W_MM, len(faces) > 6).copy()
        units = [unit(kind, f, pin["shape"], pin["fw"], pin["fh"]) for f in faces]
        if kind == "opener":
            units.append(back_unit(pin["shape"], pin["fw"], pin["fh"]))
        foot = (max(u[0].width for u in units) / px, max(u[0].height for u in units) / px)
        stage = list(STAGE[env])
        if ruler:
            stage[3] = min(stage[3], H_MM - 30)
        spots, s = layout(len(units), stage, foot, TURN[kind])
        # the pin's middle sits where the footprint's middle should be
        for (spr, anchor), (x, y, ang) in zip(units, spots):
            off = (anchor[1] - spr.height / 2) * s
            S._put(img, _centred(_scaled(spr, s), (anchor[0] * s, anchor[1] * s)), x * px,
                   y * px + off, ang, SHADOWS[kind])
        img = S._grainy(img, 4, 91)
        if ruler:
            ruler_strip(img, px)
    if return_spots:
        return img, s, spots, foot
    return img, s


def window_mm(pin, kind):
    """Width (mm) of the close-up window: the pin (with its hardware) fills about 60% of the
    height, in steps of 10 mm."""
    fw, fh = pin["fw"], pin["fh"]
    extra = {"keychain": 52, "opener": 22}.get(kind, 0)
    need = max(fw / 0.42, (fh + extra) * 1.5 / 0.6)
    if kind == "opener":
        need = max(need, fw * 2.4 / 0.66)
    return int(min(W_MM / 2, max(90, math.ceil(need / 10) * 10)))


def close_up(env, face, pin, px, w_mm, ruler=False):
    """One pin, large, in a tighter window. ``face`` is rendered at ``px`` = LONG_PX / w_mm.
    A bottle opener is shown front and back, side by side."""
    kind = KINDS[env]
    with at_px(px):
        img = backdrop(env, w_mm, False).copy()
        units = [unit(kind, face, pin["shape"], pin["fw"], pin["fh"])]
        if kind == "opener":
            units.append(back_unit(pin["shape"], pin["fw"], pin["fh"]))
        h_mm = w_mm * 2 / 3
        spr = units[0][0]
        n = len(units)
        s = min(1.0, (h_mm * 0.82) / (spr.height / px), (w_mm * 0.7) / (n * spr.width / px))
        ang = {"keychain": -10, "opener": 6, "fabric": 3, "magnet": 4, "flat": 6}[kind]
        for i, (spr, anchor) in enumerate(units):
            off = (anchor[1] - spr.height / 2) * s
            x = img.width / 2 + (i - (n - 1) / 2) * pin["fw"] * 1.22 * px * s
            S._put(img, _centred(_scaled(spr, s), (anchor[0] * s, anchor[1] * s)), x,
                   img.height * (0.45 if ruler else 0.5) + off, ang * (1 if i == 0 else -0.6),
                   SHADOWS[kind])
        img = S._grainy(img, 4, 92)
        if ruler:
            ruler_strip(img, px, 100 if w_mm >= 150 else 50)
    return img, s


def footer(img, title, lines, px):
    """The caption band for a shop listing: a title, then smaller lines on the right."""
    band = int(FOOT_MM * px)
    out = Image.new("RGB", (img.width, img.height + band), (250, 248, 245))
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    pad = int(8 * px)
    d.line([(0, img.height), (img.width, img.height)], fill=(226, 222, 214), width=max(1, int(0.3 * px)))
    f1, f2 = S._font(int(7.6 * px)), S._font(int(4.6 * px))
    if title:
        d.text((pad, img.height + band * 0.5), title, font=f1, fill=(34, 34, 40), anchor="lm")
    right = "   ·   ".join(lines)
    if right:
        d.text((img.width - pad, img.height + band * 0.5), right, font=f2, fill=(104, 102, 108), anchor="rm")
    return out
