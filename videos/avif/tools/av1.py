"""自前の AV1 復号器 (イントラ・静止画だけ)。AVIF の写真 1 枚 (と透明度の項目) を読む。

AV1 Bitstream & Decoding Process Specification の 5 章 (文法)・7 章 (復号)・8 章 (算術符号) の、
KEY_FRAME / INTRA_ONLY_FRAME が使える道具すべて：区切り (10 通り、64 と 128 の超ブロック)、
方向つき予想 (角度の微調整・端のなめらか化・2 倍化)、DC・SMOOTH・PAETH・CfL・フィルタ予想・パレット、
セグメント・delta q / delta lf、変換の大きさと種類 (縮めた組を含む)、係数、量子化行列、
DCT/ADST/FLIPADST/恒等変換 (4〜64、長方形)、WHT (可逆)、デブロッキング、CDEF、超解像、
ループ復元 (Wiener・自己誘導)、フィルムグレイン、白黒 (透明度の項目)、8/10/12 ビット。
intrabc (画面内のコピー) は読むが、使われたら止める (assert)。インター (動き) のフレームは対象外。

    uv run python videos/avif/tools/av1.py videos/avif/data/cat_q60.avif          # 復号して aomdec と比べる
    uv run python videos/avif/tools/av1.py videos/avif/data/cat_q60.avif --stats  # 使われた道具の集計も

記録 (Decoder の属性。座標はすべて画素、x が横)：
  seq, frame          頭の値 (dict)。frame["tiles"] にタイルの区切り
  fields              [(名前, 値, ファイルの中のビット位置, ビット数)]  OBU の頭・sequence header・frame header
  partitions          [dict(x, y, size, bsize, partition, coded)]  coded は "symbol" / "split_or_horz" /
                      "split_or_vert" / "implied" (写真の端や 8×8 未満で決まっているもの)
  blocks              [dict(x, y, w, h, bsize, skip, segment_id, qindex, lossless, y_mode, angle_delta_y,
                      uv_mode, angle_delta_uv, cfl_alpha_u, cfl_alpha_v, use_filter_intra, filter_intra_mode,
                      palette_size_y, palette_size_uv, palette_y, palette_u, palette_v, tx_size, tx_w, tx_h,
                      cdef_idx, delta_lf, has_chroma, tile)]  明るさの座標。uv_mode は has_chroma のときだけ意味がある
  txbs                [dict(plane, x, y, w, h, tx_size, skip, tx_type, eob, levels, dequant, resid, pred)]
                      その面の座標。levels は量子化された係数 (min(h,32)×min(w,32) の格子を行の順に。int32)、
                      dequant は逆量子化のあと、resid は逆変換のあと (反転を済ませた画面の向き、h×w)。
                      eob=0 か skip なら 3 つとも None。pred は予想を作り直すための引数 (intra_pred に渡す)
  pred, recon, deblocked, cdef, lr, final
                      面ごとの numpy 配列 (8 ビットは uint8、それ以外は uint16) の list。復号した大きさ
                      (縦横は超ブロックの倍数まで余白つき。crop() で写真の大きさに切る)。
                      pred は予想だけ、recon はループフィルタの前、lr はフィルムグレインの前、final は出力
  intra_pred(txb, keep={})   予想を recon から作り直す。keep に端の画素 (above/left、端のなめらか化・2 倍化の
                      あと above_f/left_f)、角度、CfL の luma_avg・L・ac などが入る
  cdef_log            dict(blocks=[dict(x, y, dir, var, skip, idx)] (明るさの 8×8 ごと)、
                      sb=[dict(x, y, idx, y_pri, y_sec, uv_pri, uv_sec)] (64×64 ごと)、damping)
  deblock_log         [(面, pass, x, y, filter_size, lvl, limit, blimit, thresh, apply, 4 本の結果)]
                      pass 0 は縦の境目。結果は 0 (しない) / 4 (狭い) / 6・8・16 (広い、log2Size の幅)
  lr_units            [dict(plane, row, col, type, wiener=[縦 3, 横 3], sgr_set, xqd)]
  symbols             [(名前, CDF の名前と番号の tuple / None (L() の 1 ビット), 読む前の CDF (tuple), 値,
                      読む前のビット位置, 読んだあとのビット位置)]  位置はファイルの中のビット (小数)。
                      initial_cdf(key) で最初の CDF を、symbol_prob(cdf, 値) でその値の確率を得られる
                      (-log2 の和が「覚えながら」のビット数。initial_cdf で計算すれば「最初の確率のまま」)
  film_grain          頭の値 (dict) と luma_grain・cb_grain・cr_grain・scaling・noise (面ごとの noiseImage)
"""
import math
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import av1tables as T  # noqa: E402
import heif  # noqa: E402

BW = [4 * n for n in T.Num_4x4_Blocks_Wide]
BH = [4 * n for n in T.Num_4x4_Blocks_High]
TXW, TXH = T.Tx_Width, T.Tx_Height
TX_SET_DCTONLY = 0
O = 16   # 端の配列 (AboveRow / LeftCol) の -16 の位置
MODE_NAMES = ["DC", "V", "H", "D45", "D135", "D113", "D157", "D203", "D67", "SMOOTH", "SMOOTH_V", "SMOOTH_H",
              "PAETH", "CFL"]
PARTITION_NAMES = ["NONE", "HORZ", "VERT", "SPLIT", "HORZ_A", "HORZ_B", "VERT_A", "VERT_B", "HORZ_4", "VERT_4"]
TX_TYPE_NAMES = ["DCT_DCT", "ADST_DCT", "DCT_ADST", "ADST_ADST", "FLIPADST_DCT", "DCT_FLIPADST",
                 "FLIPADST_FLIPADST", "ADST_FLIPADST", "FLIPADST_ADST", "IDTX", "V_DCT", "H_DCT", "V_ADST",
                 "H_ADST", "V_FLIPADST", "H_FLIPADST"]
BLOCK_NAMES = ["4x4", "4x8", "8x4", "8x8", "8x16", "16x8", "16x16", "16x32", "32x16", "32x32", "32x64", "64x32",
               "64x64", "64x128", "128x64", "128x128", "4x16", "16x4", "8x32", "32x8", "16x64", "64x16"]


def round2(x, n):
    return x if n == 0 else (x + (1 << (n - 1))) >> n


def round2s(x, n):
    return round2(x, n) if x >= 0 else -round2(-x, n)


def floorlog2(x):
    return x.bit_length() - 1


def ceillog2(x):
    return 0 if x < 2 else (x - 1).bit_length()


def clip3(lo, hi, x):
    return lo if x < lo else hi if x > hi else x


def np_round2(x, n):
    return x if n == 0 else (x + (1 << (n - 1))) >> n


# ---------------------------------------------------------------- ビット列

class Bits:
    """頭の f(n) を読む。name を渡すと fields に (名前, 値, ファイルのビット位置, ビット数) を残す"""

    def __init__(self, data, base, fields):
        self.d = data
        self.p = 0
        self.base = base   # data[0] のファイルの中のビット位置 (None なら不明)
        self.fields = fields

    def pos(self):
        return None if self.base is None else self.base + self.p

    def _rec(self, name, v, p0, n):
        if name is not None:
            self.fields.append((name, v, None if self.base is None else self.base + p0, n))

    def raw(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.p >> 3] >> (7 - (self.p & 7))) & 1)
            self.p += 1
        return v

    def f(self, n, name=None):
        p0 = self.p
        v = self.raw(n)
        self._rec(name, v, p0, n)
        return v

    def su(self, n, name=None):
        p0 = self.p
        v = self.raw(n)
        if v & (1 << (n - 1)):
            v -= 1 << n
        self._rec(name, v, p0, n)
        return v

    def ns(self, n, name=None):
        p0 = self.p
        w = floorlog2(n) + 1
        m = (1 << w) - n
        v = self.raw(w - 1)
        if v >= m:
            v = (v << 1) - m + self.raw(1)
        self._rec(name, v, p0, self.p - p0)
        return v

    def uvlc(self, name=None):
        p0 = self.p
        lz = 0
        while not self.raw(1):
            lz += 1
        v = (1 << 32) - 1 if lz >= 32 else self.raw(lz) + (1 << lz) - 1
        self._rec(name, v, p0, self.p - p0)
        return v

    def le(self, n, name=None):
        p0 = self.p
        t = 0
        for i in range(n):
            t += self.raw(8) << (8 * i)
        self._rec(name, t, p0, 8 * n)
        return t

    def byte_alignment(self):
        while self.p & 7:
            self.raw(1)


def leb128(b, o):
    v = 0
    for i in range(8):
        v |= (b[o + i] & 0x7F) << (7 * i)
        if not b[o + i] & 0x80:
            return v, o + i + 1
    raise ValueError("leb128")


def split_obus(buf, base):
    """ふつうの OBU の並び → [dict(type, pos (ファイルの中のバイト位置 / None), data (頭を含む全部), hdr (頭のバイト数))]"""
    out = []
    o = 0
    while o < len(buf):
        h = buf[o]
        typ, ext, has_size = (h >> 3) & 15, (h >> 2) & 1, (h >> 1) & 1
        p = o + 1 + ext
        assert has_size
        n, p = leb128(buf, p)
        out.append(dict(type=typ, pos=None if base is None else base + o, data=bytes(buf[o:p + n]), hdr=p - o))
        o = p + n
    return out


# ---------------------------------------------------------------- 算術符号 (Symbol decoder)

class SymbolDecoder:
    def __init__(self, data, start, sz, base_bit, disable_update, log):
        self.d = data
        self.bp = start * 8
        self.sz = sz
        self.start_bit = base_bit + start * 8 if base_bit is not None else start * 8
        self.disable = disable_update
        self.log = log
        nb = min(sz * 8, 15)
        buf = self._read(nb)
        self.val = ((1 << 15) - 1) ^ (buf << (15 - nb))
        self.rng = 1 << 15
        self.maxbits = 8 * sz - 15

    def _read(self, n):
        if n == 0:
            return 0
        p = self.bp
        i = p >> 3
        chunk = int.from_bytes(self.d[i:i + 4].ljust(4, b"\0"), "big")
        self.bp = p + n
        return (chunk >> (32 - (p & 7) - n)) & ((1 << n) - 1)

    def pos(self):
        """ファイルの中で、ここまでに使ったビット数の位置 (小数。区間の幅の log2 を引いたもの)"""
        return self.start_bit + (8 * self.sz - self.maxbits) - math.log2(self.rng)

    def _renorm(self, rng, val):
        bits = 16 - rng.bit_length()
        if bits:
            rng <<= bits
            nb = min(bits, max(0, self.maxbits))
            new = self._read(nb)
            val = (new << (bits - nb)) ^ (((val + 1) << bits) - 1)
            self.maxbits -= bits
        self.rng, self.val = rng, val

    def symbol(self, cdf, name, key):
        log = self.log
        if log is not None:
            pb = self.pos()
            before = tuple(cdf[:-1])
        N = len(cdf) - 1
        rng, val = self.rng, self.val
        r8 = rng >> 8
        cur = rng
        s = -1
        while True:
            s += 1
            prev = cur
            cur = ((r8 * ((32768 - cdf[s]) >> 6)) >> 1) + 4 * (N - s - 1)
            if val >= cur:
                break
        self._renorm(prev - cur, val - cur)
        if not self.disable:
            cnt = cdf[N]
            rate = 3 + (cnt > 15) + (cnt > 31) + min(floorlog2(N), 2)
            tmp = 0
            for i in range(N - 1):
                if i == s:
                    tmp = 32768
                c = cdf[i]
                if tmp < c:
                    cdf[i] = c - ((c - tmp) >> rate)
                else:
                    cdf[i] = c + ((tmp - c) >> rate)
            cdf[N] = cnt + (cnt < 32)
        if log is not None:
            log.append((name, key, before, s, pb, self.pos()))
        return s

    def bool(self, name):
        if self.log is not None:
            pb = self.pos()
        rng, val = self.rng, self.val
        cur = (((rng >> 8) * (16384 >> 6)) >> 1) + 4
        if val >= cur:
            b = 0
            self._renorm(rng - cur, val - cur)
        else:
            b = 1
            self._renorm(cur, val)
        if self.log is not None:
            self.log.append((name, None, (16384, 32768), b, pb, self.pos()))
        return b

    def literal(self, n, name):
        x = 0
        for _ in range(n):
            x = 2 * x + self.bool(name)
        return x

    def ns(self, n, name):
        w = floorlog2(n) + 1
        m = (1 << w) - n
        v = self.literal(w - 1, name)
        if v < m:
            return v
        return (v << 1) - m + self.literal(1, name)


def symbol_prob(cdf, v):
    """CDF (最後の数えを除いた tuple) で値 v が占める区間の割合。復号器と同じ計算 (幅 32768 のとき)。
    CDF の差が 0 でも、最小の確率 (EC_MIN_PROB) のぶん 0 にはならない"""
    N = len(cdf)

    def cur(k):
        if k < 0:
            return 32768
        return ((128 * ((32768 - cdf[k]) >> 6)) >> 1) + 4 * (N - k - 1)
    return (cur(v - 1) - cur(v)) / 32768


# ---------------------------------------------------------------- CDF の名前 → 既定の表

NONCOEF = {
    "YMode": "Default_Y_Mode_Cdf", "IntraFrameYMode": "Default_Intra_Frame_Y_Mode_Cdf",
    "UVModeCflNotAllowed": "Default_Uv_Mode_Cfl_Not_Allowed_Cdf",
    "UVModeCflAllowed": "Default_Uv_Mode_Cfl_Allowed_Cdf", "AngleDelta": "Default_Angle_Delta_Cdf",
    "Intrabc": "Default_Intrabc_Cdf", "PartitionW8": "Default_Partition_W8_Cdf",
    "PartitionW16": "Default_Partition_W16_Cdf", "PartitionW32": "Default_Partition_W32_Cdf",
    "PartitionW64": "Default_Partition_W64_Cdf", "PartitionW128": "Default_Partition_W128_Cdf",
    "SegmentId": "Default_Segment_Id_Cdf", "SegmentIdPredicted": "Default_Segment_Id_Predicted_Cdf",
    "Tx8x8": "Default_Tx_8x8_Cdf", "Tx16x16": "Default_Tx_16x16_Cdf", "Tx32x32": "Default_Tx_32x32_Cdf",
    "Tx64x64": "Default_Tx_64x64_Cdf", "TxfmSplit": "Default_Txfm_Split_Cdf",
    "FilterIntraMode": "Default_Filter_Intra_Mode_Cdf", "FilterIntra": "Default_Filter_Intra_Cdf",
    "Skip": "Default_Skip_Cdf", "PaletteYMode": "Default_Palette_Y_Mode_Cdf",
    "PaletteUVMode": "Default_Palette_Uv_Mode_Cdf", "PaletteYSize": "Default_Palette_Y_Size_Cdf",
    "PaletteUVSize": "Default_Palette_Uv_Size_Cdf", "DeltaQ": "Default_Delta_Q_Cdf",
    "DeltaLF": "Default_Delta_Lf_Cdf", "IntraTxTypeSet1": "Default_Intra_Tx_Type_Set1_Cdf",
    "IntraTxTypeSet2": "Default_Intra_Tx_Type_Set2_Cdf", "CflSign": "Default_Cfl_Sign_Cdf",
    "CflAlpha": "Default_Cfl_Alpha_Cdf", "UseWiener": "Default_Use_Wiener_Cdf",
    "UseSgrproj": "Default_Use_Sgrproj_Cdf", "RestorationType": "Default_Restoration_Type_Cdf",
}
for _n in range(2, 9):
    NONCOEF[f"PaletteSize{_n}YColor"] = f"Default_Palette_Size_{_n}_Y_Color_Cdf"
    NONCOEF[f"PaletteSize{_n}UVColor"] = f"Default_Palette_Size_{_n}_Uv_Color_Cdf"
COEF = {"TxbSkip": "Default_Txb_Skip_Cdf", "EobPt16": "Default_Eob_Pt_16_Cdf", "EobPt32": "Default_Eob_Pt_32_Cdf",
        "EobPt64": "Default_Eob_Pt_64_Cdf", "EobPt128": "Default_Eob_Pt_128_Cdf",
        "EobPt256": "Default_Eob_Pt_256_Cdf", "EobPt512": "Default_Eob_Pt_512_Cdf",
        "EobPt1024": "Default_Eob_Pt_1024_Cdf", "EobExtra": "Default_Eob_Extra_Cdf",
        "DcSign": "Default_Dc_Sign_Cdf", "CoeffBaseEob": "Default_Coeff_Base_Eob_Cdf",
        "CoeffBase": "Default_Coeff_Base_Cdf", "CoeffBr": "Default_Coeff_Br_Cdf"}


def deep(x):
    return [deep(y) for y in x] if isinstance(x, list) else x


def default_cdfs(base_q_idx):
    c = {k: deep(getattr(T, v)) for k, v in NONCOEF.items()}
    c["DeltaLFMulti"] = [deep(T.Default_Delta_Lf_Cdf) for _ in range(T.FRAME_LF_COUNT)]
    idx = 0 if base_q_idx <= 20 else 1 if base_q_idx <= 60 else 2 if base_q_idx <= 120 else 3
    for k, v in COEF.items():
        c[k] = deep(getattr(T, v)[idx])
    return c


# ---------------------------------------------------------------- 逆変換 (1 次元の手順を作っておく)

def brev(nb, x):
    t = 0
    for i in range(nb):
        t |= ((x >> i) & 1) << (nb - 1 - i)
    return t


def cos128(a):
    a &= 255
    if a <= 64:
        return T.Cos128_Lookup[a]
    if a <= 128:
        return -T.Cos128_Lookup[128 - a]
    if a <= 192:
        return -T.Cos128_Lookup[a - 128]
    return T.Cos128_Lookup[256 - a]


def sin128(a):
    return cos128(a - 64)


def dct_ops(n):
    """逆 DCT (7.13.2.3) の手順の list。("P", 並べ替え) / ("B", a, b, angle, flip) / ("H", a, b, flip)"""
    ops = [("P", [brev(n, i) for i in range(1 << n)])]
    B = lambda a, b, ang, f: ops.append(("B", a, b, ang, f))  # noqa: E731
    H = lambda a, b, f: ops.append(("H", a, b, f))  # noqa: E731
    if n == 6:
        for i in range(16):
            B(32 + i, 63 - i, 63 - 4 * brev(4, i), 0)
    if n >= 5:
        for i in range(8):
            B(16 + i, 31 - i, 6 + (brev(3, 7 - i) << 3), 0)
    if n == 6:
        for i in range(16):
            H(32 + i * 2, 33 + i * 2, i & 1)
    if n >= 4:
        for i in range(4):
            B(8 + i, 15 - i, 12 + (brev(2, 3 - i) << 4), 0)
    if n >= 5:
        for i in range(8):
            H(16 + 2 * i, 17 + 2 * i, i & 1)
    if n == 6:
        for i in range(4):
            for j in range(2):
                B(62 - i * 4 - j, 33 + i * 4 + j, 60 - 16 * brev(2, i) + 64 * j, 1)
    if n >= 3:
        for i in range(2):
            B(4 + i, 7 - i, 56 - 32 * i, 0)
    if n >= 4:
        for i in range(4):
            H(8 + 2 * i, 9 + 2 * i, i & 1)
    if n >= 5:
        for i in range(2):
            for j in range(2):
                B(30 - 4 * i - j, 17 + 4 * i + j, 24 + (j << 6) + ((1 - i) << 5), 1)
    if n == 6:
        for i in range(8):
            for j in range(2):
                H(32 + i * 4 + j, 35 + i * 4 - j, i & 1)
    for i in range(2):
        B(2 * i, 2 * i + 1, 32 + 16 * i, 1 - i)
    if n >= 3:
        for i in range(2):
            H(4 + 2 * i, 5 + 2 * i, i)
    if n >= 4:
        for i in range(2):
            B(14 - i, 9 + i, 48 + 64 * i, 1)
    if n >= 5:
        for i in range(4):
            for j in range(2):
                H(16 + 4 * i + j, 19 + 4 * i - j, i & 1)
    if n == 6:
        for i in range(2):
            for j in range(4):
                B(61 - i * 8 - j, 34 + i * 8 + j, 56 - i * 32 + (j >> 1) * 64, 1)
    for i in range(2):
        H(i, 3 - i, 0)
    if n >= 3:
        B(6, 5, 32, 1)
    if n >= 4:
        for i in range(2):
            for j in range(2):
                H(8 + 4 * i + j, 11 + 4 * i - j, i)
    if n >= 5:
        for i in range(4):
            B(29 - i, 18 + i, 48 + (i >> 1) * 64, 1)
    if n == 6:
        for i in range(4):
            for j in range(4):
                H(32 + 8 * i + j, 39 + 8 * i - j, i & 1)
    if n >= 3:
        for i in range(4):
            H(i, 7 - i, 0)
    if n >= 4:
        for i in range(2):
            B(13 - i, 10 + i, 32, 1)
    if n >= 5:
        for i in range(2):
            for j in range(4):
                H(16 + i * 8 + j, 23 + i * 8 - j, i)
    if n == 6:
        for i in range(8):
            B(59 - i, 36 + i, 48 if i < 4 else 112, 1)
    if n >= 4:
        for i in range(8):
            H(i, 15 - i, 0)
    if n >= 5:
        for i in range(4):
            B(27 - i, 20 + i, 32, 1)
    if n == 6:
        for i in range(8):
            H(32 + i, 47 - i, 0)
            H(48 + i, 63 - i, 1)
    if n >= 5:
        for i in range(16):
            H(i, 31 - i, 0)
    if n == 6:
        for i in range(8):
            B(55 - i, 40 + i, 32, 1)
    if n == 6:
        for i in range(32):
            H(i, 63 - i, 0)
    return ops


