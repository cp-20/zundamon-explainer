"""JPEG 動画の共通部品。シーンをまたいで同じ見た目・同じ位置で続くものはここで作る。

- gray_img(a, size)：8×8 などの明るさ配列を、ドットのままの白黒画像に
- BlockGrid(values)：8×8 のマス（明るさで塗る）＋数字。主役のブロックの表示
- BasisGrid(F)：64 種類の模様（DCT の基底）を 8×8 に並べたもの。係数の数字を重ねられる
"""
import numpy as np
from manim import *  # noqa

from vlib.data import BASIS, ZIGZAG
from zunda.scene import CORAL, DIM, INK, YELLOW, jp, px, u

# 画面上の定位置（シーンの引き継ぎで使う）
BLOCK_POS = px(960, 470)   # 主役のブロックの中心（S04 の終わり）
BLOCK_CELL = 62            # そのマスの大きさ px
GRID_POS = px(744, 424)    # 64 模様の中心（S05 後半〜S06 の始まり）
GRID_TILE, GRID_GAP = 60, 6


def gray_img(a, size_px, vmin=0, vmax=255):
    """明るさ配列 → ドットのままの白黒 ImageMobject（高さ size_px）"""
    g = np.clip((np.asarray(a, float) - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
    # 小さい配列のままだと Manim の拡大で端がずれるので、ドットを並べた大きい画像にしておく
    k = max(1, 128 // max(g.shape))
    g = g.repeat(k, 0).repeat(k, 1)
    m = ImageMobject(np.dstack([g, g, g]))
    m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.height = u(size_px)
    return m


def basis_img(uu, vv, size_px=GRID_TILE):
    """周波数 (uu 縦, vv 横) の模様。白黒をいっぱいに使う（0 の模様は真ん中より明るい灰）"""
    b = BASIS[uu, vv]
    if uu == vv == 0:
        return gray_img(np.full((8, 8), 200.0), size_px)
    return gray_img(128 + 127 * b / np.abs(b).max(), size_px)


class BlockGrid(VGroup):
    """8×8 のマス。各マスは明るさで塗り、数字を載せる（数字は明るさで白/黒）"""

    def __init__(self, values, cell=BLOCK_CELL, nums=True, size=None, **kw):
        super().__init__(**kw)
        values = np.asarray(values)
        self.values = values
        self.cells = VGroup()
        self.nums = VGroup()
        for r in range(8):
            for c in range(8):
                v = float(np.clip(values[r, c], 0, 255))
                sq = Square(side_length=u(cell), stroke_width=1.5, stroke_color="#2a2e38",
                            fill_color=rgb_to_color([v / 255] * 3), fill_opacity=1)
                sq.move_to(np.array([u(cell) * (c - 3.5), -u(cell) * (r - 3.5), 0]))
                self.cells.add(sq)
                t = jp(str(int(round(values[r, c]))), size or cell * 0.42, "#14161c" if v > 110 else INK)
                t.move_to(sq)
                self.nums.add(t)
        self.add(self.cells)
        if nums:
            self.add(self.nums)

    def cell(self, r, c):
        return self.cells[r * 8 + c]

    def num(self, r, c):
        return self.nums[r * 8 + c]


class BasisGrid(Group):
    """64 種類の模様。tiles[u*8+v]。coef() で係数の数字を重ねる"""

    def __init__(self, tile=GRID_TILE, gap=GRID_GAP, **kw):
        super().__init__(**kw)
        self.tile, self.gap = tile, gap
        self.tiles = Group()
        step = u(tile + gap)
        for uu in range(8):
            for vv in range(8):
                m = basis_img(uu, vv, tile)
                m.move_to(np.array([step * (vv - 3.5), -step * (uu - 3.5), 0]))
                self.tiles.add(m)
        self.add(self.tiles)
        self.move_to(GRID_POS)

    def at(self, uu, vv):
        return self.tiles[uu * 8 + vv]

    def zigzag(self):
        return [self.at(r, c) for r, c in ZIGZAG]

    def coef_labels(self, F, big=20):
        """係数の数字（丸め）。|F| が big 以上は黄色で大きく、それ以外は小さく灰"""
        out = VGroup()
        for uu in range(8):
            for vv in range(8):
                v = int(round(F[uu, vv]))
                strong = abs(v) >= big
                t = jp(str(v).replace("-", "−"), 28 if strong else 24, YELLOW if strong else INK)
                t.move_to(self.at(uu, vv))
                t.strong = strong
                out.add(t)
        return out


def coef_state(F):
    """S05 の終わり＝S06 の始まりの画面：暗くした 64 模様と、係数の数字（小さいものは珊瑚）"""
    g = BasisGrid()
    for t in g.tiles:
        t.set_opacity(0.28)
        t.check_ignore = True
    labels = g.coef_labels(F)
    for t in labels:
        if not t.strong:
            t.set_color(CORAL)
    return g, labels


QGRID_POS = px(960, 470)   # 割って丸めたあとの 8×8（S06 の終わり＝S07 の始まり）
QGRID_CELL = 66


class QGrid(VGroup):
    """量子化後の係数 8×8。暗いマスに数字、0 は暗い灰、0 以外は白"""

    def __init__(self, Q, cell=QGRID_CELL, **kw):
        super().__init__(**kw)
        self.cells, self.nums = VGroup(), VGroup()
        for r in range(8):
            for c in range(8):
                v = int(Q[r, c])
                sq = Square(side_length=u(cell), stroke_width=1.5, stroke_color="#2a2e38",
                            fill_color="#1d212b", fill_opacity=1)
                sq.move_to(np.array([u(cell) * (c - 3.5), -u(cell) * (r - 3.5), 0]))
                t = jp(str(v).replace("-", "−"), 30, INK if v else "#4a5060").move_to(sq)
                self.cells.add(sq)
                self.nums.add(t)
        self.add(self.cells, self.nums)
        self.move_to(QGRID_POS)

    def cell(self, r, c):
        return self.cells[r * 8 + c]

    def num(self, r, c):
        return self.nums[r * 8 + c]
