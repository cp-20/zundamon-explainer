import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import DATA, MAIN, SIZE_COLOR, dec, fmt, picture_size, rgb_decoded  # noqa: E402
import hevc  # noqa: E402,I001  (vlib.data が tools/ を読み込みの道に入れる)
import hevctables as T  # noqa: E402
from vlib.photoview import LW, Grow, PhotoView, PRect, TrackFade, ViewAnim, cross_lines, grid64_lines, move_view  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)          # 写真の定位置 (S03 と同じ)
SHRINK = ((960, 258), 690, 459)          # 大きさの見本を下に並べるとき
SMALL = ((235, 168), 390, 260)           # 4×4 の差を集めるときの写真 (左上へよける)
TU_BOX = ((250, 245), 380, 380)          # 背景の 32×32 に寄ったときの箱
TU_MARGIN = 4
LEG_Y, LEG_K = 884, 8                    # 大きさの見本 (下端の中心 y と、1 画素の px)
COEF_C, COEF_CELL = (960, 468), 26       # 32×32 の数のマス
LAB_X = 1410                             # 右の札の左端
HEAT_C, HEAT_CELL = (1020, 580), 140     # 4×4 の差の平均のマス
BAR_W, BAR_MAX, BAR_GAP = 96, 170, 14    # 波の棒 (84 のとき BAR_MAX px)
ZERO_FILL = "#2a2f3b"
HEAT_LO = "#1e1b2c"


def original_luma():
    """元の写真 (data/cat.png) の明るさ。HEIC の colr と同じ BT.601 の全範囲：Y = 0.299R + 0.587G + 0.114B を四捨五入"""
    rgb = np.asarray(Image.open(DATA / "cat.png").convert("RGB")).astype(np.float64)
    return np.floor(0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2] + 0.5)


class LineOp(Animation):
    """PLine の不透明度を変える (s03 と同じ)"""

    def __init__(self, lines, to, **kw):
        self.lines = list(lines)
        super().__init__(VGroup(*self.lines), **kw)
        self.to = to
        self.start = [ln._op for ln in self.lines]

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        for ln, s in zip(self.lines, self.start):
            ln._op = s + (self.to - s) * a
            ln.sync()


