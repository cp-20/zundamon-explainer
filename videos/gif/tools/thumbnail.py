"""YouTube のサムネイル（1280×720）。数字は実データから。

ZX_VIDEO=<video> uv run python videos/<video>/tools/thumbnail.py [a b ...]  →  build/out/thumbnail.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path[:0] = [str(ROOT.parents[1]), str(ROOT)]  # リポジトリと動画のフォルダ
from vlib.data import file_bytes, frame_rgba, info, palette, pixels, png_sizes  # noqa: E402

from zunda.thumb import FONT, H, MCOL, MONO, W, YELLOW, ZCOL, chara, text  # noqa: E402,F401


def facts():
    one_png, gif_size = png_sizes()[0], info()["file_bytes"]
    a, b = f"{round(one_png / 1000)}KB", f"{round(gif_size / 1000)}KB"
    assert (a, b) == ("42KB", "29KB"), (a, b)
    return a, b


def dark_bg(offset=300):
    g = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array([14, 16, 24]) * (1 - g) + np.array([30, 36, 56]) * g).astype(np.uint8)
    img = Image.fromarray(np.dstack([np.broadcast_to(bg, (H, W, 3)), np.full((H, W), 255, np.uint8)]), "RGBA")
    hexs = file_bytes("zunda_anim")[offset:offset + 2000].hex(" ").upper().split()
    tex = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tex)
    f = ImageFont.truetype(MONO, 22)
    for n, row in enumerate(range(0, H, 34)):
        d.text((-10 + (n % 2) * 20, row), " ".join(hexs[n * 40:n * 40 + 40]), font=f, fill=(140, 160, 210, 34))
    img.alpha_composite(tex)
    return img


def frame(k, h):
    im = Image.fromarray(frame_rgba(k=k))
    return im.resize((round(im.width * h / im.height), h), Image.NEAREST)


def save(img, name):
    out = ROOT / f"build/out/{name}.png"
    img.convert("RGB").save(out)
    print(out)


def thumb_a():
    """シリーズの型：棒の落差。PNG 1 枚 > GIF 8 枚"""
    a, b = facts()
    img = dark_bg()
    d = ImageDraw.Draw(img)
    base, top = 660, 120
    tall = base - top
    short = round(tall * info()["file_bytes"] / png_sizes()[0])
    d.rounded_rectangle((80, top, 320, base), 14, fill=(236, 104, 90))
    d.rounded_rectangle((390, base - short, 630, base), 14, fill=(110, 220, 130))
    text(img, (200, top - 95), "PNG 1枚", 48, (255, 255, 255), (140, 40, 30), 9, anchor="ma")
    text(img, (200, base - 80), a, 60, (255, 255, 255), (140, 40, 30), 9, anchor="ma", shadow=False)
    text(img, (510, base - short - 95), "GIF 8枚", 48, (110, 220, 130), (20, 60, 30), 9, anchor="ma")
    text(img, (510, base - 80), b, 60, (255, 255, 255), (20, 60, 30), 9, anchor="ma", shadow=False)
    text(img, (960, 30), "8枚なのに", 80, (255, 255, 255), (50, 56, 72), 12, anchor="ma")
    text(img, (960, 130), "1枚より", 120, YELLOW, (150, 40, 20), 16, anchor="ma")
    text(img, (960, 285), "小さい！？", 120, YELLOW, (150, 40, 20), 16, anchor="ma")
    st = frame(6, 300)
    img.alpha_composite(st, (W - st.width - 40, H - st.height - 10))
    save(img, "thumbnail_A")


def thumb_b():
    """8 コマのパラパラ漫画＋「動く画像の中身」"""
    img = dark_bg(900)
    h = 300
    fr = [frame(k, h) for k in range(8)]
    gap = 8
    total = sum(f.width for f in fr) + gap * 7
    x = (W - total) // 2
    for k, f in enumerate(fr):
        y = 40 + (k % 2) * 30
        img.alpha_composite(f, (x, y))
        x += f.width + gap
    text(img, (640, 410), "動く画像の中身", 100, (255, 255, 255), (40, 120, 200), 14, anchor="ma")
    text(img, (640, 540), "GIFのしくみ", 120, YELLOW, (150, 40, 20), 16, anchor="ma")
    save(img, "thumbnail_B")


def thumb_c():
    """LZW の辞書：色の並びに番号"""
    img = dark_bg(1500)
    pal = palette("cat16_nodither")
    seqs = [(258, [15, 14]), (259, [14, 12]), (260, [12, 14]), (261, [14, 12, 12])]
    d = ImageDraw.Draw(img)
    cell = 86
    fnum = ImageFont.truetype(MONO, 46)
    for r, (code, sq) in enumerate(seqs):
        y = 60 + r * 120
        d.text((70, y + 10), str(code), font=fnum, fill=(197, 146, 234))
        for k, v in enumerate(sq):
            x0 = 230 + k * (cell + 8)
            c = tuple(int(t) for t in pal[v])
            d.rounded_rectangle((x0, y, x0 + cell, y + cell), 10, fill=c)
    text(img, (1230, 60), "GIFは", 90, (255, 255, 255), (50, 56, 72), 12, anchor="ra")
    text(img, (1230, 170), "辞書で", 150, YELLOW, (150, 40, 20), 18, anchor="ra")
    text(img, (1230, 350), "縮む！？", 120, (255, 255, 255), ZCOL, 15, anchor="ra")
    zc = chara("Z", "zundamon", "驚", "open", 0.42, flip=True)
    img.alpha_composite(zc, (-30, H - 200))
    mc = chara("M", "metan", "得意", "closed", 0.4)
    img.alpha_composite(mc, (W - mc.width + 40, H - 190))
    save(img, "thumbnail_C")


def thumb_d():
    """明るい黄色地：動くスタンプと「8枚で29KB」"""
    a, b = facts()
    yy, xx = np.mgrid[0:H, 0:W]
    ray = (np.sin(np.arctan2(yy - 380, xx - 400) * 14) > 0)
    base = np.where(ray[..., None], np.array([255, 205, 40]), np.array([255, 220, 90])).astype(np.uint8)
    img = Image.fromarray(np.dstack([base, np.full((H, W), 255, np.uint8)]), "RGBA")
    for k, (dx, dy) in enumerate([(40, 60), (150, 40), (260, 20)]):
        f = frame([0, 1, 6][k], 560)
        img.alpha_composite(f, (dx, dy + 40))
    text(img, (1240, 60), "GIFの", 90, (30, 30, 40), (255, 255, 255), 12, anchor="ra", shadow=False)
    text(img, (1240, 170), "中身", 170, (226, 50, 50), (255, 255, 255), 18, anchor="ra", shadow=False)
    text(img, (1240, 380), "のぞいたら", 90, (30, 30, 40), (255, 255, 255), 12, anchor="ra", shadow=False)
    text(img, (1240, 500), "辞書があった！？", 76, (30, 30, 40), (255, 255, 255), 12, anchor="ra", shadow=False)
    save(img, "thumbnail_D")


if __name__ == "__main__":
    which = sys.argv[1:] or ["a", "b", "c", "d"]
    for k in which:
        globals()[f"thumb_{k}"]()
