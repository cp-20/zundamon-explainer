"""自前の VP8 (WebP の非可逆) 復号器。RFC 6386 と libwebp の復号の手順どおり。

画面に出す数字 (ブロックの予測の向き、係数、量子化の幅、算術符号の確率) はすべてここから取る。
dwebp の出力 (-yuv、-nofilter) と、Y・U・V の全画素が一致することを tools/check_decoder.py で確かめる。
"""
from vp8tables import AC_Q, COEFF_UPDATE_PROBS, DC_Q, DEFAULT_COEFF_PROBS, KF_BMODE_PROBS

# 16×16 と色 (U・V) の予測の向き
DC_PRED, V_PRED, H_PRED, TM_PRED, B_PRED = range(5)
# 4×4 の予測の向き (RFC 6386 の番号)
B_DC, B_TM, B_VE, B_HE, B_LD, B_RD, B_VR, B_VL, B_HD, B_HU = range(10)
YMODE_NAME = {DC_PRED: "DC", V_PRED: "V", H_PRED: "H", TM_PRED: "TM", B_PRED: "B"}
BMODE_NAME = ["DC", "TM", "VE", "HE", "LD", "RD", "VR", "VL", "HD", "HU"]
# 16×16 の向きを、隣の 4×4 の向きの文脈として使うときの読み替え
Y_TO_B = {DC_PRED: B_DC, V_PRED: B_VE, H_PRED: B_HE, TM_PRED: B_TM}

BMODE_TREE = [-B_DC, 2, -B_TM, 4, -B_VE, 6, 8, 12, -B_HE, 10, -B_RD, -B_VR, -B_LD, 14, -B_VL, 16, -B_HD, -B_HU]
ZIGZAG = [0, 1, 4, 8, 5, 2, 3, 6, 9, 12, 13, 10, 7, 11, 14, 15]
BANDS = [0, 1, 2, 3, 6, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 7, 0]
CAT3456 = [[173, 148, 140], [176, 155, 140, 135], [180, 157, 141, 134, 130],
           [254, 254, 243, 230, 196, 177, 153, 140, 133, 130, 129]]


def clip255(v):
    return 0 if v < 0 else 255 if v > 255 else v


