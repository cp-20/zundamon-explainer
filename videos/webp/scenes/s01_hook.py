import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import anim_canvas, anim_frames, fmt, gif_stamp_size, mean_abs_err, pixels, size  # noqa: E402
from zunda.fx import pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

OLD = DIM            # 昔からの形式 (JPEG・PNG・GIF) の棒
NEW = YELLOW         # WebP の棒

# ---- 写真 2 枚と大きさの棒 (大きい配置) ----
HOOK_W, HOOK_C = 900, (960, 330)
CARD_Y = 680
PH_W = 560
PH_C = {"jpg": (660, 250), "webp": (1260, 250)}
TAG_Y, SUB_Y = 470, 515
ROW_Y = {"jpg": 590, "webp": 680}
LAB_X, BAR_X, BAR_MAX, BAR_H, NUM_X = 450, 580, 600, 56, 1200
# ---- 3 つの欄 ----
PAN_X = [620, 960, 1300]
HEAD_Y, ILL_H, ILL_Y = 70, 420, 310
P_TXT_Y, P_BAR_Y, P_BAR_MAX, P_BAR_H = (575, 680), (618, 723), 280, 36


class S01(PScene):
    def construct(self):
        # ---- 台詞の数字 ----
        n_jpg, n_webp = size("cat_q80.jpg"), size("cat_q80")
        assert (n_jpg, n_webp) == (23693, 16974)
        assert 0.25 < 1 - n_webp / n_jpg < 0.32                      # 3 割くらい小さい
        e_jpg, e_webp = f"{mean_abs_err('cat_q80.jpg'):.1f}", f"{mean_abs_err('cat_q80'):.1f}"
        assert (e_jpg, e_webp) == ("2.6", "2.7")
        n_png, n_ll, n_lossy = size("zunda.png"), size("zunda_lossless"), size("zunda_q80")
        n_gif, n_anim = gif_stamp_size(), size("zunda_anim")
        assert (n_png, n_ll, n_lossy, n_gif, n_anim) == (162613, 113786, 41774, 28615, 21468)
        assert 0.25 < 1 - n_ll / n_png < 0.35                         # 3 割くらい小さい
        assert 0.2 < n_lossy / n_png < 0.3                            # 4 分の 1 くらい
        assert n_anim < n_gif
        a_ll, a_png = pixels("zunda_lossless"), pixels("zunda.png")
        vis = a_png[..., 3] > 0                                       # 1 バイトも消さない (見える点はすべて同じ)
        assert (a_ll[..., 3] == a_png[..., 3]).all() and (a_ll[vis] == a_png[vis]).all()

        # ---- 猫の写真 (WebP) と札 ----
        self.at("photo", -0.2)
        hook_h = HOOK_W * pixels("cat_q80").shape[0] / pixels("cat_q80").shape[1]
        ph_w = png_mob(pixels("cat_q80"), hook_h, nearest=True).move_to(px(*HOOK_C))
        self.play(FadeIn(ph_w, scale=0.95), run_time=0.9)

        self.at("name", -0.1)
        tag_w = jp("cat.webp", 40, INK).move_to(px(HOOK_C[0], CARD_Y))
        self.play(FadeIn(tag_w, shift=UP * u(10)), run_time=0.6)

        self.at("read", -0.1)
        ext = VGroup(*tag_w[3:])
        ul = underline(ext, YELLOW)
        self.play(Create(ul), ext.animate.set_color(YELLOW), run_time=0.5)

        self.at("google", -0.1)
        note = jp("2010年・Google", 32, DIM).next_to(tag_w, RIGHT, buff=u(40))
        self.play(FadeIn(note, shift=LEFT * u(10)), run_time=0.6)
        self.at("google", 3.4)        # 「ウェブサイトの画像によく使われている」：札を指す
        self.play(pop(VGroup(tag_w, ul), 1.12, 0.6), run_time=0.6)

        # ---- 同じ写真を JPEG と WebP で：2 枚に分かれる ----
        self.at("jpg", -0.1)
        ph_j = png_mob(pixels("cat_q80.jpg"), hook_h, nearest=True).move_to(px(*HOOK_C))
        self.add(ph_j)
        self.bring_to_front(ph_w)
        tag_j = jp("cat.jpg", 36, INK).move_to(px(PH_C["jpg"][0], TAG_Y))
        k = PH_W / HOOK_W
        self.play(ph_w.animate.scale(k).move_to(px(*PH_C["webp"])),
                  ph_j.animate.scale(k).move_to(px(*PH_C["jpg"])),
                  tag_w.animate.scale(36 / 40).move_to(px(PH_C["webp"][0], TAG_Y)).set_color(INK),
                  FadeOut(ul), FadeOut(note), FadeIn(tag_j, shift=RIGHT * u(30)), run_time=1.2)

        # ---- 大きさ：札の数字が、そのまま横棒に ----
        self.at("size", -0.1)
        nums = {"jpg": jp(f"{fmt(n_jpg)} バイト", 38, INK).move_to(px(PH_C["jpg"][0], SUB_Y)),
                "webp": jp(f"{fmt(n_webp)} バイト", 38, NEW).move_to(px(PH_C["webp"][0], SUB_Y))}
        self.play(*[FadeIn(m, shift=UP * u(8)) for m in nums.values()], run_time=0.5)
        self.wait(0.3)
        labs = {"jpg": jp("JPEG", 38, INK).move_to(px(LAB_X, ROW_Y["jpg"]), aligned_edge=LEFT),
                "webp": jp("WebP", 38, NEW).move_to(px(LAB_X, ROW_Y["webp"]), aligned_edge=LEFT)}
        ns = {"jpg": n_jpg, "webp": n_webp}
        cols = {"jpg": OLD, "webp": NEW}

        def bar(key, x0, wmax, y, h):
            return Rectangle(width=u(wmax * ns[key] / n_jpg), height=u(h), stroke_width=0,
                             fill_color=cols[key], fill_opacity=1).move_to(px(x0, y), aligned_edge=LEFT)

        bars = {kk: bar(kk, BAR_X, BAR_MAX, ROW_Y[kk], BAR_H) for kk in ns}
        anims = []
        for kk in ns:
            cp = nums[kk].copy()
            cp.check_ignore = True
            anims += [ReplacementTransform(cp, bars[kk]), FadeIn(labs[kk], shift=RIGHT * u(10)),
                      nums[kk].animate.move_to(px(NUM_X, ROW_Y[kk]), aligned_edge=LEFT)]
        self.play(*anims, run_time=1.2)

        # ---- 差の部分が光る ----
        self.at("small", -0.1)
        x_w = BAR_X + BAR_MAX * n_webp / n_jpg
        # 枠線は外側にはみ出して棒より大きく見えるので、塗りだけで棒とぴったり同じ高さにする
        gap = Rectangle(width=u(BAR_X + BAR_MAX - x_w), height=u(BAR_H), stroke_width=0,
                        fill_color=NEW, fill_opacity=0.35).move_to(px(x_w, ROW_Y["webp"]), aligned_edge=LEFT)
        self.play(GrowFromEdge(gap, LEFT), run_time=0.6)
        self.play(gap.animate.set_fill(opacity=0.12), pop(bars["webp"], 1.06, 0.6), run_time=0.6)

        # ---- 汚くなってない？ ----
        self.at("worse", -0.1)
        self.play(pop(ph_w, 1.05, 0.7), run_time=0.7)

        # ---- 元とのずれ ----
        self.at("same", -0.1)
        evals = {"jpg": e_jpg, "webp": e_webp}
        errs = {kk: jp(f"元とのずれ　{evals[kk]}", 36, INK, t2c={evals[kk]: CORAL}).move_to(px(PH_C[kk][0], SUB_Y))
                for kk in ns}
        self.play(*[FadeIn(m, shift=UP * u(8)) for m in errs.values()], run_time=0.6)
        self.play(*[pop(m, 1.1, 0.6) for m in errs.values()], run_time=0.6)

        self.at("more", -0.1)
        self.play(pop(VGroup(labs["webp"], bars["webp"], nums["webp"]), 1.08, 0.7), run_time=0.7)

        # ---- 写真の比べっこは消す ----
        self.at("more2", -0.1)
        cmp_vm = VGroup(tag_j, tag_w, *errs.values(), gap, *labs.values(), *bars.values(), *nums.values())
        self.play(ph_j.animate.set_opacity(0), ph_w.animate.set_opacity(0), FadeOut(cmp_vm), run_time=0.8)
        self.remove(ph_j, ph_w, cmp_vm, *cmp_vm)

        # ---- 3 つの欄 ----
        def head(i, s):
            return jp(s, 32, INK).move_to(px(PAN_X[i], HEAD_Y))

        def rows(i, old_name, n_old, n_new):
            x0 = PAN_X[i] - P_BAR_MAX / 2
            t_old = jp(f"{old_name} {fmt(n_old)}", 34, INK).move_to(px(x0, P_TXT_Y[0]), aligned_edge=LEFT)
            t_new = jp(f"WebP {fmt(n_new)}", 34, NEW).move_to(px(x0, P_TXT_Y[1]), aligned_edge=LEFT)
            b_old = Rectangle(width=u(P_BAR_MAX), height=u(P_BAR_H), stroke_width=0, fill_color=OLD,
                              fill_opacity=1).move_to(px(x0, P_BAR_Y[0]), aligned_edge=LEFT)
            b_new = Rectangle(width=u(P_BAR_MAX * n_new / n_old), height=u(P_BAR_H), stroke_width=0,
                              fill_color=NEW, fill_opacity=1).move_to(px(x0, P_BAR_Y[1]), aligned_edge=LEFT)
            return t_old, b_old, t_new, b_new

        def show_rows(r):
            t_old, b_old, t_new, b_new = r
            self.play(FadeIn(t_old, shift=RIGHT * u(10)), GrowFromEdge(b_old, LEFT), run_time=0.7)
            self.play(FadeIn(t_new, shift=RIGHT * u(10)), GrowFromEdge(b_new, LEFT), run_time=0.7)

        # 1. 消さない保存
        self.at("lossless", -0.1)
        h1 = head(0, "1バイトも消さない")
        ill1 = png_mob(pixels("zunda_lossless"), ILL_H, nearest=False).move_to(px(PAN_X[0], ILL_Y))
        self.play(FadeIn(h1, shift=DOWN * u(6)), FadeIn(ill1, scale=0.92), run_time=0.8)
        self.at("lsize", -0.1)
        r1 = rows(0, "PNG", n_png, n_ll)
        show_rows(r1)

        # 2. 透明＋捨てて縮める：同じイラストが隣へ
        self.at("alpha", -0.1)
        h2 = head(1, "透明＋捨てて縮める")
        ill2 = png_mob(pixels("zunda_q80"), ILL_H, nearest=False).move_to(px(PAN_X[0], ILL_Y))
        self.add(ill2)
        self.play(ill2.animate.move_to(px(PAN_X[1], ILL_Y)), FadeIn(h2, shift=DOWN * u(6)), run_time=1.0)
        self.at("asize", -0.1)
        r2 = rows(1, "PNG", n_png, n_lossy)
        show_rows(r2)

        # 3. 動くスタンプ：本物の待ち時間で動く
        self.at("anim", -0.1)
        h3 = head(2, "動くスタンプ")
        frames = anim_frames()
        delays = [f["duration"] / 1000 for f in frames]
        assert len(frames) == 8 and min(delays) > 0
        arrs = [png_mob(c, ILL_H, nearest=False).pixel_array.copy() for c in anim_canvas()]
        stamp = png_mob(anim_canvas()[0], ILL_H, nearest=False).move_to(px(PAN_X[2], ILL_Y))
        total = sum(delays)
        t_start = self.now + 0.6
        ends = np.cumsum(delays)

        def run_stamp(m, dt):
            t = max(0.0, self.now - t_start) % total
            kf = int(np.searchsorted(ends, t, side="right"))
            a = m.pixel_array[0, 0, 3]
            arr = arrs[min(kf, len(arrs) - 1)].copy()
            arr[:, :, 3] = a
            m.pixel_array = arr

        self.play(FadeIn(h3, shift=DOWN * u(6)), FadeIn(stamp, scale=0.92), run_time=0.6)
        stamp.add_updater(run_stamp)
        self.at("gsize", -0.1)
        r3 = rows(2, "GIF", n_gif, n_anim)
        show_rows(r3)

        # ---- 全部 WebP のほうが小さい ----
        self.at("all", -0.1)
        news = [VGroup(r[2], r[3]) for r in (r1, r2, r3)]
        self.play(LaggedStart(*[pop(g, 1.12, 0.6) for g in news], lag_ratio=0.35), run_time=1.8)

        # ---- 並んだものが縮んで消え、タイトル ----
        self.at("title", -0.2)
        title = jp("WebPの中身をのぞく", 72).move_to(px(960, 300))
        imgs = [ill1, ill2, stamp]
        for im in imgs:
            im.check_ignore = True
        stamp.clear_updaters()
        vm = VGroup(h1, h2, h3, *r1, *r2, *r3)
        c = px(960, 300)
        self.play(*[im.animate.scale(0.3).move_to(c).set_opacity(0) for im in imgs],
                  FadeOut(vm, target_position=c, scale=0.3), FadeIn(title, scale=0.9), run_time=1.0)
        self.remove(*imgs, vm, *vm)
        self.finish()
