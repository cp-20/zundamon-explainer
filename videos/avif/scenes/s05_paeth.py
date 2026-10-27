import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import MODE_NAMES, blocks, dec, picture_size, rgb_decoded, source_yuv, txbs  # noqa: E402
from vlib.photoview import PhotoView, PRect, TrackFade, ViewAnim, move_view  # noqa: E402
from vlib.ui import CellGrid, add_row, compare_card, gray, text_color_on  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)            # 写真の定位置 (S03〜S09 の始まりと終わり)
PINK = "#ff6fb5"                            # 左を選んだ (上はシアン、左上は黄)
DARK = "#262b36"                            # まだ作っていない画素
MINUS = "−"

# Paeth の例：目尻の 16×16
PB, PN = (208, 144), 16
PG_C, PG_CELL = (750, 500), 34              # 端の 1 列を足した 17×17 のマス
EX = (5, 3)                                 # 式に入れてみせる画素 (ブロックの中の行, 列)
EQ_X, EQ_Y = 1450, (150, 240)               # 式 (上の帯の右)
DF_X, DF_Y = (1250, 1450, 1650), (330, 398)  # 3 つとの差
PNG_C, PNG_CELL = (232, 196), 66            # PNG 編の Paeth の図 (左上)
PR_C, OR_C, PR_CELL = (1268, 262), (1674, 262), 24  # 予測と元 (上の帯の右。y 455 より上に収める)

# スムースの例：ぼけた背景の 32×32
SB, SN = (64, 96), 32
SG_C, SG_CELL = (700, 470), 15              # 端を足した 33×33
SR_C = (1228, 477.5)                        # 元 (32×32。予測の中身と同じ高さ)

# 棒グラフ
BAR_Y0, BAR_DY, BAR_H = 165, 66, 44
BAR_X0, BAR_LEN = 640, 720


def gray_rgb(a):
    a = np.clip(np.asarray(a), 0, 255).astype(np.uint8)
    return np.dstack([a, a, a])


def paeth_choice(above, left, corner):
    """Paeth が選ぶもの (h×w。0 左・1 上・2 左上)。仕様 7.11.2.2 と同じ順の比べ方"""
    ch = np.zeros((len(left), len(above)), int)
    for i, lv in enumerate(left):
        for j, av in enumerate(above):
            b = av + lv - corner
            pl, pt, ptl = abs(b - lv), abs(b - av), abs(b - corner)
            ch[i, j] = 0 if (pl <= pt and pl <= ptl) else (1 if pt <= ptl else 2)
    return ch


