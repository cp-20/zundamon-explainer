import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import SIZE_COLOR, cus, dec, fmt, picture_size, pixels, rgb_decoded, splits  # noqa: E402
import hevctables as HT  # noqa: E402  (vlib.data が tools/ を探す場所に入れる)
from vlib.photoview import PhotoView, PRect, TrackFade, ViewAnim, move_view, partition_lines  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)          # S03 の終わりと同じ
FAN_C = (740, 450)                        # 主役のブロックの真ん中 (画面)
ZBOX = (FAN_C, 600, 600)                  # 寄ったときの箱 (1 画素 15px)
PL = (384, 192, 32)                       # プラナーの見本 (背景のぼやけた所の 32×32)
WH = (136, 272, 4)                        # ひげの見本 (斜めの向き)
WH_C, WH_O = (700, 430), (1225, 430)      # ひげ：予想 / 元 の箱の中心
WH_BOX = 510
WH_WIN = (130, 268, 142, 280)
PANEL_X = 1660
TILE = 230
TILE_C = [(1270, 330), (1270, 650)]
BAR_X0, BAR_X1, BAR_BASE, BAR_H = 470, 1450, 820, 400


def flow_dir(m):
    """角度の予想 m の、点の流れる向き (画面の px、下が +y)"""
    a = HT.INTRA_ANGLE[m] / 32
    return np.array([-a, 1.0]) if m >= 18 else np.array([1.0, -a])


def vec(d):
    """画面の向き → Manim の向き (単位)"""
    d = np.asarray(d, float)
    d = d / np.hypot(*d)
    return np.array([d[0], -d[1], 0])


def ycc_rgb(Y, Cb, Cr):
    Y, Cb, Cr = (np.asarray(a, np.float64) for a in (Y, Cb, Cr))
    r = Y + 1.402 * (Cr - 128)
    g = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
    b = Y + 1.772 * (Cb - 128)
    return np.clip(np.round(np.dstack([r, g, b])), 0, 255).astype(np.uint8)


def img_mob(rgb, width_px):
    a = np.asarray(rgb, np.uint8)
    m = ImageMobject(np.dstack([a, np.full(a.shape[:2], 255, np.uint8)]))
    m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.width = u(width_px)
    m.check_ignore = True
    return m


class LineOp(Animation):
    """PLine の不透明度を変える (s03 と同じ)"""

    def __init__(self, lines, to, **kw):
        self.lines = list(lines)
        super().__init__(VGroup(*self.lines), **kw)
        self.to = to
        self.start = [ln._op if hasattr(ln, "_op") else ln.get_stroke_opacity() for ln in self.lines]

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        for ln, s in zip(self.lines, self.start):
            ln._op = s + (self.to - s) * a
            ln.sync()


def arrow(a, b, color, width=4, tip=16):
    ln = Arrow(a, b, buff=0, color=color, stroke_width=width, tip_length=u(tip),
               max_tip_length_to_length_ratio=0.5, max_stroke_width_to_length_ratio=40)
    return ln


