"""YouTube のサムネイル (1280×720)。数字は実データから。

ZX_VIDEO=heic uv run python videos/heic/tools/thumbnail.py [a b ...]  →  build/out/thumbnail_X.png (公開は V3)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path[:0] = [str(ROOT.parents[1]), str(ROOT)]  # リポジトリと動画のフォルダ
from vlib.data import SIZE_COLOR, cus, mean_abs_err, picture_size, pixels, size, splits  # noqa: E402

from zunda.thumb import (DELA, H, RED2, W, YEL2, YELLOW, black_tag, chevrons, face, heavy, mark, spot_bg, text)  # noqa: E402,F401


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def facts():
    j, w, h = size("cat_q80.jpg"), size("cat_q80.webp"), size("cat_q45")
    assert (j, w, h) == (23693, 16974, 13368)
    assert round((1 - h / j) * 10) == 4          # 「4割小さい」
    return j, w, h


def photo(name, w):
    im = Image.fromarray(pixels(name)).convert("RGBA")
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def partition(w, widths=None):
    """猫の写真 (自前の復号) に、実際の割れ方の線を重ねたもの (幅 w)"""
    W0, H0 = picture_size()
    im = photo("cat_q45", w)
    k = w / W0
    d = ImageDraw.Draw(im)
    widths = widths or {64: 5, 32: 4, 16: 3, 8: 2, 4: 1}

    def cross(x, y, s, size_):
        c = hex_rgb(SIZE_COLOR[size_])
        h = s / 2
        if x + h < W0:
            d.line([((x + h) * k, y * k), ((x + h) * k, min(y + s, H0) * k)], fill=c, width=widths[size_])
        if y + h < H0:
            d.line([(x * k, (y + h) * k), (min(x + s, W0) * k, (y + h) * k)], fill=c, width=widths[size_])
    for x in range(64, W0, 64):
        d.line([(x * k, 0), (x * k, H0 * k)], fill=hex_rgb(SIZE_COLOR[64]), width=widths[64])
    for y in range(64, H0, 64):
        d.line([(0, y * k), (W0 * k, y * k)], fill=hex_rgb(SIZE_COLOR[64]), width=widths[64])
    for s in splits():
        if s["split"]:
            cross(s["x"], s["y"], s["size"], s["size"] // 2)
    for c in cus():
        if c["nxn"]:
            cross(c["x"], c["y"], 8, 4)
    return im


def crop_zoom(name, box, out_w, out_h):
    im = Image.fromarray(pixels(name)).convert("RGBA").crop(box)
    return im.resize((out_w, out_h), Image.NEAREST)


def save(img, name):
    out = ROOT / f"build/out/{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    print(out)


def thumb_a():
    """シリーズの型：棒の落差。JPEG・WebP・HEIC (元とのずれはほぼ同じ)"""
    j, w, h = facts()
    img = spot_bg(cx=0.3)
    d = ImageDraw.Draw(img)
    base, top = 680, 200
    tall = base - top
    cols = [(150, 156, 172), (190, 196, 210), YELLOW]
    for i, (name, v) in enumerate((("JPEG", j), ("WebP", w), ("HEIC", h))):
        x0 = 60 + i * 200
        hh = round(tall * v / j)
        d.rounded_rectangle((x0, base - hh, x0 + 160, base), 14, fill=cols[i])
        heavy(img, (x0 + 80, base - hh - 82), name, 54, fill=YEL2 if name == "HEIC" else ((255, 255, 255),) * 2,
              anchor="ma")
        text(img, (x0 + 80, base - 64), f"{v / 1000:.1f}KB", 40, (30, 30, 40), (255, 255, 255), 6, anchor="ma",
             shadow=False)
    heavy(img, (900, 30), "同じ写真が", 80, anchor="ma")
    heavy(img, (900, 130), "4割", 200, fill=YEL2, anchor="ma")
    heavy(img, (930, 345), "小さい！？", 100, fill=YEL2, anchor="ma")
    zf = face(h=250)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_A")


def thumb_b():
    """中身を見せる型：写真に実際の割れ方。「iPhoneの写真 中身はこう！」"""
    im = partition(W, {64: 6, 32: 5, 16: 4, 8: 3, 4: 2})
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img.alpha_composite(im, (0, (H - im.height) // 2))
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = (np.clip((np.arange(H) - 330) / 300, 0, 1) * 235)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    black_tag(img, (300, 56), "iPhoneの写真 HEIC", 52)
    heavy(img, (40, 440), "ブロックを", 96)
    heavy(img, (40, 560), "割って縮める！", 120, fill=YEL2)
    zf = face(h=300)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_B")


def thumb_c():
    """どちらも 4KB：JPEG ✕ カクカク / HEIC ◎ くっきり →「HEICの圧勝！」"""
    j, h = size("cat_q5.jpg"), size("cat_q25")
    assert (j, h) == (3797, 3791) and round(j / 1000) == round(h / 1000) == 4
    assert mean_abs_err("cat_q25") < mean_abs_err("cat_q5.jpg") / 2
    box = (40, 10, 420, 295)
    hh = round(W * (box[3] - box[1]) / (box[2] - box[0]))
    L = crop_zoom("cat_q5.jpg", box, W, hh)
    R = crop_zoom("cat_q25", box, W, hh)
    oy = (H - hh) // 2 + 110
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img.alpha_composite(R, (0, oy))
    Ld = np.asarray(L).astype(np.float32)
    g = Ld[..., :3].mean(-1, keepdims=True)
    Ld[..., :3] = Ld[..., :3] * 0.55 + g * 0.25       # 負けている側は少しくすませる (WebP 編の M と同じ)
    L = Image.fromarray(np.clip(Ld, 0, 255).astype(np.uint8))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), (690, 0), (590, H), (0, H)], fill=255)
    Lfull = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    Lfull.alpha_composite(L, (0, oy))
    img.paste(Lfull, (0, 0), mask)
    ImageDraw.Draw(img).line([(690, 0), (590, H)], fill=(255, 255, 255), width=14)
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = (np.clip((np.arange(H) - 400) / 280, 0, 1) * 230)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    top = np.zeros((H, W, 4), np.uint8)
    top[..., 3] = (np.clip((170 - np.arange(H)) / 170, 0, 1) * 200)[:, None].astype(np.uint8)
    img.alpha_composite(Image.fromarray(top))
    black_tag(img, (640, 50), "どちらも 4KB", 50)
    mark(img, (78, 78), ok=False, r=46)
    heavy(img, (140, 22), "JPEG", 80, fill=RED2)
    heavy(img, (146, 120), "カクカク", 46)
    mark(img, (1202, 78), ok=True, r=46)
    heavy(img, (1140, 22), "HEIC", 80, fill=((140, 255, 160), (20, 190, 90)), anchor="ra")
    heavy(img, (1134, 120), "くっきり", 46, anchor="ra")
    heavy(img, (40, 545), "HEICの圧勝！", 140, fill=YEL2)
    zf = face(h=270)
    img.alpha_composite(zf, (W - zf.width + 50, H - zf.height + 40))
    save(img, "thumbnail_C")


def thumb_d():
    """フック：パソコンで開けない HEIC。左に「？」の窓、右に一言"""
    img = spot_bg(cx=0.32)
    d = ImageDraw.Draw(img)
    # パソコンの窓 (S01 と同じ見た目)
    x0, y0, x1, y1 = 70, 110, 650, 500
    d.rounded_rectangle((x0, y0, x1, y1), 22, fill=(30, 34, 44), outline=(120, 128, 146), width=8)
    d.rectangle(((x0 + x1) // 2 - 22, y1, (x0 + x1) // 2 + 22, y1 + 60), fill=(120, 128, 146))
    d.rounded_rectangle(((x0 + x1) // 2 - 120, y1 + 60, (x0 + x1) // 2 + 120, y1 + 80), 8, fill=(120, 128, 146))
    d.rounded_rectangle((x0 + 140, y0 + 50, x1 - 140, y1 - 120), 16, fill=(70, 76, 92))
    text(img, ((x0 + x1) // 2, y0 + 70), "？", 170, (190, 196, 210), (70, 76, 92), 0, anchor="ma", shadow=False)
    text(img, ((x0 + x1) // 2, y1 - 95), "cat.heic", 56, (255, 255, 255), (30, 34, 44), 4, anchor="ma",
         shadow=False)
    heavy(img, (960, 50), "iPhoneの写真", 76, anchor="ma")
    heavy(img, (960, 160), "開けない", 150, fill=RED2, anchor="ma")
    heavy(img, (930, 350), "のに小さい！？", 84, fill=YEL2, anchor="ma")
    zf = face(expr="困", mouth="half", h=250)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_D")


def facts_webp():
    w, h = size("cat_q80.webp"), size("cat_q45")
    assert (w, h) == (16974, 13368)
    assert round((1 - h / w) * 10) == 2                                  # 「2割小さい」
    assert abs(mean_abs_err("cat_q45") - mean_abs_err("cat_q80.webp")) < 0.1   # 見た目のずれはほぼ同じ
    return w, h


def pc_window(img, x0, y0, x1, y1, name="cat.heic", fs=50):
    """S01 と同じ見た目の、開けないパソコンの窓"""
    d = ImageDraw.Draw(img)
    cx = (x0 + x1) // 2
    d.rounded_rectangle((x0, y0, x1, y1), 22, fill=(30, 34, 44), outline=(120, 128, 146), width=8)
    d.rectangle((cx - 20, y1, cx + 20, y1 + 50), fill=(120, 128, 146))
    d.rounded_rectangle((cx - 110, y1 + 50, cx + 110, y1 + 68), 8, fill=(120, 128, 146))
    d.rounded_rectangle((x0 + 110, y0 + 40, x1 - 110, y1 - 105), 16, fill=(70, 76, 92))
    text(img, (cx, y0 + 52), "？", round((y1 - y0) * 0.38), (190, 196, 210), (70, 76, 92), 0, anchor="ma", shadow=False)
    text(img, (cx, y1 - 88), name, fs, (255, 255, 255), (30, 34, 44), 4, anchor="ma", shadow=False)


def thumb_e():
    """開けない (左の窓) ＞＞＞ でも WebP より小さい (右の棒)。見出しで言い切る"""
    w, h = facts_webp()
    img = spot_bg(cx=0.5, cy=0.55)
    heavy(img, (640, 18), "パソコンで開けないのに", 72, anchor="ma")
    pc_window(img, 40, 160, 480, 440, fs=46)
    mark(img, (440, 190), ok=False, r=44)
    chevrons(img, 515, 250, n=3, h=110)
    d = ImageDraw.Draw(img)
    base, top = 490, 210
    tall = base - top
    for i, (name, v, col) in enumerate((("WebP", w, (190, 196, 210)), ("HEIC", h, YELLOW))):
        x0 = 740 + i * 230
        hh = round(tall * v / w)
        d.rounded_rectangle((x0, base - hh, x0 + 180, base), 14, fill=col)
        heavy(img, (x0 + 90, base - hh - 70), name, 52, fill=YEL2 if name == "HEIC" else ((255, 255, 255),) * 2,
              anchor="ma")
        text(img, (x0 + 90, base - 60), f"{v / 1000:.1f}KB", 40, (30, 30, 40), (255, 255, 255), 6, anchor="ma",
             shadow=False)
    heavy(img, (520, 545), "WebPより2割小さい！", 96, fill=YEL2, anchor="ma")
    zf = face(h=230)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_E")


def thumb_f():
    """E を言葉少なく：大きな「開けない」の窓と、勝ちの一言だけ"""
    w, h = facts_webp()
    img = spot_bg(cx=0.3, cy=0.5)
    pc_window(img, 50, 70, 590, 450, fs=54)
    mark(img, (520, 120), ok=False, r=52)
    heavy(img, (320, 520), "開けない", 110, fill=RED2, anchor="ma")
    heavy(img, (960, 70), "なのに", 80, anchor="ma")
    heavy(img, (960, 170), "WebPより", 96, anchor="ma")
    heavy(img, (960, 290), "2割", 190, fill=YEL2, anchor="ma")
    heavy(img, (860, 500), "小さい！", 100, fill=YEL2, anchor="ma")
    zf = face(h=200)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_F")


def file_icon(img, x0, y0, w, label):
    """紙の角が折れたファイルの絵と、拡張子の帯"""
    h = round(w * 1.3)
    fold = round(w * 0.28)
    d = ImageDraw.Draw(img)
    body = [(x0, y0), (x0 + w - fold, y0), (x0 + w, y0 + fold), (x0 + w, y0 + h), (x0, y0 + h)]
    d.polygon(body, fill=(236, 238, 244))
    d.polygon([(x0 + w - fold, y0), (x0 + w - fold, y0 + fold), (x0 + w, y0 + fold)], fill=(180, 186, 200))
    text(img, (x0 + w // 2, y0 + round(h * 0.12)), "？", round(w * 0.62), (120, 128, 146), (236, 238, 244), 0,
         anchor="ma", shadow=False)
    bw = round(w * 1.15)
    bx = x0 + w // 2 - bw // 2
    by = y0 + round(h * 0.66)
    d.rounded_rectangle((bx, by, bx + bw, by + round(h * 0.22)), 18, fill=(230, 60, 50))
    text(img, (x0 + w // 2, by + round(h * 0.035)), label, round(h * 0.14), (255, 255, 255), (230, 60, 50), 0,
         anchor="ma", shadow=False, font=DELA)


def thumb_g():
    """謎の拡張子：大きなファイルの絵と「HEIC」だけ"""
    img = spot_bg(cx=0.32, cy=0.5)
    file_icon(img, 110, 90, 380, ".HEIC")
    heavy(img, (860, 120), "謎の拡張子", 96, anchor="ma")
    heavy(img, (860, 255), "HEIC", 180, fill=YEL2, anchor="ma")
    zf = face(expr="困", mouth="half", h=220)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_G")


def thumb_h():
    """謎の拡張子：中身 (割れ方の線) を背景に、「HEIC」を大きく"""
    im = partition(W, {64: 6, 32: 5, 16: 4, 8: 3, 4: 2})
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img.alpha_composite(im, (0, (H - im.height) // 2))
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = 120
    shade[..., 3] = np.maximum(shade[..., 3], (np.clip((np.arange(H) - 300) / 260, 0, 1) * 220)[:, None]).astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    heavy(img, (60, 300), "謎の拡張子", 92)
    heavy(img, (40, 410), "HEIC", 210, fill=YEL2)
    zf = face(expr="驚", h=270)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_H")


def thumb_i():
    """謎の拡張子：ファイルの絵の中身が猫の割れ方 (開けると中はこう)"""
    img = spot_bg(cx=0.5, cy=0.45)
    im = partition(560, {64: 4, 32: 3, 16: 3, 8: 2, 4: 1})
    x0, y0 = 80, 150
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0 - 14, y0 - 14, x0 + im.width + 14, y0 + im.height + 14), 18, fill=(236, 238, 244))
    img.alpha_composite(im, (x0, y0))
    bw = 300
    d.rounded_rectangle((x0 + im.width - bw + 40, y0 - 60, x0 + im.width + 40, y0 + 30), 18, fill=(230, 60, 50))
    text(img, (x0 + im.width - bw // 2 + 40, y0 - 52), ".HEIC", 68, (255, 255, 255), (230, 60, 50), 0, anchor="ma",
         shadow=False, font=DELA)
    heavy(img, (960, 120), "謎の拡張子", 80, anchor="ma")
    heavy(img, (960, 240), "HEIC", 150, fill=YEL2, anchor="ma")
    zf = face(expr="驚", h=220)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_I")


def thumb_j():
    """H ＋「WebPより2割小さい」：割れ方の線の猫を背景に"""
    facts_webp()
    im = partition(W, {64: 6, 32: 5, 16: 4, 8: 3, 4: 2})
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img.alpha_composite(im, (0, (H - im.height) // 2))
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., 3] = np.maximum(120, (np.clip((np.arange(H) - 220) / 260, 0, 1) * 225)[:, None]).astype(np.uint8)
    img.alpha_composite(Image.fromarray(shade))
    heavy(img, (60, 210), "謎の拡張子", 88)
    heavy(img, (40, 310), "HEIC", 210, fill=YEL2)
    heavy(img, (60, 560), "WebPより2割小さい", 84, fill=RED2)
    zf = face(expr="驚", h=260)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_J")


def thumb_k():
    """G ＋「WebPより2割小さい」：ファイルの絵と「HEIC」"""
    facts_webp()
    img = spot_bg(cx=0.32, cy=0.5)
    file_icon(img, 110, 110, 360, ".HEIC")
    heavy(img, (860, 80), "謎の拡張子", 92, anchor="ma")
    heavy(img, (860, 205), "HEIC", 180, fill=YEL2, anchor="ma")
    heavy(img, (760, 470), "WebPより", 80, anchor="ma")
    heavy(img, (750, 570), "2割小さい", 96, fill=RED2, anchor="ma")
    zf = face(expr="驚", h=220)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_K")


def sheet(keys):
    """案を並べ、YouTube の一覧の大きさ (幅 360・246) に縮めたものも添える"""
    ims = [Image.open(ROOT / f"build/out/thumbnail_{k.upper()}.png") for k in keys]
    big = Image.new("RGB", (640 * 2, 360 * ((len(ims) + 1) // 2)), (40, 40, 40))
    for i, im in enumerate(ims):
        big.paste(im.resize((640, 360), Image.LANCZOS), ((i % 2) * 640, (i // 2) * 360))
    small = Image.new("RGB", ((360 + 246 + 20) * 1, (203 + 10) * len(ims)), (255, 255, 255))
    for i, im in enumerate(ims):
        small.paste(im.resize((360, 203), Image.LANCZOS), (0, i * 213))
        small.paste(im.resize((246, 138), Image.LANCZOS), (370, i * 213))
    big.save(ROOT / "build/out/thumbnails.png")
    small.save(ROOT / "build/out/thumbnails_small.png")



# ================= 考え直した案 (X・Y・Z) =================
# 伝えること：みんなが見たことのある謎のファイル「.HEIC」が、実はすごい (WebP より小さい)。
# 武器：この動画にしかない絵＝写真に合わせて割れたブロック (中身の「透視図」)。光る線で見せる。

from PIL import ImageFilter  # noqa: E402


def part_segments():
    """割れ方の線 [(x0, y0, x1, y1, 割ったあとの大きさ)] (写真の画素の座標)"""
    W0, H0 = picture_size()
    segs = []

    def cross(x, y, s, k):
        h = s / 2
        if x + h < W0:
            segs.append((x + h, y, x + h, min(y + s, H0), k))
        if y + h < H0:
            segs.append((x, y + h, min(x + s, W0), y + h, k))
    for x in range(64, W0, 64):
        segs.append((x, 0, x, H0, 64))
    for y in range(64, H0, 64):
        segs.append((0, y, W0, y, 64))
    for s in splits():
        if s["split"]:
            cross(s["x"], s["y"], s["size"], s["size"] // 2)
    for c in cus():
        if c["nxn"]:
            cross(c["x"], c["y"], 8, 4)
    return segs


NEON = {64: (255, 255, 255), 32: (90, 170, 255), 16: (110, 240, 150), 8: (255, 215, 90), 4: (255, 130, 80)}


def neon_layer(scale, ox, oy, widths=None, glow=7, alpha=None):
    """割れ方の線を光らせたレイヤー (写真の画素 → 画面：x * scale + ox)。alpha：大きさごとの濃さ"""
    widths = widths or {64: 5, 32: 4, 16: 3.5, 8: 3, 4: 2.2}
    alpha = alpha or {64: 255, 32: 255, 16: 255, 8: 255, 4: 255}
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sharp)
    for x0, y0, x1, y1, k in sorted(part_segments(), key=lambda t: -t[4]):
        d.line([(x0 * scale + ox, y0 * scale + oy), (x1 * scale + ox, y1 * scale + oy)], fill=NEON[k] + (alpha[k],),
               width=max(1, round(widths[k])))
    g1 = sharp.filter(ImageFilter.GaussianBlur(glow))
    g2 = sharp.filter(ImageFilter.GaussianBlur(glow * 2.5))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for g in (g2, g1, g1):
        out.alpha_composite(g)
    out.alpha_composite(sharp)
    return out


def cat_full(scale_w=W, focus_y=0.40):
    """猫の写真 (自前の復号) を幅 scale_w に拡大し、画面 720 に切る。(画像, 倍率, 写真の上端の画面 y)"""
    W0, H0 = picture_size()
    k = scale_w / W0
    im = Image.fromarray(pixels("cat_q45")).convert("RGBA").resize((round(W0 * k), round(H0 * k)), Image.LANCZOS)
    oy = round(H / 2 - focus_y * H0 * k)
    oy = max(min(oy, 0), H - im.height)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    canvas.alpha_composite(im, (0, oy))
    return canvas, k, oy


def stamp(img, center, lines, size, angle=-8, fill=(225, 30, 40)):
    """斜めに押したスタンプ (赤い札に白い字)"""
    f = ImageFont.truetype(DELA, size)
    tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    widths = [d.textbbox((0, 0), s, font=f)[2] for s in lines]
    lh = round(size * 1.18)
    bw, bh = max(widths) + size, lh * len(lines) + round(size * 0.55)
    box = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle((20, 20, 20 + bw, 20 + bh), round(size * 0.35), fill=fill, outline=(255, 255, 255), width=8)
    for i, s in enumerate(lines):
        bd.text((20 + bw / 2, 20 + round(size * 0.28) + i * lh), s, font=f, fill=(255, 255, 255), anchor="ma")
    box = box.rotate(angle, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = np.asarray(box)[..., 3]
    shadow = Image.fromarray(np.dstack([np.zeros(a.shape + (3,), np.uint8), (a * 0.7).astype(np.uint8)]), "RGBA")
    pos = (round(center[0] - box.width / 2), round(center[1] - box.height / 2))
    sh.alpha_composite(shadow, (pos[0] + 8, pos[1] + 12))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    img.alpha_composite(box, pos)


from PIL import ImageFont  # noqa: E402


def thumb_x():
    """透視図：写真を斜めに切り、右は中身 (光るブロック)。左下に大きな「HEIC」"""
    facts_webp()
    photo_im, k, oy = cat_full(W, focus_y=0.42)
    # 右側：暗く・色を抜いた写真に、光る割れ方の線
    a = np.asarray(photo_im).astype(np.float32)
    g = a[..., :3].mean(-1, keepdims=True)
    xr = np.concatenate([(a[..., :3] * 0.25 + g * 0.15) * 0.55, a[..., 3:]], -1)
    xray = Image.fromarray(np.clip(xr, 0, 255).astype(np.uint8), "RGBA")
    xray.alpha_composite(neon_layer(k, 0, oy))
    mask = Image.new("L", (W, H), 0)
    seam = [(600, 0), (430, H)]
    ImageDraw.Draw(mask).polygon([seam[0], (W, 0), (W, H), seam[1]], fill=255)
    img = photo_im.copy()
    img.paste(xray, (0, 0), mask)
    # 境目の光る線
    line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(line).line(seam, fill=(255, 255, 255, 255), width=8)
    img.alpha_composite(line.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(line)
    # 左下を暗くして字を読みやすく
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip(((yy - 330) / 300) * 1.0 - (xx - 300) / 900, 0, 1) * 235
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    heavy(img, (44, 380), "謎の拡張子", 84)
    heavy(img, (30, 470), "HEIC", 230, fill=YEL2)
    stamp(img, (1010, 130), ["WebPより", "小さい"], 62, angle=6)
    zf = face(expr="驚", h=270)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_X")


def file_shape(w, h, fold, fill, outline=None, ow=0):
    im = Image.new("RGBA", (w + 2 * ow, h + 2 * ow), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(ow, ow), (ow + w - fold, ow), (ow + w, ow + fold), (ow + w, ow + h), (ow, ow + h)]
    if outline:
        d.polygon(pts, fill=outline)
        im = im.filter(ImageFilter.MaxFilter(ow * 2 + 1))
        d = ImageDraw.Draw(im)
    d.polygon(pts, fill=fill)
    d.polygon([(ow + w - fold, ow), (ow + w - fold, ow + fold), (ow + w, ow + fold)], fill=tuple(int(c * 0.72) for c in fill[:3]))
    return im


def thumb_y():
    """ファイルの大きさで勝ち負け：JPEG・WebP・HEIC のファイルの絵の面積を、バイト数に比例させる"""
    j, w = size("cat_q80.jpg"), size("cat_q80.webp")
    h = size("cat_q45")
    facts_webp()
    img = spot_bg(c0=(40, 46, 74), c1=(6, 7, 12), cx=0.42, cy=0.62)
    base_y = 610
    big = 330                                     # JPEG の絵の高さ
    xs = [150, 450, 760]
    for (name, v, col, lab), x in zip((("JPEG", j, (150, 156, 172), ".JPG"), ("WebP", w, (205, 210, 222), ".WEBP"),
                                        ("HEIC", h, (255, 214, 64), ".HEIC")), xs):
        s = (v / j) ** 0.5                           # 面積 ∝ バイト数
        fh = round(big * s)
        fw = round(fh * 0.78)
        fs = file_shape(fw, fh, round(fw * 0.28), col + (255,), outline=(10, 10, 14, 255) if name != "HEIC" else
                        (255, 255, 255, 255), ow=8)
        if name == "HEIC":
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            glow.alpha_composite(fs, (x - fs.width // 2, base_y - fs.height))
            gl = glow.filter(ImageFilter.GaussianBlur(28))
            img.alpha_composite(gl)
            img.alpha_composite(gl)
        img.alpha_composite(fs, (x - fs.width // 2, base_y - fs.height))
        text(img, (x, base_y - fs.height // 2 - 30), lab, round(fh * 0.17), (30, 30, 40), col, 0, anchor="ma",
             shadow=False, font=DELA)
        text(img, (x, base_y + 18), f"{v / 1000:.1f}KB", 44, (255, 255, 255), (10, 10, 14), 6, anchor="ma",
             shadow=False)
    heavy(img, (640, 30), "謎の拡張子が", 80, anchor="ma")
    heavy(img, (1010, 220), "最小", 190, fill=YEL2, anchor="ma")
    zf = face(expr="驚", h=260)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_Y")


def thumb_z():
    """謎のファイルが割れて、中から光るブロックの猫が出てくる"""
    facts_webp()
    img = spot_bg(c0=(34, 40, 66), c1=(5, 6, 10), cx=0.36, cy=0.5)
    # 割れたファイルの中身：光るブロックの猫
    fx, fy, fw, fh = 70, 70, 560, 590
    photo_im, k, oy = cat_full(1000, focus_y=0.42)
    a = np.asarray(photo_im).astype(np.float32)
    xr = np.concatenate([a[..., :3] * 0.42, a[..., 3:]], -1)
    inner = Image.fromarray(np.clip(xr, 0, 255).astype(np.uint8), "RGBA")
    inner.alpha_composite(neon_layer(k, 0, oy, widths={64: 4, 32: 3.5, 16: 3, 8: 2.5, 4: 1.8}, glow=6))
    inner = inner.crop((230, 0, 230 + fw, H))
    shape = file_shape(fw, fh, round(fw * 0.26), (255, 255, 255, 255))
    m = np.asarray(shape)[..., 3]
    body = Image.new("RGBA", shape.size, (0, 0, 0, 0))
    body.paste(inner.crop((0, fy, fw, fy + fh)), (0, 0), Image.fromarray(m))
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    halo.alpha_composite(shape, (fx, fy))
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(30)))
    img.alpha_composite(halo.filter(ImageFilter.MaxFilter(17)))
    img.alpha_composite(body, (fx, fy))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((fx - 30, fy + fh - 150, fx + fw + 30, fy + fh - 40), 20, fill=(230, 40, 40), outline=(255, 255, 255), width=8)
    text(img, (fx + fw // 2, fy + fh - 142), ".HEIC", 88, (255, 255, 255), (230, 40, 40), 0, anchor="ma", shadow=False,
         font=DELA)
    heavy(img, (950, 70), "謎の拡張子の", 72, anchor="ma")
    heavy(img, (950, 170), "中身", 200, fill=YEL2, anchor="ma")
    stamp(img, (930, 520), ["WebPより", "小さい"], 60, angle=-6)
    zf = face(expr="驚", h=250)
    img.alpha_composite(zf, (W - zf.width + 40, H - zf.height + 30))
    save(img, "thumbnail_Z")


def review(keys, out="review"):
    """大きい絵と、一覧の大きさ (360・246) を並べる"""
    ims = [Image.open(ROOT / f"build/out/thumbnail_{k.upper()}.png") for k in keys]
    s = Image.new("RGB", (640 + 380 + 256, 370 * len(ims)), (255, 255, 255))
    for i, im in enumerate(ims):
        s.paste(im.resize((640, 360), Image.LANCZOS), (0, i * 370))
        s.paste(im.resize((360, 203), Image.LANCZOS), (650, i * 370))
        s.paste(im.resize((246, 138), Image.LANCZOS), (1020, i * 370))
    s.save(ROOT / f"build/out/{out}.png")


def xray_split(seam, k_w=W, focus_y=0.45, keep=0.62, tint=(70, 120, 255)):
    """写真を seam (上の点, 下の点) で分け、左を透視図 (青みの暗い写真 + 光る割れ方の線)、右を普通の写真にする"""
    photo_im, k, oy = cat_full(k_w, focus_y=focus_y)
    a = np.asarray(photo_im).astype(np.float32)
    g = a[..., :3].mean(-1, keepdims=True) / 255
    xr = np.concatenate([g * np.array(tint) * keep + a[..., :3] * 0.12, a[..., 3:]], -1)
    xray = Image.fromarray(np.clip(xr, 0, 255).astype(np.uint8), "RGBA")
    xray.alpha_composite(neon_layer(k, 0, oy, widths={64: 5, 32: 4.5, 16: 4, 8: 3.2, 4: 2.4}, glow=6))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 0), seam[0], seam[1], (0, H)], fill=255)
    img = photo_im.copy()
    img.paste(xray, (0, 0), mask)
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(beam).line(seam, fill=(140, 230, 255, 255), width=10)
    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(18)))
    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(img).line(seam, fill=(235, 250, 255), width=6)
    return img


def thumb_x2():
    """X の改良：顔全体。左目 (ブロックが細かい) の側を透視図に。文字は右のぼやけた背景に"""
    facts_webp()
    img = xray_split(((760, 0), (600, H)))
    # 右下を少し暗く (字のため)
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - 700) / 500, 0, 1) * np.clip((yy - 250) / 300, 0, 1) * 200
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    heavy(img, (1240, 360), "謎の拡張子", 78, anchor="ra")
    heavy(img, (1250, 450), "HEIC", 190, fill=YEL2, anchor="ra")
    stamp(img, (1080, 120), ["WebPより", "小さい"], 58, angle=6)
    zf = face(expr="驚", h=250, flip=True)
    img.alpha_composite(zf, (-40, H - zf.height + 30))
    save(img, "thumbnail_X2")


def xray_band(band, k_w=W, focus_y=0.45, light=1.0):
    """写真の上に、band (多角形) の中だけ透視図 (明るい青の写真 + 光る割れ方の線)。帯の縁は光る線"""
    photo_im, k, oy = cat_full(k_w, focus_y=focus_y)
    a = np.asarray(photo_im).astype(np.float32)
    g = a[..., :3].mean(-1, keepdims=True) / 255
    g = np.clip((g - 0.18) / 0.62, 0, 1) ** 1.3                     # コントラストを上げる (瞳は暗く、まわりは明るく)
    xr = np.concatenate([g * np.array([150, 205, 255]) * light + 10, a[..., 3:]], -1)
    xray = Image.fromarray(np.clip(xr, 0, 255).astype(np.uint8), "RGBA")
    xray.alpha_composite(neon_layer(k, 0, oy, widths={64: 3, 32: 2.5, 16: 2.5, 8: 3.4, 4: 3},
                                    alpha={64: 110, 32: 90, 16: 120, 8: 255, 4: 255}, glow=5))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(band, fill=255)
    img = photo_im.copy()
    img.paste(xray, (0, 0), mask)
    edges = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(edges)
    n = len(band)
    for i in range(n):
        p0, p1 = band[i], band[(i + 1) % n]
        if 0 < p0[1] < H or 0 < p1[1] < H or p0[0] != p1[0]:
            if not ((p0[1] in (0, H)) and (p1[1] in (0, H)) and p0[1] == p1[1]):
                d.line([p0, p1], fill=(150, 235, 255, 255), width=8)
    img.alpha_composite(edges.filter(ImageFilter.GaussianBlur(16)))
    img.alpha_composite(edges.filter(ImageFilter.GaussianBlur(5)))
    img.alpha_composite(edges)
    return img


def thumb_x3():
    """スキャナーの帯：左目を通る斜めの帯の中だけ中身 (細かいブロック)。顔全体は猫のまま"""
    facts_webp()
    band = [(395, 0), (705, 0), (525, H), (215, H)]          # 左目 (画面の約 (470, 320)) を通る
    img = xray_band(band)
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - 760) / 400, 0, 1) * np.clip((yy - 240) / 260, 0, 1) * 210
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    heavy(img, (1245, 352), "謎の拡張子", 76, anchor="ra")
    heavy(img, (1255, 440), "HEIC", 196, fill=YEL2, anchor="ra")
    stamp(img, (1080, 125), ["WebPより", "2割小さい"], 56, angle=6)
    zf = face(expr="驚", h=240, flip=True)
    img.alpha_composite(zf, (-40, H - zf.height + 30))
    save(img, "thumbnail_X3")


def vignette(img, strength=0.55):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W * 0.5) / (W * 0.62)) ** 2 + ((yy - H * 0.45) / (H * 0.75)) ** 2)
    v = np.clip((r - 0.55) / 0.6, 0, 1) * 255 * strength
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))


def punch(img, c=1.12, sat=1.15):
    """コントラストと彩度を少し上げる (サムネの見栄え。動画の中の数字には関係しない)"""
    from PIL import ImageEnhance
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(c)
    rgb = ImageEnhance.Color(rgb).enhance(sat)
    return rgb.convert("RGBA")


def thumb_x4():
    """X3 の仕上げ：コントラストと周辺減光、「.HEIC」"""
    facts_webp()
    band = [(395, 0), (705, 0), (525, H), (215, H)]
    img = punch(xray_band(band))
    vignette(img)
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - 760) / 400, 0, 1) * np.clip((yy - 240) / 260, 0, 1) * 200
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    heavy(img, (1240, 350), "謎の拡張子", 76, anchor="ra")
    heavy(img, (1262, 440), ".HEIC", 172, fill=YEL2, anchor="ra")
    stamp(img, (1080, 125), ["WebPより", "2割小さい"], 56, angle=6)
    zf = face(expr="驚", h=240, flip=True)
    img.alpha_composite(zf, (-40, H - zf.height + 30))
    save(img, "thumbnail_X4")


def thumb_x5():
    """仕上げ：X4 の色 (コントラスト・周辺減光) に、X3 の大きな「HEIC」"""
    facts_webp()
    band = [(395, 0), (705, 0), (525, H), (215, H)]          # 左目 (細かいブロックが集まる所) を通る帯
    img = punch(xray_band(band))
    vignette(img)
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - 760) / 400, 0, 1) * np.clip((yy - 240) / 260, 0, 1) * 200
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    heavy(img, (1245, 352), "謎の拡張子", 76, anchor="ra")
    heavy(img, (1255, 440), "HEIC", 196, fill=YEL2, anchor="ra")
    stamp(img, (1080, 125), ["WebPより", "2割小さい"], 56, angle=6)
    zf = face(expr="驚", h=240, flip=True)
    img.alpha_composite(zf, (-40, H - zf.height + 30))
    save(img, "thumbnail_X5")


# ================= 文字と立ち絵の描き方を作り直したもの =================
INTER = str(ROOT.parents[1] / "assets/fonts/Inter-Variable.ttf")       # 英字：字の中の空きが大きく、極太でも潰れない
NOTO = str(ROOT.parents[1] / "assets/fonts/NotoSansJP-Variable.ttf")    # 和文


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


EYE = (468, 318)          # 左目の画面の位置 (cat_full(W, 0.45) のとき、写真の画素 (165, 120))
YEL_T, YEL_B = (255, 244, 120), (255, 168, 10)


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


def base_scan():
    band = [(395, 0), (705, 0), (525, H), (215, H)]
    img = punch(xray_band(band))
    vignette(img)
    hud(img, EYE, 118)
    return img


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


def right_shade(img, x0=760, y0=240):
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - x0) / 400, 0, 1) * np.clip((yy - y0) / 260, 0, 1) * 200
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))


def thumb_v1():
    """ずんだもんは左下、下の縁から大きく。文字は右下、スタンプは右上"""
    facts_webp()
    img = base_scan()
    right_shade(img)
    type_text(img, (1240, 330), "謎の拡張子", NOTO, 78, anchor="ra", stroke=((14, 12, 20), 0.10))
    type_text(img, (1250, 420), "HEIC", INTER, 210, fill=(YEL_T, YEL_B), stroke=((14, 12, 20), 0.05),
              tracking=0.01, anchor="ra")
    badge(img, (1075, 120), ["WebPより", "2割小さい"], 56)
    z = zunda_cut("驚", h=470, flip=True)
    place_char(img, z, (-60, H - z.height + 70))
    save(img, "thumbnail_V1")


def thumb_v2():
    """文字は右上。ずんだもんは右下で帯のほうへ振り向く。スタンプは左上"""
    facts_webp()
    img = base_scan()
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - 700) / 400, 0, 1) * np.clip((300 - yy) / 260, 0, 1) * 190
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    type_text(img, (1245, 22), "謎の拡張子", NOTO, 74, anchor="ra", stroke=((14, 12, 20), 0.10))
    type_text(img, (1255, 100), "HEIC", INTER, 200, fill=(YEL_T, YEL_B), stroke=((14, 12, 20), 0.05),
              tracking=0.01, anchor="ra")
    badge(img, (175, 115), ["WebPより", "2割小さい"], 52, angle=-6)
    z = zunda_cut("驚", h=430, flip=False)
    place_char(img, z, (W - z.width + 70, H - z.height + 60))
    save(img, "thumbnail_V2")


def thumb_v3():
    """V2 の仕上げ：主役 (左目の帯と照準) をさえぎらず、右上に文字、左上にスタンプ、右下にずんだもん"""
    facts_webp()
    img = base_scan()
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.clip((xx - 680) / 380, 0, 1) * np.clip((320 - yy) / 280, 0, 1) * 200
    img.alpha_composite(Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), v.astype(np.uint8)]), "RGBA"))
    type_text(img, (1245, 18), "謎の拡張子", NOTO, 84, anchor="ra", stroke=((14, 12, 20), 0.10))
    type_text(img, (1258, 104), "HEIC", INTER, 206, fill=(YEL_T, YEL_B), stroke=((14, 12, 20), 0.05),
              tracking=0.01, anchor="ra")
    badge(img, (178, 112), ["WebPより", "2割小さい"], 54, angle=-6)
    z = zunda_cut("驚", h=420, flip=False)
    place_char(img, z, (W - z.width + 80, H - z.height + 70))
    save(img, "thumbnail_V3")


if __name__ == "__main__":
    which = sys.argv[1:] or ["a", "b", "c", "d"]
    for k in which:
        globals()[f"thumb_{k}"]()
    review(which)