class S05(PScene):
    def construct(self):
        W, H = picture_size()
        d = dec()
        srcY = source_yuv()[0]

        # ---- 実データ：Paeth ----
        bp = next(b for b in blocks() if (b["x"], b["y"]) == PB)
        assert (bp["w"], bp["h"]) == (PN, PN) and MODE_NAMES[bp["y_mode"]] == "PAETH"
        tp = next(t for t in txbs(plane=0) if (t["x"], t["y"]) == PB)
        assert (tp["w"], tp["h"]) == (PN, PN)
        kp = {}
        pred_p = np.asarray(d.intra_pred(tp, kp), np.int64)
        assert np.array_equal(pred_p, np.asarray(d.pred[0][PB[1]:PB[1] + PN, PB[0]:PB[0] + PN], np.int64))
        corner = int(kp["above"][0])
        assert corner == int(kp["left"][0])
        A = np.array(kp["above"][1:PN + 1], np.int64)
        L = np.array(kp["left"][1:PN + 1], np.int64)
        choice = paeth_choice(A, L, corner)
        src_vals = np.stack([np.broadcast_to(L[:, None], (PN, PN)), np.broadcast_to(A[None, :], (PN, PN)),
                             np.full((PN, PN), corner)])
        assert np.array_equal(np.take_along_axis(src_vals, choice[None], 0)[0], pred_p)   # 選んだ値がそのまま予測
        ei, ej = EX
        ea, el = int(A[ej]), int(L[ei])
        base = ea + el - corner
        dfs = (abs(base - ea), abs(base - el), abs(base - corner))      # 上・左・左上 との差
        assert choice[ei, ej] == 0 and dfs[1] == min(dfs) and pred_p[ei, ej] == el
        assert all(v < 100 for v in (ea, el, corner))                   # マスの中に 2 けたで書ける

        # ---- 実データ：スムース ----
        bs = next(b for b in blocks() if (b["x"], b["y"]) == SB)
        assert (bs["w"], bs["h"]) == (SN, SN) and MODE_NAMES[bs["y_mode"]] == "SMOOTH"
        ts = next(t for t in txbs(plane=0) if (t["x"], t["y"]) == SB)
        ks = {}
        pred_s = np.asarray(d.intra_pred(ts, ks), np.int64)
        assert pred_s.shape == (SN, SN)
        assert np.array_equal(pred_s, np.asarray(d.pred[0][SB[1]:SB[1] + SN, SB[0]:SB[0] + SN], np.int64))

        # ---- 実データ：予測の種類の数 ----
        cnt = Counter(MODE_NAMES[b["y_mode"]] for b in blocks())
        ranking = cnt.most_common()
        assert ranking[0] == ("DC", 261) and ranking[1] == ("SMOOTH", 99) and ranking[2] == ("H", 68)
        assert cnt["PAETH"] == 13 and cnt["SMOOTH_V"] == 0 and cnt["SMOOTH_H"] == 0 and len(ranking) == 11
        mode_label = {"DC": "平ら", "SMOOTH": "スムース", "PAETH": "Paeth", "V": "縦", "H": "横",
                      "D45": "45°", "D135": "135°", "D113": "113°", "D157": "157°", "D203": "203°", "D67": "67°"}

        # ================= 写真 (S04 の終わり) =================
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)

        # ---- 目尻の 16×16 に寄る ----
        self.at("paeth", -0.1)
        rect_p = PRect(view, *PB, PN, PN, stroke_color=YELLOW, stroke_width=4)
        rect_p.check_ignore = True
        self.play(Create(rect_p), run_time=0.5)
        n1 = PN + 1
        box_p = (PG_C, n1 * PG_CELL, n1 * PG_CELL)
        win_p = (PB[0] - 1, PB[1] - 1, PB[0] + PN, PB[1] + PN)
        title_p = mix("Paeth予測", 48, YELLOW).move_to(px(PG_C[0], PG_C[1] - n1 * PG_CELL / 2 - 46))
        self.play(move_view(view, win_p, box_p), TrackFade(rect_p, 1, 0), FadeIn(title_p, shift=DOWN * u(8)),
                  run_time=1.2)
        self.remove(rect_p)

        # 端の画素 (灰) と、まだ作っていない中身 (暗い)
        cols_p = np.full((n1, n1), DARK, object)
        cols_p[0, 0] = gray(corner)
        cols_p[0, 1:] = [gray(v) for v in A]
        cols_p[1:, 0] = [gray(v) for v in L]
        gp = CellGrid(cols_p, PG_C, PG_CELL)
        gp.cells.set_opacity(0)
        self.add(gp.cells)
        self.play(gp.cells.animate.set_opacity(1), view.animate.set_opacity(0), run_time=0.5)
        self.remove(view)

        def pcell(i, j):              # 17×17 のマス (0 行・0 列が端)
            return gp.cell_at(i, j)

        # ---- PNG 編の Paeth ----
        self.at("png", -0.1)
        pc = {}
        for k, (di, dj), col in (("c", (0, 0), YELLOW), ("b", (0, 1), CYAN), ("a", (1, 0), PINK), ("x", (1, 1), "#4a5160")):
            sq = Square(u(PNG_CELL), stroke_width=0, fill_color=col, fill_opacity=1)
            sq.move_to(px(PNG_C[0] + (dj - 0.5) * (PNG_CELL + 4), PNG_C[1] + (di - 0.5) * (PNG_CELL + 4)))
            pc[k] = VGroup(sq, jp(k, 32, BG if k != "x" else INK).move_to(sq))
        png_d = VGroup(*pc.values())
        png_t = mix("PNG", 34, DIM).move_to(px(PNG_C[0], PNG_C[1] - PNG_CELL - 46))
        png_f = jp(f"a + b {MINUS} c", 38, INK).move_to(px(PNG_C[0], PNG_C[1] + PNG_CELL + 52))
        self.play(FadeIn(png_t), FadeIn(png_d, shift=DOWN * u(10)), FadeIn(png_f, shift=DOWN * u(10)), run_time=0.8)

        self.at("same", -0.1)
        self.play(pop(png_f, 1.2, 0.8), run_time=0.8)

        # ---- 1 つの画素で：上 ＋ 左 − 左上 ----
        self.at("calc", -0.1)
        ex_c = pcell(ei + 1, ej + 1)
        src_c = {"t": pcell(0, ej + 1), "l": pcell(ei + 1, 0), "c": pcell(0, 0)}
        src_col = {"t": CYAN, "l": PINK, "c": YELLOW}
        ex_box = Square(u(PG_CELL + 4), stroke_color=INK, stroke_width=5).move_to(ex_c)
        src_box = {k: Square(u(PG_CELL + 4), stroke_color=src_col[k], stroke_width=5).move_to(c) for k, c in src_c.items()}
        src_val = {"t": ea, "l": el, "c": corner}
        src_num = {k: mono(str(v), 24, text_color_on(gray(v))).move_to(src_c[k]) for k, v in src_val.items()}
        half = u(PG_CELL / 2 + 3)
        links = VGroup(
            DashedLine(ex_c.get_top() + UP * half * 0.2, src_c["t"].get_bottom() + DOWN * u(4), stroke_color=CYAN,
                       stroke_width=4, dash_length=u(10)),
            DashedLine(ex_c.get_left() + LEFT * half * 0.2, src_c["l"].get_right() + RIGHT * u(4), stroke_color=PINK,
                       stroke_width=4, dash_length=u(10)),
            DashedLine(ex_c.get_corner(UL) + (UL) * u(4), src_c["c"].get_corner(DR) + DR * u(4), stroke_color=YELLOW,
                       stroke_width=4, dash_length=u(10)),
        )
        self.play(Create(ex_box), run_time=0.4)
        self.play(*[Create(b) for b in src_box.values()], *[Create(ln) for ln in links],
                  *[FadeIn(n, scale=0.6) for n in src_num.values()], run_time=0.8)
        eq1 = VGroup(jp("上", 48, CYAN), jp("＋", 48), jp("左", 48, PINK), jp(MINUS, 48), jp("左上", 48, YELLOW))
        eq1.arrange(RIGHT, buff=u(18)).move_to(px(EQ_X, EQ_Y[0]))
        eq2 = VGroup(jp(str(ea), 48, CYAN), jp("＋", 48), jp(str(el), 48, PINK), jp(MINUS, 48),
                     jp(str(corner), 48, YELLOW), jp("＝", 48), jp(str(base), 48, INK))
        eq2.arrange(RIGHT, buff=u(18)).move_to(px(EQ_X, EQ_Y[1]))
        self.play(FadeIn(eq1, shift=LEFT * u(10)), run_time=0.5)
        flies = [src_num[k].copy() for k in ("t", "l", "c")]
        for f in flies:
            f.check_ignore = True
        self.add(*flies)
        self.play(*[ReplacementTransform(f, eq2[i]) for f, i in zip(flies, (0, 2, 4))],
                  FadeIn(eq2[1]), FadeIn(eq2[3]), run_time=0.8)
        eq2[5].check_ignore = True          # 「＝」は字面が低い記号
        self.play(FadeIn(eq2[5]), FadeIn(eq2[6], shift=LEFT * u(10)), run_time=0.4)

        # ---- 3 つとの差、一番近いものに丸 ----
        self.at("near", -0.1)
        diff_g = []
        for x, name, v, dv, col in zip(DF_X, ("上", "左", "左上"), (ea, el, corner), dfs, (CYAN, PINK, YELLOW)):
            top_t = mix(f"{name} {v}", 40, col).move_to(px(x, DF_Y[0]))
            bot_t = mix(f"差 {dv}", 40, INK).move_to(px(x, DF_Y[1]))
            diff_g.append(VGroup(top_t, bot_t))
        self.play(LaggedStart(*[FadeIn(g, shift=DOWN * u(8)) for g in diff_g], lag_ratio=0.25), run_time=0.9)
        win = diff_g[1]
        ring = Ellipse(width=win.width + u(60), height=win.height + u(44), stroke_color=PINK, stroke_width=5)
        ring.move_to(win)
        self.play(Create(ring), run_time=0.6)
        res = mono(str(el), 24, BG).move_to(ex_c)
        fly = win[0].copy()
        fly.check_ignore = True
        self.add(fly)
        self.play(fly.animate(path_arc=0.6).scale(0.5).move_to(ex_c).set_opacity(0), ex_c.animate.set_fill(PINK),
                  FadeIn(res), run_time=0.8)
        self.remove(fly)

        # ---- 違うのは使う画素 ----
        self.at("png2", -0.1)
        self.play(Indicate(pc["a"], color=PINK, scale_factor=1.15), Indicate(pc["b"], color=CYAN, scale_factor=1.15),
                  run_time=1.0)
        self.at("av1", -0.1)
        inner = Rectangle(width=u(PN * PG_CELL), height=u(PN * PG_CELL), stroke_color=INK, stroke_width=3)
        inner.move_to(px(PG_C[0] + PG_CELL / 2, PG_C[1] + PG_CELL / 2))
        top_row = VGroup(*[pcell(0, j) for j in range(1, n1)])
        left_col = VGroup(*[pcell(i, 0) for i in range(1, n1)])
        self.play(Create(inner), Indicate(top_row, color=CYAN, scale_factor=1.06),
                  Indicate(left_col, color=PINK, scale_factor=1.06), run_time=1.2)
        self.remove(top_row, left_col)
        self.add(gp.cells)
        self.bring_to_front(ex_box, *src_box.values(), *src_num.values(), res, links, inner)

        # ================= ブロックのすべての画素で =================
        self.at("all", -0.1)
        self.play(FadeOut(VGroup(eq1, eq2, *diff_g, ring, png_t, png_d, png_f, links, inner, ex_box,
                                 *src_box.values(), *src_num.values(), res)), run_time=0.6)
        sel_cols = (PINK, CYAN, YELLOW)
        over = VGroup()
        order = []
        for i in range(PN):
            for j in range(PN):
                sq = Square(u(PG_CELL - 2), stroke_width=0, fill_color=sel_cols[choice[i, j]], fill_opacity=1)
                sq.move_to(gp.cell_at(i + 1, j + 1))
                over.add(sq)
                order.append(i + j)
        over.check_ignore = True
        diag = [VGroup(*[over[k] for k in range(PN * PN) if order[k] == s]) for s in range(2 * PN - 1)]
        legend = VGroup()
        for name, col in (("上", CYAN), ("左", PINK), ("左上", YELLOW)):
            legend.add(VGroup(Square(u(30), stroke_width=0, fill_color=col, fill_opacity=1), jp(name, 34, INK))
                       .arrange(RIGHT, buff=u(10)))
        legend.arrange(RIGHT, buff=u(40)).move_to(px(PG_C[0], PG_C[1] + n1 * PG_CELL / 2 + 46))
        self.play(LaggedStart(*[FadeIn(g) for g in diag], lag_ratio=0.12), FadeIn(legend, shift=UP * u(8)),
                  run_time=1.2)
        self.add(gp.cells, over)

        # 色の画素が、実際の値に変わる (予測)。右上に、元と同じ大きさで並べる
        gpred = CellGrid(np.vectorize(gray)(pred_p), PR_C, PR_CELL)
        cap_pred = jp("予測", 34, CYAN).move_to(px(PR_C[0], PR_C[1] - PN * PR_CELL / 2 - 24))
        src_copy = over.copy()
        src_copy.check_ignore = True
        self.add(src_copy)
        self.play(ReplacementTransform(src_copy, gpred.cells, path_arc=-0.5), FadeIn(cap_pred, shift=DOWN * u(6)),
                  run_time=1.0)

        # 元と並べる
        g_src = CellGrid(np.vectorize(gray)(srcY[PB[1]:PB[1] + PN, PB[0]:PB[0] + PN]), OR_C, PR_CELL)
        cap_src = jp("元", 34, INK).move_to(px(OR_C[0], OR_C[1] - PN * PR_CELL / 2 - 24))
        self.play(FadeIn(g_src.cells, shift=LEFT * u(20)), FadeIn(cap_src, shift=LEFT * u(20)), run_time=0.6)

        # 角のところで、上と左を使い分けている
        self.at("corner", -0.1)
        pinks = VGroup(*[over[i * PN + j] for i in range(PN) for j in range(PN) if choice[i, j] == 0])
        cyans = VGroup(*[over[i * PN + j] for i in range(PN) for j in range(PN) if choice[i, j] == 1])
        self.play(Indicate(pinks, color=PINK, scale_factor=1.08), Indicate(legend[1], color=PINK), run_time=0.9)
        self.play(Indicate(cyans, color=CYAN, scale_factor=1.08), Indicate(legend[0], color=CYAN), run_time=0.9)
        self.remove(pinks, cyans)
        self.add(over)

        # ================= スムース予測 =================
        self.at("smooth", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        view.set_opacity(0)
        self.add(view)
        paeth_all = VGroup(gp.cells, over, gpred.cells, g_src.cells, title_p, legend, cap_pred, cap_src)
        self.play(FadeOut(paeth_all), view.animate.set_opacity(1), run_time=0.7)
        self.remove(*paeth_all)
        rect_s = PRect(view, *SB, SN, SN, stroke_color=YELLOW, stroke_width=4)
        rect_s.check_ignore = True
        title_s = mix("スムース予測", 48, YELLOW).move_to(px(960, 800))
        self.play(Create(rect_s), FadeIn(title_s, shift=UP * u(8)), run_time=0.6)

        self.at("blur", -0.1)
        s1 = SN + 1
        box_s = (SG_C, s1 * SG_CELL, s1 * SG_CELL)
        win_s = (SB[0] - 1, SB[1] - 1, SB[0] + SN, SB[1] + SN)
        sg_top = SG_C[1] - s1 * SG_CELL / 2
        self.play(move_view(view, win_s, box_s), TrackFade(rect_s, 1, 0),
                  title_s.animate.move_to(px(SG_C[0], sg_top - 46)), run_time=0.9)
        self.remove(rect_s)
        # 明るさの差が小さいので、元の 32×32 の最小〜最大を 0〜255 に広げて見せる (端・予測・元に同じ変換)
        src_s = srcY[SB[1]:SB[1] + SN, SB[0]:SB[0] + SN]
        lo, hi = float(src_s.min()), float(src_s.max())

        def sg(v):
            return gray(np.clip((v - lo) * 255 / (hi - lo), 0, 255))
        sA = np.array(ks["above"], np.int64)
        sL = np.array(ks["left"], np.int64)
        cols_s = np.full((s1, s1), DARK, object)
        cols_s[0, :] = [sg(v) for v in sA[:s1]]
        cols_s[1:, 0] = [sg(v) for v in sL[1:s1]]
        gs = CellGrid(cols_s, SG_C, SG_CELL, gap=1)
        gs.cells.set_opacity(0)
        self.add(gs.cells)
        note_s = jp("明るさの差を広げて表示", 26, DIM).move_to(px(960, SG_C[1] + s1 * SG_CELL / 2 + 34))
        self.play(gs.cells.animate.set_opacity(1), view.animate.set_opacity(0), FadeIn(note_s), run_time=0.3)
        self.remove(view)
        s_over = VGroup()
        s_order = []
        for i in range(SN):
            for j in range(SN):
                sq = Square(u(SG_CELL - 1), stroke_width=0, fill_color=sg(pred_s[i, j]), fill_opacity=1)
                sq.move_to(gs.cell_at(i + 1, j + 1))
                s_over.add(sq)
                s_order.append(i + j)
        s_over.check_ignore = True
        s_diag = [VGroup(*[s_over[k] for k in range(SN * SN) if s_order[k] == s]) for s in range(2 * SN - 1)]
        self.play(LaggedStart(*[FadeIn(g) for g in s_diag], lag_ratio=0.08), run_time=1.1)
        self.add(gs.cells, s_over)
        gsrc_s = CellGrid(np.vectorize(sg)(src_s), SR_C, SG_CELL, gap=1)
        cap_s = jp("元", 34, INK).move_to(px(SR_C[0], sg_top - 46))
        self.play(FadeIn(gsrc_s.cells, shift=LEFT * u(20)), FadeIn(cap_s, shift=LEFT * u(20)), run_time=0.5)

        # ================= 予測の種類の数 =================
        self.at("rank", -0.1)
        bar_title = jp("明るさの予測の種類 (ブロックの数)", 40, INK).move_to(px(960, 90))
        nmax = ranking[0][1]
        bars, labs, nums = [], [], []
        for r, (m, n) in enumerate(ranking):
            y = BAR_Y0 + r * BAR_DY
            b = Rectangle(width=u(BAR_LEN * n / nmax), height=u(BAR_H), stroke_width=0, fill_color="#56607a",
                          fill_opacity=1)
            b.move_to(px(BAR_X0, y), aligned_edge=LEFT).set_y(px(0, y)[1])
            bars.append(b)
            labs.append(mix(mode_label[m], 38, INK).move_to(px(BAR_X0 - 20, y), aligned_edge=RIGHT).set_y(px(0, y)[1]))
            nums.append(mix(str(n), 38, INK).next_to(b, RIGHT, buff=u(14)))
        self.play(FadeOut(VGroup(gs.cells, s_over, gsrc_s.cells, title_s, cap_s, note_s)), run_time=0.5)
        self.remove(gs.cells, s_over, gsrc_s.cells)
        self.play(FadeIn(bar_title, shift=DOWN * u(8)),
                  LaggedStart(*[AnimationGroup(FadeIn(lb), GrowFromEdge(b, LEFT), FadeIn(nm))
                                for lb, b, nm in zip(labs, bars, nums)], lag_ratio=0.12), run_time=1.8)

        self.at("top", -0.1)
        self.play(bars[0].animate.set_fill(YELLOW), labs[0].animate.set_color(YELLOW), nums[0].animate.set_color(YELLOW),
                  run_time=0.5)
        self.play(pop(VGroup(labs[0], nums[0]), 1.15, 0.6), run_time=0.6)
        self.at("second", -0.1)
        self.play(bars[1].animate.set_fill(YELLOW), labs[1].animate.set_color(YELLOW), nums[1].animate.set_color(YELLOW),
                  run_time=0.5)
        self.play(pop(VGroup(labs[1], nums[1]), 1.15, 0.6), run_time=0.6)

        # ================= 平らな予測のブロック =================
        self.at("flat", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        view.set_opacity(0)
        self.add(view)
        dc_rects = []
        mask = np.zeros((H, W), bool)
        for b in blocks():
            if b["y_mode"] != 0:
                continue
            x, y = b["x"], b["y"]
            w, h = min(b["w"], W - x), min(b["h"], H - y)
            if w <= 0 or h <= 0:
                continue
            mask[y:y + h, x:x + w] = True
            r = PRect(view, x, y, w, h, stroke_color=YELLOW, stroke_width=2.5)
            r.check_ignore = True
            dc_rects.append(r)
        assert len([b for b in blocks() if b["y_mode"] == 0]) == 261
        lit = np.ones((H, W), np.float32)
        chart = VGroup(bar_title, *bars, *labs, *nums)
        self.play(FadeOut(chart), view.animate.set_opacity(1), run_time=0.6)
        self.remove(*chart)

        def dim(t):
            lit[:] = np.where(mask, 1.0, 1 - 0.5 * t)
            view.lit = lit
        self.add(*dc_rects)
        for r in dc_rects:
            r.set_stroke(opacity=0)
        self.play(*[TrackFade(r, 0, 1) for r in dc_rects], ViewAnim(view, dim), run_time=1.0)
        self.at("dc", -0.1)
        dc_lab = mix("平らに予測したブロック", 40, YELLOW).move_to(px(960, 790))
        self.play(FadeIn(dc_lab, shift=UP * u(8)), run_time=0.7)

        # ================= 比較表 =================
        self.at("card", -0.1)
        card = compare_card(3, center=(960, 420), new=2)
        self.play(FadeOut(dc_lab), *[TrackFade(r, 1, 0) for r in dc_rects], FadeIn(card, shift=UP * u(30)),
                  run_time=0.9)
        self.remove(*dc_rects)
        self.play(add_row(card), run_time=1.4)

        # 終わり：写真だけ (S06 の最初の画面)
        self.at(self.tl["duration"] - 1.3)
        lit0 = lit.copy()

        def undim(t):
            lit[:] = lit0 + (1 - lit0) * t
            view.lit = lit
        self.play(FadeOut(card), ViewAnim(view, undim), run_time=1.0)
        view.lit = None
        self.finish()
