"""自前の HEVC (H.265) 復号器。HEIC の写真 1 枚 (イントラだけ・Main / Main Still Picture・4:2:0・8 ビット) を読む。

ITU-T H.265 の 7 章 (文法)・8 章 (復号)・9 章 (CABAC) のうち、x265 (libheif) が写真 1 枚に使う道具だけ：
CTB の四分木、35 通りの予想 (MPM)、4〜32 の変換 (4×4 の明るさは DST)、CABAC、
符号の隠し (sign data hiding)、cu_qp_delta、WPP (行ごとの文脈の引き継ぎ)、デブロッキング、SAO。

    uv run python videos/heic/tools/hevc.py videos/heic/data/cat_q45.heic     # 復号して ffmpeg と比べる

画面に出すための記録 (CU・TU・予想・係数・SAO・CABAC の判定の列) も残す。
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hevctables as T  # noqa: E402

PLANAR, DC, HOR, VER = 0, 1, 10, 26


# ---------------------------------------------------------------- ビット列

def unescape(raw):
    """NAL の本体から 00 00 03 の 03 を除く。(rbsp, raw の位置 → rbsp の位置)"""
    out = bytearray()
    pos = []
    zeros = 0
    for i, c in enumerate(raw):
        pos.append(len(out))
        if zeros >= 2 and c == 3:
            zeros = 0
            continue
        out.append(c)
        zeros = zeros + 1 if c == 0 else 0
    pos.append(len(out))
    return bytes(out), pos


class Bits:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos   # ビットの位置

    def u(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.p >> 3] >> (7 - (self.p & 7))) & 1)
            self.p += 1
        return v

    def ue(self):
        z = 0
        while self.u(1) == 0:
            z += 1
        return (1 << z) - 1 + self.u(z)

    def se(self):
        k = self.ue()
        return (k + 1) // 2 if k & 1 else -(k // 2)


def profile_tier_level(b, max_sub_layers_minus1):
    b.u(8)
    b.u(32)
    b.u(48)
    b.u(8)   # general_level_idc
    assert max_sub_layers_minus1 == 0


def parse_sps(rbsp):
    b = Bits(rbsp, 16)
    s = {}
    b.u(4)
    msl = b.u(3)
    b.u(1)
    profile_tier_level(b, msl)
    s["id"] = b.ue()
    s["chroma_format_idc"] = b.ue()
    assert s["chroma_format_idc"] in (0, 1), "4:2:0 と明るさだけ (4:0:0、透明の画像) に対応"
    s["width"], s["height"] = b.ue(), b.ue()
    s["conf"] = (0, 0, 0, 0)
    if b.u(1):
        s["conf"] = (b.ue(), b.ue(), b.ue(), b.ue())   # 左・右・上・下 (4:2:0 は明るさの 2 画素、4:0:0 は 1 画素が単位)
    s["bit_depth"] = b.ue() + 8
    assert b.ue() + 8 == s["bit_depth"] == 8
    s["log2_max_poc_lsb"] = b.ue() + 4
    sub = b.u(1)
    for _ in range(0 if sub else msl, msl + 1):
        b.ue(), b.ue(), b.ue()
    s["log2_min_cb"] = b.ue() + 3
    s["log2_ctb"] = s["log2_min_cb"] + b.ue()
    s["log2_min_tb"] = b.ue() + 2
    s["log2_max_tb"] = s["log2_min_tb"] + b.ue()
    s["max_th_depth_inter"] = b.ue()
    s["max_th_depth_intra"] = b.ue()
    assert b.u(1) == 0, "scaling_list"
    s["amp"] = b.u(1)
    s["sao"] = b.u(1)
    assert b.u(1) == 0, "pcm"
    nst = b.ue()
    assert nst == 0
    assert b.u(1) == 0, "long_term_ref_pics"
    s["temporal_mvp"] = b.u(1)
    s["strong_intra_smoothing"] = b.u(1)
    return s


def parse_pps(rbsp):
    b = Bits(rbsp, 16)
    p = {}
    p["id"] = b.ue()
    p["sps_id"] = b.ue()
    p["dependent_slices"] = b.u(1)
    p["output_flag_present"] = b.u(1)
    p["num_extra_bits"] = b.u(3)
    p["sign_data_hiding"] = b.u(1)
    p["cabac_init_present"] = b.u(1)
    b.ue(), b.ue()
    p["init_qp"] = 26 + b.se()
    p["constrained_intra_pred"] = b.u(1)
    assert p["constrained_intra_pred"] == 0
    p["transform_skip"] = b.u(1)
    p["cu_qp_delta"] = b.u(1)
    p["diff_cu_qp_delta_depth"] = b.ue() if p["cu_qp_delta"] else 0
    p["cb_qp_offset"], p["cr_qp_offset"] = b.se(), b.se()
    p["slice_chroma_qp_offsets_present"] = b.u(1)
    b.u(1), b.u(1)   # weighted
    p["transquant_bypass"] = b.u(1)
    assert p["transquant_bypass"] == 0
    p["tiles"] = b.u(1)
    assert p["tiles"] == 0
    p["wpp"] = b.u(1)
    p["loop_filter_across_slices"] = b.u(1)
    p["deblocking_control"] = b.u(1)
    p["deblock_override"], p["deblock_disabled"], p["beta_offset"], p["tc_offset"] = 0, 0, 0, 0
    if p["deblocking_control"]:
        p["deblock_override"] = b.u(1)
        p["deblock_disabled"] = b.u(1)
        if not p["deblock_disabled"]:
            p["beta_offset"], p["tc_offset"] = b.se() * 2, b.se() * 2
    assert b.u(1) == 0, "pps scaling list"
    return p


def parse_slice_header(rbsp, nal_type, sps, pps):
    b = Bits(rbsp, 16)
    h = {}
    h["first"] = b.u(1)
    assert h["first"] == 1, "スライスは 1 つだけ"
    if 16 <= nal_type <= 23:
        b.u(1)
    assert b.ue() == pps["id"]
    b.u(pps["num_extra_bits"])
    h["type"] = b.ue()
    assert h["type"] == 2, "I スライスだけ"
    if pps["output_flag_present"]:
        b.u(1)
    assert nal_type in (19, 20), "IDR だけ"
    h["sao_luma"] = h["sao_chroma"] = 0
    if sps["sao"]:
        h["sao_luma"] = b.u(1)
        if sps["chroma_format_idc"]:
            h["sao_chroma"] = b.u(1)
    h["qp_delta"] = b.se()
    h["qp"] = pps["init_qp"] + h["qp_delta"]
    h["cb_qp_offset"] = h["cr_qp_offset"] = 0
    if pps["slice_chroma_qp_offsets_present"]:
        h["cb_qp_offset"], h["cr_qp_offset"] = b.se(), b.se()
    h["deblock_disabled"], h["beta_offset"], h["tc_offset"] = pps["deblock_disabled"], pps["beta_offset"], pps["tc_offset"]
    if pps["deblock_override"] and b.u(1):
        h["deblock_disabled"] = b.u(1)
        if not h["deblock_disabled"]:
            h["beta_offset"], h["tc_offset"] = b.se() * 2, b.se() * 2
    if pps["loop_filter_across_slices"] and (h["sao_luma"] or h["sao_chroma"] or not h["deblock_disabled"]):
        b.u(1)
    h["entry_points"] = []
    if pps["tiles"] or pps["wpp"]:
        n = b.ue()
        if n:
            ln = b.ue() + 1
            h["entry_points"] = [b.u(ln) + 1 for _ in range(n)]
    # byte_alignment()
    assert b.u(1) == 1
    while b.p & 7:
        assert b.u(1) == 0
    h["data_pos"] = b.p >> 3
    return h


# ---------------------------------------------------------------- CABAC

class Ctx:
    """文脈 1 つ：状態 (0〜62。大きいほど MPS が出やすい) と MPS (出やすいほうの値)"""
    __slots__ = ("state", "mps", "name", "idx")

    def __init__(self, name, idx, init, qp):
        self.name, self.idx = name, idx
        m = (init >> 4) * 5 - 45
        n = ((init & 15) << 3) - 16
        pre = max(1, min(126, ((m * max(0, min(51, qp))) >> 4) + n))
        self.mps = 1 if pre > 63 else 0
        self.state = pre - 64 if self.mps else 63 - pre

    def p_lps(self):
        """LPS (出にくいほう) の確率のおおよそ (RANGE_LPS の平均 / 幅の平均)"""
        return 0.5 * (0.949217 ** self.state)


class Cabac:
    def __init__(self, data, start, log):
        self.d = data
        self.bp = start * 8
        self.range = 510
        self.offset = self.read(9)
        self.log = log        # 判定の記録 (None なら残さない)
        self.label = ""

    def read(self, n):
        v = 0
        d = self.d
        for _ in range(n):
            byte = self.bp >> 3
            bit = (d[byte] >> (7 - (self.bp & 7))) & 1 if byte < len(d) else 0
            v = (v << 1) | bit
            self.bp += 1
        return v

    def decision(self, c):
        st, mps = c.state, c.mps
        rng0 = self.range
        lps = T.RANGE_LPS[st][(self.range >> 6) & 3]
        self.range -= lps
        if self.offset >= self.range:
            b = 1 - mps
            self.offset -= self.range
            self.range = lps
            if st == 0:
                c.mps = 1 - mps
            c.state = T.TRANS_LPS[st]
        else:
            b = mps
            if st < 62:
                c.state = st + 1
        while self.range < 256:
            self.range <<= 1
            self.offset = (self.offset << 1) | self.read(1)
        if self.log is not None:
            self.log.append((self.label, c.name, c.idx, st, mps, b, rng0, self.bp))
        return b

    def bypass(self):
        self.offset = (self.offset << 1) | self.read(1)
        if self.offset >= self.range:
            self.offset -= self.range
            b = 1
        else:
            b = 0
        if self.log is not None:
            self.log.append((self.label, "bypass", 0, -1, -1, b, self.range, self.bp))
        return b

    def bypass_bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bypass()
        return v

    def terminate(self):
        self.range -= 2
        if self.offset >= self.range:
            b = 1
        else:
            b = 0
            while self.range < 256:
                self.range <<= 1
                self.offset = (self.offset << 1) | self.read(1)
        if self.log is not None:
            self.log.append((self.label, "terminate", 0, -1, -1, b, self.range, self.bp))
        return b


def new_contexts(qp):
    return {name: [Ctx(name, i, v, qp) for i, v in enumerate(vals)] for name, vals in T.INIT.items()}


def copy_contexts(ctx):
    out = {}
    for name, lst in ctx.items():
        out[name] = []
        for c in lst:
            d = Ctx.__new__(Ctx)
            d.name, d.idx, d.state, d.mps = c.name, c.idx, c.state, c.mps
            out[name].append(d)
    return out


# ---------------------------------------------------------------- 走査の順

def scan_order(log2, idx):
    """2^log2 角の中の走査の順 [(x, y)]。idx 0：右上へななめ、1：横、2：縦"""
    n = 1 << log2
    if idx == 0:
        out = []
        x = y = 0
        while len(out) < n * n:
            while y >= 0:
                if x < n and y < n:
                    out.append((x, y))
                y -= 1
                x += 1
            y = x
            x = 0
        return out
    if idx == 1:
        return [(x, y) for y in range(n) for x in range(n)]
    return [(x, y) for x in range(n) for y in range(n)]


SCANS = {(l, i): scan_order(l, i) for l in range(0, 4) for i in range(3)}
CTX_IDX_MAP_4x4 = [0, 1, 4, 5, 2, 3, 4, 5, 6, 6, 8, 8, 7, 7, 8]


def chroma_qp(qpi):
    if qpi < 30:
        return qpi
    if qpi > 43:
        return qpi - 6
    return T.QPC_TABLE[qpi - 30]


def tr_matrix(n):
    step = 32 // n
    return np.array([T.DCT32[k * step][:n] for k in range(n)], np.int64)


MATS = {n: tr_matrix(n) for n in (4, 8, 16, 32)}
DST = np.array(T.DST4, np.int64)


def inverse_transform(coef, dst=False, bit_depth=8):
    n = coef.shape[0]
    M = DST if dst else MATS[n]
    c = coef.astype(np.int64)
    # 縦 (列ごと) → 横 (行ごと)
    e = M.T @ c                                  # e[y][x] = Σ_k c[k][x] M[k][y]
    g = np.clip((e + 64) >> 7, -32768, 32767)
    r = g @ M                                    # r[y][x] = Σ_k g[y][k] M[k][x]
    sh = 20 - bit_depth
    return ((r + (1 << (sh - 1))) >> sh).astype(np.int32)


# ---------------------------------------------------------------- 復号器

class Decoder:
    def __init__(self, nals, keep_log=True):
        self.keep_log = keep_log
        for typ, pos, d in nals:
            rb, _ = unescape(d)
            if typ == 33:
                self.sps = parse_sps(rb)
            elif typ == 34:
                self.pps = parse_pps(rb)
            elif typ in (19, 20):
                self.slice_nal = (typ, pos, d)
        s = self.sps
        self.W, self.H = s["width"], s["height"]
        self.chroma = s["chroma_format_idc"] != 0
        self.ctb = 1 << s["log2_ctb"]
        self.wctb = -(-self.W // self.ctb)
        self.hctb = -(-self.H // self.ctb)
        W, H = self.W, self.H
        self.planes = [np.zeros((H, W), np.int32), np.zeros((H // 2, W // 2), np.int32), np.zeros((H // 2, W // 2), np.int32)]
        self.pred = [np.zeros_like(p) for p in self.planes]       # 予想だけ
        self.resid = [np.zeros_like(p) for p in self.planes]      # 差だけ
        self.done = [np.zeros(p.shape, bool) for p in self.planes]
        n4w, n4h = W // 4, H // 4
        self.mode_y = np.full((n4h, n4w), -1, np.int32)        # 4×4 ごとの明るさの予想の向き
        self.depth = np.zeros((n4h, n4w), np.int32)            # CU の深さ
        self.qp_y = np.zeros((n4h, n4w), np.int32)             # CU の QpY
        self.tu_edge_v = np.zeros((n4h, n4w + 1), bool)        # 4×4 の左の辺が TU の境目か
        self.tu_edge_h = np.zeros((n4h + 1, n4w), bool)
        self.cus, self.tus, self.sao, self.splits = [], [], {}, []
        self.log = [] if keep_log else None
        self.min_qg = s["log2_ctb"] - self.pps["diff_cu_qp_delta_depth"]

    # -------------------------------------------------------- スライス

    def decode(self):
        typ, pos, raw = self.slice_nal
        rb, rawpos = unescape(raw)
        h = self.h = parse_slice_header(rb, typ, self.sps, self.pps)
        # 小さな流れ (substream) の先頭。entry point は raw (03 を含む) のバイト数
        raw_start = rawpos.index(h["data_pos"])
        starts = [raw_start]
        for e in h["entry_points"]:
            starts.append(starts[-1] + e)
        self.sub_starts = [rawpos[s] for s in starts]
        self.data = rb
        self.slice_byte = h["data_pos"]
        ctx = new_contexts(h["qp"])
        self.ctx = ctx
        stored = None
        sub = 0
        self.cab = Cabac(rb, self.sub_starts[0], self.log)
        self.last_qpy = h["qp"]
        self.ctb_bits = {}
        for ry in range(self.hctb):
            for rx in range(self.wctb):
                if rx == 0 and ry > 0 and self.pps["wpp"]:
                    sub += 1
                    self.cab = Cabac(rb, self.sub_starts[sub], self.log)
                    self.ctx = ctx = copy_contexts(stored) if stored is not None else new_contexts(h["qp"])
                b0 = self.cab.bp
                self.ctb_xy = (rx, ry)
                self.decode_ctu(rx, ry)
                self.cab.label = "end_of_slice_segment_flag"
                end = self.cab.terminate()
                if self.pps["wpp"] and rx == 1:
                    stored = copy_contexts(self.ctx)
                self.ctb_bits[(rx, ry)] = (b0, self.cab.bp)
                if end:
                    assert rx == self.wctb - 1 and ry == self.hctb - 1
                elif self.pps["wpp"] and rx == self.wctb - 1:
                    self.cab.label = "end_of_subset_one_bit"
                    assert self.cab.terminate() == 1
        self.recon = [p.copy() for p in self.planes]
        self.deblocked = self.deblock()
        self.final = self.apply_sao(self.deblocked)
        return self

    # -------------------------------------------------------- CTU

    def decode_ctu(self, rx, ry):
        x0, y0 = rx * self.ctb, ry * self.ctb
        if self.h["sao_luma"] or self.h["sao_chroma"]:
            self.parse_sao(rx, ry)
        self.coding_quadtree(x0, y0, self.sps["log2_ctb"], 0)

    def parse_sao(self, rx, ry):
        c, ctx = self.cab, self.ctx
        if rx > 0:
            c.label = "sao_merge_left_flag"
            if c.decision(ctx["sao_merge_flag"][0]):
                self.sao[(rx, ry)] = dict(self.sao[(rx - 1, ry)], merge="left")
                return
        if ry > 0:
            c.label = "sao_merge_up_flag"
            if c.decision(ctx["sao_merge_flag"][0]):
                self.sao[(rx, ry)] = dict(self.sao[(rx, ry - 1)], merge="up")
                return
        p = {"merge": None}
        for ci in range(3):
            if (ci == 0 and not self.h["sao_luma"]) or (ci > 0 and not self.h["sao_chroma"]):
                p[ci] = dict(type=0)
                continue
            if ci < 2:
                c.label = "sao_type_idx"
                t = 0
                if c.decision(ctx["sao_type_idx"][0]):
                    t = 2 if c.bypass() else 1
            else:
                t = p[1]["type"]
            if t == 0:
                p[ci] = dict(type=0)
                continue
            c.label = "sao_offset_abs"
            cmax = (1 << (min(self.sps["bit_depth"], 10) - 5)) - 1
            absv = []
            for _ in range(4):
                v = 0
                while v < cmax and c.bypass():
                    v += 1
                absv.append(v)
            if t == 1:
                c.label = "sao_offset_sign"
                off = [-a if a and c.bypass() else a for a in absv]
                c.label = "sao_band_position"
                band = c.bypass_bits(5)
                p[ci] = dict(type=1, offsets=off, band=band)
            else:
                off = [absv[0], absv[1], -absv[2], -absv[3]]
                if ci == 0:
                    c.label = "sao_eo_class"
                    cls = c.bypass_bits(2)
                elif ci == 1:
                    c.label = "sao_eo_class"
                    cls = c.bypass_bits(2)
                else:
                    cls = p[1]["eo_class"]
                p[ci] = dict(type=2, offsets=off, eo_class=cls)
        self.sao[(rx, ry)] = p

    def coding_quadtree(self, x0, y0, log2, depth):
        s, c = self.sps, self.cab
        size = 1 << log2
        if x0 + size <= self.W and y0 + size <= self.H and log2 > s["log2_min_cb"]:
            inc = 0
            if x0 > 0 and self.depth[y0 >> 2, (x0 - 1) >> 2] > depth:
                inc += 1
            if y0 > 0 and self.depth[(y0 - 1) >> 2, x0 >> 2] > depth:
                inc += 1
            c.label = "split_cu_flag"
            split = c.decision(self.ctx["split_coding_unit_flag"][inc])
        else:
            split = 1 if log2 > s["log2_min_cb"] else 0
        coded = x0 + size <= self.W and y0 + size <= self.H and log2 > s["log2_min_cb"]
        self.splits.append(dict(x=x0, y=y0, size=size, split=split, coded=coded))
        if self.pps["cu_qp_delta"] and log2 >= self.min_qg:
            self.start_qg(x0, y0)
        if split:
            h = size >> 1
            for dy in (0, h):
                for dx in (0, h):
                    if x0 + dx < self.W and y0 + dy < self.H:
                        self.coding_quadtree(x0 + dx, y0 + dy, log2 - 1, depth + 1)
        else:
            self.coding_unit(x0, y0, log2, depth)

    def start_qg(self, x0, y0):
        self.cu_qp_delta_coded = False
        self.cu_qp_delta = 0
        # スライスの最初の QG と、WPP のときは CTB の行の最初の QG は、スライスの QP から
        if (x0 == 0 and y0 == 0) or (self.pps["wpp"] and x0 == 0 and y0 % self.ctb == 0):
            prev = self.h["qp"]
        else:
            prev = self.last_qpy
        self.qg = (x0, y0, prev)

    def qp_pred(self):
        xq, yq, prev = self.qg
        ctb = self.ctb
        a = prev
        if xq > 0 and (xq - 1) // ctb == xq // ctb:
            a = int(self.qp_y[yq >> 2, (xq - 1) >> 2])
        b = prev
        if yq > 0 and (yq - 1) // ctb == yq // ctb:
            b = int(self.qp_y[(yq - 1) >> 2, xq >> 2])
        return (a + b + 1) >> 1

    def cur_qpy(self):
        if not self.pps["cu_qp_delta"]:
            return self.h["qp"]
        return ((self.qp_pred() + self.cu_qp_delta + 52) % 52)

    def coding_unit(self, x0, y0, log2, depth):
        s, c, ctx = self.sps, self.cab, self.ctx
        size = 1 << log2
        part_nxn = 0
        if log2 == s["log2_min_cb"]:
            c.label = "part_mode"
            part_nxn = 1 - c.decision(ctx["part_mode"][0])
        cu = dict(x=x0, y=y0, size=size, depth=depth, nxn=part_nxn, pus=[])
        self.depth[y0 >> 2:(y0 + size) >> 2, x0 >> 2:(x0 + size) >> 2] = depth
        # この CU のあいだの QpY (差が後で来ても、TU の前に決まる)
        self.cur_cu = cu
        cu["qp"] = self.cur_qpy()
        self.qp_y[y0 >> 2:(y0 + size) >> 2, x0 >> 2:(x0 + size) >> 2] = cu["qp"]
        nb = 4 if part_nxn else 1
        pb = size >> part_nxn
        c.label = "prev_intra_luma_pred_flag"
        flags = [c.decision(ctx["prev_intra_luma_pred_flag"][0]) for _ in range(nb)]
        for k in range(nb):
            xp, yp = x0 + (k & 1) * pb, y0 + (k >> 1) * pb
            cand = self.mpm_cands(xp, yp)
            pu = dict(x=xp, y=yp, size=pb, cand=cand, mpm=flags[k])
            if flags[k]:
                c.label = "mpm_idx"
                i = 0
                while i < 2 and c.bypass():
                    i += 1
                mode = cand[i]
                pu["mpm_idx"] = i
            else:
                c.label = "rem_intra_luma_pred_mode"
                rem = c.bypass_bits(5)
                pu["rem"] = rem
                mode = rem
                for cv in sorted(cand):
                    if mode >= cv:
                        mode += 1
            pu["mode"] = mode
            self.mode_y[yp >> 2:(yp + pb) >> 2, xp >> 2:(xp + pb) >> 2] = mode
            cu["pus"].append(pu)
        if not self.chroma:
            cm = 4
        else:
            c.label = "intra_chroma_pred_mode"
            if not c.decision(ctx["intra_chroma_pred_mode"][0]):
                cm = 4
            else:
                cm = c.bypass_bits(2)
        ly = cu["pus"][0]["mode"]
        if cm == 4:
            mc = ly
        else:
            mc = [PLANAR, VER, HOR, DC][cm]
            if mc == ly:
                mc = 34
        cu["chroma_mode_idx"], cu["chroma_mode"] = cm, mc
        self.cus.append(cu)
        max_depth = s["max_th_depth_intra"] + part_nxn
        self.cbf_c = {}
        self.transform_tree(x0, y0, x0, y0, log2, 0, 0, max_depth, part_nxn, cu)
        # 差が来なかった CU も、同じ QG の値で QpY を確定
        cu["qp"] = self.cur_qpy()
        self.qp_y[y0 >> 2:(y0 + size) >> 2, x0 >> 2:(x0 + size) >> 2] = cu["qp"]
        self.last_qpy = cu["qp"]

    def mpm_cands(self, xp, yp):
        def nb(x, y):
            if x < 0 or y < 0:
                return DC
            m = int(self.mode_y[y >> 2, x >> 2])
            return DC if m < 0 else m
        a = nb(xp - 1, yp)
        b = DC if yp - 1 < ((yp >> self.sps["log2_ctb"]) << self.sps["log2_ctb"]) else nb(xp, yp - 1)
        if a == b:
            if a < 2:
                return [PLANAR, DC, VER]
            return [a, 2 + ((a + 29) % 32), 2 + ((a - 2 + 1) % 32)]
        if PLANAR not in (a, b):
            cc = PLANAR
        elif DC not in (a, b):
            cc = DC
        else:
            cc = VER
        return [a, b, cc]

    def transform_tree(self, x0, y0, xb, yb, log2, td, blk, max_depth, nxn, cu):
        s, c, ctx = self.sps, self.cab, self.ctx
        if log2 <= s["log2_max_tb"] and log2 > s["log2_min_tb"] and td < max_depth and not (nxn and td == 0):
            c.label = "split_transform_flag"
            split = c.decision(ctx["split_transform_flag"][5 - log2])
        else:
            split = 1 if (log2 > s["log2_max_tb"] or (nxn and td == 0)) else 0
        cb = cr = 0
        if not self.chroma:
            pass
        elif log2 > 2:
            if td == 0 or self.cbf_c[(xb, yb, td - 1)][0]:
                c.label = "cbf_cb"
                cb = c.decision(ctx["cbf_cb_cr"][td])
            if td == 0 or self.cbf_c[(xb, yb, td - 1)][1]:
                c.label = "cbf_cr"
                cr = c.decision(ctx["cbf_cb_cr"][td])
        else:
            cb, cr = self.cbf_c[(xb, yb, td - 1)]   # 4×4 のときは親の値 (色は blkIdx 3 でまとめて)
        self.cbf_c[(x0, y0, td)] = (cb, cr)
        if split:
            h = 1 << (log2 - 1)
            for k, (dx, dy) in enumerate(((0, 0), (h, 0), (0, h), (h, h))):
                self.transform_tree(x0 + dx, y0 + dy, x0, y0, log2 - 1, td + 1, k, max_depth, nxn, cu)
            return
        c.label = "cbf_luma"
        cbf_l = c.decision(ctx["cbf_luma"][1 if td == 0 else 0])
        self.transform_unit(x0, y0, xb, yb, log2, td, blk, cbf_l, cb, cr, cu)

    def transform_unit(self, x0, y0, xb, yb, log2, td, blk, cbf_l, cb, cr, cu):
        c, ctx = self.cab, self.ctx
        size = 1 << log2
        # TU の境目 (デブロッキング用)
        self.tu_edge_v[y0 >> 2:(y0 + size) >> 2, x0 >> 2] = True
        self.tu_edge_v[y0 >> 2:(y0 + size) >> 2, (x0 + size) >> 2] = True
        self.tu_edge_h[y0 >> 2, x0 >> 2:(x0 + size) >> 2] = True
        self.tu_edge_h[(y0 + size) >> 2, x0 >> 2:(x0 + size) >> 2] = True
        chroma_here = log2 > 2 and self.chroma
        if (cbf_l or cb or cr) and self.pps["cu_qp_delta"] and not self.cu_qp_delta_coded:
            c.label = "cu_qp_delta_abs"
            v = 0
            while v < 5 and c.decision(ctx["cu_qp_delta"][0 if v == 0 else 1]):
                v += 1
            if v == 5:
                k = 0
                while c.bypass():
                    v += 1 << k
                    k += 1
                v += c.bypass_bits(k)
            if v:
                c.label = "cu_qp_delta_sign_flag"
                if c.bypass():
                    v = -v
            self.cu_qp_delta = v
            self.cu_qp_delta_coded = True
            cu["qp"] = self.cur_qpy()
            x, y, sz = cu["x"], cu["y"], cu["size"]
            self.qp_y[y >> 2:(y + sz) >> 2, x >> 2:(x + sz) >> 2] = cu["qp"]
        qp = cu["qp"]
        mode = int(self.mode_y[y0 >> 2, x0 >> 2])
        tu = dict(x=x0, y=y0, size=size, mode=mode, cbf=cbf_l, qp=qp)
        self.tus.append(tu)
        self.reconstruct(0, x0, y0, log2, mode, cbf_l, qp, tu)
        if chroma_here:
            for ci, f in ((1, cb), (2, cr)):
                self.reconstruct(ci, x0 // 2, y0 // 2, log2 - 1, cu["chroma_mode"], f, qp, tu)
        elif blk == 3 and self.chroma:
            for ci, f in ((1, cb), (2, cr)):
                self.reconstruct(ci, xb // 2, yb // 2, 2, cu["chroma_mode"], f, qp, tu)

    def reconstruct(self, ci, x0, y0, log2, mode, cbf, qpy, tu):
        n = 1 << log2
        pred = self.intra_pred(ci, x0, y0, n, mode)
        self.pred[ci][y0:y0 + n, x0:x0 + n] = pred
        res = np.zeros((n, n), np.int32)
        if cbf:
            if ci == 0:
                qp = qpy
            else:
                off = self.pps["cb_qp_offset" if ci == 1 else "cr_qp_offset"] + self.h["cb_qp_offset" if ci == 1 else "cr_qp_offset"]
                qp = chroma_qp(max(0, min(57, qpy + off)))
            levels = self.residual_coding(log2, ci, mode)
            sc = T.LEVEL_SCALE[qp % 6] << (qp // 6)
            bd = self.sps["bit_depth"] + log2 - 5
            coef = np.clip((levels.astype(np.int64) * 16 * sc + (1 << (bd - 1))) >> bd, -32768, 32767)
            res = inverse_transform(coef, dst=(ci == 0 and n == 4), bit_depth=self.sps["bit_depth"])
            tu.setdefault("levels", {})[ci] = levels
            tu.setdefault("qp_c", {})[ci] = qp
        self.resid[ci][y0:y0 + n, x0:x0 + n] = res
        self.planes[ci][y0:y0 + n, x0:x0 + n] = np.clip(pred + res, 0, 255)
        self.done[ci][y0:y0 + n, x0:x0 + n] = True

    # -------------------------------------------------------- 係数

    def residual_coding(self, log2, ci, pred_mode):
        c, ctx = self.cab, self.ctx
        n = 1 << log2
        if log2 == 2 or (log2 == 3 and ci == 0):
            scan_idx = 2 if 6 <= pred_mode <= 14 else 1 if 22 <= pred_mode <= 30 else 0
        else:
            scan_idx = 0
        # 最後の 0 でない係数の位置
        if ci == 0:
            off, shift = 3 * (log2 - 2) + ((log2 - 1) >> 2), (log2 + 1) >> 2
        else:
            off, shift = 15, log2 - 2
        mx = (log2 << 1) - 1
        pre = []
        for nm in ("last_significant_coeff_x_prefix", "last_significant_coeff_y_prefix"):
            c.label = nm
            i = 0
            while i < mx and c.decision(ctx[nm][off + (i >> shift)]):
                i += 1
            pre.append(i)
        last = []
        for p in pre:
            if p > 3:
                c.label = "last_significant_coeff_suffix"
                ln = (p >> 1) - 1
                suf = c.bypass_bits(ln)
                last.append((1 << ln) * (2 + (p & 1)) + suf)
            else:
                last.append(p)
        lx, ly = last
        if scan_idx == 2:
            lx, ly = ly, lx
        levels = np.zeros((n, n), np.int32)
        sub = SCANS[(log2 - 2, scan_idx)]
        sc = SCANS[(2, scan_idx)]
        nsb = 1 << (log2 - 2)
        last_sb = next(i for i, (xs, ys) in enumerate(sub) if xs == lx >> 2 and ys == ly >> 2)
        last_pos = next(i for i, (xp, yp) in enumerate(sc) if xp == lx & 3 and yp == ly & 3)
        csbf = np.zeros((nsb, nsb), np.int32)
        greater1_ctx = 1
        for i in range(last_sb, -1, -1):
            xs, ys = sub[i]
            infer_dc = False
            if i < last_sb and i > 0:
                cc = 0
                if xs < nsb - 1:
                    cc += csbf[ys, xs + 1]
                if ys < nsb - 1:
                    cc += csbf[ys + 1, xs]
                c.label = "coded_sub_block_flag"
                csbf[ys, xs] = c.decision(ctx["significant_coeff_group_flag"][min(cc, 1) + (2 if ci else 0)])
                infer_dc = True
            else:
                csbf[ys, xs] = 1
            prev = 0
            if xs < nsb - 1:
                prev += csbf[ys, xs + 1]
            if ys < nsb - 1:
                prev += csbf[ys + 1, xs] << 1
            sig = []
            if i == last_sb:
                start = last_pos - 1
                sig.append(last_pos)
            else:
                start = 15
            if csbf[ys, xs]:
                c.label = "sig_coeff_flag"
                for k in range(start, -1, -1):
                    xp, yp = sc[k]
                    xc, yc = (xs << 2) + xp, (ys << 2) + yp
                    if k == 0 and infer_dc:
                        sig.append(0)
                        break
                    if log2 == 2:
                        sctx = CTX_IDX_MAP_4x4[(yc << 2) + xc]
                    elif xc + yc == 0:
                        sctx = 0
                    else:
                        if prev == 0:
                            sctx = 2 if xp + yp == 0 else 1 if xp + yp < 3 else 0
                        elif prev == 1:
                            sctx = 2 if yp == 0 else 1 if yp == 1 else 0
                        elif prev == 2:
                            sctx = 2 if xp == 0 else 1 if xp == 1 else 0
                        else:
                            sctx = 2
                        if ci == 0:
                            if xs or ys:
                                sctx += 3
                            sctx += (9 if scan_idx == 0 else 15) if log2 == 3 else 21
                        else:
                            sctx += 9 if log2 == 3 else 12
                    if ci:
                        sctx += 27
                    if c.decision(ctx["significant_coeff_flag"][sctx]):
                        sig.append(k)
                        infer_dc = False
            if not sig:
                continue
            ctx_set = 0 if (i == 0 or ci > 0) else 2
            if i != last_sb and greater1_ctx == 0:
                ctx_set += 1
            greater1_ctx = 1
            g1 = []
            first_g1 = -1
            c.label = "coeff_abs_level_greater1_flag"
            for m in range(min(8, len(sig))):
                f = c.decision(ctx["coeff_abs_level_greater1_flag"][ctx_set * 4 + greater1_ctx + (16 if ci else 0)])
                g1.append(f)
                if f:
                    greater1_ctx = 0
                    if first_g1 < 0:
                        first_g1 = m
                elif 0 < greater1_ctx < 3:
                    greater1_ctx += 1
            if first_g1 >= 0:
                c.label = "coeff_abs_level_greater2_flag"
                g1[first_g1] += c.decision(ctx["coeff_abs_level_greater2_flag"][ctx_set + (4 if ci else 0)])
            hidden = self.pps["sign_data_hiding"] and (sig[0] - sig[-1] >= 4)
            c.label = "coeff_sign_flag"
            nsign = len(sig) - (1 if hidden else 0)
            signs = [c.bypass() for _ in range(nsign)] + [0] * (len(sig) - nsign)
            rice = 0
            total = 0
            c.label = "coeff_abs_level_remaining"
            for m, k in enumerate(sig):
                if m < 8:
                    base = 1 + g1[m]
                    need = base == (3 if m == first_g1 else 2)
                else:
                    base, need = 1, True
                lv = base
                if need:
                    pfx = 0
                    while c.bypass():
                        pfx += 1
                    if pfx <= 3:
                        rem = (pfx << rice) + c.bypass_bits(rice)
                    else:
                        rem = (((1 << (pfx - 3)) + 2) << rice) + c.bypass_bits(pfx - 3 + rice)
                    lv = base + rem
                    if lv > 3 * (1 << rice):
                        rice = min(rice + 1, 4)
                total += lv
                if signs[m]:
                    lv = -lv
                if hidden and k == sig[-1] and total & 1:
                    lv = -lv
                xp, yp = sc[k]
                levels[(ys << 2) + yp, (xs << 2) + xp] = lv
        return levels

    # -------------------------------------------------------- 予想

    def ref_samples(self, ci, x0, y0, n):
        """まわりの点 (左の列は下から上、左上、上の行は左から右の順に 4n+1 個) と、使えたかどうか"""
        P, D = self.planes[ci], self.done[ci]
        h, w = P.shape
        coords = [(x0 - 1, y0 + 2 * n - 1 - k) for k in range(2 * n)] + [(x0 - 1, y0 - 1)] + [(x0 + k, y0 - 1) for k in range(2 * n)]
        vals, avail = [], []
        for x, y in coords:
            ok = 0 <= x < w and 0 <= y < h and D[y, x]
            avail.append(ok)
            vals.append(int(P[y, x]) if ok else 0)
        if not any(avail):
            vals = [1 << (self.sps["bit_depth"] - 1)] * len(vals)
        else:
            if not avail[0]:
                vals[0] = vals[avail.index(True)]
            for k in range(1, len(vals)):
                if not avail[k]:
                    vals[k] = vals[k - 1]
        return vals, avail

    def intra_pred(self, ci, x0, y0, n, mode, keep=None):
        vals, avail = self.ref_samples(ci, x0, y0, n)
        # left[k] = p[-1][k] (k = -1..2n-1)、top[k] = p[k][-1]
        corner = vals[2 * n]
        left = [corner] + vals[2 * n - 1::-1]     # left[0] は左上、left[1 + y] = p[-1][y]
        top = [corner] + vals[2 * n + 1:]          # top[1 + x] = p[x][-1]
        filt = False
        if ci == 0 and mode != DC and n != 4:
            dist = min(abs(mode - 26), abs(mode - 10))
            thr = {8: 7, 16: 1, 32: 0}[n]
            filt = dist > thr
        strong = False
        if filt:
            bd = self.sps["bit_depth"]
            if (self.sps["strong_intra_smoothing"] and ci == 0 and n == 32
                    and abs(corner + top[2 * n] - 2 * top[n]) < (1 << (bd - 5))
                    and abs(corner + left[2 * n] - 2 * left[n]) < (1 << (bd - 5))):
                strong = True
                nl = [corner] + [((63 - y) * corner + (y + 1) * left[64] + 32) >> 6 for y in range(63)] + [left[64]]
                nt = [corner] + [((63 - x) * corner + (x + 1) * top[64] + 32) >> 6 for x in range(63)] + [top[64]]
                left, top = nl, nt
            else:
                seq = left[:0:-1] + [corner] + top[1:]     # 下から上、左上、左から右
                f = [seq[0]] + [(seq[k - 1] + 2 * seq[k] + seq[k + 1] + 2) >> 2 for k in range(1, len(seq) - 1)] + [seq[-1]]
                m = 2 * n
                corner = f[m]
                left = [corner] + f[m - 1::-1]
                top = [corner] + f[m + 1:]
        if keep is not None:
            keep.update(left=left, top=top, filtered=filt, strong=strong, avail=avail)
        L = np.array(left, np.int64)
        Tp = np.array(top, np.int64)
        xs = np.arange(n)
        if mode == PLANAR:
            sh = n.bit_length()   # log2(n) + 1
            X, Y = np.meshgrid(xs, xs)
            pr = ((n - 1 - X) * L[1 + Y] + (X + 1) * Tp[1 + n] + (n - 1 - Y) * Tp[1 + X] + (Y + 1) * L[1 + n] + n) >> sh
        elif mode == DC:
            k = n.bit_length() - 1
            dc = (int(Tp[1:n + 1].sum()) + int(L[1:n + 1].sum()) + n) >> (k + 1)
            pr = np.full((n, n), dc, np.int64)
            if ci == 0 and n < 32:
                pr[0, 0] = (L[1] + 2 * dc + Tp[1] + 2) >> 2
                pr[0, 1:] = (Tp[2:n + 1] + 3 * dc + 2) >> 2
                pr[1:, 0] = (L[2:n + 1] + 3 * dc + 2) >> 2
        else:
            ang = T.INTRA_ANGLE[mode]
            if mode >= 18:
                main, side = Tp, L
            else:
                main, side = L, Tp
            ref = {}
            for x in range(0, n + 1):
                ref[x] = int(main[x])          # ref[x] = p[-1+x] の向き
            if ang < 0:
                if (n * ang) >> 5 < -1:
                    inv = T.INV_ANGLE[mode]
                    for x in range((n * ang) >> 5, 0):
                        ref[x] = int(side[((x * inv + 128) >> 8)])
            else:
                for x in range(n + 1, 2 * n + 1):
                    ref[x] = int(main[x])
            pr = np.zeros((n, n), np.int64)
            for j in range(n):        # mode>=18 なら j は行 (y)、そうでなければ列 (x)
                idx = ((j + 1) * ang) >> 5
                fact = ((j + 1) * ang) & 31
                line = np.array([((32 - fact) * ref[i + idx + 1] + fact * ref[i + idx + 2] + 16) >> 5 if fact else ref[i + idx + 1]
                                 for i in range(n)], np.int64)
                if mode >= 18:
                    pr[j, :] = line
                else:
                    pr[:, j] = line
            if ci == 0 and n < 32:
                if mode == VER:
                    pr[:, 0] = np.clip(Tp[1] + ((L[1:n + 1] - L[0]) >> 1), 0, 255)
                elif mode == HOR:
                    pr[0, :] = np.clip(L[1] + ((Tp[1:n + 1] - Tp[0]) >> 1), 0, 255)
        return pr.astype(np.int32)

    # -------------------------------------------------------- デブロッキング

    def deblock(self):
        out = [p.copy() for p in self.planes]
        if self.h["deblock_disabled"]:
            self.deblock_log = []
            return out
        self.deblock_log = []
        for vertical in (True, False):
            src = [p.copy() for p in out]
            self._deblock_dir(src, out, vertical)
        return out

    def _deblock_dir(self, src, out, vertical):
        H, W = self.H, self.W
        bo, to = self.h["beta_offset"], self.h["tc_offset"]
        Y, Yo = src[0], out[0]
        # 明るさ：8 の格子の TU の境目
        for e in range(8, W if vertical else H, 8):
            for s4 in range(0, (H if vertical else W) // 4):
                if vertical and not self.tu_edge_v[s4, e >> 2]:
                    continue
                if not vertical and not self.tu_edge_h[e >> 2, s4]:
                    continue
                if vertical:
                    qpq, qpp = self.qp_y[s4, e >> 2], self.qp_y[s4, (e >> 2) - 1]
                else:
                    qpq, qpp = self.qp_y[e >> 2, s4], self.qp_y[(e >> 2) - 1, s4]
                qpl = (int(qpq) + int(qpp) + 1) >> 1
                beta = T.BETA_TABLE[max(0, min(51, qpl + bo))]
                tc = T.TC_TABLE[max(0, min(53, qpl + 2 + to))]      # bS = 2 (イントラ)

                def line(k):
                    if vertical:
                        y = s4 * 4 + k
                        return [int(Y[y, e - 1 - i]) for i in range(4)], [int(Y[y, e + i]) for i in range(4)]
                    x = s4 * 4 + k
                    return [int(Y[e - 1 - i, x]) for i in range(4)], [int(Y[e + i, x]) for i in range(4)]

                def put(k, side, i, v):
                    if vertical:
                        y = s4 * 4 + k
                        Yo[y, e - 1 - i if side == 0 else e + i] = v
                    else:
                        x = s4 * 4 + k
                        Yo[e - 1 - i if side == 0 else e + i, x] = v
                P0, Q0 = line(0)
                P3, Q3 = line(3)
                dp0 = abs(P0[2] - 2 * P0[1] + P0[0])
                dp3 = abs(P3[2] - 2 * P3[1] + P3[0])
                dq0 = abs(Q0[2] - 2 * Q0[1] + Q0[0])
                dq3 = abs(Q3[2] - 2 * Q3[1] + Q3[0])
                d = dp0 + dq0 + dp3 + dq3
                rec = dict(vertical=vertical, e=e, s=s4 * 4, beta=beta, tc=tc, d=d, mode=0)
                self.deblock_log.append(rec)
                if d >= beta:
                    continue

                def dsam(P, Q, dpq):
                    return (2 * dpq < (beta >> 2) and abs(P[3] - P[0]) + abs(Q[0] - Q[3]) < (beta >> 3)
                            and abs(P[0] - Q[0]) < ((5 * tc + 1) >> 1))
                strong = dsam(P0, Q0, dp0 + dq0) and dsam(P3, Q3, dp3 + dq3)
                dep = (dp0 + dp3) < ((beta + (beta >> 1)) >> 3)
                deq = (dq0 + dq3) < ((beta + (beta >> 1)) >> 3)
                rec["mode"] = 2 if strong else 1
                for k in range(4):
                    P, Q = line(k)
                    p0, p1, p2, p3 = P
                    q0, q1, q2, q3 = Q
                    if strong:
                        c2 = 2 * tc
                        put(k, 0, 0, max(p0 - c2, min(p0 + c2, (p2 + 2 * p1 + 2 * p0 + 2 * q0 + q1 + 4) >> 3)))
                        put(k, 0, 1, max(p1 - c2, min(p1 + c2, (p2 + p1 + p0 + q0 + 2) >> 2)))
                        put(k, 0, 2, max(p2 - c2, min(p2 + c2, (2 * p3 + 3 * p2 + p1 + p0 + q0 + 4) >> 3)))
                        put(k, 1, 0, max(q0 - c2, min(q0 + c2, (p1 + 2 * p0 + 2 * q0 + 2 * q1 + q2 + 4) >> 3)))
                        put(k, 1, 1, max(q1 - c2, min(q1 + c2, (p0 + q0 + q1 + q2 + 2) >> 2)))
                        put(k, 1, 2, max(q2 - c2, min(q2 + c2, (p0 + q0 + q1 + 3 * q2 + 2 * q3 + 4) >> 3)))
                    else:
                        dl = (9 * (q0 - p0) - 3 * (q1 - p1) + 8) >> 4
                        if abs(dl) >= tc * 10:
                            continue
                        dl = max(-tc, min(tc, dl))
                        put(k, 0, 0, max(0, min(255, p0 + dl)))
                        put(k, 1, 0, max(0, min(255, q0 - dl)))
                        if dep:
                            dp = max(-(tc >> 1), min(tc >> 1, (((p2 + p0 + 1) >> 1) - p1 + dl) >> 1))
                            put(k, 0, 1, max(0, min(255, p1 + dp)))
                        if deq:
                            dq = max(-(tc >> 1), min(tc >> 1, (((q2 + q0 + 1) >> 1) - q1 - dl) >> 1))
                            put(k, 1, 1, max(0, min(255, q1 + dq)))
        # 色：色の 8 の格子 (明るさの 16) の TU の境目
        for ci in ((1, 2) if self.chroma else ()):
            C, Co = src[ci], out[ci]
            off = self.pps["cb_qp_offset" if ci == 1 else "cr_qp_offset"]
            for e in range(8, (W if vertical else H) // 2, 8):
                le = e * 2
                for s in range(0, (H if vertical else W) // 2):
                    sl = s * 2   # 明るさの位置
                    if vertical:
                        if not self.tu_edge_v[sl >> 2, le >> 2]:
                            continue
                        qpq, qpp = self.qp_y[sl >> 2, le >> 2], self.qp_y[sl >> 2, (le >> 2) - 1]
                    else:
                        if not self.tu_edge_h[le >> 2, sl >> 2]:
                            continue
                        qpq, qpp = self.qp_y[le >> 2, sl >> 2], self.qp_y[(le >> 2) - 1, sl >> 2]
                    qpc = chroma_qp(((int(qpq) + int(qpp) + 1) >> 1) + off)
                    tc = T.TC_TABLE[max(0, min(53, qpc + 2 + to))]
                    if vertical:
                        p1, p0, q0, q1 = (int(v) for v in C[s, e - 2:e + 2])
                    else:
                        p1, p0, q0, q1 = (int(v) for v in C[e - 2:e + 2, s])
                    dl = max(-tc, min(tc, ((((q0 - p0) << 2) + p1 - q1 + 4) >> 3)))
                    if vertical:
                        Co[s, e - 1], Co[s, e] = max(0, min(255, p0 + dl)), max(0, min(255, q0 - dl))
                    else:
                        Co[e - 1, s], Co[e, s] = max(0, min(255, p0 + dl)), max(0, min(255, q0 - dl))

    # -------------------------------------------------------- SAO

    EO = {0: ((-1, 0), (1, 0)), 1: ((0, -1), (0, 1)), 2: ((-1, -1), (1, 1)), 3: ((1, -1), (-1, 1))}

    def apply_sao(self, planes):
        out = [p.copy() for p in planes]
        self.sao_class = [np.zeros(p.shape, np.int32) for p in planes]   # 端の分類 (0〜4) か、帯の番号 + 1
        for (rx, ry), prm in self.sao.items():
            for ci in range(3):
                q = prm[ci]
                if q["type"] == 0:
                    continue
                sc = 1 if ci == 0 else 2
                n = self.ctb // sc
                P = planes[ci]
                h, w = P.shape
                x0, y0 = rx * n, ry * n
                x1, y1 = min(x0 + n, w), min(y0 + n, h)
                blk = P[y0:y1, x0:x1].astype(np.int64)
                if q["type"] == 1:
                    tab = np.zeros(32, np.int64)
                    cls = np.zeros(32, np.int64)
                    for k in range(4):
                        tab[(k + q["band"]) & 31] = q["offsets"][k]
                        cls[(k + q["band"]) & 31] = k + 1
                    b = blk >> 3
                    out[ci][y0:y1, x0:x1] = np.clip(blk + tab[b], 0, 255)
                    self.sao_class[ci][y0:y1, x0:x1] = cls[b]
                else:
                    (ax, ay), (bx, by) = self.EO[q["eo_class"]]
                    pad = np.pad(P.astype(np.int64), 1, mode="edge")
                    ys, xs = np.mgrid[y0:y1, x0:x1]
                    na = pad[ys + ay + 1, xs + ax + 1]
                    nb = pad[ys + by + 1, xs + bx + 1]
                    valid = ((xs + ax >= 0) & (xs + ax < w) & (ys + ay >= 0) & (ys + ay < h)
                             & (xs + bx >= 0) & (xs + bx < w) & (ys + by >= 0) & (ys + by < h))
                    e = 2 + np.sign(blk - na) + np.sign(blk - nb)
                    e = np.where(e == 2, 0, np.where(e < 2, e + 1, e))
                    e = np.where(valid, e, 0)
                    offs = np.array([0] + q["offsets"], np.int64)
                    out[ci][y0:y1, x0:x1] = np.clip(blk + offs[e], 0, 255)
                    self.sao_class[ci][y0:y1, x0:x1] = e
        return out

    # -------------------------------------------------------- 出力

    def cropped(self, planes=None):
        planes = planes or self.final
        l, r, t, b = self.sps["conf"]
        if not self.chroma:
            return planes[0][t:self.H - b, l:self.W - r], None, None
        Y = planes[0][2 * t:self.H - 2 * b, 2 * l:self.W - 2 * r]
        U = planes[1][t:self.H // 2 - b, l:self.W // 2 - r]
        V = planes[2][t:self.H // 2 - b, l:self.W // 2 - r]
        return Y, U, V


def decode_heic(path, keep_log=True):
    import heif
    r = heif.parse(path)
    d = Decoder(heif.item_nals(r), keep_log).decode()
    d.heif = r
    return d


def ffmpeg_yuv(path, w, h, extra=()):
    """ffmpeg で復号した Y・U・V (比べる用。範囲の変換をしないよう、ffmpeg の出す形のまま受け取る)"""
    import subprocess
    import tempfile
    import heif
    r = heif.parse(path)
    with tempfile.NamedTemporaryFile(suffix=".hevc") as f:
        f.write(heif.annexb(r))
        f.flush()
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", *extra, "-f", "hevc", "-i", f.name, "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    Y = np.frombuffer(raw[:w * h], np.uint8).reshape(h, w)
    U = np.frombuffer(raw[w * h:w * h + w * h // 4], np.uint8).reshape(h // 2, w // 2)
    V = np.frombuffer(raw[w * h + w * h // 4:], np.uint8).reshape(h // 2, w // 2)
    return Y, U, V


if __name__ == "__main__":
    import time
    t = time.time()
    d = decode_heic(sys.argv[1])
    print(f"復号 {time.time() - t:.1f} 秒, CU {len(d.cus)}, TU {len(d.tus)}, 判定 {len(d.log)}")
    mine = d.cropped()
    ref = ffmpeg_yuv(sys.argv[1], mine[0].shape[1], mine[0].shape[0])
    for name, a, b in zip("YUV", mine, ref):
        diff = np.abs(a.astype(int) - b.astype(int))
        print(name, a.shape, "一致" if diff.max() == 0 else f"ずれ 最大 {diff.max()}、{(diff > 0).sum()} 画素", )