def adst_ops(n):
    """逆 ADST8 / ADST16 (7.13.2.7-8)"""
    n0 = 1 << n
    ops = [("P", [(i - 1) if (i & 1) else (n0 - i - 1) for i in range(n0)])]
    B = lambda a, b, ang, f: ops.append(("B", a, b, ang, f))  # noqa: E731
    H = lambda a, b, f: ops.append(("H", a, b, f))  # noqa: E731
    if n == 3:
        for i in range(4):
            B(2 * i, 2 * i + 1, 60 - 16 * i, 1)
        for i in range(4):
            H(i, 4 + i, 0)
        for i in range(2):
            B(4 + 3 * i, 5 + i, 48 - 32 * i, 1)
        for i in range(2):
            for j in range(2):
                H(4 * j + i, 2 + 4 * j + i, 0)
        for i in range(2):
            B(2 + 4 * i, 3 + 4 * i, 32, 1)
    else:
        for i in range(8):
            B(2 * i, 2 * i + 1, 62 - 8 * i, 1)
        for i in range(8):
            H(i, 8 + i, 0)
        for i in range(2):
            B(8 + 2 * i, 9 + 2 * i, 56 - 32 * i, 1)
            B(13 + 2 * i, 12 + 2 * i, 8 + 32 * i, 1)
        for i in range(4):
            for j in range(2):
                H(8 * j + i, 4 + 8 * j + i, 0)
        for i in range(2):
            for j in range(2):
                B(4 + 8 * j + 3 * i, 5 + 8 * j + i, 48 - 32 * i, 1)
        for i in range(2):
            for j in range(4):
                H(4 * j + i, 2 + 4 * j + i, 0)
        for i in range(4):
            B(2 + 4 * i, 3 + 4 * i, 32, 1)
    # 出力の並べ替え (符号つき)
    perm = []
    for i in range(n0):
        a = (i >> 3) & 1
        b = ((i >> 2) & 1) ^ ((i >> 3) & 1)
        c = ((i >> 1) & 1) ^ ((i >> 2) & 1)
        d = (i & 1) ^ ((i >> 1) & 1)
        perm.append(((d << 3) | (c << 2) | (b << 1) | a) >> (4 - n))
    ops.append(("Q", perm))
    return ops


_OPS = {}


def run_ops(Tv, ops, r):
    """Tv: 長さ 2^n の list (各要素は numpy の 1 次元配列 = 同時に変換する行または列)"""
    lo, hi = -(1 << (r - 1)), (1 << (r - 1)) - 1
    for op in ops:
        k = op[0]
        if k == "B":
            _, a, b, ang, fl = op
            c, s = cos128(ang), sin128(ang)
            x = Tv[a] * c - Tv[b] * s
            y = Tv[a] * s + Tv[b] * c
            Tv[a] = (x + 2048) >> 12
            Tv[b] = (y + 2048) >> 12
            if fl:
                Tv[a], Tv[b] = Tv[b], Tv[a]
        elif k == "H":
            _, a, b, fl = op
            if fl:
                a, b = b, a
            x, y = Tv[a], Tv[b]
            Tv[a] = np.clip(x + y, lo, hi)
            Tv[b] = np.clip(x - y, lo, hi)
        elif k == "P":
            Tv[:] = [Tv[i] for i in op[1]]
        else:   # "Q"
            Tv[:] = [(-Tv[ix] if (i & 1) else Tv[ix]) for i, ix in enumerate(op[1])]
    return Tv


def adst4(Tv):
    S1, S2, S3, S4 = 1321, 2482, 3344, 3803
    t0, t1, t2, t3 = Tv
    s0 = S1 * t0
    s1 = S2 * t0
    s2 = S3 * t1
    s3 = S4 * t2
    s4 = S1 * t2
    s5 = S2 * t3
    s6 = S4 * t3
    a7 = t0 - t2
    b7 = a7 + t3
    s0 = s0 + s3
    s1 = s1 - s4
    s3 = s2
    s2 = S3 * b7
    s0 = s0 + s5
    s1 = s1 - s6
    x0 = s0 + s3
    x1 = s1 + s3
    x2 = s2
    x3 = s0 + s1
    x3 = x3 - s3
    return [(x0 + 2048) >> 12, (x1 + 2048) >> 12, (x2 + 2048) >> 12, (x3 + 2048) >> 12]


def wht(Tv, shift):
    a = Tv[0] >> shift
    c = Tv[1] >> shift
    d = Tv[2] >> shift
    b = Tv[3] >> shift
    a = a + c
    d = d - b
    e = (a - d) >> 1
    b = e - b
    c = e - c
    a = a - b
    d = d + c
    return [a, b, c, d]


def identity(Tv, n):
    if n == 2:
        return [(t * 5793 + 2048) >> 12 for t in Tv]
    if n == 3:
        return [t * 2 for t in Tv]
    if n == 4:
        return [(t * 11586 + 2048) >> 12 for t in Tv]
    return [t * 4 for t in Tv]


DCT_ROW = {0, 1, 4, 11}           # DCT_DCT, ADST_DCT, FLIPADST_DCT, H_DCT (行が DCT)
ADST_ROW = {2, 3, 5, 6, 7, 8, 13, 15}
DCT_COL = {0, 2, 5, 10}
ADST_COL = {1, 3, 4, 6, 7, 8, 12, 14}


def tx1d(Tv, kind, n, r):
    if kind == "dct":
        if ("d", n) not in _OPS:
            _OPS[("d", n)] = dct_ops(n)
        return run_ops(Tv, _OPS[("d", n)], r)
    if kind == "adst":
        if n == 2:
            return adst4(Tv)
        if ("a", n) not in _OPS:
            _OPS[("a", n)] = adst_ops(n)
        return run_ops(Tv, _OPS[("a", n)], r)
    return identity(Tv, n)


def inverse_transform_2d(D, txSz, tx_type, lossless, bd):
    """7.13.3。D は Dequant (h×w、32 を超える所は 0)。Residual (h×w) を返す"""
    log2W, log2H = T.Tx_Width_Log2[txSz], T.Tx_Height_Log2[txSz]
    w, h = 1 << log2W, 1 << log2H
    rowShift = 0 if lossless else T.Transform_Row_Shift[txSz]
    colShift = 0 if lossless else 4
    rowR = bd + 8
    colR = max(bd + 6, 16)
    # 行の変換：Tv[j] は全部の行の j 番目
    Tv = [D[:, j].astype(np.int64) for j in range(w)]
    if abs(log2W - log2H) == 1:
        Tv = [(t * 2896 + 2048) >> 12 for t in Tv]
    if lossless:
        Tv = wht(Tv, 2)
    elif tx_type in DCT_ROW:
        Tv = tx1d(Tv, "dct", log2W, rowR)
    elif tx_type in ADST_ROW:
        Tv = tx1d(Tv, "adst", log2W, rowR)
    else:
        Tv = tx1d(Tv, "id", log2W, rowR)
    R = np.stack([np_round2(t, rowShift) for t in Tv], axis=1)   # h×w
    R = np.clip(R, -(1 << (colR - 1)), (1 << (colR - 1)) - 1)
    Tv = [R[i, :] for i in range(h)]
    if lossless:
        Tv = wht(Tv, 0)
    elif tx_type in DCT_COL:
        Tv = tx1d(Tv, "dct", log2H, colR)
    elif tx_type in ADST_COL:
        Tv = tx1d(Tv, "adst", log2H, colR)
    else:
        Tv = tx1d(Tv, "id", log2H, colR)
    return np.stack([np_round2(t, colShift) for t in Tv], axis=0)


# ---------------------------------------------------------------- イントラ予想 (7.11.2)

def edge_strength(w, h, ft, delta):
    d = abs(delta)
    s = 0
    wh = w + h
    if ft == 0:
        if wh <= 8:
            if d >= 56:
                s = 1
        elif wh <= 12:
            if d >= 40:
                s = 1
        elif wh <= 16:
            if d >= 40:
                s = 1
        elif wh <= 24:
            if d >= 8:
                s = 1
            if d >= 16:
                s = 2
            if d >= 32:
                s = 3
        elif wh <= 32:
            s = 1
            if d >= 4:
                s = 2
            if d >= 32:
                s = 3
        else:
            s = 3
    else:
        if wh <= 8:
            if d >= 40:
                s = 1
            if d >= 64:
                s = 2
        elif wh <= 16:
            if d >= 20:
                s = 1
            if d >= 48:
                s = 2
        elif wh <= 24:
            if d >= 4:
                s = 3
        else:
            s = 3
    return s


def use_upsample(w, h, ft, delta):
    d = abs(delta)
    if d <= 0 or d >= 40:
        return 0
    return int(w + h <= 16) if ft == 0 else int(w + h <= 8)


def edge_filter(buf, sz, strength):
    if strength == 0:
        return
    edge = [buf[O + i - 1] for i in range(sz)]
    k = T.Intra_Edge_Kernel[strength - 1]
    for i in range(1, sz):
        s = 0
        for j in range(5):
            kk = i - 2 + j
            kk = 0 if kk < 0 else sz - 1 if kk > sz - 1 else kk
            s += k[j] * edge[kk]
        buf[O + i - 1] = (s + 8) >> 4


def edge_upsample(buf, numPx, bd):
    dup = [0] * (numPx + 3)
    dup[0] = buf[O - 1]
    for i in range(-1, numPx):
        dup[i + 2] = buf[O + i]
    dup[numPx + 2] = buf[O + numPx - 1]
    buf[O - 2] = dup[0]
    mx = (1 << bd) - 1
    for i in range(numPx):
        s = -dup[i] + 9 * dup[i + 1] + 9 * dup[i + 2] - dup[i + 3]
        s = clip3(0, mx, round2(s, 4))
        buf[O + 2 * i - 1] = s
        buf[O + 2 * i] = dup[i + 2]


SM_W = {2: T.Sm_Weights_Tx_4x4, 3: T.Sm_Weights_Tx_8x8, 4: T.Sm_Weights_Tx_16x16, 5: T.Sm_Weights_Tx_32x32,
        6: T.Sm_Weights_Tx_64x64}


def intra_predict(F, p, keep=None):
    """予想のブロック (h×w の int64)。F はその面の画素 (numpy 2 次元)。p は txbs の "pred" の dict。
    keep (dict) を渡すと途中の値を入れる"""
    x, y = p["x"], p["y"]
    log2W, log2H = p["log2W"], p["log2H"]
    w, h = 1 << log2W, 1 << log2H
    bd = p["bd"]
    mode = p["mode"]
    haveLeft, haveAbove = p["haveLeft"], p["haveAbove"]
    maxX, maxY = p["maxX"], p["maxY"]
    n = w + h
    A = [0] * (O + 2 * n + 40)
    L = [0] * (O + 2 * n + 40)
    if not haveAbove and haveLeft:
        A[O:O + n] = [int(F[y, x - 1])] * n
    elif not haveAbove and not haveLeft:
        A[O:O + n] = [(1 << (bd - 1)) - 1] * n
    else:
        lim = min(maxX, x + (2 * w if p["haveAboveRight"] else w) - 1)
        row = F[y - 1, x:lim + 1].tolist()
        A[O:O + n] = [row[min(lim, x + i) - x] for i in range(n)]
    if not haveLeft and haveAbove:
        L[O:O + n] = [int(F[y - 1, x])] * n
    elif not haveLeft and not haveAbove:
        L[O:O + n] = [(1 << (bd - 1)) + 1] * n
    else:
        lim = min(maxY, y + (2 * h if p["haveBelowLeft"] else h) - 1)
        col = F[y:lim + 1, x - 1].tolist()
        L[O:O + n] = [col[min(lim, y + i) - y] for i in range(n)]
    if haveAbove and haveLeft:
        corner = int(F[y - 1, x - 1])
    elif haveAbove:
        corner = int(F[y - 1, x])
    elif haveLeft:
        corner = int(F[y, x - 1])
    else:
        corner = 1 << (bd - 1)
    A[O - 1] = L[O - 1] = corner
    if keep is not None:
        keep["above"] = A[O - 1:O + n]
        keep["left"] = L[O - 1:O + n]
    mx = (1 << bd) - 1
    ii = np.arange(h)[:, None]
    jj = np.arange(w)[None, :]
    if p["plane"] == 0 and p["use_filter_intra"]:
        taps = T.Intra_Filter_Taps[p["filter_intra_mode"]]
        pred = [[0] * w for _ in range(h)]
        for i2 in range(h >> 1):
            for j4 in range(w >> 2):
                pp = [0] * 7
                for i in range(7):
                    if i < 5:
                        if i2 == 0:
                            pp[i] = A[O + (j4 << 2) + i - 1]
                        elif j4 == 0 and i == 0:
                            pp[i] = L[O + (i2 << 1) - 1]
                        else:
                            pp[i] = pred[(i2 << 1) - 1][(j4 << 2) + i - 1]
                    else:
                        if j4 == 0:
                            pp[i] = L[O + (i2 << 1) + i - 5]
                        else:
                            pp[i] = pred[(i2 << 1) + i - 5][(j4 << 2) - 1]
                for i1 in range(2):
                    for j1 in range(4):
                        tp = taps[(i1 << 2) + j1]
                        pr = sum(tp[i] * pp[i] for i in range(7))
                        pred[(i2 << 1) + i1][(j4 << 2) + j1] = clip3(0, mx, round2s(pr, 4))
        out = np.array(pred, np.int64)
    elif 1 <= mode <= 8:   # 方向
        pAngle = T.Mode_To_Angle[mode] + p["angle_delta"] * T.ANGLE_STEP
        upA = upL = 0
        if p["edge_filter"]:
            ft = p["filter_type"]
            sa = sl = 0
            if pAngle != 90 and pAngle != 180:
                if 90 < pAngle < 180 and w + h >= 24:
                    v = round2(L[O] * 5 + A[O - 1] * 6 + A[O] * 5, 4)
                    A[O - 1] = L[O - 1] = v
                if haveAbove:
                    sa = edge_strength(w, h, ft, pAngle - 90)
                    edge_filter(A, min(w, maxX - x + 1) + (h if pAngle < 90 else 0) + 1, sa)
                if haveLeft:
                    sl = edge_strength(w, h, ft, pAngle - 180)
                    edge_filter(L, min(h, maxY - y + 1) + (w if pAngle > 180 else 0) + 1, sl)
            upA = use_upsample(w, h, ft, pAngle - 90)
            if upA:
                edge_upsample(A, w + (h if pAngle < 90 else 0), bd)
            upL = use_upsample(w, h, ft, pAngle - 180)
            if upL:
                edge_upsample(L, h + (w if pAngle > 180 else 0), bd)
            if keep is not None:
                keep.update(filter_type=ft, strength_above=sa, strength_left=sl)
        if keep is not None:
            keep.update(p_angle=pAngle, upsample_above=upA, upsample_left=upL,
                        above_f=A[O - 1 - upA:O + (2 * n if upA else n)],
                        left_f=L[O - 1 - upL:O + (2 * n if upL else n)])
        Aa = np.array(A, np.int64)
        La = np.array(L, np.int64)
        top = len(A) - O - 2
        if pAngle < 90:
            dx = T.Dr_Intra_Derivative[pAngle]
            idx = (ii + 1) * dx
            base = (idx >> (6 - upA)) + (jj << upA)
            shift = ((idx << upA) >> 1) & 0x1F
            mb = (w + h - 1) << upA
            bc = np.minimum(base, mb)
            v = np_round2(Aa[O + bc] * (32 - shift) + Aa[O + bc + 1] * shift, 5)
            out = np.where(base < mb, v, Aa[O + mb])
        elif 90 < pAngle < 180:
            dx = T.Dr_Intra_Derivative[180 - pAngle]
            dy = T.Dr_Intra_Derivative[pAngle - 90]
            idx = (jj << 6) - (ii + 1) * dx
            base = idx >> (6 - upA)
            shA = ((idx << upA) >> 1) & 0x1F
            bA = np.clip(base, -O, top)
            pa = np_round2(Aa[O + bA] * (32 - shA) + Aa[O + bA + 1] * shA, 5)
            idx2 = (ii << 6) - (jj + 1) * dy
            base2 = idx2 >> (6 - upL)
            shL = ((idx2 << upL) >> 1) & 0x1F
            bL = np.clip(base2, -O, top)
            pl = np_round2(La[O + bL] * (32 - shL) + La[O + bL + 1] * shL, 5)
            out = np.where(base >= -(1 << upA), pa, pl)
        elif pAngle > 180:
            dy = T.Dr_Intra_Derivative[270 - pAngle]
            idx = (jj + 1) * dy
            base = (idx >> (6 - upL)) + (ii << upL)
            shift = ((idx << upL) >> 1) & 0x1F
            assert base.max() + 1 <= top + 1
            out = np_round2(La[O + base] * (32 - shift) + La[O + base + 1] * shift, 5)
        elif pAngle == 90:
            out = np.broadcast_to(Aa[O:O + w][None, :], (h, w)).copy()
        else:
            out = np.broadcast_to(La[O:O + h][:, None], (h, w)).copy()
    elif mode in (9, 10, 11):
        Aa = np.array(A[O:O + w], np.int64)[None, :]
        La = np.array(L[O:O + h], np.int64)[:, None]
        if mode == 9:
            wy = np.array(SM_W[log2H], np.int64)[:, None]
            wx = np.array(SM_W[log2W], np.int64)[None, :]
            s = wy * Aa + (256 - wy) * L[O + h - 1] + wx * La + (256 - wx) * A[O + w - 1]
            out = np_round2(s, 9)
        elif mode == 10:
            wy = np.array(SM_W[log2H], np.int64)[:, None]
            out = np_round2(wy * Aa + (256 - wy) * L[O + h - 1], 8) + 0 * jj
        else:
            wx = np.array(SM_W[log2W], np.int64)[None, :]
            out = np_round2(wx * La + (256 - wx) * A[O + w - 1], 8) + 0 * ii
    elif mode == 0:
        if haveLeft and haveAbove:
            s = sum(L[O:O + h]) + sum(A[O:O + w])
            s += (w + h) >> 1
            avg = s // (w + h)
        elif haveLeft:
            avg = clip3(0, mx, (sum(L[O:O + h]) + (h >> 1)) >> log2H)
        elif haveAbove:
            avg = clip3(0, mx, (sum(A[O:O + w]) + (w >> 1)) >> log2W)
        else:
            avg = 1 << (bd - 1)
        out = np.full((h, w), avg, np.int64)
    else:   # PAETH
        Aa = np.array(A[O:O + w], np.int64)[None, :]
        La = np.array(L[O:O + h], np.int64)[:, None]
        tl = A[O - 1]
        base = Aa + La - tl
        pL = np.abs(base - La)
        pT = np.abs(base - Aa)
        pTL = np.abs(base - tl)
        out = np.where((pL <= pT) & (pL <= pTL), La, np.where(pT <= pTL, Aa, tl))
    return np.ascontiguousarray(out, np.int64)


# ---------------------------------------------------------------- 復号器