class BoolDecoder:
    """算術符号 (ブール符号) の読み手。確率 prob/256 で 0 が出るとして 1 ビットずつ読む"""

    def __init__(self, data, start=0, end=None):
        self.d = data
        self.pos = start
        self.end = len(data) if end is None else end
        self.value = (self._byte() << 8) | self._byte()
        self.range = 255
        self.bit_count = 0
        self.log = None      # 記録するときは list にする：(prob, bit, range の前, range の後)

    def _byte(self):
        if self.pos < self.end:
            b = self.d[self.pos]
            self.pos += 1
            return b
        self.pos += 1
        return 0

    def bool(self, prob):
        r0 = self.range
        split = 1 + (((self.range - 1) * prob) >> 8)
        big = split << 8
        if self.value >= big:
            bit = 1
            self.range -= split
            self.value -= big
        else:
            bit = 0
            self.range = split
        while self.range < 128:
            self.value <<= 1
            self.range <<= 1
            self.bit_count += 1
            if self.bit_count == 8:
                self.bit_count = 0
                self.value |= self._byte()
        if self.log is not None:
            self.log.append((prob, bit, r0, split))
        return bit

    def lit(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bool(128)
        return v

    def signed(self, n):
        v = self.lit(n)
        return -v if self.bool(128) else v

    def bits_used(self):
        """ここまでに読み進めたビット数 (先読みの 2 バイトを除く)"""
        return (self.pos - 2) * 8 + self.bit_count


def tree_read(bd, tree, probs):
    i = 0
    while True:
        i = tree[i + bd.bool(probs[i >> 1])]
        if i <= 0:
            return -i


# ---------------- 予測 ----------------

def avg3(a, b, c):
    return (a + 2 * b + c + 2) >> 2


def avg2(a, b):
    return (a + b + 1) >> 1


def pred4(mode, top, left, X):
    """4×4 の予測。top は上の 8 画素 (右上 4 つを含む)、left は左の 4 画素、X は左上。返り値は [y][x]"""
    A, B, C, D, E, F, G, H = top
    I, J, K, L = left
    P = [[0] * 4 for _ in range(4)]

    def put(v, *xy):
        for x, y in xy:
            P[y][x] = v
    if mode == B_DC:
        v = (sum(top[:4]) + sum(left) + 4) >> 3
        return [[v] * 4 for _ in range(4)]
    if mode == B_TM:
        return [[clip255(left[y] + top[x] - X) for x in range(4)] for y in range(4)]
    if mode == B_VE:
        t = [X] + list(top[:5])
        row = [avg3(t[i], t[i + 1], t[i + 2]) for i in range(4)]
        return [row[:] for _ in range(4)]
    if mode == B_HE:
        col = [avg3(X, I, J), avg3(I, J, K), avg3(J, K, L), avg3(K, L, L)]
        return [[col[y]] * 4 for y in range(4)]
    if mode == B_LD:
        put(avg3(A, B, C), (0, 0))
        put(avg3(B, C, D), (1, 0), (0, 1))
        put(avg3(C, D, E), (2, 0), (1, 1), (0, 2))
        put(avg3(D, E, F), (3, 0), (2, 1), (1, 2), (0, 3))
        put(avg3(E, F, G), (3, 1), (2, 2), (1, 3))
        put(avg3(F, G, H), (3, 2), (2, 3))
        put(avg3(G, H, H), (3, 3))
    elif mode == B_RD:
        put(avg3(J, K, L), (0, 3))
        put(avg3(I, J, K), (1, 3), (0, 2))
        put(avg3(X, I, J), (2, 3), (1, 2), (0, 1))
        put(avg3(A, X, I), (3, 3), (2, 2), (1, 1), (0, 0))
        put(avg3(B, A, X), (3, 2), (2, 1), (1, 0))
        put(avg3(C, B, A), (3, 1), (2, 0))
        put(avg3(D, C, B), (3, 0))
    elif mode == B_VR:
        put(avg2(X, A), (0, 0), (1, 2))
        put(avg2(A, B), (1, 0), (2, 2))
        put(avg2(B, C), (2, 0), (3, 2))
        put(avg2(C, D), (3, 0))
        put(avg3(K, J, I), (0, 3))
        put(avg3(J, I, X), (0, 2))
        put(avg3(I, X, A), (0, 1), (1, 3))
        put(avg3(X, A, B), (1, 1), (2, 3))
        put(avg3(A, B, C), (2, 1), (3, 3))
        put(avg3(B, C, D), (3, 1))
    elif mode == B_VL:
        put(avg2(A, B), (0, 0))
        put(avg2(B, C), (1, 0), (0, 2))
        put(avg2(C, D), (2, 0), (1, 2))
        put(avg2(D, E), (3, 0), (2, 2))
        put(avg3(A, B, C), (0, 1))
        put(avg3(B, C, D), (1, 1), (0, 3))
        put(avg3(C, D, E), (2, 1), (1, 3))
        put(avg3(D, E, F), (3, 1), (2, 3))
        put(avg3(E, F, G), (3, 2))
        put(avg3(F, G, H), (3, 3))
    elif mode == B_HD:
        put(avg2(I, X), (0, 0), (2, 1))
        put(avg2(J, I), (0, 1), (2, 2))
        put(avg2(K, J), (0, 2), (2, 3))
        put(avg2(L, K), (0, 3))
        put(avg3(A, B, C), (3, 0))
        put(avg3(X, A, B), (2, 0))
        put(avg3(I, X, A), (1, 0), (3, 1))
        put(avg3(J, I, X), (1, 1), (3, 2))
        put(avg3(K, J, I), (1, 2), (3, 3))
        put(avg3(L, K, J), (1, 3))
    elif mode == B_HU:
        put(avg2(I, J), (0, 0))
        put(avg2(J, K), (2, 0), (0, 1))
        put(avg2(K, L), (2, 1), (0, 2))
        put(avg3(I, J, K), (1, 0))
        put(avg3(J, K, L), (3, 0), (1, 1))
        put(avg3(K, L, L), (3, 1), (1, 2))
        put(L, (3, 2), (2, 2), (0, 3), (1, 3), (2, 3), (3, 3))
    return P


def pred_big(mode, top, left, X, n, has_top, has_left):
    """16×16 (n=16) と色の 8×8 (n=8) の予測"""
    if mode == DC_PRED:
        sh = 3 if n == 8 else 4
        if has_top and has_left:
            v = (sum(top[:n]) + sum(left[:n]) + n) >> (sh + 1)
        elif has_top:
            v = (sum(top[:n]) + n // 2) >> sh
        elif has_left:
            v = (sum(left[:n]) + n // 2) >> sh
        else:
            v = 128
        return [[v] * n for _ in range(n)]
    if mode == V_PRED:
        return [list(top[:n]) for _ in range(n)]
    if mode == H_PRED:
        return [[left[y]] * n for y in range(n)]
    return [[clip255(left[y] + top[x] - X) for x in range(n)] for y in range(n)]


# ---------------- 変換 ----------------

def _m1(a):
    return ((a * 20091) >> 16) + a


def _m2(a):
    return (a * 35468) >> 16


def idct4(c):
    """4×4 の逆変換 (係数はラスタ順の 16 個)。返り値は足し込む差 [y][x]"""
    tmp = [0] * 16
    for i in range(4):
        a = c[i] + c[8 + i]
        b = c[i] - c[8 + i]
        cc = _m2(c[4 + i]) - _m1(c[12 + i])
        d = _m1(c[4 + i]) + _m2(c[12 + i])
        tmp[4 * i + 0] = a + d
        tmp[4 * i + 1] = b + cc
        tmp[4 * i + 2] = b - cc
        tmp[4 * i + 3] = a - d
    out = [[0] * 4 for _ in range(4)]
    for i in range(4):
        dc = tmp[i] + 4
        a = dc + tmp[8 + i]
        b = dc - tmp[8 + i]
        cc = _m2(tmp[4 + i]) - _m1(tmp[12 + i])
        d = _m1(tmp[4 + i]) + _m2(tmp[12 + i])
        out[i][0] = (a + d) >> 3
        out[i][1] = (b + cc) >> 3
        out[i][2] = (b - cc) >> 3
        out[i][3] = (a - d) >> 3
    return out


def iwht(c):
    """16×16 の向きのときの、16 個のブロックの DC (Y2) の逆変換。返り値は 16 個 (ブロックのラスタ順)"""
    tmp = [0] * 16
    for i in range(4):
        a0 = c[0 + i] + c[12 + i]
        a1 = c[4 + i] + c[8 + i]
        a2 = c[4 + i] - c[8 + i]
        a3 = c[0 + i] - c[12 + i]
        tmp[0 + i] = a0 + a1
        tmp[8 + i] = a0 - a1
        tmp[4 + i] = a3 + a2
        tmp[12 + i] = a3 - a2
    out = [0] * 16
    for i in range(4):
        dc = tmp[0 + i * 4] + 3
        a0 = dc + tmp[3 + i * 4]
        a1 = tmp[1 + i * 4] + tmp[2 + i * 4]
        a2 = tmp[1 + i * 4] - tmp[2 + i * 4]
        a3 = dc - tmp[3 + i * 4]
        out[4 * i + 0] = (a0 + a1) >> 3
        out[4 * i + 1] = (a3 + a2) >> 3
        out[4 * i + 2] = (a0 - a1) >> 3
        out[4 * i + 3] = (a3 - a2) >> 3
    return out


# ---------------- 係数 ----------------

def large_value(bd, p):
    if not bd.bool(p[3]):
        if not bd.bool(p[4]):
            return 2
        return 3 + bd.bool(p[5])
    if not bd.bool(p[6]):
        if not bd.bool(p[7]):
            return 5 + bd.bool(159)
        v = 7 + 2 * bd.bool(165)
        return v + bd.bool(145)
    bit1 = bd.bool(p[8])
    bit0 = bd.bool(p[9 + bit1])
    cat = 2 * bit1 + bit0
    v = 0
    for pr in CAT3456[cat]:
        v += v + bd.bool(pr)
    return v + 3 + (8 << cat)


def read_coeffs(bd, probs, typ, ctx, first):
    """1 つの 4×4 の係数 (量子化したままの段の数) を読む。返り値：(ジグザグ順の 16 個, 終わりの位置 n)"""
    lev = [0] * 16
    n = first
    p = probs[typ][BANDS[n]][ctx]
    while n < 16:
        if not bd.bool(p[0]):
            return lev, n          # 終わり (EOB)
        while not bd.bool(p[1]):   # 0 が続く
            n += 1
            if n == 16:
                return lev, 16
            p = probs[typ][BANDS[n]][0]
        if not bd.bool(p[2]):
            v = 1
            nctx = 1
        else:
            v = large_value(bd, p)
            nctx = 2
        if bd.bool(128):
            v = -v
        lev[n] = v
        n += 1
        p = probs[typ][BANDS[n]][nctx]
    return lev, 16


# ---------------- ループフィルタ ----------------

def _sclip1(v):      # [-1020, 1020] → [-128, 127]
    return -128 if v < -128 else 127 if v > 127 else v


def _sclip2(v):      # [-112, 112] → [-16, 15]
    return -16 if v < -16 else 15 if v > 15 else v


def _filter_line(P, pos, step, kind, t2, it, hev_t):
    """1 本の境目をまたぐ画素の並び P (平らなリスト) の pos の所で、境目をなだらかにする"""
    p3, p2, p1, p0 = P[pos - 4 * step], P[pos - 3 * step], P[pos - 2 * step], P[pos - step]
    q0, q1, q2, q3 = P[pos], P[pos + step], P[pos + 2 * step], P[pos + 3 * step]
    if kind == "simple":
        if 4 * abs(p0 - q0) + abs(p1 - q1) > t2:
            return False
        a = 3 * (q0 - p0) + _sclip1(p1 - q1)
        a1 = _sclip2((a + 4) >> 3)
        a2 = _sclip2((a + 3) >> 3)
        P[pos - step] = clip255(p0 + a2)
        P[pos] = clip255(q0 - a1)
        return True
    if 4 * abs(p0 - q0) + abs(p1 - q1) > t2:
        return False
    if (abs(p3 - p2) > it or abs(p2 - p1) > it or abs(p1 - p0) > it or abs(q3 - q2) > it or abs(q2 - q1) > it
            or abs(q1 - q0) > it):
        return False
    if abs(p1 - p0) > hev_t or abs(q1 - q0) > hev_t:      # 境目で大きく変わる所は 2 画素だけ
        a = 3 * (q0 - p0) + _sclip1(p1 - q1)
        a1 = _sclip2((a + 4) >> 3)
        a2 = _sclip2((a + 3) >> 3)
        P[pos - step] = clip255(p0 + a2)
        P[pos] = clip255(q0 - a1)
    elif kind == "mb":                                     # ブロックの境目：6 画素
        a = _sclip1(3 * (q0 - p0) + _sclip1(p1 - q1))
        a1 = (27 * a + 63) >> 7
        a2 = (18 * a + 63) >> 7
        a3 = (9 * a + 63) >> 7
        P[pos - 3 * step] = clip255(p2 + a3)
        P[pos - 2 * step] = clip255(p1 + a2)
        P[pos - step] = clip255(p0 + a1)
        P[pos] = clip255(q0 - a1)
        P[pos + step] = clip255(q1 - a2)
        P[pos + 2 * step] = clip255(q2 - a3)
    else:                                                  # 中の 4×4 の境目：4 画素
        a = 3 * (q0 - p0)
        a1 = _sclip2((a + 4) >> 3)
        a2 = _sclip2((a + 3) >> 3)
        a3 = (a1 + 1) >> 1
        P[pos - 2 * step] = clip255(p1 + a3)
        P[pos - step] = clip255(p0 + a2)
        P[pos] = clip255(q0 - a1)
        P[pos + step] = clip255(q1 - a3)
    return True


# ---------------- 本体 ----------------

def decode(data, filt=True):
    """VP8 のデータ (RIFF の中身、フレームのタグから) を読む。

    返り値 dict：
      width height mbw mbh q (量子化の番号) filter (type level sharpness) partitions
      Y U V：復号した平面 (MB の大きさまで含む、list の list)。filt=False ならループフィルタなし
      Y_nofilter U_nofilter V_nofilter
      mbs[mby][mbx]：ymode bmodes uvmode segment skip levels (25 個のブロックの段の数、ラスタ順。24 番は Y2)
        deq (段の数×量子化の幅) pred16/pred4 (予測) mode_log (向きを読んだ判定) tok_log[b] (係数を読んだ判定)
        判定の記録は (確率, 読んだビット, 読む前の幅, 0 の側の幅) の列
      sizes：最初の区画 (向きなど) と係数の区画のバイト数
    """
    d = data
    tag = d[0] | (d[1] << 8) | (d[2] << 16)
    key = not (tag & 1)
    assert key, "キーフレームだけ"
    first_size = (tag >> 5) & 0x7FFFF
    assert d[3:6] == b"\x9d\x01\x2a"
    width = (d[6] | (d[7] << 8)) & 0x3FFF
    height = (d[8] | (d[9] << 8)) & 0x3FFF
    mbw, mbh = (width + 15) // 16, (height + 15) // 16
    p0 = 10
    bd = BoolDecoder(d, p0, p0 + first_size)
    hdr = dict(width=width, height=height, mbw=mbw, mbh=mbh, first_size=first_size)
    hdr["colorspace"] = bd.bool(128)
    hdr["clamp"] = bd.bool(128)
    # 区分け (segment)
    use_seg = bd.bool(128)
    update_map, absolute, seg_q, seg_f, seg_probs = 0, 0, [0] * 4, [0] * 4, [255] * 3
    if use_seg:
        update_map = bd.bool(128)
        if bd.bool(128):
            absolute = bd.bool(128)
            seg_q = [bd.signed(7) if bd.bool(128) else 0 for _ in range(4)]
            seg_f = [bd.signed(6) if bd.bool(128) else 0 for _ in range(4)]
        if update_map:
            seg_probs = [bd.lit(8) if bd.bool(128) else 255 for _ in range(3)]
    hdr.update(segments=dict(enabled=use_seg, update_map=update_map, absolute=absolute, q=seg_q, f=seg_f))
    # ループフィルタ
    simple = bd.bool(128)
    level = bd.lit(6)
    sharp = bd.lit(3)
    ref_d, mode_d = [0] * 4, [0] * 4
    use_lf_delta = bd.bool(128)
    if use_lf_delta and bd.bool(128):
        for i in range(4):
            if bd.bool(128):
                ref_d[i] = bd.signed(6)
        for i in range(4):
            if bd.bool(128):
                mode_d[i] = bd.signed(6)
    ftype = 0 if level == 0 else 1 if simple else 2
    hdr["filter"] = dict(type=ftype, level=level, sharpness=sharp, use_delta=use_lf_delta, ref=ref_d, mode=mode_d)
    # 係数の区画
    nparts = 1 << bd.lit(2)
    pstart = p0 + first_size
    sz_end = pstart + 3 * (nparts - 1)
    parts, q = [], sz_end
    for i in range(nparts):
        if i < nparts - 1:
            s = d[pstart + 3 * i] | (d[pstart + 3 * i + 1] << 8) | (d[pstart + 3 * i + 2] << 16)
        else:
            s = len(d) - q
        parts.append((q, min(q + s, len(d))))
        q += s
    hdr["partitions"] = [b - a for a, b in parts]
    # 量子化
    base_q = bd.lit(7)
    dq = [bd.signed(4) if bd.bool(128) else 0 for _ in range(5)]   # y1_dc y2_dc y2_ac uv_dc uv_ac
    hdr["q"] = base_q
    hdr["dq"] = dq
    qm = []
    for s in range(4):
        if use_seg:
            qq = seg_q[s] + (0 if absolute else base_q)
        else:
            qq = base_q

        def cl(v, hi=127):
            return 0 if v < 0 else hi if v > hi else v
        y2ac = (AC_Q[cl(qq + dq[2])] * 101581) >> 16
        qm.append(dict(y1=(DC_Q[cl(qq + dq[0])], AC_Q[cl(qq)]),
                       y2=(DC_Q[cl(qq + dq[1])] * 2, max(y2ac, 8)),
                       uv=(DC_Q[cl(qq + dq[3], 117)], AC_Q[cl(qq + dq[4])]), q=qq))
        if not use_seg:
            qm = qm * 4
            break
    hdr["quant"] = qm
    bd.bool(128)          # refresh_entropy_probs (使わない)
    probs = [[[[0] * 11 for _ in range(3)] for _ in range(8)] for _ in range(4)]
    updated = 0
    for i in range(4):
        for j in range(8):
            for k in range(3):
                for t in range(11):
                    o = ((i * 8 + j) * 3 + k) * 11 + t
                    if bd.bool(COEFF_UPDATE_PROBS[o]):
                        probs[i][j][k][t] = bd.lit(8)
                        updated += 1
                    else:
                        probs[i][j][k][t] = DEFAULT_COEFF_PROBS[o]
    hdr["probs"] = probs
    hdr["probs_updated"] = updated
    use_skip = bd.bool(128)
    skip_p = bd.lit(8) if use_skip else None
    hdr["skip_prob"] = skip_p
    hdr["header_bits"] = bd.bits_used()

    # ---- 各 MB の向き (最初の区画) ----
    mbs = [[None] * mbw for _ in range(mbh)]
    top_b = [B_DC] * (4 * mbw)
    for my in range(mbh):
        left_b = [B_DC] * 4
        for mx in range(mbw):
            m = {}
            b0 = bd.bits_used()
            bd.log = []
            if update_map:
                m["segment"] = bd.bool(seg_probs[1]) if not bd.bool(seg_probs[0]) else 2 + bd.bool(seg_probs[2])
            else:
                m["segment"] = 0
            m["skip"] = bd.bool(skip_p) if use_skip else 0
            is4 = not bd.bool(145)
            if not is4:
                ym = (TM_PRED if bd.bool(128) else H_PRED) if bd.bool(156) else (V_PRED if bd.bool(163) else DC_PRED)
                m["ymode"] = ym
                bm = Y_TO_B[ym]
                for i in range(4):
                    top_b[4 * mx + i] = bm
                    left_b[i] = bm
                m["bmodes"] = None
            else:
                m["ymode"] = B_PRED
                modes = []
                for y in range(4):
                    for x in range(4):
                        a, l_ = top_b[4 * mx + x], left_b[y]
                        o = (a * 10 + l_) * 9
                        bm = tree_read(bd, BMODE_TREE, KF_BMODE_PROBS[o:o + 9])
                        modes.append(bm)
                        top_b[4 * mx + x] = bm
                        left_b[y] = bm
                m["bmodes"] = modes
            m["uvmode"] = DC_PRED if not bd.bool(142) else V_PRED if not bd.bool(114) else (
                TM_PRED if bd.bool(183) else H_PRED)
            m["mode_bits"] = bd.bits_used() - b0
            m["mode_log"] = bd.log
            bd.log = None
            mbs[my][mx] = m
    hdr["mode_bytes"] = first_size

    # ---- 係数 (残りの区画) と組み立て ----
    W16, H16 = mbw * 16, mbh * 16
    Y = [[0] * W16 for _ in range(H16)]
    U = [[0] * (W16 // 2) for _ in range(H16 // 2)]
    V = [[0] * (W16 // 2) for _ in range(H16 // 2)]
    PY = [[0] * W16 for _ in range(H16)]         # 予測だけの画面 (差を足す前)
    tbd = [BoolDecoder(d, a, b) for a, b in parts]
    above_nz = [[0] * 9 for _ in range(mbw)]     # Y 4・U 2・V 2・Y2 1
    for my in range(mbh):
        tb = tbd[my % nparts]
        left_nz = [0] * 9
        for mx in range(mbw):
            m = mbs[my][mx]
            qmat = qm[m["segment"]]
            an, ln = above_nz[mx], left_nz
            coeffs = [[0] * 16 for _ in range(25)]     # 段の数 (ラスタ順)。24 番は Y2
            deq = [[0] * 16 for _ in range(24)]
            nzcode = [0] * 24
            tok_log = [None] * 25
            b0 = tb.bits_used()
            if not m["skip"]:
                i16 = m["ymode"] != B_PRED
                if i16:
                    ctx = an[8] + ln[8]
                    tb.log = tok_log[24] = []
                    lev, n = read_coeffs(tb, probs, 1, ctx, 0)
                    an[8] = ln[8] = int(n > 0)
                    y2 = [0] * 16
                    for k in range(16):
                        coeffs[24][ZIGZAG[k]] = lev[k]
                        y2[ZIGZAG[k]] = lev[k] * qmat["y2"][0 if k == 0 else 1]
                    dcs = iwht(y2)
                    typ, first = 0, 1
                else:
                    dcs = None
                    typ, first = 3, 0
                for y in range(4):
                    for x in range(4):
                        b = 4 * y + x
                        ctx = an[x] + ln[y]
                        tb.log = tok_log[b] = []
                        lev, n = read_coeffs(tb, probs, typ, ctx, first)
                        nz = int(n > first)
                        an[x] = ln[y] = nz
                        for k in range(16):
                            coeffs[b][ZIGZAG[k]] = lev[k]
                            deq[b][ZIGZAG[k]] = lev[k] * qmat["y1"][0 if k == 0 else 1]
                        if dcs is not None:
                            deq[b][0] = dcs[b]
                        nzcode[b] = 3 if n > 3 else 2 if n > 1 else int(deq[b][0] != 0)
                for ch in (0, 1):
                    for y in range(2):
                        for x in range(2):
                            b = 16 + 4 * ch + 2 * y + x
                            ia, il = 4 + 2 * ch + x, 4 + 2 * ch + y
                            ctx = an[ia] + ln[il]
                            tb.log = tok_log[b] = []
                            lev, n = read_coeffs(tb, probs, 2, ctx, 0)
                            an[ia] = ln[il] = int(n > 0)
                            for k in range(16):
                                coeffs[b][ZIGZAG[k]] = lev[k]
                                deq[b][ZIGZAG[k]] = lev[k] * qmat["uv"][0 if k == 0 else 1]
                            nzcode[b] = 3 if n > 3 else 2 if n > 1 else int(deq[b][0] != 0)
                m["has_coeffs"] = any(nzcode)
            else:
                for i in range(8):
                    an[i] = ln[i] = 0
                if m["ymode"] != B_PRED:
                    an[8] = ln[8] = 0
                m["has_coeffs"] = False
            tb.log = None
            m["tok_log"] = tok_log
            m["coeff_bits"] = tb.bits_used() - b0
            m["levels"] = coeffs
            m["deq"] = deq
            _reconstruct(m, mx, my, mbw, Y, U, V, PY)
    out = dict(hdr, mbs=mbs, Y_nofilter=[r[:] for r in Y], U_nofilter=[r[:] for r in U],
               V_nofilter=[r[:] for r in V], PY=PY)
    if filt and ftype:
        _loop_filter(hdr, mbs, Y, U, V)
    out.update(Y=Y, U=U, V=V)
    return out


def _edges(P, x0, y0, n, nright, has_top, has_left, W):
    """平面 P の (x0, y0) の n×n の、上 (n＋右上 nright)・左・左上の画素。端の決まり：上は 127、左は 129"""
    if has_top:
        top = P[y0 - 1][x0:x0 + n]
        if nright:
            if x0 + n < W:
                top = top + P[y0 - 1][x0 + n:x0 + n + nright]
            else:
                top = top + [P[y0 - 1][x0 + n - 1]] * nright
    else:
        top = [127] * (n + nright)
    left = [P[y0 + i][x0 - 1] for i in range(n)] if has_left else [129] * n
    if not has_top:
        X = 127
    elif not has_left:
        X = 129
    else:
        X = P[y0 - 1][x0 - 1]
    return top, left, X


def _reconstruct(m, mx, my, mbw, Y, U, V, PY):
    """予測を作り、差を足す (ループフィルタの前)"""
    x0, y0 = mx * 16, my * 16
    W = mbw * 16
    ht, hl = my > 0, mx > 0
    deq = m["deq"]
    m["pred16"] = None
    if m["ymode"] != B_PRED:
        top, left, X = _edges(Y, x0, y0, 16, 0, ht, hl, W)
        P = pred_big(m["ymode"], top, left, X, 16, ht, hl)
        for y in range(16):
            PY[y0 + y][x0:x0 + 16] = P[y]
        for b in range(16):
            bx, by = b % 4, b // 4
            r = idct4(deq[b])
            for y in range(4):
                for x in range(4):
                    Y[y0 + 4 * by + y][x0 + 4 * bx + x] = clip255(P[4 * by + y][4 * bx + x] + r[y][x])
    else:
        # 21×21 の作業場 (libwebp と同じ)：0 行目が上の行 (右上 4 つまで)、0 列目が左の列
        top, left, X = _edges(Y, x0, y0, 16, 4, ht, hl, W)
        buf = [[0] * 21 for _ in range(17)]
        buf[0][0] = X
        buf[0][1:21] = top
        for i in range(16):
            buf[1 + i][0] = left[i]
        # 右の列の 4×4 の、2〜4 段目の「右上」は、この MB の右上の 4 つ (上の MB の下の行) を使う
        for r in (4, 8, 12):
            buf[r][17:21] = top[16:20]
        m["pred4"] = []
        for b in range(16):
            bx, by = b % 4, b // 4
            cx, cy = 1 + 4 * bx, 1 + 4 * by
            t8 = buf[cy - 1][cx:cx + 8]
            lf = [buf[cy + i][cx - 1] for i in range(4)]
            P = pred4(m["bmodes"][b], t8, lf, buf[cy - 1][cx - 1])
            m["pred4"].append(dict(top=t8, left=lf, X=buf[cy - 1][cx - 1], pred=P))
            r = idct4(deq[b])
            for y in range(4):
                for x in range(4):
                    buf[cy + y][cx + x] = clip255(P[y][x] + r[y][x])
                    PY[y0 + 4 * by + y][x0 + 4 * bx + x] = P[y][x]
        for y in range(16):
            Y[y0 + y][x0:x0 + 16] = buf[1 + y][1:17]
    for ch, Pl in ((0, U), (1, V)):
        cx0, cy0 = mx * 8, my * 8
        top, left, X = _edges(Pl, cx0, cy0, 8, 0, ht, hl, W // 2)
        P = pred_big(m["uvmode"], top, left, X, 8, ht, hl)
        for b in range(4):
            bx, by = b % 2, b // 2
            r = idct4(deq[16 + 4 * ch + b])
            for y in range(4):
                for x in range(4):
                    Pl[cy0 + 4 * by + y][cx0 + 4 * bx + x] = clip255(P[4 * by + y][4 * bx + x] + r[y][x])


def filter_params(hdr, segment, is4):
    f = hdr["filter"]
    sg = hdr["segments"]
    level = f["level"]
    if sg["enabled"]:
        level = sg["f"][segment] + (0 if sg["absolute"] else f["level"])
    if f["use_delta"]:
        level += f["ref"][0]
        if is4:
            level += f["mode"][0]
    level = max(0, min(63, level))
    if level == 0:
        return None
    il = level
    if f["sharpness"] > 0:
        il >>= 2 if f["sharpness"] > 4 else 1
        il = min(il, 9 - f["sharpness"])
    il = max(il, 1)
    return dict(level=level, ilevel=il, limit=2 * level + il, hev=2 if level >= 40 else 1 if level >= 15 else 0)


def _loop_filter(hdr, mbs, Y, U, V):
    """ブロックの境目をなだらかにする。MB の順に、左の境目 → 中の縦の境目 → 上の境目 → 中の横の境目"""
    ftype = hdr["filter"]["type"]
    for my, row in enumerate(mbs):
        for mx, m in enumerate(row):
            fp = filter_params(hdr, m["segment"], m["ymode"] == B_PRED)
            if fp is None:
                continue
            inner = (m["ymode"] == B_PRED) or m["has_coeffs"]
            m["filter"] = dict(fp, inner=inner)
            lim, il, hev = fp["limit"], fp["ilevel"], fp["hev"]
            planes = [(Y, 16, mx * 16, my * 16)]
            if ftype == 2:
                planes += [(U, 8, mx * 8, my * 8), (V, 8, mx * 8, my * 8)]
            kind_mb = "simple" if ftype == 1 else "mb"
            kind_in = "simple" if ftype == 1 else "inner"
            # 左の境目と中の縦の境目 (横方向に並んだ画素をなだらかに)
            for P, n, x0, y0 in planes:
                inner_x = [4, 8, 12] if n == 16 else [4]
                for y in range(y0, y0 + n):
                    rowp = P[y]
                    if mx > 0:
                        _filter_line(rowp, x0, 1, kind_mb, 2 * (lim + 4) + 1, il, hev)
                    if inner:
                        for ix in inner_x:
                            _filter_line(rowp, x0 + ix, 1, kind_in, 2 * lim + 1, il, hev)
            # 上の境目と中の横の境目
            for P, n, x0, y0 in planes:
                inner_y = [4, 8, 12] if n == 16 else [4]
                for x in range(x0, x0 + n):
                    col = [P[y][x] for y in range(max(0, y0 - 4), y0 + n)]
                    off = y0 - max(0, y0 - 4)
                    if my > 0:
                        _filter_line(col, off, 1, kind_mb, 2 * (lim + 4) + 1, il, hev)
                    if inner:
                        for iy in inner_y:
                            _filter_line(col, off + iy, 1, kind_in, 2 * lim + 1, il, hev)
                    for i, v in enumerate(col):
                        P[max(0, y0 - 4) + i][x] = v
