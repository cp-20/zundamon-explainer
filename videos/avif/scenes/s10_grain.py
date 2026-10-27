import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import dec, file_bytes, fmt, mean_abs_err, pixels, picture_size, rgb_decoded, size  # noqa: E402
from vlib.photoview import PhotoView, ViewAnim, move_view  # noqa: E402
from zunda.fx import Shake, pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)
EYE_WIN = (108, 78, 228, 158)               # 左目のあたり (120×80 画素)
A_BOX = ((960, 370), 810, 540)              # 粒子を足した写真
B_BOX = ((740, 290), 600, 400)              # 粒子の値を並べるとき (左)
PANEL_C, PANEL_W, PANEL_H = (1450, 255), 640, 380
GRAIN_C, GRAIN_K = (1250, 680), 4           # 粒子の見本の画像 (82×73 を 3 倍)
BAR_X0, BAR_Y, BAR_MAX = 640, (720, 810), 800
CMP_WIN = (133, 83, 203, 153)               # 3 枚を並べるときの範囲 (70×70 画素)
CMP_X, CMP_Y, CMP_S = (540, 960, 1380), 250, 400
LAB_Y = CMP_Y + CMP_S / 2 + 36              # 3 枚の名前 (下に置く。上は画面の端)
GRAIN_SRC = "cat_grain.png"
FG, PLAIN = "cat_grain_fg", "cat_grain_q44"


