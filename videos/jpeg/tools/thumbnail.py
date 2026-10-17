"""YouTube のサムネイル（1280×720）。数字は実データから。

ZX_VIDEO=<video> uv run python videos/<video>/tools/thumbnail.py [a b ...]  →  build/out/thumbnail.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path[:0] = [str(ROOT.parents[1]), str(ROOT)]  # リポジトリと動画のフォルダ
from vlib.data import BASIS, block_coef, file_bytes, pixels  # noqa: E402

from zunda.thumb import FONT, H, MCOL, MONO, W, YELLOW, ZCOL, chara, text  # noqa: E402,F401


def facts():
    png, jpg = len(file_bytes("cat")), len(file_bytes("cat_q80"))
    big, small = f"{round(png / 1000)}KB", f"{round(jpg / 1000)}KB"
    ratio = round(png / jpg)
    assert (big, small, ratio) == ("219KB", "24KB", 9), (big, small, ratio)
    return big, small, ratio


def dark_bg(seed_offset=4000):
    g = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array([14, 16, 24]) * (1 - g) + np.array([30, 36, 56]) * g).astype(np.uint8)
    img = Image.fromarray(np.dstack([np.broadcast_to(bg, (H, W, 3)), np.full((H, W), 255, np.uint8)]), "RGBA")
    # 背景の模様：実ファイルのバイトを16進で敷き詰める
    hexs = file_bytes("cat_q80")[seed_offset:seed_offset + 2000].hex(" ").upper().split()
    tex = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tex)
    f = ImageFont.truetype(MONO, 22)
    for n, row in enumerate(range(0, H, 34)):
        d.text((-10 + (n % 2) * 20, row), " ".join(hexs[n * 40:n * 40 + 40]), font=f, fill=(140, 160, 210, 34))
    img.alpha_composite(tex)
    return img


def photo(name, height, box=None):
    im = Image.fromarray(pixels(name)[..., :3]).convert("RGBA")
    if box:
        im = im.crop(box)
    return im.resize((round(im.width * height / im.height), height), Image.NEAREST if box else Image.LANCZOS)


def save(img, name):
    out = ROOT / f"build/out/{name}.png"
    img.convert("RGB").save(out)
    print(out)


def thumb_a():
    """PNG 編のサムネ B と同じ型：棒の落差＋「1/9 なのに見分けがつかない」"""
    big, small, ratio = facts()
    img = dark_bg()
    d = ImageDraw.Draw(img)
    base, top = 660, 40
    tall = base - top
    tiny = round(tall / ratio)
    d.rounded_rectangle((90, top, 330, base), 14, fill=(236, 104, 90))
    d.rounded_rectangle((400, base - tiny, 640, base), 8, fill=(72, 200, 230))
    text(img, (210, 250), "PNG", 60, (255, 255, 255), (140, 40, 30), 9, anchor="mm", shadow=False)
    text(img, (210, 330), big, 64, (255, 255, 255), (140, 40, 30), 9, anchor="mm", shadow=False)
    text(img, (520, base - tiny - 130), "JPEG", 60, (72, 200, 230), (14, 40, 60), 9, anchor="mm")
    text(img, (520, base - tiny - 60), small, 64, (72, 200, 230), (14, 40, 60), 9, anchor="mm")
    text(img, (950, 20), "1/" + str(ratio), 210, YELLOW, (150, 40, 20), 18, anchor="ma")
    text(img, (950, 245), "なのに", 64, (255, 255, 255), (50, 56, 72), 10, anchor="ma")
    text(img, (950, 315), "見分けが", 88, (255, 255, 255), ZCOL, 13, anchor="ma")
    text(img, (950, 415), "つかない！？", 88, (255, 255, 255), ZCOL, 13, anchor="ma")
    zc = chara("Z", "zundamon", "驚", "open", 0.4)
    img.alpha_composite(zc, (W - zc.width + 20, H - 150))
    save(img, "thumbnail_A")


def thumb_b():
    """品質を下げすぎた写真：左はきれい、右はカクカク"""
    img = dark_bg(9000)
    h = 450
    good, bad = photo("cat_q80", h), photo("cat_q5", h)
    w = good.width
    half = Image.new("RGBA", (w, h))
    half.paste(good.crop((0, 0, w // 2, h)), (0, 0))
    half.paste(bad.crop((w // 2, 0, w, h)), (w // 2, 0))
    x0, y0 = (W - w) // 2, 30
    img.alpha_composite(half, (x0, y0))
    d = ImageDraw.Draw(img)
    d.line((x0 + w // 2, y0, x0 + w // 2, y0 + h), fill=(255, 255, 255), width=6)
    text(img, (x0 + w // 4, y0 + 18), "品質80", 44, (255, 255, 255), (30, 34, 48), 9, anchor="ma")
    text(img, (x0 + 3 * w // 4, y0 + 18), "品質5", 44, (255, 255, 255), (150, 40, 20), 9, anchor="ma")
    text(img, (640, 505), "JPEGは何を", 80, (255, 255, 255), (50, 56, 72), 12, anchor="ma")
    text(img, (640, 600), "捨てている？", 96, YELLOW, (150, 40, 20), 14, anchor="ma")
    zc = chara("Z", "zundamon", "驚", "open", 0.36, flip=True)
    mc = chara("M", "metan", "得意", "closed", 0.34)
    img.alpha_composite(zc, (-30, H - 190))
    img.alpha_composite(mc, (W - mc.width + 40, H - 190))
    save(img, "thumbnail_B")


def thumb_c():
    """64 種類の波の模様：「写真は波でできている！？」"""
    img = dark_bg(15000)
    tile, gap = 62, 6
    gx, gy = 70, 70
    for uu in range(8):
        for vv in range(8):
            b = BASIS[uu, vv]
            g = np.full((8, 8), 200.0) if uu == vv == 0 else 128 + 127 * b / np.abs(b).max()
            t = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).resize((tile, tile), Image.NEAREST).convert("RGBA")
            img.alpha_composite(t, (gx + vv * (tile + gap), gy + uu * (tile + gap)))
    text(img, (1230, 70), "写真は", 96, (255, 255, 255), (50, 56, 72), 13, anchor="ra")
    text(img, (1230, 190), "波で", 140, YELLOW, (150, 40, 20), 16, anchor="ra")
    text(img, (1230, 360), "できている！？", 84, (255, 255, 255), ZCOL, 13, anchor="ra")
    text(img, (1230, 480), "JPEGのしくみ", 52, (255, 255, 255), (40, 120, 200), 10, anchor="ra")
    zc = chara("Z", "zundamon", "考", "closed", 0.42)
    img.alpha_composite(zc, (W - zc.width - 20, H - 170))
    save(img, "thumbnail_C")


def thumb_d():
    """明るい黄色地：「1/9」と「わざと捨ててる」"""
    big, small, ratio = facts()
    yy, xx = np.mgrid[0:H, 0:W]
    ang = np.arctan2(yy - 380, xx - 640)
    ray = (np.sin(ang * 14) > 0)
    base = np.where(ray[..., None], np.array([255, 205, 40]), np.array([255, 220, 90])).astype(np.uint8)
    img = Image.fromarray(np.dstack([base, np.full((H, W), 255, np.uint8)]), "RGBA")
    cat = photo("cat_q80", 300)
    img.alpha_composite(cat, ((W - cat.width) // 2, 30))
    text(img, (640, 330), "JPEGは", 70, (30, 30, 40), (255, 255, 255), 12, anchor="ma", shadow=False)
    text(img, (640, 410), "わざと捨ててる！？", 104, (226, 50, 50), (255, 255, 255), 16, anchor="ma")
    zc = chara("Z", "zundamon", "驚", "open", 0.5, flip=True)
    mc = chara("M", "metan", "得意", "closed", 0.42)
    img.alpha_composite(zc, (-40, H - 215))
    img.alpha_composite(mc, (W - mc.width + 60, H - 205))
    save(img, "thumbnail_D")


def thumb_e():
    """C の強化版：猫の写真の目のブロックが、右いっぱいの 64 の波の模様に広がる"""
    img = Image.new("RGBA", (W, H), (10, 10, 16, 255))
    # 右：大きな 64 模様（暗い紫 → 明るい黄の2色で塗る）
    tile, gap = 80, 6
    gx, gy = W - 8 * (tile + gap) - 10, (H - 8 * (tile + gap) + gap) // 2
    lo, hi = np.array([34, 16, 64]), np.array([255, 226, 120])
    for uu in range(8):
        for vv in range(8):
            b = BASIS[uu, vv]
            g = np.full((8, 8), 0.85) if uu == vv == 0 else 0.5 + 0.5 * b / np.abs(b).max()
            rgb = (lo + (hi - lo) * g[..., None]).astype(np.uint8)
            t = Image.fromarray(rgb).resize((tile, tile), Image.NEAREST).convert("RGBA")
            img.alpha_composite(t, (gx + vv * (tile + gap), gy + uu * (tile + gap)))
    # 左：猫の顔（右端は模様へ溶ける）
    cat = Image.fromarray(pixels("cat")[..., :3]).convert("RGBA")
    cat = cat.crop((20, 0, 330, 300)).resize((744, 720), Image.LANCZOS)
    a = np.asarray(cat).copy()
    fade = np.clip((np.arange(cat.width) - 520) / 220, 0, 1)
    a[..., 3] = (255 * (1 - fade))[None, :].astype(np.uint8)
    img.alpha_composite(Image.fromarray(a), (0, 0))
    # 目のブロックを光る四角で示し、模様のほうへ線を伸ばす
    d = ImageDraw.Draw(img)
    s = 744 / 310
    ex, ey = round((20 * 8 - 20) * s), round(13 * 8 * 720 / 300)  # 主役のブロック (13, 20) = 瞳のふち
    bs = round(8 * s)
    d.rectangle((ex, ey, ex + bs, ey + 8 * 720 / 300), outline=(255, 226, 120), width=5)
    for cx, cy in [(gx, gy), (gx, gy + 8 * (tile + gap) - gap)]:
        d.line((ex + bs, ey + (0 if cy == gy else 8 * 720 / 300), cx, cy), fill=(255, 226, 120, 200), width=3)
    # 文字
    text(img, (40, 300), "写真は", 92, (255, 255, 255), (20, 20, 30), 14)
    text(img, (30, 385), "波で", 210, YELLOW, (150, 40, 20), 20)
    text(img, (40, 700), "できている！？", 74, (255, 255, 255), ZCOL, 12, anchor="ls")
    zc = chara("Z", "zundamon", "驚", "open", 0.42)
    img.alpha_composite(zc, (W - zc.width + 30, H - 190))
    save(img, "thumbnail_E")


if __name__ == "__main__":
    which = sys.argv[1:] or ["a", "b", "c", "d", "e"]
    for k in which:
        globals()[f"thumb_{k}"]()
