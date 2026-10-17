import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import block_coef, block_dct, block_pixels, idct2, qtable  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from vlib.jparts import GRID_POS, QGRID_POS, QGrid, coef_state, gray_img  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import StageMap  # noqa: E402

PITCH = 58                       # 2 つの表を並べるときのマスの大きさ px
K = PITCH / 66                   # QGrid（66px）から縮める倍率
LX, RX, TY = 700, 1220, 470      # 左の表・右の表の中心
CELL = "#1d212b"
ZERO = "#4a5060"


def fm(v):
    return str(int(v)).replace("-", "−")


def num(v, size=26, color=INK):
    return jp(fm(v), size if abs(v) < 1000 else 22, color)


def heat(v):
    t = min(np.sqrt(min(v, 255) / 255) * 0.8, 1)
    return interpolate_color(ManimColor(CELL), ManimColor(CORAL), t)


def sq(cx, r, c):
    s = Square(side_length=u(PITCH), stroke_width=1.5, stroke_color="#2a2e38", fill_color=CELL, fill_opacity=1)
    return s.move_to(px(cx + PITCH * (c - 3.5), TY + PITCH * (r - 3.5)))


def table(vals, cx, heated=False):
    """右側の表（割る数・元の係数）：マス + 数字"""
    cells, nums = VGroup(), VGroup()
    for r in range(8):
        for c in range(8):
            s = sq(cx, r, c)
            if heated:
                s.set_fill(heat(vals[r, c]))
            cells.add(s)
            nums.add(num(vals[r, c]).move_to(s))
    nums.set_z_index(1)
    return VGroup(cells, nums)


