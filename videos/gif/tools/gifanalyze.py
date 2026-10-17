"""GIF を自前で読む（画面の数字はすべてここから）。

uv run python tools/gifanalyze.py data/zunda_anim.gif data/cat_dither.gif
  → 要約を表示し build/analysis/<name>.json を書く

- ヘッダ・画面の大きさ・色の表（パレット）
- 拡張（GCE：待ち時間・透明色・消し方、NETSCAPE：くり返し）
- 画像ブロック（位置・大きさ・LZW の最初の符号の長さ・255 バイトずつの小分け）
- LZW を解いて画素の番号に戻す。どの符号を読み、辞書に何を足したかの記録（trace）も取る
- Pillow で開いた結果と全コマ一致することを確かめる
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def u16(b, i):
    return b[i] | (b[i + 1] << 8)


def read_table(b, i, n):
    return [tuple(b[i + 3 * k:i + 3 * k + 3]) for k in range(n)], i + 3 * n


def sub_blocks(b, i):
    """255 バイトまでの小分けをつなぐ。(データ, 次の位置, 小分けの長さのリスト)"""
    out, sizes = bytearray(), []
    while True:
        n = b[i]
        i += 1
        if n == 0:
            return bytes(out), i, sizes
        sizes.append(n)
        out += b[i:i + n]
        i += n


def lzw_decode(data, min_size, npix, trace_limit=0):
    """GIF の LZW。符号は下位ビットから詰めてある。trace は (符号, 符号の長さ, 出した番号の列, 辞書に足した番号) の列"""
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    size = min_size + 1
    dic = {}
    nxt = eoi + 1
    bits = np.unpackbits(np.frombuffer(data, np.uint8), bitorder="little")
    p, prev, out = 0, None, []
    trace, stats = [], dict(codes=0, clears=0, max_size=size, size_changes=[])

    def get(c):
        return dic[c] if c >= eoi + 1 else (c,)

    while p + size <= len(bits):
        code = int(np.dot(bits[p:p + size], 1 << np.arange(size)))
        used = size
        p += size
        stats["codes"] += 1
        if code == clear:
            dic, nxt, size, prev = {}, eoi + 1, min_size + 1, None
            stats["clears"] += 1
            if len(trace) < trace_limit:
                trace.append(dict(code=code, size=min_size + 1, kind="clear"))
            continue
        if code == eoi:
            if len(trace) < trace_limit:
                trace.append(dict(code=code, size=size, kind="end"))
            break
        if prev is None:
            s = get(code)
            added = None
        else:
            if code < nxt and (code < clear or code in dic):
                s = get(code)
            else:  # まだ辞書にない符号（KwKwK）：前の列＋前の列の先頭
                s = get(prev) + (get(prev)[0],)
            added = (nxt, get(prev) + (s[0],))
            if nxt < 4096:
                dic[nxt] = added[1]
                nxt += 1
                if nxt == (1 << size) and size < 12:
                    size += 1
                    stats["size_changes"].append(dict(at_code=stats["codes"], size=size))
                    stats["max_size"] = max(stats["max_size"], size)
        out.extend(s)
        if len(trace) < trace_limit:
            trace.append(dict(code=code, size=used, kind="data",
                              out=list(s), add=None if added is None else [added[0], list(added[1])]))
        prev = code
    return np.array(out[:npix], np.uint8), trace, stats, p


def parse(path, trace_limit=64):
    b = Path(path).read_bytes()
    info = dict(file=Path(path).name, file_bytes=len(b), version=b[:6].decode())
    info["width"], info["height"] = u16(b, 6), u16(b, 8)
    flags = b[10]
    gct = bool(flags & 0x80)
    gct_n = 2 << (flags & 7)
    info.update(gct=gct, gct_size=gct_n if gct else 0, color_res=((flags >> 4) & 7) + 1, bg_index=b[11])
    i = 13
    blocks = [dict(kind="header", offset=0, length=13)]
    palette = None
    if gct:
        palette, i = read_table(b, i, gct_n)
        blocks.append(dict(kind="gct", offset=13, length=3 * gct_n))
    frames, gce = [], None
    while i < len(b):
        t = b[i]
        if t == 0x21:  # 拡張
            label = b[i + 1]
            start = i
            if label == 0xF9:
                n = b[i + 2]
                pf = b[i + 3]
                gce = dict(disposal=(pf >> 2) & 7, transparent=bool(pf & 1), delay=u16(b, i + 4),
                           transparent_index=b[i + 6])
                i += 3 + n + 1
                blocks.append(dict(kind="gce", offset=start, length=i - start, **gce))
            else:
                n = b[i + 2]
                head = b[i + 3:i + 3 + n]
                data, i, _ = sub_blocks(b, i + 3 + n)
                ext = dict(kind="app" if label == 0xFF else f"ext{label:02X}", offset=start, length=i - start,
                           name=head.decode("latin1"))
                if head.startswith(b"NETSCAPE"):
                    ext["loop"] = u16(data, 1)
                blocks.append(ext)
        elif t == 0x2C:  # 画像
            start = i
            left, top, w, h = u16(b, i + 1), u16(b, i + 3), u16(b, i + 5), u16(b, i + 7)
            pf = b[i + 9]
            i += 10
            lct = None
            if pf & 0x80:
                lct, i = read_table(b, i, 2 << (pf & 7))
            interlace = bool(pf & 0x40)
            min_size = b[i]
            data, j, sizes = sub_blocks(b, i + 1)
            idx, trace, stats, used_bits = lzw_decode(data, min_size, w * h, trace_limit)
            fr = dict(offset=start, length=j - start, left=left, top=top, width=w, height=h, interlace=interlace,
                      local_table=lct is not None, lzw_min=min_size, data_offset=i + 1, data_bytes=len(data),
                      sub_blocks=len(sizes), sub_block_sizes=sizes[:3] + (["…"] if len(sizes) > 3 else []),
                      lzw=stats, gce=gce, trace=trace)
            img = idx.reshape(h, w)
            if interlace:  # 行の順番が 8 行おき→4 行おき→2 行おき→残り
                rows = [r for st, step in ((0, 8), (4, 8), (2, 4), (1, 2)) for r in range(st, h, step)]
                fixed = np.zeros_like(img)
                fixed[rows] = img
                img = fixed
            frames.append((fr, img, lct or palette))
            blocks.append(dict(kind="image", offset=start, length=j - start, frame=len(frames) - 1))
            gce = None
            i = j
        elif t == 0x3B:
            blocks.append(dict(kind="trailer", offset=i, length=1))
            break
        else:
            raise ValueError(f"unknown block {t:#x} at {i}")
    info["blocks"] = blocks
    return info, palette, frames


def compose(info, frames):
    """全コマを画面に重ねた RGBA（消し方 1：そのまま残す、2：背景に戻す）"""
    W, H = info["width"], info["height"]
    canvas = np.zeros((H, W, 4), np.uint8)
    out = []
    for fr, idx, pal in frames:
        prev = canvas.copy()
        pal = np.array(pal, np.uint8)
        g = fr["gce"] or {}
        rgb = pal[idx]
        mask = np.ones(idx.shape, bool)
        if g.get("transparent"):
            mask = idx != g["transparent_index"]
        y, x = fr["top"], fr["left"]
        region = canvas[y:y + fr["height"], x:x + fr["width"]]
        region[mask, :3] = rgb[mask]
        region[mask, 3] = 255
        out.append(canvas.copy())
        if g.get("disposal") == 2:
            canvas[y:y + fr["height"], x:x + fr["width"]] = 0
        elif g.get("disposal") == 3:
            canvas = prev
    return out


def analyze(path):
    info, palette, frames = parse(path)
    from PIL import Image
    ref = Image.open(path)
    comp = compose(info, frames)
    diffs = []
    for k in range(len(frames)):
        ref.seek(k)
        r = np.asarray(ref.convert("RGBA")).astype(int)
        c = comp[k].astype(int)
        vis = (r[..., 3] > 0) | (c[..., 3] > 0)
        diffs.append(int(np.abs(r[vis, :3] - c[vis, :3]).max()) if vis.any() else 0)
    info["frames"] = [fr for fr, *_ in frames]
    info["max_diff_vs_pillow"] = max(diffs)
    info["raw_index_bytes"] = sum(fr["width"] * fr["height"] for fr, *_ in frames)
    return info, palette, frames, comp


def main():
    for p in sys.argv[1:]:
        info, palette, frames, _ = analyze(p)
        out = ROOT / "build/analysis" / (Path(p).stem + ".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        slim = dict(info, frames=[{k: v for k, v in f.items() if k != "trace"} for f in info["frames"]])
        out.write_text(json.dumps(slim, ensure_ascii=False, indent=1))
        print(p, info["file_bytes"], "bytes", f'{info["width"]}x{info["height"]}', "frames", len(frames),
              "gct", info["gct_size"], "diff vs pillow", info["max_diff_vs_pillow"])
        for f in info["frames"][:3]:
            print("   frame", f["left"], f["top"], f["width"], f["height"], "lzw", f["lzw_min"], f["lzw"]["codes"],
                  "codes, max size", f["lzw"]["max_size"], "clears", f["lzw"]["clears"], "data", f["data_bytes"],
                  "sub", f["sub_blocks"], "gce", f["gce"])


if __name__ == "__main__":
    main()
