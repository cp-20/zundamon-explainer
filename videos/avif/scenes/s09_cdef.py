import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import dec, picture_size, planes, rgb_decoded, source_yuv  # noqa: E402
from vlib.photoview import PhotoView, PLine, PRect, TrackFade, ViewAnim, move_view  # noqa: E402
from vlib.ui import CellGrid, HEIC_COL, add_row, compare_card, gray  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)
DB_WIN = (30, 230, 120, 290)               # デブロッキングを見せる所 (左のひげのあたり。段の差が大きい)
DB_K = 2.5                                  # 差が小さいので、前後の両方に同じコントラストの強調
EX = (128, 256)                             # 例の 8×8 (左下のひげ。CDEF を使った 64×64 の中)
CELL = 48                                   # 主役の 8×8 のマス (384px)
GRID_C = (760, 640)                         # 主役の 8×8 の位置
FIT_C = (1220, 640)                         # 平均で塗った 8×8 を並べる位置
ZBOX = ((960, 472), 1040, 864)              # 例に寄ったときの写真の箱 (例の 8×8 が GRID_C に CELL で来る)
PCELL, PANEL_Y, PANEL_DX = 22, 190, 222     # 8 つの向きの板
ORDER = [2, 1, 0, 7, 6, 5, 4, 3]            # 板に並べる順 (水平から反時計回りに 22.5° ずつ)
# 向き dir の線の進む向き (横 j, 縦 i。画面の下向きが +i)。仕様 7.15.2 の partial の足し方から
DIR_VEC = {0: (1, -1), 1: (2, -1), 2: (1, 0), 3: (2, 1), 4: (1, 1), 5: (1, 2), 6: (0, 1), 7: (-1, 2)}


