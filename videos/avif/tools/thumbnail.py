"""YouTube のサムネイル (1280×720)。数字は実データから。

ZX_VIDEO=avif uv run python videos/avif/tools/thumbnail.py [a b ...]  →  build/out/thumbnail_X.png と review.png (一覧の大きさも並べたもの)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path[:0] = [str(ROOT.parents[1]), str(ROOT)]  # リポジトリと動画のフォルダ
from vlib.data import dec, mean_abs_err, picture_size, pixels, size  # noqa: E402

from zunda.thumb import H, INTER, NOTO, W, badge, hud, place_char, type_text, zunda_cut  # noqa: E402

YEL = ((255, 244, 120), (255, 168, 10))
WHITE = ((255, 255, 255), (226, 232, 245))
HEIC_C = (150, 162, 186)
INK = (14, 12, 20)
CYAN = (110, 225, 255)
DIR_DEG = {0: 45, 1: 22.5, 2: 0, 3: -22.5, 4: -45, 5: -67.5, 6: 90, 7: 67.5}   # CDEF の向き (S09 で毛に重ねて確かめたもの)


def facts():
    h, a = size("cat_q45.heic"), size("cat_q60")
    assert (h, a) == (13368, 13179) and abs(mean_abs_err("cat_q45.heic") - mean_abs_err("cat_q60")) < 0.1
    return h, a


def cat_full(w=W, focus_y=0.45):
    """猫の写真 (自前の復号) を幅 w に広げ、縦は画面の高さに合わせて切る。返り値は (画像, 倍率, 上の切り落とし)"""
    im = Image.fromarray(pixels("cat_q60")).convert("RGBA")
    k = w / im.width
    big = im.resize((w, round(im.height * k)), Image.LANCZOS)
    oy = round((big.height - H) * focus_y)
    return big.crop((0, oy, w, oy + H)), k, oy


def vignette(img, strength=0.55):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx / W - 0.5) * 1.3) ** 2 + (yy / H - 0.5) ** 2)
    a = (np.clip((r - 0.35) / 0.5, 0, 1) * 255 * strength).astype(np.uint8)
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), a]), "RGBA"))


def shade(img, fn, alpha=200):
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip(fn(xx, yy), 0, 1) * alpha
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))


def direction_layer(k, oy, color=CYAN, mask_poly=None, width=4):
    """CDEF が 8×8 ごとに見つけた模様の向き (dec().cdef_log) を、写真の上の光る短い線にした層"""
    blocks = dec().cdef_log["blocks"]
    assert len(blocks) == 2166
    vmax = np.percentile([b["var"] for b in blocks], 90)
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    L = 8 * k * 0.42
    for b in blocks:
        if b["dir"] is None:
            continue
        cx, cy = (b["x"] + 4) * k, (b["y"] + 4) * k - oy
        if not (-20 < cy < H + 20):
            continue
        t = np.radians(DIR_DEG[b["dir"]])
        dx, dy = np.cos(t) * L, -np.sin(t) * L
        a = int(90 + 165 * min(1.0, b["var"] / vmax))
        d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=color + (a,), width=width)
    if mask_poly is not None:
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon(mask_poly, fill=255)
        lines.putalpha(Image.fromarray(np.minimum(np.asarray(lines.split()[3]), np.asarray(m))))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(lines.filter(ImageFilter.GaussianBlur(5)))
    out.alpha_composite(lines)
    return out


def xray_band(band, keep=0.5, tint=(60, 110, 255)):
    """写真の一部 (多角形 band) を、青く暗い透視図 + 光る向きの線にする (HEIC 編の V3 と同じ作り)"""
    photo, k, oy = cat_full()
    a = np.asarray(photo).astype(np.float32)
    g = a[..., :3].mean(-1, keepdims=True) / 255
    xr = np.concatenate([g * np.array(tint) * keep + a[..., :3] * 0.10, a[..., 3:]], -1)
    xray = Image.fromarray(np.clip(xr, 0, 255).astype(np.uint8), "RGBA")
    xray.alpha_composite(direction_layer(k, oy))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(band, fill=255)
    img = photo.copy()
    img.paste(xray, (0, 0), mask)
    edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(edge).line(band + [band[0]], fill=CYAN + (255,), width=6)
    img.alpha_composite(edge.filter(ImageFilter.GaussianBlur(8)))
    img.alpha_composite(edge)
    return img, k, oy


def save(img, name):
    out = ROOT / f"build/out/{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    print(out)


# ================= 案 =================

def thumb_a():
    """HEIC 編 (V3) と同じ型：透視図の帯に CDEF の向きの線。右に「AVIF」、左上にスタンプ「特許料0円」"""
    facts()
    band = [(330, 0), (650, 0), (470, H), (150, H)]
    img, k, oy = xray_band(band)
    vignette(img, 0.4)
    shade(img, lambda xx, yy: ((xx - 680) / 380) * ((330 - yy) / 290), 200)
    type_text(img, (1248, 22), "HEICと同じ小ささ", NOTO, 66, anchor="ra", stroke=(INK, 0.10))
    type_text(img, (1262, 96), "AVIF", INTER, 214, fill=YEL, stroke=(INK, 0.05), tracking=0.01, anchor="ra")
    badge(img, (182, 118), ["特許料", "0円"], 64, angle=-6)
    z = zunda_cut("驚", h=420)
    place_char(img, z, (W - z.width + 80, H - z.height + 70))
    save(img, "thumbnail_A")


def thumb_b():
    """互角の勝負：左が HEIC、右が AVIF (どちらも同じ写真)。大きさの数字はほぼ同じ、下に「特許料0円」"""
    h, a = facts()
    photo, k, oy = cat_full()
    img = photo.copy()
    seam = [(700, 0), (580, H)]          # 左右とも同じ写真 (どちらかだけを暗くすると、優劣があるように見える)
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(beam).line(seam, fill=(255, 255, 255, 255), width=10)
    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(beam)
    vignette(img, 0.5)
    shade(img, lambda xx, yy: (yy - 380) / 260, 230)
    shade(img, lambda xx, yy: (200 - yy) / 200, 170)
    type_text(img, (300, 26), "HEIC", INTER, 120, fill=((225, 230, 240), HEIC_C), stroke=(INK, 0.06), anchor="ma")
    type_text(img, (300, 160), f"{h:,}バイト", NOTO, 56, fill=WHITE, stroke=(INK, 0.10), anchor="ma")
    type_text(img, (930, 26), "AVIF", INTER, 120, fill=YEL, stroke=(INK, 0.06), anchor="ma")
    type_text(img, (930, 160), f"{a:,}バイト", NOTO, 56, fill=WHITE, stroke=(INK, 0.10), anchor="ma")
    badge(img, (622, 120), ["ほぼ", "同じ"], 46, angle=0, fill=(40, 44, 58))
    type_text(img, (60, 470), "大きさは互角", NOTO, 74, stroke=(INK, 0.10))
    type_text(img, (52, 556), "特許料0円", NOTO, 132, fill=YEL, stroke=(INK, 0.08))
    z = zunda_cut("驚", h=430, flip=True)
    place_char(img, z, (W - z.width + 70, H - z.height + 70))
    save(img, "thumbnail_B")


def thumb_c():
    """開けない → 開ける：左は「？」のパソコン、右はブラウザで開いた猫。下に一言 (古いソフトでは開けないので「どこでも」とは言わない)"""
    from zunda.thumb import spot_bg
    facts()
    img = spot_bg((40, 48, 78), (8, 9, 14), cx=0.5, cy=0.4)

    def window(c, w, h, inner):
        x0, y0 = c[0] - w // 2, c[1] - h // 2
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 22, fill=(28, 31, 40, 255), outline=(110, 118, 140, 255), width=6)
        d.rectangle((x0 + 6, y0 + 6, x0 + w - 6, y0 + 52), fill=(44, 48, 60, 255))
        for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((x0 + 24 + i * 30, y0 + 20, x0 + 42 + i * 30, y0 + 38), fill=col + (255,))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(lay.split()[3].point(lambda v: int(v * 0.7)))
        img.alpha_composite(sh.transform((W, H), Image.AFFINE, (1, 0, -10, 0, 1, -14)).filter(ImageFilter.GaussianBlur(12)))
        img.alpha_composite(lay)
        inner(x0 + 18, y0 + 66, w - 36, h - 84)

    def qmark(x, y, w, h):
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((x, y, x + w, y + h), 14, fill=(52, 56, 68))
        type_text(img, (x + w / 2, y + 6), "？", NOTO, 150, fill=((150, 156, 172), (120, 126, 140)),
                  stroke=None, anchor="ma", shadow=0)
        type_text(img, (x + w / 2, y + h - 62), "cat.heic", INTER, 40, fill=((210, 214, 224), (180, 186, 200)),
                  stroke=None, anchor="ma", shadow=0)

    def photo(x, y, w, h):
        im = Image.fromarray(pixels("cat_q60")).convert("RGBA")
        k = max(w / im.width, h / im.height)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        ox, oy = (im.width - w) // 2, (im.height - h) // 2
        img.alpha_composite(im.crop((ox, oy, ox + w, oy + h)), (x, y))
    window((290, 205), 440, 340, qmark)
    window((880, 215), 560, 380, photo)
    d = ImageDraw.Draw(img)
    d.polygon([(536, 175), (596, 210), (536, 245)], fill=(255, 214, 64), outline=INK, width=4)
    type_text(img, (290, 386), "HEIC", INTER, 60, fill=((225, 230, 240), HEIC_C), stroke=(INK, 0.08), anchor="ma")
    type_text(img, (880, 416), "AVIF", INTER, 60, fill=YEL, stroke=(INK, 0.08), anchor="ma")
    type_text(img, (48, 488), "同じ小ささで", NOTO, 64, stroke=(INK, 0.10))
    type_text(img, (40, 560), "ブラウザで開ける", NOTO, 104, fill=YEL, stroke=(INK, 0.09))
    z = zunda_cut("驚", h=400, flip=True)
    place_char(img, z, (W - z.width + 70, H - z.height + 70))
    save(img, "thumbnail_C")


def review(keys, out="review"):
    """大きい絵と、一覧の大きさ (360・246) を並べる"""
    ims = [Image.open(ROOT / f"build/out/thumbnail_{k.upper()}.png") for k in keys]
    s = Image.new("RGB", (640 + 380 + 256, 370 * len(ims)), (255, 255, 255))
    for i, im in enumerate(ims):
        s.paste(im.resize((640, 360), Image.LANCZOS), (0, i * 370))
        s.paste(im.resize((360, 203), Image.LANCZOS), (650, i * 370))
        s.paste(im.resize((246, 138), Image.LANCZOS), (1020, i * 370))
    s.save(ROOT / f"build/out/{out}.png")
    print(ROOT / f"build/out/{out}.png")


if __name__ == "__main__":
    which = sys.argv[1:] or ["a", "b", "c"]
    for key in which:
        globals()[f"thumb_{key}"]()
    review(which)
