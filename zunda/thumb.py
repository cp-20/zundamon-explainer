"""YouTube のサムネイル（1280×720）を作るときの共通部品。docs/publishing.md を参照。

HEIC 編から：type_text() (字間を調べられる文字・Inter と Noto Sans JP の極太)、zunda_cut()・place_char() (立ち絵を縁の光で浮かせる)、
badge() (傾いたスタンプ)、hud() (照準の角の印)。

    from zunda.thumb import W, H, FONT, MONO, YELLOW, ZCOL, MCOL, chara, text

伸びている動画のサムネの作り (WebP 編で参考にしたもの) の部品：
- heavy()：極太 (Dela Gothic One) の文字。白い内側の縁と黒い外側の縁、縦のグラデーション。色は YEL2・RED2・WHT
- face()：立ち絵の顔と腕を大きく切り抜き、白いステッカーの縁をつけたもの。sticker() は任意の切り抜きに縁
- spot_bg()：中心が明るい暗い背景。pill() / black_tag()：小さな札。mark()：◎ と ✕。bubble()：吹き出し。chevrons()：赤→黄の「＞＞＞」
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import character
from .compose import BASE, EXPR, MOUTH
from .paths import ASSETS

W, H = 1280, 720
FONT = str(ASSETS / "fonts/ZenMaruGothic-Black.ttf")
MONO = str(ASSETS / "fonts/JetBrainsMono-Bold.ttf")
YELLOW = (255, 214, 64)
ZCOL = (124, 195, 90)
MCOL = (227, 96, 154)


def chara(sp, name, expr, mouth, scale, flip=False):
    """立ち絵（表情・口）を切り抜いて縮めたもの。sp は "Z" / "M"、mouth は closed / half / open"""
    st = dict(BASE[sp]); st.update(EXPR[sp][expr]); st["!口"] = MOUTH[sp][mouth]
    im = character.render(name, st)
    im = im.crop(im.getbbox())
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def text(img, xy, s, size, fill, stroke, sw, font=FONT, anchor="la", shadow=True):
    """縁取り（stroke 色・sw 太さ）と落ち影つきの文字。描いた範囲を返す"""
    f = ImageFont.truetype(font, size)
    if shadow:  # 下に落ちる影で文字を浮かせる
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((xy[0] + 6, xy[1] + 8), s, font=f, fill=(0, 0, 0, 170),
                                stroke_width=sw, stroke_fill=(0, 0, 0, 170), anchor=anchor)
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(img)
    d.text(xy, s, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke, anchor=anchor)
    return d.textbbox(xy, s, font=f, stroke_width=sw, anchor=anchor)


# ---------------- 伸びている動画のサムネの作り ----------------

def spot_bg(c0=(36, 44, 72), c1=(8, 9, 14), cx=0.5, cy=0.45):
    """中心が明るい暗い背景 (スポットライト)"""
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx / W - cx) * 1.6) ** 2 + (yy / H - cy) ** 2)
    t = np.clip(r / 0.9, 0, 1)[..., None]
    rgb = (np.array(c0) * (1 - t) + np.array(c1) * t).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, np.full((H, W), 255, np.uint8)]), "RGBA")


def sticker(im, ow=10, color=(255, 255, 255)):
    """白い縁取りと落ち影をつけた切り抜き (ステッカー風)"""
    from PIL import ImageFilter
    a = im.split()[3]
    pad = ow * 3
    big = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    am = Image.new("L", big.size, 0)
    am.paste(a, (pad, pad))
    edge = am.filter(ImageFilter.MaxFilter(ow * 2 + 1))
    shadow = edge.filter(ImageFilter.GaussianBlur(10)).point(lambda v: v * 0.7)
    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    out.paste(Image.new("RGBA", big.size, (0, 0, 0, 255)), (8, 12), shadow)
    out.paste(Image.new("RGBA", big.size, color + (255,)), (0, 0), edge)
    out.alpha_composite(im, (pad, pad))
    return out


def big_text(img, xy, s, size, top, bottom, inner=(255, 255, 255), iw=0, outer=(20, 16, 30), ow=16,
             anchor="la", font=FONT):
    """太い外の縁 (outer)・内の縁 (inner)・縦のグラデーションの文字"""
    from PIL import ImageFilter
    f = ImageFont.truetype(font, size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bb = d.textbbox(xy, s, font=f, anchor=anchor, stroke_width=ow)
    # 影
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 8, xy[1] + 12), s, font=f, anchor=anchor, fill=(0, 0, 0, 200),
                            stroke_width=ow, stroke_fill=(0, 0, 0, 200))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d.text(xy, s, font=f, anchor=anchor, fill=outer, stroke_width=ow, stroke_fill=outer)
    if iw:
        d.text(xy, s, font=f, anchor=anchor, fill=inner, stroke_width=iw, stroke_fill=inner)
    img.alpha_composite(layer)
    # 本体：縦のグラデーション
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, s, font=f, anchor=anchor, fill=255)
    y0, y1 = bb[1], bb[3]
    g = np.clip((np.arange(H)[:, None] - y0) / max(1, y1 - y0), 0, 1)
    grad = (np.array(top) * (1 - g[..., None]) + np.array(bottom) * g[..., None]).astype(np.uint8)
    grad = np.broadcast_to(grad, (H, W, 3))
    gi = Image.fromarray(np.dstack([grad, np.full((H, W), 255, np.uint8)]), "RGBA")
    img.paste(gi, (0, 0), mask)
    return bb


def pill(img, xy, s, size, bg, fg=(255, 255, 255), anchor="mm"):
    f = ImageFont.truetype(FONT, size)
    d = ImageDraw.Draw(img)
    bb = d.textbbox(xy, s, font=f, anchor=anchor)
    pad = size * 0.35
    d.rounded_rectangle((bb[0] - pad * 1.6, bb[1] - pad, bb[2] + pad * 1.6, bb[3] + pad), radius=size, fill=bg,
                        outline=(255, 255, 255), width=5)
    d.text(xy, s, font=f, anchor=anchor, fill=fg)


YEL = ((255, 240, 120), (255, 170, 20))


WHT = ((255, 255, 255), (214, 222, 240))


RED = ((255, 120, 110), (220, 30, 40))


DELA = str(ASSETS / "fonts/DelaGothicOne-Regular.ttf")   # サムネだけに使う極太の字


def heavy(img, xy, s, size, fill=((255, 255, 255), (255, 255, 255)), white=None, black=None, anchor="la",
          font=DELA):
    """色の文字は 白い内側の縁 + 黒い外側の縁、白い文字は黒い縁だけ (極太の字は縁が太いと字の中が埋まる)"""
    is_white = fill[0] == (255, 255, 255)
    iw = 0 if is_white else (white if white is not None else max(4, round(size * 0.045)))
    ow = black if black is not None else round(size * (0.09 if is_white else 0.10)) + iw
    return big_text(img, xy, s, size, *fill, inner=(255, 255, 255), iw=iw, outer=(12, 10, 16), ow=ow,
                    anchor=anchor, font=font)


RED2 = ((255, 70, 60), (190, 0, 20))


YEL2 = ((255, 245, 110), (255, 160, 0))


def face(sp="Z", expr="驚", mouth="open", h=560, flip=False):
    """立ち絵の顔と腕を大きく切り抜く (白いステッカーの縁つき)"""
    from zunda import character
    from zunda.compose import BASE, EXPR, MOUTH
    st = dict(BASE[sp]); st.update(EXPR[sp][expr]); st["!口"] = MOUTH[sp][mouth]
    name = "zundamon" if sp == "Z" else "metan"
    im = character.render(name, st)
    box = (200, 40, 920, 820) if sp == "Z" else (180, 0, 900, 780)
    im = im.crop(box)
    im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return sticker(im, ow=12)


def bubble(img, xy, s, size=54, tail=(-60, 70), font=DELA, color=(20, 20, 26)):
    """白い吹き出し (黒い縁、しっぽつき)"""
    f = ImageFont.truetype(font, size)
    d = ImageDraw.Draw(img)
    bb = d.textbbox(xy, s, font=f, anchor="mm")
    px_, py_ = size * 0.55, size * 0.45
    box = (bb[0] - px_, bb[1] - py_, bb[2] + px_, bb[3] + py_)
    cx, cy = (box[0] + box[2]) / 2, box[3]
    tip = (cx + tail[0], cy + tail[1])
    for wdt, col in ((10, (12, 10, 16)), (0, (255, 255, 255))):
        d.polygon([(cx - 30, cy - 10), (cx + 30, cy - 10), tip], fill=(255, 255, 255), outline=(12, 10, 16),
                  width=wdt)
        d.rounded_rectangle(box, radius=size * 0.6, fill=(255, 255, 255), outline=(12, 10, 16), width=wdt or 0)
    d.rounded_rectangle(box, radius=size * 0.6, outline=(12, 10, 16), width=8)
    d.text(xy, s, font=f, anchor="mm", fill=color)


def chevrons(img, x, y, n=3, h=120):
    """赤 → 橙 → 黄 の「＞＞＞」"""
    d = ImageDraw.Draw(img)
    cols = [(230, 30, 30), (255, 110, 20), (255, 200, 30)]
    for i in range(n):
        x0 = x + i * h * 0.55
        pts = [(x0, y - h / 2), (x0 + h * 0.35, y - h / 2), (x0 + h * 0.75, y), (x0 + h * 0.35, y + h / 2),
               (x0, y + h / 2), (x0 + h * 0.4, y)]
        d.polygon(pts, fill=cols[i % 3], outline=(12, 10, 16), width=6)


def black_tag(img, xy, s, size=56):
    f = ImageFont.truetype(DELA, size)
    d = ImageDraw.Draw(img)
    bb = d.textbbox(xy, s, font=f, anchor="mm")
    d.rectangle((bb[0] - 22, bb[1] - 16, bb[2] + 22, bb[3] + 16), fill=(10, 10, 12))
    d.text(xy, s, font=f, anchor="mm", fill=(255, 255, 255))


def mark(img, xy, ok, r=58):
    """◎ (緑) か ✕ (赤) の丸い印"""
    d = ImageDraw.Draw(img)
    x, y = xy
    col = (30, 180, 90) if ok else (220, 30, 40)
    d.ellipse((x - r - 6, y - r - 6, x + r + 6, y + r + 6), fill=(255, 255, 255))
    d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    if ok:
        d.ellipse((x - r * 0.6, y - r * 0.6, x + r * 0.6, y + r * 0.6), outline=(255, 255, 255), width=12)
        d.ellipse((x - r * 0.28, y - r * 0.28, x + r * 0.28, y + r * 0.28), outline=(255, 255, 255), width=10)
    else:
        k = r * 0.5
        d.line([(x - k, y - k), (x + k, y + k)], fill=(255, 255, 255), width=16)
        d.line([(x - k, y + k), (x + k, y - k)], fill=(255, 255, 255), width=16)


# ---------------- HEIC 編で作り直した文字と立ち絵の描き方 (videos/heic/tools/thumbnail.py から) ----------------
INTER = str(ASSETS / "fonts/Inter-Variable.ttf")       # 英字：字の中の空きが大きく、極太でも潰れない
NOTO = str(ASSETS / "fonts/NotoSansJP-Variable.ttf")    # 和文


def vfont(path, size, weight=900):
    f = ImageFont.truetype(path, size)
    axes = f.get_variation_axes()
    vals = []
    for ax in axes:
        nm = ax["name"]
        if nm in (b"Weight", "Weight"):
            vals.append(weight)
        elif nm in (b"Optical size", "Optical size"):
            vals.append(ax["maximum"])
        else:
            vals.append(ax["default"])
    f.set_variation_by_axes(vals)
    return f


def type_text(img, xy, s, path, size, fill=((255, 255, 255), (255, 255, 255)), stroke=((14, 12, 20), 0.06),
              weight=900, tracking=0.0, anchor="la", shadow=0.8, glow=None):
    """字間 (tracking：字の大きさに対する割合) を調べられる文字。fill は縦のグラデーション (上, 下)、
    stroke は (色, 太さの割合)。glow=(色, ぼかし) で外側をほんのり光らせる"""
    f = vfont(path, size, weight)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    adv = [tmp.textlength(ch, font=f) for ch in s]
    total = sum(adv) + tracking * size * (len(s) - 1)
    asc, desc = f.getmetrics()
    x0 = xy[0] - (total if anchor[0] == "r" else total / 2 if anchor[0] == "m" else 0)
    y0 = xy[1]
    sw = max(1, round(size * stroke[1])) if stroke else 0

    def draw_all(d, **kw):
        x = x0
        for ch, a in zip(s, adv):
            d.text((x, y0), ch, font=f, **kw)
            x += a + tracking * size
    mask = Image.new("L", (W, H), 0)
    draw_all(ImageDraw.Draw(mask), fill=255)
    outl = Image.new("L", (W, H), 0)
    draw_all(ImageDraw.Draw(outl), fill=255, stroke_width=sw, stroke_fill=255)
    if glow:
        gl = Image.new("RGBA", (W, H), glow[0] + (0,))
        gl.putalpha(outl.filter(ImageFilter.GaussianBlur(glow[1])))
        img.alpha_composite(gl)
        img.alpha_composite(gl)
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(outl.point(lambda v: int(v * shadow)))
        sh = sh.transform((W, H), Image.AFFINE, (1, 0, -round(size * 0.04), 0, 1, -round(size * 0.06)))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(2, size * 0.05))))
    if stroke:
        st = Image.new("RGBA", (W, H), stroke[0] + (255,))
        st.putalpha(outl)
        img.alpha_composite(st)
    bb = mask.getbbox() or (0, 0, 1, 1)
    g = np.clip((np.arange(H)[:, None] - bb[1]) / max(1, bb[3] - bb[1]), 0, 1)
    top, bot = np.array(fill[0], float), np.array(fill[1], float)
    grad = (top * (1 - g[..., None]) + bot * g[..., None]).astype(np.uint8)
    gi = Image.fromarray(np.dstack([np.broadcast_to(grad, (H, W, 3)), np.full((H, W), 255, np.uint8)]), "RGBA")
    gi.putalpha(mask)
    img.alpha_composite(gi)
    return bb


def zunda_cut(expr="驚", mouth="open", h=420, flip=False, box=(170, 20, 950, 980)):
    """立ち絵を切り抜いたもの (白いステッカーの縁はつけない)"""
    from zunda import character
    from zunda.compose import BASE, EXPR, MOUTH
    st = dict(BASE["Z"]); st.update(EXPR["Z"][expr]); st["!口"] = MOUTH["Z"][mouth]
    im = character.render("zundamon", st).crop(box)
    im = im.crop(im.getbbox())
    im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def place_char(img, ch, xy, rim=(150, 235, 255), shadow=0.75):
    """立ち絵を置く：落ち影と、背景から浮かせるための細い縁の光 (白い縁取りの代わり)"""
    a = ch.split()[3]
    layer = Image.new("L", (W, H), 0)
    layer.paste(a, xy)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.putalpha(layer.point(lambda v: int(v * shadow)))
    sh = sh.transform((W, H), Image.AFFINE, (1, 0, -10, 0, 1, -8))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    if rim:
        rl = Image.new("RGBA", (W, H), rim + (0,))
        rl.putalpha(layer.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.9)))
        img.alpha_composite(rl)
    img.alpha_composite(ch, xy)


def hud(img, c, r, color=(150, 235, 255), arm=0.32, width=6):
    """照準の角の印 (中心 c、半径 r)"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = c[0] - r, c[1] - r, c[0] + r, c[1] + r
    L = r * 2 * arm
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(x, y), (x + sx * L, y)], fill=color + (255,), width=width)
        d.line([(x, y), (x, y + sy * L)], fill=color + (255,), width=width)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(6)))
    img.alpha_composite(layer)


def badge(img, center, lines, size, angle=5, fill=(228, 32, 44)):
    """スタンプ (和文の極太は Noto Sans JP の Black。字の中が潰れない)"""
    f = vfont(NOTO, size, 900)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths = [tmp.textlength(t, font=f) for t in lines]
    lh = round(size * 1.12)
    bw, bh = round(max(widths) + size * 0.9), round(lh * len(lines) + size * 0.5)
    box = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle((20, 20, 20 + bw, 20 + bh), round(size * 0.3), fill=fill, outline=(255, 255, 255), width=7)
    for i, t in enumerate(lines):
        bd.text((20 + bw / 2, 20 + size * 0.2 + i * lh), t, font=f, fill=(255, 255, 255), anchor="ma")
    box = box.rotate(angle, resample=Image.BICUBIC, expand=True)
    pos = (round(center[0] - box.width / 2), round(center[1] - box.height / 2))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = box.split()[3]
    shl = Image.new("L", (W, H), 0)
    shl.paste(a, (pos[0] + 8, pos[1] + 12))
    sh.putalpha(shl.point(lambda v: int(v * 0.7)))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)))
    img.alpha_composite(box, pos)
