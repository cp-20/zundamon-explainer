import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import filtered, fmt, info, pixels, path  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from vlib.pmap import STAGE_COL, PipelineMap  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.style import FILTER_COL, FILTER_NAME  # noqa: E402

CELL = 76  # 数字の箱（px）
ROW_Y = 640


def cell(color=None, size=CELL):
    return Square(u(size), stroke_width=0, fill_color=color or "#262b36", fill_opacity=1)


def num(v, size=38, color=INK):
    return mono(str(v), size, color)


class S05(PScene):
    def construct(self):
        F = FILTER_COL
        g = pixels("gradient").astype(int)
        z = info("zundamon")

        # ---- S05_01：地図のフィルタ段へ ----
        m = PipelineMap()
        self.add(m)
        self.at("what")
        self.play(Transform(m, m.state("strip", active="filter")), run_time=1.2)

        # ---- S05_02：グラデーションの一番上の行 ----
        self.at("s05_02", 0.1)
        img = ImageMobject(str(path("gradient"))).set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        img.height = u(300)
        img.move_to(px(960, 270))
        self.play(FadeIn(img, scale=0.92), run_time=0.8)

        N = 12
        xs = [960 + (i - (N - 1) / 2) * (CELL + 6) for i in range(N)]
        top = img.get_corner(UL)
        pw = img.width / 512
        cells = VGroup(*[cell(rgb_to_color(g[0, i] / 255)) for i in range(N)])
        for i, c in enumerate(cells):  # まず画像の一番上の画素の位置に置く
            c.stretch_to_fit_width(pw).stretch_to_fit_height(pw).move_to(top + RIGHT * pw * (i + 0.5) + DOWN * pw / 2)
        self.at("row")
        band = Rectangle(width=img.width, height=u(5), stroke_width=0, fill_color=WHITE, fill_opacity=0.9)
        band.move_to(top, aligned_edge=UL)
        self.play(FadeIn(band), run_time=0.3)
        self.add(cells)
        self.play(LaggedStart(*[c.animate.become(cell(rgb_to_color(g[0, i] / 255)).move_to(px(xs[i], ROW_Y)))
                                for i, c in enumerate(cells)], lag_ratio=0.04),
                  band.animate.set_opacity(0.35), run_time=1.2)

        self.at("red")
        R = [int(v) for v in g[0, :N, 0]]
        nums = VGroup(*[num(v).move_to(px(xs[i], ROW_Y)) for i, v in enumerate(R)])
        red_lbl = jp("赤の値", 30, CORAL).move_to(px(xs[0], ROW_Y - CELL / 2 - 36), aligned_edge=LEFT)
        self.play(LaggedStart(*[c.animate.set_fill("#262b36") for c in cells], lag_ratio=0.03),
                  LaggedStart(*[FadeIn(n, shift=UP * u(8)) for n in nums], lag_ratio=0.05),
                  FadeIn(red_lbl), run_time=1.0)

        # ---- ずんだもんが読み上げる 40, 40, 40, 41 ----
        self.at("read")
        self.play(LaggedStart(*[pop(nums[i], 1.3) for i in range(4)], lag_ratio=0.45), run_time=1.6)

        # ---- 同じ並びが二度と出てこない ----
        self.at("same")
        ul = underline(VGroup(*cells[0:3]), CYAN)
        self.play(Create(ul), run_time=0.4)
        ghost = nums[0:3].copy().set_color(CYAN)
        ghost.check_ignore = True  # 重ねて比べるための一時的な写し
        self.add(ghost)
        self.play(ghost.animate(path_arc=-PI / 2.5).move_to(VGroup(*nums[3:6]).get_center() + UP * u(4)), run_time=0.8)
        self.play(ghost.animate.set_color(CORAL), Shake(ghost, 8), run_time=0.6)
        self.play(FadeOut(ghost), FadeOut(ul), run_time=0.4)

        # ---- S05_04：Sub = 左との差 ----
        self.at("sub")
        sub_lbl = mix("Sub：左との差", 34, F[1]).move_to(px(960, ROW_Y - 130))
        arcs = VGroup(*[CurvedArrow(px(xs[i - 1], ROW_Y - 38), px(xs[i] - 6, ROW_Y - 38), angle=-PI / 2,
                                    stroke_width=3, color=F[1], tip_length=u(10))
                        for i in range(1, N)])
        self.play(FadeIn(sub_lbl, shift=DOWN * u(6)), LaggedStart(*[Create(a) for a in arcs], lag_ratio=0.06),
                  run_time=1.0)
        D = [R[0]] + [R[i] - R[i - 1] for i in range(1, N)]
        self.play(LaggedStart(*[retext(nums[i], num(D[i])) for i in range(N)], lag_ratio=0.05),
                  FadeOut(arcs), run_time=1.0)

        # ---- S05_05：0 と 1 ばかり → くり返しだらけ ----
        self.at("diff")
        ones = [i for i in range(1, N) if D[i] == 1]
        zeros = [i for i in range(1, N) if D[i] == 0]
        self.play(*[nums[i].animate.set_color(DIM) for i in zeros],
                  *[nums[i].animate.set_color(YELLOW) for i in ones], run_time=0.5)
        self.play(*[pop(nums[i], 1.35) for i in ones], run_time=0.5)
        ul = underline(VGroup(*cells[1:4]), CYAN)
        self.play(Create(ul), run_time=0.3)
        ghosts = []
        for k, start in enumerate((4, 7)):
            gh = VGroup(*nums[1:4]).copy().set_color(CYAN)
            gh.check_ignore = True
            self.add(gh)
            ghosts.append(gh)
        self.play(LaggedStart(*[gh.animate(path_arc=-PI / 2.5).move_to(VGroup(*nums[s:s + 3]).get_center())
                                for gh, s in zip(ghosts, (4, 7))], lag_ratio=0.35), run_time=1.2)
        self.play(*[FadeOut(gh, scale=1.3) for gh in ghosts], FadeOut(ul), run_time=0.5)

        # ---- S05_06：左から足せば元に戻る ----
        self.at("undo")
        plus = VGroup(*[CurvedArrow(px(xs[i - 1], ROW_Y + 38), px(xs[i] - 6, ROW_Y + 38), angle=PI / 2,
                                    stroke_width=3, color=CYAN, tip_length=u(10)) for i in range(1, N)])
        self.play(LaggedStart(*[AnimationGroup(Create(plus[i - 1]), retext(nums[i], num(R[i])))
                                for i in range(1, N)], lag_ratio=0.25), run_time=2.4)
        self.play(FadeOut(plus), FadeOut(sub_lbl), run_time=0.5)

        # ---- S05_07：5種類のフィルタ ----
        self.at("s05_07", 0.05)
        D2 = 76  # 近所図の箱
        cx = [540 + k * 210 for k in range(5)]
        dy = 560

        def diagram(cx_, size=D2):
            sq = {k: cell("#262b36", size) for k in "cbax"}
            sq["c"].move_to(px(cx_ - size / 2 - 2, dy - size / 2 - 2))
            sq["b"].move_to(px(cx_ + size / 2 + 2, dy - size / 2 - 2))
            sq["a"].move_to(px(cx_ - size / 2 - 2, dy + size / 2 + 2))
            sq["x"].move_to(px(cx_ + size / 2 + 2, dy + size / 2 + 2)).set_fill("#4a5160")
            labels = {k: jp(k, 30, DIM if k != "x" else INK).move_to(sq[k]) for k in "cbax"}
            return VGroup(*[VGroup(sq[k], labels[k]) for k in "cbax"])

        d0 = diagram(cx[0])
        # 行の中の2マス（左と今）がそのまま a と x になる
        a_src, x_src = VGroup(cells[2], nums[2]), VGroup(cells[3], nums[3])
        nums[2].check_ignore = nums[3].check_ignore = True  # 変形の途中の縮んだ数字は誤検出
        others = VGroup(*[VGroup(cells[i], nums[i]) for i in range(N) if i not in (2, 3)])
        self.play(FadeOut(others, shift=DOWN * u(20)), FadeOut(red_lbl), FadeOut(img), FadeOut(band),
                  Transform(a_src, d0[2]), Transform(x_src, d0[3]),
                  FadeIn(d0[0], shift=DOWN * u(20)), FadeIn(d0[1], shift=DOWN * u(20)), run_time=0.9)
        self.remove(a_src, x_src)
        self.add(d0)
        diags = [d0] + [d0.copy() for _ in range(4)]
        self.play(*[diags[k].animate.move_to(px(cx[k], dy)) for k in range(1, 5)], run_time=0.5)
        names = [jp(FILTER_NAME[k], 34, F[k]).move_to(px(cx[k], dy + D2 + 46)) for k in range(5)]
        uses = {0: "", 1: "a", 2: "b", 3: "ab", 4: "abc"}
        for k, cue in enumerate(["none", "sub2", "up", "avg", "paeth"]):
            self.at(cue)
            d = diags[k]
            anims = [FadeIn(names[k], shift=UP * u(8)), d[3][0].animate.set_fill(F[k], 0.55)]
            for j, key in enumerate("cbax"):
                if key in uses[k]:
                    anims += [d[j][0].animate.set_fill(F[k], 1), d[j][1].animate.set_color(BG)]
            self.play(*anims, run_time=0.5)

        self.at("hard")
        self.play(pop(VGroup(diags[4], names[4]), 1.2), run_time=0.7)

        # ---- S05_08：Paeth の予想（実データ：グラデーション 4行目 x=3 の赤）----
        # 4 行目は Paeth で圧縮されている行。a=左, b=上, c=左上
        y, x = 4, 3
        assert info("gradient")["filters"][y] == 4
        a, b, c = int(g[y, x - 1, 0]), int(g[y - 1, x, 0]), int(g[y - 1, x - 1, 0])
        p = a + b - c
        # 他の4つは左上の凡例に縮む（あとで本数のグラフになる）
        leg_y = [150 + k * 66 for k in range(5)]
        legend = []
        def chip(k, size=40):
            c_ = VGroup(cell(F[k], size), jp(str(k), size * 0.75, BG))
            c_[1].move_to(c_[0])
            return c_

        for k in range(4):
            legend.append(VGroup(diags[k], names[k]))
        self.at("s05_08")
        big = 112
        P = diags[4]
        self.play(*[Transform(legend[k][0], chip(k).move_to(px(80, leg_y[k]))) for k in range(4)],
                  *[Transform(names[k], jp(FILTER_NAME[k], 30, F[k])
                              .move_to(px(80, leg_y[k]) + RIGHT * u(40), aligned_edge=LEFT)) for k in range(4)],
                  P.animate.scale(big / D2).move_to(px(720, 600)),
                  names[4].animate.move_to(px(720 - big - 80, 600)),
                  run_time=1.0)
        self.at("pred")
        vals = {"c": c, "b": b, "a": a}
        newnums = {}
        anims = []
        for j, key in enumerate("cba"):
            n = num(vals[key], 40, BG).move_to(P[j][0])
            lab = P[j][1]
            anims.append(lab.animate.scale(0.55).set_color(BG).move_to(P[j][0].get_corner(UL) + u(14) * (RIGHT + DOWN)))
            newnums[key] = n
        eq1 = jp("a + b − c", 40, INK)
        eq1.move_to(px(1180, 520))
        self.play(*anims, *[FadeIn(n, scale=0.6) for n in newnums.values()], run_time=0.6)
        self.play(FadeIn(eq1, shift=LEFT * u(10)), run_time=0.5)

        # 上の行の増え方（c→b）を、左（a）に足す
        def step_arrow(m0, m1, side, label):
            d = UP if side == "up" else DOWN
            arr = CurvedArrow(m0.get_edge_center(d) + d * u(10), m1.get_edge_center(d) + d * u(10),
                              angle=-PI / 2 if side == "up" else PI / 2, color=YELLOW, stroke_width=4,
                              tip_length=u(14))
            t = jp(label, 30, YELLOW).next_to(arr, d, buff=u(6))
            return arr, t

        self.at("slope")
        up_arr, up_t = step_arrow(P[0][0], P[1][0], "up", f"{b - c:+d}")
        self.play(Create(up_arr), FadeIn(up_t, shift=DOWN * u(6)), run_time=0.7)
        self.at("add")
        dn_arr, dn_t = step_arrow(P[2][0], P[3][0], "down", f"{b - c:+d}")
        moving = up_t.copy()
        moving.check_ignore = True
        self.add(moving)
        self.play(moving.animate(path_arc=PI / 2).move_to(dn_t), Create(dn_arr), run_time=0.9)
        self.remove(moving)
        self.add(dn_t)

        self.at("inc")
        self.play(pop(up_t, 1.4), run_time=0.6)
        self.at("p41")
        eq2 = VGroup(jp(str(a), 40, F[4]), jp("+", 40), jp(str(b), 40, F[4]), jp("−", 40),
                     jp(str(c), 40, F[4]), jp("=", 40), jp(str(p), 40, YELLOW)).arrange(RIGHT, buff=u(18))
        eq2.next_to(eq1, DOWN, buff=u(36)).align_to(eq1, LEFT)
        flying = [newnums["a"].copy(), newnums["b"].copy(), newnums["c"].copy()]
        self.add(*flying)
        self.play(*[f.animate(path_arc=-PI / 4).become(eq2[i]) for f, i in zip(flying, (0, 2, 4))],
                  FadeIn(eq2[1]), FadeIn(eq2[3]), run_time=0.8)
        self.play(FadeIn(eq2[5]), FadeIn(eq2[6], shift=LEFT * u(10)), run_time=0.4)

        def badges(box, dist, offset=10):
            out_dir = {"c": UL, "b": UR, "a": DL}
            res = {}
            for j, key in enumerate("cba"):
                bd = VGroup(Circle(radius=u(26), stroke_width=0, fill_color="#3a4150", fill_opacity=1),
                            jp(str(dist[key]), 26 if dist[key] < 100 else 22, INK))
                bd[1].move_to(bd[0])
                bd.move_to(box[j][0].get_corner(out_dir[key]) + out_dir[key] * u(offset))
                res[key] = bd
            return res

        self.at("near")
        # 予想 p と各マスの差（距離）。一番近いものが選ばれる
        dist = {k: abs(p - v) for k, v in vals.items()}
        best = min("abc", key=lambda k: (dist[k], "abc".index(k)))
        dl = badges(P, dist)
        gp = eq2[6].copy()
        self.add(gp)
        self.play(FadeOut(VGroup(up_arr, up_t, dn_arr, dn_t)),
                  LaggedStart(*[FadeIn(bd, scale=0.5) for bd in dl.values()], lag_ratio=0.25),
                  gp.animate.move_to(P.get_center()).set_opacity(0), run_time=0.9)
        self.at("pick")
        jb = "cba".index(best)
        self.play(dl[best][0].animate.set_fill(YELLOW), dl[best][1].animate.set_color(BG),
                  P[jb][0].animate.set_fill(YELLOW), pop(VGroup(P[jb], newnums[best]), 1.2), run_time=0.7)
        arrow_src = newnums[best].copy()
        self.add(arrow_src)
        self.play(arrow_src.animate(path_arc=-PI / 3).move_to(P[3][0]).set_color(BG),
                  P[3][1].animate.set_opacity(0), P[3][0].animate.set_fill(YELLOW, 1), run_time=0.8)

        self.at("why")
        self.play(eq2[6].animate.scale(1.3).set_color(INK), run_time=0.5)
        self.play(eq2[6].animate.scale(1 / 1.3).set_color(YELLOW), run_time=0.4)

        # ---- S05_13〜16：色の境目では選び直しが効く（実データ：ずんだもんの輪郭 448行目 616列 の緑）----
        zp = pixels("zundamon").astype(int)
        ey, ex, ch = 448, 616, 1
        assert info("zundamon")["filters"][ey] == 4 and int(filtered("zundamon")[ey, 1 + ex * 4 + ch]) == 0
        ea, eb, ec, exx = (int(zp[ey, ex - 1, ch]), int(zp[ey - 1, ex, ch]), int(zp[ey - 1, ex - 1, ch]),
                           int(zp[ey, ex, ch]))
        ep = ea + eb - ec
        self.at("edge")
        zimg = png_mob(pixels("zundamon"), 480)
        zimg.move_to(px(620, 400))
        PG = VGroup(P, *newnums.values(), arrow_src)
        self.play(FadeOut(VGroup(eq1, eq2, *flying, *dl.values(), gp, names[4])), FadeIn(zimg, scale=0.97),
                  PG.animate.move_to(px(1300, 330)), run_time=0.9)
        # 6×6 画素の拡大（実際の色）
        G0y, G0x, GC = ey - 3, ex - 3, 52
        grid = VGroup()
        for r in range(6):
            for q in range(6):
                sq = cell(rgb_to_color(zp[G0y + r, G0x + q, :3] / 255), GC)
                sq.move_to(px(960 + (q - 2.5) * (GC + 2), 330 + (r - 2.5) * (GC + 2)))
                grid.add(sq)
        zx = zimg.get_left()[0] + zimg.width * (ex + 0.5) / zp.shape[1]
        zy = zimg.get_top()[1] - zimg.height * (ey + 0.5) / zp.shape[0]
        spot = Square(u(14), stroke_width=3, color=YELLOW, fill_opacity=0).move_to([zx, zy, 0])
        con = VGroup(Line(spot.get_corner(UR), grid.get_corner(UL), stroke_width=2, color=YELLOW, stroke_opacity=0.6),
                     Line(spot.get_corner(DR), grid.get_corner(DL), stroke_width=2, color=YELLOW, stroke_opacity=0.6))
        self.play(Create(spot), run_time=0.4)
        self.play(Create(con), TransformFromCopy(spot, grid), run_time=0.9)

        self.at("zoom")
        # 拡大の中の 2×2 を Paeth の図へ：色も数字も実データに変わる（図は同じオブジェクト）
        idx = {"c": (2, 2), "b": (2, 3), "a": (3, 2), "x": (3, 3)}
        evals = {"c": ec, "b": eb, "a": ea}
        anims = []
        enums = {}
        for j, key in enumerate("cbax"):
            r, q = idx[key]
            col = rgb_to_color(zp[G0y + r, G0x + q, :3] / 255)
            src = grid[r * 6 + q].copy()
            self.add(src)
            anims.append(src.animate(path_arc=-PI / 4).move_to(P[j][0]).set_opacity(0))
            anims.append(P[j][0].animate.set_fill(col, 1))
            if key != "x":
                dark = key == "c"
                n = num(evals[key], 34, INK if dark else BG).move_to(P[j][0])
                anims.append(retext(newnums[key], n))
                enums[key] = newnums[key]
            anims.append(P[j][1].animate.set_color(INK if key == "c" else BG).set_opacity(1))
        anims.append(FadeOut(arrow_src))
        anims.append(VGroup(*[grid[idx[k][0] * 6 + idx[k][1]] for k in "cbax"]).animate.set_opacity(0.35))
        self.play(*anims, run_time=1.0)
        gl = jp("緑の値", 26, "#7fd46a").next_to(P, UP, buff=u(40))
        self.play(FadeIn(gl), run_time=0.4)

        self.at("dark")
        self.play(Shake(VGroup(P[0], enums["c"]), 10), Shake(grid[2 * 6 + 2], 6), run_time=0.7)
        self.at("p364")
        eq3 = VGroup(jp(str(ea), 40, INK), jp("+", 40), jp(str(eb), 40, INK), jp("−", 40),
                     jp(str(ec), 40, INK), jp("=", 40), jp(str(ep), 40, CORAL)).arrange(RIGHT, buff=u(16))
        eq3.move_to(px(1160, 600))
        fl3 = [enums["a"].copy(), enums["b"].copy(), enums["c"].copy()]
        self.add(*fl3)
        self.play(*[f.animate(path_arc=PI / 4).become(eq3[i]) for f, i in zip(fl3, (0, 2, 4))],
                  FadeIn(eq3[1]), FadeIn(eq3[3]), run_time=0.8)
        self.play(FadeIn(eq3[5]), FadeIn(eq3[6], shift=LEFT * u(10)), run_time=0.4)
        rng = mix("1バイトは 0〜255", 28, DIM).next_to(eq3, DOWN, buff=u(26)).align_to(eq3, RIGHT)
        self.play(Shake(eq3[6], 10), run_time=0.8)
        self.at("max255")
        self.play(FadeIn(rng, shift=UP * u(6)), run_time=0.5)

        self.at("pick2")
        edist = {k: abs(ep - v) for k, v in evals.items()}
        ebest = min("abc", key=lambda k: (edist[k], "abc".index(k)))
        edl = badges(P, edist, 14)
        self.play(LaggedStart(*[FadeIn(bd, scale=0.5) for bd in edl.values()], lag_ratio=0.25), run_time=0.8)
        jb = "cba".index(ebest)
        self.play(edl[ebest][0].animate.set_fill(YELLOW), edl[ebest][1].animate.set_color(BG),
                  pop(VGroup(P[jb], enums[ebest]), 1.2), run_time=0.7)
        pick_src = enums[ebest].copy()
        self.add(pick_src)
        self.play(pick_src.animate(path_arc=-PI / 3).move_to(P[3][0]), P[3][1].animate.set_opacity(0), run_time=0.8)

        self.at("hit")
        # x の本当の値（拡大の x 画素から）が下から重なる
        true_x = num(exx, 34, BG).move_to(grid[3 * 6 + 3])
        true_x.check_ignore = True  # 予想の値にぴったり重ねて見せる
        self.add(true_x)
        diff0 = mix(f"差 {exx - int(evals[ebest])}", 30, YELLOW).next_to(P[3][0], DOWN, buff=u(16))
        self.play(true_x.animate(path_arc=-PI / 4).move_to(P[3][0]), run_time=0.8)
        self.remove(true_x)
        self.play(FadeIn(diff0, shift=UP * u(6)), pop(P[3], 1.15), run_time=0.6)
        self.at("got")
        self.play(pop(diff0, 1.4), run_time=0.6)

        # ---- S05_09：行ごとに選ぶ。番号は行の先頭に 1 バイト ----
        self.at("s05_17")
        self.play(FadeOut(VGroup(eq3, *fl3, rng, *edl.values(), pick_src, diff0, gl, grid, spot, con)),
                  Transform(VGroup(P, *newnums.values()), chip(4).move_to(px(80, leg_y[4]))),
                  FadeIn(names[4].become(jp(FILTER_NAME[4], 30, F[4])
                                         .move_to(px(80, leg_y[4]) + RIGHT * u(40), aligned_edge=LEFT))),
                  zimg.animate.scale(680 / 480).move_to(px(700, 480)), run_time=0.9)
        ztop, zh = zimg.get_top()[1], zimg.height
        H_ = z["height"]

        def row_y(r):
            return ztop - zh * (r + 0.5) / H_

        self.at("each")
        scan = Line(zimg.get_corner(UL), zimg.get_corner(UR), stroke_width=3, color=WHITE)
        self.add(scan)
        self.play(scan.animate.move_to([zimg.get_center()[0], row_y(420), 0]), run_time=0.6, rate_func=smooth)
        # 実際の 420 行目の画素を帯にして右へ引き出す
        zp = pixels("zundamon")
        rowimg = checker_composite(zp[420:421], round(14 / (680 / zp.shape[0])))
        strip = ImageMobject(rowimg).set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        strip.stretch_to_fit_width(zimg.width).stretch_to_fit_height(zh / H_ * 2)
        strip.move_to([zimg.get_center()[0], row_y(420), 0])
        self.add(strip)
        self.play(strip.animate.stretch_to_fit_width(u(440)).stretch_to_fit_height(u(40)).move_to(px(1250, 330)),
                  scan.animate.set_opacity(0.35), run_time=0.8)
        legend_chip4 = px(80, leg_y[4])
        self.at("tag")
        fz = filtered("zundamon")
        ft = int(fz[420, 0])
        assert ft == 4
        tag = VGroup(cell(F[ft], 40), jp(str(ft), 30, BG))
        tag[1].move_to(tag[0])
        src = names[4]
        tag.move_to(legend_chip4)
        self.add(tag)
        self.play(tag.animate(path_arc=-PI / 3).next_to(strip, LEFT, buff=u(6)), run_time=0.9)
        plus1 = mix("+1バイト", 28, F[ft]).next_to(tag, UP, buff=u(12))
        self.play(FadeIn(plus1, shift=DOWN * u(6)), run_time=0.4)

        # ---- S05_10：行ごとのフィルタを色で塗る ----
        self.at("s05_18", 0.2)
        self.play(FadeOut(plus1), strip.animate.stretch_to_fit_width(zimg.width).stretch_to_fit_height(zh / H_ * 2)
                  .move_to([zimg.get_center()[0], row_y(420), 0]),
                  tag[0].animate.scale(0.6).move_to([zimg.get_right()[0] + u(26), row_y(420), 0]),
                  tag[1].animate.scale(0.6).move_to([zimg.get_right()[0] + u(26), row_y(420), 0]).set_opacity(0),
                  FadeOut(scan), run_time=0.9)
        self.remove(strip)
        self.at("stripe")
        filters = info("zundamon")["filters"]
        runs, s0 = [], 0
        for r in range(1, H_ + 1):
            if r == H_ or filters[r] != filters[s0]:
                runs.append((s0, r, filters[s0])); s0 = r
        sx = zimg.get_right()[0] + u(26)
        bars = VGroup(*[Rectangle(width=u(30), height=zh * (e - s) / H_, stroke_width=0, fill_color=F[t],
                                  fill_opacity=1).move_to([sx, ztop - zh * (s + e) / 2 / H_, 0]) for s, e, t in runs])
        bars.check_group = True
        hist = info("zundamon")["filter_hist"]
        cnt = [hist.get(str(k), 0) for k in range(5)]
        maxc = max(cnt)
        cbars, ctxt = VGroup(), VGroup()
        for k in range(5):
            x0 = 80 + 150
            bw = 150 * cnt[k] / maxc
            r = Rectangle(width=u(bw), height=u(22), stroke_width=0, fill_color=F[k], fill_opacity=0.85)
            r.move_to(px(x0 + 70 + bw / 2, leg_y[k]))
            cbars.add(r)
            ctxt.add(jp(str(cnt[k]), 22, F[k]).next_to(r, RIGHT, buff=u(10)))
        # 名前の幅に合わせて棒の始まりをそろえる
        name_right = max(names[k].get_right()[0] for k in range(5))
        for r, t in zip(cbars, ctxt):
            r.shift(RIGHT * (name_right + u(18) - r.get_left()[0]))
            t.next_to(r, RIGHT, buff=u(10))
        self.play(LaggedStart(*[FadeIn(b) for b in bars], lag_ratio=0.004, run_time=1.6),
                  FadeOut(tag),
                  LaggedStart(*[GrowFromEdge(r, LEFT) for r in cbars], lag_ratio=0.15, run_time=1.2),
                  LaggedStart(*[FadeIn(t) for t in ctxt], lag_ratio=0.15, run_time=1.4))

        # ---- S05_11：Up が一番多い ----
        self.at("most")
        up = 2
        self.play(pop(VGroup(names[up], cbars[up], ctxt[up]), 1.2),
                  *[b.animate.set_opacity(0.25) for b, (s, e, t) in zip(bars, runs) if t != up], run_time=0.8)

        # ---- S05_12：フィルタ前の値の分布（グラデーション）----
        self.at("s05_20", 0.1)
        leg_all = VGroup(*[legend[k][0] for k in range(4)], P, *newnums.values(), *names, cbars, ctxt)
        self.play(FadeOut(VGroup(bars)), FadeOut(zimg), FadeOut(leg_all), run_time=0.8)
        before = np.bincount(g.ravel(), minlength=256)
        after = np.bincount(filtered("gradient")[:, 1:].ravel(), minlength=256)
        fb, fa = before / before.sum(), after / after.sum()
        X0, X1, YB, HMAX = 500, 1420, 820, 380
        bw = (X1 - X0) / 256
        axis = Line(px(X0 - 6, YB), px(X1 + 6, YB), stroke_width=3, color=DIM)
        t0 = jp("0", 24, DIM).next_to(px(X0 + bw / 2, YB), DOWN, buff=u(12))
        t255 = jp("255", 24, DIM).next_to(px(X1 - bw / 2, YB), DOWN, buff=u(12))
        hb = HMAX * 0.8 / fb.max()

        def hbars(fr, scale):
            return VGroup(*[Rectangle(width=u(bw * 0.8), height=max(u(fr[v] * scale), 1e-4), stroke_width=0,
                                      fill_color=INK if v else YELLOW, fill_opacity=0.9)
                            .move_to(px(X0 + bw * (v + 0.5), YB), aligned_edge=DOWN) for v in range(256)])

        hist_b = hbars(fb, hb)
        hist_b.check_group = True
        title = jp("フィルタ前", 32, INK).move_to(px(1330, 420))
        gthumb = ImageMobject(str(path("gradient")))
        gthumb.height = u(70)
        gthumb.next_to(title, LEFT, buff=u(20))
        self.at("hist", -0.5)
        self.play(Create(axis), FadeIn(t0), FadeIn(t255), FadeIn(title), FadeIn(gthumb), run_time=0.5)
        vmax = int(fb.argmax())
        mx = jp(f"{fb.max() * 100:.1f}%", 24, DIM)
        mx.next_to(hist_b[vmax], UP, buff=u(10))
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in hist_b], lag_ratio=0.01), run_time=1.2)
        self.play(FadeIn(mx), run_time=0.3)

        # ---- S05_13：フィルタ後は 0 に集まる ----
        self.at("zero")
        ha = HMAX / fa.max()
        hist_a = hbars(fa, ha)
        # 0 と 255 の棒は細くて軸に見えるので、変形先では太くする
        hist_a[0].stretch_to_fit_width(u(18)).move_to(px(X0 + 9, YB), aligned_edge=DOWN)
        hist_a[255].stretch_to_fit_width(u(10)).move_to(px(X1 - 5, YB), aligned_edge=DOWN)
        title2 = jp("フィルタ後", 30, YELLOW).move_to(title)
        z_lbl = jp(f"{fa[0] * 100:.0f}%", 34, YELLOW).next_to(hist_a[0].get_top(), RIGHT, buff=u(14))
        m_lbl = jp(f"{fa[255] * 100:.1f}%", 22, DIM).next_to(hist_a[255], UP, buff=u(8))
        # 台詞を止めた間に、ゆっくり変形させる
        self.play(*[Transform(hist_b[v], hist_a[v]) for v in range(256)], retext(title, title2),
                  FadeOut(mx), run_time=1.8)
        self.at("wow")
        self.play(Shake(hist_b[0], 8), run_time=0.6)
        self.at("pct")
        self.play(FadeIn(z_lbl, shift=DOWN * u(6)), FadeIn(m_lbl), run_time=0.5)

        self.at("next")
        self.play(FadeOut(VGroup(hist_b, axis, t0, t255, title, z_lbl, m_lbl)), FadeOut(gthumb), run_time=0.7)
        self.play(Transform(m, m.state("full", active=None, done=("filter",))), run_time=1.2)
        self.finish()