def line_index(k, i, j):
    """向き k の線の番号 (仕様 7.15.2 の cdef_direction の partial[k] の添え字)"""
    return [i + j, i + j // 2, i, 3 + i - j // 2, 7 + i - j, 3 - i // 2 + j, j, i // 2 + j][k]


def groups(k):
    g = {}
    for i in range(8):
        for j in range(8):
            g.setdefault(line_index(k, i, j), []).append((i, j))
    return g


def line_fill(b, k):
    """線ごとの平均で塗った 8×8"""
    out = np.zeros((8, 8))
    for cells in groups(k).values():
        m = np.mean([b[i, j] for i, j in cells])
        for i, j in cells:
            out[i, j] = m
    return out


def bundle(k, center, cell, color=CYAN, width=4, opacity=0.95):
    """向き k の線の束 (1 本の線は、同じ線に入るマスのうち両端のマスの中心を結ぶ)"""
    vx, vy = DIR_VEC[k]
    n = np.hypot(vx, vy)
    ux, uy = vx / n, vy / n
    x0, y0 = center[0] - 4 * cell, center[1] - 4 * cell
    out = VGroup()
    for cells in groups(k).values():
        if len(cells) < 2:
            continue
        pr = [(j * ux + i * uy, i, j) for i, j in cells]
        _, ia, ja = min(pr)
        _, ib, jb = max(pr)
        ax, ay = x0 + (ja + 0.5) * cell - ux * cell * 0.4, y0 + (ia + 0.5) * cell - uy * cell * 0.4
        bx, by = x0 + (jb + 0.5) * cell + ux * cell * 0.4, y0 + (ib + 0.5) * cell + uy * cell * 0.4
        out.add(Line(px(ax, ay), px(bx, by), stroke_color=color, stroke_width=width, stroke_opacity=opacity))
    return out


class DLine(Line):
    """写真の画素の座標で引いた斜めの線 (窓が動いてもついてくる。PLine は縦横の線だけを切るので、斜めはこちら)"""

    def __init__(self, view, a, b, **style):
        super().__init__(ORIGIN, RIGHT, **style)
        self.view, self.a, self.b = view, a, b
        self.sync()
        self.add_updater(lambda m: m.sync())

    def sync(self):
        self.put_start_and_end_on(self.view.to_point(*self.a), self.view.to_point(*self.b))
        return self


def gray_cols(a):
    return np.vectorize(gray)(np.clip(np.round(a), 0, 255))


class S09(PScene):
    def construct(self):
        W, H = picture_size()
        d = dec()
        cl = d.cdef_log
        Yd = planes(stage="deblocked")[0].astype(float)
        Yc = planes(stage="cdef")[0].astype(float)
        src = source_yuv()[0]

        # ---- 実データの確かめ ----
        blocks = cl["blocks"]
        assert len(blocks) == 2166 and not any(b["skip"] for b in blocks)
        used = [s for s in cl["sb"] if s["y_pri"] or s["y_sec"]]
        assert len(cl["sb"]) == 40 and len(used) == 9 and all(s["idx"] == 1 and s["y_pri"] == 5 for s in used)
        mask = np.zeros((H, W), bool)
        for s in used:
            mask[s["y"]:s["y"] + 64, s["x"]:s["x"] + 64] = True
        e_db, e_cd = np.abs(Yd - src)[mask].mean(), np.abs(Yc - src)[mask].mean()
        assert f"{e_db:.3f}" == "1.444" and f"{e_cd:.3f}" == "1.371" and round(100 * (1 - e_cd / e_db)) == 5
        ex, ey = EX
        blk = Yd[ey:ey + 8, ex:ex + 8]
        dirx = next(b["dir"] for b in blocks if (b["x"], b["y"]) == EX)
        fills = {k: line_fill(blk, k) for k in range(8)}
        errs = {k: float(np.abs(blk - fills[k]).mean()) for k in range(8)}
        sse = {k: float(((blk - fills[k]) ** 2).sum()) for k in range(8)}
        assert min(sse, key=sse.get) == dirx == min(errs, key=errs.get) == 1     # 線ごとの平均がいちばん元に近い向き
        assert any(s["x"] <= ex < s["x"] + 64 and s["y"] <= ey < s["y"] + 64 for s in used)  # 例は CDEF を使った所

        # ---- 写真 (S08 の終わり) ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)

        # ---- デブロッキングの前後 (左のひげのあたりに寄る。前後の両方に同じ強調) ----
        rgb = {s: rgb_decoded(stage=s).astype(np.float32) for s in ("final", "recon", "deblocked")}
        L, T, R, B = DB_WIN
        mcol = rgb["recon"][T:B, L:R].reshape(-1, 3).mean(0)

        def stretch(img, k):
            return mcol + (img - mcol) * k

        def to_recon(t):
            view.base = stretch(rgb["final"] + (rgb["recon"] - rgb["final"]) * t, 1 + (DB_K - 1) * t)

        self.at("db", -0.1)
        zin = move_view(view, win=DB_WIN, box=(PHOTO[0], PHOTO[1], PHOTO[2]), run_time=1.2)
        self.play(zin, ViewAnim(view, to_recon, run_time=1.2), run_time=1.2)
        segs = []
        for (plane, pss, x, y, fs, lvl, lim, blim, thr, app, res) in d.deblock_log:
            if plane or not any(res):
                continue
            a, b = ((x, y), (x, y + 4)) if pss == 0 else ((x, y), (x + 4, y))
            if L <= a[0] <= R and T <= a[1] <= B and L <= b[0] <= R and T <= b[1] <= B:
                segs.append(PLine(view, a, b, stroke_color=YELLOW, stroke_width=3))
        for s_ in segs:
            s_.check_ignore = True
        self.play(LaggedStart(*[Create(s_) for s_ in segs], lag_ratio=0.004), run_time=0.7)

        def to_deb(t):
            view.base = stretch(rgb["recon"] + (rgb["deblocked"] - rgb["recon"]) * t, DB_K)
        self.play(ViewAnim(view, to_deb), run_time=1.2)
        self.play(*[TrackFade(s_, 1, 0) for s_ in segs], run_time=0.6)
        self.remove(*segs)

        # ---- HEIC は SAO、AV1 は CDEF ----
        def back(t):
            view.base = stretch(rgb["deblocked"] + (rgb["final"] - rgb["deblocked"]) * t, DB_K + (1 - DB_K) * t)
        self.at("heic", -0.1)
        self.play(move_view(view, win=(0, 0, W, H), box=(PHOTO[0], PHOTO[1], PHOTO[2])), ViewAnim(view, back),
                  run_time=1.2)
        view.base = rgb["final"].copy()
        heic = mix("HEIC  SAO", 44, HEIC_COL).move_to(px(700, 790))
        heic2 = jp("山と谷をならす", 32, HEIC_COL).move_to(px(700, 852))
        self.play(FadeIn(heic, shift=UP * u(8)), FadeIn(heic2, shift=UP * u(8)), run_time=0.7)
        self.at("av1", -0.1)
        av1 = mix("AV1  CDEF", 48, YELLOW).move_to(px(1220, 790))
        self.play(FadeIn(av1, shift=UP * u(8)), run_time=0.7)
        self.at("dir", -0.1)
        av12 = jp("模様の向きに沿ってならす", 32, INK).move_to(px(1220, 852))
        self.play(FadeIn(av12, shift=UP * u(8)), run_time=0.7)
        self.at("how", 0.2)
        self.play(pop(av12, 1.12, 0.8), run_time=0.8)

        # ---- 8×8 ごとに探す：ひげの 8×8 に寄る ----
        self.at("s09_04", -0.1)
        s = CELL
        (bcx, bcy), bw, bh = ZBOX
        cx, cy = ex + 4 + (bcx - GRID_C[0]) / s, ey + 4 + (bcy - GRID_C[1]) / s
        zwin = (cx - bw / s / 2, cy - bh / s / 2, cx + bw / s / 2, cy + bh / s / 2)
        sq = PRect(view, ex, ey, 8, 8, stroke_color=YELLOW, stroke_width=4)
        sq.check_ignore = True
        self.play(FadeOut(VGroup(heic, heic2, av1, av12)), Create(sq), run_time=0.4)
        self.play(move_view(view, win=zwin, box=ZBOX), run_time=1.3)

        big = CellGrid(gray_cols(blk), GRID_C, CELL, gap=2)
        cap = jp("明るさ 8×8", 32, INK).move_to(px(GRID_C[0], GRID_C[1] - 4 * CELL - 30))
        big.cells.set_opacity(0)
        self.add(big.cells)
        self.play(view.animate.set_opacity(0), big.cells.animate.set_opacity(1), TrackFade(sq, 1, 0),
                  FadeIn(cap), run_time=0.5)
        self.remove(view, sq)

        # ---- 8 つの向きで線を引く ----
        self.at("lines", -0.1)
        pc = {k: (960 + (n - 3.5) * PANEL_DX, PANEL_Y) for n, k in enumerate(ORDER)}
        pgrid = {k: CellGrid(gray_cols(blk), pc[k], PCELL, gap=1) for k in ORDER}
        pl = {k: bundle(k, pc[k], PCELL, width=2.5) for k in ORDER}
        bl = {k: bundle(k, GRID_C, CELL, width=4) for k in ORDER}
        anims = []
        for k in ORDER:
            anims.append(Succession(Create(bl[k], run_time=0.5),
                                    AnimationGroup(ReplacementTransform(bl[k], pl[k]),
                                                   FadeIn(pgrid[k].cells, target_position=px(*GRID_C),
                                                          scale=CELL / PCELL), run_time=0.6)))
        self.play(LaggedStart(*anims, lag_ratio=0.13), run_time=self.until("avg", -0.15))

        # ---- 線ごとに平均をとって塗る ----
        self.at("avg", -0.1)
        fgrid = {k: CellGrid(gray_cols(fills[k]), pc[k], PCELL, gap=1) for k in ORDER}
        self.play(LaggedStart(*[AnimationGroup(Transform(pgrid[k].cells, fgrid[k].cells),
                                               pl[k].animate.set_stroke(opacity=0.3)) for k in ORDER],
                              lag_ratio=0.1), run_time=1.6)

        # ---- 模様に沿った向きだけが元に近い ----
        self.at("best", -0.1)
        others = [k for k in ORDER if k != dirx]
        hi = Square(u(8 * PCELL + 14), stroke_color=YELLOW, stroke_width=5).move_to(px(*pc[dirx]))
        self.play(*[pgrid[k].cells.animate.set_opacity(0.3) for k in others],
                  *[pl[k].animate.set_stroke(opacity=0.12) for k in others], Create(hi), run_time=0.8)
        self.at("same", -0.1)
        bb = bundle(dirx, GRID_C, CELL, width=5)
        self.play(Create(bb), run_time=0.8)
        self.at("fit", -0.1)
        fit = CellGrid(gray_cols(fills[dirx]), FIT_C, CELL, gap=2)
        cap_f = jp("線ごとの平均で塗る", 32, YELLOW).move_to(px(FIT_C[0], GRID_C[1] - 4 * CELL - 30))
        self.play(FadeIn(fit.cells, target_position=px(*pc[dirx]), scale=PCELL / CELL), FadeIn(cap_f),
                  run_time=0.9)
        errl = {k: mix(f"ずれ {errs[k]:.1f}", 28, YELLOW if k == dirx else DIM)
                .move_to(px(pc[k][0], PANEL_Y + 4 * PCELL + 34)) for k in ORDER}
        self.play(LaggedStart(*[FadeIn(errl[k], shift=UP * u(6)) for k in ORDER], lag_ratio=0.08), run_time=1.0)
        self.play(pop(errl[dirx], 1.3, 0.7), run_time=0.7)

        # ---- それが模様の向き ----
        self.at("s09_07", -0.1)
        vx, vy = DIR_VEC[dirx]
        n = np.hypot(vx, vy)
        L0 = 3.6                                   # 写真の上の短い線の半分の長さ (画素)
        half = L0 * CELL
        arrow = Line(px(GRID_C[0] - vx / n * half, GRID_C[1] - vy / n * half),
                     px(GRID_C[0] + vx / n * half, GRID_C[1] + vy / n * half), stroke_color=YELLOW, stroke_width=7)
        self.play(FadeOut(bb), Create(arrow), run_time=0.8)

        # ---- 画像全体で探す ----
        self.at("whole", -0.1)
        panels = VGroup(*[pgrid[k].cells for k in ORDER], *[pl[k] for k in ORDER], hi, *errl.values())
        view.set_opacity(0)
        view.lit = None
        self.add(view)
        self.bring_to_front(big.cells, arrow)
        self.play(FadeOut(panels), FadeOut(fit.cells), FadeOut(cap_f), FadeOut(cap),
                  big.cells.animate.set_opacity(0), view.animate.set_opacity(1), run_time=0.6)
        self.remove(big.cells)

        def seg(b):
            vx_, vy_ = DIR_VEC[b["dir"]]
            n_ = np.hypot(vx_, vy_)
            c = (min(b["x"] + 4, W - 0.5), min(b["y"] + 4, H - 0.5))
            h_ = L0 if b is exb else 3.0
            return (c[0] - vx_ / n_ * h_, c[1] - vy_ / n_ * h_), (c[0] + vx_ / n_ * h_, c[1] + vy_ / n_ * h_)
        exb = next(b for b in blocks if (b["x"], b["y"]) == EX)
        a0, b0 = seg(exb)
        pex = DLine(view, a0, b0, stroke_color=YELLOW, stroke_width=7)
        pex.check_ignore = True
        self.add(pex)
        self.remove(arrow)
        lit = np.ones((H, W), np.float32)

        def dim(t):
            lit[:] = 1 - 0.45 * t
            view.lit = lit
        self.play(move_view(view, win=(0, 0, W, H), box=PHOTO), run_time=1.4)
        dirs = VGroup()
        for b in blocks:
            if b is exb:
                continue
            a, c = seg(b)
            # 平らな所 (var が小さい) の向きは当てにならないので薄く
            op = 0.2 + 0.8 * float(np.clip((np.log10(max(b["var"], 1)) - 2.3) / 1.7, 0, 1))
            ln = Line(view.to_point(*a), view.to_point(*c), stroke_color=INK, stroke_width=2.6, stroke_opacity=op)
            ln.check_ignore = True
            dirs.add(ln)
        dirs.check_ignore = True
        order = sorted(range(len(dirs)), key=lambda i: dirs[i].get_center()[0] - 0.5 * dirs[i].get_center()[1])
        self.play(ViewAnim(view, dim), LaggedStart(*[Create(dirs[i]) for i in order], lag_ratio=0.0006),
                  run_time=1.9)
        assert len(dirs) + 1 == 2166

        # ---- その向きに並ぶ画素どうしでならす ----
        self.at("along", -0.1)

        def undim(t):
            lit[:] = 0.55 + 0.45 * t
            view.lit = lit
        self.play(FadeOut(dirs), TrackFade(pex, 1, 0), ViewAnim(view, undim), move_view(view, win=zwin, box=ZBOX),
                  run_time=0.9)
        self.remove(dirs, pex)
        view.lit = None
        g2 = CellGrid(gray_cols(blk), GRID_C, CELL, gap=2)
        cap2 = jp("ならす前", 34, INK).move_to(px(GRID_C[0], GRID_C[1] - 4 * CELL - 30))
        g2.cells.set_opacity(0)
        self.add(g2.cells)
        b2 = bundle(dirx, GRID_C, CELL, width=4, opacity=0.6)
        self.play(view.animate.set_opacity(0), g2.cells.animate.set_opacity(1), FadeIn(cap2), Create(b2),
                  run_time=0.4)
        self.remove(view)

        # 1 本の線 (ひげの上) の画素が、その線の上でならされる
        self.at("only", -0.1)
        gs = groups(dirx)
        key = max((kk for kk, c in gs.items() if len(c) >= 6), key=lambda kk: np.mean([blk[i, j] for i, j in gs[kk]]))
        on = gs[key]
        x0, y0 = GRID_C[0] - 4 * CELL, GRID_C[1] - 4 * CELL
        boxes = VGroup(*[Square(u(CELL - 6), stroke_color=YELLOW, stroke_width=4)
                         .move_to(px(x0 + (j + 0.5) * CELL, y0 + (i + 0.5) * CELL)) for i, j in on])
        along_t = jp("向きに沿って ならす", 34, YELLOW).move_to(px(FIT_C[0] + 20, GRID_C[1] - 70))
        self.play(LaggedStart(*[Create(bx) for bx in boxes], lag_ratio=0.12), FadeIn(along_t, shift=LEFT * u(8)),
                  run_time=1.0)
        # 輪郭 (ひげ) をまたぐ向き
        self.at("cross", -0.1)
        pxv, pyv = -vy / n, vx / n                         # 線に直交する向き
        mi, mj = on[len(on) // 2]
        mcx, mcy = x0 + (mj + 0.5) * CELL, y0 + (mi + 0.5) * CELL
        crs = Line(px(mcx - pxv * 2.4 * CELL, mcy - pyv * 2.4 * CELL), px(mcx + pxv * 2.4 * CELL, mcy + pyv * 2.4 * CELL),
                   stroke_color=CORAL, stroke_width=6)
        xm = VGroup(Line(px(-16, -16), px(16, 16)), Line(px(-16, 16), px(16, -16))).set_stroke(CORAL, 7)
        xm.move_to(px(mcx + pxv * 2.4 * CELL + 30, mcy + pyv * 2.4 * CELL))
        cross_t = jp("輪郭をまたがない", 34, CORAL).move_to(px(FIT_C[0] + 20, GRID_C[1] + 30))
        self.play(Create(crs), run_time=0.6)
        self.play(Create(xm), FadeIn(cross_t, shift=LEFT * u(8)), run_time=0.6)

        # ならした後：ひげはくっきり残る
        self.at("sharp", -0.3)
        after = CellGrid(gray_cols(Yc[ey:ey + 8, ex:ex + 8]), GRID_C, CELL, gap=2)
        cap3 = jp("ならした後", 34, INK)
        self.play(FadeOut(VGroup(crs, xm)), FadeOut(boxes), Transform(g2.cells, after.cells), retext(cap2, cap3),
                  run_time=1.0)
        self.play(Indicate(along_t, color=YELLOW, scale_factor=1.08), run_time=0.8)

        # ---- 9 か所でずれが 5% 減る ----
        self.at("used", -0.1)
        view.set_opacity(0)
        self.add(view)
        self.play(FadeOut(VGroup(b2, along_t, cross_t)), g2.cells.animate.set_opacity(0),
                  view.animate.set_opacity(1), run_time=0.4)
        self.remove(g2.cells)
        self.play(move_view(view, win=(0, 0, W, H), box=PHOTO), FadeOut(cap2), run_time=0.8)
        self.at("nine", -0.1)
        hot = [PRect(view, s_["x"], s_["y"], min(64, W - s_["x"]), min(64, H - s_["y"]), stroke_color=YELLOW,
                     stroke_width=4) for s_ in used]
        for r in hot:
            r.check_ignore = True

        def dim9(t):
            lit[:] = np.where(mask, 1.0, 1 - 0.5 * t)
            view.lit = lit
        self.play(LaggedStart(*[Create(r) for r in hot], lag_ratio=0.12), ViewAnim(view, dim9), run_time=1.3)
        self.at("less", -0.1)
        res = mix(f"明るさのずれ  {e_db:.3f} → {e_cd:.3f}", 44, INK).move_to(px(960, 800))
        self.play(FadeIn(res, shift=UP * u(8)), run_time=0.7)

        # ---- 比較表 ----
        self.at("card", -0.1)
        card = compare_card(7, center=(960, 420), new=6)
        self.play(FadeOut(res), *[TrackFade(r, 1, 0) for r in hot], FadeIn(card, shift=UP * u(30)), run_time=0.9)
        self.remove(*hot)
        self.play(add_row(card), run_time=1.4)

        # 終わり：写真だけ (S10 の最初の画面)
        self.at(self.tl["duration"] - 1.3)
        lit0 = lit.copy()

        def undim9(t):
            lit[:] = lit0 + (1 - lit0) * t
            view.lit = lit
        self.play(FadeOut(card), ViewAnim(view, undim9), run_time=1.0)
        view.lit = None
        self.finish()
