import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.catview import CatView, ViewAnim, window_around, zoom  # noqa: E402
from vlib.data import fmt, size, vp8_info, y_decoded  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NAME = "cat_q10"
BIG_C, BIG_W, BIG_H = (960, 420), 1020, 680       # 大きく映すとき
SIDE_C, SIDE_W = {"off": (640, 245), "on": (1280, 245)}, 620   # 棒を出すときは、なし・ありを上の帯に並べる


def corner_label(text, color, key):
    """画像の左上の内側に置く札 (暗い下地つき)"""
    t = jp(text, 34, color)
    x0 = SIDE_C[key][0] - SIDE_W / 2 + 14
    y0 = SIDE_C[key][1] - SIDE_W / 3 + 12
    back = RoundedRectangle(corner_radius=u(8), width=t.width + u(24), height=t.height + u(16), stroke_width=0,
                            fill_color=BG, fill_opacity=0.8)
    back.move_to(px(x0, y0), aligned_edge=UL)
    t.move_to(back)
    return VGroup(back, t)
EYE_WIN = (112, 80, 256, 176)                     # 目のあたり (画素の座標。16 の倍数にそろえる)
BAR_W, BAR_STEP, BAR_BASE, BAR_K = 46, 60, 880, 280 / 160
CHART_X = {"a": 705, "b": 1215}
STEP_MIN = 8                                      # 「段」として光らせる境目の差


def lum(v):
    g = float(np.clip(v, 0, 255)) / 255
    return rgb_to_color([g, g, g])


def bar(v, i, cx):
    h = max(v * BAR_K, 2)
    r = Rectangle(width=u(BAR_W), height=u(h), stroke_width=2, stroke_color="#9aa0ae",
                  fill_color=lum(v), fill_opacity=1)
    return r.move_to(px(cx + (i - 3.5) * BAR_STEP, BAR_BASE - h / 2))


def bar_num(v, i, cx):
    return mono(str(int(v)), 30, INK).move_to(px(cx + (i - 3.5) * BAR_STEP, BAR_BASE - v * BAR_K - 24))


def renum(old, new):
    """数字を書き換えて、棒の上へ動かす (検査用の文字も更新)"""
    old.text = getattr(new, "text", None)
    return Transform(old, new)


def pick_rows(A, B):
    """目のあたりで、ブロックの縦の境目をまたぐ横 8 点を調べて選ぶ。
    (a) 両側が平らな段で、フィルタで段がいちばん小さくなった所
    (b) フィルタでほぼ変わらなかった (どの点も ±1 以内) 所のうち、8 点の明るさの幅がいちばん大きい所 (本当の模様)"""
    L, T, R, Bm = EYE_WIN
    best_a = best_b = None
    for y in range(T, Bm):
        for x in range(L + 16, R, 16):
            a, b = A[y, x - 4:x + 4], B[y, x - 4:x + 4]
            flat = np.ptp(a[:4]) <= 2 and np.ptp(a[4:]) <= 2
            drop = abs(a[4] - a[3]) - abs(b[4] - b[3])
            if flat and (best_a is None or drop > best_a[0]):
                best_a = (drop, x, y)
            if np.abs(a - b).max() <= 1 and (best_b is None or np.ptp(a) > best_b[0]):
                best_b = (np.ptp(a), x, y)
    return best_a[1:], best_b[1:]


