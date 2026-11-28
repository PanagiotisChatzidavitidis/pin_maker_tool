"""Realistic "in the wild" previews of a finished pin, drawn with Pillow only.

Three small scenes (a wooden desk, a denim jacket, a canvas tote) are painted at 7 pixels per
millimetre, with everyday objects of known size next to the pin (a coin, a bank card, a pencil,
a paper clip, a jeans button and rivet) so its real size reads at a glance. The pin is cut to its
shape, given a little dome of light, a rim and soft shadows, and set down at a slight angle.
Light comes from the top left everywhere.
"""

import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import ring as ring_mod

PX = 7                                   # pixels per millimetre
W_MM, H_MM = 260, 170                    # the scene, in millimetres
SCENES = (("desk", "Desk"), ("denim", "Denim"), ("canvas", "Canvas"))
# where the pin goes (mm) and how it is turned (degrees, anticlockwise)
PIN_AT = {"desk": (108, 88, 6), "denim": (108, 88, -5), "canvas": (104, 88, 4)}
SIZE = (W_MM * PX, H_MM * PX)


# ---- little helpers ----------------------------------------------------------------------
def _noise(w, h, cw, ch, seed):
    """Smooth random texture, 0-255: a grid of about (w / cw) x (h / ch) random cells, blown up."""
    gw, gh = max(2, w // cw), max(2, h // ch)
    img = Image.frombytes("L", (gw, gh), random.Random(seed).randbytes(gw * gh))
    return img.resize((w, h), Image.BICUBIC)


def _mix(a, b, t):
    return Image.blend(a, b, t)


def _diag(w, h, flip=False):
    """A diagonal gradient (0 at the top left, 255 at the bottom right; the reverse if flip)."""
    hz = Image.linear_gradient("L").rotate(90).resize((w, h))
    vt = Image.linear_gradient("L").resize((w, h))
    g = ImageChops.add(hz, vt, scale=2.0)
    return ImageOps.invert(g) if flip else g


def _lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def _vignette(img, strength=0.35):
    """Light from the top left, darker towards the corners."""
    w, h = img.size
    g = Image.new("L", (64, 40), 0)
    ImageDraw.Draw(g).ellipse([-10, -6, 54, 34], fill=255)
    g = g.filter(ImageFilter.GaussianBlur(9)).resize((w, h), Image.BICUBIC)
    shade = ImageOps.colorize(g, (int(255 * (1 - strength)),) * 3, (255, 255, 255))
    light = _diag(w, h, flip=True).point(lambda v: 215 + v // 6)
    out = ImageChops.multiply(img, shade)
    return ImageChops.multiply(out, light.convert("RGB"))


def _grainy(img, amount=7, seed=77):
    """A trace of photographic grain so nothing looks too clean."""
    w, h = img.size
    g = _noise(w, h, 1, 1, seed).point(lambda v: 128 + (v - 128) * amount / 60)
    return ImageChops.add(img, g.convert("RGB"), 1.0, -128)


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ---- placing a sprite with shadows -------------------------------------------------------
def _put(canvas, spr, cx, cy, angle=0, shadows=((0.5, 0.8, 0.9, 0.5), (1.8, 2.8, 4.0, 0.32)),
         shadow_col=(28, 18, 10)):
    """Paste RGBA ``spr`` centred on (cx, cy) pixels, turned ``angle`` degrees anticlockwise,
    with soft shadows ``(dx mm, dy mm, blur mm, opacity)`` cast to the lower right."""
    if angle:
        spr = spr.rotate(angle, Image.BICUBIC, expand=True)
    w, h = spr.size
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    a = spr.getchannel("A")
    for dx, dy, blur, op in shadows:
        pad = int(blur * PX * 3) + 2
        layer = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
        layer.paste(a, (pad, pad))
        layer = layer.filter(ImageFilter.GaussianBlur(blur * PX)).point(lambda v, op=op: int(v * op))
        canvas.paste(Image.new("RGB", layer.size, shadow_col),
                     (x0 - pad + round(dx * PX), y0 - pad + round(dy * PX)), layer)
    canvas.paste(spr.convert("RGB"), (x0, y0), a)


def _sprite(w, h, draw_fn, ss=3):
    """An RGBA sprite painted at ``ss``x by ``draw_fn(rgb_draw, alpha_draw, k)``."""
    rgb = Image.new("RGB", (w * ss, h * ss), (0, 0, 0))
    alpha = Image.new("L", (w * ss, h * ss), 0)
    draw_fn(rgb, alpha, ss)
    rgb = rgb.resize((w, h), Image.LANCZOS)
    alpha = alpha.resize((w, h), Image.LANCZOS)
    rgb.putalpha(alpha)
    return rgb


# ---- objects (real sizes) ----------------------------------------------------------------
def _disc_metal(size, c_dark, c_light, c_mid=None, ss=4):
    """A round metal disc: brushed-looking diagonal sheen. Returns (RGB, mask) at ``size``."""
    s = size * ss
    g = _diag(s, s, flip=True)
    sheen = ImageOps.colorize(g, c_dark, c_light, mid=c_mid)
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).ellipse([0, 0, s - 1, s - 1], fill=255)
    return sheen, m


def coin(d_mm=23.25):
    """A two-tone coin (silver ring, gold centre) with an embossed star."""
    size = int(d_mm * PX) + 6
    ss = 4
    s = size * ss
    c = s / 2
    r = d_mm * PX * ss / 2
    rgb = Image.new("RGB", (s, s), (0, 0, 0))
    alpha = Image.new("L", (s, s), 0)
    d, da = ImageDraw.Draw(rgb), ImageDraw.Draw(alpha)
    da.ellipse([c - r, c - r, c + r, c + r], fill=255)
    silver, m1 = _disc_metal(int(2 * r / ss), (118, 120, 126), (238, 240, 244), (184, 186, 192))
    gold, m2 = _disc_metal(int(2 * r * 0.64 / ss), (150, 108, 40), (250, 224, 140), (206, 160, 74))
    rgb.paste(silver, (int(c - r), int(c - r)), m1)
    gi = int(2 * r * 0.64)
    rgb.paste(gold, (int(c - gi / 2), int(c - gi / 2)), m2)
    # grooves round the gold, a lit rim top left, a dark rim bottom right
    for rr, col, w in ((r * 0.655, (92, 94, 100), 5), (r * 0.625, (252, 246, 214), 3),
                       (r * 0.985, (70, 72, 78), 6)):
        d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=col, width=w)
    d.arc([c - r * 0.93, c - r * 0.93, c + r * 0.93, c + r * 0.93], 200, 290,
          fill=(255, 255, 255), width=int(r * 0.05))
    d.arc([c - r * 0.93, c - r * 0.93, c + r * 0.93, c + r * 0.93], 20, 110,
          fill=(96, 98, 104), width=int(r * 0.05))
    # an embossed star
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        rr = r * (0.34 if i % 2 == 0 else 0.14)
        pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
    d.polygon([(x + 5, y + 6) for x, y in pts], fill=(120, 84, 24))
    d.polygon(pts, fill=(222, 178, 90))
    d.polygon([(x - 2, y - 3) for x, y in pts], outline=(255, 240, 190), width=3)
    rgb = rgb.resize((size, size), Image.LANCZOS)
    rgb = _grainy(rgb, 5, 5)
    rgb.putalpha(alpha.resize((size, size), Image.LANCZOS))
    return rgb