class Decoder:
    def __init__(self, obus, keep_symbols=True):
        self.obus = obus
        self.fields = []
        self.symbols = [] if keep_symbols else None
        self.partitions, self.blocks, self.txbs = [], [], []
        self.deblock_log, self.lr_units = [], []
        self.cdef_log = dict(blocks=[], sb=[])
        self.film_grain = None
        self.seq = self.frame = None

    # ---------------- OBU

    def decode(self):
        frames = 0
        for ob in self.obus:
            base = None if ob["pos"] is None else ob["pos"] * 8
            b = Bits(ob["data"], base, self.fields if base is not None else [])   # av1C の中の OBU は残さない
            b.f(1, "obu_forbidden_bit")
            typ = b.f(4, "obu_type")
            ext = b.f(1, "obu_extension_flag")
            b.f(1, "obu_has_size_field")
            b.f(1, "obu_reserved_1bit")
            self.temporal_id = self.spatial_id = 0
            if ext:
                self.temporal_id = b.f(3, "temporal_id")
                self.spatial_id = b.f(2, "spatial_id")
                b.f(3, "extension_header_reserved_3bits")
            b.p = ob["hdr"] * 8
            size = len(ob["data"]) - ob["hdr"]
            if base is not None:
                self.fields.append(("obu_size", size, base + (1 + ext) * 8, (ob["hdr"] - 1 - ext) * 8))
            if typ == 1:
                if self.seq is None or base is not None:
                    self.sequence_header(b)
            elif typ in (3, 6):
                assert frames == 0, "静止画 (フレーム 1 枚) だけ"
                frames += 1
                start = b.p
                self.uncompressed_header(b)
                if typ == 6:
                    b.byte_alignment()
                    sz = size - (b.p - start) // 8
                    self.tile_group(b, sz)
            elif typ == 4:
                self.tile_group(b, size)
        self.finish()
        return self

    # ---------------- sequence header

    def sequence_header(self, b):
        s = {}

        def r(name, n):
            s[name] = b.f(n, name)
            return s[name]
        r("seq_profile", 3)
        r("still_picture", 1)
        red = r("reduced_still_picture_header", 1)
        s["timing_info_present_flag"] = s["decoder_model_info_present_flag"] = 0
        s["equal_picture_interval"] = 0
        if red:
            r("seq_level_idx[0]", 5)
            s["operating_point_idc[0]"] = 0
        else:
            if r("timing_info_present_flag", 1):
                r("num_units_in_display_tick", 32)
                r("time_scale", 32)
                if r("equal_picture_interval", 1):
                    s["num_ticks_per_picture_minus_1"] = b.uvlc("num_ticks_per_picture_minus_1")
                if r("decoder_model_info_present_flag", 1):
                    r("buffer_delay_length_minus_1", 5)
                    r("num_units_in_decoding_tick", 32)
                    r("buffer_removal_time_length_minus_1", 5)
                    r("frame_presentation_time_length_minus_1", 5)
            idd = r("initial_display_delay_present_flag", 1)
            cnt = r("operating_points_cnt_minus_1", 5)
            for i in range(cnt + 1):
                r(f"operating_point_idc[{i}]", 12)
                if r(f"seq_level_idx[{i}]", 5) > 7:
                    r(f"seq_tier[{i}]", 1)
                s[f"decoder_model_present_for_this_op[{i}]"] = 0
                if s["decoder_model_info_present_flag"]:
                    if r(f"decoder_model_present_for_this_op[{i}]", 1):
                        n = s["buffer_delay_length_minus_1"] + 1
                        r(f"decoder_buffer_delay[{i}]", n)
                        r(f"encoder_buffer_delay[{i}]", n)
                        r(f"low_delay_mode_flag[{i}]", 1)
                if idd:
                    if r(f"initial_display_delay_present_for_this_op[{i}]", 1):
                        r(f"initial_display_delay_minus_1[{i}]", 4)
        s["OperatingPointIdc"] = s["operating_point_idc[0]"]
        r("frame_width_bits_minus_1", 4)
        r("frame_height_bits_minus_1", 4)
        r("max_frame_width_minus_1", s["frame_width_bits_minus_1"] + 1)
        r("max_frame_height_minus_1", s["frame_height_bits_minus_1"] + 1)
        s["frame_id_numbers_present_flag"] = 0 if red else r("frame_id_numbers_present_flag", 1)
        if s["frame_id_numbers_present_flag"]:
            r("delta_frame_id_length_minus_2", 4)
            r("additional_frame_id_length_minus_1", 3)
        r("use_128x128_superblock", 1)
        r("enable_filter_intra", 1)
        r("enable_intra_edge_filter", 1)
        if red:
            for k in ("enable_interintra_compound", "enable_masked_compound", "enable_warped_motion",
                      "enable_dual_filter", "enable_order_hint", "enable_jnt_comp", "enable_ref_frame_mvs"):
                s[k] = 0
            s["seq_force_screen_content_tools"] = T.SELECT_SCREEN_CONTENT_TOOLS
            s["seq_force_integer_mv"] = T.SELECT_INTEGER_MV
            s["OrderHintBits"] = 0
        else:
            for k in ("enable_interintra_compound", "enable_masked_compound", "enable_warped_motion",
                      "enable_dual_filter", "enable_order_hint"):
                r(k, 1)
            s["enable_jnt_comp"] = s["enable_ref_frame_mvs"] = 0
            if s["enable_order_hint"]:
                r("enable_jnt_comp", 1)
                r("enable_ref_frame_mvs", 1)
            if r("seq_choose_screen_content_tools", 1):
                s["seq_force_screen_content_tools"] = T.SELECT_SCREEN_CONTENT_TOOLS
            else:
                r("seq_force_screen_content_tools", 1)
            if s["seq_force_screen_content_tools"] > 0:
                if r("seq_choose_integer_mv", 1):
                    s["seq_force_integer_mv"] = T.SELECT_INTEGER_MV
                else:
                    r("seq_force_integer_mv", 1)
            else:
                s["seq_force_integer_mv"] = T.SELECT_INTEGER_MV
            s["OrderHintBits"] = r("order_hint_bits_minus_1", 3) + 1 if s["enable_order_hint"] else 0
        r("enable_superres", 1)
        r("enable_cdef", 1)
        r("enable_restoration", 1)
        # color_config
        hb = r("high_bitdepth", 1)
        if s["seq_profile"] == 2 and hb:
            s["BitDepth"] = 12 if r("twelve_bit", 1) else 10
        else:
            s["BitDepth"] = 10 if hb else 8
        s["mono_chrome"] = 0 if s["seq_profile"] == 1 else r("mono_chrome", 1)
        s["NumPlanes"] = 1 if s["mono_chrome"] else 3
        if r("color_description_present_flag", 1):
            r("color_primaries", 8)
            r("transfer_characteristics", 8)
            r("matrix_coefficients", 8)
        else:
            s["color_primaries"], s["transfer_characteristics"], s["matrix_coefficients"] = 2, 2, 2
        s["separate_uv_delta_q"] = 0
        s["chroma_sample_position"] = 0
        if s["mono_chrome"]:
            r("color_range", 1)
            s["subsampling_x"] = s["subsampling_y"] = 1
        else:
            if s["color_primaries"] == 1 and s["transfer_characteristics"] == 13 and s["matrix_coefficients"] == 0:
                s["color_range"] = 1
                s["subsampling_x"] = s["subsampling_y"] = 0
            else:
                r("color_range", 1)
                if s["seq_profile"] == 0:
                    s["subsampling_x"] = s["subsampling_y"] = 1
                elif s["seq_profile"] == 1:
                    s["subsampling_x"] = s["subsampling_y"] = 0
                else:
                    if s["BitDepth"] == 12:
                        if r("subsampling_x", 1):
                            r("subsampling_y", 1)
                        else:
                            s["subsampling_y"] = 0
                    else:
                        s["subsampling_x"], s["subsampling_y"] = 1, 0
                if s["subsampling_x"] and s["subsampling_y"]:
                    r("chroma_sample_position", 2)
            r("separate_uv_delta_q", 1)
        r("film_grain_params_present", 1)
        self.seq = s

    # ---------------- frame header

    def uncompressed_header(self, b):
        s = self.seq
        h = {}

        def r(name, n):
            h[name] = b.f(n, name)
            return h[name]

        def su(name, n):
            h[name] = b.su(n, name)
            return h[name]
        allFrames = (1 << 8) - 1
        idLen = 0
        if s["frame_id_numbers_present_flag"]:
            idLen = s["additional_frame_id_length_minus_1"] + s["delta_frame_id_length_minus_2"] + 3
        if s["reduced_still_picture_header"]:
            h["show_existing_frame"] = 0
            h["frame_type"] = T.KEY_FRAME
            h["show_frame"] = 1
            h["showable_frame"] = 0
            h["error_resilient_mode"] = 1
        else:
            assert r("show_existing_frame", 1) == 0
            ft = r("frame_type", 2)
            assert ft in (T.KEY_FRAME, T.INTRA_ONLY_FRAME), "インターのフレームは対象外"
            r("show_frame", 1)
            if h["show_frame"] and s["decoder_model_info_present_flag"] and not s["equal_picture_interval"]:
                r("frame_presentation_time", s["frame_presentation_time_length_minus_1"] + 1)
            if h["show_frame"]:
                h["showable_frame"] = int(ft != T.KEY_FRAME)
            else:
                r("showable_frame", 1)
            if ft == T.KEY_FRAME and h["show_frame"]:
                h["error_resilient_mode"] = 1
            else:
                r("error_resilient_mode", 1)
        h["FrameIsIntra"] = 1
        r("disable_cdf_update", 1)
        if s["seq_force_screen_content_tools"] == T.SELECT_SCREEN_CONTENT_TOOLS:
            r("allow_screen_content_tools", 1)
        else:
            h["allow_screen_content_tools"] = s["seq_force_screen_content_tools"]
        if h["allow_screen_content_tools"] and s["seq_force_integer_mv"] == T.SELECT_INTEGER_MV:
            r("force_integer_mv", 1)
        h["force_integer_mv"] = 1
        if s["frame_id_numbers_present_flag"]:
            r("current_frame_id", idLen)
        if s["reduced_still_picture_header"]:
            h["frame_size_override_flag"] = 0
        else:
            r("frame_size_override_flag", 1)
        r("order_hint", s["OrderHintBits"])
        h["primary_ref_frame"] = T.PRIMARY_REF_NONE
        if s["decoder_model_info_present_flag"]:
            if r("buffer_removal_time_present_flag", 1):
                for op in range(s["operating_points_cnt_minus_1"] + 1):
                    if s[f"decoder_model_present_for_this_op[{op}]"]:
                        idc = s[f"operating_point_idc[{op}]"]
                        inT = (idc >> self.temporal_id) & 1
                        inS = (idc >> (self.spatial_id + 8)) & 1
                        if idc == 0 or (inT and inS):
                            r(f"buffer_removal_time[{op}]", s["buffer_removal_time_length_minus_1"] + 1)
        h["allow_intrabc"] = 0
        if h["frame_type"] == T.KEY_FRAME and h["show_frame"]:
            h["refresh_frame_flags"] = allFrames
        else:
            r("refresh_frame_flags", 8)
        if h["refresh_frame_flags"] != allFrames and h["error_resilient_mode"] and s["enable_order_hint"]:
            for i in range(8):
                r(f"ref_order_hint[{i}]", s["OrderHintBits"])
        # frame_size
        if h["frame_size_override_flag"]:
            h["FrameWidth"] = r("frame_width_minus_1", s["frame_width_bits_minus_1"] + 1) + 1
            h["FrameHeight"] = r("frame_height_minus_1", s["frame_height_bits_minus_1"] + 1) + 1
        else:
            h["FrameWidth"] = s["max_frame_width_minus_1"] + 1
            h["FrameHeight"] = s["max_frame_height_minus_1"] + 1
        h["use_superres"] = r("use_superres", 1) if s["enable_superres"] else 0
        h["SuperresDenom"] = r("coded_denom", 3) + 9 if h["use_superres"] else 8
        h["UpscaledWidth"] = h["FrameWidth"]
        h["FrameWidth"] = (h["UpscaledWidth"] * 8 + h["SuperresDenom"] // 2) // h["SuperresDenom"]
        h["MiCols"] = 2 * ((h["FrameWidth"] + 7) >> 3)
        h["MiRows"] = 2 * ((h["FrameHeight"] + 7) >> 3)
        if r("render_and_frame_size_different", 1):
            h["RenderWidth"] = r("render_width_minus_1", 16) + 1
            h["RenderHeight"] = r("render_height_minus_1", 16) + 1
        else:
            h["RenderWidth"], h["RenderHeight"] = h["UpscaledWidth"], h["FrameHeight"]
        if h["allow_screen_content_tools"] and h["UpscaledWidth"] == h["FrameWidth"]:
            r("allow_intrabc", 1)
        if s["reduced_still_picture_header"] or h["disable_cdf_update"]:
            h["disable_frame_end_update_cdf"] = 1
        else:
            r("disable_frame_end_update_cdf", 1)
        # tile_info
        MiCols, MiRows = h["MiCols"], h["MiRows"]
        sb128 = s["use_128x128_superblock"]
        sbCols = ((MiCols + 31) >> 5) if sb128 else ((MiCols + 15) >> 4)
        sbRows = ((MiRows + 31) >> 5) if sb128 else ((MiRows + 15) >> 4)
        sbShift = 5 if sb128 else 4
        sbSize = sbShift + 2
        maxTileWidthSb = T.MAX_TILE_WIDTH >> sbSize
        maxTileAreaSb = T.MAX_TILE_AREA >> (2 * sbSize)

        def tile_log2(blk, target):
            k = 0
            while (blk << k) < target:
                k += 1
            return k
        minLog2TileCols = tile_log2(maxTileWidthSb, sbCols)
        maxLog2TileCols = tile_log2(1, min(sbCols, T.MAX_TILE_COLS))
        maxLog2TileRows = tile_log2(1, min(sbRows, T.MAX_TILE_ROWS))
        minLog2Tiles = max(minLog2TileCols, tile_log2(maxTileAreaSb, sbRows * sbCols))
        colStarts, rowStarts = [], []
        if r("uniform_tile_spacing_flag", 1):
            TileColsLog2 = minLog2TileCols
            while TileColsLog2 < maxLog2TileCols:
                if b.f(1, "increment_tile_cols_log2"):
                    TileColsLog2 += 1
                else:
                    break
            tw = (sbCols + (1 << TileColsLog2) - 1) >> TileColsLog2
            colStarts = [sb << sbShift for sb in range(0, sbCols, tw)] + [MiCols]
            minLog2TileRows = max(minLog2Tiles - TileColsLog2, 0)
            TileRowsLog2 = minLog2TileRows
            while TileRowsLog2 < maxLog2TileRows:
                if b.f(1, "increment_tile_rows_log2"):
                    TileRowsLog2 += 1
                else:
                    break
            th = (sbRows + (1 << TileRowsLog2) - 1) >> TileRowsLog2
            rowStarts = [sb << sbShift for sb in range(0, sbRows, th)] + [MiRows]
        else:
            widest = 0
            sb = 0
            while sb < sbCols:
                colStarts.append(sb << sbShift)
                size = b.ns(min(sbCols - sb, maxTileWidthSb), "width_in_sbs_minus_1") + 1
                widest = max(size, widest)
                sb += size
            colStarts.append(MiCols)
            TileColsLog2 = tile_log2(1, len(colStarts) - 1)
            if minLog2Tiles > 0:
                maxTileAreaSb = (sbRows * sbCols) >> (minLog2Tiles + 1)
            else:
                maxTileAreaSb = sbRows * sbCols
            maxTileHeightSb = max(maxTileAreaSb // widest, 1)
            sb = 0
            while sb < sbRows:
                rowStarts.append(sb << sbShift)
                sb += b.ns(min(sbRows - sb, maxTileHeightSb), "height_in_sbs_minus_1") + 1
            rowStarts.append(MiRows)
            TileRowsLog2 = tile_log2(1, len(rowStarts) - 1)
        h["TileCols"], h["TileRows"] = len(colStarts) - 1, len(rowStarts) - 1
        h["TileColsLog2"], h["TileRowsLog2"] = TileColsLog2, TileRowsLog2
        h["MiColStarts"], h["MiRowStarts"] = colStarts, rowStarts
        h["context_update_tile_id"] = 0
        h["TileSizeBytes"] = 4
        if TileColsLog2 > 0 or TileRowsLog2 > 0:
            r("context_update_tile_id", TileRowsLog2 + TileColsLog2)
            h["TileSizeBytes"] = r("tile_size_bytes_minus_1", 2) + 1
        # quantization_params
        NumPlanes = s["NumPlanes"]

        def delta_q(name):
            if b.f(1, f"delta_coded ({name})"):
                return su(name, 7)
            h[name] = 0
            return 0
        r("base_q_idx", 8)
        delta_q("DeltaQYDc")
        h["DeltaQUDc"] = h["DeltaQUAc"] = h["DeltaQVDc"] = h["DeltaQVAc"] = 0
        if NumPlanes > 1:
            h["diff_uv_delta"] = r("diff_uv_delta", 1) if s["separate_uv_delta_q"] else 0
            delta_q("DeltaQUDc")
            delta_q("DeltaQUAc")
            if h["diff_uv_delta"]:
                delta_q("DeltaQVDc")
                delta_q("DeltaQVAc")
            else:
                h["DeltaQVDc"], h["DeltaQVAc"] = h["DeltaQUDc"], h["DeltaQUAc"]
        if r("using_qmatrix", 1):
            r("qm_y", 4)
            r("qm_u", 4)
            if not s["separate_uv_delta_q"]:
                h["qm_v"] = h["qm_u"]
            else:
                r("qm_v", 4)
        # segmentation_params
        FE = [[0] * 8 for _ in range(8)]
        FD = [[0] * 8 for _ in range(8)]
        if r("segmentation_enabled", 1):
            h["segmentation_update_map"] = 1
            h["segmentation_temporal_update"] = 0
            for i in range(8):
                for j in range(8):
                    fe = b.f(1, f"feature_enabled[{i}][{j}]")
                    FE[i][j] = fe
                    v = 0
                    if fe:
                        bits = T.Segmentation_Feature_Bits[j]
                        lim = T.Segmentation_Feature_Max[j]
                        if T.Segmentation_Feature_Signed[j]:
                            v = clip3(-lim, lim, b.su(1 + bits, f"feature_value[{i}][{j}]"))
                        else:
                            v = clip3(0, lim, b.f(bits, f"feature_value[{i}][{j}]"))
                    FD[i][j] = v
        h["FeatureEnabled"], h["FeatureData"] = FE, FD
        h["SegIdPreSkip"] = 0
        h["LastActiveSegId"] = 0
        for i in range(8):
            for j in range(8):
                if FE[i][j]:
                    h["LastActiveSegId"] = i
                    if j >= T.SEG_LVL_REF_FRAME:
                        h["SegIdPreSkip"] = 1
        # delta_q_params / delta_lf_params
        h["delta_q_res"] = h["delta_q_present"] = 0
        if h["base_q_idx"] > 0:
            r("delta_q_present", 1)
        if h["delta_q_present"]:
            r("delta_q_res", 2)
        h["delta_lf_present"] = h["delta_lf_res"] = h["delta_lf_multi"] = 0
        if h["delta_q_present"]:
            if not h["allow_intrabc"]:
                r("delta_lf_present", 1)
            if h["delta_lf_present"]:
                r("delta_lf_res", 2)
                r("delta_lf_multi", 1)
        self.frame = h
        self._set_frame_vars()
        # 可逆 (lossless)
        h["CodedLossless"] = 1
        self.LosslessArray = []
        self.SegQMLevel = [[0] * 8 for _ in range(3)]
        for seg in range(8):
            q = self.get_qindex(1, seg)
            ll = int(q == 0 and h["DeltaQYDc"] == 0 and h["DeltaQUAc"] == 0 and h["DeltaQUDc"] == 0
                     and h["DeltaQVAc"] == 0 and h["DeltaQVDc"] == 0)
            self.LosslessArray.append(ll)
            if not ll:
                h["CodedLossless"] = 0
            if h["using_qmatrix"]:
                for pl, k in enumerate(("qm_y", "qm_u", "qm_v")):
                    self.SegQMLevel[pl][seg] = 15 if ll else h[k]
        h["AllLossless"] = int(h["CodedLossless"] and h["FrameWidth"] == h["UpscaledWidth"])
        # loop_filter_params
        h["loop_filter_level"] = [0, 0, 0, 0]
        h["loop_filter_ref_deltas"] = [1, 0, 0, 0, -1, 0, -1, -1]
        h["loop_filter_mode_deltas"] = [0, 0]
        h["loop_filter_sharpness"] = 0
        h["loop_filter_delta_enabled"] = 1
        if not (h["CodedLossless"] or h["allow_intrabc"]):
            lv = h["loop_filter_level"]
            lv[0] = b.f(6, "loop_filter_level[0]")
            lv[1] = b.f(6, "loop_filter_level[1]")
            if NumPlanes > 1 and (lv[0] or lv[1]):
                lv[2] = b.f(6, "loop_filter_level[2]")
                lv[3] = b.f(6, "loop_filter_level[3]")
            r("loop_filter_sharpness", 3)
            if r("loop_filter_delta_enabled", 1):
                if r("loop_filter_delta_update", 1):
                    for i in range(8):
                        if b.f(1, f"update_ref_delta[{i}]"):
                            h["loop_filter_ref_deltas"][i] = b.su(7, f"loop_filter_ref_deltas[{i}]")
                    for i in range(2):
                        if b.f(1, f"update_mode_delta[{i}]"):
                            h["loop_filter_mode_deltas"][i] = b.su(7, f"loop_filter_mode_deltas[{i}]")
        # cdef_params
        h["cdef_y_pri"], h["cdef_y_sec"], h["cdef_uv_pri"], h["cdef_uv_sec"] = [0], [0], [0], [0]
        h["cdef_bits"] = 0
        h["CdefDamping"] = 3
        if not (h["CodedLossless"] or h["allow_intrabc"] or not s["enable_cdef"]):
            h["CdefDamping"] = r("cdef_damping_minus_3", 2) + 3
            r("cdef_bits", 2)
            n = 1 << h["cdef_bits"]
            h["cdef_y_pri"], h["cdef_y_sec"] = [0] * n, [0] * n
            h["cdef_uv_pri"], h["cdef_uv_sec"] = [0] * n, [0] * n
            for i in range(n):
                h["cdef_y_pri"][i] = b.f(4, f"cdef_y_pri_strength[{i}]")
                v = b.f(2, f"cdef_y_sec_strength[{i}]")
                h["cdef_y_sec"][i] = 4 if v == 3 else v
                if NumPlanes > 1:
                    h["cdef_uv_pri"][i] = b.f(4, f"cdef_uv_pri_strength[{i}]")
                    v = b.f(2, f"cdef_uv_sec_strength[{i}]")
                    h["cdef_uv_sec"][i] = 4 if v == 3 else v
        # lr_params
        h["FrameRestorationType"] = [0, 0, 0]
        h["UsesLr"] = 0
        h["LoopRestorationSize"] = [256, 256, 256]
        if not (h["AllLossless"] or h["allow_intrabc"] or not s["enable_restoration"]):
            chroma = 0
            for i in range(NumPlanes):
                t = T.Remap_Lr_Type[b.f(2, f"lr_type[{i}]")]
                h["FrameRestorationType"][i] = t
                if t != T.RESTORE_NONE:
                    h["UsesLr"] = 1
                    if i > 0:
                        chroma = 1
            if h["UsesLr"]:
                if sb128:
                    shift = b.f(1, "lr_unit_shift") + 1
                else:
                    shift = b.f(1, "lr_unit_shift")
                    if shift:
                        shift += b.f(1, "lr_unit_extra_shift")
                h["lr_unit_shift"] = shift
                sz0 = T.RESTORATION_TILESIZE_MAX >> (2 - shift)
                uv = 0
                if s["subsampling_x"] and s["subsampling_y"] and chroma:
                    uv = b.f(1, "lr_uv_shift")
                h["LoopRestorationSize"] = [sz0, sz0 >> uv, sz0 >> uv]
        # read_tx_mode
        if h["CodedLossless"]:
            h["TxMode"] = T.ONLY_4X4
        else:
            h["TxMode"] = T.TX_MODE_SELECT if r("tx_mode_select", 1) else T.TX_MODE_LARGEST
        r("reduced_tx_set", 1)
        # film_grain_params
        g = dict(apply_grain=0)
        if s["film_grain_params_present"] and (h["show_frame"] or h["showable_frame"]):
            if b.f(1, "apply_grain"):
                g["apply_grain"] = 1

                def gr(name, n):
                    g[name] = b.f(n, name)
                    return g[name]
                gr("grain_seed", 16)
                g["update_grain"] = 1
                mono = s["mono_chrome"]
                for c in ("y", "cb", "cr"):
                    g[f"point_{c}_value"], g[f"point_{c}_scaling"] = [], []

                def points(c):
                    n = gr(f"num_{c}_points", 4)
                    for i in range(n):
                        g[f"point_{c}_value"].append(b.f(8, f"point_{c}_value[{i}]"))
                        g[f"point_{c}_scaling"].append(b.f(8, f"point_{c}_scaling[{i}]"))
                points("y")
                g["chroma_scaling_from_luma"] = 0 if mono else gr("chroma_scaling_from_luma", 1)
                if mono or g["chroma_scaling_from_luma"] or (
                        s["subsampling_x"] == 1 and s["subsampling_y"] == 1 and g["num_y_points"] == 0):
                    g["num_cb_points"] = g["num_cr_points"] = 0
                else:
                    points("cb")
                    points("cr")
                gr("grain_scaling_minus_8", 2)
                lag = gr("ar_coeff_lag", 2)
                npl = 2 * lag * (lag + 1)
                g["ar_coeffs_y_plus_128"] = [0] * 24
                g["ar_coeffs_cb_plus_128"] = [0] * 25
                g["ar_coeffs_cr_plus_128"] = [0] * 25
                if g["num_y_points"]:
                    npc = npl + 1
                    for i in range(npl):
                        g["ar_coeffs_y_plus_128"][i] = b.f(8, f"ar_coeffs_y_plus_128[{i}]")
                else:
                    npc = npl
                for c in ("cb", "cr"):
                    if g["chroma_scaling_from_luma"] or g[f"num_{c}_points"]:
                        for i in range(npc):
                            g[f"ar_coeffs_{c}_plus_128"][i] = b.f(8, f"ar_coeffs_{c}_plus_128[{i}]")
                gr("ar_coeff_shift_minus_6", 2)
                gr("grain_scale_shift", 2)
                for c in ("cb", "cr"):
                    if g[f"num_{c}_points"]:
                        gr(f"{c}_mult", 8)
                        gr(f"{c}_luma_mult", 8)
                        gr(f"{c}_offset", 9)
                gr("overlap_flag", 1)
                gr("clip_to_restricted_range", 1)
        h["film_grain"] = g
        self.frame = h

    # ---------------- 毎フレームの変数

    def _set_frame_vars(self):
        s, h = self.seq, self.frame
        self.bd = s["BitDepth"]
        self.subx, self.suby = s["subsampling_x"], s["subsampling_y"]
        self.nplanes = s["NumPlanes"]
        self.MiRows, self.MiCols = h["MiRows"], h["MiCols"]
        self.sb128 = s["use_128x128_superblock"]

    def get_qindex(self, ignore_delta, seg):
        h = self.frame
        if h["segmentation_enabled"] and h["FeatureEnabled"][seg][0]:
            q = h["base_q_idx"] + h["FeatureData"][seg][0]
            if not ignore_delta and h["delta_q_present"]:
                q = self.CurrentQIndex + h["FeatureData"][seg][0]
            return clip3(0, 255, q)
        if not ignore_delta and h["delta_q_present"]:
            return self.CurrentQIndex
        return h["base_q_idx"]

    # ---------------- tile group

    def _alloc(self):
        """フレーム全体の配列を用意する (タイルの読み取りの前に 1 度)"""
        if hasattr(self, "F"):
            return
        sbpx = 128 if self.sb128 else 64
        H = ((self.MiRows * 4 + sbpx - 1) // sbpx) * sbpx + 160
        W = ((self.MiCols * 4 + sbpx - 1) // sbpx) * sbpx + 160
        self.F = [np.zeros((H >> (p and self.suby), W >> (p and self.subx)), np.int32)
                  for p in range(self.nplanes)]
        self.P = [a.copy() for a in self.F]   # 予想だけ
        R, C = self.MiRows + 40, self.MiCols + 40
        z = lambda: np.zeros((R, C), np.int32)  # noqa: E731
        self.YModes, self.UVModes, self.MiSizes, self.Skips = z(), z(), z(), z()
        self.TxSizes, self.InterTxSizes, self.SegmentIds = z(), z(), z()
        self.PaletteSizes = [z(), z()]
        self.PaletteColors = [{}, {}]   # (row, col) → list。ブロックの左上だけでなく覆う全部の 4×4 に
        self.DeltaLFs = np.zeros((R, C, 4), np.int32)
        self.LfTxSizes = [z() for _ in range(3)]
        self.TxTypes = z()
        self.cdef_idx = {}
        self.LrType = [dict() for _ in range(3)]
        self.LrWiener = [dict() for _ in range(3)]
        self.LrSgrSet = [dict() for _ in range(3)]
        self.LrSgrXqd = [dict() for _ in range(3)]
        self.tile_of_mi = z()
        self.tile_index = 0

    def tile_group(self, b, sz):
        h = self.frame
        self._alloc()
        NumTiles = h["TileCols"] * h["TileRows"]
        start = b.p
        flag = 0
        if NumTiles > 1:
            flag = b.f(1, "tile_start_and_end_present_flag")
        if NumTiles == 1 or not flag:
            tg_start, tg_end = 0, NumTiles - 1
        else:
            nb = h["TileColsLog2"] + h["TileRowsLog2"]
            tg_start = b.f(nb, "tg_start")
            tg_end = b.f(nb, "tg_end")
        b.byte_alignment()
        sz -= (b.p - start) // 8
        h.setdefault("tiles", [])
        for tn in range(tg_start, tg_end + 1):
            trow, tcol = divmod(tn, h["TileCols"])
            if tn == tg_end:
                tsize = sz
            else:
                tsize = b.le(h["TileSizeBytes"], f"tile_size_minus_1[{tn}]") + 1
                sz -= tsize + h["TileSizeBytes"]
            self.MiRowStart, self.MiRowEnd = h["MiRowStarts"][trow], h["MiRowStarts"][trow + 1]
            self.MiColStart, self.MiColEnd = h["MiColStarts"][tcol], h["MiColStarts"][tcol + 1]
            self.CurrentQIndex = h["base_q_idx"]
            pos = b.p // 8
            h["tiles"].append(dict(index=tn, row=trow, col=tcol, x=self.MiColStart * 4, y=self.MiRowStart * 4,
                                   x1=self.MiColEnd * 4, y1=self.MiRowEnd * 4, size=tsize,
                                   pos=None if b.base is None else b.base // 8 + pos))
            self.sd = SymbolDecoder(b.d, pos, tsize, b.base, h["disable_cdf_update"], self.symbols)
            self.cdf = default_cdfs(h["base_q_idx"])
            self.tile_index = tn
            self.decode_tile()
            b.p += tsize * 8

    # ---------------- 記号の読み取り (CDF の選び方 8.3.2)

    def S(self, name, cdfname, *idx):
        c = self.cdf[cdfname]
        for i in idx:
            c = c[i]
        return self.sd.symbol(c, name, (cdfname,) + idx)

    def L(self, n, name):
        return self.sd.literal(n, name)

    def initial_cdf(self, key):
        """symbols の key → その CDF の最初の値 (tuple、最後の数えを除く)"""
        if key is None:
            return (16384, 32768)
        name = key[0]
        if name.startswith("split_or_"):
            pc = self.initial_cdf(key[1:3])
            return split_cdf(list(pc) + [0], name, key[-1])[:-1]
        if name in NONCOEF:
            c = getattr(T, NONCOEF[name])
        elif name == "DeltaLFMulti":
            c = [T.Default_Delta_Lf_Cdf] * 4
        else:
            q = self.frame["base_q_idx"]
            c = getattr(T, COEF[name])[0 if q <= 20 else 1 if q <= 60 else 2 if q <= 120 else 3]
        for i in key[1:]:
            c = c[i]
        return tuple(c[:-1])

    # ---------------- タイル

    def is_inside(self, r, c):
        return self.MiColStart <= c < self.MiColEnd and self.MiRowStart <= r < self.MiRowEnd

    def decode_tile(self):
        np_ = self.nplanes
        n = self.MiCols + 64
        self.AboveLevel = [[0] * n for _ in range(3)]
        self.AboveDc = [[0] * n for _ in range(3)]
        self.DeltaLF = [0, 0, 0, 0]
        self.RefSgrXqd = [[-32, 31] for _ in range(np_)]
        self.RefLrWiener = [[[3, -7, 15], [3, -7, 15]] for _ in range(np_)]
        sbSize = T.BLOCK_128X128 if self.sb128 else T.BLOCK_64X64
        s4 = T.Num_4x4_Blocks_Wide[sbSize]
        m = self.MiRows + 64
        for r in range(self.MiRowStart, self.MiRowEnd, s4):
            self.LeftLevel = [[0] * m for _ in range(3)]
            self.LeftDc = [[0] * m for _ in range(3)]
            for c in range(self.MiColStart, self.MiColEnd, s4):
                self.ReadDeltas = self.frame["delta_q_present"]
                self.cdef_idx[(r, c)] = -1
                if self.sb128:
                    for dr, dc in ((0, 16), (16, 0), (16, 16)):
                        self.cdef_idx[(r + dr, c + dc)] = -1
                self.clear_block_decoded(r, c, s4)
                self.read_lr(r, c, sbSize)
                self.decode_partition(r, c, sbSize)

    def clear_block_decoded(self, r, c, s4):
        self.BD = []
        for plane in range(self.nplanes):
            sx = self.subx if plane else 0
            sy = self.suby if plane else 0
            sw = (self.MiColEnd - c) >> sx
            sh = (self.MiRowEnd - r) >> sy
            g = [[0] * 36 for _ in range(36)]   # [y + 1][x + 1]
            for y in range(-1, (s4 >> sy) + 1):
                for x in range(-1, (s4 >> sx) + 1):
                    if y < 0 and x < sw:
                        g[y + 1][x + 1] = 1
                    elif x < 0 and y < sh:
                        g[y + 1][x + 1] = 1
            g[(s4 >> sy) + 1][0] = 0
            self.BD.append(g)

    # ---------------- ループ復元の読み取り

    def read_lr(self, r, c, bSize):
        h = self.frame
        if h["allow_intrabc"]:
            return
        w = T.Num_4x4_Blocks_Wide[bSize]
        hh = T.Num_4x4_Blocks_High[bSize]
        for plane in range(self.nplanes):
            if h["FrameRestorationType"][plane] == T.RESTORE_NONE:
                continue
            sx = self.subx if plane else 0
            sy = self.suby if plane else 0
            us = h["LoopRestorationSize"][plane]
            rows = max((round2(h["FrameHeight"], sy) + (us >> 1)) // us, 1)
            cols = max((round2(h["UpscaledWidth"], sx) + (us >> 1)) // us, 1)
            r0 = (r * (4 >> sy) + us - 1) // us
            r1 = min(rows, ((r + hh) * (4 >> sy) + us - 1) // us)
            if h["use_superres"]:
                num = (4 >> sx) * h["SuperresDenom"]
                den = us * 8
            else:
                num, den = 4 >> sx, us
            c0 = (c * num + den - 1) // den
            c1 = min(cols, ((c + w) * num + den - 1) // den)
            for ur in range(r0, r1):
                for uc in range(c0, c1):
                    self.read_lr_unit(plane, ur, uc)

    def subexp_bool(self, numSyms, k, name):
        i = mk = 0
        while True:
            b2 = k + i - 1 if i else k
            a = 1 << b2
            if numSyms <= mk + 3 * a:
                return self.sd.ns(numSyms - mk, name) + mk
            if self.L(1, name):
                i += 1
                mk += a
            else:
                return self.L(b2, name) + mk

    def signed_subexp_ref(self, low, high, k, r, name):
        mx = high - low
        r -= low
        v = self.subexp_bool(mx, k, name)
        if (r << 1) <= mx:
            x = inverse_recenter(r, v)
        else:
            x = mx - 1 - inverse_recenter(mx - 1 - r, v)
        return x + low

    def read_lr_unit(self, plane, ur, uc):
        ft = self.frame["FrameRestorationType"][plane]
        if ft == T.RESTORE_WIENER:
            rt = T.RESTORE_WIENER if self.S("use_wiener", "UseWiener") else T.RESTORE_NONE
        elif ft == T.RESTORE_SGRPROJ:
            rt = T.RESTORE_SGRPROJ if self.S("use_sgrproj", "UseSgrproj") else T.RESTORE_NONE
        else:
            rt = self.S("restoration_type", "RestorationType")
        self.LrType[plane][(ur, uc)] = rt
        rec = dict(plane=plane, row=ur, col=uc, type=rt)
        if rt == T.RESTORE_WIENER:
            coef = []
            for ps in range(2):
                cc = [0, 0, 0]
                for j in range(1 if plane else 0, 3):
                    v = self.signed_subexp_ref(T.Wiener_Taps_Min[j], T.Wiener_Taps_Max[j] + 1, T.Wiener_Taps_K[j],
                                               self.RefLrWiener[plane][ps][j], "lr_wiener")
                    cc[j] = v
                    self.RefLrWiener[plane][ps][j] = v
                coef.append(cc)
            self.LrWiener[plane][(ur, uc)] = coef
            rec["wiener"] = coef
        elif rt == T.RESTORE_SGRPROJ:
            st = self.L(T.SGRPROJ_PARAMS_BITS, "lr_sgr_set")
            self.LrSgrSet[plane][(ur, uc)] = st
            xq = [0, 0]
            for i in range(2):
                radius = T.Sgr_Params[st][i * 2]
                mn, mxv = T.Sgrproj_Xqd_Min[i], T.Sgrproj_Xqd_Max[i]
                if radius:
                    v = self.signed_subexp_ref(mn, mxv + 1, T.SGRPROJ_PRJ_SUBEXP_K, self.RefSgrXqd[plane][i],
                                               "lr_sgrproj_xqd")
                else:
                    v = 0
                    if i == 1:
                        v = clip3(mn, mxv, (1 << T.SGRPROJ_PRJ_BITS) - self.RefSgrXqd[plane][0])
                xq[i] = v
                self.RefSgrXqd[plane][i] = v
            self.LrSgrXqd[plane][(ur, uc)] = xq
            rec.update(sgr_set=st, xqd=xq)
        self.lr_units.append(rec)

    # ---------------- 区切り

    def decode_partition(self, r, c, bSize):
        if r >= self.MiRows or c >= self.MiCols:
            return
        availU = self.is_inside(r - 1, c)
        availL = self.is_inside(r, c - 1)
        num4 = T.Num_4x4_Blocks_Wide[bSize]
        half = num4 >> 1
        quarter = half >> 1
        hasRows = (r + half) < self.MiRows
        hasCols = (c + half) < self.MiCols
        coded = "symbol"
        if bSize < T.BLOCK_8X8:
            partition = T.PARTITION_NONE
            coded = "implied"
        else:
            bsl = T.Mi_Width_Log2[bSize]
            above = availU and T.Mi_Width_Log2[self.MiSizes[r - 1, c]] < bsl
            left = availL and T.Mi_Height_Log2[self.MiSizes[r, c - 1]] < bsl
            ctx = int(left) * 2 + int(above)
            cname = {1: "PartitionW8", 2: "PartitionW16", 3: "PartitionW32", 4: "PartitionW64",
                     5: "PartitionW128"}[bsl]
            if hasRows and hasCols:
                partition = self.S("partition", cname, ctx)
            elif hasCols:
                cdf = split_cdf(self.cdf[cname][ctx], "split_or_horz", bSize)
                v = self.sd.symbol(cdf, "split_or_horz", ("split_or_horz", cname, ctx, bSize))
                partition = T.PARTITION_SPLIT if v else T.PARTITION_HORZ
                coded = "split_or_horz"
            elif hasRows:
                cdf = split_cdf(self.cdf[cname][ctx], "split_or_vert", bSize)
                v = self.sd.symbol(cdf, "split_or_vert", ("split_or_vert", cname, ctx, bSize))
                partition = T.PARTITION_SPLIT if v else T.PARTITION_VERT
                coded = "split_or_vert"
            else:
                partition = T.PARTITION_SPLIT
                coded = "implied"
        self.partitions.append(dict(x=c * 4, y=r * 4, size=BW[bSize], bsize=bSize, partition=partition,
                                    coded=coded))
        sub = T.Partition_Subsize[partition][bSize]
        split = T.Partition_Subsize[T.PARTITION_SPLIT][bSize]
        db = self.decode_block
        if partition == T.PARTITION_NONE:
            db(r, c, sub)
        elif partition == T.PARTITION_HORZ:
            db(r, c, sub)
            if hasRows:
                db(r + half, c, sub)
        elif partition == T.PARTITION_VERT:
            db(r, c, sub)
            if hasCols:
                db(r, c + half, sub)
        elif partition == T.PARTITION_SPLIT:
            self.decode_partition(r, c, sub)
            self.decode_partition(r, c + half, sub)
            self.decode_partition(r + half, c, sub)
            self.decode_partition(r + half, c + half, sub)
        elif partition == T.PARTITION_HORZ_A:
            db(r, c, split)
            db(r, c + half, split)
            db(r + half, c, sub)
        elif partition == T.PARTITION_HORZ_B:
            db(r, c, sub)
            db(r + half, c, split)
            db(r + half, c + half, split)
        elif partition == T.PARTITION_VERT_A:
            db(r, c, split)
            db(r + half, c, split)
            db(r, c + half, sub)
        elif partition == T.PARTITION_VERT_B:
            db(r, c, sub)
            db(r, c + half, split)
            db(r + half, c + half, split)
        elif partition == T.PARTITION_HORZ_4:
            for k in range(4):
                if k < 3 or r + quarter * 3 < self.MiRows:
                    db(r + quarter * k, c, sub)
        else:
            for k in range(4):
                if k < 3 or c + quarter * 3 < self.MiCols:
                    db(r, c + quarter * k, sub)

    # ---------------- ブロック

    def plane_res_size(self, bsize, plane):
        sx = self.subx if plane else 0
        sy = self.suby if plane else 0
        return T.Subsampled_Size[bsize][sx][sy]

    def decode_block(self, r, c, sub):
        self.MiRow, self.MiCol, self.MiSize = r, c, sub
        bw4, bh4 = T.Num_4x4_Blocks_Wide[sub], T.Num_4x4_Blocks_High[sub]
        if bh4 == 1 and self.suby and (r & 1) == 0:
            hc = 0
        elif bw4 == 1 and self.subx and (c & 1) == 0:
            hc = 0
        else:
            hc = int(self.nplanes > 1)
        self.HasChroma = hc
        self.AvailU = self.is_inside(r - 1, c)
        self.AvailL = self.is_inside(r, c - 1)
        self.AvailUChroma, self.AvailLChroma = self.AvailU, self.AvailL
        if hc:
            if self.suby and bh4 == 1:
                self.AvailUChroma = self.is_inside(r - 2, c)
            if self.subx and bw4 == 1:
                self.AvailLChroma = self.is_inside(r, c - 2)
        else:
            self.AvailUChroma = self.AvailLChroma = False
        blk = dict(x=c * 4, y=r * 4, w=BW[sub], h=BH[sub], bsize=sub, has_chroma=hc, tile=self.tile_index)
        self.blk = blk
        self.intra_frame_mode_info(blk)
        self.palette_tokens()
        self.read_tx_size()
        if self.skip:
            self.reset_block_context(bw4, bh4)
        self.YModes[r:r + bh4, c:c + bw4] = self.YMode
        if hc:
            self.UVModes[r:r + bh4, c:c + bw4] = self.UVMode
        self.InterTxSizes[r:r + bh4, c:c + bw4] = self.TxSize
        blk.update(tx_size=self.TxSize, tx_w=TXW[self.TxSize], tx_h=TXH[self.TxSize])
        self.blocks.append(blk)
        self.residual()
        self.Skips[r:r + bh4, c:c + bw4] = self.skip
        self.TxSizes[r:r + bh4, c:c + bw4] = self.TxSize
        self.MiSizes[r:r + bh4, c:c + bw4] = sub
        self.SegmentIds[r:r + bh4, c:c + bw4] = self.segment_id
        self.PaletteSizes[0][r:r + bh4, c:c + bw4] = self.PaletteSizeY
        self.PaletteSizes[1][r:r + bh4, c:c + bw4] = self.PaletteSizeUV
        if self.PaletteSizeY or self.PaletteSizeUV:
            for yy in range(bh4):
                for xx in range(bw4):
                    self.PaletteColors[0][(r + yy, c + xx)] = self.palette_y
                    self.PaletteColors[1][(r + yy, c + xx)] = self.palette_u
        self.DeltaLFs[r:r + bh4, c:c + bw4] = self.DeltaLF
        self.tile_of_mi[r:r + bh4, c:c + bw4] = self.tile_index

    def reset_block_context(self, bw4, bh4):
        for plane in range(1 + 2 * self.HasChroma):
            sx = self.subx if plane else 0
            sy = self.suby if plane else 0
            for i in range(self.MiCol >> sx, (self.MiCol + bw4) >> sx):
                self.AboveLevel[plane][i] = 0
                self.AboveDc[plane][i] = 0
            for i in range(self.MiRow >> sy, (self.MiRow + bh4) >> sy):
                self.LeftLevel[plane][i] = 0
                self.LeftDc[plane][i] = 0

    def intra_frame_mode_info(self, blk):
        h = self.frame
        r, c = self.MiRow, self.MiCol
        self.skip = 0
        if h["SegIdPreSkip"]:
            self.intra_segment_id()
        # read_skip
        if h["SegIdPreSkip"] and self.seg_feature_active(T.SEG_LVL_SKIP):
            self.skip = 1
        else:
            ctx = 0
            if self.AvailU:
                ctx += self.Skips[r - 1, c]
            if self.AvailL:
                ctx += self.Skips[r, c - 1]
            self.skip = self.S("skip", "Skip", int(ctx))
        if not h["SegIdPreSkip"]:
            self.intra_segment_id()
        self.read_cdef()
        self.read_delta_qindex()
        self.read_delta_lf()
        self.ReadDeltas = 0
        if h["allow_intrabc"]:
            use = self.S("use_intrabc", "Intrabc")
            assert not use, "intrabc (画面内のコピー) には対応していない"
        abovemode = T.Intra_Mode_Context[self.YModes[r - 1, c] if self.AvailU else 0]
        leftmode = T.Intra_Mode_Context[self.YModes[r, c - 1] if self.AvailL else 0]
        self.YMode = self.S("intra_frame_y_mode", "IntraFrameYMode", abovemode, leftmode)
        self.AngleDeltaY = 0
        ms = self.MiSize
        if ms >= T.BLOCK_8X8 and 1 <= self.YMode <= 8:
            self.AngleDeltaY = self.S("angle_delta_y", "AngleDelta", self.YMode - 1) - 3
        self.UVMode = 0
        self.AngleDeltaUV = 0
        self.CflAlphaU = self.CflAlphaV = 0
        if self.HasChroma:
            if self.Lossless and self.plane_res_size(ms, 1) == T.BLOCK_4X4:
                cn = "UVModeCflAllowed"
            elif not self.Lossless and max(BW[ms], BH[ms]) <= 32:
                cn = "UVModeCflAllowed"
            else:
                cn = "UVModeCflNotAllowed"
            self.UVMode = self.S("uv_mode", cn, self.YMode)
            if self.UVMode == T.UV_CFL_PRED:
                signs = self.S("cfl_alpha_signs", "CflSign")
                sU, sV = (signs + 1) // 3, (signs + 1) % 3
                if sU:
                    a = 1 + self.S("cfl_alpha_u", "CflAlpha", (sU - 1) * 3 + sV)
                    self.CflAlphaU = -a if sU == T.CFL_SIGN_NEG else a
                if sV:
                    a = 1 + self.S("cfl_alpha_v", "CflAlpha", (sV - 1) * 3 + sU)
                    self.CflAlphaV = -a if sV == T.CFL_SIGN_NEG else a
            if ms >= T.BLOCK_8X8 and 1 <= self.UVMode <= 8:
                self.AngleDeltaUV = self.S("angle_delta_uv", "AngleDelta", self.UVMode - 1) - 3
        self.PaletteSizeY = self.PaletteSizeUV = 0
        self.palette_y = self.palette_u = self.palette_v = []
        if ms >= T.BLOCK_8X8 and BW[ms] <= 64 and BH[ms] <= 64 and h["allow_screen_content_tools"]:
            self.palette_mode_info()
        self.use_filter_intra = 0
        self.filter_intra_mode = 0
        if (self.seq["enable_filter_intra"] and self.YMode == 0 and self.PaletteSizeY == 0
                and max(BW[ms], BH[ms]) <= 32):
            self.use_filter_intra = self.S("use_filter_intra", "FilterIntra", ms)
            if self.use_filter_intra:
                self.filter_intra_mode = self.S("filter_intra_mode", "FilterIntraMode")
        blk.update(skip=self.skip, segment_id=self.segment_id, qindex=self.get_qindex(0, self.segment_id),
                   lossless=self.Lossless, y_mode=self.YMode, angle_delta_y=self.AngleDeltaY,
                   uv_mode=self.UVMode, angle_delta_uv=self.AngleDeltaUV, cfl_alpha_u=self.CflAlphaU,
                   cfl_alpha_v=self.CflAlphaV, use_filter_intra=self.use_filter_intra,
                   filter_intra_mode=self.filter_intra_mode, palette_size_y=self.PaletteSizeY,
                   palette_size_uv=self.PaletteSizeUV, palette_y=list(self.palette_y),
                   palette_u=list(self.palette_u), palette_v=list(self.palette_v),
                   cdef_idx=self.cdef_idx.get((r & ~15, c & ~15), -1), delta_lf=list(self.DeltaLF))

    def seg_feature_active(self, f):
        h = self.frame
        return h["segmentation_enabled"] and h["FeatureEnabled"][self.segment_id][f]

    def intra_segment_id(self):
        h = self.frame
        if h["segmentation_enabled"]:
            r, c = self.MiRow, self.MiCol
            U, Lf = self.AvailU, self.AvailL
            prevUL = int(self.SegmentIds[r - 1, c - 1]) if U and Lf else -1
            prevU = int(self.SegmentIds[r - 1, c]) if U else -1
            prevL = int(self.SegmentIds[r, c - 1]) if Lf else -1
            if prevU == -1:
                pred = 0 if prevL == -1 else prevL
            elif prevL == -1:
                pred = prevU
            else:
                pred = prevU if prevUL == prevU else prevL
            if self.skip:
                self.segment_id = pred
            else:
                if prevUL < 0:
                    ctx = 0
                elif prevUL == prevU and prevUL == prevL:
                    ctx = 2
                elif prevUL == prevU or prevUL == prevL or prevU == prevL:
                    ctx = 1
                else:
                    ctx = 0
                v = self.S("segment_id", "SegmentId", ctx)
                self.segment_id = neg_deinterleave(v, pred, h["LastActiveSegId"] + 1)
        else:
            self.segment_id = 0
        self.Lossless = self.LosslessArray[self.segment_id]

    def read_cdef(self):
        h = self.frame
        if self.skip or h["CodedLossless"] or not self.seq["enable_cdef"] or h["allow_intrabc"]:
            return
        r, c = self.MiRow & ~15, self.MiCol & ~15
        if self.cdef_idx[(r, c)] == -1:
            v = self.L(h["cdef_bits"], "cdef_idx")
            w4, h4 = T.Num_4x4_Blocks_Wide[self.MiSize], T.Num_4x4_Blocks_High[self.MiSize]
            for i in range(r, r + h4, 16):
                for j in range(c, c + w4, 16):
                    self.cdef_idx[(i, j)] = v
            self.cdef_idx[(r, c)] = v

    def read_delta_qindex(self):
        h = self.frame
        sbSize = T.BLOCK_128X128 if self.sb128 else T.BLOCK_64X64
        if self.MiSize == sbSize and self.skip:
            return
        if self.ReadDeltas:
            a = self.S("delta_q_abs", "DeltaQ")
            if a == T.DELTA_Q_SMALL:
                rb = self.L(3, "delta_q_rem_bits") + 1
                a = self.L(rb, "delta_q_abs_bits") + (1 << rb) + 1
            if a:
                sign = self.L(1, "delta_q_sign_bit")
                red = -a if sign else a
                self.CurrentQIndex = clip3(1, 255, self.CurrentQIndex + (red << h["delta_q_res"]))

    def read_delta_lf(self):
        h = self.frame
        sbSize = T.BLOCK_128X128 if self.sb128 else T.BLOCK_64X64
        if self.MiSize == sbSize and self.skip:
            return
        if self.ReadDeltas and h["delta_lf_present"]:
            cnt = 1
            if h["delta_lf_multi"]:
                cnt = T.FRAME_LF_COUNT if self.nplanes > 1 else T.FRAME_LF_COUNT - 2
            for i in range(cnt):
                if h["delta_lf_multi"]:
                    a = self.S("delta_lf_abs", "DeltaLFMulti", i)
                else:
                    a = self.S("delta_lf_abs", "DeltaLF")
                if a == T.DELTA_LF_SMALL:
                    n = self.L(3, "delta_lf_rem_bits") + 1
                    a = self.L(n, "delta_lf_abs_bits") + (1 << n) + 1
                if a:
                    sign = self.L(1, "delta_lf_sign_bit")
                    red = -a if sign else a
                    self.DeltaLF[i] = clip3(-63, 63, self.DeltaLF[i] + (red << h["delta_lf_res"]))

    # ---------------- パレット

    def get_palette_cache(self, plane):
        r, c = self.MiRow, self.MiCol
        aboveN = int(self.PaletteSizes[plane][r - 1, c]) if (r * 4) % 64 else 0
        leftN = int(self.PaletteSizes[plane][r, c - 1]) if self.AvailL else 0
        ab = self.PaletteColors[plane].get((r - 1, c), []) if aboveN else []
        lf = self.PaletteColors[plane].get((r, c - 1), []) if leftN else []
        ab, lf = ab[:aboveN], lf[:leftN]
        ai = li = 0
        cache = []
        while ai < aboveN and li < leftN:
            aC, lC = ab[ai], lf[li]
            if lC < aC:
                if not cache or lC != cache[-1]:
                    cache.append(lC)
                li += 1
            else:
                if not cache or aC != cache[-1]:
                    cache.append(aC)
                ai += 1
                if lC == aC:
                    li += 1
        for v in ab[ai:]:
            if not cache or v != cache[-1]:
                cache.append(v)
        for v in lf[li:]:
            if not cache or v != cache[-1]:
                cache.append(v)
        return cache

    def palette_mode_info(self):
        ms = self.MiSize
        r, c = self.MiRow, self.MiCol
        bd = self.bd
        mx = (1 << bd) - 1
        bctx = T.Mi_Width_Log2[ms] + T.Mi_Height_Log2[ms] - 2
        if self.YMode == 0:
            ctx = 0
            if self.AvailU and self.PaletteSizes[0][r - 1, c] > 0:
                ctx += 1
            if self.AvailL and self.PaletteSizes[0][r, c - 1] > 0:
                ctx += 1
            if self.S("has_palette_y", "PaletteYMode", bctx, ctx):
                n = self.S("palette_size_y_minus_2", "PaletteYSize", bctx) + 2
                self.PaletteSizeY = n
                cache = self.get_palette_cache(0)
                cols = []
                for i in range(len(cache)):
                    if len(cols) >= n:
                        break
                    if self.L(1, "use_palette_color_cache_y"):
                        cols.append(cache[i])
                if len(cols) < n:
                    cols.append(self.L(bd, "palette_colors_y"))
                if len(cols) < n:
                    pbits = bd - 3 + self.L(2, "palette_num_extra_bits_y")
                while len(cols) < n:
                    d = self.L(pbits, "palette_delta_y") + 1
                    v = clip3(0, mx, cols[-1] + d)
                    cols.append(v)
                    rng = (1 << bd) - v - 1
                    pbits = min(pbits, ceillog2(rng))
                self.palette_y = sorted(cols)
        if self.HasChroma and self.UVMode == 0:
            if self.S("has_palette_uv", "PaletteUVMode", 1 if self.PaletteSizeY > 0 else 0):
                n = self.S("palette_size_uv_minus_2", "PaletteUVSize", bctx) + 2
                self.PaletteSizeUV = n
                cache = self.get_palette_cache(1)
                cols = []
                for i in range(len(cache)):
                    if len(cols) >= n:
                        break
                    if self.L(1, "use_palette_color_cache_u"):
                        cols.append(cache[i])
                if len(cols) < n:
                    cols.append(self.L(bd, "palette_colors_u"))
                if len(cols) < n:
                    pbits = bd - 3 + self.L(2, "palette_num_extra_bits_u")
                while len(cols) < n:
                    d = self.L(pbits, "palette_delta_u")
                    v = clip3(0, mx, cols[-1] + d)
                    cols.append(v)
                    rng = (1 << bd) - v
                    pbits = min(pbits, ceillog2(rng))
                self.palette_u = sorted(cols)
                vv = []
                if self.L(1, "delta_encode_palette_colors_v"):
                    maxv = 1 << bd
                    pbits = bd - 4 + self.L(2, "palette_num_extra_bits_v")
                    vv.append(self.L(bd, "palette_colors_v"))
                    for i in range(1, n):
                        d = self.L(pbits, "palette_delta_v")
                        if d and self.L(1, "palette_delta_sign_bit_v"):
                            d = -d
                        v = vv[-1] + d
                        if v < 0:
                            v += maxv
                        if v >= maxv:
                            v -= maxv
                        vv.append(clip3(0, mx, v))
                else:
                    for i in range(n):
                        vv.append(self.L(bd, "palette_colors_v"))
                self.palette_v = vv

    def palette_tokens(self):
        ms = self.MiSize
        bh, bw = BH[ms], BW[ms]
        onh = min(bh, (self.MiRows - self.MiRow) * 4)
        onw = min(bw, (self.MiCols - self.MiCol) * 4)
        self.ColorMapY = self.ColorMapUV = None
        if self.PaletteSizeY:
            self.ColorMapY = self._color_map(self.PaletteSizeY, bh, bw, onh, onw, "Y")
        if self.PaletteSizeUV:
            bh >>= self.suby
            bw >>= self.subx
            onh >>= self.suby
            onw >>= self.subx
            if bw < 4:
                bw += 2
                onw += 2
            if bh < 4:
                bh += 2
                onh += 2
            self.ColorMapUV = self._color_map(self.PaletteSizeUV, bh, bw, onh, onw, "UV")

    def _color_map(self, n, bh, bw, onh, onw, pl):
        m = [[0] * bw for _ in range(bh)]
        m[0][0] = self.sd.ns(n, f"color_index_map_{pl.lower()}")
        cname = f"PaletteSize{n}{pl}Color"
        for i in range(1, onh + onw - 1):
            for j in range(min(i, onw - 1), max(0, i - onh + 1) - 1, -1):
                rr, cc = i - j, j
                scores = [0] * 8
                order = list(range(8))
                if cc > 0:
                    scores[m[rr][cc - 1]] += 2
                if rr > 0 and cc > 0:
                    scores[m[rr - 1][cc - 1]] += 1
                if rr > 0:
                    scores[m[rr - 1][cc]] += 2
                for k in range(3):
                    best, bi = scores[k], k
                    for t in range(k + 1, n):
                        if scores[t] > best:
                            best, bi = scores[t], t
                    if bi != k:
                        bo = order[bi]
                        for t in range(bi, k, -1):
                            scores[t] = scores[t - 1]
                            order[t] = order[t - 1]
                        scores[k] = best
                        order[k] = bo
                hsh = scores[0] * 1 + scores[1] * 2 + scores[2] * 2
                ctx = T.Palette_Color_Context[hsh]
                v = self.S(f"palette_color_idx_{pl.lower()}", cname, ctx)
                m[rr][cc] = order[v]
        for i in range(onh):
            for j in range(onw, bw):
                m[i][j] = m[i][onw - 1]
        for i in range(onh, bh):
            m[i] = list(m[onh - 1])
        return np.array(m, np.int64)

    # ---------------- 変換の大きさ

    def read_tx_size(self):
        ms = self.MiSize
        if self.Lossless:
            self.TxSize = T.TX_4X4
            return
        maxRect = T.Max_Tx_Size_Rect[ms]
        maxDepth = T.Max_Tx_Depth[ms]
        self.TxSize = maxRect
        if ms > T.BLOCK_4X4 and self.frame["TxMode"] == T.TX_MODE_SELECT:
            r, c = self.MiRow, self.MiCol
            aboveW = TXW[self.InterTxSizes[r - 1, c]] if self.AvailU else 0
            leftH = TXH[self.InterTxSizes[r, c - 1]] if self.AvailL else 0
            ctx = int(aboveW >= TXW[maxRect]) + int(leftH >= TXH[maxRect])
            cn = {4: "Tx64x64", 3: "Tx32x32", 2: "Tx16x16"}.get(maxDepth, "Tx8x8")
            d = self.S("tx_depth", cn, ctx)
            for _ in range(d):
                self.TxSize = T.Split_Tx_Size[self.TxSize]

    # ---------------- 残差

    def get_tx_size(self, plane, txSz):
        if plane == 0:
            return txSz
        uv = T.Max_Tx_Size_Rect[self.plane_res_size(self.MiSize, plane)]
        if TXW[uv] == 64 or TXH[uv] == 64:
            if TXW[uv] == 16:
                return T.TX_16X32
            if TXH[uv] == 16:
                return T.TX_32X16
            return T.TX_32X32
        return uv

    def residual(self):
        ms = self.MiSize
        wc = max(1, BW[ms] >> 6)
        hc = max(1, BH[ms] >> 6)
        msc = T.BLOCK_64X64 if (wc > 1 or hc > 1) else ms
        for cy in range(hc):
            for cx in range(wc):
                for plane in range(1 + self.HasChroma * 2):
                    txSz = T.TX_4X4 if self.Lossless else self.get_tx_size(plane, self.TxSize)
                    stepX, stepY = TXW[txSz] >> 2, TXH[txSz] >> 2
                    psz = self.plane_res_size(msc, plane)
                    n4w, n4h = T.Num_4x4_Blocks_Wide[psz], T.Num_4x4_Blocks_High[psz]
                    sx = self.subx if plane else 0
                    sy = self.suby if plane else 0
                    bx = (self.MiCol >> sx) * 4
                    by = (self.MiRow >> sy) * 4
                    for y in range(0, n4h, stepY):
                        for x in range(0, n4w, stepX):
                            self.transform_block(plane, bx, by, txSz, x + ((cx << 4) >> sx), y + ((cy << 4) >> sy))

    def transform_block(self, plane, baseX, baseY, txSz, x, y):
        startX, startY = baseX + 4 * x, baseY + 4 * y
        sx = self.subx if plane else 0
        sy = self.suby if plane else 0
        row = (startY << sy) >> 2
        col = (startX << sx) >> 2
        mask = 31 if self.sb128 else 15
        sbr, sbc = row & mask, col & mask
        stepX, stepY = TXW[txSz] >> 2, TXH[txSz] >> 2
        maxX = (self.MiCols * 4) >> sx
        maxY = (self.MiRows * 4) >> sy
        if startX >= maxX or startY >= maxY:
            return
        w, h = TXW[txSz], TXH[txSz]
        F = self.F[plane]
        rec = dict(plane=plane, x=startX, y=startY, w=w, h=h, tx_size=txSz, skip=self.skip, tx_type=None, eob=0,
                   levels=None, dequant=None, resid=None, pred=None)
        if (plane == 0 and self.PaletteSizeY) or (plane and self.PaletteSizeUV):
            pal = self.palette_y if plane == 0 else (self.palette_u if plane == 1 else self.palette_v)
            m = self.ColorMapY if plane == 0 else self.ColorMapUV
            F[startY:startY + h, startX:startX + w] = np.array(pal, np.int64)[m[y * 4:y * 4 + h, x * 4:x * 4 + w]]
            rec["pred"] = dict(plane=plane, palette=list(pal), x=startX, y=startY, w=w, h=h)
        else:
            isCfl = plane > 0 and self.UVMode == T.UV_CFL_PRED
            mode = self.YMode if plane == 0 else (0 if isCfl else self.UVMode)
            BD = self.BD[plane]
            haveL = (self.AvailL if plane == 0 else self.AvailLChroma) or x > 0
            haveA = (self.AvailU if plane == 0 else self.AvailUChroma) or y > 0
            haveAR = BD[(sbr >> sy) - 1 + 1][(sbc >> sx) + stepX + 1]
            haveBL = BD[(sbr >> sy) + stepY + 1][(sbc >> sx) - 1 + 1]
            p = dict(plane=plane, x=startX, y=startY, haveLeft=bool(haveL), haveAbove=bool(haveA),
                     haveAboveRight=bool(haveAR), haveBelowLeft=bool(haveBL), mode=mode,
                     log2W=T.Tx_Width_Log2[txSz], log2H=T.Tx_Height_Log2[txSz], maxX=maxX - 1, maxY=maxY - 1,
                     bd=self.bd, angle_delta=self.AngleDeltaY if plane == 0 else self.AngleDeltaUV,
                     use_filter_intra=self.use_filter_intra if plane == 0 else 0,
                     filter_intra_mode=self.filter_intra_mode, edge_filter=self.seq["enable_intra_edge_filter"],
                     filter_type=self.get_filter_type(plane) if 1 <= mode <= 8 else 0)
            F[startY:startY + h, startX:startX + w] = intra_predict(F, p)
            if isCfl:
                alpha = self.CflAlphaU if plane == 1 else self.CflAlphaV
                p.update(cfl_alpha=alpha, max_luma_w=self.MaxLumaW, max_luma_h=self.MaxLumaH,
                         subx=self.subx, suby=self.suby)
                F[startY:startY + h, startX:startX + w] = cfl_predict(self.F[0], F, p)
            rec["pred"] = p
        if plane == 0:
            self.MaxLumaW = startX + stepX * 4
            self.MaxLumaH = startY + stepY * 4
        self.P[plane][startY:startY + h, startX:startX + w] = F[startY:startY + h, startX:startX + w]
        if not self.skip:
            eob = self.coeffs(plane, startX, startY, txSz, rec)
            if eob > 0:
                self.reconstruct(plane, startX, startY, txSz, rec)
        self.LfTxSizes[plane][(row >> sy):(row >> sy) + stepY, (col >> sx):(col >> sx) + stepX] = txSz
        BD = self.BD[plane]
        for i in range(stepY):
            rr = BD[(sbr >> sy) + i + 1]
            for j in range(stepX):
                rr[(sbc >> sx) + j + 1] = 1
        self.txbs.append(rec)

    def get_filter_type(self, plane):
        r, c = self.MiRow, self.MiCol

        def smooth(rr, cc):
            m = self.YModes[rr, cc] if plane == 0 else self.UVModes[rr, cc]
            return m in (9, 10, 11)
        a = l_ = False
        if self.AvailU if plane == 0 else self.AvailUChroma:
            rr, cc = r - 1, c
            if plane > 0:
                if self.subx and not (c & 1):
                    cc += 1
                if self.suby and (r & 1):
                    rr -= 1
            a = smooth(rr, cc)
        if self.AvailL if plane == 0 else self.AvailLChroma:
            rr, cc = r, c - 1
            if plane > 0:
                if self.subx and (c & 1):
                    cc -= 1
                if self.suby and not (r & 1):
                    rr += 1
            l_ = smooth(rr, cc)
        return int(a or l_)

    # ---------------- 係数

    def get_tx_set(self, txSz):
        sq, up = T.Tx_Size_Sqr[txSz], T.Tx_Size_Sqr_Up[txSz]
        if up > T.TX_32X32:
            return TX_SET_DCTONLY
        if up == T.TX_32X32:
            return TX_SET_DCTONLY
        if self.frame["reduced_tx_set"]:
            return T.TX_SET_INTRA_2
        if sq == T.TX_16X16:
            return T.TX_SET_INTRA_2
        return T.TX_SET_INTRA_1

    def compute_tx_type(self, plane, txSz, bx, by):
        if self.Lossless or T.Tx_Size_Sqr_Up[txSz] > T.TX_32X32:
            return T.DCT_DCT
        st = self.get_tx_set(txSz)
        if plane == 0:
            return int(self.TxTypes[by, bx])
        t = T.Mode_To_Txfm[self.UVMode]
        return t if T.Tx_Type_In_Set_Intra[st][t] else T.DCT_DCT

    def coeffs(self, plane, startX, startY, txSz, rec):
        x4, y4 = startX >> 2, startY >> 2
        w4, h4 = TXW[txSz] >> 2, TXH[txSz] >> 2
        txSzCtx = (T.Tx_Size_Sqr[txSz] + T.Tx_Size_Sqr_Up[txSz] + 1) >> 1
        ptype = int(plane > 0)
        segEob = 512 if txSz in (T.TX_16X64, T.TX_64X16) else min(1024, TXW[txSz] * TXH[txSz])
        Quant = [0] * segEob
        eob = 0
        culLevel = 0
        dcCategory = 0
        # all_zero の文脈
        maxX4, maxY4 = self.MiCols, self.MiRows
        if plane > 0:
            maxX4 >>= self.subx
            maxY4 >>= self.suby
        w, h = TXW[txSz], TXH[txSz]
        AL, AD = self.AboveLevel[plane], self.AboveDc[plane]
        LL, LD = self.LeftLevel[plane], self.LeftDc[plane]
        bsize = self.plane_res_size(self.MiSize, plane)
        bw, bh = BW[bsize], BH[bsize]
        if plane == 0:
            top = left = 0
            for k in range(w4):
                if x4 + k < maxX4:
                    top = max(top, AL[x4 + k])
            for k in range(h4):
                if y4 + k < maxY4:
                    left = max(left, LL[y4 + k])
            top, left = min(top, 255), min(left, 255)
            if bw == w and bh == h:
                ctx = 0
            elif top == 0 and left == 0:
                ctx = 1
            elif top == 0 or left == 0:
                ctx = 2 + int(max(top, left) > 3)
            elif max(top, left) <= 3:
                ctx = 4
            elif min(top, left) <= 3:
                ctx = 5
            else:
                ctx = 6
        else:
            above = left = 0
            for i in range(w4):
                if x4 + i < maxX4:
                    above |= AL[x4 + i] | AD[x4 + i]
            for i in range(h4):
                if y4 + i < maxY4:
                    left |= LL[y4 + i] | LD[y4 + i]
            ctx = int(above != 0) + int(left != 0) + 7
            if bw * bh > w * h:
                ctx += 3
        all_zero = self.S("all_zero", "TxbSkip", txSzCtx, ctx)
        if all_zero:
            if plane == 0:
                self.TxTypes[y4:y4 + h4, x4:x4 + w4] = T.DCT_DCT
            self.PlaneTxType = T.DCT_DCT
        else:
            if plane == 0:
                self.transform_type(x4, y4, txSz)
            ptt = self.compute_tx_type(plane, txSz, x4, y4)
            self.PlaneTxType = ptt
            scan = get_scan(txSz, ptt)
            ems = min(T.Tx_Width_Log2[txSz], 5) + min(T.Tx_Height_Log2[txSz], 5) - 4
            txClass = tx_class(ptt)
            ectx = 0 if txClass == T.TX_CLASS_2D else 1
            if ems <= 4:
                nm = ["EobPt16", "EobPt32", "EobPt64", "EobPt128", "EobPt256"][ems]
                eobPt = self.S("eob_pt_" + nm[5:], nm, ptype, ectx) + 1
            elif ems == 5:
                eobPt = self.S("eob_pt_512", "EobPt512", ptype) + 1
            else:
                eobPt = self.S("eob_pt_1024", "EobPt1024", ptype) + 1
            eob = eobPt if eobPt < 2 else (1 << (eobPt - 2)) + 1
            eobShift = max(-1, eobPt - 3)
            if eobShift >= 0:
                if self.S("eob_extra", "EobExtra", txSzCtx, ptype, eobPt - 3):
                    eob += 1 << eobShift
                for i in range(1, max(0, eobPt - 2)):
                    eobShift = max(0, eobPt - 2) - 1 - i
                    if self.L(1, "eob_extra_bit"):
                        eob += 1 << eobShift
            adj = T.Adjusted_Tx_Size[txSz]
            bwl = T.Tx_Width_Log2[adj]
            width = 1 << bwl
            height = TXH[adj]
            offs = T.Sig_Ref_Diff_Offset[txClass]
            cbo = T.Coeff_Base_Ctx_Offset[txSz]
            mro = T.Mag_Ref_Offset_With_Tx_Class[txClass]
            brc = min(txSzCtx, T.TX_32X32)
            cBase = self.cdf["CoeffBase"][txSzCtx][ptype]
            cBr = self.cdf["CoeffBr"][brc][ptype]
            sym = self.sd.symbol
            for c in range(eob - 1, -1, -1):
                pos = scan[c]
                row = pos >> bwl
                col = pos - (row << bwl)
                if c == eob - 1:
                    if c == 0:
                        ctx = 0
                    elif c <= (height << bwl) // 8:
                        ctx = 1
                    elif c <= (height << bwl) // 4:
                        ctx = 2
                    else:
                        ctx = 3
                    level = self.S("coeff_base_eob", "CoeffBaseEob", txSzCtx, ptype, ctx) + 1
                else:
                    mag = 0
                    for dr, dc in offs:
                        rr, cc = row + dr, col + dc
                        if rr < height and cc < width:
                            q = Quant[(rr << bwl) + cc]
                            mag += q if q < 3 else 3
                    ctx = min((mag + 1) >> 1, 4)
                    if txClass == T.TX_CLASS_2D:
                        if row == 0 and col == 0:
                            ctx = 0
                        else:
                            ctx += cbo[min(row, 4)][min(col, 4)]
                    else:
                        idx = row if txClass == T.TX_CLASS_VERT else col
                        ctx += T.Coeff_Base_Pos_Ctx_Offset[min(idx, 2)]
                    level = sym(cBase[ctx], "coeff_base", ("CoeffBase", txSzCtx, ptype, ctx))
                if level > T.NUM_BASE_LEVELS:
                    mag = 0
                    for dr, dc in mro:
                        rr, cc = row + dr, col + dc
                        if rr < height and cc < width:
                            q = Quant[rr * width + cc]
                            mag += q if q < 15 else 15
                    mag = min((mag + 1) >> 1, 6)
                    if pos == 0:
                        ctx = mag
                    elif txClass == 0:
                        ctx = mag + 7 if (row < 2 and col < 2) else mag + 14
                    elif txClass == 1:
                        ctx = mag + 7 if col == 0 else mag + 14
                    else:
                        ctx = mag + 7 if row == 0 else mag + 14
                    for _ in range(T.COEFF_BASE_RANGE // (T.BR_CDF_SIZE - 1)):
                        br = sym(cBr[ctx], "coeff_br", ("CoeffBr", brc, ptype, ctx))
                        level += br
                        if br < T.BR_CDF_SIZE - 1:
                            break
                Quant[pos] = level
            for c in range(eob):
                pos = scan[c]
                if Quant[pos] != 0:
                    if c == 0:
                        dcs = 0
                        for k in range(w4):
                            if x4 + k < maxX4:
                                s_ = AD[x4 + k]
                                dcs += -1 if s_ == 1 else 1 if s_ == 2 else 0
                        for k in range(h4):
                            if y4 + k < maxY4:
                                s_ = LD[y4 + k]
                                dcs += -1 if s_ == 1 else 1 if s_ == 2 else 0
                        dctx = 1 if dcs < 0 else 2 if dcs > 0 else 0
                        sign = self.S("dc_sign", "DcSign", ptype, dctx)
                    else:
                        sign = self.L(1, "sign_bit")
                else:
                    sign = 0
                if Quant[pos] > T.NUM_BASE_LEVELS + T.COEFF_BASE_RANGE:
                    length = 0
                    while True:
                        length += 1
                        if self.L(1, "golomb_length_bit"):
                            break
                        assert length < 32
                    xv = 1
                    for i in range(length - 2, -1, -1):
                        xv = (xv << 1) | self.L(1, "golomb_data_bit")
                    Quant[pos] = xv + T.COEFF_BASE_RANGE + T.NUM_BASE_LEVELS
                if pos == 0 and Quant[pos] > 0:
                    dcCategory = 1 if sign else 2
                Quant[pos] &= 0xFFFFF
                culLevel += Quant[pos]
                if sign:
                    Quant[pos] = -Quant[pos]
            culLevel = min(63, culLevel)
        for i in range(w4):
            AL[x4 + i] = culLevel
            AD[x4 + i] = dcCategory
        for i in range(h4):
            LL[y4 + i] = culLevel
            LD[y4 + i] = dcCategory
        self.Quant = Quant
        rec["eob"] = eob
        rec["tx_type"] = self.PlaneTxType
        return eob

    def transform_type(self, x4, y4, txSz):
        st = self.get_tx_set(txSz)
        q = self.get_qindex(1, self.segment_id) if self.frame["segmentation_enabled"] else self.frame["base_q_idx"]
        if st > 0 and q > 0:
            intraDir = T.Filter_Intra_Mode_To_Intra_Dir[self.filter_intra_mode] if self.use_filter_intra \
                else self.YMode
            if st == T.TX_SET_INTRA_1:
                t = T.Tx_Type_Intra_Inv_Set1[self.S("intra_tx_type", "IntraTxTypeSet1", T.Tx_Size_Sqr[txSz],
                                                    intraDir)]
            else:
                t = T.Tx_Type_Intra_Inv_Set2[self.S("intra_tx_type", "IntraTxTypeSet2", T.Tx_Size_Sqr[txSz],
                                                    intraDir)]
        else:
            t = T.DCT_DCT
        self.TxTypes[y4:y4 + (TXH[txSz] >> 2), x4:x4 + (TXW[txSz] >> 2)] = t

    def reconstruct(self, plane, x, y, txSz, rec):
        h_ = self.frame
        bd = self.bd
        dqDenom = 2 if txSz in (T.TX_32X32, T.TX_16X32, T.TX_32X16, T.TX_16X64, T.TX_64X16) else \
            4 if txSz in (T.TX_64X64, T.TX_32X64, T.TX_64X32) else 1
        log2W, log2H = T.Tx_Width_Log2[txSz], T.Tx_Height_Log2[txSz]
        w, h = 1 << log2W, 1 << log2H
        tw, th = min(32, w), min(32, h)
        ptt = self.PlaneTxType
        flipUD = ptt in (T.FLIPADST_DCT, T.FLIPADST_ADST, T.V_FLIPADST, T.FLIPADST_FLIPADST)
        flipLR = ptt in (T.DCT_FLIPADST, T.ADST_FLIPADST, T.H_FLIPADST, T.FLIPADST_FLIPADST)
        qi = self.get_qindex(0, self.segment_id)
        bdi = (bd - 8) >> 1
        dq_ = {0: h_["DeltaQYDc"], 1: h_["DeltaQUDc"], 2: h_["DeltaQVDc"]}[plane]
        aq_ = {0: 0, 1: h_["DeltaQUAc"], 2: h_["DeltaQVAc"]}[plane]
        dcq = T.Dc_Qlookup[bdi][clip3(0, 255, qi + dq_)]
        acq = T.Ac_Qlookup[bdi][clip3(0, 255, qi + aq_)]
        Q = np.array(self.Quant[:tw * th], np.int64).reshape(th, tw)
        q = np.full((th, tw), acq, np.int64)
        q[0, 0] = dcq
        lvl = self.SegQMLevel[plane][self.segment_id]
        if h_["using_qmatrix"] and ptt < T.IDTX and lvl < 15:
            off = T.Qm_Offset[txSz]
            qm = np.array(T.Quantizer_Matrix[lvl][int(plane > 0)][off:off + tw * th], np.int64).reshape(th, tw)
            q = np_round2(q * qm, 5)
        dq = Q * q
        dq2 = np.sign(dq) * ((np.abs(dq) & 0xFFFFFF) // dqDenom)
        lim = 1 << (7 + bd)
        D = np.zeros((h, w), np.int64)
        D[:th, :tw] = np.clip(dq2, -lim, lim - 1)
        R = inverse_transform_2d(D, txSz, ptt, self.Lossless, bd)
        if flipUD:
            R = R[::-1, :]
        if flipLR:
            R = R[:, ::-1]
        F = self.F[plane]
        F[y:y + h, x:x + w] = np.clip(F[y:y + h, x:x + w] + R, 0, (1 << bd) - 1)
        rec.update(levels=Q.astype(np.int32), dequant=D[:th, :tw].astype(np.int32), resid=R.astype(np.int32))

    # ---------------- ループの中のフィルタと出力

    def finish(self):
        h = self.frame
        dt = np.uint8 if self.bd == 8 else np.uint16
        self.pred = [p.astype(dt) for p in self.P]
        self.recon = [p.astype(dt) for p in self.F]
        if h["loop_filter_level"][0] or h["loop_filter_level"][1]:
            self.loop_filter()
        self.deblocked = [p.astype(dt) for p in self.F]
        cdef = self.cdef_process()
        self.cdef = [p.astype(dt) for p in cdef]
        up_cdef = self.upscale(cdef)
        up_cur = self.upscale(self.F)
        self.upscaled = [p.astype(dt) for p in up_cdef] if h["use_superres"] else self.cdef
        lr = self.loop_restoration(up_cur, up_cdef)
        self.lr = [p.astype(dt) for p in lr]
        out = [p[:self.plane_h(i), :self.plane_w(i)].astype(np.int64) for i, p in enumerate(lr)]
        if h["film_grain"]["apply_grain"]:
            out = self.film_grain_synthesis(out)
        else:
            self.film_grain = dict(h["film_grain"])
        self.final = []
        for i, p in enumerate(self.lr):
            q = p.copy()
            q[:self.plane_h(i), :self.plane_w(i)] = out[i]
            self.final.append(q)

    def plane_w(self, plane):
        w = self.frame["UpscaledWidth"]
        return w if plane == 0 else (w + self.subx) >> self.subx

    def plane_h(self, plane):
        hh = self.frame["FrameHeight"]
        return hh if plane == 0 else (hh + self.suby) >> self.suby

    def crop(self, planes=None):
        """写真の大きさ (UpscaledWidth × FrameHeight、色は半分の切り上げ) に切った面の list"""
        planes = self.final if planes is None else planes
        return [p[:self.plane_h(i), :self.plane_w(i)] for i, p in enumerate(planes)]

    def intra_pred(self, txb, keep=None):
        """txbs の 1 つの予想を recon から作り直す (h×w の numpy)。keep に途中の値が入る"""
        p = txb["pred"]
        if "palette" in p:
            raise ValueError("パレットのブロック")
        F = self.recon[p["plane"]].astype(np.int64)
        out = intra_predict(F, p, keep)
        if "cfl_alpha" in p:
            G = F.copy()
            w, h = 1 << p["log2W"], 1 << p["log2H"]
            G[p["y"]:p["y"] + h, p["x"]:p["x"] + w] = out
            out = cfl_predict(self.recon[0].astype(np.int64), G, p, keep)
        return out

    # ---- デブロッキング (7.14)

    def lf_strength(self, row, col, plane, pss):
        h = self.frame
        seg = int(self.SegmentIds[row, col])
        i = pss if plane == 0 else plane + 1
        dl = int(self.DeltaLFs[row, col, i if h["delta_lf_multi"] else 0])
        key = (seg, dl, i)
        if key in self._lfc:
            return self._lfc[key]
        lvl = clip3(0, 63, dl + h["loop_filter_level"][i])
        feat = T.SEG_LVL_ALT_LF_Y_V + i
        if h["segmentation_enabled"] and h["FeatureEnabled"][seg][feat]:
            lvl = clip3(0, 63, lvl + h["FeatureData"][seg][feat])
        if h["loop_filter_delta_enabled"]:
            ns = lvl >> 5
            lvl = clip3(0, 63, lvl + (h["loop_filter_ref_deltas"][0] << ns))
        sh = h["loop_filter_sharpness"]
        shift = 2 if sh > 4 else 1 if sh > 0 else 0
        limit = clip3(1, 9 - sh, lvl >> shift) if sh > 0 else max(1, lvl >> shift)
        r = (lvl, limit, 2 * (lvl + 2) + limit, lvl >> 4)
        self._lfc[key] = r
        return r

    def loop_filter(self):
        h = self.frame
        self._lfc = {}
        bd = self.bd
        for plane in range(self.nplanes):
            if not (plane == 0 or h["loop_filter_level"][1 + plane]):
                continue
            P = self.F[plane].tolist()
            sx = self.subx if plane else 0
            sy = self.suby if plane else 0
            for pss in range(2):
                dx, dy = (1, 0) if pss == 0 else (0, 1)
                for row0 in range(0, self.MiRows, 1 << sy):
                    for col0 in range(0, self.MiCols, 1 << sx):
                        x, y = col0 * 4, row0 * 4
                        if x >= h["FrameWidth"] or y >= h["FrameHeight"]:
                            continue
                        if (pss == 0 and x == 0) or (pss == 1 and y == 0):
                            continue
                        row, col = row0 | sy, col0 | sx
                        xP, yP = x >> sx, y >> sy
                        prow, pcol = row - (dy << sy), col - (dx << sx)
                        tx = int(self.LfTxSizes[plane][row >> sy, col >> sx])
                        ptx = int(self.LfTxSizes[plane][prow >> sy, pcol >> sx])
                        if pss == 0:
                            isTx = xP % TXW[tx] == 0
                            base = min(TXW[ptx], TXW[tx])
                        else:
                            isTx = yP % TXH[tx] == 0
                            base = min(TXH[ptx], TXH[tx])
                        if not isTx:
                            continue
                        fs = min(16, base) if plane == 0 else min(8, base)
                        lvl, limit, blimit, thresh = self.lf_strength(row, col, plane, pss)
                        if lvl == 0:
                            lvl, limit, blimit, thresh = self.lf_strength(prow, pcol, plane, pss)
                        res = (0, 0, 0, 0)
                        if lvl > 0:
                            res = tuple(sample_filter(P, xP + dy * i, yP + dx * i, plane, limit, blimit, thresh,
                                                      dx, dy, fs, bd) for i in range(4))
                        self.deblock_log.append((plane, pss, xP, yP, fs, lvl, limit, blimit, thresh, lvl > 0, res))
            self.F[plane] = np.array(P, np.int32)

    # ---- CDEF (7.15)

    def cdef_process(self):
        h = self.frame
        out = [p.copy() for p in self.F]
        cs = self.bd - 8
        PAD = 4
        pads, avails = [], []
        for plane in range(self.nplanes):
            sx = self.subx if plane else 0
            sy = self.suby if plane else 0
            p = self.F[plane].astype(np.int64)
            pads.append(np.pad(p, PAD))
            av = np.zeros(pads[-1].shape, bool)
            av[PAD:PAD + ((self.MiRows * 4) >> sy), PAD:PAD + ((self.MiCols * 4) >> sx)] = True
            avails.append(av)
        seen = set()
        for r in range(0, self.MiRows, 2):
            for c in range(0, self.MiCols, 2):
                key = (r & ~15, c & ~15)
                idx = self.cdef_idx.get(key, -1)
                if key not in seen:
                    seen.add(key)
                    if idx >= 0:
                        self.cdef_log["sb"].append(dict(x=key[1] * 4, y=key[0] * 4, idx=idx,
                                                        y_pri=h["cdef_y_pri"][idx], y_sec=h["cdef_y_sec"][idx],
                                                        uv_pri=h["cdef_uv_pri"][idx], uv_sec=h["cdef_uv_sec"][idx]))
                if idx == -1:
                    continue
                skip = (self.Skips[r, c] and self.Skips[r + 1, c] and self.Skips[r, c + 1]
                        and self.Skips[r + 1, c + 1])
                rec = dict(x=c * 4, y=r * 4, idx=idx, skip=bool(skip), dir=None, var=None)
                self.cdef_log["blocks"].append(rec)
                if skip:
                    continue
                yDir, var = cdef_direction(self.F[0][r * 4:r * 4 + 8, c * 4:c * 4 + 8], self.bd)
                rec.update(dir=yDir, var=var)
                pri = h["cdef_y_pri"][idx] << cs
                sec = h["cdef_y_sec"][idx] << cs
                d = 0 if pri == 0 else yDir
                vs = min(floorlog2(var >> 6), 12) if (var >> 6) else 0
                pri = (pri * (4 + vs) + 8) >> 4 if var else 0
                cdef_filter(out[0], pads[0], avails[0], c * 4, r * 4, 8, 8, pri, sec, h["CdefDamping"] + cs, d,
                            cs, PAD)
                if self.nplanes == 1:
                    continue
                pri = h["cdef_uv_pri"][idx] << cs
                sec = h["cdef_uv_sec"][idx] << cs
                d = 0 if pri == 0 else T.Cdef_Uv_Dir[self.subx][self.suby][yDir]
                for plane in (1, 2):
                    cdef_filter(out[plane], pads[plane], avails[plane], (c * 4) >> self.subx, (r * 4) >> self.suby,
                                8 >> self.subx, 8 >> self.suby, pri, sec, h["CdefDamping"] + cs - 1, d, cs, PAD)
        self.cdef_log["damping"] = h["CdefDamping"]
        return out

    # ---- 超解像 (7.16)

    def upscale(self, planes):
        h = self.frame
        if not h["use_superres"]:
            return planes
        out = []
        for plane, src in enumerate(planes):
            sx = self.subx if plane else 0
            downW = round2(h["FrameWidth"], sx)
            upW = round2(h["UpscaledWidth"], sx)
            stepX = ((downW << 14) + upW // 2) // upW
            err = upW * stepX - (downW << 14)
            init = cdiv(-((upW - downW) << 13) + upW // 2, upW) + (1 << 7) - cdiv(err, 2)
            init &= (1 << 14) - 1
            maxX = (self.MiCols >> sx) * 4 - 1
            xs = np.arange(upW, dtype=np.int64)
            srcX = -(1 << 14) + init + xs * stepX
            px = srcX >> 14
            sub = (srcX & ((1 << 14) - 1)) >> 8
            filt = np.array(T.Upscale_Filter, np.int64)[sub]   # upW×8
            s = src.astype(np.int64)
            acc = np.zeros((s.shape[0], upW), np.int64)
            for k in range(8):
                acc += s[:, np.clip(px + k - 3, 0, maxX)] * filt[:, k][None, :]
            W = s.shape[1] + ((upW - downW) + 64)
            o = np.zeros((s.shape[0], W), np.int32)
            o[:, :upW] = np.clip(np_round2(acc, 7), 0, (1 << self.bd) - 1)
            out.append(o)
        return out

    # ---- ループ復元 (7.17)

    def loop_restoration(self, cur, cdef):
        h = self.frame
        out = [p.astype(np.int64) for p in cdef]
        if not h["UsesLr"]:
            return out
        bd = self.bd
        for plane in range(self.nplanes):
            if h["FrameRestorationType"][plane] == T.RESTORE_NONE:
                continue
            sx = self.subx if plane else 0
            sy = self.suby if plane else 0
            us = h["LoopRestorationSize"][plane]
            unitRows = max((round2(h["FrameHeight"], sy) + (us >> 1)) // us, 1)
            unitCols = max((round2(h["UpscaledWidth"], sx) + (us >> 1)) // us, 1)
            PEX = round2(h["UpscaledWidth"], sx) - 1
            PEY = round2(h["FrameHeight"], sy) - 1
            C = cur[plane].astype(np.int64)
            D = cdef[plane].astype(np.int64)
            # 行ごとの (帯の番号, 単位の行)、列ごとの単位の列
            ys = np.arange(PEY + 1)
            lrow = (ys << sy) >> 2
            stripe = (lrow * 4 + 8) // 64
            urow = np.minimum(unitRows - 1, ((lrow * 4 + 8) >> sy) // us)
            xs = np.arange(PEX + 1)
            lcol = (xs << sx) >> 2
            ucol = np.minimum(unitCols - 1, ((lcol * 4) >> sx) // us)

            def runs(*keys):
                out_, s0 = [], 0
                n = len(keys[0])
                for i in range(1, n + 1):
                    if i == n or any(k[i] != k[s0] for k in keys):
                        out_.append((s0, i))
                        s0 = i
                return out_
            for y0, y1 in runs(stripe, urow):
                sn = int(stripe[y0])
                ss = (-8 + sn * 64) >> sy
                se = ss + (64 >> sy) - 1
                ur = int(urow[y0])
                for x0, x1 in runs(ucol):
                    uc = int(ucol[x0])
                    rt = self.LrType[plane].get((ur, uc), T.RESTORE_NONE)
                    if rt == T.RESTORE_NONE:
                        continue
                    # 周り 4 画素つきの元の画素 (get_source_sample)
                    ry = np.arange(y0 - 4, y1 + 4)
                    rx = np.clip(np.arange(x0 - 4, x1 + 4), 0, PEX)
                    ry = np.clip(ry, 0, PEY)
                    W = np.empty((len(ry), len(rx)), np.int64)
                    for k, yy in enumerate(ry):
                        if yy < ss:
                            W[k] = C[max(ss - 2, yy), rx]
                        elif yy > se:
                            W[k] = C[min(se + 2, yy), rx]
                        else:
                            W[k] = D[yy, rx]
                    hh, ww = y1 - y0, x1 - x0
                    if rt == T.RESTORE_WIENER:
                        cf = self.LrWiener[plane][(ur, uc)]
                        out[plane][y0:y1, x0:x1] = wiener(W, hh, ww, cf, bd)
                    else:
                        st = self.LrSgrSet[plane][(ur, uc)]
                        xq = self.LrSgrXqd[plane][(ur, uc)]
                        out[plane][y0:y1, x0:x1] = self_guided(W, D[y0:y1, x0:x1], hh, ww, st, xq, bd)
        return out

    # ---- フィルムグレイン (7.18.3)

    def film_grain_synthesis(self, out):
        g = dict(self.frame["film_grain"])
        bd = self.bd
        sx, sy = self.subx, self.suby
        mono = self.nplanes == 1
        rnd = [g["grain_seed"]]

        def rand(bits):
            r = rnd[0]
            bit = ((r >> 0) ^ (r >> 1) ^ (r >> 3) ^ (r >> 12)) & 1
            r = (r >> 1) | (bit << 15)
            rnd[0] = r
            return (r >> (16 - bits)) & ((1 << bits) - 1)
        GC = 128 << (bd - 8)
        GMin, GMax = -GC, (256 << (bd - 8)) - 1 - GC
        shift = 12 - bd + g["grain_scale_shift"]
        gs = T.Gaussian_Sequence
        LG = [[round2(gs[rand(11)], shift) if g["num_y_points"] > 0 else 0 for _ in range(82)] for _ in range(73)]
        arsh = g["ar_coeff_shift_minus_6"] + 6
        lag = g["ar_coeff_lag"]
        cy = g["ar_coeffs_y_plus_128"]
        for y in range(3, 73):
            for x in range(3, 82 - 3):
                s = 0
                pos = 0
                for dr in range(-lag, 1):
                    for dc in range(-lag, lag + 1):
                        if dr == 0 and dc == 0:
                            break
                        s += LG[y + dr][x + dc] * (cy[pos] - 128)
                        pos += 1
                LG[y][x] = clip3(GMin, GMax, LG[y][x] + round2(s, arsh))
        CbG = CrG = None
        if not mono:
            cw = 44 if sx else 82
            ch = 38 if sy else 73
            rnd[0] = g["grain_seed"] ^ 0xb524
            CbG = [[round2(gs[rand(11)], shift) if (g["num_cb_points"] or g["chroma_scaling_from_luma"]) else 0
                    for _ in range(cw)] for _ in range(ch)]
            rnd[0] = g["grain_seed"] ^ 0x49d8
            CrG = [[round2(gs[rand(11)], shift) if (g["num_cr_points"] or g["chroma_scaling_from_luma"]) else 0
                    for _ in range(cw)] for _ in range(ch)]
            c0s, c1s = g["ar_coeffs_cb_plus_128"], g["ar_coeffs_cr_plus_128"]
            for y in range(3, ch):
                for x in range(3, cw - 3):
                    s0 = s1 = 0
                    pos = 0
                    for dr in range(-lag, 1):
                        for dc in range(-lag, lag + 1):
                            c0 = c0s[pos] - 128
                            c1 = c1s[pos] - 128
                            if dr == 0 and dc == 0:
                                if g["num_y_points"] > 0:
                                    luma = 0
                                    lx = ((x - 3) << sx) + 3
                                    ly = ((y - 3) << sy) + 3
                                    for i in range(sy + 1):
                                        for j in range(sx + 1):
                                            luma += LG[ly + i][lx + j]
                                    luma = round2(luma, sx + sy)
                                    s0 += luma * c0
                                    s1 += luma * c1
                                break
                            s0 += CbG[y + dr][x + dc] * c0
                            s1 += CrG[y + dr][x + dc] * c1
                            pos += 1
                    CbG[y][x] = clip3(GMin, GMax, CbG[y][x] + round2(s0, arsh))
                    CrG[y][x] = clip3(GMin, GMax, CrG[y][x] + round2(s1, arsh))
        # 倍率の表
        csl = g.get("chroma_scaling_from_luma", 0)

        def pts(plane):
            if plane == 0 or csl:
                return g["point_y_value"], g["point_y_scaling"]
            if plane == 1:
                return g["point_cb_value"], g["point_cb_scaling"]
            return g["point_cr_value"], g["point_cr_scaling"]
        lut = []
        for plane in range(self.nplanes):
            xv, yv = pts(plane)
            t = [0] * 256
            if xv:
                for x in range(xv[0]):
                    t[x] = yv[0]
                for i in range(len(xv) - 1):
                    dY = yv[i + 1] - yv[i]
                    dX = xv[i + 1] - xv[i]
                    delta = dY * ((65536 + (dX >> 1)) // dX)
                    for x in range(dX):
                        t[xv[i] + x] = yv[i] + ((x * delta + 32768) >> 16)
                for x in range(xv[-1], 256):
                    t[x] = yv[-1]
            lut.append(t)
        # 雑音の帯
        w, h = self.plane_w(0), self.plane_h(0)
        grains = [np.array(LG, np.int64)] + ([np.array(CbG, np.int64), np.array(CrG, np.int64)] if not mono else [])
        stripes = []
        lumaNum = 0
        for y in range(0, (h + 1) // 2, 16):
            rnd[0] = g["grain_seed"]
            rnd[0] ^= ((lumaNum * 37 + 178) & 255) << 8
            rnd[0] ^= ((lumaNum * 173 + 105) & 255)
            st = []
            for plane in range(self.nplanes):
                psx = sx if plane else 0
                psy = sy if plane else 0
                st.append(np.zeros((34 >> psy, ((w + psx) >> psx) + 80), np.int64))
            for x in range(0, (w + 1) // 2, 16):
                rv = rand(8)
                ox, oy = rv >> 4, rv & 15
                for plane in range(self.nplanes):
                    psx = sx if plane else 0
                    psy = sy if plane else 0
                    pox = 6 + ox if psx else 9 + ox * 2
                    poy = 6 + oy if psy else 9 + oy * 2
                    blk = grains[plane][poy:poy + (34 >> psy), pox:pox + (34 >> psx)].copy()
                    S_ = st[plane]
                    if psx == 0:
                        if g["overlap_flag"] and x > 0:
                            old = S_[:, x * 2:x * 2 + 2]
                            blk[:, 0] = np.clip(np_round2(old[:, 0] * 27 + blk[:, 0] * 17, 5), GMin, GMax)
                            blk[:, 1] = np.clip(np_round2(old[:, 1] * 17 + blk[:, 1] * 27, 5), GMin, GMax)
                        S_[:, x * 2:x * 2 + blk.shape[1]] = blk
                    else:
                        if g["overlap_flag"] and x > 0:
                            old = S_[:, x]
                            blk[:, 0] = np.clip(np_round2(old * 23 + blk[:, 0] * 22, 5), GMin, GMax)
                        S_[:, x:x + blk.shape[1]] = blk
            stripes.append(st)
            lumaNum += 1
        noise = []
        for plane in range(self.nplanes):
            psx = sx if plane else 0
            psy = sy if plane else 0
            ph, pw = (h + psy) >> psy, (w + psx) >> psx
            N = np.zeros((ph, pw), np.int64)
            for y in range(ph):
                ln = y >> (5 - psy)
                i = y - (ln << (5 - psy))
                gv = stripes[ln][plane][i, :pw].copy()
                if g["overlap_flag"] and ln > 0:
                    if psy == 0 and i < 2:
                        old = stripes[ln - 1][plane][i + 32, :pw]
                        gv = old * 27 + gv * 17 if i == 0 else old * 17 + gv * 27
                        gv = np.clip(np_round2(gv, 5), GMin, GMax)
                    elif psy and i < 1:
                        old = stripes[ln - 1][plane][i + 16, :pw]
                        gv = np.clip(np_round2(old * 23 + gv * 22, 5), GMin, GMax)
                N[y] = gv
            noise.append(N)
        # 混ぜる
        if g["clip_to_restricted_range"]:
            mn = 16 << (bd - 8)
            maxL = 235 << (bd - 8)
            maxC = maxL if self.seq["matrix_coefficients"] == 0 else 240 << (bd - 8)
        else:
            mn, maxL = 0, (256 << (bd - 8)) - 1
            maxC = maxL
        SS = g["grain_scaling_minus_8"] + 8
        luts = [np.array(t + [t[-1]], np.int64) for t in lut]

        def scale(plane, idx):
            sh = bd - 8
            x = idx >> sh
            if bd == 8:
                return luts[plane][x]
            rem = idx - (x << sh)
            st_ = luts[plane][x]
            en = luts[plane][np.minimum(x + 1, 256)]
            return np.where(x == 255, st_, st_ + np_round2((en - st_) * rem, sh))
        Y = out[0]
        res = [Y.copy()] + [p.copy() for p in out[1:]]
        if not mono:
            ph, pw = (h + sy) >> sy, (w + sx) >> sx
            lx = np.arange(pw) << sx
            ly = np.arange(ph) << sy
            lnx = np.minimum(lx + 1, w - 1)
            if sx:
                avg = np_round2(Y[ly][:, lx] + Y[ly][:, lnx], 1)
            else:
                avg = Y[ly][:, lx]
            for plane, c in ((1, "cb"), (2, "cr")):
                if g[f"num_{c}_points"] > 0 or csl:
                    orig = out[plane][:ph, :pw]
                    if csl:
                        merged = avg
                    else:
                        comb = avg * (g[f"{c}_luma_mult"] - 128) + orig * (g[f"{c}_mult"] - 128)
                        merged = np.clip((comb >> 6) + ((g[f"{c}_offset"] - 256) << (bd - 8)), 0, (1 << bd) - 1)
                    nz = np_round2(scale(plane, merged) * noise[plane], SS)
                    res[plane][:ph, :pw] = np.clip(orig + nz, mn, maxC)
        if g["num_y_points"] > 0:
            nz = np_round2(scale(0, Y) * noise[0], SS)
            res[0] = np.clip(Y + nz, mn, maxL)
        g.update(luma_grain=grains[0], cb_grain=None if mono else grains[1], cr_grain=None if mono else grains[2],
                 scaling=lut, noise=noise, noise_stripes=stripes)
        self.film_grain = g
        return res


# ---------------------------------------------------------------- 小さな関数

def cdiv(a, b):
    """C の割り算 (0 の方へ切り捨て)"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def inverse_recenter(r, v):
    if v > 2 * r:
        return v
    if v & 1:
        return r - ((v + 1) >> 1)
    return r + (v >> 1)


def neg_deinterleave(diff, ref, mx):
    if not ref:
        return diff
    if ref >= mx - 1:
        return mx - diff - 1
    if 2 * ref < mx:
        if diff <= 2 * ref:
            return ref + ((diff + 1) >> 1) if diff & 1 else ref - (diff >> 1)
        return diff
    if diff <= 2 * (mx - ref - 1):
        return ref + ((diff + 1) >> 1) if diff & 1 else ref - (diff >> 1)
    return mx - (diff + 1)


def split_cdf(pc, name, bSize):
    """split_or_horz / split_or_vert の CDF (区切りの CDF から作る)"""
    def p(k):
        return pc[k] - (pc[k - 1] if k > 0 else 0)
    if name == "split_or_horz":
        ps = p(2) + p(3) + p(4) + p(6) + p(7)
        if bSize != T.BLOCK_128X128:
            ps += p(9)
    else:
        ps = p(1) + p(3) + p(4) + p(5) + p(6)
        if bSize != T.BLOCK_128X128:
            ps += p(8)
    return [32768 - ps, 32768, 0]


def tx_class(t):
    if t in (T.V_DCT, T.V_ADST, T.V_FLIPADST):
        return T.TX_CLASS_VERT
    if t in (T.H_DCT, T.H_ADST, T.H_FLIPADST):
        return T.TX_CLASS_HORIZ
    return T.TX_CLASS_2D


_SCAN_NAMES = {T.TX_4X4: "4x4", T.TX_4X8: "4x8", T.TX_8X4: "8x4", T.TX_8X8: "8x8", T.TX_8X16: "8x16",
               T.TX_16X8: "16x8", T.TX_16X16: "16x16", T.TX_16X32: "16x32", T.TX_32X16: "32x16",
               T.TX_4X16: "4x16", T.TX_16X4: "16x4", T.TX_8X32: "8x32", T.TX_32X8: "32x8"}


def get_scan(txSz, ptt):
    if txSz == T.TX_16X64:
        return T.Default_Scan_16x32
    if txSz == T.TX_64X16:
        return T.Default_Scan_32x16
    if T.Tx_Size_Sqr_Up[txSz] == T.TX_64X64:
        return T.Default_Scan_32x32
    nm = _SCAN_NAMES.get(txSz, "32x32")
    if ptt != T.IDTX:
        if ptt in (T.V_DCT, T.V_ADST, T.V_FLIPADST):
            return getattr(T, f"Mrow_Scan_{nm}")
        if ptt in (T.H_DCT, T.H_ADST, T.H_FLIPADST):
            return getattr(T, f"Mcol_Scan_{nm}")
    return getattr(T, f"Default_Scan_{nm}")


def cfl_predict(Y, F, p, keep=None):
    """7.11.5。Y は明るさの面、F はこの面 (DC の予想が入っている)"""
    x, y = p["x"], p["y"]
    w, h = 1 << p["log2W"], 1 << p["log2H"]
    sx, sy = p["subx"], p["suby"]
    ly = np.minimum((np.arange(h) + y) << sy, p["max_luma_h"] - (1 << sy))
    lx = np.minimum((np.arange(w) + x) << sx, p["max_luma_w"] - (1 << sx))
    t = np.zeros((h, w), np.int64)
    for dy in range(sy + 1):
        for dx in range(sx + 1):
            t += Y[(ly + dy)[:, None], (lx + dx)[None, :]]
    Lv = t << (3 - sx - sy)
    avg = round2(int(Lv.sum()), p["log2W"] + p["log2H"])
    d = p["cfl_alpha"] * (Lv - avg)
    sc = np.where(d >= 0, np_round2(d, 6), -np_round2(-d, 6))
    dc = F[y:y + h, x:x + w].astype(np.int64)
    if keep is not None:
        keep.update(cfl_L=Lv, luma_avg=avg, cfl_ac=sc, dc=dc.copy(), alpha=p["cfl_alpha"])
    return np.clip(dc + sc, 0, (1 << p["bd"]) - 1)


def sample_filter(P, x, y, plane, limit, blimit, thresh, dx, dy, fs, bd):
    """7.14.6。P は list の list。結果の種類 (0 / 4 / 6・8 / 16) を返す"""
    if dx:
        rw = P[y]

        def g(k):
            return rw[x + k]

        def s(k, v):
            rw[x + k] = v
    else:
        def g(k):
            return P[y + k][x]

        def s(k, v):
            P[y + k][x] = v
    q0, q1, p0, p1 = g(0), g(1), g(-1), g(-2)
    sh = bd - 8
    hev = abs(p1 - p0) > (thresh << sh) or abs(q1 - q0) > (thresh << sh)
    fl = 4 if fs == 4 else 6 if plane else 8 if fs == 8 else 16
    lb, bb = limit << sh, blimit << sh
    if abs(p1 - p0) > lb or abs(q1 - q0) > lb or abs(p0 - q0) * 2 + abs(p1 - q1) // 2 > bb:
        return 0
    if fl >= 6:
        q2, p2 = g(2), g(-3)
        if abs(p2 - p1) > lb or abs(q2 - q1) > lb:
            return 0
    if fl >= 8:
        q3, p3 = g(3), g(-4)
        if abs(p3 - p2) > lb or abs(q3 - q2) > lb:
            return 0
    t1 = 1 << sh
    flat = False
    if fs >= 8:
        flat = not (abs(p1 - p0) > t1 or abs(q1 - q0) > t1 or abs(p2 - p0) > t1 or abs(q2 - q0) > t1)
        if flat and fl >= 8:
            flat = not (abs(p3 - p0) > t1 or abs(q3 - q0) > t1)
    flat2 = False
    if fs >= 16:
        flat2 = all(abs(g(k) - p0) <= t1 for k in (-7, -6, -5)) and all(abs(g(k) - q0) <= t1 for k in (4, 5, 6))
    if fs == 4 or not flat:
        # 狭いフィルタ
        lo, hi = -(1 << (bd - 1)), (1 << (bd - 1)) - 1
        o = 0x80 << sh
        ps1, ps0, qs0, qs1 = p1 - o, p0 - o, q0 - o, q1 - o
        f = clip3(lo, hi, ps1 - qs1) if hev else 0
        f = clip3(lo, hi, f + 3 * (qs0 - ps0))
        f1 = clip3(lo, hi, f + 4) >> 3
        f2 = clip3(lo, hi, f + 3) >> 3
        s(0, clip3(lo, hi, qs0 - f1) + o)
        s(-1, clip3(lo, hi, ps0 + f2) + o)
        if not hev:
            f = round2(f1, 1)
            s(1, clip3(lo, hi, qs1 - f) + o)
            s(-2, clip3(lo, hi, ps1 + f) + o)
        return 4
    log2 = 3 if (fs == 8 or not flat2) else 4
    n = 6 if log2 == 4 else 3 if plane == 0 else 2
    n2 = 0 if (log2 == 3 and plane == 0) else 1
    v = {k: g(k) for k in range(-(n + 1), n + 1)}
    Fo = []
    for i in range(-n, n):
        t = 0
        for j in range(-n, n + 1):
            pp = clip3(-(n + 1), n, i + j)
            t += v[pp] * (2 if abs(j) <= n2 else 1)
        Fo.append(round2(t, log2))
    for k, i in enumerate(range(-n, n)):
        s(i, Fo[k])
    return 16 if log2 == 4 else (6 if plane else 8)


def cdef_direction(blk, bd):
    b = ((blk.astype(np.int64) >> (bd - 8)) - 128).tolist()
    partial = [[0] * 15 for _ in range(8)]
    for i in range(8):
        for j in range(8):
            x = b[i][j]
            partial[0][i + j] += x
            partial[1][i + j // 2] += x
            partial[2][i] += x
            partial[3][3 + i - j // 2] += x
            partial[4][7 + i - j] += x
            partial[5][3 - i // 2 + j] += x
            partial[6][j] += x
            partial[7][i // 2 + j] += x
    D = T.Div_Table
    cost = [0] * 8
    for i in range(8):
        cost[2] += partial[2][i] ** 2
        cost[6] += partial[6][i] ** 2
    cost[2] *= D[8]
    cost[6] *= D[8]
    for i in range(7):
        cost[0] += (partial[0][i] ** 2 + partial[0][14 - i] ** 2) * D[i + 1]
        cost[4] += (partial[4][i] ** 2 + partial[4][14 - i] ** 2) * D[i + 1]
    cost[0] += partial[0][7] ** 2 * D[8]
    cost[4] += partial[4][7] ** 2 * D[8]
    for i in range(1, 8, 2):
        for j in range(5):
            cost[i] += partial[i][3 + j] ** 2
        cost[i] *= D[8]
        for j in range(3):
            cost[i] += (partial[i][j] ** 2 + partial[i][10 - j] ** 2) * D[2 * j + 2]
    best, yDir = 0, 0
    for i in range(8):
        if cost[i] > best:
            best, yDir = cost[i], i
    return yDir, (best - cost[(yDir + 4) & 7]) >> 10


def _constrain(diff, thr, damping):
    if not thr:
        return np.zeros_like(diff)
    adj = max(0, damping - floorlog2(thr))
    a = np.abs(diff)
    return np.where(diff < 0, -1, 1) * np.clip(thr - (a >> adj), 0, a)


def cdef_filter(out, pad, avail, x0, y0, w, h, pri, sec, damping, d, cs, PAD):
    X = pad[PAD + y0:PAD + y0 + h, PAD + x0:PAD + x0 + w]
    s = np.zeros((h, w), np.int64)
    mx = X.copy()
    mn = X.copy()
    pt = T.Cdef_Pri_Taps[(pri >> cs) & 1]
    st = T.Cdef_Sec_Taps[(pri >> cs) & 1]
    for k in range(2):
        for sign in (-1, 1):
            for dd, strength, taps in ((d, pri, pt), ((d - 2) & 7, sec, st), ((d + 2) & 7, sec, st)):
                oy = sign * T.Cdef_Directions[dd][k][0]
                ox = sign * T.Cdef_Directions[dd][k][1]
                ys, xs = PAD + y0 + oy, PAD + x0 + ox
                Pv = pad[ys:ys + h, xs:xs + w]
                Av = avail[ys:ys + h, xs:xs + w]
                s += np.where(Av, taps[k] * _constrain(Pv - X, strength, damping), 0)
                mx = np.where(Av, np.maximum(mx, Pv), mx)
                mn = np.where(Av, np.minimum(mn, Pv), mn)
    out[y0:y0 + h, x0:x0 + w] = np.clip(X + ((8 + s - (s < 0)) >> 4), mn, mx)


def wiener(W, h, w, coef, bd):
    """W は周り 4 画素つき ((h+8)×(w+8))。coef = [縦 3, 横 3]"""
    def full(c):
        f = [0] * 7
        f[3] = 128
        for i in range(3):
            f[i] = f[6 - i] = c[i]
            f[3] -= 2 * c[i]
        return f
    vf, hf = full(coef[0]), full(coef[1])
    r0 = 5 if bd == 12 else 3
    r1 = 9 if bd == 12 else 11
    off = 1 << (bd + 7 - r0 - 1)
    lim = (1 << (bd + 1 + 7 - r0)) - 1
    # 行 y0-3 .. y1+2 (W の 1..h+6)、列 x0..x1-1 (W の 4..)
    Wr = W[1:h + 7]
    s = np.zeros((h + 6, w), np.int64)
    for t in range(7):
        s += hf[t] * Wr[:, 1 + t:1 + t + w]
    inter = np.clip(np_round2(s, r0), -off, lim - off)
    s = np.zeros((h, w), np.int64)
    for t in range(7):
        s += vf[t] * inter[t:t + h]
    return np.clip(np_round2(s, r1), 0, (1 << bd) - 1)


def self_guided(W, U, h, w, st, xq, bd):
    """7.17.2-3。W は周り 4 画素つきの元、U はその場所の CDEF のあと (h×w)"""
    flts = []
    for ps in range(2):
        r = T.Sgr_Params[st][ps * 2]
        if r == 0:
            flts.append(None)
            continue
        eps = T.Sgr_Params[st][ps * 2 + 1]
        n = (2 * r + 1) ** 2
        n2e = n * n * eps
        s = ((1 << 20) + n2e // 2) // n2e
        # A, B は i=-1..h、j=-1..w。W の (4+i, 4+j) が中心
        H2, W2 = h + 2, w + 2
        a = np.zeros((H2, W2), np.int64)
        b = np.zeros((H2, W2), np.int64)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                c = W[3 + dy:3 + dy + H2, 3 + dx:3 + dx + W2]
                a += c * c
                b += c
        a = np_round2(a, 2 * (bd - 8))
        d = np_round2(b, bd - 8)
        p = np.maximum(0, a * n - d * d)
        z = np_round2(p * s, 20)
        a2 = np.where(z >= 255, 256, np.where(z == 0, 1, ((z << 8) + z // 2) // (z + 1)))
        one = ((1 << 12) + n // 2) // n
        b2 = ((1 << 8) - a2) * b * one
        A = a2
        B = np_round2(b2, 12)
        Fv = np.zeros((h, w), np.int64)
        for i in range(h):
            sh = 4 if (ps == 0 and (i & 1)) else 5
            aa = np.zeros(w, np.int64)
            bb = np.zeros(w, np.int64)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if ps == 0:
                        wt = (6 if dx == 0 else 5) if ((i + dy) & 1) else 0
                    else:
                        wt = 4 if (dx == 0 or dy == 0) else 3
                    if wt:
                        aa += wt * A[1 + i + dy, 1 + dx:1 + dx + w]
                        bb += wt * B[1 + i + dy, 1 + dx:1 + dx + w]
            v = aa * U[i] + bb
            Fv[i] = np_round2(v, 8 + sh - 4)
        flts.append(Fv)
    w0, w1 = xq
    w2 = (1 << 7) - w0 - w1
    u = U << 4
    v = w1 * u
    v = v + (w0 * flts[0] if flts[0] is not None else w0 * u)
    v = v + (w2 * flts[1] if flts[1] is not None else w2 * u)
    return np.clip(np_round2(v, 11), 0, (1 << bd) - 1)


# ---------------------------------------------------------------- ファイル

def av1_items(path):
    """AVIF の AV1 の項目 (主の絵と、透明度などほかの av01) → [(項目の番号, 名前, OBU の list, OBU の並びのバイト列)]"""
    r = heif.parse(path)
    out = []
    order = [r["primary"]] + sorted(i for i, it in r["items"].items() if it["type"] == "av01" and i != r["primary"])
    for iid in order:
        it = r["items"][iid]
        if it["type"] != "av01":
            continue
        obus = []
        av = heif.item_prop(it, "av1C")
        if av and av["config_obus"]:
            obus += split_obus(av["config_obus"], None)
        for pos, ln in it["extents"]:
            obus += split_obus(r["bytes"][pos:pos + ln], pos)
        aux = heif.item_prop(it, "auxC")
        name = "primary" if iid == r["primary"] else ("alpha" if aux is not None else f"item{iid}")
        out.append((iid, name, obus, heif.obu_stream(r, iid)))
    return out


def read_input(path):
    """.avif → av1_items。.obu (OBU の並び) / .ivf → 1 項目"""
    path = Path(path)
    b = path.read_bytes()
    if b[4:8] == b"ftyp":
        return av1_items(path)
    if b[:4] == b"DKIF":
        hl = int.from_bytes(b[6:8], "little")
        o = hl
        sz = int.from_bytes(b[o:o + 4], "little")
        data = b[o + 12:o + 12 + sz]
        return [(0, "ivf", split_obus(data, o + 12), data)]
    return [(0, "obu", split_obus(b, 0), b)]


def decode_file(path, keep_symbols=True, item=0):
    return Decoder(read_input(path)[item][2], keep_symbols).decode()


def aomdec_planes(stream, d, workdir):
    """aomdec --rawvideo の出力を面に分ける"""
    ob = Path(workdir) / "x.obu"
    yuv = Path(workdir) / "x.yuv"
    ob.write_bytes(stream)
    subprocess.run(["aomdec", "--rawvideo", "-o", str(yuv), str(ob)], check=True, capture_output=True)
    raw = yuv.read_bytes()
    dt = np.uint8 if d.bd == 8 else np.uint16
    a = np.frombuffer(raw, dtype=np.dtype(dt).newbyteorder("<"))
    w, h = d.plane_w(0), d.plane_h(0)
    cw, ch = ((w + d.subx) >> d.subx, (h + d.suby) >> d.suby)
    out = [a[:w * h].reshape(h, w)]
    if d.nplanes > 1:
        out.append(a[w * h:w * h + cw * ch].reshape(ch, cw))
        out.append(a[w * h + cw * ch:w * h + 2 * cw * ch].reshape(ch, cw))
    return out


def stats(d):
    h = d.frame
    s = d.seq
    lines = []
    lines.append(f"大きさ {h['UpscaledWidth']}×{h['FrameHeight']} (符号化 {h['FrameWidth']})  {s['BitDepth']} ビット  "
                 f"面 {s['NumPlanes']}  超ブロック {128 if s['use_128x128_superblock'] else 64}  "
                 f"タイル {h['TileCols']}×{h['TileRows']}  base_q_idx {h['base_q_idx']}")
    lines.append(f"reduced_still_picture_header {s['reduced_still_picture_header']}  "
                 f"screen_content_tools {h['allow_screen_content_tools']}  intrabc {h['allow_intrabc']}  "
                 f"superres {h['use_superres']}  film_grain {h['film_grain']['apply_grain']}  "
                 f"qmatrix {h['using_qmatrix']}  delta_q {h['delta_q_present']}  delta_lf {h['delta_lf_present']}  "
                 f"segmentation {h['segmentation_enabled']}  reduced_tx_set {h['reduced_tx_set']}  "
                 f"TxMode {h['TxMode']}  loop_filter_level {h['loop_filter_level']}")
    c = Counter((PARTITION_NAMES[p["partition"]], p["coded"]) for p in d.partitions)
    lines.append("区切り: " + ", ".join(f"{a}/{b} {n}" for (a, b), n in sorted(c.items())))
    lines.append("ブロックの大きさ: " + ", ".join(f"{BLOCK_NAMES[k]} {n}" for k, n in
                                          sorted(Counter(b["bsize"] for b in d.blocks).items())))
    lines.append(f"ブロック {len(d.blocks)}  skip {sum(b['skip'] for b in d.blocks)}")
    lines.append("y_mode: " + ", ".join(f"{MODE_NAMES[k]} {n}" for k, n in
                                        sorted(Counter(b["y_mode"] for b in d.blocks).items())))
    uv = Counter(b["uv_mode"] for b in d.blocks if b["has_chroma"])
    lines.append("uv_mode: " + ", ".join(f"{MODE_NAMES[k]} {n}" for k, n in sorted(uv.items()))
                 + f"  (CfL {uv.get(13, 0)})")
    ad = Counter(b["angle_delta_y"] for b in d.blocks if 1 <= b["y_mode"] <= 8 and b["bsize"] >= T.BLOCK_8X8)
    lines.append("angle_delta_y: " + ", ".join(f"{k:+d} {n}" for k, n in sorted(ad.items())))
    ad = Counter(b["angle_delta_uv"] for b in d.blocks if b["has_chroma"] and 1 <= b["uv_mode"] <= 8
                 and b["bsize"] >= T.BLOCK_8X8)
    lines.append("angle_delta_uv: " + ", ".join(f"{k:+d} {n}" for k, n in sorted(ad.items())))
    lines.append(f"フィルタ予想 {sum(b['use_filter_intra'] for b in d.blocks)}  "
                 f"パレット (明るさ {sum(1 for b in d.blocks if b['palette_size_y'])}, "
                 f"色 {sum(1 for b in d.blocks if b['palette_size_uv'])})")
    lines.append("変換の大きさ (明るさ): " + ", ".join(
        f"{TXW[k]}x{TXH[k]} {n}" for k, n in sorted(Counter(t["tx_size"] for t in d.txbs if t["plane"] == 0).items())))
    tt = Counter((t["plane"] > 0, TX_TYPE_NAMES[t["tx_type"]]) for t in d.txbs if t["eob"])
    lines.append("変換の種類 (係数のある変換): " + ", ".join(f"{'色' if a else '明'}:{b} {n}"
                                                    for (a, b), n in sorted(tt.items())))
    lines.append(f"変換 {len(d.txbs)}  係数のある変換 {sum(1 for t in d.txbs if t['eob'])}")
    lines.append(f"CDEF damping {h['CdefDamping']}  強さ (y_pri, y_sec, uv_pri, uv_sec): " + ", ".join(
        f"{i}:({h['cdef_y_pri'][i]},{h['cdef_y_sec'][i]},{h['cdef_uv_pri'][i]},{h['cdef_uv_sec'][i]})"
        for i in range(len(h["cdef_y_pri"]))))
    lines.append("CDEF の番号 (64×64): " + ", ".join(f"{k} {n}" for k, n in
                                               sorted(Counter(s_["idx"] for s_ in d.cdef_log["sb"]).items())))
    lines.append(f"ループ復元 {h['FrameRestorationType']} (0 なし 1 Wiener 2 自己誘導 3 切り替え)  単位 "
                 f"{h['LoopRestorationSize']}  " + ", ".join(
                     f"{['なし', 'Wiener', '自己誘導'][k]} {n}" for k, n in
                     sorted(Counter(u["type"] for u in d.lr_units).items())))
    if d.symbols is not None:
        n_lit = sum(1 for s_ in d.symbols if s_[1] is None)
        lines.append(f"記号 {len(d.symbols)} (うち L() の 1 ビット {n_lit})")
    return "\n".join(lines)


def main():
    import time
    args = sys.argv[1:]
    path = args[0]
    items = read_input(path)
    ok = True
    with tempfile.TemporaryDirectory() as wd:
        for iid, name, obus, stream in items:
            t0 = time.time()
            d = Decoder(obus).decode()
            dt = time.time() - t0
            ref = aomdec_planes(stream, d, wd)
            mine = d.crop()
            res = []
            for i, rp in enumerate(ref):
                bad = int(np.count_nonzero(mine[i].astype(np.int64) != rp.astype(np.int64)))
                res.append(bad)
                if bad:
                    ok = False
            print(f"{path} [{name}] {d.plane_w(0)}×{d.plane_h(0)}  {dt:.1f} 秒  ずれた画素 (Y, U, V) = {res}")
            if "--stats" in args:
                print(stats(d))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
