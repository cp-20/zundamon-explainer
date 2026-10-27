"""HEIF (AVIF) の箱を自前で読む。ISO/IEC 23008-12、ISOBMFF (ISO/IEC 14496-12)、AVIF の、この動画で使う所だけ。
HEIC 編の videos/heic/tools/heif.py に、av1C と AV1 の OBU の切り分けを足したもの。

    uv run python videos/avif/tools/heif.py videos/avif/data/cat_q60.avif   # 箱の木を表示
    uv run python videos/avif/tools/heif.py <file> --obu out.obu           # AV1 の本体 (OBU の並び) を取り出す

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


def parse_av1C(b, body, end):
    """av1C：AV1 の設定 (AV1-ISOBMFF 2.3)。後ろに設定の OBU (sequence header) が付くことがある"""
    c = b[body:end]
    assert c[0] == 0x81   # marker 1 + version 1
    return dict(profile=c[1] >> 5, level=c[1] & 31, tier=c[2] >> 7, high_bitdepth=(c[2] >> 6) & 1,
                twelve_bit=(c[2] >> 5) & 1, monochrome=(c[2] >> 4) & 1, subsampling_x=(c[2] >> 3) & 1,
                subsampling_y=(c[2] >> 2) & 1, chroma_position=c[2] & 3, config_obus=bytes(c[4:]))


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
        if method == 1:   # idat の中の位置
            idat = find(tree, "idat")[0]
            exts = [(idat["body"] + eo, el) for eo, el in exts]
        assert method in (0, 1)
        items[iid]["extents"] = exts
    r["iloc"] = il
    # 性質 (ipco) と結びつけ (ipma)
    ipco = find(tree, "ipco")[0]
    props = []
    for p in ipco["kids"]:
        d = dict(type=p["type"], box=p)
        if p["type"] == "hvcC":
            d.update(parse_hvcC(b, p["body"], p["pos"] + p["size"]))
        elif p["type"] == "av1C":
            d.update(parse_av1C(b, p["body"], p["pos"] + p["size"]))
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


def leb128(b, o):
    v = 0
    for i in range(8):
        v |= (b[o + i] & 0x7F) << (7 * i)
        if not b[o + i] & 0x80:
            return v, o + i + 1
    raise ValueError


OBU_NAMES = {1: "sequence header", 2: "temporal delimiter", 3: "frame header", 4: "tile group",
             5: "metadata", 6: "frame", 7: "redundant frame header", 8: "tile list", 15: "padding"}


def item_data(r, iid=None):
    b = r["bytes"]
    it = r["items"][iid or r["primary"]]
    return b"".join(bytes(b[pos:pos + ln]) for pos, ln in it["extents"])


def item_obus(r, iid=None):
    """その項目の AV1 の OBU。[dict(type, name, pos (ファイルの中の位置), header (頭のバイト数), size, data (中身))]
    (av1C の設定の OBU は pos=None)"""
    b = r["bytes"]
    it = r["items"][iid or r["primary"]]
    out = []
    av = item_prop(it, "av1C")
    srcs = [(None, av["config_obus"])] if av and av["config_obus"] else []
    srcs += [(pos, bytes(b[pos:pos + ln])) for pos, ln in it["extents"]]
    for base, d in srcs:
        o = 0
        while o < len(d):
            h = d[o]
            typ, ext, has_size = (h >> 3) & 15, (h >> 2) & 1, (h >> 1) & 1
            p = o + 1 + ext
            assert has_size
            n, p = leb128(d, p)
            out.append(dict(type=typ, name=OBU_NAMES.get(typ, "?"), pos=None if base is None else base + o,
                            header=p - o, size=n, data=d[p:p + n]))
            o = p + n
    return out


def obu_stream(r, iid=None):
    """OBU の並びをそのまま (頭つき) つないだもの。aomdec --annexb ではなく、ふつうの OBU の並び"""
    b = r["bytes"]
    it = r["items"][iid or r["primary"]]
    av = item_prop(it, "av1C")
    return (av["config_obus"] if av else b"") + item_data(r, iid)


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
    for ob in item_obus(r):
        print(ob["name"], ob["pos"], ob["header"], ob["size"])
    if "--obu" in sys.argv:
        open(sys.argv[sys.argv.index("--obu") + 1], "wb").write(obu_stream(r))
