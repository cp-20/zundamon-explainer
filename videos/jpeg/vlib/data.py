"""実データ。画面に出す数値はすべてここ（data/ の画像と tools/jpeganalyze.py の結果）から取る。"""
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
import jpeganalyze as J  # noqa: E402

ZIGZAG = J.ZIGZAG          # ジグザグ順 k → (行, 列)
BASIS = J.BASIS            # BASIS[u, v] = 8×8 の模様（u 縦の周波数, v 横の周波数）
dct2, idct2, to_block, rgb_to_ycc, codes_of = J.dct2, J.idct2, J.to_block, J.rgb_to_ycc, J.codes_of

MAIN = "cat_q80"           # 本編の JPEG
BLOCK = (13, 20)           # 主役のブロック（輝度の 行, 列）= 猫の左目の瞳のふち


def path(name):
    p = DATA / f"{name}.png"
    return p if p.exists() else DATA / f"{name}.jpg"


@lru_cache(None)
def pixels(name):
    """RGB(A) 画素。JPEG は libjpeg（Pillow）で開いたもの"""
    return np.asarray(Image.open(path(name)))


@lru_cache(None)
def file_bytes(name):
    return path(name).read_bytes()


@lru_cache(None)
def jpeg(name=MAIN):
    """(要約 dict, 構造 info, 係数 coef[comp][by, bx, 64(ジグザグ)], 自前復号の RGB)"""
    return J.analyze(DATA / f"{name}.jpg")


def summary(name=MAIN):
    return jpeg(name)[0]


def qtable(name=MAIN, comp=0):
    """量子化表（8×8, 行=縦の周波数）"""
    s, info, *_ = jpeg(name)
    return to_block(np.array(info["qt"][info["comps"][comp]["tq"]]))


@lru_cache(None)
def ycc(name="cat"):
    """元画像の Y, Cb, Cr（float, JFIF の式）"""
    return rgb_to_ycc(pixels(name)[..., :3])


def block_pixels(by=BLOCK[0], bx=BLOCK[1], name="cat"):
    """元画像の輝度ブロック 8×8（float）"""
    return ycc(name)[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8, 0]


def block_dct(by=BLOCK[0], bx=BLOCK[1], name="cat"):
    """元のブロック −128 の DCT 係数 F[u, v]（float）"""
    return dct2(block_pixels(by, bx, name) - 128)


def block_coef(by=BLOCK[0], bx=BLOCK[1], name=MAIN):
    """ファイルの中の量子化後の係数 8×8（int）"""
    return to_block(jpeg(name)[2][0][by, bx])


def fmt(n):
    return f"{n:,}"


# 主役のブロックは、元画素の DCT を量子化すると、ファイルの係数と完全に一致する
assert (np.round(block_dct() / qtable()).astype(int) == block_coef()).all()
