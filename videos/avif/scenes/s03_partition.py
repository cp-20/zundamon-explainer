import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import dec, picture_size, rgb_decoded  # noqa: E402
import av1tables as T  # noqa: E402  (vlib.data が tools/ を探す場所に入れる)
from vlib.photoview import LW, Grow, PhotoView, PLine, PRect, TrackFade, ViewAnim, cross_lines, grid64_lines, move_view  # noqa: E402
from vlib.ui import HEIC_COL, add_row, compare_card  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)          # 写真の定位置 (S02 の終わり・S04 の始まり)
SMALL_C, SMALL_W = (760, 480), 640       # 問いのあいだ、写真は左寄りに (格子は見えたまま)
ZBOX = ((760, 480), 640, 640)            # 64×64 に寄ったときの箱
MARGIN = 6                               # 寄ったときに 64×64 のまわりに見せる画素
MAIN = (128, 64)                         # 主役の 64×64 (まぶたにかかる)
CARD_C, CARD_W, CARD_H = (1498, 82), 400, 88       # 問いのカード (右上)
TAG_C = (1215, 82)                                 # HEIC / AV1 の札
ICON = 128
ROW_Y, PITCH, ROW_X = (228, 375), 152, 1498        # 10 通りの見本の 2 段 (右側)
YN_LY = 330                                        # HEIC の 2 択 (はい / いいえ) の札
PANEL_C, PANEL_W, PANEL_H = (1498, 302), 776, 300  # 写真の上に見本を重ねるときの暗い板
EYE_WIN_C, EYE_WIN_W = (176, 108), 132            # 目のまわりへ少し寄る窓
SIZE_COLOR = {64: "#eef0f4", 32: "#5aa7ea", 16: "#7fd18b", 8: "#e8c36a", 4: "#f08a5d"}
RECT_COL = "#ff6fb5"                     # 横長・縦長のブロック
NONE_, HORZ, VERT, SPLIT = 0, 1, 2, 3
ROW1 = [0, 1, 2, 3, 8]                    # 分割なし・横に 2・縦に 2・4 分割・横に 4 本
ROW2 = [4, 5, 6, 7, 9]                    # T 字 4 つ・縦に 4 本
USED = [0, 1, 2, 3]


class LineOp(Animation):
    """PLine の不透明度を変える (PLine は窓で切るときに不透明度を持ち直すので、FadeIn/Out ではなくこれで)"""

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


class MoveRect(Animation):
    """PRect の囲む範囲を別の範囲へ"""

    def __init__(self, rect, r, **kw):
        super().__init__(rect, **kw)
        self.r0, self.r1 = np.array(rect.r, float), np.array(r, float)

    def interpolate_mobject(self, alpha):
        self.mobject.r = tuple(self.r0 + (self.r1 - self.r0) * self.rate_func(alpha))
        self.mobject.sync()


def shape_icon(kind, center, s=ICON):
    """分割の形の見本 (10 通り)。PARTITION_NAMES の順"""
    cx, cy = center
    h = s / 2
    frame = Square(u(s), stroke_color=INK, stroke_width=5, fill_color="#232833", fill_opacity=1).move_to(px(cx, cy))

    def ln(x0, y0, x1, y1):
        return Line(px(cx + x0 * h, cy + y0 * h), px(cx + x1 * h, cy + y1 * h), stroke_color=INK, stroke_width=5)
    segs = {
        0: [],
        1: [ln(-1, 0, 1, 0)],
        2: [ln(0, -1, 0, 1)],
        3: [ln(-1, 0, 1, 0), ln(0, -1, 0, 1)],
        4: [ln(-1, 0, 1, 0), ln(0, -1, 0, 0)],          # HORZ_A：上が 2 つ
        5: [ln(-1, 0, 1, 0), ln(0, 0, 0, 1)],           # HORZ_B：下が 2 つ
        6: [ln(0, -1, 0, 1), ln(-1, 0, 0, 0)],          # VERT_A：左が 2 つ
        7: [ln(0, -1, 0, 1), ln(0, 0, 1, 0)],           # VERT_B：右が 2 つ
        8: [ln(-1, k, 1, k) for k in (-0.5, 0, 0.5)],   # HORZ_4
        9: [ln(k, -1, k, 1) for k in (-0.5, 0, 0.5)],   # VERT_4
    }[kind]
    g = VGroup(frame, *segs)
    g.frame = frame
    return g