def bank_card(w_mm=85.6, h_mm=54.0, top=(28, 64, 70), bottom=(12, 26, 34)):
    """A plain bank-style card: deep colour, soft arcs, a gold chip and a glossy sheen."""
    w, h = int(w_mm * PX), int(h_mm * PX)
    ss = 3
    s = (w * ss, h * ss)
    base = ImageOps.colorize(_diag(*s, flip=False).rotate(0), top, bottom)
    d = ImageDraw.Draw(base, "RGBA")
    for i, (cx, cy, rr, a) in enumerate(((0.80, 0.30, 0.55, 26), (0.95, 0.55, 0.50, 20),
                                          (0.72, 0.90, 0.42, 18))):
        R = rr * s[1]
        d.ellipse([cx * s[0] - R, cy * s[1] - R, cx * s[0] + R, cy * s[1] + R],
                  fill=(255, 255, 255, a))
    # the chip
    cw, ch = 11.5 * PX * ss, 9 * PX * ss
    x0, y0 = 9 * PX * ss, 20 * PX * ss
    chip = ImageOps.colorize(_diag(int(cw), int(ch), True), (160, 122, 52), (248, 224, 150),
                             mid=(210, 170, 90))
    cm = Image.new("L", chip.size, 0)
    ImageDraw.Draw(cm).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=int(1.4 * PX * ss),
                                         fill=255)
    base.paste(chip, (int(x0), int(y0)), cm)
    for fx in (0.33, 0.66):
        d.line([(x0 + cw * fx, y0), (x0 + cw * fx, y0 + ch)], fill=(120, 90, 36, 190),
               width=ss * 2)
    d.line([(x0, y0 + ch / 2), (x0 + cw, y0 + ch / 2)], fill=(120, 90, 36, 190), width=ss * 2)
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=int(1.4 * PX * ss),
                        outline=(110, 82, 34, 220), width=ss * 2)
    # a few quiet "text" bars
    for i, wd in enumerate((0.46, 0.30)):
        d.rounded_rectangle([9 * PX * ss, (38 + i * 6) * PX * ss, (9 + 70 * wd) * PX * ss,
                             (40 + i * 6) * PX * ss], radius=ss * 4, fill=(255, 255, 255, 70))
    # glossy sheen: a soft diagonal band
    sheen = Image.new("L", s, 0)
    ImageDraw.Draw(sheen).polygon([(0, 0), (s[0] * 0.55, 0), (s[0] * 0.18, s[1]), (0, s[1])],
                                  fill=60)
    sheen = sheen.filter(ImageFilter.GaussianBlur(ss * 6))
    base = Image.composite(Image.new("RGB", s, (255, 255, 255)), base, sheen)
    mask = Image.new("L", s, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s[0] - 1, s[1] - 1], radius=int(3.2 * PX * ss),
                                           fill=255)
    # bevel: bright top-left edge, dark bottom-right edge
    ed = ImageDraw.Draw(base)
    ed.rounded_rectangle([0, 0, s[0] - 1, s[1] - 1], radius=int(3.2 * PX * ss),
                         outline=(8, 14, 18), width=ss * 2)
    ed.rounded_rectangle([ss * 2, ss * 2, s[0] - 1 - ss * 2, s[1] - 1 - ss * 2],
                         radius=int(3.0 * PX * ss), outline=(120, 150, 154), width=ss)
    out = base.resize((w, h), Image.LANCZOS)
    out = _grainy(out, 4, 9)
    out.putalpha(mask.resize((w, h), Image.LANCZOS))
    return out


