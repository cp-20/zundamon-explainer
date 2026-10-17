import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import BLOCK, block_coef, idct2, jpeg, pixels, qtable, to_block, ycc  # noqa: E402
from zunda.fx import underline  # noqa: E402
from vlib.jparts import QGrid, gray_img  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import ORDER, STAGE_COL, StageMap  # noqa: E402

# 写真の枠（px）：中央の大きい表示
PH_C, PH_W = (960, 470), 1040
IMG_W, IMG_H = 451, 300
# ズームする場所（8×8 の境目に合わせた画素の範囲）：猫の左目のまわり
RA = (120, 72, 96, 64)             # x, y, 幅, 高さ（12×8 ブロック）
RB = (160, 72, 48, 32)             # さらに目のふち


def nearest(im):
    im.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    return im


def rgb_img(a, h_px):
    return nearest(ImageMobject(np.asarray(a, np.uint8))).set(height=u(h_px))


def place(im, cx, cy, h):
    im.set(height=u(h))
    im.move_to(px(cx, cy))
    return im


def sub_box(parent, parent_px, rect):
    """親の枠（中心 x, y, 幅, 高さ）の中の、画素 rect の位置（中心 x, y, 幅, 高さ）"""
    cx, cy, w, h = parent
    k = w / parent_px[0]
    x, y, rw, rh = rect
    return (cx - w / 2 + (x + rw / 2) * k, cy - h / 2 + (y + rh / 2) * k, rw * k, rh * k)


