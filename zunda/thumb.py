"""YouTube のサムネイル（1280×720）を作るときの共通部品。docs/publishing.md を参照。

    from zunda.thumb import W, H, FONT, MONO, YELLOW, ZCOL, MCOL, chara, text
"""
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