def pencil(length_mm=175.0, w_mm=7.0):
    """A yellow hexagonal pencil (lying on its side), eraser at the left, point at the right."""
    L, Hh = int(length_mm * PX), int(w_mm * PX) + 2
    ss = 3

    def paint(rgb, alpha, k):
        d, da = ImageDraw.Draw(rgb), ImageDraw.Draw(alpha)
        H = Hh * k
        tip = 16 * PX * k
        er, fe = 8 * PX * k, 8 * PX * k
        x_body0, x_body1 = er + fe, L * k - tip
        bands = ((0, .16, (255, 226, 118)), (.16, .5, (250, 200, 52)),
                 (.5, .84, (234, 166, 26)), (.84, 1.0, (186, 118, 10)))
        for a, b, col in bands:
            d.rectangle([x_body0, 1 * k + a * (H - 2 * k), x_body1, 1 * k + b * (H - 2 * k)],
                        fill=col)
        da.rectangle([x_body0, k, x_body1, H - k], fill=255)
        # wood cone, then the graphite
        cone = [(x_body1, k), (L * k - 1, H / 2), (x_body1, H - k)]
        d.polygon(cone, fill=(236, 200, 150))
        d.polygon([(x_body1, k), (L * k - 1, H / 2), (x_body1, H / 2)], fill=(250, 222, 176))
        d.polygon([(x_body1, H / 2), (L * k - 1, H / 2), (x_body1, H - k)], fill=(206, 164, 112))
        da.polygon(cone, fill=255)
        gx = L * k - 5 * PX * k
        d.polygon([(gx, H / 2 - 0.0 * k - (H / 2 - k) * (5 * PX * k) / tip),
                   (L * k - 1, H / 2), (gx, H / 2 + (H / 2 - k) * (5 * PX * k) / tip)],
                  fill=(58, 58, 62))
        # a painted end: dark lacquer band before the cone
        d.rectangle([x_body1 - 3 * PX * k, k, x_body1, H - k], fill=(168, 98, 24))
        # ferrule (metal) and eraser
        for a, b, col in ((0, .2, (240, 242, 246)), (.2, .5, (200, 204, 212)),
                          (.5, .8, (150, 154, 164)), (.8, 1, (112, 116, 126))):
            d.rectangle([er, 1 * k + a * (H - 2 * k), x_body0, 1 * k + b * (H - 2 * k)], fill=col)
        da.rectangle([er, k, x_body0, H - k], fill=255)
        for i in range(1, 4):
            x = er + i * fe / 4
            d.line([(x, k), (x, H - k)], fill=(96, 100, 110), width=k)
        for a, b, col in ((0, .25, (250, 190, 190)), (.25, .7, (238, 150, 152)),
                          (.7, 1, (206, 112, 118))):
            d.rounded_rectangle([k, 1 * k + a * (H - 2 * k), er + 2 * k, 1 * k + b * (H - 2 * k)],
                                radius=0, fill=col)
        da.rounded_rectangle([k, k, er + 2 * k, H - k], radius=3 * k, fill=255)
    return _sprite(L, Hh, paint, ss)


