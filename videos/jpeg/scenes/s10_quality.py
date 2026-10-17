import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, fmt, pixels  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

QS = [5, 10, 30, 50, 80, 95]
SIZES = [len(file_bytes(f"cat_q{q}")) for q in QS]
assert SIZES[5] >= 2 * SIZES[4]          # 台詞「95だと、80の倍以上」

# 棒グラフ
COL_X0, COL_DX = 510, 166
BASE_Y, BAR_MAX = 640, 430
BAR_COL = CYAN
# 線のまわりのズーム（輪郭線と白背景の境目）
CROP_Y, CROP_X, CROP_N = 176, 124, 56
IMG_H = 640
IMG_CX = (700, 1220)
IMG_CY = 465


def rgb_mob(arr, height_px, k=1):
    """RGB 配列 → ImageMobject。k 倍に整数で引き伸ばして、ドットのまま置く"""
    a = np.ascontiguousarray(np.asarray(arr)[..., :3]).repeat(k, 0).repeat(k, 1)
    m = ImageMobject(a)
    if k > 1:
        m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.height = u(height_px)
    return m


class S10(PScene):
    def construct(self):
        # ---- 品質ごとの写真と、ファイルの大きさ（実際のファイルサイズ）----
        xs = [COL_X0 + COL_DX * i for i in range(6)]
        thumbs, bars, vals, names = [], [], [], []
        for q, s, x in zip(QS, SIZES, xs):
            t = rgb_mob(pixels(f"cat_q{q}"), 108).move_to(px(x, 750))
            h = BAR_MAX * s / SIZES[-1]
            b = Rectangle(width=u(92), height=u(h), stroke_width=0, fill_color=BAR_COL, fill_opacity=0.9)
            b.move_to(px(x, BASE_Y), aligned_edge=DOWN)
            v = jp(fmt(s), 32, INK).next_to(b, UP, buff=u(12))
            n = jp(f"品質 {q}", 34, INK).move_to(px(x, 850))
            thumbs.append(t); bars.append(b); vals.append(v); names.append(n)
        base = Line(px(COL_X0 - 70, BASE_Y), px(COL_X0 + COL_DX * 5 + 70, BASE_Y), stroke_width=3, color=DIM)
        unit = jp("ファイルの大きさ（バイト）", 32, DIM).move_to(px(960, 130))

        self.at("s10_01")
        self.play(LaggedStart(*[FadeIn(Group(t, n), shift=UP * u(10)) for t, n in zip(thumbs, names)],
                              lag_ratio=0.12), run_time=1.5)
        self.at("sizes", -0.1)
        for b in bars:
            b.save_state()
            b.stretch_to_fit_height(u(0.01), about_edge=DOWN)
        self.play(Create(base), FadeIn(unit),
                  LaggedStart(*[b.animate.restore() for b in bars], lag_ratio=0.12),
                  LaggedStart(*[FadeIn(v, shift=UP * u(8)) for v in vals], lag_ratio=0.12), run_time=1.6)

        # ---- 95 は 80 の倍以上 ----
        self.at("q95", -0.05)
        h80 = BAR_MAX * SIZES[4] / SIZES[-1]
        dash = DashedLine(px(xs[4] - 60, BASE_Y - 2 * h80), px(xs[5] + 60, BASE_Y - 2 * h80),
                          color=YELLOW, stroke_width=3, dash_length=u(8))
        self.play(bars[4].animate.set_fill(YELLOW), bars[5].animate.set_fill(YELLOW), Create(dash),
                  pop(vals[5], 1.2, 0.6), run_time=0.7)

        # ---- 上げすぎても見た目はほとんど同じ ----
        self.at("top", -0.05)
        rest = [Group(thumbs[i], names[i]) for i in range(4)]
        self.play(*[g.animate.set_opacity(0.3) for g in rest],
                  *[pop(thumbs[i], 1.25, 0.8) for i in (4, 5)], run_time=0.9)

        # ---- イラストを JPEG で保存 ----
        self.at("illust", -0.1)
        A, B = pixels("zunda_white"), pixels("zunda_q80")
        imgs = [rgb_mob(A, IMG_H).move_to(px(IMG_CX[0], IMG_CY)), rgb_mob(B, IMG_H).move_to(px(IMG_CX[1], IMG_CY))]
        tags = [jp("PNG", 40, YELLOW).move_to(px(IMG_CX[0], 110)), jp("JPEG", 40, CYAN).move_to(px(IMG_CX[1], 110))]
        old = Group(*thumbs, *names, *bars, *vals, base, unit, dash)
        for m in old:
            m.check_ignore = True
        self.play(FadeOut(old), *[FadeIn(i) for i in imgs], *[FadeIn(t) for t in tags], run_time=0.8)
        self.remove(old, *old)

        # ---- 線のまわりへズーム（実画素）----
        self.at("line", -0.1)
        sc = IMG_H / A.shape[0]
        crops = []
        for arr, img, cx in zip((A, B), imgs, IMG_CX):
            c = rgb_mob(arr[CROP_Y:CROP_Y + CROP_N, CROP_X:CROP_X + CROP_N], CROP_N * sc, k=8)
            c.move_to(img.get_center() + (np.array([CROP_X + CROP_N / 2 - A.shape[1] / 2,
                                                    -(CROP_Y + CROP_N / 2 - A.shape[0] / 2), 0]) * sc / UNIT))
            crops.append(c)
        ZH = 430
        ZY = 440
        self.add(*crops)
        self.play(*[FadeOut(i) for i in imgs],
                  *[c.animate.scale(ZH / (CROP_N * sc)).move_to(px(cx, ZY)) for c, cx in zip(crops, IMG_CX)],
                  tags[0].animate.move_to(px(IMG_CX[0], 175)), tags[1].animate.move_to(px(IMG_CX[1], 175)),
                  run_time=1.6)
        self.remove(*imgs)

        # ---- もやもや ----
        self.at("noise", -0.1)
        moya = jp("もやもや", 36, CORAL).move_to(px(IMG_CX[1], 700))
        self.play(FadeIn(moya, shift=UP * u(8)), pop(crops[1], 1.06, 0.6), run_time=0.7)

        # ---- くっきり → もやもや ----
        self.at("sharp", -0.1)
        self.play(pop(crops[0], 1.06, 0.6), run_time=0.6)
        self.at("mosq", -0.1)
        self.play(pop(crops[1], 1.06, 0.6), pop(moya, 1.2, 0.6), run_time=0.6)

        # ---- 得意なものが違う ----
        self.at("rule", -0.1)
        gone = Group(*crops, *tags, moya)
        cat = rgb_mob(pixels("cat"), 180).move_to(px(620, 270))
        zun = rgb_mob(A, 180).move_to(px(620, 600))
        photo = jp("写真", 40, INK).move_to(px(790, 270), aligned_edge=LEFT)
        illu = jp("イラスト・文字", 40, INK).move_to(px(790, 600), aligned_edge=LEFT)
        AX0, AX1, RX = 1110, 1200, 1230
        arr1 = Arrow(px(AX0, 270), px(AX1, 270), buff=0, color=DIM, stroke_width=5, max_tip_length_to_length_ratio=0.4)
        arr2 = Arrow(px(AX0, 600), px(AX1, 600), buff=0, color=DIM, stroke_width=5, max_tip_length_to_length_ratio=0.4)
        j_lbl = jp("JPEG", 48, CYAN).move_to(px(RX, 262), aligned_edge=LEFT)
        j_sub = jp("なめらか", 30, CYAN).move_to(px(RX, 325), aligned_edge=LEFT)
        p_lbl = jp("PNG", 48, YELLOW).move_to(px(RX, 592), aligned_edge=LEFT)
        p_sub = jp("くっきり", 30, YELLOW).move_to(px(RX, 655), aligned_edge=LEFT)
        self.play(FadeOut(gone), FadeIn(cat, shift=UP * u(8)), FadeIn(photo, shift=UP * u(8)), run_time=0.6)
        self.play(GrowArrow(arr1), FadeIn(j_lbl, shift=RIGHT * u(8)), FadeIn(j_sub, shift=RIGHT * u(8)), run_time=0.7)
        self.at("rule", 2.0)  # 「イラストや文字は」の頭
        self.play(FadeIn(zun, shift=UP * u(8)), FadeIn(illu, shift=UP * u(8)), run_time=0.6)
        self.play(GrowArrow(arr2), FadeIn(p_lbl, shift=RIGHT * u(8)), FadeIn(p_sub, shift=RIGHT * u(8)), run_time=0.7)
        self.at("fit", -0.1)
        self.play(pop(j_lbl, 1.2, 0.6), pop(p_lbl, 1.2, 0.6), run_time=0.6)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 1.0)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.8)
        self.finish()