class S10(PScene):
    def construct(self):
        W, H = picture_size()
        # ---- 実データの確かめ ----
        n0, n1 = size("cat_q60"), size("cat_grain_q60")
        n_fg, n_pl = size(FG), size(PLAIN)
        assert (n0, n1, n_fg, n_pl) == (13179, 25872, 9531, 8783) and 1.9 < n1 / n0 < 2.0   # 「ほぼ2倍」
        e_pl, e_fg = mean_abs_err(PLAIN, GRAIN_SRC), mean_abs_err(FG, GRAIN_SRC)
        assert f"{e_pl:.1f}" == "7.6" and f"{e_fg:.1f}" == "9.3"
        d = dec(FG)
        g = d.film_grain
        assert g["apply_grain"] and len(g["point_y_value"]) == len(g["point_y_scaling"]) == 11
        fl = d.fields
        i0 = next(i for i, f in enumerate(fl) if f[0] == "apply_grain")
        last = fl[-1]
        assert last[0] == "clip_to_restricted_range"
        bit0, bit1 = fl[i0][2], last[2] + last[3]
        nbits = sum(f[3] for f in fl[i0:])
        assert nbits == bit1 - bit0 and round(nbits / 8, -1) == 140                      # 「140バイトくらい」
        luma_grain = np.asarray(g["luma_grain"])
        assert luma_grain.shape == (73, 82)
        src_rgb = pixels(GRAIN_SRC)[..., :3]
        assert src_rgb.shape[:2] == (H, W)
        lr = rgb_decoded(FG, "lr").astype(np.float32)
        fin = rgb_decoded(FG, "final").astype(np.float32)

        # ---- 写真 (S09 の終わり) ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)

        # ---- 目のあたりに寄る → 粒子を足した写真 ----
        self.at("dark", -0.1)
        self.play(move_view(view, win=EYE_WIN, box=A_BOX), run_time=1.8)
        self.at("test", -0.1)
        base0 = view.base.copy()
        gsrc = src_rgb.astype(np.float32)

        def to_grain(t):
            view.base = base0 + (gsrc - base0) * t
        lab = jp("粒子を足した写真", 34, INK).move_to(px(A_BOX[0][0], A_BOX[0][1] - A_BOX[2] / 2 - 34))
        self.play(ViewAnim(view, to_grain), FadeIn(lab, shift=DOWN * u(6)), run_time=1.2)

        # ---- ファイルサイズ：粒子なし / 粒子あり ----
        def bar(n, y, col, name, tcol):
            w = BAR_MAX * n / n1
            r = Rectangle(width=u(w), height=u(64), stroke_width=0, fill_color=col, fill_opacity=1)
            r.move_to(px(BAR_X0 + w / 2, y))
            nm = jp(name, 32, INK).move_to(px(BAR_X0 - 20, y), aligned_edge=RIGHT).set_y(px(0, y)[1])
            v = mix(f"{fmt(n)} バイト", 34, tcol).move_to(px(BAR_X0 + w - 18, y), aligned_edge=RIGHT)
            v.set_y(px(0, y)[1])
            return r, nm, v
        r0, nm0, v0 = bar(n0, BAR_Y[0], "#5c6577", "粒子なし", INK)
        r1, nm1, v1 = bar(n1, BAR_Y[1], CORAL, "粒子あり", BG)
        self.at("size", -0.1)
        self.play(GrowFromEdge(r0, LEFT), FadeIn(nm0), run_time=0.8)
        self.play(FadeIn(v0), run_time=0.4)
        self.at("double", -0.1)
        self.play(GrowFromEdge(r1, LEFT), FadeIn(nm1), run_time=1.2)
        self.play(FadeIn(v1), run_time=0.4)
        self.at("random", 0.2)
        self.play(Shake(VGroup(r1, v1), amp=10, run_time=0.6))

        # ---- 粒子を取り除いて圧縮 → 粒子の値だけを記録 ----
        self.at("idea", -0.1)
        self.play(FadeOut(VGroup(r0, r1, nm0, nm1, v0, v1)), run_time=0.6)
        self.at("remove", -0.1)

        def to_lr(t):
            view.base = gsrc + (lr - gsrc) * t
        lab2 = jp("粒子を取り除いて圧縮", 34, INK)
        self.play(ViewAnim(view, to_lr), retext(lab, lab2), run_time=1.2)

        self.at("recipe", -0.1)
        frame = RoundedRectangle(corner_radius=u(16), width=u(PANEL_W), height=u(PANEL_H), stroke_color="#3a4050",
                                 stroke_width=2, fill_color="#1b1e26", fill_opacity=1).move_to(px(*PANEL_C))
        ptitle = jp("記録する粒子の値", 34, YELLOW).move_to(px(PANEL_C[0], PANEL_C[1] - PANEL_H / 2 + 40))
        raw = file_bytes(FG)[bit0 // 8:(bit1 + 7) // 8]
        hex_lines = VGroup(*[mono(" ".join(f"{b:02X}" for b in raw[r * 8:r * 8 + 8]) + (" …" if r == 3 else ""),
                                  30, INK) for r in range(4)])
        hex_lines.arrange(DOWN, buff=u(16), aligned_edge=LEFT).move_to(px(PANEL_C[0], PANEL_C[1] + 30))
        self.play(move_view(view, win=EYE_WIN, box=B_BOX),
                  lab.animate.move_to(px(B_BOX[0][0], B_BOX[0][1] - B_BOX[2] / 2 - 30)), run_time=1.0)
        self.play(FadeIn(frame, shift=LEFT * u(20)), FadeIn(ptitle, shift=LEFT * u(20)),
                  LaggedStart(*[FadeIn(h_, shift=LEFT * u(10)) for h_ in hex_lines], lag_ratio=0.2), run_time=1.0)

        # ---- 表示する側が粒子を作って重ねる ----
        self.at("make", -0.1)
        gimg = np.clip(128 + luma_grain, 0, 255).astype(np.uint8)
        gm = ImageMobject(np.dstack([gimg] * 3))
        gm.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        gm.width = u(82 * GRAIN_K)
        gm.move_to(px(*GRAIN_C))
        gm.check_ignore = True
        glab = jp("作った粒子", 30, INK).move_to(px(GRAIN_C[0], GRAIN_C[1] + 73 * GRAIN_K / 2 + 30))
        self.play(FadeIn(gm, target_position=px(*PANEL_C), scale=0.3), FadeIn(glab, shift=UP * u(6)), run_time=1.2)
        self.at("put", -0.1)
        fly = gm.copy()
        fly.check_ignore = True
        self.add(fly)

        def to_fin(t):
            view.base = lr + (fin - lr) * t
        lab3 = jp("粒子を重ねた写真", 34, YELLOW)
        self.play(fly.animate(path_arc=0.6).move_to(px(*B_BOX[0])).set(width=u(B_BOX[1])).set_opacity(0),
                  ViewAnim(view, to_fin), retext(lab, lab3), run_time=1.3)
        self.remove(fly)

        # ---- 記録するもの：明るさごとの強さ・となりどうしの似かた ----
        self.at("how", -0.1)
        self.play(FadeOut(hex_lines), run_time=0.5)
        self.at("bright", -0.1)
        GX0, GX1, GY0, GY1 = PANEL_C[0] - 250, PANEL_C[0] + 270, PANEL_C[1] + 120, PANEL_C[1] - 110

        def gp(v, s):
            return px(GX0 + (GX1 - GX0) * v / 255, GY0 + (GY1 - GY0) * s / 255)
        axes = VGroup(Line(px(GX0, GY0), px(GX1, GY0)), Line(px(GX0, GY0), px(GX0, GY1))).set_stroke(DIM, 3)
        xl = jp("明るさ", 28, DIM).move_to(px((GX0 + GX1) / 2, GY0 + 32))
        t0 = mix("0", 26, DIM).move_to(px(GX0, GY0 + 32))
        t1 = mix("255", 26, DIM).move_to(px(GX1, GY0 + 32))
        pts = [gp(v, s) for v, s in zip(g["point_y_value"], g["point_y_scaling"])]
        curve = VMobject(stroke_color=YELLOW, stroke_width=4).set_points_as_corners(pts)
        dots = VGroup(*[Dot(p, radius=u(7), color=YELLOW) for p in pts])
        self.play(retext(ptitle, jp("明るさごとの粒子の強さ", 34, YELLOW)), Create(axes), FadeIn(VGroup(xl, t0, t1)),
                  run_time=0.8)
        self.play(Create(curve), LaggedStart(*[FadeIn(dt, scale=0.5) for dt in dots], lag_ratio=0.08), run_time=1.0)
        self.at("pattern", -0.1)
        gfr = Rectangle(width=u(82 * GRAIN_K + 12), height=u(73 * GRAIN_K + 12), stroke_color=YELLOW,
                        stroke_width=4).move_to(gm)
        glab2 = jp("となりどうしが似た粒子", 30, YELLOW).move_to(glab)
        self.play(Create(gfr), retext(glab, glab2), run_time=0.9)
        self.at("bytes", -0.1)
        nb = mix(f"約 {int(round(nbits / 8, -1))} バイト", 44, YELLOW).move_to(px(720, 620))
        self.play(FadeIn(nb, shift=UP * u(8)), run_time=0.7)
        self.play(pop(nb, 1.2, 0.7), run_time=0.7)

        # ---- 3 枚を同じ倍率で：粒子を足した元 / そのまま圧縮 / 作り直し ----
        self.at("cmp", -0.1)
        box3 = ((CMP_X[2], CMP_Y), CMP_S, CMP_S)
        lab_c3 = jp("粒子を作り直す", 32, YELLOW).move_to(px(CMP_X[2] - 20, LAB_Y))
        v1_ = PhotoView(src_rgb, (CMP_X[0], CMP_Y), CMP_S, CMP_S, win=CMP_WIN)
        v1_.check_ignore = True
        lab_c1 = jp("粒子を足した元", 32, INK).move_to(px(CMP_X[0] + 30, LAB_Y))
        graph = VGroup(axes, xl, t0, t1, curve, dots)
        self.play(FadeOut(VGroup(frame, ptitle, graph, gfr, glab, nb)), gm.animate.set_opacity(0), run_time=0.5)
        self.remove(gm)
        v1_.set_opacity(0)
        self.add(v1_)
        self.play(move_view(view, win=CMP_WIN, box=box3), ReplacementTransform(lab, lab_c3),
                  v1_.animate.set_opacity(1), FadeIn(lab_c1, shift=RIGHT * u(10)), run_time=1.2)
        self.at("plain", -0.1)
        v2_ = PhotoView(pixels(PLAIN), (CMP_X[1], CMP_Y), CMP_S, CMP_S, win=CMP_WIN)
        v2_.check_ignore = True
        lab_c2 = jp("そのまま圧縮", 32, INK).move_to(px(CMP_X[1], LAB_Y))
        s2 = mix(f"{fmt(n_pl)} バイト", 38, INK).move_to(px(CMP_X[1], LAB_Y + 56))
        v2_.set_opacity(0)
        self.add(v2_)
        self.play(v2_.animate.set_opacity(1), FadeIn(lab_c2, shift=DOWN * u(6)), FadeIn(s2, shift=UP * u(6)),
                  run_time=0.9)
        self.at("fg", -0.1)
        s3 = mix(f"{fmt(n_fg)} バイト", 38, INK).move_to(px(CMP_X[2] - 20, LAB_Y + 56))
        self.play(FadeIn(s3, shift=UP * u(6)), run_time=0.7)

        # 作り直したほうが元らしく見える
        self.at("look", -0.1)
        fr1 = Square(u(CMP_S + 14), stroke_color=YELLOW, stroke_width=5).move_to(px(CMP_X[0], CMP_Y))
        fr3 = Square(u(CMP_S + 14), stroke_color=YELLOW, stroke_width=5).move_to(px(CMP_X[2], CMP_Y))
        self.play(Create(fr1), Create(fr3), run_time=0.9)

        # 画素ごとのずれは作り直したほうが大きい
        self.at("num", -0.1)
        e2 = mix(f"ずれ {e_pl:.1f}", 42, CORAL).move_to(px(CMP_X[1], LAB_Y + 120))
        e3 = mix(f"ずれ {e_fg:.1f}", 42, CORAL).move_to(px(CMP_X[2] - 20, LAB_Y + 120))
        self.play(FadeOut(VGroup(fr1, fr3)), FadeIn(e2, shift=UP * u(8)), FadeIn(e3, shift=UP * u(8)), run_time=0.8)
        self.at("worse", -0.1)
        self.play(pop(e3, 1.3, 0.8), run_time=0.8)

        # 見た目は似ているが、元の粒子そのものではない
        self.at("fake", -0.1)
        self.play(Indicate(lab_c1, color=INK, scale_factor=1.1), Indicate(lab_c3, color=YELLOW, scale_factor=1.1),
                  run_time=1.0)

        # 終わり：空 (S11 の最初の画面)
        self.at("film", 0.2)
        self.play(FadeOut(VGroup(lab_c1, lab_c2, lab_c3, s2, s3, e2, e3)),
                  *[m.animate.set_opacity(0) for m in (view, v1_, v2_)], run_time=1.0)
        self.remove(view, v1_, v2_)
        self.finish()
