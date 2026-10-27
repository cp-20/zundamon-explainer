"""AVIF 編の画面の部品：Cb・Cr の塗り分け、数のマス (CellGrid)、比較表 (compare_card)。"""
import numpy as np
from manim import *  # noqa

from zunda.scene import BG, DIM, INK, YELLOW, jp, mix, mono, px, u

HEIC_COL = "#8d97ad"      # 比較表・棒グラフの HEIC
# Cb・Cr の塗り分け：128 (どちらでもない) を灰、そこから CHROMA_RANGE 離れたら端の色。青みと赤みで同じ決まり
CHROMA_RANGE = 40
MID_RGB = np.array([128, 128, 128], np.float64)
CB_LO, CB_HI = np.array([232, 204, 64.0]), np.array([84, 140, 240.0])     # 青みが少ない (黄) / 多い (青)
CR_LO, CR_HI = np.array([64, 196, 170.0]), np.array([238, 92, 92.0])      # 赤みが少ない (青緑) / 多い (赤)


def _hex(rgb):
    r, g, b = (int(np.clip(round(v), 0, 255)) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def gray(v):
    return _hex((v, v, v))


def _chroma_rgb(p, lo, hi):
    t = np.clip((np.asarray(p, np.float64) - 128) / CHROMA_RANGE, -1, 1)[..., None]
    return np.where(t < 0, MID_RGB + (lo - MID_RGB) * -t, MID_RGB + (hi - MID_RGB) * t)


def cb_color(v):
    """青み (Cb) の値 → 見せる色 (少ないと黄、多いと青、128 は灰)"""
    return _hex(_chroma_rgb(v, CB_LO, CB_HI))


def cr_color(v):
    """赤み (Cr) の値 → 見せる色 (少ないと青緑、多いと赤)"""
    return _hex(_chroma_rgb(v, CR_LO, CR_HI))


def chroma_image(plane, which):
    """Cb か Cr (2 次元の配列) → 塗り分けた RGB 画像 (uint8)"""
    lo, hi = (CB_LO, CB_HI) if which == "cb" else (CR_LO, CR_HI)
    return np.clip(np.round(_chroma_rgb(plane, lo, hi)), 0, 255).astype(np.uint8)


class CellGrid(VGroup):
    """数のマス。colors (h×w の色) のマスを cell px で並べ、nums (h×w の文字 or None) を書く。
    同じ位置に新しい CellGrid を作り、.cells と .nums をそれぞれ Transform で変形させる。
    場面には .cells と .nums を別々に入れる (まとめて入れると、検査が文字の束を 1 つの図として扱う)。
    マスは塗りだけなので検査しない (check_ignore)"""

    def __init__(self, colors, center, cell, nums=None, num_size=24, num_colors=None, gap=2):
        super().__init__()
        colors = np.asarray(colors, object)
        h, w = colors.shape
        self.shape_hw, self.center_px, self.cell, self.gap = (h, w), center, cell, gap
        self.cells = VGroup()
        self.nums = VGroup()
        x0 = center[0] - w * cell / 2 + cell / 2
        y0 = center[1] - h * cell / 2 + cell / 2
        for i in range(h):
            for j in range(w):
                sq = Square(u(cell - gap), stroke_width=0, fill_color=colors[i, j], fill_opacity=1)
                sq.move_to(px(x0 + j * cell, y0 + i * cell))
                self.cells.add(sq)
                if nums is not None:
                    c = num_colors[i][j] if num_colors is not None else INK
                    t = mono(str(nums[i][j]), num_size, c).move_to(sq)
                    self.nums.add(t)
        self.cells.check_ignore = True
        self.add(self.cells, self.nums)

    def cell_at(self, i, j):
        return self.cells[i * self.shape_hw[1] + j]

    def corner_px(self):
        h, w = self.shape_hw
        return (self.center_px[0] - w * self.cell / 2, self.center_px[1] - h * self.cell / 2)


def text_color_on(hexcol):
    """マスの色の上で読める文字の色 (明るいマスには暗い字)"""
    c = hexcol.lstrip("#")
    r, g, b = (int(c[k:k + 2], 16) for k in (0, 2, 4))
    return BG if 0.299 * r + 0.587 * g + 0.114 * b > 140 else INK


# ---------------- 比較表 ----------------

CARD_ROWS = [
    ("ブロックの分け方", "4分割をくり返す", "10通りから選ぶ"),
    ("予測の方向", "33方向", "8方向 × 7段階の傾き"),
    ("方向以外の予測", "平ら・プラナー", "平ら・スムース・Paeth"),
    ("色の予測", "まわりの画素から", "明るさのパターンを流用"),
    ("波", "4×4の明るさだけ別の波", "縦と横で別々に選ぶ"),
    ("算術符号", "2択をくり返す", "一度に何択も"),
    ("仕上げのフィルタ", "山と谷をならす", "模様の向きに沿ってならす"),
]
CARD_COLS = (270, 350, 380)       # 列の幅 (px)。枠を足して 1,040px (2 人の間にちょうど入る)
CARD_PAD = 20                     # 枠の内側の余白
NAME_INSET = 28                   # 項目名の左の余白 (書き足す行の黄の線と重ならないように)
CARD_ROW_H = 64


def compare_card(n_rows, center=(960, 440), new=None, size=32):
    """比較表 (頭の行 + CARD_ROWS の最初の n_rows 行)。new 行目 (0 始まり) は、はじめは空けておき、
    add_row(表) で書き足す (それ以外の行は少し沈める)。戻り値の VGroup に .rows (行ごとの VGroup)、.head、.frame がある"""
    W = sum(CARD_COLS)
    H = CARD_ROW_H * (n_rows + 1)
    left, top = center[0] - W / 2, center[1] - H / 2
    g = VGroup()
    frame = RoundedRectangle(corner_radius=u(16), width=u(W + 2 * CARD_PAD), height=u(H + 2 * CARD_PAD), stroke_color="#3a4050",
                             stroke_width=2, fill_color="#1b1e26", fill_opacity=0.97).move_to(px(*center))
    g.add(frame)
    xs = [left + sum(CARD_COLS[:k]) + CARD_COLS[k] / 2 for k in range(3)]
    head = VGroup(jp("HEIC", size, HEIC_COL).move_to(px(xs[1], top + CARD_ROW_H / 2)),
                  jp("AVIF", size, YELLOW).move_to(px(xs[2], top + CARD_ROW_H / 2)))
    g.add(head)
    rows = VGroup()
    g.new_row = None
    for k in range(n_rows):
        y = top + CARD_ROW_H * (k + 1.5)
        name, a, b = CARD_ROWS[k]
        op = 1.0 if (new is None or k == new) else 0.55
        nm = mix(name, size - 2, DIM)
        nm.move_to(px(left + NAME_INSET, y), aligned_edge=LEFT).set_y(px(0, y)[1])
        r = VGroup(nm,
                   mix(a, size - 2, HEIC_COL).move_to(px(xs[1], y)),
                   mix(b, size - 2, YELLOW if k == new else INK).move_to(px(xs[2], y)))
        r.set_opacity(op)
        sep = Line(px(left, y - CARD_ROW_H / 2), px(left + W, y - CARD_ROW_H / 2), stroke_color="#2c313d",
                   stroke_width=2)
        if k == new:
            # 書き足す行：うすい黄の帯と左の黄の線 (はじめは見えない)。文字も add_row まで見えない
            band = Rectangle(width=u(W), height=u(CARD_ROW_H - 4), stroke_width=0, fill_color=YELLOW,
                             fill_opacity=0).move_to(px(center[0], y))
            mark = Line(px(left + 3, y - CARD_ROW_H / 2 + 8), px(left + 3, y + CARD_ROW_H / 2 - 8),
                        stroke_color=YELLOW, stroke_width=6, stroke_opacity=0)
            for t in r:
                t.set_opacity(0)
            rows.add(VGroup(sep, band, mark, r))
            g.new_row = (band, mark, r)
        else:
            rows.add(VGroup(sep, r))
    g.add(rows)
    g.rows, g.head, g.frame = rows, head, frame
    return g


def add_row(card, run_time=1.4):
    """compare_card(…, new=k) の空けておいた行を書き足す動き：帯と線が出て、項目・HEIC・AVIF の順に文字が入る"""
    band, mark, r = card.new_row
    for t in r:
        t.shift(LEFT * u(16))
    cells = [t.animate.set_opacity(1).shift(RIGHT * u(16)) for t in r]   # 左から 16px すべり込んで、元の位置に止まる
    return Succession(AnimationGroup(band.animate.set_fill(opacity=0.12), mark.animate.set_stroke(opacity=1),
                                     run_time=0.35 * run_time),
                      LaggedStart(*cells, lag_ratio=0.45, run_time=0.65 * run_time), run_time=run_time)
