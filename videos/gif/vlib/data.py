"""実データ。画面に出す数値はすべてここ（data/ と tools/gifanalyze.py の結果）から取る。"""
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "tools"))
import gifanalyze as G  # noqa: E402

MAIN = "zunda_anim"


def path(name):
    for ext in ("gif", "png", "jpg"):
        p = DATA / f"{name}.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(name)


@lru_cache(None)
def file_bytes(name):
    return path(name).read_bytes()


@lru_cache(None)
def pixels(name):
    """RGB(A) 画素（1 コマ目）"""
    return np.asarray(Image.open(path(name)).convert("RGBA" if name == MAIN else "RGB"))


@lru_cache(None)
def gif(name=MAIN):
    """(info, palette, frames, composed)。frames は (情報 dict, 色番号の 2 次元配列, 色の表) の列、
    composed は各コマを画面に重ねた RGBA。info["frames"][k]["trace"] は LZW を読んだ記録（最初の 64 個）"""
    return G.analyze(path(name))


def info(name=MAIN):
    return gif(name)[0]


def palette(name=MAIN):
    return np.array(gif(name)[1], np.uint8)


def indices(name=MAIN, k=0):
    """k コマ目の色番号（そのコマの四角の中だけ）"""
    return gif(name)[2][k][1]


def frame_rgba(name=MAIN, k=0):
    """k コマ目まで重ねた画面"""
    return gif(name)[3][k]


def fmt(n):
    return f"{n:,}"


@lru_cache(None)
def full_trace(name=MAIN, k=0):
    """k コマ目の LZW を読んだ記録をすべて。各要素に、その符号が始まる画素の位置 pos を足したもの"""
    _, _, frames = G.parse(path(name), trace_limit=10 ** 7)
    tr = frames[k][0]["trace"]
    pos = 0
    for t in tr:
        t["pos"] = pos
        if t["kind"] == "data":
            pos += len(t["out"])
    return tr


@lru_cache(None)
def png_sizes(name=MAIN):
    """各コマを（重ねた画面のまま）PNG で保存したときの大きさ"""
    import io
    out = []
    for k in range(len(info(name)["frames"])):
        b = io.BytesIO()
        Image.fromarray(frame_rgba(name, k)).save(b, "PNG", optimize=True)
        out.append(b.tell())
    return out