class S08(PScene):
    def construct(self):
        # ---- 実データ ----
        Q = qtable()
        F_q = block_coef().astype(int)
        deq = F_q * Q
        Yblk = np.clip(idct2(deq) + 128, 0, 255)
        by, bx = BLOCK
        dec_rgb = pixels("cat_q80")[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8]   # libjpeg の復号結果（色の補間が違うだけ）
        assert np.abs(dec_rgb.astype(float) - jpeg()[3][by * 8:by * 8 + 8, bx * 8:bx * 8 + 8]).max() <= 10
        assert np.abs(ycc("cat_q80")[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8, 0] - Yblk).max() <= 3

        ph_h = PH_W * IMG_H / IMG_W
        PH = (PH_C[0], PH_C[1], PH_W, ph_h)
        A_big = PH
        A_in_ph = sub_box(PH, (IMG_W, IMG_H), RA)
        B_in_A = sub_box(A_big, (RA[2], RA[3]), (RB[0] - RA[0], RB[1] - RA[1], RB[2], RB[3]))
        B_in_ph = sub_box(PH, (IMG_W, IMG_H), RB)

        # 平らなブロック（ズーム範囲の中で、ファイルの係数が DC だけのもの）
        s5, info5, coef5, _ = jpeg("cat_q5")
        c5 = coef5[0]
        flat = None
        for r in range(RA[1] // 8, (RA[1] + RA[3]) // 8):
            for c in range(RA[0] // 8, (RA[0] + RA[2]) // 8):
                if not c5[r, c, 1:].any() and c5[r, c, 0] > 0 and flat is None:
                    flat = (r, c)
        fy, fx = flat
        Fq5 = to_block(c5[fy, fx]).astype(int)
        Y5 = np.clip(idct2(Fq5 * qtable("cat_q5")) + 128, 0, 255)
        assert np.abs(Y5 - Y5[0, 0]).max() < 1e-6 and np.abs(ycc("cat_q5")[fy * 8:fy * 8 + 8, fx * 8:fx * 8 + 8, 0] - Y5).max() <= 3

        # ---- 始まり：S07 の終わり（地図が全体表示）。部品を 1 つずつ場面に置く ----
        m = StageMap("full", done=tuple(ORDER))
        pills = {k: m.parts[k][0] for k in ORDER}
        texts = {k: m.parts[k][1] for k in ORDER}
        arrows = list(m.arrows)
        map_all = [*pills.values(), *texts.values(), *arrows, *m.lossy.values(), *m.checks]
        self.add(*map_all)

        # ---- 逆にたどる：矢印が逆向きに ----
        self.at("reverse", -0.1)
        rev = [Arrow(m.parts[b].get_left(), m.parts[a].get_right(), buff=u(8), stroke_width=4,
                     max_tip_length_to_length_ratio=0.4, color=INK)
               for a, b in zip(ORDER, ORDER[1:])]
        self.play(LaggedStart(*[Transform(a, r) for a, r in list(zip(arrows, rev))[::-1]], lag_ratio=0.3),
                  run_time=1.6)

        def light(k, on=True):
            return [pills[k].animate.set_fill(STAGE_COL[k], 0.9 if on else 0.22),
                    texts[k].animate.set_color(BG if on else INK)]

        # ---- 符号を読んで・掛け直して・模様を足して・色を配り直す（目のブロックが戻る）----
        CX, CY, CELL = 960, 640, 66
        qg = QGrid(F_q, cell=CELL).move_to(px(CX, CY))
        cells, nums = qg.cells, list(qg.nums)
        self.at("decode", -0.1)
        self.add(cells, *nums)
        self.play(*light("code"), FadeIn(cells, shift=UP * u(10)), *[FadeIn(t, shift=UP * u(10)) for t in nums],
                  run_time=0.6)

        self.at("mul", -0.1)
        new_nums = [jp(str(int(deq[r, c])).replace("-", "−"), 26, INK if deq[r, c] else "#4a5060").move_to(nums[r * 8 + c])
                    for r in range(8) for c in range(8)]
        self.play(*light("code", False), *light("quant"), *[Transform(a, b) for a, b in zip(nums, new_nums)],
                  run_time=0.8)

        self.at("sum", -0.1)
        gray = gray_img(Yblk, CELL * 8).move_to(px(CX, CY))
        self.play(*light("quant", False), *light("dct"), FadeOut(cells), *[FadeOut(t) for t in nums],
                  FadeIn(gray), run_time=0.8)
        self.remove(cells, *nums)

        self.at("color", -0.1)
        col = rgb_img(dec_rgb, CELL * 8).move_to(px(CX, CY))
        self.play(*light("dct", False), *light("color"), FadeIn(col), run_time=0.8)
        self.remove(gray)

        # ---- 全部のブロックでやれば、写真に戻る：ブロックが写真の中の元の場所へ ----
        self.at("done", -0.1)
        ph_small_h = 420
        SM = (960, 640, ph_small_h * IMG_W / IMG_H, ph_small_h)
        photo = nearest(ImageMobject(pixels("cat_q80")))
        photo.set_resampling_algorithm(RESAMPLING_ALGORITHMS["cubic"])
        place(photo, SM[0], SM[1], SM[3]).set_z_index(0)
        col.set_z_index(1)
        bx_, by_, bw_, _ = sub_box(SM, (IMG_W, IMG_H), (bx * 8, by * 8, 8, 8))
        self.play(*light("color", False), FadeIn(photo),
                  col.animate.scale(bw_ / (CELL * 8)).move_to(px(bx_, by_)), run_time=1.4)
        self.remove(col)

        # ---- 品質をうんと下げたら：写真が大きく、地図は消える ----
        self.at("s08_04", -0.1)
        self.play(*[FadeOut(x) for x in map_all],
                  photo.animate.scale(PH_W / SM[2]).move_to(px(*PH_C)), run_time=1.0)
        self.remove(*map_all)

        self.at("low", -0.1)
        q5 = ImageMobject(pixels("cat_q5"))
        q5.set_resampling_algorithm(RESAMPLING_ALGORITHMS["cubic"])
        place(q5, *PH_C, ph_h)
        label = jp("品質5", 48, CORAL).move_to(px(960, 78))
        self.play(Transform(photo, q5), FadeIn(label, shift=DOWN * u(8)), run_time=1.0)

        # ---- カクカクのタイル：一部をズームして 8×8 の境目の線 ----
        self.at("blocks", -0.1)
        ax = pixels("cat_q5")
        cropA = rgb_img(ax[RA[1]:RA[1] + RA[3], RA[0]:RA[0] + RA[2]], A_in_ph[3]).move_to(px(A_in_ph[0], A_in_ph[1]))
        cropA.set_z_index(2)
        self.add(cropA)
        self.play(cropA.animate.scale(A_big[2] / A_in_ph[2]).move_to(px(A_big[0], A_big[1])), run_time=1.2)
        self.remove(photo)
        L, T = A_big[0] - A_big[2] / 2, A_big[1] - A_big[3] / 2
        ku = A_big[2] / RA[2]
        lines = VGroup(*[Line(px(L + i * 8 * ku, T), px(L + i * 8 * ku, T + A_big[3]), color=INK, stroke_width=2,
                              stroke_opacity=0.6) for i in range(1, RA[2] // 8)],
                       *[Line(px(L, T + j * 8 * ku), px(L + A_big[2], T + j * 8 * ku), color=INK, stroke_width=2,
                              stroke_opacity=0.6) for j in range(1, RA[3] // 8)])
        self.play(LaggedStart(*[Create(l) for l in lines], lag_ratio=0.04), run_time=1.0)
        lines.set_z_index(4)
        zoomA = Group(cropA, lines)

        # ---- 平らな模様だけのブロック：係数（ほとんど DC だけ）と、できた四角 ----
        self.at("flat", -0.1)
        SMALL_S = 0.55
        SA_C = (960, 300)
        self.play(zoomA.animate.scale(SMALL_S).move_to(px(*SA_C)), run_time=1.0)
        k_sm = A_big[2] * SMALL_S / RA[2]
        bc = (SA_C[0] - A_big[2] * SMALL_S / 2 + ((fx * 8 - RA[0]) + 4) * k_sm,
              SA_C[1] - A_big[3] * SMALL_S / 2 + ((fy * 8 - RA[1]) + 4) * k_sm)
        frame = Square(side_length=u(8 * k_sm), color=YELLOW, stroke_width=4).move_to(px(*bc))
        frame.check_ignore = True
        frame.set_z_index(5)
        blk = rgb_img(ax[fy * 8:fy * 8 + 8, fx * 8:fx * 8 + 8], 8 * k_sm).move_to(px(*bc))
        blk.check_ignore = True
        DC_, DS = 48, 8 * 48
        coef_c, sq_c = (700, 705), (1220, 705)
        grid5 = VGroup()
        for r in range(8):
            for c in range(8):
                v = int(Fq5[r, c])
                cell = Square(side_length=u(DC_), stroke_width=1.5, stroke_color="#2a2e38", fill_color="#1d212b",
                              fill_opacity=1).move_to(px(coef_c[0] + (c - 3.5) * DC_, coef_c[1] + (r - 3.5) * DC_))
                t = jp(str(v).replace("-", "−"), 26, INK if v else "#4a5060").move_to(cell)
                grid5.add(VGroup(cell, t))
        grid5.check_group = False
        self.add(frame, blk)
        self.play(FadeIn(frame, scale=1.6), run_time=0.4)
        self.play(blk.animate.scale(DS / (8 * k_sm)).move_to(px(*coef_c)).set_opacity(0), FadeIn(grid5), run_time=1.0)
        self.remove(blk)
        square = gray_img(Y5, DS).move_to(px(*sq_c))
        arr = Arrow(px(coef_c[0] + DS / 2 + 24, coef_c[1]), px(sq_c[0] - DS / 2 - 24, sq_c[1]), buff=0, color=INK,
                    stroke_width=5, max_tip_length_to_length_ratio=0.3)
        self.play(GrowArrow(arr), FadeIn(square), run_time=0.8)

        # ---- 目のふち：ズームしなおす ----
        self.at("edge", -0.1)
        self.play(FadeOut(Group(grid5, arr, square, frame)), zoomA.animate.scale(1 / SMALL_S).move_to(px(*PH_C)),
                  FadeOut(lines), run_time=0.9)
        cropB = rgb_img(ax[RB[1]:RB[1] + RB[3], RB[0]:RB[0] + RB[2]], B_in_A[3]).move_to(px(B_in_A[0], B_in_A[1]))
        cropB.set_z_index(3)
        self.add(cropB)
        self.play(cropB.animate.scale(PH_W / B_in_A[2]).move_to(px(*PH_C)), run_time=1.2)
        self.remove(cropA)

        # ---- リンギング：境目に沿った波打つにじみ ----
        self.at("ring", -0.1)
        Lb, Tb = PH_C[0] - PH_W / 2, PH_C[1] - ph_h / 2
        ts = np.linspace(0, 1, 40)
        pts = []
        for t in ts:
            x0_, y0_ = 0.60 + 0.38 * t, 0.36 + 0.46 * t
            w_ = 0.012 * np.sin(t * 6 * np.pi)
            pts.append(px(Lb + (x0_ + w_) * PH_W, Tb + (y0_ - w_) * ph_h))
        wave = VMobject(stroke_color=YELLOW, stroke_width=7).set_points_smoothly(pts)
        wave.set_z_index(5)
        self.play(Create(wave), run_time=1.0)

        # ---- ズームを戻す ----
        self.at("S08_09", 0.2)
        self.add(photo)
        self.play(FadeOut(wave), cropB.animate.scale(B_in_ph[2] / PH_W).move_to(px(B_in_ph[0], B_in_ph[1])),
                  run_time=1.2)
        self.remove(cropB)

        # ---- 多くのアプリは品質 75〜95：品質 5 が品質 80 に ----
        self.at("normal", -0.1)
        q80 = ImageMobject(pixels("cat_q80"))
        q80.set_resampling_algorithm(RESAMPLING_ALGORITHMS["cubic"])
        place(q80, *PH_C, ph_h)
        self.play(Transform(photo, q80), Transform(label, jp("品質80", 48, CYAN).move_to(label)), run_time=1.0)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 1.0)
        self.play(FadeOut(Group(photo, label)), run_time=0.9)
        self.finish()
