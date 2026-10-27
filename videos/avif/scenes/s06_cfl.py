import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import CFL_BLOCK, cfl_example, cfl_stats, dec, picture_size, planes, rgb_decoded  # noqa: E402
from vlib.photoview import PhotoView, PRect, TrackFade, ViewAnim  # noqa: E402
from vlib.ui import CellGrid, cb_color, chroma_image, add_row, compare_card, gray, text_color_on  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)            # 写真の定位置 (S03〜S09 の始まりと終わり)
PANEL_X, PANEL_Y, PANEL_W = (330, 960, 1590), 263, 576      # 3 枚の板 (上の帯いっぱい)
CTX_C, CTX_W = ((240, 214), (1680, 214)), 400              # 例のときに左上・右上に残す板 (明るさ・青み)
GRID_C, CELL = (720, 480), 50              # 主役のマス (8×8 で 400px)
ZOOM_X, ZOOM_Y, ZOOM_W = (620, 960, 1300), 660, 300   # 目のあたりの拡大 (3 枚)
EYE = (130, 68, 86, 86)                     # 拡大する範囲 (明るさの座標 x, y, w, h)
RULE_X, RULE_Y = 1000, (350, 425, 500, 575)
REAL_C = (1220, 480)
TRIO_X, TRIO_Y, TRIO_CELL = (600, 960, 1320), 470, 38
NL_Y, NL_X0, NL_X1 = 800, 580, 1340        # 掛ける数の目盛り
MINUS = "−"


def signed(v):
    v = int(round(v))
    return f"+{v}" if v > 0 else (f"{MINUS}{-v}" if v < 0 else "0")


def gray_rgb(a):
    a = np.clip(np.asarray(a), 0, 255).astype(np.uint8)
    return np.dstack([a, a, a])


def upscale2(a, W, H):
    """Cb・Cr (半分の細かさ) を、写真と同じ大きさの画像に (ドットのまま 2 倍)"""
    return np.repeat(np.repeat(a, 2, axis=0), 2, axis=1)[:H, :W]


