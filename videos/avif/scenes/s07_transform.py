import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from collections import Counter  # noqa: E402

import numpy as np  # noqa: E402

from vlib.data import TX_TYPE_NAMES, dec, picture_size, rgb_decoded, source_yuv, txbs  # noqa: E402
import av1  # noqa: E402,I001  (vlib.data が tools/ を読み込みの道に入れる)
from vlib.photoview import PhotoView, PRect, TrackFade, ViewAnim, move_view  # noqa: E402
from vlib.ui import add_row, compare_card, text_color_on  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)            # 写真の定位置 (S03〜S09 の始まりと終わり)
CTX = ((245, 190), 390, 260)               # 例のときに左上に残す写真
EX = (104, 184)                            # 実例の 8×8 (左から予測・傾きなし・DCT_ADST)
GC, CELL = (960, 575), 64                  # 主役の 8×8 のマス (512px)
GX0, GY0 = GC[0] - 4 * CELL, GC[1] - 4 * CELL
GAP = 14                                   # マスと棒のすき間
BAR_W, BAR_MAX = 50, 130                   # 列・行の棒 (太さ、いちばん長い棒)
VMAX = 20.0                                # 差の大きさの色の尺度
HEAT_LO = "#1e1b2c"
HEIC_X0, HEIC_BASE, HEIC_BW, HEIC_MAX = 1530, 420, 64, 210    # HEIC の 4×4 の波の棒
HEIC_DST4 = [29, 55, 74, 84]               # HEIC 編 (videos/heic/tools/hevctables.py の DST4 の 1 行目)
TBL_L, TBL_T, TBL_HW, TBL_HH, TBL_CW, TBL_CH = 450, 150, 240, 120, 260, 190    # 2×2 の表
BX0, BX1, BH = 1290, 1860, 70              # 予測の方向ごとの内訳の帯
BAND_Y = (230, 400)
TX_COL = {"DCT_DCT": "#596273", "DCT_ADST": "#d98a4e", "ADST_DCT": "#4fa8a0", "ADST_ADST": "#9b86d6"}


def swap(old, new, right=None):
    """見出しの差し替え：古い文字を消してから新しい文字を出す (2 つの文字が重なって崩れて見えないように)。
    right=(x, y) なら右端をそろえる。それ以外は古い文字の真ん中に置く"""
    if right is not None:
        new.move_to(px(*right), aligned_edge=RIGHT)
    else:
        new.move_to(old)
    return Succession(FadeOut(old, run_time=0.3), FadeIn(new, run_time=0.35))


def heat(v):
    return interpolate_color(ManimColor(HEAT_LO), ManimColor(PURPLE), float(np.clip(v / VMAX, 0, 1))).to_hex()


def rect(x0, x1, y0, y1, color, op=1.0):
    return Rectangle(width=u(max(x1 - x0, 0.5)), height=u(max(y1 - y0, 0.5)), stroke_width=0, fill_color=color,
                     fill_opacity=op).move_to(px((x0 + x1) / 2, (y0 + y1) / 2))


def col_bars(vals, k, color, op=1.0):
    """マスの上に、列ごとの縦の棒 (下端をそろえる)"""
    base = GY0 - GAP
    return VGroup(*[rect(GX0 + (j + 0.5) * CELL - BAR_W / 2, GX0 + (j + 0.5) * CELL + BAR_W / 2,
                         base - v * k, base, color, op) for j, v in enumerate(vals)])


def row_bars(vals, k, color, op=1.0):
    """マスの左に、行ごとの横の棒 (右端をそろえる)"""
    base = GX0 - GAP
    return VGroup(*[rect(base - v * k, base, GY0 + (i + 0.5) * CELL - BAR_W / 2, GY0 + (i + 0.5) * CELL + BAR_W / 2,
                         color, op) for i, v in enumerate(vals)])


def basis(kind):
    """8 点の逆変換 (復号器と同じ計算) の、いちばん低い波の形"""
    Tv = [np.array([0]) for _ in range(8)]
    Tv[0] = np.array([4096])
    return [int(v[0]) for v in av1.tx1d(Tv, kind, 3, 16)]


