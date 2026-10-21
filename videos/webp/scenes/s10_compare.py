import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import fmt, pixels, size, y_planes  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

JPG, WEBP = "cat_q5.jpg", "cat_q10"
BOX_W, BOX_H = 630, 420                     # 写真の枠 (px)。ズームしても枠は変えず、見える範囲だけを変える
BOX_C = {"j": (625, 245), "w": (1295, 245)}
SRC_W, SRC_H = 450, 300                     # 写真の全体 (右端の 1 列は使わない：枠と同じ 3:2)
EYE_WIN = (118, 82, 226, 154)               # 目のあたり (画素の座標。3:2)
OUT = 2                                     # 描く配列は枠の 2 倍の細かさ


def win_at(a):
    """ズームの進み具合 a (0 = 全体, 1 = 目) の窓。拡大率が一定の速さで変わる"""
    w0 = np.array([0, 0, SRC_W, SRC_H], float)
    w1 = np.array(EYE_WIN, float)
    r = (w1[2] - w1[0]) / (w0[2] - w0[0])
    g = (1 - r ** a) / (1 - r)
    return tuple(w0 + (w1 - w0) * g)


def view(src, a):
    im = Image.fromarray(np.ascontiguousarray(src[..., :3]))
    out = np.asarray(im.resize((BOX_W * OUT, BOX_H * OUT), Image.NEAREST, box=win_at(a)))
    return np.dstack([out, np.full(out.shape[:2], 255, np.uint8)])


def photo(src, key):
    m = ImageMobject(view(src, 0))
    m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.width = u(BOX_W)
    m.move_to(px(*BOX_C[key]))
    m.check_ignore = True
    return m


class Zoom(Animation):
    """2 枚の写真を、同じ場所へ同時に同じ倍率でズーム (a0 → a1)"""

    def __init__(self, pairs, a0, a1, **kw):
        self.pairs, self.a0, self.a1 = pairs, a0, a1
        kw.setdefault("rate_func", smooth)
        super().__init__(Group(*[m for m, _ in pairs]), **kw)

    def interpolate_mobject(self, alpha):
        a = self.a0 + (self.a1 - self.a0) * alpha
        for m, src in self.pairs:
            op = m.pixel_array[0, 0, 3]
            m.pixel_array = view(src, a)
            m.pixel_array[:, :, 3] = op


COL_X = (690, 1200)                         # 弱点の 2 つの列
PIC_Y, CC = 330, 100                        # 絵の中心の高さ、2×2 の 1 マス


def lum(v):
    g = float(np.clip(v, 0, 255)) / 255
    return rgb_to_color([g, g, g])


def yuv_rgb(y, uu, vv):
    """明るさ y と色 U・V → 表示の色 (BT.601。VP8 と同じ式の小数版)"""
    c, d, e = 1.164 * (y - 16), uu - 128, vv - 128
    rgb = np.clip([c + 1.596 * e, c - 0.391 * d - 0.813 * e, c + 2.018 * d], 0, 255) / 255
    return rgb_to_color(rgb)


def pick_chroma():
    """猫の顔のあたりで、明るさが 30 以上ばらつく 2×2 (色の点 1 つぶん) のうち、色がいちばんはっきりした所"""
    Y, U, V = y_planes("cat_q80")
    best = None
    for cy in range(35, 85):
        for cx in range(55, 115):
            y = Y[2 * cy:2 * cy + 2, 2 * cx:2 * cx + 2]
            sc = abs(int(U[cy, cx]) - 128) + abs(int(V[cy, cx]) - 128)
            if np.ptp(y) >= 30 and (best is None or sc > best[0]):
                best = (sc, cx, cy, y.tolist(), int(U[cy, cx]), int(V[cy, cx]))
    return best[1:]