def tu_split_nodes(tus, ctb=64):
    """波のブロック (TU) の割れ方：割れた (x, y, 大きさ) の集まり (64 から 8 まで)"""
    out = set()
    for t in tus:
        s = ctb
        while s > t["size"]:
            out.add((t["x"] // s * s, t["y"] // s * s, s))
            s //= 2
    return out


class S06(PScene):
    def construct(self):
        d = dec(MAIN)
        W, H = picture_size()
        assert (W, H) == (451, 300)
        tus = d.tus
        sizes = sorted(set(t["size"] for t in tus))
        assert sizes == [4, 8, 16, 32]                                     # 「4×4から32×32まで」

        # ---- 背景の 32×32 (0 でない数が最も少ないもの) ----
        def nonzero(t):
            lv = t.get("levels", {}).get(0)
            return 0 if lv is None else int(np.count_nonzero(lv))
        t32 = [t for t in tus if t["size"] == 32 and t["x"] + 32 <= W and t["y"] + 32 <= H]
        blur = min(t32, key=nonzero)
        lv = blur["levels"][0]
        assert lv.size == 1024 and nonzero(blur) == 6                       # 「1,024個のうち0じゃないのは6個」
        assert sorted(nonzero(t) for t in t32)[1] > 6                       # 6 個は 1 つだけ
        Yo = original_luma()
        bx, by = blur["x"], blur["y"]
        assert Yo[by:by + 32, bx:bx + 32].std() < 0.3 * Yo.std()           # 平らな所 (ぼやけた背景)
        assert bx >= 384 and by < 96                                        # 右上の背景

        # ---- 4×4 の明るさの差の平均 ----
        P = np.asarray(d.pred[0], np.float64)
        t4 = [t for t in tus if t["size"] == 4 and t["x"] + 4 <= W and t["y"] + 4 <= H]
        assert len(t4) == 788
        acc = np.zeros((4, 4))
        for t in t4:
            x, y = t["x"], t["y"]
            acc += np.abs(Yo[y:y + 4, x:x + 4] - P[y:y + 4, x:x + 4])
        heat = acc / len(t4)
        assert round(heat[0, 0], 1) == 4.3 and round(heat[3, 3], 1) == 9.0
        assert heat[0, 0] == heat.min() and heat[3, 3] == heat.max()       # 左上が最小、右下が最大
        dst = list(T.DST4[0])
        dct = list(hevc.tr_matrix(4)[0])
        assert dst == [29, 55, 74, 84] and dct == [64, 64, 64, 64]

        # ---- 写真と、予想との差の絵 ----
        photo = rgb_decoded().astype(np.float32)
        Pc = P[:H, :W]
        err = np.abs(Yo - Pc)
        k = np.clip(err / 48.0, 0, 1)[..., None]
        lo = np.array([0x14, 0x16, 0x1c], np.float32)
        hi = np.array(color_to_int_rgb(PURPLE), np.float32)
        resid_img = (lo + (hi - lo) * k).astype(np.float32)
        view = PhotoView(photo, *PHOTO)
        view.check_ignore = True
        view.set_opacity(0)

        def blend(a, b):
            def fn(t):
                view.base = a + (b - a) * t
            return ViewAnim(view, fn)

        self.at("s06_01", -0.05)
        self.add(view)
        self.play(view.animate.set_opacity(1), run_time=0.9)

        # 差を波に分ける：写真 → 予想との差
        self.at("wave", -0.1)
        self.play(blend(photo, resid_img), move_view(view, (0, 0, W, H), SHRINK), run_time=1.6)

        # 波のブロック (TU) の割れ方
        nodes = tu_split_nodes(tus)
        levels = {64: grid64_lines(view, W, H, frac=0), 32: [], 16: [], 8: [], 4: []}
        for (x, y, s) in sorted(nodes):
            if x < W and y < H:
                levels[s // 2] += cross_lines(view, x, y, s, W, H, SIZE_COLOR[s // 2], LW[s // 2])
        all_lines = [ln for ls in levels.values() for ln in ls]
        self.add(*all_lines)
        self.at("size", -0.1)
        for s in (64, 32, 16, 8, 4):
            self.play(*[Grow(ln) for ln in levels[s]], run_time=0.45, rate_func=rate_functions.ease_out_cubic)

        # 4・8・16・32 の見本 (同じ縮尺)
        self.at("range", -0.1)
        leg = VGroup()
        for s in (4, 8, 16, 32):
            sq = Square(u(s * LEG_K), stroke_color=SIZE_COLOR[s], stroke_width=4, fill_color=SIZE_COLOR[s], fill_opacity=0.18)
            lab = mix(f"{s}×{s}", 32, SIZE_COLOR[s]).next_to(sq, RIGHT, buff=u(12)).align_to(sq, DOWN)
            leg.add(VGroup(sq, lab))
        leg.arrange(RIGHT, buff=u(44), aligned_edge=DOWN)
        leg.move_to(px(960, 0), coor_mask=np.array([1, 0, 0])).align_to(px(0, LEG_Y), DOWN)
        assert leg.width / u(1) <= 1040
        self.play(LaggedStart(*[AnimationGroup(GrowFromCenter(g[0]), FadeIn(g[1], shift=RIGHT * u(8))) for g in leg],
                              lag_ratio=0.3), run_time=1.6)

        # ---- 背景の 32×32 へ寄る ----
        self.at("blur", -0.1)
        tu_rect = PRect(view, bx, by, 32, 32, stroke_color=SIZE_COLOR[32], stroke_width=6)
        self.play(LineOp(all_lines, 0), FadeOut(leg), blend(resid_img, photo), Create(tu_rect), run_time=0.9)
        self.remove(*all_lines)
        lit = np.ones((H, W), np.float32)

        def dim_out(t):
            lit[:] = 1 - 0.68 * t
            lit[by:by + 32, bx:bx + 32] = 1
            view.lit = lit
        win = (bx - TU_MARGIN, by - TU_MARGIN, bx + 32 + TU_MARGIN, by + 32 + TU_MARGIN)
        self.play(move_view(view, win, TU_BOX), ViewAnim(view, dim_out), run_time=1.6)

        # 32×32 の数のマス
        self.at("coef", -0.1)
        g0 = px(COEF_C[0] - 16 * COEF_CELL, COEF_C[1] - 16 * COEF_CELL)
        cells = VGroup()
        for j in range(32):
            for i in range(32):
                c = Square(u(COEF_CELL - 4), stroke_width=0, fill_color=ZERO_FILL, fill_opacity=1)
                c.move_to(g0 + np.array([u((i + 0.5) * COEF_CELL), -u((j + 0.5) * COEF_CELL), 0]))
                cells.add(c)
        frame = Square(u(32 * COEF_CELL + 8), stroke_color=SIZE_COLOR[32], stroke_width=4).move_to(px(*COEF_C))
        n_all = mix(f"{fmt(lv.size)}個の数", 40, INK)
        n_all.move_to(px(LAB_X, 150), aligned_edge=LEFT)
        self.play(TransformFromCopy(tu_rect, frame), run_time=0.8)
        self.add(frame)
        self.play(LaggedStart(*[FadeIn(cells[j * 32:(j + 1) * 32]) for j in range(32)], lag_ratio=0.12),
                  FadeIn(n_all, shift=LEFT * u(10)), run_time=1.2)

        self.at("few", -0.1)
        nz = [(int(j), int(i)) for j, i in np.argwhere(lv != 0)]
        lit_cells = VGroup(*[cells[j * 32 + i] for j, i in nz])
        n_nz = mix(f"0でない数 {len(nz)}個", 40, YELLOW).move_to(px(LAB_X, 240), aligned_edge=LEFT)
        self.play(lit_cells.animate.set_fill(YELLOW), FadeIn(n_nz, shift=LEFT * u(10)), run_time=0.6)
        self.play(pop(lit_cells, 1.5, 0.6), run_time=0.6)

        # 6 個だけで、この広い所が書ける
        self.at("only", -0.05)
        flies = VGroup(*[c.copy() for c in lit_cells])
        self.add(flies)
        tu_c = tu_rect.get_center()
        self.play(LaggedStart(*[f.animate(path_arc=0.7).move_to(tu_c).scale(0.6).set_opacity(0) for f in flies],
                              lag_ratio=0.12), run_time=1.2)
        self.remove(flies)
        self.play(Indicate(tu_rect, color=YELLOW, scale_factor=1.06), run_time=0.8)

        # ---- 4×4 の明るさ ----
        mask4 = np.zeros((H, W), bool)
        for t in t4:
            mask4[t["y"]:t["y"] + 4, t["x"]:t["x"] + 4] = True
        lit4 = np.where(mask4, 1.0, 0.25).astype(np.float32)
        lit0 = lit.copy()

        def to4(t):
            lit[:] = lit0 + (lit4 - lit0) * t
            view.lit = lit
        self.at("s06_04", -0.05)
        self.play(FadeOut(VGroup(cells, frame, n_all, n_nz)), TrackFade(tu_rect, 1, 0),
                  move_view(view, (0, 0, W, H), PHOTO), ViewAnim(view, to4), run_time=1.5)

        # ---- 差を場所ごとに平均する ----
        hc = np.array(px(*HEAT_C))
        hs = 4 * HEAT_CELL

        def cell_pt(r, c):
            return px(HEAT_C[0] + (c - 1.5) * HEAT_CELL, HEAT_C[1] + (r - 1.5) * HEAT_CELL)
        vmax = heat.max()
        hcells, hnums = VGroup(), VGroup()
        for r in range(4):
            for c in range(4):
                v = heat[r, c]
                col = interpolate_color(ManimColor(HEAT_LO), ManimColor(PURPLE), v / vmax)
                sq = Square(u(HEAT_CELL), stroke_color=BG, stroke_width=3, fill_color=HEAT_LO, fill_opacity=1)
                sq.target_col = col
                sq.move_to(cell_pt(r, c))
                hcells.add(sq)
                hnums.add(mono(f"{v:.1f}", 44, INK).move_to(sq))
        head = jp("予想との差の平均", 36, PURPLE).move_to(px(HEAT_C[0], 236))

        self.at("other", -0.05)
        self.play(move_view(view, (0, 0, W, H), SMALL),
                  LaggedStart(*[FadeIn(c, scale=0.7) for c in hcells], lag_ratio=0.04), run_time=1.4)

        self.at("err", -0.1)
        side = view.px_per_pixel() * 4
        order = sorted(t4, key=lambda t: (t["y"] + t["x"]))
        flyers = []
        for t in order:
            e = float(np.abs(Yo[t["y"]:t["y"] + 4, t["x"]:t["x"] + 4] - Pc[t["y"]:t["y"] + 4, t["x"]:t["x"] + 4]).mean())
            sq = Square(u(side), stroke_color=SIZE_COLOR[4], stroke_width=1.2, fill_color=PURPLE,
                        fill_opacity=min(0.4, e / 30))
            sq.move_to(view.to_point(t["x"] + 2, t["y"] + 2))
            sq.check_ignore = True
            flyers.append(sq)
        self.add(*flyers)
        fly = LaggedStart(*[sq.animate(path_arc=-0.5).move_to(hc).scale(hs / side).set_opacity(0) for sq in flyers],
                          lag_ratio=0.004, run_time=3.0)
        build = AnimationGroup(*[c.animate.set_fill(c.target_col) for c in hcells], run_time=3.0, rate_func=lambda a: rate_functions.smooth(max(0, (a - 0.35) / 0.65)))
        self.play(fly, build, FadeIn(head, shift=DOWN * u(8)), run_time=3.0)
        self.remove(*flyers)
        self.play(LaggedStart(*[FadeIn(n, scale=0.8) for n in hnums], lag_ratio=0.05), run_time=1.0)

        # 予想に使った上と左の点
        STRIP = 26
        top0 = HEAT_C[1] - 2 * HEAT_CELL
        left0 = HEAT_C[0] - 2 * HEAT_CELL
        refs = VGroup()
        for i in range(4):
            refs.add(Rectangle(width=u(HEAT_CELL - 6), height=u(STRIP), stroke_width=0, fill_color=CYAN, fill_opacity=1)
                     .move_to(px(HEAT_C[0] + (i - 1.5) * HEAT_CELL, top0 - 8 - STRIP / 2)))
            refs.add(Rectangle(width=u(STRIP), height=u(HEAT_CELL - 6), stroke_width=0, fill_color=CYAN, fill_opacity=1)
                     .move_to(px(left0 - 8 - STRIP / 2, HEAT_C[1] + (i - 1.5) * HEAT_CELL)))
        refs.add(Square(u(STRIP), stroke_width=0, fill_color=CYAN, fill_opacity=1)
                 .move_to(px(left0 - 8 - STRIP / 2, top0 - 8 - STRIP / 2)))

        def ring(r, c):
            return Square(u(HEAT_CELL - 16), stroke_color=YELLOW, stroke_width=6).move_to(cell_pt(r, c))
        self.at("near", -0.1)
        self.play(FadeOut(head), LaggedStart(*[GrowFromEdge(m, DOWN if m.width > m.height else RIGHT) for m in refs],
                                             lag_ratio=0.08), run_time=1.0)
        near = ring(0, 0)
        self.play(Create(near), pop(hnums[0], 1.2, 0.7), run_time=0.7)
        self.at("far", -0.1)
        far = ring(3, 3)
        self.play(Create(far), pop(hnums[15], 1.2, 0.7), run_time=0.7)

        # 近い所ほど当たる：左上から右下へ
        self.at("why", -0.05)
        diag = [[k for k in range(16) if k // 4 + k % 4 == s] for s in range(7)]
        self.play(FadeOut(near), FadeOut(far), run_time=0.4)
        self.play(LaggedStart(*[AnimationGroup(*[VGroup(hcells[k], hnums[k]).animate(rate_func=there_and_back).scale(1.08)
                                                 for k in ks]) for ks in diag], lag_ratio=0.25), run_time=2.2)

        # ---- 波の形 ----
        base_y = top0 - BAR_GAP
        K = BAR_MAX / max(dst)
        col_x = [HEAT_C[0] + (i - 1.5) * HEAT_CELL for i in range(4)]

        def vbar(x, v, **st):
            r = Rectangle(width=u(BAR_W), height=u(v * K), **st)
            return r.move_to(px(x, base_y - v * K / 2))
        flat = VGroup(*[vbar(x, v, stroke_width=0, fill_color=DIM, fill_opacity=0.85) for x, v in zip(col_x, dct)])
        jl = jp("JPEGの波", 36, DIM).move_to(px(LAB_X - 70, base_y - dct[0] * K), aligned_edge=LEFT)
        self.at("sine", -0.1)
        self.play(FadeOut(refs), view.animate.set_opacity(0), run_time=0.6)
        self.remove(view)
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in flat], lag_ratio=0.1), FadeIn(jl, shift=LEFT * u(8)),
                  run_time=0.9)

        # 0 に近い所から、だんだん大きく
        bars = VGroup(*[vbar(x, v, stroke_width=0, fill_color=YELLOW, fill_opacity=1) for x, v in zip(col_x, dst)])
        vals = VGroup(*[mono(str(v), 34, BG).move_to(b.get_bottom() + UP * u(26)) for v, b in zip(dst, bars)])
        ghost = VGroup(*[vbar(x, v, stroke_color=DIM, stroke_width=3, fill_opacity=0) for x, v in zip(col_x, dct)])
        self.at("start", -0.1)
        self.add(ghost)
        self.play(FadeOut(flat), run_time=0.4)
        self.play(LaggedStart(*[AnimationGroup(GrowFromEdge(b, DOWN), FadeIn(t)) for b, t in zip(bars, vals)],
                              lag_ratio=0.45), run_time=2.0)

        # 縦の向きにも同じ波 (差のマスの形と重ねる)
        right_x = left0 - BAR_GAP
        row_y = [HEAT_C[1] + (i - 1.5) * HEAT_CELL for i in range(4)]
        rbars = VGroup(*[Rectangle(width=u(v * K), height=u(BAR_W), stroke_width=0, fill_color=YELLOW, fill_opacity=1)
                         .move_to(px(right_x - v * K / 2, y)) for v, y in zip(dst, row_y)])
        rvals = VGroup(*[mono(str(v), 34, BG).move_to(b.get_right() + LEFT * u(32)) for v, b in zip(dst, rbars)])
        self.play(*[TransformFromCopy(b, rb, path_arc=0.6) for b, rb in zip(bars, rbars)],
                  *[TransformFromCopy(t, rt, path_arc=0.6) for t, rt in zip(vals, rvals)], run_time=1.4)

        self.at("dst", -0.1)
        name = jp("離散サイン変換", 48, YELLOW).move_to(px(LAB_X - 70, 72), aligned_edge=LEFT)
        self.play(FadeIn(name, shift=DOWN * u(8)), run_time=0.7)

        # 差の形に合わせた波
        self.at("match", -0.05)
        self.play(pop(VGroup(bars, vals), 1.04, 0.8), pop(VGroup(rbars, rvals), 1.04, 0.8),
                  LaggedStart(*[AnimationGroup(*[VGroup(hcells[k], hnums[k]).animate(rate_func=there_and_back).scale(1.05) for k in ks])
                                for ks in diag], lag_ratio=0.2), run_time=1.6)

        # 終わり：空に
        self.at("match", 2.3)
        self.play(FadeOut(VGroup(hcells, hnums, bars, vals, rbars, rvals, ghost, jl, name)), run_time=0.8)
        self.finish()
