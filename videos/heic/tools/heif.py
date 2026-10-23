"""HEIF (HEIC) の箱を自前で読む。ISO/IEC 23008-12 と ISOBMFF (ISO/IEC 14496-12) の、この動画で使う所だけ。

    uv run python videos/heic/tools/heif.py videos/heic/data/cat_q45.heic   # 箱の木を表示
    uv run python videos/heic/tools/heif.py <file> --annexb out.hevc       # HEVC の本体を取り出す (ffmpeg で読める形)

箱 (box) は「大きさ 4 バイト + 種類 4 文字 + 中身」。中身にまた箱が入る。
"""
import struct
import sys

# 中身が箱の並びになっている箱 (meta は先頭に version/flags の 4 バイト)
CONTAINERS = {"meta": 4, "iprp": 0, "ipco": 0, "dinf": 0, "iref": 4, "moov": 0, "trak": 0, "mdia": 0}


def u(b, o, n):
    return int.from_bytes(b[o:o + n], "big")


def boxes(b, start, end, depth=0, path=""):
    """[(種類, 先頭の位置, 大きさ, 中身の先頭, 深さ, 子の list)]"""
    out = []
    o = start
    while o + 8 <= end:
        size = u(b, o, 4)
        typ = b[o + 4:o + 8].decode("latin1")
        hdr = 8
        if size == 1:
            size = u(b, o + 8, 8)
            hdr = 16
        elif size == 0:
            size = end - o
        body = o + hdr
        kids = []
        if typ in CONTAINERS:
            skip = CONTAINERS[typ]
            if typ == "iref":   # iref の子は version 0 なら 2 バイトの番号
                pass
            else:
                kids = boxes(b, body + skip, o + size, depth + 1, path + "/" + typ)
        elif typ == "iinf":
            ver = b[body]
            cnt = u(b, body + 4, 2 if ver == 0 else 4)
            kids = boxes(b, body + 4 + (2 if ver == 0 else 4), o + size, depth + 1, path + "/" + typ)
            assert len(kids) == cnt
        out.append(dict(type=typ, pos=o, size=size, body=body, hdr=hdr, depth=depth, kids=kids))
        o += size
    assert o == end, (o, end)
    return out


def walk(tree):
    for bx in tree:
        yield bx
        yield from walk(bx["kids"])


def find(tree, typ):
    return [bx for bx in walk(tree) if bx["type"] == typ]


def parse_hvcC(b, body, end):
    """hvcC：HEVC の設定 (VPS・SPS・PPS の NAL を中に持つ)"""
    d = dict(version=b[body], profile_idc=b[body + 1] & 31, level_idc=b[body + 12],
             chroma_format=b[body + 16] & 3, bit_depth_luma=(b[body + 17] & 7) + 8,
             bit_depth_chroma=(b[body + 18] & 7) + 8, length_size=(b[body + 21] & 3) + 1)
    n = b[body + 22]
    o = body + 23
    nals = []
    for _ in range(n):
        typ = b[o] & 63
        cnt = u(b, o + 1, 2)
        o += 3
        for _ in range(cnt):
            ln = u(b, o, 2)
            nals.append(dict(type=typ, pos=o + 2, data=bytes(b[o + 2:o + 2 + ln])))
            o += 2 + ln
    assert o == end
    d["nals"] = nals
    return d