class S07(PScene):
    def construct(self):
        v8 = vp8_info(NAME)
        assert size(NAME) == 3898 and v8["filter"]["level"] == 63 and v8["filter"]["sharpness"] == 0
        A = y_decoded(NAME, filt=False)
        B = y_decoded(NAME, filt=True)
        (xa, ya), (xb, yb) = pick_rows(A, B)
        assert (xa, ya) == (128, 128) and (xb, yb) == (144, 133)
        ra0, ra1 = A[ya, xa - 4:xa + 4], B[ya, xa - 4:xa + 4]
        rb0, rb1 = A[yb, xb - 4:xb + 4], B[yb, xb - 4:xb + 4]
        assert list(ra0) == [103] * 4 + [155] * 4 and abs(ra1[4] - ra1[3]) == 4      # 段 52 → 4
        assert np.abs(rb0 - rb1).max() == 1 and np.ptp(rb0) == 99                     # 坂 (幅 99) はほぼそのまま

        # ---- 品質 10 の WebP (ループフィルタの前) ----
        view = CatView(A, BIG_C, BIG_W, BIG_H)
        view.check_ignore = True
        view.set_opacity(0)
        view.refresh()
        self.add(view)
        self.at("s07_01", -0.1)
        self.play(view.animate.set_opacity(1), run_time=0.8)

        lab_q = jp("品質10", 36, INK).move_to(px(170, 220))
        lab_n = jp(f"{fmt(size(NAME))} バイト", 32, DIM).move_to(px(170, 272))
        self.at("low", -0.1)
        self.play(FadeIn(lab_q, shift=DOWN * u(8)), FadeIn(lab_n, shift=DOWN * u(8)), run_time=0.6)
        self.play(zoom(view, EYE_WIN), run_time=2.0)

        # ---- 16×16 の格子と、境目の段 ----
        self.at("blocks", -0.1)

        def grid_on(t):
            view.grid_mb = t
        self.play(ViewAnim(view, grid_on), run_time=0.8)

        L, T, R, Bm = EYE_WIN
        k = 8
        ov = np.zeros(((Bm - T) * k, (R - L) * k, 4), np.uint8)
        col = (242, 193, 78, 235)
        for x in range(L + 16, R, 16):          # 縦の境目
            for y in range(T, Bm):
                if abs(A[y, x] - A[y, x - 1]) >= STEP_MIN:
                    ov[(y - T) * k:(y - T + 1) * k, (x - L) * k - 3:(x - L) * k + 3] = col
        for y in range(T + 16, Bm, 16):         # 横の境目
            for x in range(L, R):
                if abs(A[y, x] - A[y - 1, x]) >= STEP_MIN:
                    ov[(y - T) * k - 3:(y - T) * k + 3, (x - L) * k:(x - L + 1) * k] = col
        steps = ImageMobject(ov)
        steps.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        steps.width = view.width
        steps.move_to(view)
        steps.check_ignore = True
        self.at("edge", -0.1)
        self.play(FadeIn(steps), run_time=0.8)
        self.play(steps.animate(rate_func=there_and_back).set_opacity(0.35), run_time=1.2)

        # ---- 上へ寄せて、境目をまたぐ 8 点 ----
        self.at("filter", -0.1)
        def grid_off(t):
            view.grid_mb = 1 - t
        self.play(FadeOut(steps), ViewAnim(view, grid_off), run_time=0.5)
        self.remove(steps)
        lab_off = corner_label("ループフィルタなし", INK, "off")
        self.play(view.animate.set(width=u(SIDE_W)).move_to(px(*SIDE_C["off"])), FadeIn(lab_off), run_time=1.0)

        def fly_bars(x0, y0, vals, cx, color, extra=()):
            """画像の 8 点が、下の棒になる"""
            rect = view.track_rect(x0 - 4, y0, 8, 1, stroke_color=color, stroke_width=4)
            p = view.pix()
            bars, nums, srcs = VGroup(), VGroup(), []
            for i, v in enumerate(vals):
                s = Square(p, stroke_width=0, fill_color=lum(v), fill_opacity=1)
                s.move_to(view.to_point(x0 - 4 + i + 0.5, y0 + 0.5))
                s.check_ignore = True
                srcs.append(s)
                bars.add(bar(v, i, cx))
                nums.add(bar_num(v, i, cx))
            edge = DashedLine(px(cx, BAR_BASE + 14), px(cx, BAR_BASE - 150), color=INK, stroke_width=4,
                              dash_length=u(10))
            self.play(Create(rect), LaggedStart(*[ReplacementTransform(s, b) for s, b in zip(srcs, bars)],
                                                lag_ratio=0.06),
                      FadeIn(nums), Create(edge), *extra, run_time=1.2)
            return rect, bars, nums, edge

        self.at("smooth", -0.1)
        rect_a, bars_a, nums_a, edge_a = fly_bars(xa, ya, ra0, CHART_X["a"], YELLOW)

        def morph(bars, nums, vals, cx, extra=(), run_time=1.1):
            ghosts = VGroup()
            for b in bars:
                g = b.copy().set_fill(opacity=0).set_stroke(DIM, 2, opacity=0.8)
                g.check_ignore = True
                ghosts.add(g)
            self.add(ghosts)
            self.play(*[Transform(b, bar(v, i, cx)) for i, (b, v) in enumerate(zip(bars, vals))],
                      *[renum(n, bar_num(v, i, cx)) for i, (n, v) in enumerate(zip(nums, vals))],
                      *extra, run_time=run_time)
            return ghosts

        # ---- 棒が坂に、画像全体もフィルタありに (数字は 2.5 秒以上読めるように、ここで変える) ----
        # 右に、同じ窓・同じ倍率のフィルタあり
        von = CatView(B, SIDE_C["on"], BIG_W, BIG_H, win=EYE_WIN)
        von.width = u(SIDE_W)
        von.move_to(px(*SIDE_C["on"]))
        von.check_ignore = True
        lab_lf = corner_label("ループフィルタあり", CYAN, "on")
        self.at("lf", -0.3)
        ghost_a = morph(bars_a, nums_a, ra1, CHART_X["a"],
                        extra=(FadeIn(von, shift=LEFT * u(30)), FadeIn(lab_lf, shift=LEFT * u(30))), run_time=1.6)

        self.at("gone", -0.1)
        self.play(pop(von, 1.05, 0.7), run_time=0.7)

        # ---- 目のふちの坂は、ほぼそのまま ----
        self.at("texture", -0.1)
        rect_b, bars_b, nums_b, edge_b = fly_bars(xb, yb, rb0, CHART_X["b"], YELLOW,
                                                  extra=(rect_a.animate.set_stroke(opacity=0.35),))

        t_a = jp("平らな所の段 → ならす", 32, INK).move_to(px(CHART_X["a"], 505))
        t_b = jp("本当の模様 → ほぼそのまま", 32, INK).move_to(px(CHART_X["b"], 505))
        self.at("check", -0.25)
        ghost_b = morph(bars_b, nums_b, rb1, CHART_X["b"],
                        extra=(FadeIn(t_a, shift=DOWN * u(6)), FadeIn(t_b, shift=DOWN * u(6))))

        self.at("wise", -0.1)
        self.play(pop(VGroup(t_a, t_b), 1.06, 0.6), run_time=0.6)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 0.8)
        rest = VGroup(lab_q, lab_n, lab_lf, lab_off, rect_a, rect_b, bars_a, nums_a, edge_a, ghost_a,
                      bars_b, nums_b, edge_b, ghost_b, t_a, t_b)
        rect_a.clear_updaters()
        rect_b.clear_updaters()
        self.play(view.animate.set_opacity(0), von.animate.set_opacity(0), FadeOut(rest), run_time=0.7)
        self.remove(view, von, rest, *rest)
        self.finish()
