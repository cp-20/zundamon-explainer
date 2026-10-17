import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import BLOCK, block_pixels, fmt, summary, ycc  # noqa: E402
from zunda.fx import pop  # noqa: E402
from vlib.jparts import BLOCK_CELL, BLOCK_POS, BlockGrid, gray_img  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import STAGE_COL, StageMap  # noqa: E402

WAVE = STAGE_COL["dct"]
SCALE = 2                       # 写真 1 画素 = 画面 2px
CELL = 8 * SCALE                # 写真の上の 1 ブロックの大きさ px
CENTER = (960, 480)


def row_wave(row, cell=BLOCK_CELL):
    """1 行の 8 個の明るさを通る、なめらかな cos の和の波（マスの上に重ねる）"""
    n = np.arange(8)
    C = lambda k, t: np.cos((2 * t + 1) * k * np.pi / 16)  # noqa: E731
    A = (C(n[:, None], n[None, :]) @ row) * np.array([1 / 8] + [2 / 8] * 7)
    ts = np.linspace(-0.5, 7.5, 120)
    f = sum(A[k] * C(k, ts) for k in range(8))
    pts = [BLOCK_POS + np.array([u(cell) * (t - 3.5), 0, 0]) + np.array([0, u(cell * 0.42) * (v - 128) / 128 , 0])
           for t, v in zip(ts, f)]
    return VMobject(stroke_color=WAVE, stroke_width=5).set_points_smoothly(pts)


class S04(PScene):
    def construct(self):
        P = block_pixels()
        Y = ycc("cat")[..., 0]
        H, W_ = Y.shape
        comp = summary()["comps"][0]
        nblk = comp["blocks"]
        gw, gh = 2 * -(-W_ // 16), 2 * -(-H // 16)      # 符号化されるブロックの列数・行数（端は 16 の倍数まで埋める）
        assert gw * gh == nblk and nblk > 2000
        assert 8 * BLOCK[0] + 8 <= H and 8 * BLOCK[1] + 8 <= W_

        # ---- 始まり：S03 の終わり ----
        m = StageMap("full", done=("color", "sub"))
        self.add(m)

        self.at("s04_01", 0.4)
        self.play(Transform(m, m.state("strip", active="block", done=("color", "sub"))), run_time=0.5)

        # ---- Y の写真 ----
        self.at("yonly")
        gw_px, gh_px = gw * CELL, gh * CELL
        tl = px(CENTER[0] - gw_px / 2, CENTER[1] - gh_px / 2)
        img = gray_img(Y, H * SCALE).move_to(tl, aligned_edge=UP + LEFT)
        pad = Rectangle(width=u(gw_px), height=u(gh_px), stroke_width=0, fill_color="#14161c", fill_opacity=1)
        pad.move_to(tl, aligned_edge=UP + LEFT)
        self.add(pad)
        self.play(FadeIn(pad), FadeIn(img), run_time=0.9)

        # ---- 8×8 に切る：格子が左上から右下へ ----
        self.at("cut", -0.1)
        hl = [Line(tl + DOWN * u(CELL * j), tl + DOWN * u(CELL * j) + RIGHT * u(gw_px)) for j in range(1, gh)]
        vl = [Line(tl + RIGHT * u(CELL * i), tl + RIGHT * u(CELL * i) + DOWN * u(gh_px)) for i in range(1, gw)]
        lines = VGroup(*hl, *vl).set_stroke("#0c0e13", width=1.2, opacity=0.8)
        order = [(i / gw + 0.0, l) for i, l in enumerate(vl, 1)] + [(j / gh, l) for j, l in enumerate(hl, 1)]
        order.sort(key=lambda t: t[0])
        self.play(LaggedStart(*[Create(l) for _, l in order], lag_ratio=0.02), run_time=self.until("cut", 3.2))

        # ---- ブロックの数 ----
        self.at("many", -0.1)
        count = jp(f"{fmt(nblk)}個", 44, YELLOW).move_to(px(CENTER[0], CENTER[1] + gh_px / 2 + 55))
        self.play(FadeIn(count, shift=UP * u(10)), run_time=0.5)
        self.play(pop(count, 1.12, 0.5), run_time=0.5)  # FadeIn と同じ play で pop すると、終わった瞬間に消えてしまう

        # ---- 1 つ取り出す ----
        self.at("pick", -0.1)
        bx0 = CENTER[0] - gw_px / 2 + BLOCK[1] * CELL + CELL / 2
        by0 = CENTER[1] - gh_px / 2 + BLOCK[0] * CELL + CELL / 2
        small = gray_img(P, CELL).move_to(px(bx0, by0))
        ring = Square(side_length=u(CELL), stroke_color=YELLOW, stroke_width=3, fill_opacity=0).move_to(px(bx0, by0))
        self.add(small)
        self.play(Create(ring), run_time=0.5)
        # 写真・格子・個数は不透明度で消す（画像を含む Group の FadeOut は最初の数フレームで一瞬消えてちらつく）
        self.play(img.animate.set_opacity(0), pad.animate.set_opacity(0), lines.animate.set_stroke(opacity=0),
                  count.animate.set_opacity(0),
                  small.animate.scale(8 * BLOCK_CELL / CELL).move_to(BLOCK_POS),
                  ring.animate.scale(8 * BLOCK_CELL / CELL).move_to(BLOCK_POS), run_time=1.4)
        blk = BlockGrid(P).move_to(BLOCK_POS)
        blk.nums.set_opacity(0)
        self.add(blk)
        self.remove(small, ring, img, pad, lines, *lines, count)

        # ---- 中身は 64 個の数字 ----
        self.at("nums", -0.1)
        self.play(blk.nums.animate.set_opacity(1), run_time=0.8)

        # ---- 右のほうは小さい ----
        self.at("lr", -0.1)
        right = VGroup(*[blk.num(r, c) for r in range(8) for c in (6, 7)])
        self.play(LaggedStart(*[pop(t, 1.25, 0.5) for t in right], lag_ratio=0.03), run_time=1.2)

        # ---- 波の重ね合わせとして見る ----
        self.at("wave", -0.1)
        self.play(blk.nums.animate.set_opacity(0.25), run_time=0.8)
        self.at("waves", -0.1)
        waves = VGroup(*[row_wave(P[r]) for r in range(8)])
        for r, w in enumerate(waves):
            w.shift(DOWN * u(BLOCK_CELL) * (r - 3.5))
        self.play(LaggedStart(*[Create(w) for w in waves], lag_ratio=0.12), run_time=1.6)

        # ---- 終わり：S05 の始まりと同じ画面 ----
        self.at(self.cue("S04_10.end") + 0.2)
        self.play(FadeOut(waves), blk.nums.animate.set_opacity(1), run_time=0.8)
        self.finish()