def jeans_button(d_mm=17.0):
    """An antique-brass jeans button: domed, with a stamped ring."""
    size = int(d_mm * PX) + 4
    ss = 4
    s = size * ss
    c = s / 2
    r = d_mm * PX * ss / 2
    brass, m = _disc_metal(int(2 * r / ss), (112, 76, 34), (244, 206, 132), (176, 128, 66))
    rgb = Image.new("RGB", (s, s), (0, 0, 0))
    alpha = Image.new("L", (s, s), 0)
    ImageDraw.Draw(alpha).ellipse([c - r, c - r, c + r, c + r], fill=255)
    rgb.paste(brass, (int(c - r), int(c - r)), m)
    d = ImageDraw.Draw(rgb)
    for rr, col, w in ((r * 0.97, (86, 56, 24), 7), (r * 0.80, (80, 52, 22), 4),
                       (r * 0.77, (255, 230, 170), 3), (r * 0.46, (86, 56, 24), 4),
                       (r * 0.43, (255, 230, 170), 3)):
        d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=col, width=w)
    d.ellipse([c - r * 0.12, c - r * 0.12, c + r * 0.12, c + r * 0.12], fill=(90, 60, 26))
    out = _grainy(rgb.resize((size, size), Image.LANCZOS), 5, 13)
    out.putalpha(alpha.resize((size, size), Image.LANCZOS))
    return out


