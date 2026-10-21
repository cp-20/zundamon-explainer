import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.catview import gray_img  # noqa: E402
from vlib.data import (MAIN_MB, MAIN_SB, all_levels, basis4, fdct4, fmt, mb, quant_steps, quantize,  # noqa: E402
                       sub_block)
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

L_C, R_C = (690, 490), (1230, 490)      # 左の表・右の表の中心
CELL = 112                               # 差のマス (S04 の差と同じ見た目)
TILE, STEP = 106, 114                     # 模様のタイル
TILE_DIM = 0.17                          # 数字の下敷きにした模様の濃さ
ZERO = "#8a91a2"
STRIP_W = 1040                           # 写真全体の数を並べた帯 (1 つの数 = 1 点)
STRIP_C = (960, 520)
JP8_C, JP8_T, JP8_G = (1700, 272), 32, 4  # JPEG の 64 種類 (比べる用)


def fm(v):
    return str(v).replace("-", "−")


def fdec(v):
    s = f"{v:.1f}"
    if s in ("-0.0",):
        s = "0.0"
    return s.replace("-", "−")


def at_k(center, k, step):
    return px(center[0] + (k % 4 - 1.5) * step, center[1] + (k // 4 - 1.5) * step)


def diff_grid(vals, center, size=42):
    """差の 4×4 (S04 と同じ：暗いマスに紫の数字)。返り値は (マス, 数字)"""
    sqs, nums = VGroup(), VGroup()
    for k in range(16):
        v = int(vals[k // 4][k % 4])
        sq = Square(u(CELL), stroke_width=2, stroke_color="#3a3f4c", fill_color="#232833", fill_opacity=1)
        sq.move_to(at_k(center, k, CELL))
        sqs.add(sq)
        nums.add(mono(fm(v), size, PURPLE).move_to(sq))
    return sqs, nums


def basis_tiles(center, opacity=1.0):
    """16 種類の模様。DC は真ん中より明るい灰 (JPEG 編と同じ描き方)"""
    B = basis4()
    g = Group()
    for k in range(16):
        b = B[k].astype(float)
        a = np.full((4, 4), 200.0) if k == 0 else 128 + 127 * b / np.abs(b).max()
        t = gray_img(a, TILE).move_to(at_k(center, k, STEP))
        t.set_opacity(opacity)
        g.add(t)
    return g


def jpeg_basis():
    """JPEG の 8×8 の 64 種類 (DCT の模様。計算で作る)"""
    n = np.arange(8)
    C = np.cos((2 * n[None, :] + 1) * n[:, None] * np.pi / 16)
    g = Group()
    step = JP8_T + JP8_G
    for uu in range(8):
        for vv in range(8):
            b = np.outer(C[uu], C[vv])
            a = np.full((8, 8), 200.0) if uu == vv == 0 else 128 + 127 * b / np.abs(b).max()
            t = gray_img(a, JP8_T).move_to(px(JP8_C[0] + (vv - 3.5) * step, JP8_C[1] + (uu - 3.5) * step))
            g.add(t)
    return g


def zig_order():
    return sorted(range(16), key=lambda k: (k // 4 + k % 4, k // 4))


class Reveal(Animation):
    """画像を、並びの順 (左上から行ごと) に n 個まで見せる"""

    def __init__(self, img, n, **kw):
        self.n = n
        super().__init__(img, **kw)

    def interpolate_mobject(self, a):
        m = self.mobject
        h, w = m.pixel_array.shape[:2]
        k = int(round(self.rate_func(a) * self.n))
        al = np.zeros(h * w, np.uint8)
        al[:k] = 255
        m.pixel_array[:, :, 3] = al.reshape(h, w)


class S05(PScene):
    def construct(self):
        sb = sub_block()
        assert (sb["x"], sb["y"]) == (164, 124)
        diff = sb["orig"] - sb["pred"]
        assert diff.min() == -3 and diff.max() == 7
        coefs = fdct4(diff)
        steps = quant_steps(sb["segment"])
        assert tuple(steps) == (20, 23)
        q = quantize(coefs, steps)
        assert q == [0] * 16 and list(sb["levels"]) == [0] * 16    # 実際に書いた数も全部 0
        flat = sb["orig"] - 128
        coefs0 = fdct4(flat)
        q0 = quantize(coefs0, steps)
        nz0 = [k for k in range(16) if q0[k]]
        assert len(nz0) == 6
        L = all_levels()
        N = L.size
        nzmask = (L.ravel() != 0)
        assert N == 211584 and int(nzmask.sum()) == 24144
        mx, my = MAIN_MB
        assert list(mb()["levels"][MAIN_SB]) == list(sb["levels"])

        # ---- 主役の 4×4 の差 ----
        self.at("s05_01", -0.1)
        dsq, dnum = diff_grid(diff, L_C)
        lab_d = jp("差", 34, PURPLE).move_to(px(L_C[0], 226))
        self.play(FadeIn(dsq), FadeIn(dnum), FadeIn(lab_d, shift=DOWN * u(6)), run_time=0.8)

        # 手順：模様に分ける → 割って丸める
        chip1 = jp("模様に分ける", 38, INK).move_to(px(760, 100))
        chip2 = jp("割って丸める", 38, INK).move_to(px(1160, 100))
        arr = Arrow(chip1.get_right() + RIGHT * u(8), chip2.get_left() + LEFT * u(8), buff=0, color=DIM,
                    stroke_width=4, max_tip_length_to_length_ratio=0.25)
        self.at("wave", -0.1)
        self.play(FadeIn(chip1, shift=DOWN * u(8)), run_time=0.6)
        self.at("div", -0.1)
        self.play(GrowArrow(arr), FadeIn(chip2, shift=DOWN * u(8)), run_time=0.6)

        # ---- 4×4 → 16 種類の模様 ----
        self.at("four", -0.1)
        self.play(pop(VGroup(dsq, dnum), 1.08, 0.6), run_time=0.6)
        self.at("p16", -0.1)
        tiles = basis_tiles(R_C)
        lab_r = jp("模様", 34, INK).move_to(px(R_C[0], 226))
        zo = zig_order()
        self.play(LaggedStart(*[FadeIn(tiles[k], scale=0.7) for k in zo], lag_ratio=0.08), FadeIn(lab_r),
                  run_time=1.5)

        # JPEG は 64 種類
        self.at("S05_03", 0.1)
        j8 = jpeg_basis()
        lab_j = jp("JPEG", 32, DIM).move_to(px(JP8_C[0], 98))
        self.play(LaggedStart(*[FadeIn(t, scale=0.7) for t in j8], lag_ratio=0.015), FadeIn(lab_j), run_time=1.4)

        # ---- 差 → 模様の量 ----
        self.at("s05_04", -0.1)
        self.play(*[t.animate.set_opacity(0) for t in j8], FadeOut(lab_j), chip1.animate.set_color(YELLOW),
                  run_time=0.6)
        self.remove(j8, *j8)
        self.at("coef", -0.1)
        for t in tiles:
            t.check_ignore = True          # 数字の下敷き
        clab = VGroup(*[mono(fm(coefs[k]), 42, INK).move_to(at_k(R_C, k, STEP)) for k in range(16)])
        flies = VGroup(*[dnum[k].copy() for k in range(16)])
        for f_ in flies:
            f_.check_ignore = True
        self.play(*[t.animate.set_opacity(TILE_DIM) for t in tiles],
                  LaggedStart(*[ReplacementTransform(flies[k], clab[k], path_arc=-0.6) for k in range(16)],
                              lag_ratio=0.04), dnum.animate.set_opacity(0.35), run_time=1.0)
        self.remove(flies, *flies)
        self.add(clab)

        # ---- 割る数で割って、丸める ----
        self.at("q", -0.1)
        divs = VGroup(*[jp(f"÷{steps[0] if k == 0 else steps[1]}", 28, CYAN).move_to(at_k(R_C, k, STEP) + DOWN * u(30))
                        for k in range(16)])
        self.play(chip1.animate.set_color(INK), chip2.animate.set_color(YELLOW),
                  *[c.animate.shift(UP * u(16)) for c in clab],
                  LaggedStart(*[FadeIn(d, shift=UP * u(6)) for d in divs], lag_ratio=0.03), run_time=0.8)
        self.at("q", 2.5)
        vals = [coefs[k] / (steps[0] if k == 0 else steps[1]) for k in range(16)]
        assert all(abs(v) < 0.5 for v in vals)      # どれも丸めると 0
        zeros = VGroup(*[mono(fm(q[k]), 42, ZERO).move_to(at_k(R_C, k, STEP)) for k in range(16)])
        self.play(*[ReplacementTransform(VGroup(clab[k], divs[k]), zeros[k]) for k in range(16)], run_time=0.8)
        self.remove(clab, *clab, divs, *divs)

        self.at("allzero", -0.1)
        self.play(LaggedStart(*[pop(zeros[k], 1.4, 0.5) for k in zo], lag_ratio=0.05), run_time=1.2)

        # ---- 予想しないと ----
        self.at("s05_06", -0.1)
        lab_r2 = jp("予想あり", 34, CYAN)
        self.play(FadeOut(VGroup(dsq, dnum, lab_d)), chip2.animate.set_color(INK), retext(lab_r, lab_r2),
                  run_time=0.7)
        self.at("flat", -0.35)
        fsq, fnum = diff_grid(flat, L_C, 40)
        lab_l = jp("予想なし (全部128)", 34, INK).move_to(px(L_C[0], 226))
        self.play(FadeIn(fsq), FadeIn(fnum), FadeIn(lab_l, shift=DOWN * u(6)), run_time=0.6)
        ltiles = basis_tiles(L_C, 0)
        for t in ltiles:
            t.check_ignore = True
        self.add(ltiles)
        self.bring_to_front(fnum)
        self.at("six", -1.15)
        fq = VGroup(*[mono(fm(q0[k]), 42, INK if q0[k] else ZERO).move_to(at_k(L_C, k, STEP)) for k in range(16)])
        self.play(FadeOut(fsq), *[t.animate.set_opacity(TILE_DIM) for t in ltiles],
                  *[ReplacementTransform(fnum[k], fq[k]) for k in range(16)],
                  chip2.animate.set_color(YELLOW), run_time=1.0)

        self.at("six", -0.1)
        n6 = jp(f"{len(nz0)} 個", 44, YELLOW).move_to(px(L_C[0], 780))
        self.play(*[fq[k].animate.set_color(YELLOW) for k in nz0], chip2.animate.set_color(INK), run_time=0.5)
        self.play(LaggedStart(*[pop(fq[k], 1.35, 0.5) for k in nz0], lag_ratio=0.12), FadeIn(n6, shift=UP * u(8)),
                  run_time=1.1)

        self.at("cost", -0.1)
        n0 = jp(f"{sum(1 for v in q if v)} 個", 44, CYAN).move_to(px(R_C[0], 780))
        self.play(FadeIn(n0, shift=UP * u(8)), run_time=0.6)
        self.play(pop(n6, 1.15, 0.6), pop(n0, 1.15, 0.6), run_time=0.6)

        # ---- 写真全体の数 ----
        self.at("s05_08", -0.1)
        self.play(FadeOut(VGroup(fq, lab_l, n6, n0, lab_r, chip1, chip2, arr)),
                  *[t.animate.set_opacity(0) for t in [*ltiles, *tiles]], run_time=0.8)
        self.remove(ltiles, *ltiles, tiles, *tiles)

        H = -(-N // STRIP_W)
        base = np.zeros((H * STRIP_W, 4), np.uint8)
        base[:N] = (70, 76, 92, 255)
        hi = np.zeros((H * STRIP_W, 4), np.uint8)
        hi[:N][nzmask] = (242, 193, 78, 255)
        strip = ImageMobject(base.reshape(H, STRIP_W, 4))
        strip.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
        strip.width = u(STRIP_W)
        strip.move_to(px(*STRIP_C))
        strip.pixel_array[:, :, 3] = 0
        strip.check_ignore = True
        glow = ImageMobject(hi.reshape(H, STRIP_W, 4))
        glow.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
        glow.width = u(STRIP_W)
        glow.move_to(strip)
        glow.set_opacity(0)
        glow.check_ignore = True

        # 主役の 16 個は、帯の中のその場所へ
        idx0 = ((my * 29 + mx) * 24 + MAIN_SB) * 16
        assert (L.ravel()[idx0:idx0 + 16] == 0).all()
        sx0, sy0 = STRIP_C[0] - STRIP_W / 2, STRIP_C[1] - H / 2

        def spot(i):
            j = idx0 + i
            return px(sx0 + j % STRIP_W + 0.5, sy0 + j // STRIP_W + 0.5)
        self.at("whole", -0.1)
        for z in zeros:
            z.check_ignore = True
        self.play(LaggedStart(*[z.animate.move_to(spot(i)).scale(0.05).set_opacity(0.4) for i, z in enumerate(zeros)],
                              lag_ratio=0.03), run_time=0.9)
        lab_all = jp(f"{fmt(N)} 個", 40, INK).move_to(px(960, 372))
        self.add(strip)
        self.play(Reveal(strip, N, rate_func=linear), FadeOut(zeros), FadeIn(lab_all, shift=DOWN * u(6)), run_time=1.3)
        self.remove(zeros, *zeros)

        self.at("nz", -0.1)
        self.add(glow)
        nzc = fmt(int(nzmask.sum()))
        frac = jp(f"{nzc} / {fmt(N)}", 48, INK, t2c={nzc: YELLOW}).move_to(px(960, 700))
        self.play(glow.animate.set_opacity(1), FadeIn(frac, shift=UP * u(6)), run_time=1.0)

        self.at("rate", -0.1)
        self.play(pop(frac, 1.15, 0.7), run_time=0.7)

        self.at("lots", -0.1)
        self.play(glow.animate.set_opacity(0.35), run_time=0.7)
        self.play(pop(strip, 1.03, 0.7), pop(glow, 1.03, 0.7), run_time=0.7)

        self.at("diff", -0.1)
        self.play(FadeOut(VGroup(frac, lab_all)), glow.animate.set_opacity(1), run_time=0.7)
        # 終わり：帯 (灰) と、0 でない所が黄色 (S06 の始まりと同じ)
        self.finish()
