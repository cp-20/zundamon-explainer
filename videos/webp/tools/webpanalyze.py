"""自前の WebP 読み取り。RIFF の箱 (チャンク) を分け、中身を自前の復号器で読む。

- VP8 (非可逆)：tools/vp8.py
- VP8L (可逆)：tools/vp8l.py
- ALPH (非可逆の透明度)・ANIM / ANMF (動き)

    uv run python videos/webp/tools/webpanalyze.py videos/webp/data/cat_q80.webp
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp8  # noqa: E402


def le(b, n):
    return int.from_bytes(b[:n], "little")


def chunks(data, start=12, end=None):
    """RIFF の箱の並び：[(名前, 中身の始まり, 長さ)]。長さが奇数なら 1 バイト詰め物が入る"""
    end = len(data) if end is None else end
    out, p = [], start
    while p + 8 <= end:
        tag = data[p:p + 4].decode("latin1")
        n = le(data[p + 4:], 4)
        out.append((tag, p + 8, n))
        p += 8 + n + (n & 1)
    return out


def parse(path_or_bytes):
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", "WebP ではない"
    info = dict(file_bytes=len(data), riff_size=le(data[4:], 4), chunks=chunks(data))
    return data, info


def yuv_to_rgb(Y, U, V, w, h):
    """libwebp の「なめらかな色の拡大」(fancy upsampling) を使わず、色の画素をそのまま 2×2 に広げる簡易の変換。
    画面に出す絵を作るだけに使う (一致の確認は Y・U・V で行う)"""
    import numpy as np
    y = np.array(Y, np.int32)[:h, :w]
    u = np.array(U, np.int32).repeat(2, 0).repeat(2, 1)[:h, :w] - 128
    v = np.array(V, np.int32).repeat(2, 0).repeat(2, 1)[:h, :w] - 128
    # BT.601 (libwebp の VP8YUVToR などと同じ係数を小数で)
    r = 1.164 * (y - 16) + 1.596 * v
    g = 1.164 * (y - 16) - 0.813 * v - 0.391 * u
    b = 1.164 * (y - 16) + 2.018 * u
    return np.clip(np.stack([r, g, b], -1) + 0.5, 0, 255).astype(np.uint8)


def analyze(path, filt=True):
    data, info = parse(path)
    for tag, off, n in info["chunks"]:
        if tag == "VP8 ":
            info["vp8"] = vp8.decode(data[off:off + n], filt=filt)
            info["vp8_offset"] = off
        elif tag == "VP8L":
            import vp8l
            info["vp8l"] = vp8l.decode(data[off:off + n])
            info["vp8l_offset"] = off
        elif tag == "VP8X":
            f = data[off]
            info["vp8x"] = dict(icc=bool(f & 0x20), alpha=bool(f & 0x10), exif=bool(f & 0x08), xmp=bool(f & 0x04),
                                anim=bool(f & 0x02), width=le(data[off + 4:], 3) + 1, height=le(data[off + 7:], 3) + 1)
        elif tag == "ALPH":
            import vp8l
            w, h = info["vp8x"]["width"], info["vp8x"]["height"]
            info["alph"] = vp8l.decode_alpha(data[off:off + n], w, h)
        elif tag == "ANIM":
            info["anim"] = dict(bg=tuple(data[off:off + 4]), loops=le(data[off + 4:], 2))
        elif tag == "ANMF":
            import vp8l
            fr = dict(x=2 * le(data[off:], 3), y=2 * le(data[off + 3:], 3), width=le(data[off + 6:], 3) + 1,
                      height=le(data[off + 9:], 3) + 1, duration=le(data[off + 12:], 3),
                      blend=not (data[off + 15] & 2), dispose=bool(data[off + 15] & 1), offset=off,
                      chunks=chunks(data, off + 16, off + n))
            for t2, o2, n2 in fr["chunks"]:
                if t2 == "VP8L":
                    fr["vp8l"] = vp8l.decode(data[o2:o2 + n2])
                elif t2 == "VP8 ":
                    fr["vp8"] = vp8.decode(data[o2:o2 + n2])
                elif t2 == "ALPH":
                    fr["alph"] = vp8l.decode_alpha(data[o2:o2 + n2], fr["width"], fr["height"])
            info.setdefault("frames", []).append(fr)
    return info


if __name__ == "__main__":
    inf = analyze(sys.argv[1])
    print(inf["file_bytes"], [(t, n) for t, _, n in inf["chunks"]])
    if "vp8" in inf:
        v = inf["vp8"]
        print(v["width"], v["height"], v["q"], v["filter"], v["partitions"], v["probs_updated"])