def glow(icon, k=1.15, **kw):
    """見本の形を光らせる (線だけ黄色に。Indicate は塗りまで黄色になる)"""
    return icon.animate(rate_func=there_and_back, **kw).scale(k).set_stroke(YELLOW)


def flow_vec(angle):
    """予測の角度 (AV1 の度。90 が真上・180 が左から) → 画素が流れる向き (Manim の単位ベクトル)"""
    a = np.radians(angle)
    return np.array([-np.cos(a), -np.sin(a), 0.0])


class S03(PScene):
    def construct(self):
        W, H = picture_size()
        assert (W, H) == (451, 300)
        d = dec()
        parts = d.partitions
        X0, Y0 = MAIN
        pmap = {(p["x"], p["y"], p["size"]): p for p in parts}
        # 調べてある分け方 (台詞と画面の流れ)
        assert pmap[(X0, Y0, 64)]["partition"] == SPLIT and pmap[(X0, Y0, 32)]["partition"] == SPLIT
        assert pmap[(144, 80, 16)]["partition"] == HORZ                      # まぶたの輪郭
        assert all(pmap[(x, y, 32)]["partition"] == SPLIT for x, y in ((160, 64), (128, 96), (160, 96)))
        assert pmap[(160, 96, 16)]["partition"] == VERT                      # 右下に「縦に 2 分割」
        inside = [p for p in parts if X0 <= p["x"] < X0 + 64 and Y0 <= p["y"] < Y0 + 64]
        assert all(p["coded"] == "symbol" for p in inside)
        assert {p["partition"] for p in inside} == {NONE_, HORZ, VERT, SPLIT}
        assert {p["partition"] for p in parts if p["coded"] == "symbol"} == {NONE_, HORZ, VERT, SPLIT}   # 「4種類だけ」
        rect_blocks = [b for b in d.blocks if b["w"] != b["h"]]
        assert len(rect_blocks) == 44
        # 横長・縦長に分けると選んだもの (写真の端で自動的に決まったものは除く)
        chosen = []
        for p in parts:
            if p["partition"] in (HORZ, VERT) and p["coded"] == "symbol":
                s, x, y = p["size"], p["x"], p["y"]
                halves = ((x, y, s, s // 2), (x, y + s // 2, s, s // 2)) if p["partition"] == HORZ else \
                    ((x, y, s // 2, s), (x + s // 2, y, s // 2, s))
                for r in halves:
                    assert any((b["x"], b["y"], b["w"], b["h"]) == r for b in rect_blocks)
                    chosen.append(r)
        assert len(chosen) == 32 and all(x + w <= W and y + h <= H for x, y, w, h in chosen)
        # まぶたの 16×16 の上下の予測 (実際の向き)
        lid = []
        for y in (80, 88):
            b = next(b for b in d.blocks if (b["x"], b["y"]) == (144, y))
            assert (b["w"], b["h"]) == (16, 8) and 1 <= b["y_mode"] <= 8
            lid.append(T.Mode_To_Angle[b["y_mode"]] + 3 * b["angle_delta_y"])
        assert lid == [186, 206]

        # ---- 写真 (S02 の終わり) ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)

        # ---- 64×64 の格子 ----
        self.at("grid", -0.1)
        g64 = grid64_lines(view, W, H, frac=0)
        self.add(*g64)
        self.play(LaggedStart(*[Grow(ln, run_time=0.9) for ln in g64], lag_ratio=0.08), run_time=1.6)

        # ---- HEIC：4分割する？ (2 択) ----
        self.at("heic", -0.1)
        sh = SMALL_W * H / W
        tag = jp("HEIC", 42, HEIC_COL).move_to(px(*TAG_C))
        self.play(move_view(view, (0, 0, W, H), (SMALL_C, SMALL_W, sh)), FadeIn(tag, shift=DOWN * u(8)), run_time=1.0)
        self.at("q", -0.1)
        card = RoundedRectangle(corner_radius=u(18), width=u(CARD_W), height=u(CARD_H), stroke_color=YELLOW,
                                stroke_width=3, fill_color="#232833", fill_opacity=1).move_to(px(*CARD_C))
        card_t = jp("4分割する？", 46, INK).move_to(card)
        self.play(FadeIn(card, shift=LEFT * u(14)), FadeIn(card_t, shift=LEFT * u(14)), run_time=0.6)
        self.at("ans", -0.1)
        slot = {}
        for row, ks in zip(ROW_Y, (ROW1, ROW2)):
            for i, k in enumerate(ks):
                slot[k] = (ROW_X + (i - 2) * PITCH, row)
        ic = {k: shape_icon(k, slot[k]) for k in range(10)}
        yn = VGroup(jp("はい", 40, BLUE).move_to(px(slot[SPLIT][0], YN_LY)),
                    jp("いいえ", 40, CORAL).move_to(px(slot[NONE_][0], YN_LY)))
        self.play(LaggedStart(AnimationGroup(FadeIn(ic[SPLIT], shift=UP * u(10)), FadeIn(yn[0], shift=UP * u(10))),
                              AnimationGroup(FadeIn(ic[NONE_], shift=UP * u(10)), FadeIn(yn[1], shift=UP * u(10))),
                              lag_ratio=0.5), run_time=1.0)

        # ---- AV1：どう分割する？ (10 通り) ----
        self.at("av1", -0.1)
        tag2 = jp("AV1", 42, YELLOW)
        self.play(retext(tag, tag2), FadeOut(yn), run_time=0.6)
        self.at("shape", -0.1)
        self.play(retext(card_t, jp("どう分割する？", 46, INK)), run_time=0.7)
        self.play(pop(VGroup(card, card_t), 1.06, 0.6), run_time=0.6)

        self.at("ten", -0.1)
        icons = VGroup(*[ic[k] for k in range(10)])
        others = [k for k in (1, 2, 8, 4, 5, 6, 7, 9)]
        self.play(pop(VGroup(ic[NONE_], ic[SPLIT]), 1.08, 0.5), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(ic[k], scale=0.7) for k in others], lag_ratio=0.12), run_time=1.4)
        self.at("many", -0.1)
        self.play(LaggedStart(*[glow(ic[k], 1.08) for k in range(10)], lag_ratio=0.08),
                  run_time=1.6)

        # ---- まぶたにかかる 64×64 へ寄る ----
        self.at("walk", -0.1)
        win = (X0 - MARGIN, Y0 - MARGIN, X0 + 64 + MARGIN, Y0 + 64 + MARGIN)
        lit = np.ones((H, W), np.float32)

        def dim_out(t):
            lit[:] = 1 - 0.6 * t
            lit[Y0:Y0 + 64, X0:X0 + 64] = 1
            view.lit = lit
        cur = PRect(view, X0, Y0, 64, 64, stroke_color=YELLOW, stroke_width=6)
        cur.set_stroke(opacity=0)
        self.add(cur)
        self.play(move_view(view, win, ZBOX), ViewAnim(view, dim_out), TrackFade(cur, 0, 1), FadeOut(tag), run_time=1.6)

        def crosses(x, y, s):
            ls = cross_lines(view, x, y, s, W, H, SIZE_COLOR[s // 2], LW[s // 2])
            self.add(*ls)
            self.bring_to_front(cur)
            return ls

        def half_line(p, k=None):
            """HORZ / VERT の線 (ピンク)"""
            x, y, s = p["x"], p["y"], p["size"]
            if p["partition"] == HORZ:
                if y + s // 2 >= H:
                    return []
                ln = PLine(view, (x, y + s // 2), (min(x + s, W), y + s // 2), frac=0, stroke_color=RECT_COL,
                           stroke_width=LW[s // 2] + 1)
            else:
                if x + s // 2 >= W:
                    return []
                ln = PLine(view, (x + s // 2, y), (x + s // 2, min(y + s, H)), frac=0, stroke_color=RECT_COL,
                           stroke_width=LW[s // 2] + 1)
            self.add(ln)
            self.bring_to_front(cur)
            return [ln]

        mine = []      # 主役の 64×64 で引いた線
        self.at("a64", -0.1)
        ls = crosses(X0, Y0, 64)
        mine += ls
        self.play(glow(ic[SPLIT], 1.2), *[Grow(ln) for ln in ls], run_time=0.9)
        self.at("a32", -0.1)
        self.play(MoveRect(cur, (X0, Y0, 32, 32)), run_time=0.4)
        ls = crosses(X0, Y0, 32)
        mine += ls
        self.play(glow(ic[SPLIT], 1.2), *[Grow(ln) for ln in ls], run_time=0.8)

        # まぶたの輪郭の 16×16
        self.at("lid", -0.1)
        self.play(MoveRect(cur, (144, 80, 16, 16)), run_time=0.6)
        self.play(Indicate(cur, color=YELLOW, scale_factor=1.15), run_time=0.8)
        self.at("horz", -0.1)
        ls = half_line(pmap[(144, 80, 16)])
        mine += ls
        self.play(glow(ic[HORZ], 1.2), *[Grow(ln) for ln in ls], run_time=0.9)
        self.at("fit", -0.1)
        self.play(pop(ls[0], 1.25, 0.7), run_time=0.7)

        # 上と下で別々の予測
        self.at("each", -0.1)
        arrows = VGroup()
        for (y, ang) in zip((80, 88), lid):
            c = view.to_point(152, y + 4)
            v = flow_vec(ang)
            a = Arrow(c - v * u(46), c + v * u(46), buff=0, color=CYAN, stroke_width=8, tip_length=u(22),
                      max_tip_length_to_length_ratio=0.4, max_stroke_width_to_length_ratio=20)
            arrows.add(a)
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.5), run_time=1.1)

        # 残りの 32×32
        self.at("rest", -0.1)
        for i, (x, y) in enumerate(((160, 64), (128, 96), (160, 96))):
            ls = crosses(x, y, 32)
            mine += ls
            self.play(Succession(MoveRect(cur, (x, y, 32, 32), run_time=0.2),
                                 AnimationGroup(glow(ic[SPLIT], 1.15),
                                                *[Grow(ln) for ln in ls], run_time=0.4)),
                      *([FadeOut(arrows, run_time=0.3)] if i == 0 else []), run_time=0.6)
        ls = half_line(pmap[(160, 96, 16)])
        mine += ls
        self.play(MoveRect(cur, (160, 96, 16, 16), run_time=0.2), run_time=0.2)
        self.play(glow(ic[VERT], 1.2), *[Grow(ln) for ln in ls], run_time=0.4)

        # ---- 写真全体 ----
        self.at("s03_10", -0.1)

        def undim(t):
            lit[:] = 0.4 + 0.6 * t
            lit[Y0:Y0 + 64, X0:X0 + 64] = 1
            view.lit = lit
        self.play(move_view(view, (0, 0, W, H), PHOTO), ViewAnim(view, undim), TrackFade(cur, 1, 0),
                  FadeOut(icons), FadeOut(VGroup(card, card_t)), run_time=1.3)
        self.remove(cur)
        view.lit = None

        self.at("all", -0.1)
        levels = {64: [], 32: [], 16: [], 8: []}
        for p in parts:
            if X0 <= p["x"] < X0 + 64 and Y0 <= p["y"] < Y0 + 64:
                continue
            s = p["size"]
            if p["partition"] == SPLIT:
                ls = cross_lines(view, p["x"], p["y"], s, W, H, SIZE_COLOR[s // 2], LW[s // 2])
                self.add(*ls)
                levels[s] += ls
            elif p["partition"] in (HORZ, VERT):
                levels[s] += half_line(p)
        for k in (64, 32, 16, 8):
            self.play(*[Grow(ln) for ln in levels[k]], run_time=0.5, rate_func=rate_functions.ease_out_cubic)
        all_lines = g64 + mine + [ln for k in levels for ln in levels[k]]

        # ---- 横長・縦長のブロック ----
        self.at("rect", -0.1)
        mask = np.zeros((H, W), bool)
        for x, y, w, h in chosen:
            mask[y:y + h, x:x + w] = True
        lit = np.ones((H, W), np.float32)

        def spot(t):
            lit[:] = np.where(mask, 1.0, 1 - 0.55 * t)
            view.lit = lit
        hot = [PRect(view, *r, stroke_color=RECT_COL, stroke_width=5) for r in chosen]
        for r in hot:
            r.check_ignore = True          # 写真の上の線 (写真の一部として見せる)
        self.play(ViewAnim(view, spot), LineOp(all_lines, 0.45), LaggedStart(*[Create(r) for r in hot], lag_ratio=0.03),
                  run_time=1.2)
        self.at("where", -0.1)
        ew = EYE_WIN_W
        eh = ew * PHOTO[2] / PHOTO[1]
        ewin = (EYE_WIN_C[0] - ew / 2, EYE_WIN_C[1] - eh / 2, EYE_WIN_C[0] + ew / 2, EYE_WIN_C[1] + eh / 2)
        outside = [r for r, (x, y, w, h) in zip(hot, chosen)
                   if not (x >= ewin[0] and y >= ewin[1] and x + w <= ewin[2] and y + h <= ewin[3])]
        self.play(move_view(view, ewin, PHOTO), *[TrackFade(r, 1, 0, run_time=0.5) for r in outside], run_time=1.6)
        self.remove(*outside)
        hot = [r for r in hot if r not in outside]

        # ---- 使われたのは 4 種類だけ ----
        self.at("honest", -0.1)
        lit0 = lit.copy()

        def dim_all(t):
            lit[:] = lit0 + (0.4 - lit0) * t
            view.lit = lit
        self.play(move_view(view, (0, 0, W, H), PHOTO), ViewAnim(view, dim_all), LineOp(all_lines, 0),
                  *[TrackFade(r, 1, 0) for r in hot], run_time=1.2)
        self.remove(*all_lines, *hot)
        panel = RoundedRectangle(corner_radius=u(16), width=u(PANEL_W), height=u(PANEL_H), stroke_color="#3a4050",
                                 stroke_width=2, fill_color="#1b1e26", fill_opacity=0.95).move_to(px(*PANEL_C))
        self.play(FadeIn(panel), LaggedStart(*[FadeIn(ic[k], scale=0.8) for k in range(10)], lag_ratio=0.06),
                  run_time=1.0)
        self.at("four", -0.1)
        row2 = VGroup(*[ic[k] for k in range(10) if k not in USED])
        row1 = VGroup(*[ic[k] for k in USED])
        self.play(row2.animate.set_opacity(0.22), run_time=0.8)
        self.play(LaggedStart(*[glow(ic[k], 1.12) for k in USED], lag_ratio=0.5),
                  run_time=3.0)

        # T 字・細長い 4 分割は、時間をかける設定で試される
        self.at("slow", -0.1)
        self.play(*[pop(ic[k], 1.1, 0.7) for k in (4, 5, 6, 7)], run_time=0.7)
        self.play(*[pop(ic[k], 1.1, 0.7) for k in (8, 9)], run_time=0.7)
        self.at("time", -0.1)
        self.play(*[pop(ic[k], 1.08, 0.8) for k in range(4, 10)], run_time=0.8)
        self.at("more", -0.1)
        self.play(row2.animate(rate_func=there_and_back).set_opacity(0.85), run_time=1.6)
        row2.set_opacity(0.22)

        # ---- 比較表 ----
        self.at("card", -0.1)
        cmp_ = compare_card(1, center=(960, 420), new=0)
        self.play(FadeOut(row1), FadeOut(row2), FadeOut(panel), FadeIn(cmp_, shift=UP * u(30)), run_time=0.9)
        self.play(add_row(cmp_), run_time=1.4)

        # 終わり：写真だけ (S04 の最初の画面)
        self.at(self.tl["duration"] - 1.3)
        lit1 = lit.copy()

        def back(t):
            lit[:] = lit1 + (1 - lit1) * t
            view.lit = lit
        self.play(FadeOut(cmp_), ViewAnim(view, back), run_time=1.0)
        view.lit = None
        self.finish()

