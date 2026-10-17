import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import file_bytes, fmt, info, pixels  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

BOX_W, BOX_H = 468, 684            # 画像を置く箱（px）
IMG_C = (960, 500)
WIN = (369, 403, 382, 422)         # 目のあたりの 13×19 画素（すべて不透明）
CELL = 36                          # 格子の1マス（px）。13×36=468, 19×36=684
OUT_W, OUT_H = BOX_W * 2, BOX_H * 2

R_COL, G_COL, A_COL = "#ef5a5a", "#5fc96b", "#d5d9e2"
CH_COL = [R_COL, G_COL, BLUE, A_COL]


class ZoomImg(ImageMobject):
    """元画像のうち窓 (L,T,R,B)（画素座標・小数可）だけを箱いっぱいに映す画像"""

    def __init__(self, rgba):
        self.src = Image.fromarray(rgba, "RGBA")
        self.full = (0, 0, rgba.shape[1], rgba.shape[0])
        super().__init__(self.render(self.full))
        self.height = u(BOX_H)
        self.move_to(px(*IMG_C))

    def render(self, win):
        L, T, R, B = win
        factor = OUT_W / (R - L)
        rs = Image.NEAREST if factor >= 3 else Image.BILINEAR
        out = self.src.resize((OUT_W, OUT_H), rs, box=(L, T, R, B))
        rgb = checker_composite(np.asarray(out), 28)
        return np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])

    def show(self, win):
        self.pixel_array = self.render(win)
        self.orig_alpha_pixel_array = self.pixel_array[:, :, 3].copy()


class ZoomTo(Animation):
    """窓を幾何的に（拡大率が一定の速さで）変える"""

    def __init__(self, mob, w0, w1, **kw):
        kw.setdefault("rate_func", smooth)
        super().__init__(mob, **kw)
        self.w0, self.w1 = np.array(w0, float), np.array(w1, float)
        self.r = (self.w1[2] - self.w1[0]) / (self.w0[2] - self.w0[0])

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        g = a if abs(self.r - 1) < 1e-9 else (1 - self.r ** a) / (1 - self.r)
        self.mobject.show(tuple(self.w0 + (self.w1 - self.w0) * g))


def sq(color, size, **kw):
    return Square(u(size), stroke_width=0, fill_color=color, fill_opacity=1, **kw)