class S04(PScene):
    def construct(self):
        d = dec()
        W, H = picture_size()
        pus = [p for c in d.cus for p in c["pus"]]
        cnt = Counter(p["mode"] for p in pus)
        assert len(pus) == 1104 and cnt.most_common(1)[0] == (0, 236)
        assert len(HT.INTRA_ANGLE) == 35 and sum(a is not None for a in HT.INTRA_ANGLE) == 33

        # ---- プラナーの見本 ----
        px0, py0, n = PL
        pu = next(p for p in pus if (p["x"], p["y"], p["size"]) == (px0, py0, n))
        cu = next(c for c in d.cus if pu in c["pus"])
        assert pu["mode"] == 0 and cu["chroma_mode"] == 0 and px0 > 330      # 背景 (右のぼやけた所)
        ramps = {}
        for ci, (x, y, s) in ((0, (px0, py0, n)), (1, (px0 // 2, py0 // 2, n // 2)), (2, (px0 // 2, py0 // 2, n // 2))):
            k = {}
            pr = d.intra_pred(ci, x, y, s, 0, keep=k)
            assert (pr == d.pred[ci][y:y + s, x:x + s]).all()
            Lf, Tf = np.array(k["left"], float), np.array(k["top"], float)
            X, Y = np.meshgrid(np.arange(s), np.arange(s))
            hr = ((s - 1 - X) * Lf[1 + Y] + (X + 1) * Tf[1 + s]) / s       # 横の坂：左の点 → 右上の点
            vr = ((s - 1 - Y) * Tf[1 + X] + (Y + 1) * Lf[1 + s]) / s       # 縦の坂：上の点 → 左下の点
            assert np.abs((hr + vr) / 2 - pr).max() <= 0.5 + 1e-9                # 2 枚の平均 (丸め)
            ramps[ci] = (hr, vr, pr)

        def up2(a):
            return np.kron(a, np.ones((2, 2)))
        rgb_h = ycc_rgb(ramps[0][0], up2(ramps[1][0]), up2(ramps[2][0]))
        rgb_v = ycc_rgb(ramps[0][1], up2(ramps[1][1]), up2(ramps[2][1]))
        rgb_p = ycc_rgb(ramps[0][2], up2(ramps[1][2]), up2(ramps[2][2]))

        # ---- ひげの見本 ----
        wx, wy, wn = WH
        wpu = next(p for p in pus if (p["x"], p["y"], p["size"]) == (wx, wy, wn))
        wm = wpu["mode"]
        assert 2 <= wm <= 34 and min(abs(wm - 10), abs(wm - 26)) >= 5        # 斜め
        wk = {}
        wpr = d.intra_pred(0, wx, wy, wn, wm, keep=wk)
        assert (wpr == d.pred[0][wy:wy + wn, wx:wx + wn]).all()
        ang = HT.INTRA_ANGLE[wm]
        assert wm < 18 and ang > 0        # 左の列から、右上へ流れる

        # ---- S03 の終わり：写真と割れ方 ----
        base = rgb_decoded().astype(np.float32).copy()
        view = PhotoView(base, *PHOTO)
        view.check_ignore = True
        self.add(view)
        levels = partition_lines(view, splits(), cus(), W, H, SIZE_COLOR)
        lines = [ln for ls in levels.values() for ln in ls]
        self.add(*lines)

        # ---- 1 つのブロックへ寄る ----
        self.at("s04_01", -0.05)
        bcx, bcy = px0 + n / 2, py0 + n / 2
        half = 20
        win = (bcx - half, bcy - half, bcx + half, bcy + half)
        lit = np.ones((H, W), np.float32)

        def dim(t):
            lit[:] = 1 - 0.45 * t
            lit[py0 - 1:py0 + n + 1, px0 - 1:px0 + n + 1] = 1
            view.lit = lit
        cur = PRect(view, px0, py0, n, n, stroke_color=YELLOW, stroke_width=5)
        cur.set_stroke(opacity=0)
        self.add(cur)
        self.play(move_view(view, win, ZBOX), ViewAnim(view, dim), LineOp(lines, 0), TrackFade(cur, 0, 1), run_time=1.4)
        self.remove(*lines)

        # 中身はまだない
        self.at("pred", -0.1)
        blk = np.ones((n, n), np.float32)

        def dark(t):
            lit[py0:py0 + n, px0:px0 + n] = 1 - 0.85 * t * blk
            view.lit = lit
        q = jp("？", 120, DIM).move_to(view.to_point(bcx, bcy))
        self.play(ViewAnim(view, dark), FadeIn(q, scale=0.8), run_time=0.7)

        # 上の行と左の列
        self.at("known", -0.1)
        top = PRect(view, px0 - 1, py0 - 1, win[2] - px0 + 1, 1, stroke_color=CYAN, stroke_width=4, fill_color=CYAN,
                    fill_opacity=0.18)
        left = PRect(view, px0 - 1, py0, 1, win[3] - py0, stroke_color=CYAN, stroke_width=4, fill_color=CYAN, fill_opacity=0.18)
        top.check_ignore = left.check_ignore = True
        self.play(GrowFromEdge(top, LEFT), GrowFromEdge(left, UP), run_time=0.9)
        self.play(Indicate(VGroup(top, left), color=CYAN, scale_factor=1.0), run_time=0.8)

        # ---- WebP の 10 通り ----
        O = np.array(FAN_C, float)
        R0, R1 = 46, 290
        self.at("webp", -0.1)
        webp_dirs = [(0, 1), (1, 0), (-1, 1), (1, 1), (0.5, 1), (-0.5, 1), (1, 0.5), (1, -0.5)]
        warr = VGroup(*[arrow(px(*(O + R0 * vec(dd)[:2] * [1, -1])), px(*(O + 250 * vec(dd)[:2] * [1, -1])),
                              DIM, width=9, tip=26) for dd in webp_dirs])
        lab_w = mix("WebP 10通り", 44, DIM).move_to(px(PANEL_X, 170))
        num_w = VGroup()
        self.play(FadeOut(q), LaggedStart(*[GrowArrow(a) for a in warr], lag_ratio=0.08),
                  FadeIn(lab_w, shift=LEFT * u(10)), FadeIn(num_w, shift=LEFT * u(10)), run_time=1.3)

        # ---- HEIC の 35 通り：33 の向き ----
        self.at("n35", -0.1)
        lab_h = mix("HEIC 35通り", 44, CYAN).move_to(px(PANEL_X, 260))
        num_h = VGroup()
        self.play(FadeIn(lab_h, shift=LEFT * u(10)), FadeIn(num_h, shift=LEFT * u(10)),
                  warr.animate.set_opacity(0.35), run_time=0.8)
        self.at("angles", -0.1)
        modes = list(range(2, 35))
        fan = VGroup(*[arrow(px(*(O + R0 * vec(flow_dir(m))[:2] * [1, -1])), px(*(O + R1 * vec(flow_dir(m))[:2] * [1, -1])),
                             CYAN, width=3.5, tip=15) for m in modes])
        self.play(LaggedStart(*[GrowArrow(a) for a in fan], lag_ratio=0.06), run_time=2.0)

        # WebP の隣り合う 2 本 (真下と、下へ少し右) のあいだに、HEIC の向きが何本も入る
        self.at("fine", -0.1)

        def theta(d):
            v = vec(d)
            return np.arctan2(v[1], v[0])
        wa, wb = sorted((theta((0, 1)), theta((0.5, 1))))
        between = [k for k, m in enumerate(modes) if wa + 1e-6 < theta(flow_dir(m)) < wb - 1e-6]
        assert len(between) == 4
        pair = VGroup(warr[webp_dirs.index((0, 1))], warr[webp_dirs.index((0.5, 1))])
        gap = Arc(radius=u(272), start_angle=wa, angle=wb - wa, arc_center=px(*O), stroke_color=YELLOW, stroke_width=5)
        self.bring_to_front(pair)
        self.play(warr.animate.set_opacity(0.35), pair.animate.set_opacity(1).set_color(INK), Create(gap), run_time=0.6)
        self.play(LaggedStart(*[fan[k].animate.set_color(YELLOW) for k in between], lag_ratio=0.25), run_time=1.0)

        # ---- プラナー ----
        # 坂が見えるように、明るさの幅を広げる (このブロックの元と予想の最小〜最大を 0〜255 に。比べるものすべてに同じ処理)
        oblk = pixels("cat")[py0:py0 + n, px0:px0 + n, :3].astype(np.float64)
        lo = min(oblk.min(), rgb_p.min())
        hi = max(oblk.max(), rgb_p.max())
        assert hi - lo > 40

        def st(a):
            return np.clip((np.asarray(a, np.float64) - lo) * 255 / (hi - lo), 0, 255)
        base0 = base.copy()
        base_st = st(base0).astype(np.float32)

        def stretch(t):
            view.base[:] = base0 * (1 - t) + base_st * t
        self.at("planar", -0.1)
        self.play(FadeOut(VGroup(fan, warr, gap, lab_w, num_w)), ViewAnim(view, stretch),
                  run_time=0.9)
        rgb_h, rgb_v, rgb_p = (st(a).round().astype(np.uint8) for a in (rgb_h, rgb_v, rgb_p))
        self.at("name", -0.1)
        lab_p = jp("プラナー", 48, CYAN).move_to(px(TILE_C[0][0], 130))
        self.play(FadeIn(lab_p, shift=UP * u(8)), run_time=0.6)

        p = view.px_per_pixel()

        def cell(x, y, rgb, w=p):
            sq = Square(u(w), stroke_width=2, stroke_color=YELLOW, fill_color=rgb_to_color(np.asarray(rgb) / 255),
                        fill_opacity=1).move_to(view.to_point(x + 0.5, y + 0.5))
            return sq
        disp = st(rgb_decoded())
        TRp, BLp = (px0 + n, py0 - 1), (px0 - 1, py0 + n)
        tr, bl = cell(*TRp, disp[TRp[1], TRp[0]]), cell(*BLp, disp[BLp[1], BLp[0]])
        tr.set_stroke(YELLOW, 5)
        bl.set_stroke(YELLOW, 5)

        blank = base.copy()

        def fill_block(rgb, key):
            """ブロックの中を、key の順 (0〜1) に rgb で塗っていく"""
            src0 = view.base[py0:py0 + n, px0:px0 + n].copy()
            l0 = lit[py0:py0 + n, px0:px0 + n].copy()

            def fn(t):
                m = np.clip((t * (1 + 3 / n) - key) * n / 3, 0, 1)[..., None]
                view.base[py0:py0 + n, px0:px0 + n] = src0 * (1 - m) + rgb * m
                lit[py0:py0 + n, px0:px0 + n] = l0 * (1 - m[..., 0]) + m[..., 0]
                view.lit = lit
            return ViewAnim(view, fn, rate_func=linear)

        def reset_block():
            view.base[py0:py0 + n, px0:px0 + n] = blank[py0:py0 + n, px0:px0 + n]
            lit[py0:py0 + n, px0:px0 + n] = 0.15
            view.lit = lit
            view.refresh()

        X, Y = np.meshgrid(np.arange(n), np.arange(n))
        a0, b0 = view.to_point(px0, py0), view.to_point(px0 + n, py0 + n)
        bc = (a0 + b0) / 2

        def lift(rgb, slot, dirv):
            img = img_mob(rgb, p * n).move_to(bc)
            self.add(img)
            reset_block()
            c = px(*TILE_C[slot])
            ar = Arrow(c - dirv * u(TILE * 0.36), c + dirv * u(TILE * 0.36), buff=0, color=INK, stroke_width=7,
                       tip_length=u(26), max_tip_length_to_length_ratio=0.3)
            ar.check_ignore = True
            arrows.append(ar)
            return img, AnimationGroup(img.animate.set(width=u(TILE)).move_to(c), GrowArrow(ar, run_time=0.5))
        arrows = []

        # 横の坂：右上の点を、各行の右はしへ
        self.at("grad", -0.1)
        self.play(FadeIn(tr, scale=1.3), FadeIn(bl, scale=1.3), run_time=0.4)
        trc = [tr.copy().set_stroke(width=0) for _ in range(n)]
        for c in trc:
            c.check_ignore = True
        self.play(LaggedStart(*[c.animate(path_arc=-0.5).move_to(view.to_point(px0 + n + 0.5, py0 + i + 0.5))
                                for i, c in enumerate(trc)], lag_ratio=0.03), run_time=0.7)
        self.play(fill_block(rgb_h.astype(np.float32), X / n), run_time=1.0)
        img_h, mv = lift(rgb_h, 0, RIGHT)
        blc = [bl.copy().set_stroke(width=0) for _ in range(n)]
        for c in blc:
            c.check_ignore = True
        self.play(mv, FadeOut(VGroup(*trc)),
                  LaggedStart(*[c.animate(path_arc=0.5).move_to(view.to_point(px0 + i + 0.5, py0 + n + 0.5))
                                for i, c in enumerate(blc)], lag_ratio=0.03), run_time=0.8)
        self.remove(*trc)
        self.play(fill_block(rgb_v.astype(np.float32), Y / n), run_time=1.0)
        img_v, mv = lift(rgb_v, 1, DOWN)
        self.play(mv, FadeOut(VGroup(*blc)), run_time=0.6)
        self.remove(*blc)

        # 2 枚が重なって平均に
        self.at("smooth", -0.4)
        img_p = img_mob(rgb_p, p * n).move_to(bc)
        img_p.set_opacity(0)
        self.add(img_p)
        self.play(img_h.animate.set(width=u(p * n)).move_to(bc).set_opacity(0.0),
                  img_v.animate.set(width=u(p * n)).move_to(bc).set_opacity(0.0),
                  img_p.animate.set_opacity(1), FadeOut(VGroup(tr, bl, *arrows)), run_time=1.0)
        self.remove(img_h, img_v)
        view.base[py0:py0 + n, px0:px0 + n] = rgb_p
        lit[py0:py0 + n, px0:px0 + n] = 1
        view.lit = lit
        view.refresh()
        self.remove(img_p)
        self.play(pop(cur, 1.06, 0.6), run_time=0.6)

        # ---- 棒グラフ：向きごとの数 ----
        self.at("count", -0.1)
        self.play(view.animate.set_opacity(0), FadeOut(VGroup(cur, top, left, lab_h, num_h)),
                  lab_p.animate.set_opacity(0), run_time=0.5)
        self.remove(view, lab_p)
        top_n = cnt[0]
        xs = {0: 515, 1: 630}
        pitch = (BAR_X1 - 700) / 32
        for m in range(2, 35):
            xs[m] = 700 + (m - 2) * pitch
        bars, icons = VGroup(), VGroup()
        for m in range(35):
            h = BAR_H * cnt[m] / top_n
            w = 46 if m < 2 else pitch - 6
            r = Rectangle(width=u(w), height=u(h), stroke_width=0, fill_color=CYAN, fill_opacity=0.9)
            r.move_to(px(xs[m], BAR_BASE - h / 2))
            bars.add(r)
            if m >= 2:
                dv = vec(flow_dir(m))
                icons.add(Arrow(px(xs[m], BAR_BASE + 30) - dv * u(11), px(xs[m], BAR_BASE + 30) + dv * u(11), buff=0,
                                color=DIM, stroke_width=3, tip_length=u(9), max_tip_length_to_length_ratio=0.5,
                                max_stroke_width_to_length_ratio=20))
        axis = Line(px(BAR_X0 - 10, BAR_BASE), px(BAR_X1 + 12, BAR_BASE), stroke_color=DIM, stroke_width=2)
        lb0 = jp("プラナー", 32, INK).move_to(px(xs[0], BAR_BASE + 38))
        lb1 = jp("平均", 32, INK).move_to(px(xs[1], BAR_BASE + 38))
        total = mix(f"{fmt(len(pus))}個", 40, INK).move_to(px(1000, 330))
        self.play(Create(axis), LaggedStart(*[GrowFromEdge(b, DOWN) for b in bars], lag_ratio=0.03),
                  FadeIn(icons), FadeIn(lb0), FadeIn(lb1), FadeIn(total, shift=DOWN * u(8)), run_time=1.6)

        self.at("top", -0.1)
        v236 = mix(str(top_n), 40, YELLOW).next_to(bars[0], UP, buff=u(12))
        self.play(bars[0].animate.set_fill(YELLOW), lb0.animate.set_color(YELLOW), FadeIn(v236, shift=UP * u(8)),
                  run_time=0.6)
        self.at("n", -0.1)
        self.play(pop(VGroup(bars[0], v236), 1.08, 0.7), pop(total, 1.1, 0.7), run_time=0.7)

        # ---- ひげの斜めの線 ----
        self.at("whisker", -0.1)
        wbase = rgb_decoded().astype(np.float32).copy()
        wlit = np.full((H, W), 0.5, np.float32)
        wv = PhotoView(wbase, *PHOTO)
        wv.check_ignore = True
        wv.lit = wlit
        wv.refresh()
        wv.set_opacity(0)
        self.add(wv)
        wcur = PRect(wv, wx, wy, wn, wn, stroke_color=YELLOW, stroke_width=5)

        def wlit_fn(t):
            wlit[:] = 0.5 + 0.5 * t
            wv.lit = wlit
        self.play(FadeOut(VGroup(bars, icons, axis, lb0, lb1, total, v236)), wv.animate.set_opacity(1), Create(wcur),
                  run_time=0.5)
        self.play(move_view(wv, WH_WIN, (WH_C, WH_BOX, WH_BOX)), ViewAnim(wv, wlit_fn), run_time=1.3)
        wv.lit = None

        # 左の列の点が、矢印の向きに流れ込む
        self.at("diag", -0.1)
        wp = wv.px_per_pixel()
        wl = np.ones((H, W), np.float32)

        def wdark(t):
            wl[wy:wy + wn, wx:wx + wn] = 1 - 0.85 * t
            wv.lit = wl
        refs = PRect(wv, wx - 1, wy, 1, 2 * wn, stroke_color=CYAN, stroke_width=4, fill_color=CYAN, fill_opacity=0.15)
        refs.check_ignore = True
        dvv = vec(flow_dir(wm))
        guides = VGroup()
        for k0 in range(1, 2 * wn + 1):
            a = wv.to_point(wx, wy + k0)
            guides.add(DashedLine(a, a + dvv * u(wp * (wn + 0.4) / dvv[0]), color=CYAN, stroke_width=3,
                                  dash_length=u(9)).set_opacity(0.75))
        guides.check_ignore = True
        self.play(ViewAnim(wv, wdark), GrowFromEdge(refs, UP), Create(guides), run_time=0.6)
        prgb = rgb_decoded(stage="pred")
        chips = []
        for xx in range(wn):
            for yy in range(wn):
                sy = yy + (xx + 1) * ang / 32
                sq = Square(u(wp), stroke_width=0, fill_color=rgb_to_color(prgb[wy + yy, wx + xx] / 255), fill_opacity=1)
                sq.move_to(wv.to_point(wx + xx + 0.5, wy + yy + 0.5))
                st = sq.copy().scale(0.3).move_to(wv.to_point(wx - 0.5, wy + sy + 0.5))
                st.check_ignore = sq.check_ignore = True
                chips.append((st, sq))
        self.play(LaggedStart(*[ReplacementTransform(s, t) for s, t in chips], lag_ratio=0.07), run_time=1.5)
        wbase[wy:wy + wn, wx:wx + wn] = prgb[wy:wy + wn, wx:wx + wn]
        wl[wy:wy + wn, wx:wx + wn] = 1
        wv.lit = None
        wv.refresh()
        self.remove(*[t for _, t in chips])

        # 元と並べる
        orig = PhotoView(pixels("cat")[..., :3], WH_O, WH_BOX, WH_BOX, win=WH_WIN)
        orig.check_ignore = True
        ocur = PRect(orig, wx, wy, wn, wn, stroke_color=YELLOW, stroke_width=5)
        lab_pr = jp("予想", 36, CYAN).move_to(px(WH_C[0], WH_C[1] - WH_BOX / 2 - 36))
        lab_or = jp("元", 36, INK).move_to(px(WH_O[0], WH_O[1] - WH_BOX / 2 - 36))
        # 元の写真は、予想の写真の後ろから枠ごと右へ滑り出す (フェードさせない)
        orig.box = (WH_C, WH_BOX, WH_BOX)
        orig.refresh()
        ocur.sync()
        self.mobjects.insert(self.mobjects.index(wv), orig)
        self.mobjects.insert(self.mobjects.index(wv), ocur)
        self.play(FadeOut(guides), move_view(orig, WH_WIN, (WH_O, WH_BOX, WH_BOX)),
                  FadeIn(lab_pr), FadeIn(lab_or), run_time=0.9)

        self.at("fine2", -0.1)
        self.play(pop(wcur, 1.15, 0.7), pop(ocur, 1.15, 0.7), run_time=0.7)
        self.finish()
