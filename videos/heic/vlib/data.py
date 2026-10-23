"""実データ。画面に出す数値はすべてここ (data/ と tools/ の自前の読み取り器・復号器の結果) から取る。"""
import io
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
import heif as HEIF  # noqa: E402
import hevc  # noqa: E402

MAIN = "cat_q45"
MAIN_CTB = (2, 2)        # 四分木の見本の 64×64 (横, 縦)。左目の下のふち
SIZE_COLOR = {64: "#eef0f4", 32: "#5aa7ea", 16: "#7fd18b", 8: "#e8c36a", 4: "#f08a5d"}


def path(name):
    """名前 (拡張子は省略可。省略すると heic → png → webp → jpg の順に探す) → data/ のファイル"""
    if (DATA / name).is_file():
        return DATA / name
    for ext in ("heic", "png", "webp", "jpg"):
        p = DATA / f"{name}.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(name)


@lru_cache(None)
def file_bytes(name):
    return path(name).read_bytes()


def size(name):
    return len(file_bytes(name))


def fmt(n):
    return f"{n:,}"


@lru_cache(None)
def pixels(name):
    """絵として出す RGB(A)。HEIC は自前の復号器の Y・U・V を RGB にしたもの、それ以外は Pillow"""
    p = path(name)
    if p.suffix == ".heic":
        return rgb_decoded(name)
    im = Image.open(p)
    return np.asarray(im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"))


def mean_abs_err(name, src="cat"):
    """元の写真との、1 つの点あたりの平均のずれ (RGB の 3 色の差の絶対値の平均)。
    HEIC は libheif (pillow-heif) で RGB にしたもの (見る人のソフトが出す色)"""
    a = np.asarray(Image.open(path(src)).convert("RGB")).astype(float)
    p = path(name)
    if p.suffix == ".heic":
        import pillow_heif
        b = np.asarray(pillow_heif.open_heif(p).to_pillow().convert("RGB")).astype(float)
    else:
        b = np.asarray(Image.open(p).convert("RGB")).astype(float)
    return float(np.abs(a - b).mean())


# ---------------- 箱 (HEIF) ----------------

@lru_cache(None)
def boxes(name=MAIN):
    """自前の箱の読み取りの結果 (tools/heif.py)"""
    return HEIF.parse(path(name))


# ---------------- 本体 (HEVC) ----------------

@lru_cache(None)
def dec(name=MAIN):
    """自前の HEVC 復号器の結果 (tools/hevc.py の Decoder)。ffmpeg と全画素一致を確認済み"""
    return hevc.decode_heic(path(name))


def picture_size(name=MAIN):
    """(幅, 高さ)：切り取ったあとの写真の大きさ"""
    r = boxes(name)
    it = r["items"][r["primary"]]
    c = HEIF.item_prop(it, "clap") or HEIF.item_prop(it, "ispe")
    return c["width"], c["height"]


@lru_cache(None)
def rgb_decoded(name=MAIN, stage="final"):
    """自前の復号の Y・U・V を RGB に (colr の決まり：BT.601、全範囲)。色は縦横 2 倍に線形補間"""
    d = dec(name)
    planes = {"final": d.final, "deblocked": d.deblocked, "recon": d.recon, "pred": d.pred}[stage]
    Y, U, V = (np.asarray(p, np.float32) for p in d.cropped(planes))
    h, w = Y.shape
    up = [np.asarray(Image.fromarray(c).resize((w, h), Image.BILINEAR), np.float32) - 128 for c in (U, V)]
    r = Y + 1.402 * up[1]
    g = Y - 0.344136 * up[0] - 0.714136 * up[1]
    b = Y + 1.772 * up[0]
    W, H = picture_size(name)
    return np.clip(np.round(np.dstack([r, g, b])), 0, 255).astype(np.uint8)[:H, :W]


def ctb_size(name=MAIN):
    return dec(name).ctb


def ctb_grid(name=MAIN):
    """(横の数, 縦の数)"""
    d = dec(name)
    return d.wctb, d.hctb


def splits(name=MAIN):
    """「4 つに割る？」の答えすべて (復号の順)。dict(x, y, size, split, coded)。coded=False は写真の端で決まっているもの"""
    return dec(name).splits


def ctb_splits(rx, ry, name=MAIN):
    n = ctb_size(name)
    return [s for s in splits(name) if rx * n <= s["x"] < (rx + 1) * n and ry * n <= s["y"] < (ry + 1) * n]


def cus(name=MAIN):
    """予想のブロック (CU)。dict(x, y, size, nxn, pus, qp, chroma_mode)。nxn=1 は 8×8 を 4×4 ずつ予想するもの"""
    return dec(name).cus


def area_shares(name=MAIN):
    """写真の中で、各大きさのブロックが占める面積の割合 {32: 0.51, ...} (4 は 8×8 を 4×4 で予想するもの)"""
    W, H = picture_size(name)
    area = {}
    for cu in cus(name):
        x0, y0, s = cu["x"], cu["y"], cu["size"]
        a = max(0, min(x0 + s, W) - x0) * max(0, min(y0 + s, H) - y0)
        k = 4 if cu["nxn"] else s
        area[k] = area.get(k, 0) + a
    tot = sum(area.values())
    assert tot == W * H
    return {k: v / tot for k, v in sorted(area.items(), reverse=True)}


# ---------------- CABAC ----------------

ALPHA = (0.01875 / 0.5) ** (1 / 63)


def p_lps(state):
    """CABAC の状態 (0〜62) → 出にくいほう (LPS) の確率。H.265 の状態の決め方 (0.5 × α^状態)"""
    return 0.5 * ALPHA ** state


def cabac_log(name=MAIN):
    """判定の記録 [(文法の名前, 文脈の名前 / 'bypass' / 'terminate', 文脈の番号, 読む前の状態, 読む前の MPS, 答え, 幅, 読んだあとのビット位置)]"""
    return dec(name).log


def ctx_trace(ctx_name, idx, name=MAIN):
    """1 つの文脈の動き [(読む前の「1」の確率, 答え)]"""
    out = []
    for lab, nm, i, st, mps, b, rng, bp in cabac_log(name):
        if nm == ctx_name and i == idx:
            p1 = 1 - p_lps(st) if mps == 1 else p_lps(st)
            out.append((p1, b))
    return out


@lru_cache(None)
def cabac_costs(name=MAIN):
    """確率を使う判定の数と、そのビット数の計算 (1 回 1 ビット / 最初の確率のまま / 覚えながら)"""
    d = dec(name)
    init = hevc.new_contexts(d.h["qp"])
    n = 0
    fixed = adapt = 0.0
    for lab, nm, i, st, mps, b, rng, bp in d.log:
        if nm in ("bypass", "terminate"):
            continue
        n += 1
        p = p_lps(st)
        adapt += -np.log2(p if b != mps else 1 - p)
        c = init[nm][i]
        p0 = p_lps(c.state)
        fixed += -np.log2(p0 if b != c.mps else 1 - p0)
    return dict(n=n, one_bit=n, fixed=round(fixed), adapt=round(adapt))
