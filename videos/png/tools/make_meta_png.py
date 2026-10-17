"""data/zundamon.png の IHDR の直後に tEXt と tIME を挿入した data/zundamon_meta.png を作り、
Pillow で画素がまったく同じことを確かめる。   uv run python tools/make_meta_png.py"""
import struct, zlib
from pathlib import Path

import numpy as np
from PIL import Image

DATA = Path(__file__).resolve().parent.parent / "data"
SRC, DST = DATA / "zundamon.png", DATA / "zundamon_meta.png"

KEYWORD, TEXT = b"Comment", b"This is a PNG explainer demo."
TIME = (2026, 10, 16, 12, 0, 0)  # 年 月 日 時 分 秒（固定：毎回同じファイルになる）


def chunk(typ: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def main():
    b = SRC.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n"
    ihdr_len, = struct.unpack(">I", b[8:12])
    assert b[12:16] == b"IHDR"
    end = 8 + 12 + ihdr_len  # IHDR チャンクの終わり
    text = chunk(b"tEXt", KEYWORD + b"\x00" + TEXT)
    time = chunk(b"tIME", struct.pack(">HBBBBB", *TIME))
    DST.write_bytes(b[:end] + text + time + b[end:])
    a, c = np.asarray(Image.open(SRC)), np.asarray(Image.open(DST))
    assert a.shape == c.shape and np.array_equal(a, c), "画素が違う"
    print(f"{DST.name}: {len(b)} -> {DST.stat().st_size} バイト（+{len(text) + len(time)}）, 画素は完全に一致 {a.shape}")


if __name__ == "__main__":
    main()