def retable(nums, vals, colors=None):
    """数字を書き換えるアニメーション（同じオブジェクトのまま）"""
    out = []
    for i in range(64):
        v = vals[i // 8, i % 8]
        col = INK if colors is None else colors[i // 8, i % 8]
        out.append(retext(nums[i], num(v, color=col)))
    return out


def coral_img(a, size_px):
    t = np.clip(a / a.max(), 0, 1)[..., None]
    rgb = np.array(color_to_rgb(CELL)) * (1 - t) + np.array(color_to_rgb(CORAL)) * t
    g = (rgb * 255).astype(np.uint8).repeat(16, 0).repeat(16, 1)
    m = ImageMobject(g)
    m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.height = u(size_px)
    return m


def qx(q):
    return 800 + 6 * q


class S06(PScene):
    def construct(self):
        P = block_pixels()
        F = block_dct()
        Fi = np.round(F).astype(int)
        Q = qtable("cat_q80")
        R = block_coef()
        assert (np.round(F / Q).astype(int) == R).all()
        assert np.count_nonzero(R) == 21
        D = R * Q                                   # 掛け直した係数
        rec = idct2(D) + 128                        # そこから作り直したブロック
        err = np.abs(rec - P).mean()
        assert f"{err:.1f}" == "2.5"
        Q95, Q10 = qtable("cat_q95"), qtable("cat_q10")
        R95, R10 = (np.round(F / q).astype(int) for q in (Q95, Q10))
        zeros = {80: int((R == 0).sum()), 95: int((R95 == 0).sum()), 10: int((R10 == 0).sum())}
        assert zeros[10] > zeros[80] > zeros[95]

        # ---- 始まり：S05 の終わり（帯の地図、暗い模様、係数）----
        m = StageMap("strip", active="dct", done=("color", "sub", "block"))
        grid, labels = coef_state(F)
        cells = QGrid(R).cells.move_to(GRID_POS)     # 表のマス（模様の下に敷く）
        cells.set_opacity(0)
        labels.set_z_index(1)
        self.add(m, grid, cells, labels)

        self.at("s06_01")
        self.play(Transform(m, m.state("strip", active="quant", done=("color", "sub", "block", "dct"))),
                  cells.animate.set_opacity(1), grid.tiles.animate.set_opacity(0), run_time=0.8)
        self.remove(grid)

        # ---- 表を左へ、右に割る数の表 ----
        self.at("table", -0.1)
        QT = table(Q, RX)
        self.play(cells.animate.scale(K).move_to(px(LX, TY)),
                  *[labels[i].animate.move_to(px(LX + PITCH * (i % 8 - 3.5), TY + PITCH * (i // 8 - 3.5)))
                    for i in range(64)],
                  FadeIn(QT, shift=LEFT * u(30)), run_time=1.0)
        qcells, qnums = QT
        self.bring_to_front(labels)

        # ---- 割って丸める：左上の数マスは丁寧に、あとは一気に ----
        self.at("round", -0.1)
        def calc_text(r, c):
            assert round(Fi[r, c] / Q[r, c]) == R[r, c]
            return jp(f"{fm(Fi[r, c])} ÷ {Q[r, c]} = {fm(round(Fi[r, c] / Q[r, c], 1))} → {fm(R[r, c])}", 40, INK
                      ).move_to(px(960, 160))

        calc = calc_text(0, 0)
        calc.set_opacity(0)
        self.add(calc)
        self.play(calc.animate.set_opacity(1), retext(labels[0], num(R[0, 0])), pop(qnums[0], 1.4, 0.5), run_time=0.5)
        for r, c in [(0, 1), (1, 0)]:
            i = r * 8 + c
            self.play(retext(labels[i], num(R[r, c])), pop(qnums[i], 1.4, 0.4), run_time=0.4)
        self.at(8.85)
        rest = [i for i in range(64) if i not in (0, 1, 8)]
        self.play(*[retext(labels[i], num(R[i // 8, i % 8])) for i in rest], run_time=0.45)

        # ---- 割る数は場所によってバラバラ ----
        self.at("div", -0.1)
        order = [(r, c) for s in range(15) for r in range(8) for c in range(8) if r + c == s]
        self.play(FadeOut(calc), LaggedStart(*[qcells[r * 8 + c].animate.set_fill(heat(Q[r, c])) for r, c in order],
                                             lag_ratio=0.03),
                  *[n.animate.set_opacity(1) for n in qnums], run_time=1.6)
        self.bring_to_front(qnums)
        self.at("small", -0.1)
        self.play(LaggedStart(*[pop(qnums[r * 8 + c], 1.5, 0.6) for r, c in [(0, 0), (0, 1), (1, 0)]],
                              lag_ratio=0.15), run_time=1.2)
        self.at("large", -0.1)
        self.play(LaggedStart(*[pop(qnums[r * 8 + c], 1.5, 0.6) for r, c in [(7, 7), (6, 7), (7, 6)]],
                              lag_ratio=0.15), run_time=1.2)
        self.at("fine", -0.1)
        fine = [(r, c) for r in range(5, 8) for c in range(5, 8)]
        self.play(LaggedStart(*[pop(qnums[r * 8 + c], 1.4, 0.5) for r, c in fine], lag_ratio=0.08), run_time=1.6)

        # ---- 割った結果：0 は暗く沈む ----
        self.at("s06_05", -0.1)
        zi = [i for i in range(64) if R[i // 8, i % 8] == 0]
        nz = [i for i in range(64) if R[i // 8, i % 8] != 0]
        self.play(*[labels[i].animate.set_color(ZERO) for i in zi], run_time=0.8)

        # ---- 0 でないのは 21 個 ----
        self.at("count", -0.1)
        counter = jp(f"{len(nz)} / 64", 48, YELLOW).move_to(px(LX, 795))
        self.play(*[labels[i].animate.set_color(YELLOW).scale(1.2) for i in nz], FadeIn(counter, shift=UP * u(10)),
                  run_time=1.0)

        # ---- 戻す：割った数を掛け直す ----
        self.at("s06_08", -0.1)
        self.play(*[labels[i].animate.set_color(INK).scale(1 / 1.2) for i in nz], FadeOut(counter), run_time=0.6)
        self.at("mul", -0.1)
        self.play(*retable(labels, D), LaggedStart(*[pop(n, 1.3, 0.5) for n in qnums], lag_ratio=0.01), run_time=1.0)

        # ---- 元の係数と並べる ----
        self.at(41.0)
        orig = retable(qnums, Fi)
        lbl_L, lbl_R = jp("戻した", 32, INK).move_to(px(LX, 185)), jp("元の", 32, INK).move_to(px(RX, 185))
        self.play(*[c.animate.set_fill(CELL) for c in qcells], *orig, FadeIn(lbl_L), FadeIn(lbl_R), run_time=0.9)
        self.bring_to_front(qnums, labels)
        self.at("close", -0.1)
        diff = [i for i in range(64) if D[i // 8, i % 8] != Fi[i // 8, i % 8]]
        self.play(LaggedStart(*[labels[i].animate.set_color(CORAL) for i in diff], lag_ratio=0.02), run_time=1.2)

        # ---- 丸めたぶんが、捨てたもの ----
        self.at("lost", -0.1)
        self.play(pop(m.lossy["quant"], 1.6, 0.9), run_time=0.9)

        # ---- 戻した係数から、ブロックを作り直す ----
        self.at("s06_11", -0.1)
        IMG = 340
        img_o = gray_img(P, IMG).move_to(px(RX, TY))
        self.play(FadeOut(QT), FadeIn(img_o), run_time=0.8)
        self.at("rebuild", -0.1)
        flat = gray_img(np.full((8, 8), 128.0), IMG).move_to(px(LX, TY))
        img_r = gray_img(rec, IMG).move_to(px(LX, TY))
        self.play(FadeOut(VGroup(cells, labels)), FadeIn(flat), lbl_L.animate.move_to(px(LX, 275)),
                  lbl_R.animate.move_to(px(RX, 275)), run_time=0.5)
        self.play(Transform(flat, img_r), run_time=1.2)
        self.at("look", -0.1)
        self.play(pop(flat, 1.08, 0.6), pop(img_o, 1.08, 0.6), run_time=0.6)

        # ---- 明るさのずれは平均 2.5 ----
        self.at("err", -0.1)
        d_img = coral_img(np.abs(rec - P), 140).move_to(px(960, TY))
        d_lbl = jp(f"平均 {err:.1f}", 44, CORAL).move_to(px(960, TY + 70 + 48))
        self.play(FadeIn(d_img, scale=0.8), FadeIn(d_lbl, shift=UP * u(8)), run_time=0.9)

        # ---- 品質：割る数を変えるつまみ ----
        self.at("s06_q", -0.1)
        L2 = table(R, LX)
        for t, v in zip(L2[1], R.flatten()):
            t.set_color(INK if v else ZERO)
        Q2 = table(Q, RX, heated=True)
        cnt = jp(f"0 が {zeros[80]} 個", 44, INK).move_to(px(LX, 795))
        self.play(FadeOut(Group(flat, img_o, d_img, d_lbl, lbl_L, lbl_R)), run_time=0.6)
        self.add(L2, Q2, cnt)
        for mob in (L2, Q2, cnt):
            mob.set_opacity(0)
        self.play(L2.animate.set_opacity(1), Q2.animate.set_opacity(1), cnt.animate.set_opacity(1), run_time=0.8)
        l2cells, l2nums = L2
        q2cells, q2nums = Q2

        self.at("quality", -0.1)
        qlabel = jp("品質（quality）", 36, INK).move_to(px(590, 140))
        track = Line(px(qx(0), 140), px(qx(100), 140), color=DIM, stroke_width=6)
        t0, t100 = jp("0", 28, DIM).move_to(px(qx(0) - 28, 140)), jp("100", 28, DIM).move_to(px(qx(100) + 44, 140))
        knob = Dot(px(qx(80), 140), radius=u(14), color=YELLOW)
        qnum = jp("80", 34, YELLOW).move_to(px(qx(80), 190))
        slider = VGroup(qlabel, track, t0, t100, knob, qnum)
        self.play(FadeIn(slider, shift=DOWN * u(10)), run_time=0.8)

        def set_quality(q, Qq, Rq, rt):
            zc = np.where(Rq == 0, ZERO, INK)
            self.play(knob.animate.move_to(px(qx(q), 140)),
                      retext(qnum, jp(str(q), 34, YELLOW).move_to(px(qx(q), 190))),
                      *[q2cells[i].animate.set_fill(heat(Qq[i // 8, i % 8])) for i in range(64)], *retable(q2nums, Qq),
                      *retable(l2nums, Rq, zc),
                      retext(cnt, jp(f"0 が {int((Rq == 0).sum())} 個", 44, INK)), run_time=rt)
            self.bring_to_front(q2nums, l2nums)

        self.at("q95", -0.1)
        set_quality(95, Q95, R95, 1.6)
        self.at("q10", -0.1)
        set_quality(10, Q10, R10, 1.6)

        # ---- 終わり：品質 80 に戻し、割って丸めた 8×8 だけに（S07 の始まり）----
        self.at(82.4)
        set_quality(80, Q, R, 1.0)
        self.at(83.5)
        self.play(FadeOut(Group(Q2, slider, cnt)), l2cells.animate.scale(1 / K).move_to(QGRID_POS),
                  *[l2nums[i].animate.move_to(px(960 + 66 * (i % 8 - 3.5), 470 + 66 * (i // 8 - 3.5))).scale(30 / 26)
                    for i in range(64)], run_time=0.9)
        self.finish()
