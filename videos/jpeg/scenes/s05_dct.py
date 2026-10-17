import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import ZIGZAG, block_dct, block_pixels, idct2  # noqa: E402
from zunda.fx import pop, retext, underline  # noqa: E402
from vlib.jparts import BLOCK_CELL, BLOCK_POS, BasisGrid, BlockGrid, gray_img  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import STAGE_COL, StageMap  # noqa: E402

WAVE = STAGE_COL["dct"]
# 1行の棒グラフ
BAR_X0, BAR_STEP, BAR_W = 520, 62, 46
BASE_Y, BAR_K = 730, 2.6          # 底の y と、明るさ 1 あたりの高さ px
# 8種類の波の列
WAVE_X, WAVE_W, WAVE_Y0, WAVE_DY, WAVE_AMP = 1160, 230, 182, 74, 24
AMT_X = 1340


def cosw(k, t):
    """k 番目の波（t は画素の位置 0..7 を連続にしたもの）"""
    return np.cos((2 * t + 1) * k * np.pi / 16)


def wave_mob(k, color=DIM, width=4, amp=WAVE_AMP):
    """k 番目の波の見本（まだ足していない波は灰色）。amp は振れ幅 px（負なら上下反転）"""
    cy = WAVE_Y0 + WAVE_DY * k
    ts = np.linspace(-0.5, 7.5, 120)
    pts = [px(WAVE_X - WAVE_W / 2 + WAVE_W * (t + 0.5) / 8, cy - amp * (cosw(k, t) if k else 0.0)) for t in ts]
    return VMobject(stroke_color=color, stroke_width=width).set_points_smoothly(pts)


def sum_curve(A, upto, color=WAVE, width=6):
    """最初の upto+1 個の波を足した形を、棒グラフの上に描く"""
    ts = np.linspace(-0.5, 7.5, 160)
    f = sum(A[j] * cosw(j, ts) for j in range(upto + 1))
    pts = [px(BAR_X0 + BAR_STEP * t, BASE_Y - BAR_K * v) for t, v in zip(ts, f)]
    return VMobject(stroke_color=color, stroke_width=width).set_points_smoothly(pts)


def partial(F, k):
    """ジグザグ順で最初の k 個の模様だけを足したブロック（明るさ）"""
    G = np.zeros((8, 8))
    for r, c in ZIGZAG[:k]:
        G[r, c] = F[r, c]
    return idct2(G) + 128


