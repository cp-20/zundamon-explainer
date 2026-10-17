"""PNG を実際に分解し、動画に出す数値をすべて計算して build/analysis/<name>.json に保存する。

DEFLATE は自前の inflate でデコードし、ブロック・LZ77 トークン・ハフマン符号長を記録する。
"""
import json, struct, sys, zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LEN_BASE = [3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258]
LEN_EXTRA = [0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0]
DIST_BASE = [1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577]
DIST_EXTRA = [0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13]
CL_ORDER = [16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15]


class Bits:
    def __init__(self, data):
        self.d = data; self.pos = 0  # bit position
    def bit(self):
        b = (self.d[self.pos >> 3] >> (self.pos & 7)) & 1; self.pos += 1; return b
    def bits(self, n):
        v = 0
        for i in range(n): v |= self.bit() << i
        return v


def build_decoder(lengths):
    """canonical Huffman: returns dict (len, code) -> symbol"""
    maxl = max(lengths) if lengths else 0
    bl = Counter(l for l in lengths if l)
    code = 0; nxt = {}
    for l in range(1, maxl + 1):
        code = (code + bl.get(l - 1, 0)) << 1
        nxt[l] = code
    table = {}
    for s, l in enumerate(lengths):
        if l:
            table[(l, nxt[l])] = s; nxt[l] += 1
    return table


def decode_sym(br, table):
    code = 0; l = 0
    while True:
        code = (code << 1) | br.bit(); l += 1
        s = table.get((l, code))
        if s is not None: return s
        if l > 15: raise ValueError("bad code")


FIXED_LIT = [8]*144 + [9]*112 + [7]*24 + [8]*8
FIXED_DIST = [5]*30


def inflate(data, keep_tokens=True):
    br = Bits(data); out = bytearray(); blocks = []
    while True:
        start = br.pos
        final = br.bit(); btype = br.bits(2)
        blk = dict(final=final, btype=btype, start_bit=start, out_start=len(out))
        toks = []
        if btype == 0:
            br.pos = (br.pos + 7) & ~7
            ln = br.bits(16); br.bits(16)
            p = br.pos >> 3
            out += data[p:p+ln]; br.pos += ln * 8
            toks.append(("raw", ln))
        else:
            if btype == 1:
                lit_l, dist_l = FIXED_LIT, FIXED_DIST
            else:
                hlit = br.bits(5) + 257; hdist = br.bits(5) + 1; hclen = br.bits(4) + 4
                cl = [0]*19
                for i in range(hclen): cl[CL_ORDER[i]] = br.bits(3)
                clt = build_decoder(cl)
                ls = []
                while len(ls) < hlit + hdist:
                    s = decode_sym(br, clt)
                    if s < 16: ls.append(s)
                    elif s == 16: ls += [ls[-1]] * (3 + br.bits(2))
                    elif s == 17: ls += [0] * (3 + br.bits(3))
                    else: ls += [0] * (11 + br.bits(7))
                lit_l, dist_l = ls[:hlit], ls[hlit:]
                blk["header_bits"] = br.pos - start
            blk["lit_lengths"] = list(lit_l); blk["dist_lengths"] = list(dist_l)
            lt = build_decoder(lit_l); dt = build_decoder(dist_l)
            while True:
                s = decode_sym(br, lt)
                if s < 256:
                    out.append(s); toks.append(s)
                elif s == 256:
                    break
                else:
                    i = s - 257
                    ln = LEN_BASE[i] + br.bits(LEN_EXTRA[i])
                    ds = decode_sym(br, dt)
                    d = DIST_BASE[ds] + br.bits(DIST_EXTRA[ds])
                    for _ in range(ln): out.append(out[-d])
                    toks.append((ln, d))
        blk["end_bit"] = br.pos; blk["out_end"] = len(out)
        if keep_tokens: blk["tokens"] = toks
        blocks.append(blk)
        if final: break
    return bytes(out), blocks, (br.pos + 7) >> 3


def chunks(b):
    i = 8; res = []
    while i < len(b):
        n, = struct.unpack(">I", b[i:i+4]); t = b[i+4:i+8].decode("latin1")
        res.append(dict(type=t, offset=i, length=n, data=b[i+8:i+8+n], crc=b[i+8+n:i+12+n].hex()))
        i += 12 + n
    return res


def analyze(path):
    b = Path(path).read_bytes()
    cs = chunks(b)
    ih = cs[0]["data"]
    w, h, depth, ctype, comp, filt, inter = struct.unpack(">IIBBBBB", ih)
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = ch * depth // 8
    stride = w * bpp
    idat = b"".join(c["data"] for c in cs if c["type"] == "IDAT")
    cmf, flg = idat[0], idat[1]
    raw, blocks, used = inflate(idat[2:])
    assert raw == zlib.decompress(idat)
    adler = idat[2+used:2+used+4].hex()
    filters = [raw[y*(stride+1)] for y in range(h)]
    # 統計
    tokstat = []
    for bl in blocks:
        toks = bl["tokens"]
        lits = sum(1 for t in toks if isinstance(t, int))
        matches = [t for t in toks if isinstance(t, tuple) and t[0] != "raw"]
        tokstat.append(dict(btype=bl["btype"], final=bl["final"], bits=bl["end_bit"]-bl["start_bit"],
                            header_bits=bl.get("header_bits", 0),
                            out_bytes=bl["out_end"]-bl["out_start"], literals=lits, matches=len(matches),
                            match_bytes=sum(m[0] for m in matches)))
    return dict(
        file=Path(path).name, file_size=len(b), width=w, height=h, bit_depth=depth, color_type=ctype,
        compression=comp, filter=filt, interlace=inter, channels=ch, bpp=bpp,
        pixel_bytes=w*h*bpp, raw_bytes=len(raw), idat_bytes=len(idat), zlib_header=f"{cmf:02x} {flg:02x}", adler32=adler,
        signature=b[:8].hex(" "),
        chunks=[dict(type=c["type"], offset=c["offset"], length=c["length"], crc=c["crc"],
                     head=c["data"][:16].hex(" ")) for c in cs],
        filter_hist={str(k): v for k, v in sorted(Counter(filters).items())},
        filters=filters,
        blocks=tokstat,
    ), raw, blocks


if __name__ == "__main__":
    outdir = ROOT / "build" / "analysis"; outdir.mkdir(parents=True, exist_ok=True)
    for p in sys.argv[1:]:
        info, raw, blocks = analyze(p)
        name = Path(p).stem
        (outdir / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
        # 先頭ブロックのトークン（可視化用）を別保存
        (outdir / f"{name}.tokens0.json").write_text(json.dumps(
            dict(lit_lengths=blocks[0].get("lit_lengths"), dist_lengths=blocks[0].get("dist_lengths"),
                 tokens=blocks[0]["tokens"][:4000]), ensure_ascii=False))
        print(name, {k: info[k] for k in ("file_size","pixel_bytes","raw_bytes","idat_bytes","filter_hist")}, len(info["blocks"]), "blocks")
