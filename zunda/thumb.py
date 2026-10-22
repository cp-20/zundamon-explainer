"""YouTube のサムネイル（1280×720）を作るときの共通部品。docs/publishing.md を参照。

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