def parse(path_or_bytes):
    b = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else open(path_or_bytes, "rb").read()
    tree = boxes(b, 0, len(b))
    r = dict(bytes=b, tree=tree, size=len(b))
    ftyp = find(tree, "ftyp")[0]
    r["brand"] = b[ftyp["body"]:ftyp["body"] + 4].decode()
    r["compat"] = [b[o:o + 4].decode() for o in range(ftyp["body"] + 8, ftyp["pos"] + ftyp["size"], 4)]
    # 項目 (item) の一覧
    items = {}
    for inf in find(tree, "infe"):
        o = inf["body"]
        ver = b[o]
        assert ver >= 2
        iid = u(b, o + 4, 2 if ver == 2 else 4)
        o2 = o + 4 + (2 if ver == 2 else 4) + 2
        typ = b[o2:o2 + 4].decode("latin1")
        name_end = b.index(b"\0", o2 + 4)
        items[iid] = dict(id=iid, type=typ, name=b[o2 + 4:name_end].decode(), box=inf)
    pitm = find(tree, "pitm")[0]
    r["primary"] = u(b, pitm["body"] + 4, 2)
    # 置き場所 (iloc)
    il = find(tree, "iloc")[0]
    o = il["body"]
    ver = b[o]
    o += 4
    off_size, len_size = b[o] >> 4, b[o] & 15
    base_size, idx_size = b[o + 1] >> 4, (b[o + 1] & 15 if ver in (1, 2) else 0)
    o += 2
    cnt = u(b, o, 2 if ver < 2 else 4)
    o += 2 if ver < 2 else 4
    for _ in range(cnt):
        iid = u(b, o, 2 if ver < 2 else 4)
        o += 2 if ver < 2 else 4
        method = 0
        if ver in (1, 2):
            method = u(b, o, 2) & 15
            o += 2
        o += 2   # data_reference_index
        base = u(b, o, base_size)
        o += base_size
        ext_cnt = u(b, o, 2)
        o += 2
        exts = []
        for _ in range(ext_cnt):
            o += idx_size
            eo = u(b, o, off_size)
            o += off_size
            el = u(b, o, len_size)
            o += len_size
            exts.append((base + eo, el))
        assert method == 0, "idat は使っていない"
        items[iid]["extents"] = exts
    r["iloc"] = il
    # 性質 (ipco) と結びつけ (ipma)
    ipco = find(tree, "ipco")[0]
    props = []
    for p in ipco["kids"]:
        d = dict(type=p["type"], box=p)
        if p["type"] == "hvcC":
            d.update(parse_hvcC(b, p["body"], p["pos"] + p["size"]))
        elif p["type"] == "ispe":
            d["width"], d["height"] = u(b, p["body"] + 4, 4), u(b, p["body"] + 8, 4)
        elif p["type"] == "clap":
            v = [struct.unpack(">I", b[p["body"] + 4 * k:p["body"] + 4 * k + 4])[0] for k in range(8)]
            d["width"], d["height"] = v[0] // v[1], v[2] // v[3]
        elif p["type"] == "colr":
            d["kind"] = b[p["body"]:p["body"] + 4].decode()
            if d["kind"] == "nclx":
                d["primaries"], d["transfer"], d["matrix"] = (u(b, p["body"] + 4, 2), u(b, p["body"] + 6, 2),
                                                              u(b, p["body"] + 8, 2))
                d["full_range"] = b[p["body"] + 10] >> 7
        elif p["type"] == "pixi":
            n = b[p["body"] + 4]
            d["bits"] = list(b[p["body"] + 5:p["body"] + 5 + n])
        props.append(d)
    ipma = find(tree, "ipma")[0]
    o = ipma["body"]
    ver, flags = b[o], u(b, o + 1, 3)
    o += 4
    cnt = u(b, o, 4)
    o += 4
    for _ in range(cnt):
        iid = u(b, o, 2 if ver < 1 else 4)
        o += 2 if ver < 1 else 4
        n = b[o]
        o += 1
        assoc = []
        for _ in range(n):
            if flags & 1:
                v = u(b, o, 2)
                o += 2
                assoc.append((v & 0x7FFF, v >> 15))
            else:
                v = b[o]
                o += 1
                assoc.append((v & 0x7F, v >> 7))
        items[iid]["props"] = [dict(props[k - 1], essential=e) for k, e in assoc]
    r["items"] = items
    r["props"] = props
    r["mdat"] = find(tree, "mdat")[0]
    return r


def item_prop(item, typ):
    for p in item["props"]:
        if p["type"] == typ:
            return p
    return None


def item_nals(r, iid=None):
    """その項目の HEVC の NAL (hvcC の VPS・SPS・PPS と、本体の NAL)。[(種類, ファイルの中の位置, bytes)]"""
    b = r["bytes"]
    it = r["items"][iid or r["primary"]]
    hv = item_prop(it, "hvcC")
    out = [(n["type"], n["pos"], n["data"]) for n in hv["nals"]]
    for pos, ln in it["extents"]:
        o = pos
        while o < pos + ln:
            n = u(b, o, hv["length_size"])
            o += hv["length_size"]
            out.append(((b[o] >> 1) & 63, o, bytes(b[o:o + n])))
            o += n
    return out


def annexb(r, iid=None):
    return b"".join(b"\0\0\0\1" + d for _, _, d in item_nals(r, iid))


def show(r):
    def rec(tree):
        for bx in tree:
            print(f"{'  ' * bx['depth']}{bx['type']}  @{bx['pos']}  {bx['size']} バイト")
            rec(bx["kids"])
    rec(r["tree"])
    for it in r["items"].values():
        print(it["id"], it["type"], it.get("extents"), [p["type"] for p in it["props"]])


if __name__ == "__main__":
    r = parse(sys.argv[1])
    show(r)
    if "--annexb" in sys.argv:
        open(sys.argv[sys.argv.index("--annexb") + 1], "wb").write(annexb(r))
