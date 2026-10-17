"""ベースライン JPEG を自前で読む（画面の数字はすべてここから）。

uv run python tools/jpeganalyze.py data/cat_q80.jpg   → 要約を表示し build/analysis/<name>.json を書く

- マーカーの並び（位置・名前・長さ）
- 量子化表（DQT）・ハフマン表（DHT）・画像の大きさと色の間引き（SOF0）
- エントロピー符号を解いて、全ブロックの量子化後の係数（ジグザグ順）を取り出す
- それを逆量子化・逆DCTして画素に戻す（Pillow の復号と比べて検算）
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

MARKERS = {0xD8: "SOI", 0xD9: "EOI", 0xDB: "DQT", 0xC4: "DHT", 0xC0: "SOF0", 0xDA: "SOS", 0xDD: "DRI",
           0xFE: "COM", **{0xE0 + i: f"APP{i}" for i in range(16)}}

# ジグザグ順 k → (行, 列)
ZIGZAG = sorted(((r, c) for r in range(8) for c in range(8)),
                key=lambda rc: (rc[0] + rc[1], rc[0] if (rc[0] + rc[1]) % 2 else rc[1]))


def dct_basis():
    """B[u, v, y, x]：周波数 (u=縦, v=横) の模様"""
    n = np.arange(8)
    c = np.array([np.sqrt(1 / 8)] + [np.sqrt(2 / 8)] * 7)
    C = c[:, None] * np.cos((2 * n[None, :] + 1) * n[:, None] * np.pi / 16)  # C[u, y]
    return np.einsum("uy,vx->uvyx", C, C)


BASIS = dct_basis()


def dct2(block):
    """8×8（-128 済み）→ 係数 F[u, v]（JPEG と同じ正規化）"""
    return np.einsum("uvyx,yx->uv", BASIS, block)


def idct2(F):
    return np.einsum("uvyx,uv->yx", BASIS, F)


def parse(data):
    segs, i = [], 2
    assert data[:2] == b"\xff\xd8"
    segs.append(dict(name="SOI", offset=0, length=2))
    out = dict(qt={}, ht={}, segments=segs)
    while i < len(data):
        assert data[i] == 0xFF, i
        m = data[i + 1]
        if m == 0xD9:
            segs.append(dict(name="EOI", offset=i, length=2))
            break
        L = int.from_bytes(data[i + 2:i + 4], "big")
        body = data[i + 4:i + 2 + L]
        name = MARKERS.get(m, f"FF{m:02X}")
        seg = dict(name=name, offset=i, length=L + 2)
        segs.append(seg)
        if name == "DQT":
            p = 0
            while p < len(body):
                pq, tq = body[p] >> 4, body[p] & 15
                assert pq == 0
                out["qt"][tq] = list(body[p + 1:p + 65])  # ジグザグ順
                p += 65
            seg["tables"] = sorted(out["qt"])
        elif name == "DHT":
            p = 0
            seg["tables"] = []
            while p < len(body):
                tc, th = body[p] >> 4, body[p] & 15
                counts = list(body[p + 1:p + 17])
                n = sum(counts)
                syms = list(body[p + 17:p + 17 + n])
                out["ht"][(tc, th)] = (counts, syms)
                seg["tables"].append(("DC" if tc == 0 else "AC") + str(th))
                p += 17 + n
        elif name == "SOF0":
            out["precision"] = body[0]
            out["height"] = int.from_bytes(body[1:3], "big")
            out["width"] = int.from_bytes(body[3:5], "big")
            nc = body[5]
            out["comps"] = [dict(id=body[6 + 3 * k], h=body[7 + 3 * k] >> 4, v=body[7 + 3 * k] & 15,
                                 tq=body[8 + 3 * k]) for k in range(nc)]
        elif name == "SOS":
            ns = body[0]
            sel = {body[1 + 2 * k]: (body[2 + 2 * k] >> 4, body[2 + 2 * k] & 15) for k in range(ns)}
            for c in out["comps"]:
                c["td"], c["ta"] = sel[c["id"]]
            # エントロピー符号の範囲（次のマーカーまで。FF00 は FF）
            j = i + 2 + L
            k = j
            while not (data[k] == 0xFF and data[k + 1] not in (0x00,) and not 0xD0 <= data[k + 1] <= 0xD7):
                k += 1
            seg["scan_offset"], seg["scan_length"] = j, k - j
            out["scan"] = (j, k)
            i = k
            continue
        elif name == "DRI":
            assert int.from_bytes(body[:2], "big") == 0, "restart 非対応"
        i += 2 + L
    return out


def huff_lookup(counts, syms):
    """(長さ, 符号) → 記号"""
    code, k, table = 0, 0, {}
    for L in range(1, 17):
        for _ in range(counts[L - 1]):
            table[(L, code)] = syms[k]
            k += 1
            code += 1
        code <<= 1
    return table


def codes_of(counts, syms):
    """記号 → 符号の文字列"""
    return {s: format(c, f"0{L}b") for (L, c), s in huff_lookup(counts, syms).items()}


class Bits:
    def __init__(self, data, a, b):
        raw = data[a:b].replace(b"\xff\x00", b"\xff")
        self.bits = np.unpackbits(np.frombuffer(raw, np.uint8))
        self.p = 0

    def read(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | int(self.bits[self.p])
            self.p += 1
        return v


def extend(v, t):
    return v if t == 0 or v >= (1 << (t - 1)) else v - (1 << t) + 1


def decode(data, info):
    tabs = {k: huff_lookup(*v) for k, v in info["ht"].items()}
    bs = Bits(data, *info["scan"])
    comps = info["comps"]
    hmax, vmax = max(c["h"] for c in comps), max(c["v"] for c in comps)
    mcux = -(-info["width"] // (8 * hmax))
    mcuy = -(-info["height"] // (8 * vmax))
    coef = [np.zeros((mcuy * c["v"], mcux * c["h"], 64), int) for c in comps]
    pred = [0] * len(comps)
    stats = dict(dc_bits=0, ac_bits=0, eob=0, zrl=0, ac_symbols=0, dc_symbols=0)

    def sym(tab):
        L, code = 0, 0
        while True:
            code = (code << 1) | bs.read(1)
            L += 1
            if (L, code) in tab:
                return tab[(L, code)], L

    for my in range(mcuy):
        for mx in range(mcux):
            for ci, c in enumerate(comps):
                for by in range(c["v"]):
                    for bx in range(c["h"]):
                        zz = np.zeros(64, int)
                        t, L = sym(tabs[(0, c["td"])])
                        diff = extend(bs.read(t), t)
                        stats["dc_bits"] += L + t
                        stats["dc_symbols"] += 1
                        pred[ci] += diff
                        zz[0] = pred[ci]
                        k = 1
                        while k < 64:
                            rs, L = sym(tabs[(1, c["ta"])])
                            r, s = rs >> 4, rs & 15
                            stats["ac_bits"] += L + s
                            stats["ac_symbols"] += 1
                            if s == 0:
                                if r == 15:
                                    stats["zrl"] += 1
                                    k += 16
                                    continue
                                stats["eob"] += 1
                                break
                            k += r
                            zz[k] = extend(bs.read(s), s)
                            k += 1
                        coef[ci][my * c["v"] + by, mx * c["h"] + bx] = zz
    return coef, stats


def to_block(zz):
    """ジグザグ順 64 → 8×8"""
    b = np.zeros((8, 8), zz.dtype)
    for k, (r, c) in enumerate(ZIGZAG):
        b[r, c] = zz[k]
    return b


def reconstruct(info, coef):
    """逆量子化 → 逆DCT → +128 → 色の間引きを戻す → RGB（JFIF の式）"""
    comps = info["comps"]
    hmax, vmax = max(c["h"] for c in comps), max(c["v"] for c in comps)
    planes = []
    for c, cf in zip(comps, coef):
        q = to_block(np.array(info["qt"][c["tq"]]))
        by, bx = cf.shape[:2]
        pl = np.zeros((by * 8, bx * 8))
        for y in range(by):
            for x in range(bx):
                pl[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = idct2(to_block(cf[y, x]) * q) + 128
        pl = pl.repeat(vmax // c["v"], 0).repeat(hmax // c["h"], 1)
        planes.append(pl[:info["height"], :info["width"]])
    Y, Cb, Cr = planes
    rgb = np.stack([Y + 1.402 * (Cr - 128),
                    Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128),
                    Y + 1.772 * (Cb - 128)], -1)
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)


def rgb_to_ycc(rgb):
    rgb = rgb.astype(float)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cb = -0.168736 * R - 0.331264 * G + 0.5 * B + 128
    Cr = 0.5 * R - 0.418688 * G - 0.081312 * B + 128
    return np.stack([Y, Cb, Cr], -1)


def analyze(path):
    path = Path(path)
    data = path.read_bytes()
    info = parse(data)
    coef, stats = decode(data, info)
    rgb = reconstruct(info, coef)
    from PIL import Image
    ref = np.asarray(Image.open(path).convert("RGB")).astype(int)
    diff = np.abs(ref - rgb.astype(int))
    zeros = [int((cf[..., 1:] == 0).sum()) for cf in coef]
    total_ac = [int(cf[..., 1:].size) for cf in coef]
    seg_sizes = {}
    for s in info["segments"]:
        seg_sizes[s["name"]] = seg_sizes.get(s["name"], 0) + s["length"]
    a, b = info["scan"]
    summary = dict(
        file=path.name, file_bytes=len(data), width=info["width"], height=info["height"],
        raw_bytes=info["width"] * info["height"] * 3,
        comps=[dict(id=c["id"], h=c["h"], v=c["v"], tq=c["tq"], blocks=int(cf.shape[0] * cf.shape[1]))
               for c, cf in zip(info["comps"], coef)],
        qt={str(k): v for k, v in info["qt"].items()},
        segments=[{k: v for k, v in s.items()} for s in info["segments"]],
        seg_sizes=seg_sizes, scan_bytes=b - a,
        ac_zero=zeros, ac_total=total_ac,
        stats=stats,
        max_diff_vs_pillow=int(diff.max()), mean_diff_vs_pillow=float(diff.mean()),
    )
    return summary, info, coef, rgb


def main():
    for p in sys.argv[1:]:
        s, *_ = analyze(p)
        out = ROOT / "build/analysis" / (Path(p).stem + ".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(s, ensure_ascii=False, indent=1))
        print(p, s["file_bytes"], "bytes", f'{s["width"]}x{s["height"]}', "raw", s["raw_bytes"],
              "zeros", [f"{z / t:.1%}" for z, t in zip(s["ac_zero"], s["ac_total"])],
              "diff max", s["max_diff_vs_pillow"], "mean", round(s["mean_diff_vs_pillow"], 3))
        print("  ", " ".join(f'{x["name"]}({x["length"]})' for x in s["segments"]))


if __name__ == "__main__":
    main()