class S06(PScene):
    def construct(self):
        W, H = picture_size()
        assert (W, H) == (451, 300)
        Y, U, V = planes()
        ex = cfl_example()
        cx, cy = CFL_BLOCK
        lx, ly = ex["luma_xy"]
        assert (lx, ly) == (2 * cx, 2 * cy) == (192, 112)
        avg = ex["avg"]
        au, dcu = ex["u"]["alpha"], ex["u"]["dc"]
        av_, dcv = ex["v"]["alpha"], ex["v"]["dc"]
        assert round(avg) == 63 and au == -2 and dcu == 105 and av_ == 1          # 「平均 63」「−0.25」「105」「+1/8」
        assert f"{ex['u']['err_dc']:.1f}" == "11.5" and f"{ex['u']['err_cfl']:.1f}" == "4.6"
        n_chroma, n_cfl = cfl_stats()
        assert (n_chroma, n_cfl) == (556, 129) and 0.2 < n_cfl / n_chroma < 0.25    # 「4つに1つ近く」
        bump = ex["bump"]
        scaled = ex["u"]["scaled"]
        pred = ex["u"]["pred"]
        src = ex["u"]["src"]
        assert np.array_equal(pred, dcu + scaled)
        # 表示の丸めた数どうしでも、明暗のパターン × −0.25 と足した数のずれは 1 まで
        assert np.abs(np.round(bump) * au / 8 - scaled).max() <= 1.0

        # ---- 写真 (S05 の終わり) ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)

        # ---- Y・Cb・Cr の 3 枚に分ける ----
        imgs = {
            "y": gray_rgb(Y),
            "cb": upscale2(chroma_image(U, "cb"), W, H),
            "cr": upscale2(chroma_image(V, "cr"), W, H),
        }
        names = {"y": "Y (明るさ)", "cb": "Cb (青み)", "cr": "Cr (赤み)"}
        panels = {}
        for k, x in zip(("y", "cb", "cr"), PANEL_X):
            m = ImageMobject(imgs[k])
            m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
            m.width = u(PANEL_W)
            m.move_to(px(x, PANEL_Y))
            m.check_ignore = True
            panels[k] = m
        PH = PANEL_W * H / W
        labels = {k: jp(names[k], 34, INK).move_to(px(x, PANEL_Y - PH / 2 - 26)) for k, x in zip(("y", "cb", "cr"), PANEL_X)}

        self.at("split", -0.1)
        copies = []
        for k in ("y", "cb", "cr"):
            c = ImageMobject(rgb_decoded())
            c.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
            c.width = u(PHOTO[1])
            c.move_to(px(*PHOTO[0]))
            c.check_ignore = True
            copies.append(c)
        self.add(*copies)
        self.remove(view)
        self.play(*[c.animate.set(width=u(PANEL_W)).move_to(px(x, PANEL_Y)) for c, x in zip(copies, PANEL_X)],
                  run_time=1.3)
        for k in panels:
            panels[k].set_opacity(0)
            self.add(panels[k])
        self.play(*[panels[k].animate.set_opacity(1) for k in panels], *[c.animate.set_opacity(0) for c in copies],
                  run_time=0.9)
        self.remove(*copies)
        self.at("three", -0.1)
        self.play(LaggedStart(*[FadeIn(labels[k], shift=DOWN * u(8)) for k in ("y", "cb", "cr")], lag_ratio=0.35),
                  run_time=1.4)

        # ---- 見比べる ----
        def ppos(k, x, y, w=PANEL_W, c=None):
            """写真の画素の座標 → その板の上の画面の px"""
            cxp, cyp = c if c is not None else (PANEL_X[("y", "cb", "cr").index(k)], PANEL_Y)
            h = w * H / W
            return cxp - w / 2 + x * w / W, cyp - h / 2 + y * h / H

        self.at("look", -0.1)
        self.play(LaggedStart(*[Indicate(labels[k], color=YELLOW, scale_factor=1.15) for k in ("y", "cb", "cr")],
                              lag_ratio=0.4), run_time=1.6)
        self.at("shape", -0.1)
        rings = VGroup()
        for k in ("y", "cb", "cr"):
            rings.add(Circle(radius=u(58), stroke_color=YELLOW, stroke_width=5).move_to(px(*ppos(k, 168, 118))))
        self.play(LaggedStart(*[Create(r) for r in rings], lag_ratio=0.4), run_time=1.6)
        # 目のあたりを 3 枚とも拡大して並べる
        ex0, ey0, ew, eh = EYE
        zooms = []
        for k, x in zip(("y", "cb", "cr"), ZOOM_X):
            a = imgs[k][ey0:ey0 + eh, ex0:ex0 + ew]
            z = ImageMobject(a)
            z.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
            z.width = u(ZOOM_W)
            z.move_to(px(x, ZOOM_Y))
            z.check_ignore = True
            zooms.append(z)
        self.play(*[FadeIn(z, target_position=r.get_center(), scale=0.3) for z, r in zip(zooms, rings)], run_time=1.0)
        self.at("also", -0.1)
        self.play(LaggedStart(*[Indicate(r, color=YELLOW, scale_factor=1.12) for r in rings[1:]], lag_ratio=0.4),
                  run_time=1.2)

        # ---- 明るさの明暗のパターンを、色の予測に流用する ----
        self.at("first", -0.1)
        sq_y = Square(u(16 * PANEL_W / W), stroke_color=YELLOW, stroke_width=4)
        sq_y.move_to(px(*ppos("y", lx + 8, ly + 8)))
        self.play(FadeOut(rings), *[z.animate.set_opacity(0) for z in zooms], Create(sq_y), run_time=0.8)
        self.remove(*zooms)
        self.play(Indicate(sq_y, color=YELLOW, scale_factor=1.4), run_time=0.8)
        self.at("copy", -0.1)
        blk = ImageMobject(gray_rgb(ex["luma16"]))
        blk.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        blk.width = u(16 * PANEL_W / W)
        blk.move_to(sq_y)
        blk.check_ignore = True
        self.add(blk)
        sq_cb = sq_y.copy().move_to(px(*ppos("cb", lx + 8, ly + 8)))
        self.play(blk.animate(path_arc=-0.8).move_to(sq_cb), run_time=1.3)
        self.play(Create(sq_cb), blk.animate.set_opacity(0), run_time=0.5)
        self.remove(blk)

        # ---- CfL という名前 ----
        self.at("name", -0.1)
        cfl = mono("CfL", 96, YELLOW).move_to(px(960, 580))
        self.play(FadeIn(cfl, scale=0.8), run_time=0.7)
        self.at("read", -0.1)
        full = mono("Chroma from Luma", 40, DIM).move_to(px(960, 675))
        jpn = jp("明るさから色を予測", 44, INK).move_to(px(960, 745))
        self.play(FadeIn(full, shift=UP * u(8)), run_time=0.6)
        self.play(FadeIn(jpn, shift=UP * u(8)), run_time=0.6)

        # ---- 左目のふちのブロックで、やってみる ----
        self.at("s06_08", -0.1)
        ctx_scale = CTX_W / PANEL_W
        self.play(FadeOut(VGroup(cfl, full, jpn)), panels["cr"].animate.set_opacity(0), FadeOut(labels["cr"]),
                  run_time=0.4)
        self.play(panels["y"].animate.scale(ctx_scale).move_to(px(*CTX_C[0])),
                  sq_y.animate.scale(ctx_scale).move_to(px(*ppos("y", lx + 8, ly + 8, CTX_W, CTX_C[0]))),
                  labels["y"].animate.move_to(px(CTX_C[0][0], CTX_C[0][1] - CTX_W * H / W / 2 - 28)),
                  panels["cb"].animate.scale(ctx_scale).move_to(px(*CTX_C[1])),
                  sq_cb.animate.scale(ctx_scale).move_to(px(*ppos("cb", lx + 8, ly + 8, CTX_W, CTX_C[1]))),
                  labels["cb"].animate.move_to(px(CTX_C[1][0], CTX_C[1][1] - CTX_W * H / W / 2 - 28)),
                  run_time=1.2)
        self.remove(panels["cr"])

        # 明るさの 16×16 が大きくなる
        g16 = CellGrid(np.vectorize(gray)(ex["luma16"]), GRID_C, CELL / 2, gap=1)
        g16_small = g16.copy().scale(16 * CTX_W / W / (8 * CELL)).move_to(sq_y)
        cap = jp("明るさ 16×16", 34, INK).move_to(px(GRID_C[0], GRID_C[1] - 4 * CELL - 34))

        # 決まり (手順) を出しておく
        rules = VGroup(
            mix("① 4つずつ平均", 38, INK),
            mix("② 平均を引く", 38, INK),
            mix(f"③ × {MINUS}0.25", 38, INK),
            mix(f"④ ＋ 平らな予測 {dcu}", 38, INK),
        )
        for r, y in zip(rules, RULE_Y):
            r.move_to(px(RULE_X, y), aligned_edge=LEFT).set_y(px(0, y)[1])
        rules.set_opacity(0.35)
        self.play(ReplacementTransform(g16_small.cells, g16.cells), FadeIn(cap, shift=DOWN * u(6)),
                  LaggedStart(*[FadeIn(r, shift=LEFT * u(10)) for r in rules], lag_ratio=0.15), run_time=1.1)

        def light(k):
            return [r.animate.set_opacity(1.0 if i == k else 0.35) for i, r in enumerate(rules)]

        # ① 4 つずつ平均
        self.at("avg4", -0.1)
        boxes = VGroup()
        for i in range(8):
            for j in range(8):
                boxes.add(Square(u(CELL - 4), stroke_color=YELLOW, stroke_width=2, stroke_opacity=0.9)
                          .move_to(px(GRID_C[0] - 4 * CELL + (j + 0.5) * CELL, GRID_C[1] - 4 * CELL + (i + 0.5) * CELL)))
        self.play(*light(0), LaggedStart(*[Create(b) for b in boxes], lag_ratio=0.01), run_time=1.0)
        l8 = ex["luma8"]
        g8 = CellGrid(np.vectorize(gray)(l8), GRID_C, CELL)
        self.play(ReplacementTransform(g16.cells, g8.cells), FadeOut(boxes), run_time=1.2)
        self.at("size8", -0.1)
        cap8 = jp("明るさ 8×8 (Cb・Cr と同じ細かさ)", 34, INK).move_to(cap)
        nums8 = np.round(l8).astype(int)
        g8n = CellGrid(np.vectorize(gray)(l8), GRID_C, CELL, nums=nums8,
                       num_colors=[[text_color_on(gray(v)) for v in row] for row in l8])
        self.play(retext(cap, cap8), FadeIn(g8n.nums), run_time=0.8)
        g8.nums = g8n.nums

        # ② 平均を引く
        self.at("mean", -0.1)
        chip = mix(f"平均 {round(avg)}", 38, YELLOW).move_to(px(GRID_C[0], GRID_C[1] + 4 * CELL + 44))
        self.play(*light(1), FadeIn(chip, shift=UP * u(8)), run_time=0.8)
        self.at("bump", -0.1)
        bump_r = np.round(bump).astype(int)
        cols_b = np.vectorize(lambda v: gray(128 + v))(bump)
        gb = CellGrid(cols_b, GRID_C, CELL, nums=[[signed(v) for v in row] for row in bump_r],
                      num_colors=[[text_color_on(c) for c in row] for row in cols_b])
        capb = jp("明暗のパターン (明るさ − 平均)", 34, INK).move_to(cap)
        self.play(Transform(g8.cells, gb.cells), Transform(g8.nums, gb.nums), retext(cap, capb),
                  chip.animate.scale(0.9).set_opacity(0.6), run_time=1.4)
        self.at("shape2", -0.1)
        plus = VGroup(*[g8.cells[i * 8 + j] for i in range(8) for j in range(8) if bump[i, j] > 0])
        minus = VGroup(*[g8.cells[i * 8 + j] for i in range(8) for j in range(8) if bump[i, j] < 0])
        self.play(Indicate(plus, color=WHITE, scale_factor=1.06), run_time=0.8)
        self.play(Indicate(minus, color="#000000", scale_factor=1.06), run_time=0.8)
        self.remove(plus, minus)          # Indicate が場面に入れたまとまりを外す (数字の上にマスが重なる)
        self.add(g8.cells)
        self.bring_to_front(g8.nums)

        # ③ × −0.25
        self.at("mul", -0.1)
        self.play(*light(2), run_time=0.6)
        self.at("alpha", -0.1)
        k_chip = mix(f"× {MINUS}0.25", 44, YELLOW).move_to(rules[2])
        self.add(k_chip)
        self.play(k_chip.animate(path_arc=0.7).move_to(px(GRID_C[0] + 4 * CELL + 200, GRID_C[1] - 4 * CELL - 34)),
                  run_time=0.7)
        cols_s = np.vectorize(lambda v: gray(128 + v))(scaled)
        gs = CellGrid(cols_s, GRID_C, CELL, nums=[[signed(v) for v in row] for row in scaled],
                      num_colors=[[text_color_on(c) for c in row] for row in cols_s])
        caps = jp(f"明暗のパターン × {MINUS}0.25", 34, INK).move_to(cap)
        self.play(Transform(g8.cells, gs.cells), Transform(g8.nums, gs.nums), retext(cap, caps), run_time=1.2)

        # ④ 平らな予測に足す
        self.at("add", -0.1)
        cols_p = np.vectorize(cb_color)(pred)
        gp = CellGrid(cols_p, GRID_C, CELL, nums=pred, num_colors=[[text_color_on(c) for c in row] for row in cols_p])
        capp = jp("Cb (青み) の予測", 34, YELLOW).move_to(cap)
        self.play(*light(3), run_time=0.5)
        self.play(Transform(g8.cells, gp.cells), Transform(g8.nums, gp.nums), retext(cap, capp),
                  FadeOut(chip), run_time=1.3)

        # ---- 本物と並べる ----
        self.at("real", -0.1)
        src_r = np.round(src).astype(int)
        cols_r = np.vectorize(cb_color)(src)
        gr = CellGrid(cols_r, REAL_C, CELL, nums=src_r, num_colors=[[text_color_on(c) for c in row] for row in cols_r])
        capr = jp("元の Cb (青み)", 34, INK).move_to(px(REAL_C[0], GRID_C[1] - 4 * CELL - 34))
        self.play(FadeOut(rules), FadeOut(k_chip), run_time=0.5)
        self.play(FadeIn(gr.cells, shift=LEFT * u(20)), FadeIn(gr.nums, shift=LEFT * u(20)),
                  FadeIn(capr, shift=LEFT * u(20)), run_time=0.9)

        # 目は黄緑 (青みが少ない)・ふちは黒 (青みは真ん中くらい)
        self.at("blue", -0.1)
        Lb = GRID_C[1] + 4 * CELL + 30

        def bracket(c, j0, j1, col, text):
            x0 = c[0] - 4 * CELL + j0 * CELL + 4
            x1 = c[0] - 4 * CELL + j1 * CELL - 4
            ln = Line(px(x0, Lb), px(x1, Lb), stroke_color=col, stroke_width=6)
            return ln, mix(text, 32, col).move_to(px((x0 + x1) / 2, Lb + 34))
        iris = [bracket(c, 0, 4, "#c9d65a", "目 (黄緑)") for c in (GRID_C, REAL_C)]
        self.play(*[Create(a) for a, _ in iris], *[FadeIn(t) for _, t in iris], run_time=0.8)
        self.at("rim", -0.1)
        rim = [bracket(c, 5, 8, INK, "輪郭 (黒)") for c in (GRID_C, REAL_C)]
        self.play(*[Create(a) for a, _ in rim], *[FadeIn(t) for _, t in rim], run_time=0.8)
        self.at("inv", -0.1)
        rel = mix("明るい所ほど 青みが少ない", 38, YELLOW).move_to(px(960, Lb + 110))
        self.play(FadeIn(rel, shift=UP * u(8)), run_time=0.8)

        # ---- ずれ：平ら / 明るさを流用 / 元 ----
        self.at("err", -0.1)
        flat = CellGrid(np.full((8, 8), cb_color(dcu), object), (TRIO_X[0], TRIO_Y), TRIO_CELL)
        k3 = TRIO_CELL / CELL
        tcap = [jp(s, 34, c).move_to(px(x, TRIO_Y - 4 * TRIO_CELL - 34))
                for s, c, x in (("平らな予測", INK, TRIO_X[0]), ("明るさを流用", YELLOW, TRIO_X[1]), ("元", INK, TRIO_X[2]))]
        self.play(FadeOut(VGroup(*[a for a, _ in iris + rim], *[t for _, t in iris + rim], rel)),
                  FadeOut(g8.nums), FadeOut(gr.nums),
                  g8.cells.animate.scale(k3).move_to(px(TRIO_X[1], TRIO_Y)),
                  gr.cells.animate.scale(k3).move_to(px(TRIO_X[2], TRIO_Y)),
                  ReplacementTransform(cap, tcap[1]), ReplacementTransform(capr, tcap[2]),
                  FadeIn(flat.cells, shift=RIGHT * u(20)), FadeIn(tcap[0], shift=RIGHT * u(20)), run_time=1.1)
        self.remove(g8.nums, gr.nums)
        ey = TRIO_Y + 4 * TRIO_CELL + 46
        self.at("flatp", -0.1)
        e_dc = mix(f"ずれ {ex['u']['err_dc']:.1f}", 40, CORAL).move_to(px(TRIO_X[0], ey))
        self.play(FadeIn(e_dc, shift=UP * u(8)), run_time=0.6)
        self.at("cflp", -0.1)
        e_cf = mix(f"ずれ {ex['u']['err_cfl']:.1f}", 40, YELLOW).move_to(px(TRIO_X[1], ey))
        self.play(FadeIn(e_cf, shift=UP * u(8)), run_time=0.6)
        self.play(pop(e_cf, 1.2, 0.7), run_time=0.7)

        # ---- 掛ける数の目盛り ----
        self.at("coef", -0.1)

        def nx(v):
            return NL_X0 + (v + 2) / 4 * (NL_X1 - NL_X0)
        axis = Line(px(NL_X0, NL_Y), px(NL_X1, NL_Y), stroke_color=DIM, stroke_width=3)
        ticks = VGroup(*[Line(px(nx(k / 8), NL_Y - (12 if k % 8 == 0 else 6)), px(nx(k / 8), NL_Y + (12 if k % 8 == 0 else 6)),
                              stroke_color=INK if k % 8 == 0 else DIM, stroke_width=3 if k % 8 == 0 else 2)
                         for k in range(-16, 17)])
        tl = VGroup(*[mix(signed(k), 30, DIM).move_to(px(nx(k), NL_Y + 40)) for k in (-2, -1, 1, 2)])
        self.play(Create(axis), LaggedStart(*[Create(t) for t in ticks], lag_ratio=0.02), FadeIn(tl), run_time=1.2)
        self.at("each", -0.1)

        def marker(v, col, text, up):
            s = 1 if up else -1
            tri = Triangle(stroke_width=0, fill_color=col, fill_opacity=1).scale(u(12)).rotate(PI if up else 0)
            tri.move_to(px(nx(v), NL_Y - s * 24))
            lab = mix(text, 32, col).move_to(px(nx(v), NL_Y - s * 60))
            return VGroup(tri, lab)
        mu = marker(au / 8, "#6aa7ff", f"Cb {MINUS}2/8", True)
        self.play(FadeIn(mu, shift=DOWN * u(10)), run_time=0.7)
        self.at("red", -0.1)
        mv = marker(av_ / 8, "#ff7a7a", "Cr +1/8", False)
        self.play(FadeIn(mv, shift=DOWN * u(10)), run_time=0.7)

        # ---- 写真全体で ----
        self.at("stat", -0.3)
        trio = VGroup(flat, g8.cells, gr.cells, *tcap, e_dc, e_cf)
        nl = VGroup(axis, ticks, tl, mu, mv)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        lit = np.ones((H, W), np.float32)
        view.set_opacity(0)
        self.add(view)
        self.play(FadeOut(trio), FadeOut(nl), FadeOut(VGroup(labels["y"], labels["cb"], sq_y, sq_cb)),
                  panels["y"].animate.set_opacity(0), panels["cb"].animate.set_opacity(0),
                  view.animate.set_opacity(1), run_time=0.6)
        self.remove(panels["y"], panels["cb"])
        d = dec()
        rects_all, rects_cfl = [], []
        for b in d.blocks:
            if not b["has_chroma"]:
                continue
            # 色のブロックが受け持つ明るさの範囲 (4×4 は 2 つ・4 つまとめて 8×8 になるので、そのときは 8×8 にそろえる)
            bx, by = b["x"] & ~7 if b["w"] < 8 else b["x"], b["y"] & ~7 if b["h"] < 8 else b["y"]
            bw, bh = max(b["w"], 8), max(b["h"], 8)
            bw, bh = min(bw, W - bx), min(bh, H - by)
            if b["uv_mode"] == 13:
                rects_cfl.append((bx, by, bw, bh))
            else:
                rects_all.append((bx, by, bw, bh))
        thin = [PRect(view, *r, stroke_color=INK, stroke_width=1.5, stroke_opacity=0.35) for r in rects_all]
        hot = [PRect(view, *r, stroke_color=YELLOW, stroke_width=3.5) for r in rects_cfl]
        for r in thin + hot:
            r.check_ignore = True          # 写真の一部として見せる線 (写真と同じく、端は立ち絵の後ろに隠れる)
        self.add(*thin)
        mask = np.zeros((H, W), bool)
        for x, y, w, h in rects_cfl:
            mask[y:y + h, x:x + w] = True

        def dim(t):
            lit[:] = np.where(mask, 1.0, 1 - 0.45 * t)
            view.lit = lit
        self.play(LaggedStart(*[Create(r) for r in hot], lag_ratio=0.01), ViewAnim(view, dim), run_time=0.9)
        self.at("n", -0.1)
        cnt = mix(f"明るさから色を予測したブロック  {n_cfl} / {n_chroma}", 40, YELLOW).move_to(px(960, 790))
        self.play(FadeIn(cnt, shift=UP * u(8)), run_time=0.7)

        # ---- 比較表 ----
        self.at("card", -0.1)
        card = compare_card(4, center=(960, 420), new=3)
        self.play(FadeOut(cnt), *[TrackFade(r, 1, 0) for r in hot + thin], FadeIn(card, shift=UP * u(30)),
                  run_time=0.9)
        self.remove(*hot, *thin)
        self.play(add_row(card), run_time=1.4)

        # 終わり：写真だけ (S07 の最初の画面)
        self.at(self.tl["duration"] - 1.3)
        lit0 = lit.copy()

        def undim(t):
            lit[:] = lit0 + (1 - lit0) * t
            view.lit = lit
        self.play(FadeOut(card), ViewAnim(view, undim), run_time=1.0)
        view.lit = None
        self.finish()