class S01(PScene):
    def construct(self):
        P = pixels("zundamon")
        z = info("zundamon")
        H, W = P.shape[:2]
        fsize, pbytes = z["file_size"], z["pixel_bytes"]
        assert (W, H) == (z["width"], z["height"]) == (1082, 1594) and fsize == 333074
        assert pbytes == W * H * 4 == 6898832
        assert round(fsize / 1000) == 333 and round(pbytes / 1e6, 1) == 6.9
        ratio = round(pbytes / fsize)
        assert pbytes / fsize > 20 and ratio == 21

        L, T, R, B = WIN
        cw, ch = R - L, B - T
        assert P[T:B, L:R, 3].min() == 255 and (cw * CELL, ch * CELL) == (BOX_W, BOX_H)

        # ---- S01_01：ファイルの札 → 画像が開く ----
        CARD_C = (960, 500)
        card_body = RoundedRectangle(corner_radius=u(16), width=u(600), height=u(110), stroke_width=3,
                                     stroke_color=DIM, fill_color="#262b36", fill_opacity=1)
        icon = VGroup(RoundedRectangle(corner_radius=u(8), width=u(78), height=u(78), stroke_width=0,
                                       fill_color=CYAN, fill_opacity=1),
                      jp("PNG", 40, BG))
        icon[1].move_to(icon[0])
        fname = jp("zundamon.png", 44)
        icon.move_to(card_body.get_left() + RIGHT * u(66))
        fname.next_to(icon, RIGHT, buff=u(28))
        card = VGroup(card_body, icon, fname).move_to(px(*CARD_C))
        card_scale0 = 1.0

        self.at("s01_01")
        self.play(FadeIn(card, shift=UP * u(24), scale=0.9), run_time=1.0)
        self.play(pop(card, 1.06, run_time=0.8))

        # 札から画像が開く。札は右の方へ小さく退く
        CARD_SMALL = (1345, 330)
        img = ZoomImg(P)
        opening = img.copy().scale(0.12).move_to(px(*CARD_C))
        opening.check_ignore = True
        self.at("img", -0.1)
        self.add(opening)
        self.play(Transform(opening, img, path_arc=0), card.animate.scale(0.55).move_to(px(*CARD_SMALL)),
                  run_time=1.1)
        self.remove(opening)
        self.add(img)

        # ---- S01_02：ゆっくり少し寄る（画素はまだ見せない） ----
        PUSH_W = 757.0
        PUSH = (121.0, 142.0, 121.0 + PUSH_W, 142.0 + PUSH_W * BOX_H / BOX_W)
        self.at("what", -0.2)
        self.play(ZoomTo(img, img.full, PUSH, run_time=self.until("color", -0.5), rate_func=smooth))

        # ---- S01_03：{color} 画像から代表色を取り出す ----
        pl, pt, pr_, pb_ = PUSH
        vis = P[int(pt):int(pb_), int(pl):int(pr_)]
        q = (vis[..., :3] // 48).astype(int)
        keys = q[..., 0] * 100 + q[..., 1] * 10 + q[..., 2]
        vals_, cnts = np.unique(np.where(vis[..., 3] == 255, keys, -1), return_counts=True)
        order = [int(k) for k in vals_[np.argsort(-cnts)] if k >= 0]
        picks, used = [], []
        for k in order:
            ys, xs_ = np.nonzero(keys == k)
            j = len(ys) // 2
            sy, sx = int(pt) + int(ys[j]), int(pl) + int(xs_[j])
            if vis[sy - int(pt), sx - int(pl), 3] != 255:
                continue
            rgb = P[sy, sx, :3].astype(int)
            if all(np.abs(rgb - c).sum() > 90 for c in used):
                used.append(rgb)
                picks.append((sx, sy))
            if len(picks) == 5:
                break
        scr = lambda sx, sy: px(IMG_C[0] + (sx - pl) / PUSH_W * BOX_W - BOX_W / 2,
                                IMG_C[1] + (sy - pt) / (pb_ - pt) * BOX_H - BOX_H / 2)
        dots = VGroup(*[Circle(u(34), stroke_width=3, stroke_color=INK, fill_color=rgb_to_color(P[sy, sx, :3] / 255),
                               fill_opacity=1) for sx, sy in picks])
        dot_home = [px(1345, 450 + k * 88) for k in range(len(picks))]
        for d, (sx, sy) in zip(dots, picks):
            d.scale(0.2).move_to(scr(sx, sy))
        self.at("color", -0.1)
        self.add(dots)
        self.play(LaggedStart(*[d.animate(path_arc=-PI / 4).scale(5).move_to(h) for d, h in zip(dots, dot_home)],
                              lag_ratio=0.12), run_time=1.0)

        self.at("S01_04", 0.5)  # M「半分正解」
        self.play(pop(dots, 1.12, run_time=0.7))

        # ---- {px}：色の丸は画像に戻り、目のあたりへズーム。ここで初めて画素 ----
        self.at("px", -0.1)
        self.play(*[d.animate(run_time=0.7).scale(0.2).move_to(scr(sx, sy)).set_opacity(0)
                    for d, (sx, sy) in zip(dots, picks)],
                  FadeOut(card, shift=RIGHT * u(10), run_time=0.5),
                  ZoomTo(img, PUSH, WIN, run_time=2.1))
        self.remove(dots)

        # 実際の画素の格子（窓と完全に同じ見た目）に置き換え、すき間を出す
        grid = VGroup(*[sq(rgb_to_color(P[T + j, L + i, :3] / 255), CELL)
                        .move_to(px(IMG_C[0] + (i - (cw - 1) / 2) * CELL, IMG_C[1] + (j - (ch - 1) / 2) * CELL))
                        for j in range(ch) for i in range(cw)])
        self.add(grid)
        self.remove(img)
        self.play(grid.animate.set_stroke(BG, 2, 1), run_time=0.5)

        # ---- S01_05：1画素を持ち上げて、4つの数字（バイト）に割る ----
        # 中間の明るさ（縁の画素）のものを選ぶ
        lum = [(abs(float(P[T + j, L + i, :3].mean()) - 150), j, i) for j in range(ch) for i in range(cw)
               if len(set(int(v) for v in P[T + j, L + i, :3])) == 3]
        _, pj, pi = min(lum)
        pr, pg, pb, pa = [int(v) for v in P[T + pj, L + pi]]
        vals = [pr, pg, pb, pa]
        src = grid[pj * cw + pi]
        self.at("one", -0.05)
        swatch = src.copy()
        swatch.set_stroke(INK, 3, 1)
        swatch.check_ignore = True  # 格子から持ち上げる一時的な写し
        self.add(swatch)
        sw_lbl = mix("この1画素", 32).move_to(px(610, 640))
        self.play(swatch.animate(path_arc=PI / 3).scale(150 / CELL).move_to(px(610, 520)),
                  grid.animate.set_opacity(0.0), FadeIn(sw_lbl, shift=UP * u(10)),
                  run_time=1.0)
        self.remove(grid)

        BASE, BAR_W = 740, 90
        bx = [790 + k * 130 for k in range(4)]
        bars = VGroup(*[Rectangle(width=u(BAR_W), height=u(max(v, 6) / 255 * 380), stroke_width=0,
                                  fill_color=CH_COL[k], fill_opacity=1)
                        .move_to(px(bx[k], BASE), aligned_edge=DOWN) for k, v in enumerate(vals)])
        letters = VGroup(*[jp("RGBA"[k], 36, CH_COL[k]).move_to(px(bx[k], BASE + 34)) for k in range(4)])
        vlabels = VGroup(*[mix(str(v), 36, INK).move_to(bars[k].get_top() + UP * u(26)) for k, v in enumerate(vals)])
        bytes_lbl = VGroup(*[mix("1バイト", 30, DIM).move_to(px(bx[k], BASE + 80)) for k in range(4)])
        self.at("rgba", -0.15)
        splits = [swatch.copy().set_stroke(width=0) for _ in range(4)]
        for s in splits:
            s.check_ignore = True
            self.add(s)
        self.play(*[Transform(splits[k], bars[k]) for k in range(4)],
                  LaggedStart(*[FadeIn(l, shift=UP * u(10)) for l in letters], lag_ratio=0.15),
                  run_time=1.0)
        self.remove(*splits)
        self.add(bars)
        self.play(LaggedStart(*[FadeIn(v, shift=UP * u(8)) for v in vlabels], lag_ratio=0.2), run_time=0.9)
        self.at("S01_05", 5.5)
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(8)) for b in bytes_lbl], lag_ratio=0.2), run_time=1.0)

        self.at("S01_06", 0.15)
        ul4 = underline(bytes_lbl, YELLOW)
        self.play(Create(ul4), run_time=0.5)

        # ---- S01_04：画像へ戻って、幅と高さを数える ----
        self.at("s01_04", -0.45)
        # 4本の棒は「4バイト／画素」に畳んで右下へ
        cmp_sq = VGroup(*[sq(CH_COL[k], 44) for k in range(4)]).arrange(RIGHT, buff=u(6)).move_to(px(1345, 640))
        for k, s in enumerate(cmp_sq):
            s.add(jp("RGBA"[k], 28, BG).move_to(s))
        cmp_lbl = mix("4バイト／画素", 34, YELLOW).move_to(px(1345, 720))
        grid2 = VGroup(*[g.copy() for g in grid]).set_opacity(0)
        grid2.check_ignore = True
        self.add(grid2)
        self.play(*[Transform(bars[k], cmp_sq[k]) for k in range(4)],
                  FadeOut(ul4), FadeOut(letters), FadeOut(vlabels), FadeOut(bytes_lbl), FadeOut(swatch), FadeOut(sw_lbl),
                  grid2.animate.set_opacity(1.0), FadeIn(cmp_lbl, shift=UP * u(10)), run_time=0.6)
        self.remove(grid2)
        img = ZoomImg(P)
        img.show(WIN)
        self.add(img)

        x0, x1 = IMG_C[0] - BOX_W / 2, IMG_C[0] + BOX_W / 2
        y0, y1 = IMG_C[1] - BOX_H / 2, IMG_C[1] + BOX_H / 2
        wline = DoubleArrow(px(x0, y0 - 28), px(x1, y0 - 28), buff=0, stroke_width=3, color=CYAN,
                            tip_length=u(14), max_tip_length_to_length_ratio=0.2)
        wlab = mix(fmt(W).replace(",", ""), 60, INK).move_to(px(960, y0 - 70))
        hline = DoubleArrow(px(x0 - 32, y0), px(x0 - 32, y1), buff=0, stroke_width=3, color=CYAN,
                            tip_length=u(14), max_tip_length_to_length_ratio=0.2)
        hlab = mix(str(H), 60, INK).move_to(px(x0 - 32 - 100, IMG_C[1]))
        self.at("w", -0.1)
        self.play(ZoomTo(img, WIN, img.full, run_time=1.9),
                  AnimationGroup(Create(wline), FadeIn(wlab, shift=DOWN * u(8)), run_time=0.8),
                  Succession(Wait(1.75), AnimationGroup(Create(hline), FadeIn(hlab, shift=RIGHT * u(8)), run_time=0.7)))

        # ---- S01_05：掛け算 ----
        parts = VGroup(mix("1082", 60), mix("×", 60, DIM), mix("1594", 60), mix("×", 60, DIM), mix("4", 60),
                       mix("=", 60, DIM)).arrange(RIGHT, buff=u(22))
        ans = mix(f"{fmt(pbytes)} バイト", 66, YELLOW)
        formula = VGroup(parts, ans).arrange(RIGHT, buff=u(30), aligned_edge=DOWN).move_to(px(960, 330))
        assert wlab.text == "1082" and hlab.text == "1594"
        self.at("s01_05", 0.05)
        self.se("whoosh")
        four = mix("4", 34, YELLOW).move_to(cmp_lbl.get_left() + RIGHT * u(10))  # 「4バイト」の4をそのまま飛ばす
        self.add(four)
        self.play(wlab.animate.move_to(parts[0]), hlab.animate.move_to(parts[2]),
                  four.animate.scale(60 / 34).move_to(parts[4]),
                  FadeOut(wline), FadeOut(hline), FadeOut(img, scale=0.9), FadeOut(cmp_sq), FadeOut(cmp_lbl),
                  FadeOut(bars),
                  *[FadeIn(parts[k], scale=0.6) for k in (1, 3, 5)], run_time=0.85)
        self.at("total", -0.05)
        self.se("pop")
        self.play(FadeIn(ans, scale=1.5), run_time=0.5)
        approx = mix("だいたい 6.9 MB", 48, DIM).move_to(px(960, 470))
        assert f"{pbytes / 1e6:.1f}" == "6.9"
        self.play(FadeIn(approx, shift=UP * u(8)), run_time=0.6)

        # ---- S01_10：最初のファイルの札が戻ってきて、本当のファイルの大きさを見せる ----
        card.scale(1 / 0.55).move_to(px(960, 640))
        small_lbl = mix(f"{fmt(fsize)} バイト", 45, CYAN)
        small_lbl.move_to(px(960, 730))
        self.at("file", -0.1)
        self.play(FadeIn(card, shift=UP * u(30), scale=0.85), run_time=0.7)
        self.at("size", -0.1)
        self.play(card_body.animate.stretch_to_fit_height(u(190)).shift(DOWN * u(40)),
                  FadeIn(small_lbl, shift=UP * u(10)), run_time=0.6)
        self.play(pop(small_lbl, 1.12, run_time=0.5))

        # ---- S01_11：式の答えが縦棒に、札の数字が小さい棒に ----
        self.at("bars", -0.05)
        BL, TALL_H = 860, 660
        tiny_h = TALL_H * fsize / pbytes
        bar_big = Rectangle(width=u(120), height=u(TALL_H), stroke_width=0, fill_color=CORAL, fill_opacity=1)
        bar_big.move_to(px(700, BL), aligned_edge=DOWN)
        bar_small = Rectangle(width=u(120), height=u(tiny_h), stroke_width=0, fill_color=CYAN, fill_opacity=1)
        bar_small.move_to(px(1000, BL), aligned_edge=DOWN)
        big_lbl = mix(f"{fmt(pbytes)} バイト", 44, CORAL)
        big_lbl.move_to(px(770, BL - TALL_H + 30), aligned_edge=LEFT)
        self.play(FadeOut(parts[0:6]), FadeOut(wlab), FadeOut(hlab), FadeOut(four), FadeOut(approx),
                  FadeOut(card), run_time=0.5)
        # 答えの数字はそのまま大きい棒のラベルへ、札の数字は小さい棒のラベルへ。棒は下から伸びる
        ans.text = big_lbl.text
        self.play(Transform(ans, big_lbl), GrowFromEdge(bar_big, DOWN),
                  small_lbl.animate.move_to(px(1000, BL - tiny_h - 80)),
                  GrowFromEdge(bar_small, DOWN), run_time=1.1)

        ratio_lbl = mix(f"約 1/{ratio}", 72, YELLOW)
        ratio_lbl.move_to(px(1290, 560))
        self.at("ratio", -0.1)
        self.se("surprise")
        self.play(FadeIn(ratio_lbl, scale=1.4), run_time=0.6)
        self.at("gone", -0.1)
        self.play(Shake(VGroup(bar_small, small_lbl), 10, run_time=0.7), run_time=0.7)

        # ---- S01_08：ロスレス（開けば元に戻る）----
        self.at("s01_08", 0.1)
        chip = Rectangle(width=u(120), height=u(tiny_h), stroke_width=0, fill_color=CYAN, fill_opacity=1)
        chip.move_to(px(900, 130))
        chip_lbl = mix(f"{fmt(fsize)} バイト", 40, CYAN).move_to(px(1150, 130))
        self.play(FadeOut(ans), FadeOut(bar_big), FadeOut(ratio_lbl),
                  Transform(bar_small, chip), Transform(small_lbl, chip_lbl), run_time=1.0)

        orig = ZoomImg(P)
        orig.show(orig.full)
        orig.height = u(520)
        orig.move_to(px(700, 520))
        o_lbl = jp("元の画像", 32, DIM).move_to(px(700, 520 + 260 + 34))
        self.play(FadeIn(orig, scale=0.9), FadeIn(o_lbl), run_time=0.7)

        self.at("lossless", -0.2)
        self.se("shine")
        rest = ZoomImg(P)
        rest.show(rest.full)
        rest.height = u(520)
        rest.move_to(px(1220, 520))
        r_lbl = jp("開いた画像", 32, CYAN).move_to(px(1220, 520 + 260 + 34))
        rest_start = rest.copy().scale(0.12).move_to(px(900, 130))
        self.add(rest_start)
        self.play(Transform(rest_start, rest, path_arc=-PI / 3), run_time=1.2)
        self.remove(rest_start)
        self.add(rest)
        self.play(FadeIn(r_lbl), run_time=0.4)
        eq = mix("=", 96, YELLOW).move_to(px(960, 520))
        diff = (np.asarray(Image.open(Path(__file__).resolve().parent.parent / "data" / "zundamon.png").convert("RGBA"))
                != P).any(axis=2).sum()
        assert diff == 0
        same = mix("ちがう画素 0 こ", 40, YELLOW).move_to(px(960, 872))
        self.play(FadeIn(eq, scale=1.6), FadeIn(same, shift=UP * u(10)), run_time=0.6)
        self.play(pop(eq, 1.25), run_time=0.5)
        self.at("S01_14", 0.3)
        self.play(pop(same, 1.3), run_time=0.7)

        # ---- S01_09：バイトの列をのぞく → タイトル ----
        self.at("peek", -0.35)
        head = list(file_bytes("zundamon")[:16])
        n = 16
        bw, gap = 58, 6
        xs = [960 + (i - (n - 1) / 2) * (bw + gap) for i in range(n)]
        byte_cells = VGroup(*[VGroup(sq("#262b36", bw), mono(f"{v:02X}", 32, INK)) for v in head])
        for i, bc in enumerate(byte_cells):
            bc[1].move_to(bc[0])
            bc.move_to(px(xs[i], 520))
        byte_cells.set_opacity(1)
        byte_note = mix("PNGファイルの先頭16バイト", 40, DIM).move_to(px(960, 640))
        gone = Group(orig, rest, o_lbl, r_lbl, eq, same)
        self.play(FadeOut(gone, scale=0.9), Transform(small_lbl, small_lbl.copy().move_to(px(960, 380))),
                  Transform(bar_small, bar_small.copy().move_to(px(960, 440))), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(12)) for b in byte_cells], lag_ratio=0.06),
                  FadeOut(bar_small), FadeIn(byte_note), run_time=1.4)

        self.at("title", -0.55)
        title = jp("PNGの中身をのぞく", 72).move_to(px(960, 300))
        shrink = VGroup(byte_cells, byte_note, small_lbl)
        self.play(FadeOut(shrink, scale=0.8), run_time=0.5)
        self.at("title", -0.05)
        self.play(FadeIn(title, shift=UP * u(12)), run_time=0.9)
        self.finish()