class S05(PScene):
    def construct(self):
        P = block_pixels()               # 主役のブロック（元の明るさ）
        F = block_dct()                  # その DCT 係数
        row = P[0]
        n = np.arange(8)
        C = cosw(n[:, None], n[None, :])
        A = (C @ row) * np.array([1 / 8] + [2 / 8] * 7)   # 1行ぶん：波ごとの振れ幅（明るさの単位）
        assert np.allclose(A @ C, row)
        amps = [int(round(a)) for a in A]

        # ---- 始まり：S04 の終わり（地図の帯＝8×8に切る、主役のブロック）----
        m = StageMap("strip", active="block", done=("color", "sub"))
        blk = BlockGrid(P).move_to(BLOCK_POS)
        self.add(m, blk)

        self.at("s05_01")
        self.play(Transform(m, m.state("strip", active="dct", done=("color", "sub", "block"))), run_time=0.8)

        # ---- 1行だけ：一番上の行が棒グラフに ----
        self.at("row", -0.2)
        mini = blk.copy()
        mini.scale(22 / BLOCK_CELL).move_to(px(250, 300))
        for i in range(8, 64):
            mini.cells[i].set_opacity(0.3)
        mini.nums.set_opacity(0)
        bars = VGroup()
        for i, v in enumerate(row):
            b = Rectangle(width=u(BAR_W), height=u(BAR_K * v), stroke_width=0,
                          fill_color=rgb_to_color([v / 255] * 3), fill_opacity=1)
            b.move_to(px(BAR_X0 + BAR_STEP * i, BASE_Y), aligned_edge=DOWN)
            bars.add(b)
        base = Line(px(BAR_X0 - 40, BASE_Y), px(BAR_X0 + BAR_STEP * 7 + 40, BASE_Y), stroke_width=3, color=DIM)
        vals = VGroup(*[jp(str(int(round(v))), 28, INK).next_to(b, UP, buff=u(10)) for v, b in zip(row, bars)])
        top_cells = VGroup(*[blk.cells[i].copy() for i in range(8)])
        self.add(top_cells)
        self.play(Transform(blk, mini),
                  LaggedStart(*[Transform(c, b) for c, b in zip(top_cells, bars)], lag_ratio=0.05),
                  Create(base), run_time=1.4)
        self.remove(top_cells, *top_cells)  # 中身も個別に場面へ入っているので、まとめて外す
        self.add(bars)
        self.play(LaggedStart(*[FadeIn(v, shift=DOWN * u(6)) for v in vals], lag_ratio=0.05), run_time=0.6)

        # ---- 8種類の波 ----
        waves = VGroup(*[wave_mob(k) for k in range(8)])
        axes = VGroup(*[Line(px(WAVE_X - WAVE_W / 2, WAVE_Y0 + WAVE_DY * k), px(WAVE_X + WAVE_W / 2, WAVE_Y0 + WAVE_DY * k),
                             stroke_width=1.5, color="#333846") for k in range(8)])
        for k, cue in [(0, "w0"), (1, "w1"), (2, "w2")]:
            self.at(cue, -0.1)
            self.play(FadeIn(axes[k]), Create(waves[k]), run_time=0.7)
        self.at("w7", -0.2)
        self.play(LaggedStart(*[AnimationGroup(FadeIn(axes[k]), Create(waves[k])) for k in range(3, 8)],
                              lag_ratio=0.3), run_time=1.8)

        # ---- 「波を足すと？」：波の間に ＋ ----
        self.at("how")
        plus = VGroup(*[jp("＋", 26, DIM).move_to(px(WAVE_X - WAVE_W / 2 - 34, WAVE_Y0 + WAVE_DY * (k + 0.5)))
                        for k in range(7)])  # 波と波のあいだの「＋」（足すたびに消え、左の点に替わる）
        self.play(LaggedStart(*[FadeIn(p, scale=0.6) for p in plus], lag_ratio=0.1), run_time=1.0)

        # ---- 足していく：平らな波 → ゆっくりの波 → 残り ----
        self.at("a0", -0.1)
        curve = sum_curve(A, 0)
        fly = waves[0].copy().set_stroke(WAVE)
        added = VGroup(*[Dot(px(WAVE_X - WAVE_W / 2 - 34, WAVE_Y0 + WAVE_DY * k), radius=u(8), color=WAVE)
                         for k in range(8)])
        self.play(ReplacementTransform(fly, curve), waves[0].animate.set_stroke(WAVE),
                  FadeOut(plus[0]), FadeIn(added[0], scale=2), run_time=1.0)

        def add_wave(k, rt):
            fly = waves[k].copy().set_stroke(WAVE)
            fly.check_ignore = True
            anims = [fly.animate.move_to(curve).set_opacity(0), Transform(curve, sum_curve(A, k)),
                     waves[k].animate.set_stroke(WAVE), FadeIn(added[k], scale=2)]
            if k < 7:
                anims.append(FadeOut(plus[k]))
            self.play(*anims, run_time=rt)
            self.remove(fly)

        self.at("a1", -0.1)
        add_wave(1, 1.2)
        self.at("a2", -0.1)
        for k in range(2, 8):
            add_wave(k, 0.5)

        # ---- ぴったり：棒の頭に点 ----
        self.at("fit", -0.1)
        dots = VGroup(*[Dot(px(BAR_X0 + BAR_STEP * i, BASE_Y - BAR_K * v), radius=u(8), color=YELLOW)
                        for i, v in enumerate(row)])
        self.play(LaggedStart(*[FadeIn(d, scale=2) for d in dots], lag_ratio=0.08), run_time=0.9)

        # ---- 波ごとの量 ----
        self.at("amount", -0.1)
        amt = VGroup(*[jp(f"×{a}".replace("-", "−"), 30, INK).move_to(px(AMT_X, WAVE_Y0 + WAVE_DY * k), aligned_edge=LEFT)
                       for k, a in enumerate(amps)])
        for a in amt:
            a.shift(LEFT * u(30))
        # 波そのものも、掛けた倍率の高さに（いちばん大きい 57 を見本の高さに）
        ref = max(abs(a) for a in amps[1:])
        scaled = [wave_mob(k, WAVE, amp=WAVE_AMP * 1.25 * amps[k] / ref) if k else waves[0].copy() for k in range(8)]
        self.play(FadeOut(dots), *[Transform(waves[k], scaled[k]) for k in range(1, 8)],
                  LaggedStart(*[FadeIn(a, shift=LEFT * u(10)) for a in amt], lag_ratio=0.08), run_time=1.2)

        self.at("look", -0.1)
        self.play(LaggedStart(*[pop(a, 1.2, 0.5) for a in amt], lag_ratio=0.12), run_time=1.6)

        # ---- 最初の数個は大きく、後ろは小さい ----
        self.at("few", -0.1)
        big3 = [k for k in range(8) if abs(amps[k]) >= 20]
        assert big3 == [0, 1, 2], amps
        self.play(*[amt[k].animate.set_color(DIM) for k in range(3, 8)], run_time=0.8)

        # ---- となりどうしがなめらか → ゆっくりの波だけでほとんど表せる ----
        self.at("smooth", -0.1)
        self.play(*[w.animate.set_stroke(opacity=0.25) for w in waves[3:]],
                  *[a.animate.set_opacity(0.3) for a in amt[3:]], *[d.animate.set_opacity(0.25) for d in added[3:]],
                  *[amt[k].animate.set_color(YELLOW).scale(1.2) for k in big3], run_time=0.8)
        self.at("slow", -0.1)
        approx = sum_curve(A, 2, YELLOW, 6)
        self.play(Transform(curve, approx), run_time=1.2)

        # ---- 縦と横の両方で：64 種類の模様 ----
        self.at("s05_12", -0.1)
        self.play(*[FadeOut(x, shift=UP * u(20)) for x in (bars, vals, base, curve, waves, axes, added, amt)],
                  run_time=0.9)
        self.at("grid", -0.1)
        grid = BasisGrid()
        self.play(LaggedStart(*[FadeIn(t, scale=0.7) for t in grid.zigzag()], lag_ratio=0.04), run_time=2.2)

        self.at("checker", -0.1)
        corner = [grid.at(7, 7), grid.at(6, 7), grid.at(7, 6)]
        self.play(LaggedStart(*[pop(t, 1.5, 0.8) for t in corner], lag_ratio=0.25), run_time=1.4)

        # ---- 目のブロックは、64 個の模様を何倍かして足したもの ----
        self.at("s05_14", -0.1)
        target_lbl = jp("目のブロック", 30, INK).move_to(px(1260, 150))
        target = gray_img(P, 200).move_to(px(1260, 290))
        res = gray_img(np.full((8, 8), 128.0), 300).move_to(px(1260, 600))
        res_lbl = jp("足した結果", 30, INK).move_to(px(1260, 430))
        for i in range(8, 64):
            blk.cells[i].set_opacity(1)
        self.play(blk.animate.scale(200 / (22 * 8)).move_to(target), FadeIn(target_lbl), run_time=1.0)
        self.remove(blk)
        self.add(target)
        self.play(FadeIn(res), FadeIn(res_lbl), run_time=0.6)

        self.at("build", -0.1)
        count = mix("0 / 64", 30, DIM).move_to(px(1260, 780))
        count.check_ignore = True  # 数えている途中の数字（読むものではなく、増えていく様子を見せる）
        self.add(count)
        order = grid.zigzag()

        def step(k, rt):
            """k 番目（1始まり）の模様を結果に足す"""
            fly = order[k - 1].copy()
            fly.check_ignore = True
            new = gray_img(partial(F, k), 300).move_to(res)
            self.add(fly)
            self.play(fly.animate.move_to(res).scale(2.2).set_opacity(0),
                      Transform(res, new), retext(count, mix(f"{k} / 64", 30, DIM)), run_time=rt)
            self.remove(fly)

        for k in range(1, 7):        # 最初の 6 個は 1 つずつ
            step(k, 0.7)
        self.at("almost", -0.1)
        self.play(pop(res, 1.08, 0.6), run_time=0.6)
        k = 6
        for nxt, rt in [(10, 0.6), (15, 0.5), (21, 0.5), (28, 0.5), (36, 0.5), (45, 0.5), (55, 0.5), (64, 0.5)]:
            flies = Group(*[order[j].copy() for j in range(k, nxt)])
            for f_ in flies:
                f_.check_ignore = True
            self.add(flies)
            new = gray_img(partial(F, nxt), 300).move_to(res)
            self.play(LaggedStart(*[f_.animate.move_to(res).scale(2.2).set_opacity(0) for f_ in flies], lag_ratio=0.1),
                      Transform(res, new), retext(count, mix(f"{nxt} / 64", 30, DIM)), run_time=rt)
            self.remove(flies, *flies)
            k = nxt
        assert np.allclose(partial(F, 64), P)

        # ---- 模様ごとの量 ----
        self.at("s05_16", -0.1)
        for t in grid.tiles:
            t.check_ignore = True  # 暗くした模様は、係数の数字の下敷き
        self.play(*[t.animate.set_opacity(0.28) for t in grid.tiles],
                  FadeOut(Group(res, res_lbl, count, target, target_lbl)), run_time=0.8)
        self.at("coef", -0.1)
        labels = grid.coef_labels(F)
        zz = [labels[r * 8 + c] for r, c in ZIGZAG]
        self.play(LaggedStart(*[FadeIn(t, scale=0.8) for t in zz], lag_ratio=0.03), run_time=1.6)

        # ---- 離散コサイン変換（DCT）----
        self.at("name", -0.1)
        nm = jp("DCT", 72, WAVE).move_to(px(1250, 250))
        self.play(FadeIn(nm, shift=UP * u(10)), run_time=0.6)
        self.at("abbr", -0.1)
        en = jp("Discrete Cosine Transform", 34, INK, t2c={"D": YELLOW, "C": YELLOW, "T": YELLOW})
        en.move_to(px(1250, 340))
        self.play(FadeIn(en, shift=UP * u(8)), run_time=0.7)
        self.at("jp", -0.1)
        ja = jp("離散コサイン変換", 40, WAVE).move_to(px(1250, 420))
        self.play(FadeIn(ja, shift=UP * u(8)), run_time=0.6)
        self.at("cos", -0.1)
        ts = np.linspace(-0.5, 7.5, 80)
        cw = VMobject(stroke_color=WAVE, stroke_width=4).set_points_smoothly(
            [px(1180 + 140 * (t + 0.5) / 8, 500 - 18 * cosw(2, t)) for t in ts])
        cl = jp("コサイン＝波", 30, INK).next_to(cw, RIGHT, buff=u(16))
        self.play(Create(cw), FadeIn(cl), run_time=0.8)
        names = VGroup(nm, en, ja, cw, cl)

        # ---- 大きい数字は左上 ----
        self.at("big", -0.1)
        self.play(FadeOut(names), run_time=0.6)
        self.at("bigz", -0.1)
        strong = [t for t in zz if t.strong]
        self.play(LaggedStart(*[pop(t, 1.35, 0.6) for t in strong], lag_ratio=0.12), run_time=1.6)

        # ---- 左上に大きいのが少し／右下に小さいのがたくさん ----
        self.at("s05_19", -0.1)
        self.at("left", -0.1)
        few = jp("大きいのが少し", 34, YELLOW).move_to(px(250, 120))
        many = jp("小さいのがたくさん", 34, CORAL).move_to(px(1250, 640))
        weak = VGroup(*[t for t in zz if not t.strong])
        a1 = Arrow(few.get_bottom(), grid.at(0, 0).get_left() + LEFT * u(6), buff=u(10), color=YELLOW,
                   stroke_width=4, max_tip_length_to_length_ratio=0.15)
        a2 = Arrow(many.get_left(), grid.at(6, 7).get_right() + RIGHT * u(4), buff=u(10), color=CORAL,
                   stroke_width=4, max_tip_length_to_length_ratio=0.15)
        self.play(FadeIn(few), GrowArrow(a1), run_time=0.8)
        self.play(FadeIn(many), GrowArrow(a2), weak.animate.set_color(CORAL), run_time=1.0)
        # ここで画面は jparts.coef_state(F) と同じ（S06 はそこから始める）

        # ---- 終わり：S06 の始まりと同じ画面（帯の地図、暗い模様、係数）----
        self.at(self.tl["duration"] - 1.2)
        self.play(FadeOut(VGroup(few, many, a1, a2)), run_time=0.8)
        self.finish()
