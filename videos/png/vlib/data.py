"""実データ。画面に出す数値はすべてここ（data/ の画像と build/analysis/*.json）から取る。"""
import json, struct, zlib
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def path(name):
    return DATA / f"{name}.png"


@lru_cache(None)
def pixels(name):
    return np.asarray(Image.open(path(name)))


@lru_cache(None)
def info(name):
    return json.loads((ROOT / "build" / "analysis" / f"{name}.json").read_text())


@lru_cache(None)
def file_bytes(name):
    return path(name).read_bytes()


def chunks(name):
    b = file_bytes(name); i = 8; out = []
    while i < len(b):
        n, = struct.unpack(">I", b[i:i + 4])
        out.append(dict(type=b[i + 4:i + 8].decode("latin1"), offset=i, length=n, data=b[i + 8:i + 8 + n],
                        crc=b[i + 8 + n:i + 12 + n]))
        i += 12 + n
    return out


@lru_cache(None)
def filtered(name):
    """フィルタ後のデータ（各行の先頭がフィルタ番号）を 行×(1+stride) の配列で"""
    inf = info(name)
    idat = b"".join(c["data"] for c in chunks(name) if c["type"] == "IDAT")
    raw = np.frombuffer(zlib.decompress(idat), np.uint8)
    return raw.reshape(inf["height"], 1 + inf["width"] * inf["bpp"])


def fmt(n):
    return f"{n:,}"
