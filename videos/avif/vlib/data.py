"""実データ。画面に出す数値はすべてここ (data/ と tools/ の自前の読み取り器・復号器の結果) から取る。"""
import hashlib
import io
import pickle
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = ROOT.parents[1] / "cache" / "avif"
sys.path.insert(0, str(ROOT / "tools"))
import av1  # noqa: E402
import heif as HEIF  # noqa: E402

MAIN = "cat_q60"
MODE_NAMES = av1.MODE_NAMES
PARTITION_NAMES = av1.PARTITION_NAMES
TX_TYPE_NAMES = av1.TX_TYPE_NAMES


def path(name):
    """名前 (拡張子は省略可。省略すると avif → png → heic → webp → jpg の順に探す) → data/ のファイル"""
    if (DATA / name).is_file():
        return DATA / name
    for ext in ("avif", "png", "heic", "webp", "jpg"):
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
    """絵として出す RGB(A)。AVIF は自前の復号器の Y・U・V を RGB にしたもの、HEIC は pillow-heif、それ以外は Pillow"""
    p = path(name)
    if p.suffix == ".avif":
        return rgb_decoded(name)
    if p.suffix == ".heic":
        import pillow_heif
        return np.asarray(pillow_heif.open_heif(p).to_pillow().convert("RGB"))
    im = Image.open(p)
    return np.asarray(im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"))


def mean_abs_err(name, src="cat.png"):
    """元の写真との、1 つの点あたりの平均のずれ (RGB の 3 色の差の絶対値の平均)。
    AVIF・HEIC は Pillow・pillow-heif で RGB にしたもの (見る人のソフトが出す色)"""
    a = np.asarray(Image.open(path(src)).convert("RGB")).astype(float)
    p = path(name)
    if p.suffix == ".heic":
        import pillow_heif
        b = np.asarray(pillow_heif.open_heif(p).to_pillow().convert("RGB")).astype(float)
    else:
        b = np.asarray(Image.open(p).convert("RGB")).astype(float)
    return float(np.abs(a - b).mean())


# ---------------- 箱 (HEIF) と OBU ----------------

@lru_cache(None)
def boxes(name=MAIN):
    """自前の箱の読み取りの結果 (tools/heif.py)"""
    return HEIF.parse(path(name))


def obus(name=MAIN):
    """本体の OBU の並び [dict(type, name, pos, header, size, data)]"""
    r = boxes(name)
    return [o for o in HEIF.item_obus(r) if o["pos"] is not None]


# ---------------- 本体 (AV1) ----------------

@lru_cache(None)
def dec(name=MAIN):
    """自前の AV1 復号器の結果 (tools/av1.py の Decoder)。aomdec と全画素一致を確認済み。
    復号に数秒かかるので、ファイルと復号器の中身で決まる名前で cache/avif/ に残す"""
    h = hashlib.sha1(file_bytes(name) + (ROOT / "tools" / "av1.py").read_bytes()
                     + (ROOT / "tools" / "av1tables.py").read_bytes()).hexdigest()[:16]
    cp = CACHE / f"{path(name).stem}_{h}.pkl"
    if cp.exists():
        try:
            return pickle.loads(cp.read_bytes())
        except Exception:
            pass
    d = av1.decode_file(path(name))
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp%d" % id(d))
    tmp.write_bytes(pickle.dumps(d, protocol=pickle.HIGHEST_PROTOCOL))
    tmp.replace(cp)
    return d


def picture_size(name=MAIN):
    """(幅, 高さ)"""
    f = dec(name).frame
    return f["UpscaledWidth"], f["FrameHeight"]


def yuv_to_rgb(Y, U, V):
    """colr の決まり (BT.601、全範囲) で RGB に。色は縦横 2 倍に線形補間"""
    Y, U, V = (np.asarray(c, np.float32) for c in (Y, U, V))
    h, w = Y.shape
    up = [np.asarray(Image.fromarray(c).resize((w, h), Image.BILINEAR), np.float32) - 128 for c in (U, V)]
    r = Y + 1.402 * up[1]
    g = Y - 0.344136 * up[0] - 0.714136 * up[1]
    b = Y + 1.772 * up[0]
    return np.clip(np.round(np.dstack([r, g, b])), 0, 255).astype(np.uint8)


@lru_cache(None)
def planes(name=MAIN, stage="final"):
    """写真の大きさに切った Y・U・V (uint8)。stage は final / lr / cdef / deblocked / recon / pred"""
    d = dec(name)
    return tuple(np.asarray(p) for p in d.crop(getattr(d, stage)))


@lru_cache(None)
def rgb_decoded(name=MAIN, stage="final"):
    return yuv_to_rgb(*planes(name, stage))


@lru_cache(None)
def source_yuv(name="cat.png"):
    """元の写真を、AVIF と同じ決まり (BT.601、全範囲) で Y・Cb・Cr に (色は 2×2 の平均で半分に)。比べる用"""
    a = np.asarray(Image.open(path(name)).convert("RGB")).astype(np.float64)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    Y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = (b - Y) / 1.772 + 128
    cr = (r - Y) / 1.402 + 128
    h, w = Y.shape

    def half(c):
        c = np.pad(c, ((0, h % 2), (0, w % 2)), mode="edge")
        return (c[0::2, 0::2] + c[1::2, 0::2] + c[0::2, 1::2] + c[1::2, 1::2]) / 4
    return Y, half(cb), half(cr)


def blocks(name=MAIN):
    return dec(name).blocks


def partitions(name=MAIN):
    return dec(name).partitions


def txbs(name=MAIN, plane=None):
    t = dec(name).txbs
    return t if plane is None else [b for b in t if b["plane"] == plane]


# ---------------- 色の予測 (CfL) ----------------

CFL_BLOCK = (96, 56)     # Cb・Cr の座標。左目の右のふち (明るさでは (192, 112) から 16×16)


def _txb(plane, x, y, name=MAIN):
    return next(t for t in dec(name).txbs if t["plane"] == plane and t["x"] == x and t["y"] == y)


@lru_cache(None)
def cfl_example(name=MAIN, block=CFL_BLOCK):
    """CfL の見本のブロック。値はすべて復号器の途中の値 (intra_pred の keep) から。
    luma16：先にできた明るさ (ループフィルタの前)、luma8：4 つずつの平均 (小数)、avg：その平均、bump：luma8 − avg、
    alpha：掛ける数 (8 分の 1 の単位)、scaled：bump × alpha を丸めて足した数、dc：平らな予測、pred：予測、
    src：元の写真の色、err_dc / err_cfl：元との平均のずれ (平らな予測 / CfL の予測)"""
    d = dec(name)
    cx, cy = block
    out = {}
    for plane, key in ((1, "u"), (2, "v")):
        t = _txb(plane, cx, cy, name)
        assert "cfl_alpha" in t["pred"]
        k = {}
        pred = d.intra_pred(t, k)
        w, h = t["w"], t["h"]
        L = np.asarray(k["cfl_L"], np.int64)
        avg8 = int(k["luma_avg"])
        dc = int(np.asarray(k["dc"]).flat[0]) if np.ndim(k["dc"]) else int(k["dc"])
        alpha = int(k["alpha"])
        scaled = np.asarray(pred, np.int64) - dc
        src = source_yuv()[plane][cy:cy + h, cx:cx + w]
        out[key] = dict(alpha=alpha, dc=dc, pred=np.asarray(pred, np.int64), scaled=scaled, src=src,
                        err_dc=float(np.abs(src - dc).mean()), err_cfl=float(np.abs(src - pred).mean()))
        out["luma8"] = L / 8
        out["avg"] = avg8 / 8
        out["bump"] = (L - avg8) / 8
    lx, ly = cx * 2, cy * 2
    out["luma16"] = np.asarray(d.recon[0][ly:ly + 16, lx:lx + 16], np.int64)
    out["luma_xy"] = (lx, ly)
    return out


def cfl_stats(name=MAIN):
    """(色を持つブロックの数, そのうち CfL の数)"""
    bl = [b for b in dec(name).blocks if b["has_chroma"]]
    return len(bl), sum(1 for b in bl if b["uv_mode"] == 13)
