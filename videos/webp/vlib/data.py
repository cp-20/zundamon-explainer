"""実データ。画面に出す数値はすべてここ (data/ と tools/ の自前の復号器の結果) から取る。"""
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
import vp8  # noqa: E402
import webpanalyze as W  # noqa: E402

MAIN = "cat_q80"
MAIN_MB = (10, 7)        # 主役の MB (横, 縦)。猫の左目の瞳のふち
MAIN_SB = 13             # その中の 4×4 の番号 (ラスタ順)
BMODE_NAME = vp8.BMODE_NAME


def path(name):
    """名前 (拡張子は省略可。省略すると webp → png → jpg → gif の順に探す) → data/ のファイル"""
    if (DATA / name).is_file():
        return DATA / name
    for ext in ("webp", "png", "jpg", "gif"):
        p = DATA / f"{name}.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(name)


@lru_cache(None)
def file_bytes(name):
    return path(name).read_bytes()


@lru_cache(None)
def pixels(name):
    """Pillow で読んだ RGB(A)。WebP は libwebp の復号 (画面に出す絵として使う)"""
    im = Image.open(path(name))
    return np.asarray(im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"))


@lru_cache(None)
def webp(name=MAIN):
    """自前の復号器の結果 (tools/webpanalyze.py)"""
    return W.analyze(path(name))


def vp8_info(name=MAIN):
    return webp(name)["vp8"]


def _crop(a, name):
    v = vp8_info(name)
    return np.array(a, np.int32)[:v["height"], :v["width"]]


def y_decoded(name=MAIN, filt=False):
    """復号した明るさ。filt=False はループフィルタの前 (予想に使う値)"""
    v = vp8_info(name)
    return _crop(v["Y"] if filt else v["Y_nofilter"], name)


def y_pred(name=MAIN):
    """どのブロックも、差を足す前の予想だけを並べた明るさ"""
    return _crop(vp8_info(name)["PY"], name)


@lru_cache(None)
def y_orig(src="cat"):
    """元の写真の明るさ。libwebp が保存のときに使う式 (VP8RGBToY) と同じ"""
    rgb = np.asarray(Image.open(path(src)).convert("RGB")).astype(np.int64)
    y = (16839 * rgb[..., 0] + 33059 * rgb[..., 1] + 6420 * rgb[..., 2] + (1 << 15) + (16 << 16)) >> 16
    return y.astype(np.int32)


def mb(mx=MAIN_MB[0], my=MAIN_MB[1], name=MAIN):
    return vp8_info(name)["mbs"][my][mx]


def sub_block(mx=MAIN_MB[0], my=MAIN_MB[1], b=MAIN_SB, name=MAIN):
    """4×4 の予想の材料と結果。dict(x, y (画素の左上), mode, top (8), left (4), X, pred (4×4), orig (4×4), levels)"""
    m = mb(mx, my, name)
    p = m["pred4"][b]
    x, y = mx * 16 + 4 * (b % 4), my * 16 + 4 * (b // 4)
    return dict(x=x, y=y, mode=m["bmodes"][b], top=p["top"], left=p["left"], X=p["X"],
                pred=np.array(p["pred"], np.int32), orig=y_orig()[y:y + 4, x:x + 4].copy(),
                levels=m["levels"][b], segment=m["segment"])


def big_preds(mx=MAIN_MB[0], my=MAIN_MB[1], name=MAIN):
    """その MB の上と左の点 (ループフィルタの前) から作った、16×16 の 4 つの予想 (縦・横・平均・TM)"""
    Y = vp8_info(name)["Y_nofilter"]
    W_ = vp8_info(name)["mbw"] * 16
    top, left, X = vp8._edges(Y, mx * 16, my * 16, 16, 0, my > 0, mx > 0, W_)
    out = {}
    for k, mode in (("V", vp8.V_PRED), ("H", vp8.H_PRED), ("DC", vp8.DC_PRED), ("TM", vp8.TM_PRED)):
        out[k] = np.array(vp8.pred_big(mode, top, left, X, 16, my > 0, mx > 0), np.int32)
    return out, np.array(top[:16]), np.array(left), X


def fmt(n):
    return f"{n:,}"


# ---------------- 大きさ・ずれ ----------------

def size(name):
    """ファイルの大きさ (バイト)"""
    return len(file_bytes(name))


GIF_STAMP = ROOT.parent / "gif" / "data" / "zunda_anim.gif"


def gif_stamp_size():
    return GIF_STAMP.stat().st_size


def mean_abs_err(name, src="cat"):
    """元の写真との、1 つの点あたりの平均のずれ (RGB の 3 色の差の絶対値の平均)"""
    a = np.asarray(Image.open(path(src)).convert("RGB")).astype(float)
    b = np.asarray(Image.open(path(name)).convert("RGB")).astype(float)
    return float(np.abs(a - b).mean())


# ---------------- 非可逆 (VP8) ----------------

def y_planes(name=MAIN):
    """復号した Y・U・V (ループフィルタあり、画像の大きさに切ったもの)"""
    v = vp8_info(name)
    w, h = v["width"], v["height"]
    cw, ch = (w + 1) // 2, (h + 1) // 2
    return (np.array(v["Y"], np.int32)[:h, :w], np.array(v["U"], np.int32)[:ch, :cw],
            np.array(v["V"], np.int32)[:ch, :cw])


def fdct4(d):
    """VP8 の 4×4 の変換 (libwebp の FTransform と同じ整数の計算)。d は 4×4 の差。返り値はラスタ順の 16 個"""
    d = [[int(x) for x in r] for r in d]
    tmp = [0] * 16
    for i in range(4):
        d0, d1, d2, d3 = d[i]
        a0, a1, a2, a3 = d0 + d3, d1 + d2, d1 - d2, d0 - d3
        tmp[0 + i * 4] = (a0 + a1) * 8
        tmp[1 + i * 4] = (a2 * 2217 + a3 * 5352 + 1812) >> 9
        tmp[2 + i * 4] = (a0 - a1) * 8
        tmp[3 + i * 4] = (a3 * 2217 - a2 * 5352 + 937) >> 9
    out = [0] * 16
    for i in range(4):
        a0, a1 = tmp[0 + i] + tmp[12 + i], tmp[4 + i] + tmp[8 + i]
        a2, a3 = tmp[4 + i] - tmp[8 + i], tmp[0 + i] - tmp[12 + i]
        out[0 + i] = (a0 + a1 + 7) >> 4
        out[4 + i] = ((a2 * 2217 + a3 * 5352 + 12000) >> 16) + (a3 != 0)
        out[8 + i] = (a0 - a1 + 7) >> 4
        out[12 + i] = (a3 * 2217 - a2 * 5352 + 51000) >> 16
    return out


def quant_steps(segment, name=MAIN):
    """その区分けの、明るさの 4×4 の割る数 (直流, それ以外)"""
    return vp8_info(name)["quant"][segment]["y1"]


def quantize(coefs, steps):
    """割って丸める (四捨五入)。係数はラスタ順の 16 個"""
    out = []
    for k, c in enumerate(coefs):
        q = steps[0] if k == 0 else steps[1]
        out.append(int(np.sign(c)) * ((abs(c) + q // 2) // q))
    return out


@lru_cache(None)
def basis4():
    """4×4 の 16 種類の模様 (VP8 の逆変換に 1 つの係数だけを入れたもの)。[k] は 4×4、k はラスタ順"""
    out = []
    for k in range(16):
        c = [0] * 16
        c[k] = 128
        out.append(np.array(vp8.idct4(c), np.int32))
    return out


def all_levels(name=MAIN):
    """書いた数 (段の数) をすべて。MB の順、各 MB の 24 個の 4×4 (Y 16・U 4・V 4) × 16"""
    v = vp8_info(name)
    return np.array([m["levels"][b] for r in v["mbs"] for m in r for b in range(24)], np.int32)


def decisions(name=MAIN):
    """係数を読んだ「はい・いいえ」の判定の数と、係数の区画のビット数"""
    v = vp8_info(name)
    n = sum(len(m["tok_log"][b] or []) for r in v["mbs"] for m in r for b in range(25))
    return n, sum(v["partitions"]) * 8


def bits_of(log):
    """判定の記録 [(確率, ビット, …)] を書くのに要るビット数 (−log2 の和)"""
    import math
    return sum(-math.log2((p if b == 0 else 256 - p) / 256) for p, b, *_ in log)


# ---------------- 可逆 (VP8L)・透明・動き ----------------

def vp8l_info(name="zunda_lossless"):
    """自前の VP8L 復号の結果。transforms (type 0 予測・1 色の相関・2 緑を引く・3 色の表、bits、data)、
    tokens [("lit", 位置, 1, ビット) / ("copy", 位置, 長さ, ビット, 距離の番号, 距離, (左へ, 上へ)) /
    ("cache", 位置, 1, ビット, 表の番号)]、cache_bits、residual (変換したあとの値)、argb (元の色)"""
    return webp(name)["vp8l"]


def distance_map():
    """距離の番号 1〜120 → (左へ, 上へ)"""
    import vp8l
    return list(vp8l.DISTANCE_MAP)


def alpha_info(name="zunda_q80"):
    """VP8X・ALPH・VP8 の箱の並び [(名前, 大きさ)] と、ALPH の透明度 (2 次元)"""
    w = webp(name)
    return [(t, n) for t, _, n in w["chunks"]], w["alph"]["alpha"]


def anim_frames(name="zunda_anim"):
    """動く WebP の各コマ：dict(x, y, width, height, duration (ms), blend, chunk_bytes, rgba (そのコマの四角))"""
    w = webp(name)
    out = []
    for fr in w["frames"]:
        out.append(dict(x=fr["x"], y=fr["y"], width=fr["width"], height=fr["height"], duration=fr["duration"],
                        blend=fr["blend"], chunk_bytes=sum(n for _, _, n in fr["chunks"]),
                        rgba=fr["vp8l"]["rgba"]))
    return out


def anim_canvas(name="zunda_anim"):
    """各コマを重ねた画面 (RGBA) の列。透明な点は前のコマが透ける"""
    w = webp(name)
    W_, H_ = w["vp8x"]["width"], w["vp8x"]["height"]
    canvas = np.zeros((H_, W_, 4), np.float32)
    out = []
    for fr in anim_frames(name):
        src = fr["rgba"].astype(np.float32)
        reg = canvas[fr["y"]:fr["y"] + fr["height"], fr["x"]:fr["x"] + fr["width"]]
        if fr["blend"]:
            a = src[..., 3:4] / 255
            rgb = src[..., :3] * a + reg[..., :3] * (1 - a)
            al = src[..., 3:4] + reg[..., 3:4] * (1 - a)
            reg[:] = np.concatenate([rgb, al], -1)
        else:
            reg[:] = src
        out.append(canvas.astype(np.uint8).copy())
    return out