def paper_clip(len_mm=33.0, w_mm=9.0):
    """A silver paper clip: a long wire in three nested loops."""
    w, h = int(len_mm * PX) + 8, int(w_mm * PX) + 8
    ss = 4
    a = Image.new("L", (w * ss, h * ss), 0)
    rgb = Image.new("RGB", (w * ss, h * ss), (0, 0, 0))
    L, H = (w - 8) * ss, (h - 8) * ss
    x0, y0 = 4 * ss, 4 * ss
    r = H / 2
    ri = H * 0.32
    # nested rounded rectangles, opened at alternating ends (as a clip's wire does)
    paths = [
        [(x0 + L * 0.86, y0 + r - ri), (x0 + L * 0.12 + 0, y0 + r - ri)],
    ]
    wire = int(0.85 * PX * ss)

    def stroke(layer_draw, col, width, off=(0, 0)):
        ox, oy = off
        pts = [(x0 + L * 0.80, y0 + H * 0.30), (x0 + L * 0.20, y0 + H * 0.30)]
        # outer loop (left)
        layer_draw.arc([x0 + ox, y0 + oy, x0 + H + ox, y0 + H + oy], 90, 270, fill=col, width=width)
        layer_draw.line([(x0 + r + ox, y0 + oy), (x0 + L - r + ox, y0 + oy)], fill=col, width=width)
        layer_draw.arc([x0 + L - H + ox, y0 + oy, x0 + L + ox, y0 + H + oy], 270, 90, fill=col,
                       width=width)
        layer_draw.line([(x0 + L - r + ox, y0 + H + oy), (x0 + r * 1.9 + ox, y0 + H + oy)],
                        fill=col, width=width)
        # middle loop
        m = H * 0.2
        layer_draw.arc([x0 + r * 0.5 + ox + m, y0 + m + oy, x0 + r * 0.5 + H - m + ox + m * 0,
                        y0 + H - m + oy], 90, 270, fill=col, width=width)
        layer_draw.line([(x0 + r * 0.5 + (H - 2 * m) / 2 + m + ox, y0 + m + oy),
                         (x0 + L * 0.72 + ox, y0 + m + oy)], fill=col, width=width)
        layer_draw.arc([x0 + L * 0.72 - (H - 2 * m) / 2 + ox, y0 + m + oy,
                        x0 + L * 0.72 + (H - 2 * m) / 2 + ox, y0 + H - m + oy], 270, 90,
                       fill=col, width=width)
        layer_draw.line([(x0 + L * 0.72 + ox, y0 + H - m + oy), (x0 + r * 1.1 + ox, y0 + H - m + oy)],
                        fill=col, width=width)
    stroke(ImageDraw.Draw(a), 255, wire)
    d = ImageDraw.Draw(rgb)
    stroke(d, (92, 96, 106), wire)
    stroke(d, (186, 190, 200), max(2, wire - 2 * ss), (-ss * 0.4, -ss * 0.4))
    stroke(d, (250, 252, 255), max(2, wire // 3), (-ss * 0.8, -ss * 0.8))
    out = rgb.resize((w, h), Image.LANCZOS)
    out.putalpha(a.resize((w, h), Image.LANCZOS))
    return out


def rivet(d_mm=9.0):
    return jeans_button(d_mm)


# ---- the backgrounds ---------------------------------------------------------------------
def _wood(w, h):
    """Oak planks: long grain, a few darker figure lines, plank seams."""
    n1 = _noise(w, h, 420, 4, 1)
    n2 = _noise(w, h, 180, 2, 2)
    n3 = _noise(w, h, 900, 60, 3)
    base = _mix(n1, n2, 0.5)
    bands = base.point(lambda v: int(127 + 127 * math.sin(v / 255 * 22)))
    g = _mix(bands, n3, 0.45)
    wood = ImageOps.colorize(g, (146, 100, 62), (212, 164, 116), mid=(182, 132, 88))
    fine = _noise(w, h, 90, 1, 4).filter(ImageFilter.GaussianBlur(0.6))
    wood = ImageChops.multiply(wood, ImageOps.colorize(fine, (226, 218, 208), (255, 255, 255)))
    # each plank gets its own tone
    plank_h = h // 3 + 1
    d = ImageDraw.Draw(wood, "RGBA")
    for i in range(3):
        tone = (0, 0, 0, 0)
        d.rectangle([0, i * plank_h, w, (i + 1) * plank_h],
                    fill=[(255, 235, 200, 18), (0, 0, 0, 0), (60, 30, 10, 22)][i])
    for i in (1, 2):
        y = i * plank_h
        d.rectangle([0, y - 2, w, y + 1], fill=(40, 22, 10, 210))
        d.rectangle([0, y + 1, w, y + 3], fill=(255, 226, 180, 70))
    return wood


def _denim(w, h):
    """Indigo twill: diagonal ribs, uneven yarn, and faded patches."""
    base = Image.new("RGB", (w, h), (34, 58, 100))
    tw = Image.new("L", (w + h, h), 128)
    d = ImageDraw.Draw(tw)
    step = 5
    for x in range(-h, w + h, step):
        d.line([(x, h), (x + h, 0)], fill=170, width=2)
        d.line([(x + 3, h), (x + 3 + h, 0)], fill=96, width=1)
    tw = tw.crop((0, 0, w, h)).filter(ImageFilter.GaussianBlur(0.45))
    tw = ImageOps.autocontrast(tw, cutoff=1)
    yarn = _noise(w, h, 1, 1, 21).filter(ImageFilter.GaussianBlur(0.5))
    fade = _noise(w, h, 380, 300, 23).filter(ImageFilter.GaussianBlur(60))
    tex = _mix(tw, yarn, 0.28)
    dark = ImageOps.colorize(tex, (20, 38, 74), (64, 96, 146))
    faded = ImageOps.colorize(tex, (58, 90, 140), (126, 160, 202))
    return Image.composite(faded, dark, fade.point(lambda v: max(0, min(150, (v - 100)))))


def _canvas(w, h):
    """Natural cotton canvas: a fine plain weave with slubs."""
    horiz = _noise(w, h, w // 1, 1, 31)
    vert = _noise(w, h, 1, h // 1, 32)
    weave = ImageChops.add(horiz, vert, scale=2.0)
    cell = Image.new("L", (6, 6), 128)
    cd = ImageDraw.Draw(cell)
    cd.rectangle([0, 0, 2, 2], fill=170)
    cd.rectangle([3, 3, 5, 5], fill=170)
    cd.rectangle([3, 0, 5, 2], fill=100)
    cd.rectangle([0, 3, 2, 5], fill=100)
    pat = Image.new("L", (w, h))
    for y in range(0, h, 6):
        for x in range(0, w, 6):
            pat.paste(cell, (x, y))
    slub = _noise(w, h, 600, 3, 33).point(lambda v: 255 if v > 232 else 128)
    tex = _mix(_mix(pat, weave, 0.22), slub, 0.08).filter(ImageFilter.GaussianBlur(0.5))
    blotch = _noise(w, h, 500, 400, 34).filter(ImageFilter.GaussianBlur(30))
    img = ImageOps.colorize(tex, (200, 188, 166), (244, 236, 220), mid=(226, 216, 196))
    tone = ImageOps.colorize(blotch, (238, 232, 222), (255, 255, 255))
    return ImageChops.multiply(img, tone)


def _stitches(img, pts, length=3.0, gap=1.2, col=(232, 168, 58), width=0.62):
    """A dashed line of thread between two points (mm), with a little shadow under each."""
    (ax, ay), (bx, by) = pts
    ax, ay, bx, by = (v * PX for v in (ax, ay, bx, by))
    dist = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / dist, (by - ay) / dist
    n = int(dist / ((length + gap) * PX))
    ss = 3
    layer = Image.new("RGBA", (img.width * ss // 1, 1), 0)
    sh = Image.new("L", img.size, 0)
    th = Image.new("L", img.size, 0)
    sd, td = ImageDraw.Draw(sh), ImageDraw.Draw(th)
    for i in range(n):
        s0 = i * (length + gap) * PX
        p0 = (ax + ux * s0, ay + uy * s0)
        p1 = (ax + ux * (s0 + length * PX), ay + uy * (s0 + length * PX))
        sd.line([(p0[0] + 1.2, p0[1] + 1.6), (p1[0] + 1.2, p1[1] + 1.6)], fill=255,
                width=int(width * PX) + 1)
        td.line([p0, p1], fill=255, width=int(width * PX))
    sh = sh.filter(ImageFilter.GaussianBlur(1.3)).point(lambda v: int(v * 0.55))
    img.paste(Image.new("RGB", img.size, (10, 14, 28)), (0, 0), sh)
    thread = ImageOps.colorize(_noise(*img.size, 2, 2, 41), _lerp(col, (60, 30, 6), 0.35),
                               _lerp(col, (255, 255, 255), 0.3))
    img.paste(thread, (0, 0), th.filter(ImageFilter.GaussianBlur(0.5)))


def _backdrop_desk():
    img = _wood(*SIZE)
    _put(img, pencil(), 130 * PX, 20 * PX, 2)
    _put(img, bank_card(), 212 * PX, 128 * PX, 13)
    _put(img, coin(), 235 * PX, 55 * PX, 0)
    return _vignette(img, 0.30)


def _backdrop_denim():
    img = _denim(*SIZE)
    # a raised seam: a soft ridge, then two rows of orange stitches
    ridge = Image.new("L", SIZE, 0)
    ImageDraw.Draw(ridge).rectangle([int(214 * PX), 0, int(218.5 * PX), SIZE[1]], fill=255)
    ridge = ridge.filter(ImageFilter.GaussianBlur(5))
    img = Image.composite(Image.new("RGB", SIZE, (12, 22, 48)), img, ridge.point(lambda v: v // 2))
    for x in (211.5, 221.5):
        _stitches(img, ((x, -2), (x, H_MM + 2)), 3.2, 1.0)
    _put(img, rivet(), 216.5 * PX, 36 * PX, 0, ((0.5, 0.8, 0.7, 0.55), (1.2, 1.8, 2.5, 0.3)))
    _put(img, jeans_button(), 237 * PX, 125 * PX, 0, ((0.6, 1.0, 0.9, 0.55), (1.6, 2.6, 3.5, 0.32)))
    return _vignette(img, 0.32)


def _backdrop_canvas():
    img = _canvas(*SIZE)
    # a webbing strap down the right side, with box stitching
    strap = Image.new("RGB", (int(34 * PX), SIZE[1]))
    s = _noise(strap.width, strap.height, 1, 6, 51)
    strap.paste(ImageOps.colorize(s, (176, 150, 112), (222, 200, 162)))
    sm = Image.new("L", strap.size, 255)
    sx = SIZE[0] - strap.width - 6 * PX
    _put(img, Image.merge("RGBA", (*strap.split(), sm)), sx + strap.width / 2, SIZE[1] / 2, 0,
         ((0.4, 0.6, 0.8, 0.45), (1.2, 1.6, 2.5, 0.25)))
    for x in (sx / PX + 3, sx / PX + 31):
        _stitches(img, ((x, -2), (x, H_MM + 2)), 3.4, 1.2, (96, 70, 44))
    _put(img, coin(), (sx + strap.width / 2), 128 * PX, 0)
    _put(img, paper_clip(), (sx + strap.width / 2) - 2 * PX, 44 * PX, -66)
    return _vignette(img, 0.26)


@lru_cache(maxsize=4)
def backdrop(name):
    """The empty scene (props included, pin not) for ``name``."""
    return {"desk": _backdrop_desk, "denim": _backdrop_denim, "canvas": _backdrop_canvas}[name]()


# ---- the pin -----------------------------------------------------------------------------
def pin_sprite(face, shape, fw, fh):
    """RGBA sprite of the finished pin. ``face`` is the picture area (the paper-shape box) at
    ``PX`` pixels per mm, centred on the pin."""
    pad = 6
    W, H = int(fw * PX) + 2 * pad, int(fh * PX) + 2 * pad
    mask = ring_mod.mask(shape, fw, fh, 0, (W, H), PX, PX, W / 2, H / 2, 3)
    art = Image.new("RGB", (W, H), (255, 255, 255))
    art.paste(face.convert("RGB"), (int(W / 2 - face.width / 2), int(H / 2 - face.height / 2)))
    # a faint print texture (paper and varnish are never perfectly flat)
    art = _grainy(art, 3, 61)
    # the dome: it darkens towards the edge as the surface turns away
    blur = mask.filter(ImageFilter.GaussianBlur(1.1 * PX))
    edge = ImageChops.subtract(mask, blur).point(lambda v: min(255, v * 2))
    art = ImageChops.multiply(art, ImageOps.invert(edge.point(lambda v: int(v * 0.42))).convert("RGB"))
    # the crimped rim: a thin metal lip, lit from the top left
    rim_px = max(2, int(0.45 * PX))
    inner = mask.filter(ImageFilter.MinFilter(2 * rim_px + 1))
    rim = ImageChops.subtract(mask, inner)
    metal = ImageOps.colorize(_diag(W, H, flip=True), (112, 114, 122), (248, 248, 252),
                              mid=(184, 186, 194))
    art.paste(metal, (0, 0), rim)
    # a soft gloss crescent top left, plus a small glint
    hl = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(hl)
    d.ellipse([W * 0.05, H * 0.03, W * 0.80, H * 0.60], fill=255)
    cut = Image.new("L", (W, H), 0)
    ImageDraw.Draw(cut).ellipse([W * 0.12, H * 0.13, W * 0.90, H * 0.70], fill=255)
    hl = ImageChops.subtract(hl, cut).filter(ImageFilter.GaussianBlur(max(2, W * 0.035)))
    hl = ImageChops.multiply(hl, mask).point(lambda v: int(v * 0.42))
    gl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gl).ellipse([W * 0.19, H * 0.14, W * 0.27, H * 0.19], fill=255)
    gl = ImageChops.multiply(gl.filter(ImageFilter.GaussianBlur(max(1.5, W * 0.012))), mask)
    glass = Image.new("RGB", (W, H), (255, 255, 255))
    art = Image.composite(glass, art, hl)
    art = Image.composite(glass, art, gl.point(lambda v: int(v * 0.75)))
    # the reflection of a window across the lower right, very faint
    wd = Image.new("L", (W, H), 0)
    ImageDraw.Draw(wd).polygon([(W * 0.55, H), (W * 0.78, H), (W, H * 0.62), (W, H * 0.40)], fill=255)
    wd = ImageChops.multiply(wd.filter(ImageFilter.GaussianBlur(max(2, W * 0.04))), mask)
    art = Image.composite(glass, art, wd.point(lambda v: int(v * 0.12)))
    art.putalpha(mask)
    return art


def compose(name, face, shape, fw, fh, ruler=False):
    """The whole picture: scene ``name`` with the pin (``face``: see ``pin_sprite``) set down on
    it. Returns an RGB image ``SIZE`` pixels big."""
    img = backdrop(name).copy()
    x, y, ang = PIN_AT[name]
    _put(img, pin_sprite(face, shape, fw, fh), x * PX, y * PX, ang,
         ((0.5, 0.9, 1.0, 0.55), (1.8, 3.0, 4.5, 0.36)))
    img = _grainy(img, 4, 91)
    if ruler:
        _ruler(img)
    return img


def _ruler(img):
    """A 10 cm ruler along the bottom edge, in millimetres."""
    ss = 2
    w = int(104 * PX)
    h = int(15 * PX)
    r = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(r)
    d.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=int(1.2 * PX * ss),
                        fill=(250, 246, 232, 226), outline=(120, 108, 84, 230), width=ss * 2)
    f = _font(int(3.2 * PX * ss))
    for mm in range(0, 101):
        x = (2 + mm) * PX * ss
        ln = 7 if mm % 10 == 0 else 4.6 if mm % 5 == 0 else 2.6
        d.line([(x, 0), (x, ln * PX * ss)], fill=(60, 52, 40, 255),
               width=max(1, int((0.16 if mm % 5 else 0.26) * PX * ss)))
        if mm % 10 == 0:
            t = str(mm // 10)
            tw = d.textlength(t, font=f)
            d.text((x - tw / 2, 7.6 * PX * ss), t, font=f, fill=(60, 52, 40, 255))
    d.text((int(86 * PX * ss), int(10.2 * PX * ss)), "cm", font=_font(int(2.8 * PX * ss)),
           fill=(60, 52, 40, 255))
    r = r.resize((w, h), Image.LANCZOS)
    x0, y0 = int(12 * PX), int(H_MM * PX - 22 * PX)
    shadow = r.getchannel("A").filter(ImageFilter.GaussianBlur(3)).point(lambda v: v // 3)
    img.paste(Image.new("RGB", r.size, (20, 14, 8)), (x0 + 3, y0 + 5), shadow)
    img.paste(r.convert("RGB"), (x0, y0), r.getchannel("A"))
