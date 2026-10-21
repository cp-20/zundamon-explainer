"""YouTube のサムネイル (1280×720)。数字は実データから。

ZX_VIDEO=webp uv run python videos/webp/tools/thumbnail.py [a b ...]  →  build/out/thumbnail_X.png (公開は M)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path[:0] = [str(ROOT.parents[1]), str(ROOT)]  # リポジトリと動画のフォルダ
from vlib.data import BMODE_NAME, file_bytes, mb, pixels, size, y_orig, y_pred  # noqa: E402

from zunda.thumb import FONT, H, MONO, W, YELLOW, ZCOL, chara, text  # noqa: E402,F401

CYAN = (79, 209, 232)
CORAL = (239, 111, 94)


def facts():
    j, w = size("cat_q80.jpg"), size("cat_q80")
    assert (j, w) == (23693, 16974)
    cut = 1 - w / j
    assert round(cut * 10) == 3       # 「3割」
    return j, w


def dark_bg(offset=40):
    """濃紺のグラデーションに、WebP ファイルのバイト列をうっすら"""
    g = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array([14, 16, 24]) * (1 - g) + np.array([30, 36, 56]) * g).astype(np.uint8)
    img = Image.fromarray(np.dstack([np.broadcast_to(bg, (H, W, 3)), np.full((H, W), 255, np.uint8)]), "RGBA")
    hexs = file_bytes("cat_q80")[offset:offset + 2000].hex(" ").upper().split()
    tex = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tex)
    f = ImageFont.truetype(MONO, 22)
    for n, row in enumerate(range(0, H, 34)):
        d.text((-10 + (n % 2) * 20, row), " ".join(hexs[n * 40:n * 40 + 40]), font=f, fill=(140, 160, 210, 34))
    img.alpha_composite(tex)
    return img


def gray(a, w):
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def photo(name, w):
    im = Image.fromarray(pixels(name)).convert("RGBA")
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def save(img, name):
    out = ROOT / f"build/out/{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    print(out)


def thumb_a():
    """シリーズの型：棒の落差。JPEG と WebP、同じ品質 80"""
    j, w = facts()
    img = dark_bg()
    d = ImageDraw.Draw(img)
    base, top = 660, 150
    tall = base - top
    short = round(tall * w / j)
    d.rounded_rectangle((80, top, 320, base), 14, fill=(150, 156, 172))
    d.rounded_rectangle((390, base - short, 630, base), 14, fill=YELLOW)
    text(img, (200, top - 95), "JPEG", 56, (255, 255, 255), (60, 64, 80), 9, anchor="ma")
    text(img, (200, base - 80), f"{j / 1000:.1f}KB", 52, (255, 255, 255), (60, 64, 80), 8, anchor="ma",
         shadow=False)
    text(img, (510, base - short - 95), "WebP", 56, YELLOW, (150, 90, 10), 9, anchor="ma")
    text(img, (510, base - 80), f"{w / 1000:.1f}KB", 52, (40, 40, 50), (255, 255, 255), 8, anchor="ma",
         shadow=False)
    text(img, (960, 40), "同じ写真が", 84, (255, 255, 255), (50, 56, 72), 12, anchor="ma")
    text(img, (960, 150), "3割", 180, YELLOW, (150, 40, 20), 18, anchor="ma")
    text(img, (960, 350), "小さい！？", 110, YELLOW, (150, 40, 20), 15, anchor="ma")
    zc = chara("Z", "zundamon", "驚", "open", 0.3, flip=True)
    img.alpha_composite(zc, (W - zc.width + 20, H - 170))
    save(img, "thumbnail_A")


def thumb_b():
    """「予想だけ」の画面：差を足す前の予想だけで、もうネコ"""
    img = dark_bg()
    yo, py = gray(y_orig(), 600), gray(y_pred(), 600)
    img.alpha_composite(yo, (30, 40))
    img.alpha_composite(py, (650, 40))
    d = ImageDraw.Draw(img)
    d.rectangle((650, 40, 650 + py.width - 1, 40 + py.height - 1), outline=CYAN, width=6)
    text(img, (330, 40 + yo.height + 10), "元の写真", 48, (255, 255, 255), (50, 56, 72), 9, anchor="ma")
    text(img, (950, 40 + py.height + 10), "となりから予想しただけ", 48, CYAN, (20, 60, 80), 9, anchor="ma")
    text(img, (640, 520), "WebPは「予想」で縮む", 92, YELLOW, (150, 40, 20), 15, anchor="ma")
    save(img, "thumbnail_B")


def thumb_c():
    """主役の 4×4 (目のふち)：まわりの点 (シアン) から、ななめになぞって予想した 16 マス (実際の値)"""
    from vlib.data import sub_block
    img = dark_bg()
    sb = sub_block()
    assert BMODE_NAME[sb["mode"]] == "VR"
    d = ImageDraw.Draw(img)
    cell, ox, oy = 92, 40, 120
    fnum = ImageFont.truetype(MONO, 36)

    def box(c, r, v, outline):
        x, y = ox + c * cell, oy + r * cell
        g = int(np.clip(v, 0, 255))
        d.rectangle((x, y, x + cell - 4, y + cell - 4), fill=(g, g, g), outline=outline, width=5)
        d.text((x + cell / 2 - 2, y + cell / 2 - 2), str(int(v)), font=fnum, anchor="mm",
               fill=(20, 22, 28) if g > 120 else (238, 240, 244))
    box(0, 0, sb["X"], CYAN)
    for i, v in enumerate(sb["top"]):
        box(1 + i, 0, v, CYAN)
    for i, v in enumerate(sb["left"]):
        box(0, 1 + i, v, CYAN)
    for r in range(4):
        for c in range(4):
            box(1 + c, 1 + r, sb["pred"][r][c], (60, 64, 76))
    d.rectangle((ox + cell - 4, oy + cell - 4, ox + 5 * cell, oy + 5 * cell), outline=YELLOW, width=8)
    # VR の向き (下へ、少し右へ)
    for k in range(4):
        sx, sy = ox + (1.5 + k) * cell, oy + 0.6 * cell
        ex, ey = sx + 1.6 * cell, sy + 3.3 * cell
        if ex > ox + 5 * cell:
            continue
        v = np.array([ex - sx, ey - sy]); v = v / np.linalg.norm(v); n_ = np.array([-v[1], v[0]])
        tip = np.array([ex, ey])
        d.line((sx, sy, *(tip - 30 * v)), fill=CYAN, width=12)
        d.polygon([tuple(tip), tuple(tip - 48 * v + 24 * n_), tuple(tip - 48 * v - 24 * n_)], fill=CYAN)
    text(img, (1250, 60), "WebPは", 90, (255, 255, 255), (50, 56, 72), 12, anchor="ra")
    text(img, (1250, 180), "となりから", 110, YELLOW, (150, 40, 20), 15, anchor="ra")
    text(img, (1250, 340), "予想する！？", 110, YELLOW, (150, 40, 20), 15, anchor="ra")
    mc = chara("M", "metan", "得意", "closed", 0.3)
    img.alpha_composite(mc, (W - mc.width + 30, H - 170))
    save(img, "thumbnail_C")


def thumb_d():
    """明るい地：フィルムの 1 コマ目に猫。「WebPの正体は動画の1コマ」"""
    yy, xx = np.mgrid[0:H, 0:W]
    ray = (np.sin(np.arctan2(yy - 360, xx - 330) * 14) > 0)
    base = np.where(ray[..., None], np.array([255, 205, 40]), np.array([255, 220, 90])).astype(np.uint8)
    img = Image.fromarray(np.dstack([base, np.full((H, W), 255, np.uint8)]), "RGBA")
    d = ImageDraw.Draw(img)
    # フィルム
    fx, fy, fw, fh = 30, 150, 640, 430
    d.rectangle((fx, fy, fx + fw, fy + fh), fill=(26, 28, 36))
    for k in range(0, fw, 46):
        d.rounded_rectangle((fx + 10 + k, fy + 12, fx + 34 + k, fy + 34), 4, fill=(255, 220, 90))
        d.rounded_rectangle((fx + 10 + k, fy + fh - 34, fx + 34 + k, fy + fh - 12), 4, fill=(255, 220, 90))
    ph = photo("cat_q80", 520)
    img.alpha_composite(ph, (fx + 60, fy + 50))
    text(img, (1250, 50), "WebPの正体は", 80, (30, 30, 40), (255, 255, 255), 12, anchor="ra", shadow=False)
    text(img, (1250, 170), "動画の", 160, (226, 50, 50), (255, 255, 255), 18, anchor="ra", shadow=False)
    text(img, (1250, 360), "1コマ！？", 140, (226, 50, 50), (255, 255, 255), 18, anchor="ra", shadow=False)
    zc = chara("Z", "zundamon", "驚", "open", 0.26)
    img.alpha_composite(zc, (760, H - 150))
    save(img, "thumbnail_D")


# ---------------- 2 回目の案 (E〜H)：主役を 1 つ、文字は 2 行まで、色数をしぼる ----------------

BOLD = FONT


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


def upper(im, frac=0.62):
    """立ち絵の上の部分 (胸から上)"""
    return im.crop((0, 0, im.width, round(im.height * frac)))


def big_text(img, xy, s, size, top, bottom, inner=(255, 255, 255), iw=0, outer=(20, 16, 30), ow=16,
             anchor="la", font=BOLD):
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
    f = ImageFont.truetype(BOLD, size)
    d = ImageDraw.Draw(img)
    bb = d.textbbox(xy, s, font=f, anchor=anchor)
    pad = size * 0.35
    d.rounded_rectangle((bb[0] - pad * 1.6, bb[1] - pad, bb[2] + pad * 1.6, bb[3] + pad), radius=size, fill=bg,
                        outline=(255, 255, 255), width=5)
    d.text(xy, s, font=f, anchor=anchor, fill=fg)


def crop_zoom(name, box, out_w, out_h):
    a = pixels(name)
    x0, y0, x1, y1 = box
    im = Image.fromarray(a[y0:y1, x0:x1]).convert("RGBA")
    return im.resize((out_w, out_h), Image.NEAREST)


YEL = ((255, 240, 120), (255, 170, 20))
WHT = ((255, 255, 255), (214, 222, 240))
RED = ((255, 120, 110), (220, 30, 40))


def thumb_e():
    """同じ 4KB の比べ：JPEG (品質 5) はカクカク、WebP (品質 10) はなめらか。目を画面いっぱいに"""
    j, w = size("cat_q5.jpg"), size("cat_q10")
    assert (j, w) == (3797, 3898) and round(j / 1000) == round(w / 1000) == 4
    img = spot_bg()
    box = (128, 70, 200, 151)                         # 目 (縦長の窓)
    L = crop_zoom("cat_q5.jpg", box, 636, 720)
    R = crop_zoom("cat_q10", box, 636, 720)
    img.alpha_composite(L, (0, 0))
    img.alpha_composite(R, (644, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((636, 0, 644, H), fill=(255, 255, 255))
    # 下を暗く (文字を読みやすく)
    g = np.clip((np.arange(H) - 330) / 390, 0, 1)[:, None] * 0.85
    shade = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8),
                                       np.broadcast_to((g * 255).astype(np.uint8), (H, W))]), "RGBA")
    img.alpha_composite(shade)
    pill(img, (150, 60), "JPEG", 46, (210, 50, 50))
    pill(img, (1130, 60), "WebP", 46, (40, 150, 90))
    big_text(img, (640, 410), "同じ4KBで", 84, *WHT, anchor="ma", ow=14)
    big_text(img, (640, 520), "この差！？", 150, *YEL, iw=8, inner=(120, 30, 10), ow=18, anchor="ma")
    save(img, "thumbnail_E")


def thumb_f():
    """「JPEGより 28% 軽い」：大きなカラーの猫と、大きな数字"""
    j, w = facts()
    pct = round((1 - w / j) * 100)
    assert pct == 28
    img = spot_bg(cx=0.72)
    cat = Image.fromarray(pixels("cat_q80")).convert("RGBA")
    ch = H
    cat = cat.resize((round(cat.width * ch / cat.height), ch), Image.LANCZOS).crop((0, 0, 720, ch))
    # 右端を背景へ溶かす
    al = np.clip((720 - np.arange(720)) / 260, 0, 1)
    a = np.broadcast_to((al * 255).astype(np.uint8), (ch, 720))
    cat.putalpha(Image.fromarray(np.minimum(np.asarray(cat.split()[3]), a)))
    img.alpha_composite(cat, (0, 0))
    big_text(img, (1010, 50), "同じ画質で", 74, *WHT, anchor="ma", ow=12)
    big_text(img, (1010, 140), f"{pct}%", 250, *YEL, iw=10, inner=(120, 30, 10), ow=20, anchor="ma")
    big_text(img, (1010, 420), "軽い！？", 130, *WHT, anchor="ma", ow=16)
    pill(img, (1010, 640), "JPEG → WebP", 40, (40, 150, 90))
    zc = sticker(upper(chara("Z", "zundamon", "驚", "open", 0.36), 0.55), ow=9)
    img.alpha_composite(zc, (-10, H - zc.height + 60))
    save(img, "thumbnail_F")


def thumb_g():
    """予想だけの画面：差を足す前なのに、もう猫。元と左右に、境目をシアンに光らせる"""
    img = spot_bg()
    yo = np.clip(y_orig(), 0, 255).astype(np.uint8)
    py = np.clip(y_pred(), 0, 255).astype(np.uint8)
    hh = 720
    def big(a):
        im = Image.fromarray(a).convert("RGBA")
        return im.resize((round(im.width * hh / im.height), hh), Image.LANCZOS)
    A, B = big(yo), big(py)
    # 左に元、右に予想だけ (同じ位置の画像の左右半分ずつ)
    cx = A.width // 2
    off = (W - A.width) // 2
    img.alpha_composite(A.crop((0, 0, cx, hh)), (off, 0))
    Bh = B.crop((cx, 0, A.width, hh))
    # 予想だけの側はシアンがかった色に
    arr = np.asarray(Bh).astype(np.float32)
    arr[..., 0] *= 0.75
    arr[..., 1] *= 0.98
    img.alpha_composite(Image.fromarray(arr.astype(np.uint8)), (off + cx, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((off + cx - 4, 0, off + cx + 4, H), fill=CYAN)
    g = np.clip((np.arange(H) - 360) / 360, 0, 1)[:, None] * 0.85
    shade = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8),
                                       np.broadcast_to((g * 255).astype(np.uint8), (H, W))]), "RGBA")
    img.alpha_composite(shade)
    pill(img, (off + cx - 170, 60), "元の写真", 40, (70, 76, 96))
    pill(img, (off + cx + 190, 60), "予想しただけ", 40, (20, 130, 160))
    big_text(img, (640, 420), "となりから予想するだけで", 66, *WHT, anchor="ma", ow=12)
    big_text(img, (640, 510), "もうネコ！？", 150, *YEL, iw=8, inner=(120, 30, 10), ow=18, anchor="ma")
    save(img, "thumbnail_G")


def thumb_h():
    """WebP の正体は動画の 1 コマ：横のフィルム、1 コマ目だけカラーで光る"""
    img = spot_bg(c0=(70, 30, 44), c1=(10, 8, 12), cx=0.3, cy=0.35)
    strip = Image.new("RGBA", (1600, 400), (14, 14, 18, 255))
    ds = ImageDraw.Draw(strip)
    for k in range(0, 1600, 52):
        ds.rounded_rectangle((k + 12, 14, k + 38, 38), 5, fill=(220, 220, 220))
        ds.rounded_rectangle((k + 12, 362, k + 38, 386), 5, fill=(220, 220, 220))
    cat = Image.fromarray(pixels("cat_q80")).convert("RGBA").resize((444, 296), Image.LANCZOS)
    dim = Image.fromarray((np.asarray(cat.convert("L").convert("RGBA")).astype(np.float32)
                           * [0.32, 0.32, 0.36, 1]).astype(np.uint8))
    for i in range(4):
        strip.alpha_composite(cat if i == 0 else dim, (40 + i * 480, 52))
    ImageDraw.Draw(strip).rectangle((34, 46, 34 + 456, 46 + 308), outline=YELLOW, width=8)
    img.alpha_composite(strip.crop((0, 0, W + 40, 400)), (-20, 40))
    big_text(img, (40, 470), "WebPの正体は", 76, *WHT, ow=13)
    big_text(img, (40, 560), "動画の1コマ！？", 120, *RED, iw=8, inner=(255, 255, 255), ow=18)
    zc = sticker(upper(chara("Z", "zundamon", "驚", "open", 0.32, flip=True), 0.55), ow=9)
    img.alpha_composite(zc, (W - zc.width + 50, H - zc.height + 60))
    save(img, "thumbnail_H")


# ---------------- 3 回目の案 (I〜L)：再生数の多い動画を参考に ----------------
# 和文の解説動画で伸びているもの：極太のゴシック、白と黒の二重の縁、大事な語だけ赤・黄、大きく切り抜いた顔、
# 吹き出し、赤い「＞＞＞」で前後をつなぐ。英語の画像圧縮の動画：ひとつの具体的な絵 (崩れた画素となめらかな画素)。

DELA = str(Path(FONT).with_name("DelaGothicOne-Regular.ttf"))


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


def thumb_i():
    """同じ 4KB：猫の顔をまん中で割って、左目は JPEG (ブロック)、右目は WebP (なめらか)"""
    j, w = size("cat_q5.jpg"), size("cat_q10")
    assert (j, w) == (3797, 3898) and round(j / 1000) == round(w / 1000) == 4
    box = (40, 10, 420, 295)                          # 顔全体 (4:3)
    hh = round(W * (box[3] - box[1]) / (box[2] - box[0]))
    L = crop_zoom("cat_q5.jpg", box, W, hh)
    R = crop_zoom("cat_q10", box, W, hh)
    oy = (H - hh) // 2 + 40
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img.alpha_composite(R, (0, oy))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (690, 0), (590, H), (0, H)], fill=255)
    Lfull = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    Lfull.alpha_composite(L, (0, oy))
    img.paste(Lfull, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.line([(690, 0), (590, H)], fill=(255, 255, 255), width=14)
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = (np.clip((np.arange(H) - 420) / 300, 0, 1) * 210)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    heavy(img, (40, 30), "JPEG", 90, fill=RED2)
    black_tag(img, (110, 170), "4KB")
    heavy(img, (1240, 30), "WebP", 90, fill=((140, 255, 160), (20, 190, 90)), anchor="ra")
    black_tag(img, (1170, 170), "4KB")
    heavy(img, (560, 535), "この差！？", 150, fill=YEL2, anchor="ma")
    zf = face(h=280)
    img.alpha_composite(zf, (W - zf.width + 50, H - zf.height + 40))
    save(img, "thumbnail_I")


def thumb_j():
    """顔が主役：大きなずんだもん + 「WebPの正体」+ 吹き出し"""
    j, w = facts()
    img = spot_bg(c0=(255, 210, 60), c1=(255, 150, 20), cx=0.72, cy=0.5)
    # 放射の線
    yy, xx = np.mgrid[0:H, 0:W]
    ray = (np.sin(np.arctan2(yy - 380, xx - 900) * 16) > 0.2)
    over = np.zeros((H, W, 4), np.uint8)
    over[ray] = (255, 255, 255, 45)
    img.alpha_composite(Image.fromarray(over))
    zf = face(h=760)
    img.alpha_composite(zf, (W - zf.width + 150, H - zf.height + 120))
    heavy(img, (40, 40), "WebPの", 120)
    heavy(img, (30, 190), "正体", 250, fill=RED2)
    bubble(img, (330, 600), "3割も軽いのだ！？", 58, tail=(220, 40))
    save(img, "thumbnail_J")


def thumb_k():
    """前 → 後：JPEG 23.7KB ＞＞＞ WebP 17.0KB、下に大きく「同じ画質で3割軽い」"""
    j, w = facts()
    img = spot_bg(c0=(40, 46, 70), c1=(6, 7, 12), cy=0.35)
    ph = Image.fromarray(pixels("cat_q80")).convert("RGBA").resize((450, 300), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    for x, lab, val, col in ((60, "JPEG", f"{j / 1000:.1f}KB", (90, 96, 112)),
                             (770, "WebP", f"{w / 1000:.1f}KB", (20, 170, 90))):
        d.rounded_rectangle((x - 10, 40, x + 460, 350), 18, fill=col)
        img.alpha_composite(ph, (x, 30 + 20))
        pill(img, (x + 225, 50), lab, 44, col)
        black_tag(img, (x + 225, 320), val, 50)
    chevrons(img, 540, 200, 3, 130)
    heavy(img, (700, 385), "同じ画質で", 80, anchor="ma")
    heavy(img, (290, 500), "3割", 165, fill=RED2, anchor="la")
    heavy(img, (640, 525), "軽い！？", 130, fill=YEL2, anchor="la")
    zf = face(h=270)
    img.alpha_composite(zf, (-70, H - zf.height + 40))
    save(img, "thumbnail_K")


def thumb_l():
    """写真が 16×16 のブロックに崩れていき、矢印で予想。「となりから予想」"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    cat = Image.fromarray(pixels("cat_q80")).convert("RGBA")
    cat = cat.resize((W, round(cat.height * W / cat.width)), Image.LANCZOS)
    img.alpha_composite(cat, (0, (H - cat.height) // 2))
    # 右の方ほど、ブロックごとの予想 (色は元の写真のブロックの平均で塗った「予想だけ」の明るさを使う)
    py = np.clip(y_pred(), 0, 255).astype(np.uint8)
    pyc = Image.fromarray(py).convert("RGBA").resize((W, round(py.shape[0] * W / py.shape[1])), Image.NEAREST)
    a = np.asarray(pyc).copy()
    xs = np.arange(a.shape[1])
    fade = np.clip((xs - 560) / 260, 0, 1)
    a[..., 3] = (fade * 255).astype(np.uint8)[None, :]
    tint = a.astype(np.float32)
    tint[..., 0] *= 0.55
    tint[..., 1] *= 0.95
    img.alpha_composite(Image.fromarray(tint.astype(np.uint8)), (0, (H - cat.height) // 2))
    # 16×16 の格子 (右側)
    d = ImageDraw.Draw(img)
    sc = W / 451
    for k in range(0, 452, 16):
        x = k * sc
        if x > 640:
            d.line([(x, 0), (x, H)], fill=(10, 12, 18), width=3)
    for k in range(0, 301, 16):
        y = (H - cat.height) / 2 + k * sc
        d.line([(640, y), (W, y)], fill=(10, 12, 18), width=3)
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = (np.clip((np.arange(H) - 380) / 340, 0, 1) * 220)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    heavy(img, (40, 420), "となりから", 100)
    heavy(img, (40, 535), "予想して縮む", 116, fill=YEL2)
    heavy(img, (1240, 40), "WebP", 110, fill=((150, 240, 255), (40, 170, 220)), anchor="ra")
    save(img, "thumbnail_L")


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


def thumb_m():
    """I の改良：「どちらも 4KB」を先に言い、JPEG は ✕ カクカク、WebP は ◎ なめらか、見出しで勝ちを言い切る"""
    j, w = size("cat_q5.jpg"), size("cat_q10")
    assert (j, w) == (3797, 3898) and round(j / 1000) == round(w / 1000) == 4
    box = (40, 10, 420, 295)
    hh = round(W * (box[3] - box[1]) / (box[2] - box[0]))
    L = crop_zoom("cat_q5.jpg", box, W, hh)
    R = crop_zoom("cat_q10", box, W, hh)
    oy = (H - hh) // 2 + 110
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img.alpha_composite(R, (0, oy))
    # JPEG 側は少しくすませる (負けている側)。WebP 側はそのまま
    Ld = np.asarray(L).astype(np.float32)
    gray = Ld[..., :3].mean(-1, keepdims=True)
    Ld[..., :3] = Ld[..., :3] * 0.55 + gray * 0.25
    L = Image.fromarray(np.clip(Ld, 0, 255).astype(np.uint8))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (690, 0), (590, H), (0, H)], fill=255)
    Lfull = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    Lfull.alpha_composite(L, (0, oy))
    img.paste(Lfull, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.line([(690, 0), (590, H)], fill=(255, 255, 255), width=14)
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = (np.clip((np.arange(H) - 400) / 280, 0, 1) * 230)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    # 上の帯：まん中に「どちらも 4KB」、左右に名前と印
    top = np.zeros((H, W, 4), np.uint8)
    top[..., 3] = (np.clip((170 - np.arange(H)) / 170, 0, 1) * 200)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(top))
    black_tag(img, (640, 50), "どちらも 4KB", 50)
    mark(img, (78, 78), ok=False, r=46)
    heavy(img, (140, 22), "JPEG", 80, fill=RED2)
    heavy(img, (146, 120), "カクカク", 46)
    mark(img, (1202, 78), ok=True, r=46)
    heavy(img, (1140, 22), "WebP", 80, fill=((140, 255, 160), (20, 190, 90)), anchor="ra")
    heavy(img, (1134, 120), "なめらか", 46, anchor="ra")
    # 下：言い切り
    heavy(img, (40, 545), "WebPの圧勝！", 140, fill=YEL2)
    zf = face(h=270)
    img.alpha_composite(zf, (W - zf.width + 50, H - zf.height + 40))
    save(img, "thumbnail_M")


if __name__ == "__main__":
    which = sys.argv[1:] or ["i", "j", "k", "l"]
    for k in which:
        globals()[f"thumb_{k}"]()
