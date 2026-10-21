"""自前の VP8L (WebP の可逆) 復号器。RFC 9649 の手順どおり。

Pillow (libwebp) と RGBA の全画素が一致することを tools/check_decoder.py で確かめる。
本体の画像の読み取りの記録 (1 つずつの「そのままの色」「何画素前をコピー」「最近の色の何番」) を tokens に残す。
"""
import numpy as np

PREDICTOR, CROSS_COLOR, SUBTRACT_GREEN, COLOR_INDEXING = range(4)
TRANSFORM_NAME = ["予測", "色の相関", "緑を引く", "色の表"]
CODE_LENGTH_ORDER = [17, 18, 0, 1, 2, 3, 4, 5, 16, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
# 距離の番号 1〜120 → (左へ xi, 上へ yi)。RFC 9649 の Figure 20
DISTANCE_MAP = [
    (0, 1), (1, 0), (1, 1), (-1, 1), (0, 2), (2, 0), (1, 2),
    (-1, 2), (2, 1), (-2, 1), (2, 2), (-2, 2), (0, 3), (3, 0),
    (1, 3), (-1, 3), (3, 1), (-3, 1), (2, 3), (-2, 3), (3, 2),
    (-3, 2), (0, 4), (4, 0), (1, 4), (-1, 4), (4, 1), (-4, 1),
    (3, 3), (-3, 3), (2, 4), (-2, 4), (4, 2), (-4, 2), (0, 5),
    (3, 4), (-3, 4), (4, 3), (-4, 3), (5, 0), (1, 5), (-1, 5),
    (5, 1), (-5, 1), (2, 5), (-2, 5), (5, 2), (-5, 2), (4, 4),
    (-4, 4), (3, 5), (-3, 5), (5, 3), (-5, 3), (0, 6), (6, 0),
    (1, 6), (-1, 6), (6, 1), (-6, 1), (2, 6), (-2, 6), (6, 2),
    (-6, 2), (4, 5), (-4, 5), (5, 4), (-5, 4), (3, 6), (-3, 6),
    (6, 3), (-6, 3), (0, 7), (7, 0), (1, 7), (-1, 7), (5, 5),
    (-5, 5), (7, 1), (-7, 1), (4, 6), (-4, 6), (6, 4), (-6, 4),
    (2, 7), (-2, 7), (7, 2), (-7, 2), (3, 7), (-3, 7), (7, 3),
    (-7, 3), (5, 6), (-5, 6), (6, 5), (-6, 5), (8, 0), (4, 7),
    (-4, 7), (7, 4), (-7, 4), (8, 1), (8, 2), (6, 6), (-6, 6),
    (8, 3), (5, 7), (-5, 7), (7, 5), (-7, 5), (8, 4), (6, 7),
    (-6, 7), (7, 6), (-7, 6), (8, 5), (7, 7), (-7, 7), (8, 6),
    (8, 7),
]
assert len(DISTANCE_MAP) == 120


class BitReader:
    """下位のビットから読む"""

    def __init__(self, data):
        self.d = bytes(data) + b"\0" * 8
        self.pos = 0
        self.n = len(data) * 8

    def peek(self, n):
        i = self.pos >> 3
        return (int.from_bytes(self.d[i:i + 4], "little") >> (self.pos & 7)) & ((1 << n) - 1)

    def read(self, n):
        if n == 0:
            return 0
        if n > 24:
            lo = self.read(16)
            return lo | (self.read(n - 16) << 16)
        v = self.peek(n)
        self.pos += n
        return v


class Huffman:
    """長さの表から作る標準形のハフマン符号。読むときは、次の maxlen ビットで表を引く"""

    def __init__(self, lengths):
        self.lengths = lengths
        syms = [s for s, l_ in enumerate(lengths) if l_]
        if len(syms) <= 1:                 # 記号が 1 つだけなら 0 ビットで読める
            self.single = syms[0] if syms else 0
            return
        self.single = None
        maxlen = max(lengths)
        self.maxlen = maxlen
        bl_count = [0] * (maxlen + 1)
        for l_ in lengths:
            if l_:
                bl_count[l_] += 1
        code, nxt = 0, [0] * (maxlen + 2)
        for b in range(1, maxlen + 1):
            code = (code + bl_count[b - 1]) << 1
            nxt[b] = code
        table = [None] * (1 << maxlen)
        self.codes = {}
        for s, l_ in enumerate(lengths):
            if not l_:
                continue
            c = nxt[l_]
            nxt[l_] += 1
            self.codes[s] = (c, l_)
            r = int(f"{c:0{l_}b}"[::-1], 2)     # 先に読むビットが符号の上の桁
            for hi in range(1 << (maxlen - l_)):
                table[r | (hi << l_)] = (s, l_)
        self.table = table

    def read(self, br):
        if self.single is not None:
            return self.single
        s, l_ = self.table[br.peek(self.maxlen)]
        br.pos += l_
        return s


def read_code(br, alphabet):
    if br.read(1):          # 簡単な符号：記号 1 つか 2 つ
        n = br.read(1) + 1
        first8 = br.read(1)
        lengths = [0] * alphabet
        s0 = br.read(1 + 7 * first8)
        lengths[s0] = 1
        if n == 2:
            lengths[br.read(8)] = 1
        return Huffman(lengths)
    ncl = 4 + br.read(4)
    cl = [0] * 19
    for i in range(ncl):
        cl[CODE_LENGTH_ORDER[i]] = br.read(3)
    clh = Huffman(cl)
    if br.read(1):
        nb = 2 + 2 * br.read(3)
        max_sym = 2 + br.read(nb)
    else:
        max_sym = alphabet
    lengths = [0] * alphabet
    prev, s = 8, 0
    while s < alphabet:
        if max_sym == 0:
            break
        max_sym -= 1
        c = clh.read(br)
        if c < 16:
            lengths[s] = c
            s += 1
            if c:
                prev = c
        else:
            if c == 16:
                rep, val = 3 + br.read(2), prev
            elif c == 17:
                rep, val = 3 + br.read(3), 0
            else:
                rep, val = 11 + br.read(7), 0
            for _ in range(rep):
                lengths[s] = val
                s += 1
    return Huffman(lengths)


def prefix_value(br, sym):
    """長さ・距離の「前置きの記号＋追加のビット」"""
    if sym < 4:
        return sym + 1
    extra = (sym - 2) >> 1
    off = (2 + (sym & 1)) << extra
    return off + br.read(extra) + 1


def subsample(size, bits):
    return (size + (1 << bits) - 1) >> bits


def decode_entropy_image(br, w, h, level0, log=None):
    cache_bits = 0
    if br.read(1):
        cache_bits = br.read(4)
        assert 1 <= cache_bits <= 11
    meta, meta_bits = None, 0
    if level0 and br.read(1):
        meta_bits = br.read(3) + 2
        mw, mh = subsample(w, meta_bits), subsample(h, meta_bits)
        mimg = decode_entropy_image(br, mw, mh, False)
        meta = [(p >> 8) & 0xFFFF for p in mimg]
        ngroups = max(meta) + 1
    else:
        ngroups = 1
    cache_size = (1 << cache_bits) if cache_bits else 0
    groups = []
    for _ in range(ngroups):
        groups.append([read_code(br, 256 + 24 + cache_size), read_code(br, 256), read_code(br, 256),
                       read_code(br, 256), read_code(br, 40)])
    out = [0] * (w * h)
    cache = [0] * cache_size
    shift = 32 - cache_bits
    pos, last_cached, n = 0, 0, w * h
    tokens = [] if log is not None else None

    def flush(upto):
        nonlocal last_cached
        while last_cached < upto:
            p = out[last_cached]
            cache[((0x1E35A7BD * p) & 0xFFFFFFFF) >> shift] = p
            last_cached += 1
    while pos < n:
        if meta is not None:
            x, y = pos % w, pos // w
            g = groups[meta[(y >> meta_bits) * subsample(w, meta_bits) + (x >> meta_bits)]]
        else:
            g = groups[0]
        b0 = br.pos
        code = g[0].read(br)
        if code < 256:
            r = g[1].read(br)
            b = g[2].read(br)
            a = g[3].read(br)
            out[pos] = (a << 24) | (r << 16) | (code << 8) | b
            if tokens is not None:
                tokens.append(("lit", pos, 1, br.pos - b0))
            pos += 1
        elif code < 256 + 24:
            length = prefix_value(br, code - 256)
            dsym = g[4].read(br)
            dcode = prefix_value(br, dsym)
            if dcode > 120:
                dist = dcode - 120
                xy = None
            else:
                xi, yi = DISTANCE_MAP[dcode - 1]
                dist = max(xi + yi * w, 1)
                xy = (xi, yi)
            for k in range(length):
                out[pos + k] = out[pos + k - dist]
            if tokens is not None:
                tokens.append(("copy", pos, length, br.pos - b0, dcode, dist, xy))
            pos += length
        else:
            idx = code - 280
            flush(pos)
            out[pos] = cache[idx]
            if tokens is not None:
                tokens.append(("cache", pos, 1, br.pos - b0, idx))
            pos += 1
        if cache_size:
            flush(pos)
    if log is not None:
        log.update(tokens=tokens, cache_bits=cache_bits, meta_bits=meta_bits, groups=ngroups)
    return out


def _avg2(a, b):
    return (((a ^ b) & 0xFEFEFEFE) >> 1) + (a & b)


def _ch(p):
    return [(p >> 24) & 255, (p >> 16) & 255, (p >> 8) & 255, p & 255]


def _pack(c):
    return (c[0] << 24) | (c[1] << 16) | (c[2] << 8) | c[3]


def _clamp(v):
    return 0 if v < 0 else 255 if v > 255 else v


def _select(L, T, TL):
    l_, t, tl = _ch(L), _ch(T), _ch(TL)
    pl = sum(abs(t[i] - tl[i]) for i in range(4))
    pt = sum(abs(l_[i] - tl[i]) for i in range(4))
    return L if pl < pt else T


def _cas_full(a, b, c):
    a, b, c = _ch(a), _ch(b), _ch(c)
    return _pack([_clamp(a[i] + b[i] - c[i]) for i in range(4)])


def _cas_half(a, b):
    a, b = _ch(a), _ch(b)
    return _pack([_clamp(a[i] + int((a[i] - b[i]) / 2)) for i in range(4)])


def predict(mode, L, T, TR, TL):
    if mode == 0:
        return 0xFF000000
    if mode == 1:
        return L
    if mode == 2:
        return T
    if mode == 3:
        return TR
    if mode == 4:
        return TL
    if mode == 5:
        return _avg2(_avg2(L, TR), T)
    if mode == 6:
        return _avg2(L, TL)
    if mode == 7:
        return _avg2(L, T)
    if mode == 8:
        return _avg2(TL, T)
    if mode == 9:
        return _avg2(T, TR)
    if mode == 10:
        return _avg2(_avg2(L, TL), _avg2(T, TR))
    if mode == 11:
        return _select(L, T, TL)
    if mode == 12:
        return _cas_full(L, T, TL)
    return _cas_half(_avg2(L, T), TL)


def _add(a, b):
    return (((a & 0xFF00FF00) + (b & 0xFF00FF00)) & 0xFF00FF00) | (((a & 0x00FF00FF) + (b & 0x00FF00FF)) & 0x00FF00FF)


def _delta(t, c):
    t = t - 256 if t > 127 else t
    c = c - 256 if c > 127 else c
    return (t * c) >> 5


def inverse_transform(tr, px, w, h):
    kind = tr["type"]
    if kind == SUBTRACT_GREEN:
        out = []
        for p in px:
            g = (p >> 8) & 255
            out.append((p & 0xFF00FF00) | ((((p >> 16) + g) & 255) << 16) | (((p & 255) + g) & 255))
        return out
    if kind == PREDICTOR:
        bits, data = tr["bits"], tr["data"]
        bw = subsample(w, bits)
        out = list(px)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if y == 0:
                    pred = 0xFF000000 if x == 0 else out[i - 1]
                elif x == 0:
                    pred = out[i - w]
                else:
                    mode = (data[(y >> bits) * bw + (x >> bits)] >> 8) & 15
                    pred = predict(mode, out[i - 1], out[i - w], out[i - w + 1], out[i - w - 1])
                out[i] = _add(out[i], pred)
        return out
    if kind == CROSS_COLOR:
        bits, data = tr["bits"], tr["data"]
        bw = subsample(w, bits)
        out = []
        for i, p in enumerate(px):
            y, x = divmod(i, w)
            m = data[(y >> bits) * bw + (x >> bits)]
            g2r, g2b, r2b = m & 255, (m >> 8) & 255, (m >> 16) & 255
            g = (p >> 8) & 255
            r = (((p >> 16) & 255) + _delta(g2r, g)) & 255
            b = ((p & 255) + _delta(g2b, g) + _delta(r2b, r)) & 255
            out.append((p & 0xFF00FF00) | (r << 16) | b)
        return out
    # COLOR_INDEXING：詰めた番号を色に戻す
    table, wb = tr["table"], tr["width_bits"]
    pw = subsample(w, wb)
    per = 1 << wb
    bpp = 8 >> wb
    mask = (1 << bpp) - 1
    out = []
    for y in range(h):
        for x in range(w):
            g = (px[y * pw + (x >> wb)] >> 8) & 255
            idx = (g >> ((x & (per - 1)) * bpp)) & mask
            out.append(table[idx] if idx < len(table) else 0)
    return out


def decode_stream(br, w, h, log=None):
    """変換の並び＋本体の画像 (ヘッダのあと)"""
    transforms, xw = [], w
    seen = set()
    while br.read(1):
        t = br.read(2)
        assert t not in seen
        seen.add(t)
        tr = dict(type=t, width=xw)
        b0 = br.pos
        if t in (PREDICTOR, CROSS_COLOR):
            tr["bits"] = br.read(3) + 2
            tr["data"] = decode_entropy_image(br, subsample(xw, tr["bits"]), subsample(h, tr["bits"]), False)
        elif t == COLOR_INDEXING:
            n = br.read(8) + 1
            raw = decode_entropy_image(br, n, 1, False)
            table = [raw[0]]
            for p in raw[1:]:
                table.append(_add(table[-1], p))
            tr["table"] = table
            tr["width_bits"] = 0 if n > 16 else 1 if n > 4 else 2 if n > 2 else 3
            xw = subsample(xw, tr["width_bits"])
        tr["bits_used"] = br.pos - b0
        transforms.append(tr)
    b0 = br.pos
    lg = {} if log is not None else None
    px = decode_entropy_image(br, xw, h, True, lg)
    if log is not None:
        log.update(lg, transforms=transforms, coded_width=xw, image_bits=br.pos - b0, residual=list(px))
    for tr in reversed(transforms):
        px = inverse_transform(tr, px, tr["width"], h)
    return px, transforms


def to_rgba(px, w, h):
    a = np.array(px, np.uint32).reshape(h, w)
    return np.stack([(a >> 16) & 255, (a >> 8) & 255, a & 255, a >> 24], -1).astype(np.uint8)


def decode(data):
    assert data[0] == 0x2F
    br = BitReader(data[1:])
    w = br.read(14) + 1
    h = br.read(14) + 1
    alpha = br.read(1)
    ver = br.read(3)
    assert ver == 0
    log = {}
    px, transforms = decode_stream(br, w, h, log)
    return dict(width=w, height=h, alpha_used=alpha, rgba=to_rgba(px, w, h), argb=px, **log)


def decode_alpha(data, w, h):
    """ALPH の箱：先頭 1 バイトに圧縮のしかたと前処理、残りが VP8L の本体 (ヘッダなし) の緑に入った透明度"""
    hd = data[0]
    method, filt, pre = hd & 3, (hd >> 2) & 3, (hd >> 4) & 3
    if method == 0:
        a = np.frombuffer(bytes(data[1:1 + w * h]), np.uint8).reshape(h, w).astype(np.int32)
        log = {}
    else:
        br = BitReader(data[1:])
        log = {}
        px, _ = decode_stream(br, w, h, log)
        a = ((np.array(px, np.uint32) >> 8) & 255).reshape(h, w).astype(np.int32)
    out = a.copy()
    for y in range(h):
        for x in range(w):
            if filt == 0:
                break
            if x == 0 and y == 0:
                pred = 0
            elif y == 0:
                pred = out[0, x - 1]
            elif x == 0:
                pred = out[y - 1, 0]
            elif filt == 1:
                pred = out[y, x - 1]
            elif filt == 2:
                pred = out[y - 1, x]
            else:
                pred = _clamp(int(out[y, x - 1]) + int(out[y - 1, x]) - int(out[y - 1, x - 1]))
            out[y, x] = (a[y, x] + pred) & 255
    return dict(method=method, filter=filt, preprocessing=pre, alpha=out.astype(np.uint8), log=log)
