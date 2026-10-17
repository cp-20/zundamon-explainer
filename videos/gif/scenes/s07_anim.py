import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import fmt, frame_rgba, info  # noqa: E402
from zunda.fx import pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NAME = "zunda_anim"
THUMB_H, THUMB_Y, STEP = 240, 270, 205
TAG_Y = 125
STAGE_H, STAGE_X, STAGE_Y = 480, 960, 660


class S07(PScene):
    def construct(self):
        inf = info(NAME)
        fr = inf["frames"]
        n = len(fr)
        delays = [f["gce"]["delay"] for f in fr]
        sizes = [f["data_bytes"] for f in fr]
        W_, H_ = inf["width"], inf["height"]
        rgba = [frame_rgba(NAME, k) for k in range(n)]
        f1 = fr[1]
        rect = (f1["left"], f1["top"], f1["width"], f1["height"])
        assert rect == (26, 50, 69, 31) and delays[0] == 60 and delays[1] == 12
        assert 900 <= sizes[1] <= 1100
        app = [b for b in inf["blocks"] if b["kind"] == "app"][0]
        assert app["name"] == "NETSCAPE2.0" and app["loop"] == 0

        # 変わった画素（1 コマ目 → 2 コマ目）。すべて 2 コマ目の画像ブロックの中にある
        diff = (rgba[0] != rgba[1]).any(axis=2)
        ys, xs = np.nonzero(diff)
        L, T, RW, RH = rect
        assert xs.min() >= L and xs.max() < L + RW and ys.min() >= T and ys.max() < T + RH

        # ---- 8 コマが横に並ぶ ----
        thumbs = Group(*[png_mob(rgba[k], THUMB_H, nearest=True).move_to(px(960 + STEP * (k - (n - 1) / 2), THUMB_Y))
                         for k in range(n)])
        self.at("anim", -0.2)
        self.play(LaggedStart(*[FadeIn(t, shift=UP * u(10)) for t in thumbs], lag_ratio=0.12), run_time=1.3)

        # ---- 待ち時間の札 ----
        self.at("gce", -0.1)
        tags = VGroup(*[jp(str(d), 36, INK).move_to(px(960 + STEP * (k - (n - 1) / 2), TAG_Y))
                        for k, d in enumerate(delays)])
        self.play(LaggedStart(*[FadeIn(t, shift=DOWN * u(8)) for t in tags], lag_ratio=0.1), run_time=1.2)
        self.at("unit", -0.1)
        unit = mix(f"{delays[0]} → {delays[0] / 100:g} 秒", 48, YELLOW).move_to(px(960, 600))
        self.play(FadeIn(unit, shift=UP * u(8)), tags[0].animate.set_color(YELLOW), run_time=0.7)

        # ---- まばたきのコマは短い ----
        self.at("blink", -0.1)
        ul = underline(tags[1], YELLOW)
        self.play(Create(ul), tags[0].animate.set_color(INK), tags[1].animate.set_color(YELLOW), run_time=0.6)

        # ---- 2 コマ目は、変わったところだけ ----
        self.at("only", -0.3)
        SX1, SX2 = 700, 1250
        big = png_mob(rgba[0], STAGE_H, nearest=True).move_to(px(SX1, STAGE_Y))
        self.play(FadeOut(unit), FadeIn(big, shift=UP * u(10)), tags[1].animate.set_color(INK), FadeOut(ul), run_time=0.7)
        sc = big.height / H_
        tl1 = big.get_corner(UL)

        def at_px(tl, x, y):
            return tl + RIGHT * sc * x + DOWN * sc * y

        # 2 コマ目の画像ブロック：その長方形だけ（あとは空）
        empty = png_mob(np.zeros((H_, W_, 4), dtype=np.uint8), STAGE_H, nearest=True).move_to(px(SX2, STAGE_Y))
        tl2 = empty.get_corner(UL)
        patch = ImageMobject(rgba[1][T:T + RH, L:L + RW])
        patch.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        patch.height = RH * sc
        patch.move_to(at_px(tl2, L + RW / 2, T + RH / 2))
        pbox = Rectangle(width=RW * sc, height=RH * sc, stroke_color=YELLOW, stroke_width=5).move_to(patch)
        size_lab = mix(f"{RW}×{RH}", 32, YELLOW).next_to(empty, LEFT, buff=u(50))
        size_lab.set_y(patch.get_center()[1])
        self.at("diff", -0.3)
        self.play(FadeIn(empty, shift=UP * u(10)), run_time=0.6)
        self.play(FadeIn(patch), Create(pbox), FadeIn(size_lab, shift=UP * u(6)), run_time=0.7)

        self.at("face", -0.1)
        tgt = at_px(tl1, L + RW / 2, T + RH / 2)
        grp = Group(patch, pbox)
        self.play(grp.animate.shift(tgt - patch.get_center()), size_lab.animate.set_opacity(0.4), run_time=1.0)
        big2 = png_mob(rgba[1], STAGE_H, nearest=True).move_to(big)
        self.add(big2)
        self.remove(big)
        self.bring_to_front(patch, pbox)
        self.play(pop(pbox, 1.3, 0.6), run_time=0.6)

        self.at("rest", -0.1)
        self.play(FadeOut(Group(empty, size_lab)), run_time=0.6)
        big, ov, box = big2, patch, pbox

        # ---- 各コマのデータの大きさ ----
        self.at("size", -0.9)
        ROW0, DY, X_BAR = 500, 50, 620
        scale = 600 / max(sizes)
        bars, labs, nums = VGroup(), VGroup(), VGroup()
        for k, s in enumerate(sizes):
            y = ROW0 + DY * k
            b = Rectangle(width=u(max(s * scale, 2)), height=u(40), stroke_width=0, fill_color=BLUE, fill_opacity=1)
            b.move_to(px(X_BAR, y), aligned_edge=LEFT)
            bars.add(b)
            labs.add(jp(str(k + 1), 32, INK).move_to(px(X_BAR - 40, y)))
            nums.add(mix(fmt(s), 32, INK).next_to(b, RIGHT, buff=u(14)))
        self.play(FadeOut(Group(big, ov, box)), run_time=0.5)
        self.play(LaggedStart(*[AnimationGroup(FadeIn(labs[k]), GrowFromEdge(bars[k], LEFT), FadeIn(nums[k]))
                                for k in range(n)], lag_ratio=0.1), run_time=1.1)
        self.at("small", -0.2)
        self.play(bars[1].animate.set_color(YELLOW), nums[1].animate.set_color(YELLOW), pop(bars[1], 1.15, 0.6),
                  run_time=0.6)

        self.at("smart", -0.1)
        self.play(LaggedStart(*[pop(bars[k], 1.2, 0.5) for k in range(1, n)], lag_ratio=0.2), run_time=1.8)

        # ---- くり返しの印 ----
        self.at("loop", -0.1)
        self.play(FadeOut(Group(bars, labs, nums)), run_time=0.5)
        nets = mono(app["name"], 40, PURPLE).move_to(px(780, 600))
        rep = mix("くり返し 0 ＝ ずっと", 44, INK).move_to(px(780, 690))
        self.play(FadeIn(nets, shift=UP * u(8)), FadeIn(rep, shift=UP * u(8)), run_time=0.7)

        # ---- 元の大きさで動き出す（本物の待ち時間で、コマを切り替える）----
        stamp = Group(*[png_mob(rgba[k], 480, nearest=True).move_to(px(1250, 660)) for k in range(n)])
        for k in range(1, n):
            stamp[k].set_opacity(0)
        self.add(*stamp[1:])
        self.play(FadeIn(stamp[0]), run_time=0.3)
        end = self.tl["duration"] - 0.9
        k = 0
        t_next = self.now + delays[0] / 100
        while True:
            self.at(t_next)
            if t_next + 0.0 >= end:
                break
            k = (k + 1) % n
            for j in range(n):
                stamp[j].set_opacity(1 if j == k else 0)
            self.wait(1 / FPS)
            t_next += delays[k] / 100
            if t_next > end:
                t_next = end
        self.at(end)
        self.play(FadeOut(Group(tags, thumbs, nets, rep)), stamp[k].animate.set_opacity(0), run_time=0.8)
        self.remove(*stamp)
        self.finish()
