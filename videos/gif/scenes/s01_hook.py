import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import fmt, frame_rgba, info, png_sizes  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NAME = "zunda_anim"
GREEN = "#7ee08a"
STAMP_H = 480
STAMP_C = (960, 310)
FRAME_H, FRAME_GAP, FRAME_Y = 170, 20, 130
LABEL_Y0, LABEL_Y1 = 620, 270
BAR_X, BAR_W, BAR_H = 560, 650, 64
ROW_Y = [470, 610, 750]
ONE_W = 640   # 「PNG 1コマ」の棒をここまで伸ばす


class S01(PScene):
    def construct(self):
        inf = info(NAME)
        n = len(inf["frames"])
        delays = [f["gce"]["delay"] / 100 for f in inf["frames"]]   # 秒
        sizes = png_sizes(NAME)
        gif_bytes = inf["file_bytes"]
        # 台詞の数字
        assert n == 8 and sizes[0] == 42099 and sum(sizes) >= 330000 and gif_bytes == 28615, (n, sizes, gif_bytes)
        assert gif_bytes < sizes[0]
        scale = BAR_W / sum(sizes)

        # ---- 動くスタンプ：8 枚を重ね、コマの待ち時間どおりに不透明度で切り替える ----
        imgs = [png_mob(frame_rgba(NAME, k), STAMP_H, nearest=True).move_to(px(*STAMP_C)) for k in range(n)]
        for im in imgs:
            im.set_opacity(0)
        for im in imgs[1:]:
            im.check_ignore = True
        st = dict(t=0.0, on=True, a=0.0)
        total = sum(delays)

        def animate_stamp(_, dt):
            if not st["on"]:
                return
            st["t"] = (st["t"] + dt) % total
            acc, cur = 0.0, n - 1
            for k, d in enumerate(delays):
                acc += d
                if st["t"] < acc:
                    cur = k
                    break
            a = st['a']
            for k, im in enumerate(imgs):
                im.set_opacity(a if k == cur else 0)

        host = imgs[0]
        host.add_updater(animate_stamp)
        self.add(*imgs)

        label = jp(f"{NAME}.gif", 36, INK).move_to(px(STAMP_C[0], LABEL_Y0))
        label.set_opacity(0)

        self.at("stamp", -0.1)
        label.set_opacity(1)
        self.play(UpdateFromAlphaFunc(host, lambda m, al: st.__setitem__('a', al)), FadeIn(label, shift=UP * u(8)), run_time=0.6)

        # ---- 「ギフ？ジフ？」：ファイル名の .gif を指す ----
        self.at("read", -0.1)
        self.play(pop(label, 1.15, 0.6), run_time=0.6)

        # ---- 8 コマに分かれて横に並ぶ ----
        self.at("frames", -0.1)
        fw = imgs[0].width * UNIT * FRAME_H / STAMP_H
        xs = [960 + (fw + FRAME_GAP) * (k - (n - 1) / 2) for k in range(n)]
        st["on"] = False
        host.clear_updaters()
        for im in imgs[1:]:
            im.check_ignore = False
        self.play(*[im.animate.scale(FRAME_H / STAMP_H).move_to(px(xs[k], FRAME_Y)).set_opacity(1)
                    for k, im in enumerate(imgs)],
                  label.animate.move_to(px(STAMP_C[0], LABEL_Y1)), run_time=1.0)

        # ---- ファイルの大きさ ----
        self.at("size", -0.1)
        new = jp(f"{NAME}.gif　{fmt(gif_bytes)} バイト", 36, INK, t2c={f"{fmt(gif_bytes)} バイト": YELLOW})
        self.play(retext(label, new), run_time=0.6)

        # ---- 比べる：棒 ----
        def row_name(text, y, color):
            return jp(text, 36, color).move_to(px(BAR_X, y - 58), aligned_edge=LEFT)

        def bar_rect(w, y, color):
            return Rectangle(width=u(w), height=u(BAR_H), stroke_width=0, fill_color=color, fill_opacity=1) \
                .move_to(px(BAR_X, y), aligned_edge=LEFT)

        def num_text(v, y, w, color=INK):
            return jp(f"{fmt(v)} バイト", 34, color).move_to(px(BAR_X + w + 24, y), aligned_edge=LEFT)

        # PNG 1 コマ
        self.at("png1", -0.1)
        y1 = ROW_Y[0]
        n1 = row_name("PNG 1コマ", y1, CORAL)
        b1 = bar_rect(sizes[0] * scale, y1, CORAL)
        c1 = num_text(sizes[0], y1, sizes[0] * scale)
        self.play(FadeOut(label, shift=UP * u(8)), FadeIn(n1, shift=UP * u(8)), GrowFromEdge(b1, LEFT),
                  FadeIn(c1, shift=RIGHT * u(10)), run_time=0.8)
        self.play(pop(imgs[0], 1.1, 0.5), run_time=0.5)

        # PNG 8 コマ：コマごとの大きさを積む
        self.at("png8", -0.1)
        y2 = ROW_Y[1]
        n2 = row_name("PNG 8コマ", y2, CORAL)
        segs, x = [], BAR_X
        for k in range(n):
            w = sizes[k] * scale
            s = Rectangle(width=u(w), height=u(BAR_H), stroke_width=0,
                          fill_color=CORAL if k % 2 == 0 else "#b8503f", fill_opacity=1).move_to(px(x, y2), aligned_edge=LEFT)
            segs.append(s)
            x += w
        bar2 = VGroup(*segs)
        total_png = sum(sizes)
        c2 = num_text(total_png, y2, BAR_W)
        self.play(FadeIn(n2, shift=UP * u(8)), run_time=0.5)
        self.play(LaggedStart(*[AnimationGroup(GrowFromEdge(segs[k], LEFT), pop(imgs[k], 1.1, 0.4))
                                for k in range(n)], lag_ratio=0.3), run_time=2.3)
        self.play(FadeIn(c2), run_time=0.4)

        # GIF
        self.at("gif", -0.1)
        y3 = ROW_Y[2]
        n3 = row_name("GIF 8コマ", y3, GREEN)
        b3 = bar_rect(gif_bytes * scale, y3, GREEN)
        c3 = num_text(gif_bytes, y3, gif_bytes * scale, GREEN)
        self.play(FadeIn(n3, shift=UP * u(8)), GrowFromEdge(b3, LEFT), FadeIn(c3, shift=RIGHT * u(10)), run_time=0.9)

        # ---- PNG 1 枚より、GIF 8 枚のほうが小さい ----
        self.at("one", -0.1)
        # PNG 8 コマを消し、残る 2 本を同じ棒のまま伸ばして比べる
        k2 = ONE_W / sizes[0]
        w1, w3 = sizes[0] * k2, gif_bytes * k2
        xe = BAR_X + w1
        nb1, nb3 = bar_rect(w1, y1, CORAL), bar_rect(w3, y2, GREEN)
        row3 = VGroup(n3, b3, c3)
        self.play(FadeOut(VGroup(n2, bar2, c2)),
                  Transform(b1, nb1), c1.animate.move_to(px(xe + 24, y1), aligned_edge=LEFT),
                  row3.animate.shift(UP * u(y3 - y2)), run_time=0.9)
        self.play(Transform(b3, nb3), c3.animate.move_to(px(xe + 24, y2), aligned_edge=LEFT), run_time=0.7)
        line = DashedLine(px(xe, y1 - 50), px(xe, y2 + 50), color=YELLOW, stroke_width=4)
        self.play(Create(line), run_time=0.5)
        self.play(pop(c3, 1.15, 0.5), c3.animate.set_color(YELLOW), run_time=0.5)

        # ---- 小さくして動かす工夫：コマが順に跳ねる ----
        self.at("tricks", -0.1)
        self.play(LaggedStart(*[pop(im, 1.12, 0.4) for im in imgs], lag_ratio=0.25), run_time=2.2)

        # ---- コマが縮んで消え、タイトル ----
        self.at("title", -0.2)
        title = jp("GIFの中身をのぞく", 72).move_to(px(960, 300))
        others = VGroup(n1, b1, c1, n3, b3, c3, line)
        for im in imgs:
            im.check_ignore = True
        self.play(*[im.animate.scale(0.3).move_to(px(960, 300)).set_opacity(0) for im in imgs],
                  FadeOut(others), FadeIn(title, scale=0.9), run_time=1.0)
        self.remove(*imgs)
        self.finish()