class S10(PScene):
    def construct(self):
        nj, nw = size(JPG), size(WEBP)
        assert (nj, nw) == (3797, 3898) and round((nj + nw) / 2, -3) == 4000      # どちらも 4 千バイトくらい
        sj, sw = pixels(JPG), pixels(WEBP)
        assert sj.shape[:2] == sw.shape[:2] == (300, 451)

        pj, pw = photo(sj, "j"), photo(sw, "w")
        lab_j = jp("JPEG 品質5", 36, INK).move_to(px(BOX_C["j"][0], 500))
        lab_w = jp("WebP 品質10", 36, INK).move_to(px(BOX_C["w"][0], 500))
        num_j = jp(f"{fmt(nj)} バイト", 32, DIM).move_to(px(BOX_C["j"][0], 556))
        num_w = jp(f"{fmt(nw)} バイト", 32, DIM).move_to(px(BOX_C["w"][0], 556))

        # ---- 2 枚の写真 ----
        self.at("s10_01", -0.1)
        self.play(FadeIn(pj, scale=0.96), FadeIn(pw, scale=0.96), FadeIn(lab_j), FadeIn(lab_w), run_time=0.8)
        self.at("same", -0.1)
        self.play(FadeIn(num_j, shift=UP * u(8)), FadeIn(num_w, shift=UP * u(8)), run_time=0.6)

        # ---- 目のあたりへズーム ----
        pairs = [(pj, sj), (pw, sw)]
        self.at("tiny", -0.1)
        self.play(Zoom(pairs, 0, 1), run_time=2.2)

        self.at("jb", -0.1)
        self.play(lab_j.animate.set_color(CORAL), pop(pj, 1.05, 0.7), run_time=0.7)
        self.at("wb", -0.1)
        self.play(lab_w.animate.set_color(CYAN), pop(pw, 1.05, 0.7), run_time=0.7)

        self.at("why", -0.1)
        why = VGroup(jp("予想", 34, CYAN), jp("ループフィルタ", 34, CYAN)).arrange(RIGHT, buff=u(48))
        why.move_to(px(BOX_C["w"][0], 650))
        self.play(LaggedStart(*[FadeIn(t, shift=UP * u(8)) for t in why], lag_ratio=0.4), run_time=1.0)

        # ---- 弱点 ----

        weak = jp("弱点", 48, CORAL).move_to(px(960, 110))
        c1 = jp("色はいつも半分", 40, INK).move_to(px(COL_X[0], 560))
        c2 = jp("古いソフトで開けないことも", 40, INK).move_to(px(COL_X[1], 560))
        self.at("s10_04", -0.1)
        self.play(pj.animate.set_opacity(0), pw.animate.set_opacity(0),
                  FadeOut(VGroup(lab_j, lab_w, num_j, num_w, why)), FadeIn(weak, scale=0.8), run_time=0.7)
        self.remove(pj, pw)

        # 色は 2×2 の点で 1 つ：明るさ 4 つの上に、色 1 つをかぶせる
        cx, cy, ys, uu, vv = pick_chroma()
        assert (cx, cy) == (97, 82)
        grays = VGroup(*[Square(u(CC), stroke_width=2, stroke_color="#2a2e38", fill_color=lum(ys[r][c]), fill_opacity=1)
                         .move_to(px(COL_X[0] + (c - 0.5) * CC, PIC_Y + (r - 0.5) * CC)) for r in range(2) for c in range(2)])
        chip = Square(u(2 * CC), stroke_width=4, stroke_color=INK, fill_color=yuv_rgb(np.mean(ys), uu, vv),
                      fill_opacity=1).move_to(px(COL_X[0] + 2 * CC + 40, PIC_Y))
        self.at("chroma", -0.1)
        self.play(LaggedStart(*[FadeIn(g, scale=0.8) for g in grays], lag_ratio=0.12), FadeIn(chip),
                  FadeIn(c1, shift=UP * u(10)), run_time=0.9)
        self.play(chip.animate.move_to(grays).set_fill(opacity=0.55), run_time=0.9)

        # 古いソフト：開けないファイル
        card = RoundedRectangle(corner_radius=u(14), width=u(170), height=u(210), stroke_width=3, stroke_color=DIM,
                                fill_color="#232833", fill_opacity=1).move_to(px(COL_X[1], PIC_Y))
        fname = mono("cat.webp", 28, INK).move_to(px(COL_X[1], PIC_Y + 60))
        qm = jp("？", 96, CORAL).move_to(px(COL_X[1], PIC_Y - 28))
        self.at("old", -0.1)
        self.play(FadeIn(card), FadeIn(fname), FadeIn(c2, shift=UP * u(10)), run_time=0.6)
        self.play(FadeIn(qm, scale=1.6), run_time=0.5)

        self.at("use", -0.1)
        self.play(pop(VGroup(c1, c2), 1.06, 0.7), run_time=0.7)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 0.8)
        self.play(FadeOut(VGroup(weak, c1, c2, grays, chip, card, fname, qm)), run_time=0.7)
        self.finish()