def wave_icon(kind, center, vertical=False, size=56):
    """表の見出しの小さな波 (4 本の棒)。vertical なら左から伸びる横の棒"""
    vals = [1, 1, 1, 1] if kind == "dct" else [0.3, 0.55, 0.8, 1.0]
    col = DIM if kind == "dct" else YELLOW
    g = VGroup()
    step, bw = size / 4, size / 4 - 4
    cx, cy = center
    for i, v in enumerate(vals):
        h = size * v
        if vertical:
            y = cy - size / 2 + (i + 0.5) * step
            g.add(rect(cx - size / 2, cx - size / 2 + h, y - bw / 2, y + bw / 2, col))
        else:
            x = cx - size / 2 + (i + 0.5) * step
            g.add(rect(x - bw / 2, x + bw / 2, cy + size / 2 - h, cy + size / 2, col))
    return g


class S07(PScene):
    def construct(self):
        d = dec()
        W, H = picture_size()
        assert (W, H) == (451, 300)
        Ys = source_yuv()[0]
        P = np.asarray(d.pred[0], np.float64)
        coded = [b for b in txbs(plane=0) if b["eob"] and not b["skip"]]
        names = Counter(TX_TYPE_NAMES[b["tx_type"]] for b in coded)
        assert (names["DCT_DCT"], names["DCT_ADST"], names["ADST_DCT"], names["ADST_ADST"], names["H_DCT"]) == \
            (339, 167, 100, 111, 4) and sum(names.values()) == 721
        n_any = names["DCT_ADST"] + names["ADST_DCT"] + names["ADST_ADST"]
        n_tbl = n_any + names["DCT_DCT"]
        assert n_any > n_tbl / 2 and n_any > 721 / 2                     # 「半分以上」

        def inside8(b):
            return b["w"] == 8 and b["h"] == 8 and b["x"] + 8 <= W and b["y"] + 8 <= H

        def err(b):
            x, y = b["x"], b["y"]
            return np.abs(Ys[y:y + 8, x:x + 8] - P[y:y + 8, x:x + 8])
        h8 = [b for b in coded if b["pred"]["mode"] == 2 and inside8(b)]
        v8 = [b for b in coded if b["pred"]["mode"] == 1 and inside8(b)]
        assert len(h8) == 25 and len(v8) == 12
        avg = sum(err(b) for b in h8) / len(h8)
        cm, rm = avg.mean(0), avg.mean(1)
        assert f"{cm.min():.1f}" == "3.8" and f"{cm.max():.1f}" == "11.6"
        assert all(np.diff(cm) > 0)                                       # 右ほど大きい
        assert 0.4 <= (rm.max() - rm.min()) / (cm.max() - cm.min()) <= 0.6   # 縦の変わり方は、その半分くらい
        vavg = sum(err(b) for b in v8) / len(v8)
        assert f"{vavg.mean(1).min():.1f}" == "5.7" and f"{vavg.mean(1).max():.1f}" == "12.9"
        hb = [b for b in coded if b["pred"]["mode"] == 2]
        vb = [b for b in coded if b["pred"]["mode"] == 1]
        hc = Counter(TX_TYPE_NAMES[b["tx_type"]] for b in hb)
        vc = Counter(TX_TYPE_NAMES[b["tx_type"]] for b in vb)
        assert (hc["DCT_ADST"], len(hb), vc["ADST_DCT"], len(vb)) == (46, 75, 17, 29)
        assert round(10 * hc["DCT_ADST"] / len(hb)) == 6 and round(10 * vc["ADST_DCT"] / len(vb)) == 6   # 6割
        ex = next(b for b in h8 if (b["x"], b["y"]) == EX)
        assert TX_TYPE_NAMES[ex["tx_type"]] == "DCT_ADST" and ex["pred"]["angle_delta"] == 0
        ex_err = err(ex)
        assert np.corrcoef(ex_err.mean(0), np.arange(8))[0, 1] > 0.95    # この例も右ほど大きい
        adst, dct = basis("adst"), basis("dct")
        assert all(np.diff(adst) > 0) and len(set(dct)) == 1

        # ---- 写真 (S06 の終わり) → 左上に小さく、実例の 8×8 ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)
        self.at("s07_01", -0.05)
        sq = PRect(view, EX[0], EX[1], 8, 8, stroke_color=YELLOW, stroke_width=4)
        sq.check_ignore = True
        self.add(sq)
        self.play(move_view(view, (0, 0, W, H), CTX), TrackFade(sq, 0, 1, rate_func=lambda a: smooth(max(0.0, (a - 0.5) / 0.5))), run_time=1.1)

        self.at("wave", -0.1)
        cols = [[heat(v) for v in row] for row in ex_err]
        nums = np.round(ex_err).astype(int)
        grid = VGroup()
        gnums = VGroup()
        for i in range(8):
            for j in range(8):
                c = Square(u(CELL - 3), stroke_width=0, fill_color=cols[i][j], fill_opacity=1)
                c.move_to(px(GX0 + (j + 0.5) * CELL, GY0 + (i + 0.5) * CELL))
                grid.add(c)
                gnums.add(mono(str(nums[i, j]), 28, text_color_on(cols[i][j])).move_to(c))
        grid.check_ignore = True
        cap = jp("元と予測の差の大きさ", 34, PURPLE).move_to(px(GC[0], GY0 + 8 * CELL + 40))
        small = grid.copy().scale(sq.width / grid.width).move_to(sq)
        self.play(ReplacementTransform(small, grid), FadeIn(cap, shift=UP * u(8)), run_time=1.0)
        self.play(FadeIn(gnums), run_time=0.6)

        # ---- HEIC の「だんだん大きくなる波」 ----
        self.at("heic", -0.1)
        hx = [HEIC_X0 + 16 + (i + 0.5) * (HEIC_BW + 14) for i in range(4)]
        hk = HEIC_MAX / max(HEIC_DST4)
        htitle = jp("HEIC の 4×4", 36, INK).move_to(px((hx[0] + hx[3]) / 2, 120))
        href = rect(HEIC_X0 - 16, HEIC_X0, HEIC_BASE - HEIC_MAX, HEIC_BASE, CYAN)
        hbars = VGroup(*[rect(x - HEIC_BW / 2, x + HEIC_BW / 2, HEIC_BASE - v * hk, HEIC_BASE, YELLOW)
                         for x, v in zip(hx, HEIC_DST4)])
        hvals = VGroup(*[mono(str(v), 30, BG).move_to(px(x, HEIC_BASE - 22)) for x, v in zip(hx, HEIC_DST4)])
        self.play(FadeIn(htitle, shift=DOWN * u(8)), GrowFromEdge(href, DOWN), run_time=0.8)
        self.at("grow", -0.1)
        self.play(LaggedStart(*[AnimationGroup(GrowFromEdge(b, DOWN), FadeIn(t)) for b, t in zip(hbars, hvals)],
                              lag_ratio=0.45), run_time=1.8)

        self.at("near", -0.1)
        self.play(Indicate(href, color=CYAN, scale_factor=1.08), run_time=0.9)
        self.at("small", -0.1)
        self.play(pop(VGroup(hbars[0], hvals[0]), 1.15, 0.7), run_time=0.7)

        # ---- 左から延ばした予測なら？ ----
        self.at("left", -0.1)
        refs = VGroup(*[rect(GX0 - GAP - 22, GX0 - GAP, GY0 + i * CELL + 2, GY0 + (i + 1) * CELL - 2, CYAN)
                        for i in range(8)])
        self.play(FadeOut(VGroup(htitle, hbars, hvals, href)), run_time=0.5)
        self.play(LaggedStart(*[GrowFromEdge(r, RIGHT) for r in refs], lag_ratio=0.08), run_time=0.8)
        arrow = Arrow(px(GX0, GY0 - 34), px(GX0 + 8 * CELL, GY0 - 34), buff=0, color=CYAN, stroke_width=8,
                      max_tip_length_to_length_ratio=0.08)
        self.play(GrowArrow(arrow), run_time=0.9)
        self.at("where", -0.1)
        self.play(pop(gnums, 1.06, 0.8), run_time=0.8)
        self.at("right", -0.1)
        self.play(Indicate(arrow, color=CYAN, scale_factor=1.06), run_time=0.9)
        self.at("rside", -0.1)
        rs = Rectangle(width=u(3 * CELL + 6), height=u(8 * CELL + 6), stroke_color=YELLOW, stroke_width=5,
                       fill_opacity=0).move_to(px(GX0 + 6.5 * CELL, GC[1]))
        self.play(Create(rs), run_time=0.7)

        # ---- 25 個の 8×8 を重ねて平均 ----
        self.at("check", -0.1)
        self.play(FadeOut(rs), FadeOut(arrow), FadeOut(refs), FadeOut(gnums), run_time=0.6)
        self.at("avg", -0.1)
        others = [b for b in h8 if b is not ex]
        marks = [PRect(view, b["x"], b["y"], 8, 8, stroke_color=YELLOW, stroke_width=2.5) for b in others]
        for m in marks:
            m.check_ignore = True
        side = view.px_per_pixel() * 8
        flyers = []
        for b in h8:
            e = float(err(b).mean())
            f = Square(u(side), stroke_width=0, fill_color=PURPLE, fill_opacity=min(0.6, e / 15))
            f.move_to(view.to_point(b["x"] + 4, b["y"] + 4))
            f.check_ignore = True
            flyers.append(f)
        self.play(LaggedStart(*[Create(m) for m in marks], lag_ratio=0.03), run_time=0.6)
        self.add(*flyers)
        cap_avg = jp(f"左から予測した 8×8  {len(h8)}個の平均", 34, PURPLE)
        avg_cols = VGroup(*[Square(u(CELL - 3), stroke_width=0, fill_color=heat(avg[i, j]), fill_opacity=1)
                            .move_to(grid[i * 8 + j]) for i in range(8) for j in range(8)])
        fly = LaggedStart(*[f.animate(path_arc=-0.5).move_to(px(*GC)).scale(8 * CELL / side).set_opacity(0)
                            for f in flyers], lag_ratio=0.04, run_time=2.2)
        build = Transform(grid, avg_cols, run_time=2.2,
                          rate_func=lambda a: rate_functions.smooth(max(0.0, (a - 0.4) / 0.6)))
        self.play(fly, build, Succession(Wait(0.6), swap(cap, cap_avg)), run_time=2.2)
        self.remove(*flyers, cap)
        cap = cap_avg

        # 列ごとの平均の棒
        self.at("col", -0.1)
        k = BAR_MAX / 12.0
        cb = col_bars(cm, k, PURPLE)
        cvals = VGroup(*[jp(f"{v:.1f}", 28, INK).next_to(b, UP, buff=u(8)) for v, b in zip(cm, cb)])
        clab = jp("列ごとの平均", 32, INK).move_to(px(GC[0], 100))
        self.play(FadeIn(clab, shift=DOWN * u(6)),
                  LaggedStart(*[AnimationGroup(GrowFromEdge(b, DOWN), FadeIn(t, shift=UP * u(6)))
                                for b, t in zip(cb, cvals)], lag_ratio=0.25), run_time=2.2)
        self.at("s07_06", -0.1)
        self.play(LaggedStart(*[pop(VGroup(b, t), 1.12, 0.5) for b, t in zip(cb, cvals)], lag_ratio=0.15),
                  run_time=1.6)
        # 行ごとの平均の棒 (ほぼ平ら)
        self.at("flat", -0.1)
        rb = row_bars(rm, k, PURPLE)
        rvals = VGroup(*[jp(f"{v:.1f}", 28, INK).next_to(b, LEFT, buff=u(8)) for v, b in zip(rm, rb)])
        rlab = jp("行ごとの平均", 32, INK).move_to(px(GX0 - GAP, GY0 - 30), aligned_edge=RIGHT)
        self.play(FadeIn(rlab, shift=DOWN * u(6)),
                  LaggedStart(*[AnimationGroup(GrowFromEdge(b, RIGHT), FadeIn(t, shift=LEFT * u(6)))
                                for b, t in zip(rb, rvals)], lag_ratio=0.15), run_time=1.3)

        # 列の幅と行の幅を比べる印
        # 幅は画面の数字 (小数 1 桁に丸めたもの) どうしの差。列 11.6 − 3.8 = 7.8、行 10.3 − 6.4 = 3.9
        cw = round(cm.max(), 1) - round(cm.min(), 1)
        rw = round(rm.max(), 1) - round(rm.min(), 1)
        assert f"{cw:.1f}" == "7.8" and f"{rw:.1f}" == "3.9"
        bx = GX0 + 8 * CELL + 26
        base_c = GY0 - GAP
        cbr = VGroup(Line(px(bx, base_c - cm.max() * k), px(bx, base_c - cm.min() * k), color=YELLOW, stroke_width=4),
                     *[Line(px(bx - 10, base_c - v * k), px(bx + 10, base_c - v * k), color=YELLOW, stroke_width=4)
                       for v in (cm.max(), cm.min())])
        cbr_t = jp(f"幅 {cw:.1f}", 32, YELLOW).move_to(px(bx + 20, base_c - (cm.max() + cm.min()) / 2 * k),
                                                        aligned_edge=LEFT)
        base_r = GX0 - GAP
        by_ = GY0 + 8 * CELL + 18
        rbr = VGroup(Line(px(base_r - rm.max() * k, by_), px(base_r - rm.min() * k, by_), color=YELLOW, stroke_width=4),
                     *[Line(px(base_r - v * k, by_ - 10), px(base_r - v * k, by_ + 10), color=YELLOW, stroke_width=4)
                       for v in (rm.max(), rm.min())])
        rbr_t = jp(f"幅 {rw:.1f}", 32, YELLOW).move_to(px(base_r - (rm.max() + rm.min()) / 2 * k, by_ + 34))
        brackets = VGroup(cbr, cbr_t, rbr, rbr_t)
        self.play(Create(cbr), FadeIn(cbr_t, shift=LEFT * u(6)), run_time=0.5)
        self.play(Create(rbr), FadeIn(rbr_t, shift=UP * u(6)), run_time=0.5)

        # ---- 横と縦で別々に波を選ぶ ----
        self.at("sep", -0.1)
        self.play(cb.animate.set_fill(opacity=0.45), rb.animate.set_fill(opacity=0.45), run_time=0.6)
        self.at("h", -0.1)
        clab2 = jp("横の波", 36, INK)
        rlab2 = jp("縦の波", 36, INK)
        self.play(swap(clab, clab2), FadeOut(cvals), FadeOut(rvals), run_time=0.65)
        self.play(swap(rlab, rlab2, (GX0 - GAP, GY0 - 30)), run_time=0.65)
        self.remove(clab, rlab)
        clab, rlab = clab2, rlab2

        self.at("hh", -0.1)
        kb = BAR_MAX / max(adst)
        ex_cols = VGroup(*[Square(u(CELL - 3), stroke_width=0, fill_color=cols[i][j], fill_opacity=1)
                           .move_to(grid[i * 8 + j]) for i in range(8) for j in range(8)])
        cap_ex = jp("この 8×8 (元と予測の差の大きさ)", 34, PURPLE)
        clab3 = jp("横：だんだん大きくなる波", 36, YELLOW)
        self.play(Transform(grid, ex_cols), swap(cap, cap_ex), FadeOut(brackets), Indicate(sq, color=YELLOW, scale_factor=1.6),
                  run_time=1.0)
        self.remove(cap)
        cap = cap_ex
        self.play(Transform(cb, col_bars(adst, kb, YELLOW)), swap(clab, clab3), run_time=1.2)
        self.remove(clab)
        clab = clab3
        self.at("vv", -0.1)
        rlab3 = jp("縦：ふつうの波", 36, INK)
        self.play(Transform(rb, row_bars(dct, kb, DIM, 0.9)), swap(rlab, rlab3, (GX0 - GAP, GY0 - 30)), run_time=1.2)
        self.remove(rlab)
        rlab = rlab3

        # ---- 写真全体で数える：2×2 の表 ----
        self.at("stat", 0.8)
        self.play(FadeOut(VGroup(grid, cb, rb, cap, clab, rlab)), TrackFade(sq, 1, 0), *[TrackFade(m, 1, 0) for m in marks],
                  view.animate.set_opacity(0), run_time=0.7)
        self.remove(view, sq, *marks)
        cx = [TBL_L + TBL_HW + (c + 0.5) * TBL_CW for c in range(2)]
        ry = [TBL_T + TBL_HH + (r + 0.5) * TBL_CH for r in range(2)]
        kinds = ("dct", "adst")
        word = {"dct": "ふつう", "adst": "だんだん"}
        heads = VGroup()
        for c, kd in enumerate(kinds):
            heads.add(wave_icon(kd, (cx[c], TBL_T + 34), size=48),
                      jp(f"横 {word[kd]}", 30, YELLOW if kd == "adst" else INK).move_to(px(cx[c], TBL_T + 92)))
        for r, kd in enumerate(kinds):
            heads.add(wave_icon(kd, (TBL_L + 30, ry[r]), vertical=True, size=48),
                      jp(f"縦 {word[kd]}", 30, YELLOW if kd == "adst" else INK).move_to(
                          px(TBL_L + 68, ry[r]), aligned_edge=LEFT))
        cells, cnums, cell_name = VGroup(), VGroup(), {}
        for r, vk in enumerate(("DCT", "ADST")):
            for c, hk_ in enumerate(("DCT", "ADST")):
                nm = f"{vk}_{hk_}"
                col = TX_COL[nm]
                cell = RoundedRectangle(corner_radius=u(10), width=u(TBL_CW - 12), height=u(TBL_CH - 12),
                                        stroke_width=0, fill_color=col, fill_opacity=1).move_to(px(cx[c], ry[r]))
                cells.add(cell)
                cnums.add(jp(str(names[nm]), 56, text_color_on(col)).move_to(cell))
                cell_name[nm] = len(cells) - 1
        self.play(LaggedStart(*[FadeIn(h, shift=DOWN * u(6)) for h in heads], lag_ratio=0.08),
                  LaggedStart(*[FadeIn(c, scale=0.9) for c in cells], lag_ratio=0.12), run_time=1.4)
        self.play(LaggedStart(*[FadeIn(n, scale=0.8) for n in cnums], lag_ratio=0.25), run_time=1.4)

        # 半分以上がどちらかに「だんだん」
        self.at("half", -0.1)
        PY, PH_ = 735, 60
        PW = 2 * TBL_CW
        PX0 = TBL_L + TBL_HW
        segs, x = VGroup(), PX0
        for nm in ("DCT_ADST", "ADST_DCT", "ADST_ADST", "DCT_DCT"):
            w = PW * names[nm] / n_tbl
            segs.add(rect(x, x + w, PY - PH_ / 2, PY + PH_ / 2, TX_COL[nm]))
            x += w
        mid = Line(px(PX0 + PW / 2, PY - PH_ / 2 - 14), px(PX0 + PW / 2, PY + PH_ / 2 + 14), color=INK, stroke_width=4)
        mid_l = jp("半分", 30, INK).move_to(px(PX0 + PW / 2, PY + PH_ / 2 + 40))
        dd = cell_name["DCT_DCT"]
        self.play(cells[dd].animate.set_fill(opacity=0.4), cnums[dd].animate.set_opacity(0.5),
                  LaggedStart(*[GrowFromEdge(s, LEFT) for s in segs], lag_ratio=0.2), run_time=1.3)
        self.play(Create(mid), FadeIn(mid_l, shift=UP * u(6)), run_time=0.6)
        self.play(pop(VGroup(segs[:3]), 1.05, 0.7), run_time=0.7)

        # 予測の方向ごとの内訳
        def band(y, cnt, hot, title):
            total = sum(cnt.values())
            g, x = VGroup(), BX0
            order = [hot] + [n for n in ("DCT_DCT", "DCT_ADST", "ADST_DCT", "ADST_ADST") if n != hot]
            hot_seg = None
            for nm in order:
                if cnt[nm] == 0:
                    continue
                w = (BX1 - BX0) * cnt[nm] / total
                s = rect(x + 1, x + w - 1, y - BH / 2, y + BH / 2, TX_COL[nm], 1.0 if nm == hot else 0.45)
                g.add(s)
                if nm == hot:
                    hot_seg = s
                x += w
            t = jp(title, 32, INK).move_to(px(BX0, y - BH / 2 - 30), aligned_edge=LEFT)
            n = jp(f"{total}個", 30, DIM).move_to(px(BX1, y - BH / 2 - 30), aligned_edge=RIGHT)
            return g, hot_seg, t, n
        self.at("match2", -0.1)
        hb_g, hb_hot, hb_t, hb_n = band(BAND_Y[0], hc, "DCT_ADST", "左から予測したブロック")
        vb_g, vb_hot, vb_t, vb_n = band(BAND_Y[1], vc, "ADST_DCT", "上から予測したブロック")
        self.play(FadeIn(hb_t, shift=DOWN * u(6)), FadeIn(hb_n, shift=DOWN * u(6)),
                  FadeIn(vb_t, shift=DOWN * u(6)), FadeIn(vb_n, shift=DOWN * u(6)), run_time=0.7)
        self.at("hmode", -0.1)
        hl = jp(f"横だけ {hc['DCT_ADST']}", 32, text_color_on(TX_COL["DCT_ADST"])).move_to(hb_hot)
        self.play(LaggedStart(*[GrowFromEdge(s, LEFT) for s in hb_g], lag_ratio=0.25), run_time=0.9)
        self.play(FadeIn(hl), pop(cells[cell_name["DCT_ADST"]], 1.06, 0.6), run_time=0.6)
        self.at("vmode", -0.1)
        vl = jp(f"縦だけ {vc['ADST_DCT']}", 32, text_color_on(TX_COL["ADST_DCT"])).move_to(vb_hot)
        self.play(LaggedStart(*[GrowFromEdge(s, LEFT) for s in vb_g], lag_ratio=0.25), run_time=0.9)
        self.play(FadeIn(vl), pop(cells[cell_name["ADST_DCT"]], 1.06, 0.6), run_time=0.6)

        self.at("fit", -0.1)
        self.play(pop(VGroup(hb_hot, hl), 1.06, 0.7), run_time=0.7)
        self.play(pop(VGroup(vb_hot, vl), 1.06, 0.7), run_time=0.7)

        # ---- 比較表 ----
        self.at("card", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        lit = np.full((H, W), 0.55, np.float32)
        view.lit = lit
        view.refresh()
        view.set_opacity(0)
        self.add(view)
        card = compare_card(5, center=(960, 420), new=4)
        self.play(FadeOut(VGroup(heads, cells, cnums, segs, mid, mid_l, hb_g, hb_t, hb_n, hl, vb_g, vb_t, vb_n, vl)),
                  view.animate.set_opacity(1), FadeIn(card, shift=UP * u(30)), run_time=0.8)
        self.play(add_row(card, run_time=1.1), run_time=1.1)

        # 終わり：写真だけ (S08 の最初の画面)
        self.at(self.tl["duration"] - 1.3)
        lit0 = lit.copy()

        def undim(t):
            lit[:] = lit0 + (1 - lit0) * t
            view.lit = lit
        self.play(FadeOut(card), ViewAnim(view, undim), run_time=1.0)
        view.lit = None
        self.finish()
