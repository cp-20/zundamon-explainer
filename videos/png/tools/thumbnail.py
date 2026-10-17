"""YouTube のサムネイル（1280×720）。数字は実データから。

ZX_VIDEO=<video> uv run python videos/<video>/tools/thumbnail.py [a b ...]  →  build/out/thumbnail.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path[:0] = [str(ROOT.parents[1]), str(ROOT)]  # リポジトリと動画のフォルダ
from vlib.data import file_bytes, info  # noqa: E402

from zunda.thumb import FONT, H, MCOL, MONO, W, YELLOW, ZCOL, chara, text  # noqa: E402,F401


def facts():
    z = info("zundamon")
    raw, size = z["pixel_bytes"], len(file_bytes("zundamon"))
    big, small = f"{raw / 1e6:.1f}MB", f"{round(size / 1000)}KB"
    assert (big, small) == ("6.9MB", "333KB"), (big, small)
    return big, small, round(raw / size)


def dark_bg(offset=60000):
    g = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array([14, 16, 24]) * (1 - g) + np.array([30, 36, 56]) * g).astype(np.uint8)
    img = Image.fromarray(np.dstack([np.broadcast_to(bg, (H, W, 3)), np.full((H, W), 255, np.uint8)]), "RGBA")
    # 背景の模様：実ファイルのバイトを16進で敷き詰める
    hexs = file_bytes("zundamon")[offset:offset + 2000].hex(" ").upper().split()
    tex = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tex)
    f = ImageFont.truetype(MONO, 22)
    for n, row in enumerate(range(0, H, 34)):
        d.text((-10 + (n % 2) * 20, row), " ".join(hexs[n * 40:n * 40 + 40]), font=f, fill=(140, 160, 210, 34))
    img.alpha_composite(tex)
    return img


def zimg(height):
    zp = Image.open(ROOT / "data/zundamon.png").convert("RGBA")
    return zp.resize((round(zp.width * height / zp.height), height), Image.LANCZOS)


def grid(im, px, dark=0.55):
    """画素を px 角のマスに拡大して、境目に細い線"""
    blocky = im.resize((im.width // px, im.height // px), Image.BOX).resize(im.size, Image.NEAREST)
    bl = np.asarray(blocky).copy()
    bl[::px, :, :3] = (bl[::px, :, :3] * dark).astype(np.uint8)
    bl[:, ::px, :3] = (bl[:, ::px, :3] * dark).astype(np.uint8)
    return Image.fromarray(bl)


def save(img, name):
    out = ROOT / f"build/out/{name}.png"
    img.convert("RGB").save(out)
    print(out)


def thumb_a():
    """数字の落差＋崩れる画素"""
    big, small, _ = facts()
    img = dark_bg()
    zp = zimg(760)
    mask = Image.fromarray((np.clip((np.arange(zp.width) - zp.width * 0.35) / (zp.width * 0.25), 0, 1)[None, :]
                            * 255).repeat(zp.height, 0).astype(np.uint8))
    mixed = Image.composite(grid(zp, 26), zp, mask)
    a = np.asarray(mixed).copy()
    a[..., 3] = (a[..., 3] * 0.9).astype(np.uint8)
    img.alpha_composite(Image.fromarray(a), (800, -10))
    zc = chara("Z", "zundamon", "驚", "open", 0.62, flip=True)
    mc = chara("M", "metan", "得意", "closed", 0.5)
    img.alpha_composite(mc, (W - mc.width + 70, H - 330))
    img.alpha_composite(zc, (-40, H - 300))
    text(img, (48, 44), "PNGの中身", 64, (255, 255, 255), (40, 120, 200), 12)
    text(img, (44, 132), big, 118, (220, 224, 235), (50, 56, 72), 12)
    bb = text(img, (390, 160), "→", 96, (255, 255, 255), (50, 56, 72), 10)
    text(img, (bb[2] + 10, 110), small, 168, YELLOW, (150, 40, 20), 16)
    text(img, (300, 330), "1バイトも", 92, (255, 255, 255), ZCOL, 14)
    text(img, (360, 440), "消えないのだ！？", 92, (255, 255, 255), ZCOL, 14)
    save(img, "thumbnail_A")


def thumb_b():
    """棒グラフの落差：巨大な棒と、髪の毛ほどの棒"""
    big, small, ratio = facts()
    img = dark_bg(120000)
    d = ImageDraw.Draw(img)
    base, top = 660, 40
    tall = base - top
    tiny = max(4, round(tall / ratio))
    d.rounded_rectangle((90, top, 330, base), 14, fill=(236, 104, 90))
    d.rounded_rectangle((400, base - tiny, 640, base), 4, fill=(72, 200, 230))
    text(img, (210, 300), big, 78, (255, 255, 255), (140, 40, 30), 10, anchor="mm", shadow=False)
    text(img, (520, base - tiny - 70), small, 78, (72, 200, 230), (14, 40, 60), 10, anchor="mm")
    text(img, (950, 20), "1/" + str(ratio), 210, YELLOW, (150, 40, 20), 18, anchor="ma")
    text(img, (950, 255), "なのに", 72, (255, 255, 255), (50, 56, 72), 10, anchor="ma")
    text(img, (950, 335), "劣化ゼロ！？", 104, (255, 255, 255), ZCOL, 14, anchor="ma")
    zc = chara("Z", "zundamon", "驚", "open", 0.46)
    img.alpha_composite(zc, (W - zc.width + 20, H - 215))
    save(img, "thumbnail_B")


def thumb_c():
    """虫めがね：画像の目のあたりを拡大すると、色の数字の粒"""
    _, small, _ = facts()
    img = dark_bg(200000)
    zp = zimg(700)
    zx, zy = 70, 10
    img.alpha_composite(zp, (zx, zy))
    full = Image.open(ROOT / "data/zundamon.png").convert("RGBA")
    s = full.width / zp.width
    fx, fy = 468, 446  # 元画像の上の、のぞく場所（口のあたり）
    cx, cy = round(fx / s), round(fy / s)
    R, n = 205, 15     # 拡大鏡の半径と、見せる画素の数（n×n）
    crop = full.crop((fx - n // 2, fy - n // 2, fx + n // 2 + 1, fy + n // 2 + 1))
    cell = 2 * R // n + 1
    mag = grid(crop.resize((n * cell, n * cell), Image.NEAREST), cell, 0.4)
    bgc = Image.new("RGBA", mag.size, (30, 34, 48, 255))
    bgc.alpha_composite(mag)
    mx, my = 730, 250
    mk = Image.new("L", bgc.size, 0)
    ImageDraw.Draw(mk).ellipse((0, 0, bgc.width - 1, bgc.height - 1), fill=255)
    d = ImageDraw.Draw(img)
    d.line((zx + cx, zy + cy, mx, my), fill=(255, 255, 255), width=6)
    d.ellipse((zx + cx - 34, zy + cy - 34, zx + cx + 34, zy + cy + 34), outline=(255, 255, 255), width=6)
    img.paste(bgc, (mx - bgc.width // 2, my - bgc.height // 2), mk)
    d.ellipse((mx - bgc.width // 2 - 8, my - bgc.height // 2 - 8, mx + bgc.width // 2 + 8, my + bgc.height // 2 + 8),
              outline=(255, 255, 255), width=14)
    # 真ん中の1画素の、実際の RGBA
    r, g, b, a = full.getpixel((fx, fy))
    text(img, (730, 500), f"R{r} G{g} B{b} A{a}", 44, (255, 255, 255), (50, 56, 72), 8, font=MONO, anchor="ma")
    text(img, (1250, 40), "PNGの中身", 92, (255, 255, 255), (40, 120, 200), 14, anchor="ra")
    text(img, (1250, 160), "のぞいて", 110, YELLOW, (150, 40, 20), 14, anchor="ra")
    text(img, (1250, 290), "みた", 110, YELLOW, (150, 40, 20), 14, anchor="ra")
    zc = chara("Z", "zundamon", "考", "closed", 0.44)
    img.alpha_composite(zc, (W - zc.width + 40, H - 250))
    save(img, "thumbnail_C")


def thumb_d():
    """明るい黄色地：一目で数字"""
    big, small, _ = facts()
    yy, xx = np.mgrid[0:H, 0:W]
    ang = np.arctan2(yy - 380, xx - 640)
    ray = (np.sin(ang * 14) > 0)
    base = np.where(ray[..., None], np.array([255, 205, 40]), np.array([255, 220, 90])).astype(np.uint8)
    img = Image.fromarray(np.dstack([base, np.full((H, W), 255, np.uint8)]), "RGBA")
    bb = text(img, (640, 40), big, 120, (90, 90, 100), (255, 255, 255), 12, anchor="ma", shadow=False)
    d = ImageDraw.Draw(img)
    d.line((bb[0] + 10, bb[3] - 10, bb[2] - 10, bb[1] + 20), fill=(226, 50, 50), width=16)
    text(img, (640, 150), small, 220, (226, 50, 50), (255, 255, 255), 20, anchor="ma")
    text(img, (640, 418), "1バイトも消えない！？", 72, (30, 30, 40), (255, 255, 255), 14, anchor="ma")
    zc = chara("Z", "zundamon", "驚", "open", 0.5, flip=True)
    mc = chara("M", "metan", "笑", "closed", 0.42)
    img.alpha_composite(zc, (-40, H - 215))
    img.alpha_composite(mc, (W - mc.width + 60, H - 205))
    save(img, "thumbnail_D")


if __name__ == "__main__":
    which = sys.argv[1:] or ["a", "b", "c", "d"]
    for k in which:
        globals()[f"thumb_{k}"]()
