import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import dec, fmt, picture_size, pixels, rgb_decoded  # noqa: E402
import hevctables as HT  # noqa: E402  (vlib.data が tools/ を探す場所に入れる)
from vlib.photoview import PhotoView, PRect, ViewAnim, move_view  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

# S04 の終わり
WH = (136, 272, 4)
WH_C, WH_O = (700, 430), (1225, 430)
WH_BOX = 510
WH_WIN = (130, 268, 142, 280)
# このシーン
EX = (132, 264, 4)                        # 候補の見本 (左も上も向き 5、自分は 4 = 2 番目の候補)
VBOX = ((700, 470), 560, 560)
VWIN = (123, 255, 145, 277)
PX = 1240                                  # 右の札の中心
CHIP_W, CHIP_H, CHIP_GAP = 44, 54, 6


class MoveRect(Animation):
    def __init__(self, rect, r, **kw):
        super().__init__(rect, **kw)
        self.r0, self.r1 = np.array(rect.r, float), np.array(r, float)

    def interpolate_mobject(self, alpha):
        self.mobject.r = tuple(self.r0 + (self.r1 - self.r0) * self.rate_func(alpha))
        self.mobject.sync()


def flow_dir(m):
    a = HT.INTRA_ANGLE[m] / 32
    return np.array([-a, 1.0]) if m >= 18 else np.array([1.0, -a])


def vec(d):
    d = np.asarray(d, float)
    d = d / np.hypot(*d)
    return np.array([d[0], -d[1], 0])


def mode_glyph(m, length, color, width=6):
    """向きの矢印 (角度の予想) か、プラナー・平均の丸"""
    if m < 2:
        return Circle(radius=u(length * 0.16), stroke_color=color, stroke_width=width * 0.7)
    v = vec(flow_dir(m)) * u(length) / 2
    return Arrow(-v, v, buff=0, color=color, stroke_width=width, tip_length=u(length * 0.32),
                 max_tip_length_to_length_ratio=0.5, max_stroke_width_to_length_ratio=30)


def chip(b, color=None, size=34):
    on = color or (YELLOW if b == "1" else "#3a3f4c")
    box = RoundedRectangle(corner_radius=u(8), width=u(CHIP_W), height=u(CHIP_H), stroke_width=0, fill_color=on,
                           fill_opacity=1)
    t = mono(b, size, BG if on in (YELLOW, CYAN, CORAL) else INK).move_to(box)
    g = VGroup(box, t)
    g.box, g.t = box, t
    return g


def chip_row(bits, center, colors=None):
    g = VGroup(*[chip(b, (colors or {}).get(i)) for i, b in enumerate(bits)])
    g.arrange(RIGHT, buff=u(CHIP_GAP)).move_to(px(*center))
    return g


class S05(PScene):
    def construct(self):
        d = dec()
        W, H = picture_size()
        pus = [p for c in d.cus for p in c["pus"]]
        assert len(pus) == 1104
        hits = [p for p in pus if p["mpm"]]
        assert len(hits) == 654 and round(len(hits) / len(pus) * 10) == 6          # 6 割
        assert 2 ** 5 == 32 < 35 <= 2 ** 6                                          # 35 通りは 6 ビット
        bins = sum((2 if p["mpm_idx"] == 0 else 3) if p["mpm"] else 1 + 5 for p in pus)
        avg = bins / len(pus)
        assert f"{avg:.1f}" == "3.9" and round(avg) == 4

        def pu_at(x, y):
            return next(p for p in pus if p["x"] <= x < p["x"] + p["size"] and p["y"] <= y < p["y"] + p["size"])
        wpu = pu_at(*WH[:2])
        ex = pu_at(*EX[:2])
        assert (ex["x"], ex["y"], ex["size"]) == EX
        lnb, anb = pu_at(EX[0] - 1, EX[1]), pu_at(EX[0], EX[1] - 1)
        assert lnb["mode"] == anb["mode"] == 5
        a = lnb["mode"]
        cand = [a, 2 + ((a + 29) % 32), 2 + ((a - 2 + 1) % 32)]
        assert ex["cand"] == cand == [5, 4, 6] and ex["mpm"] and ex["mpm_idx"] == 1 and ex["mode"] == 4
        idx_bits = {0: "0", 1: "10", 2: "11"}

        # ---- S04 の終わり ----
        wbase = rgb_decoded().astype(np.float32).copy()
        prgb = rgb_decoded(stage="pred")
        wx, wy, wn = WH
        wbase[wy:wy + wn, wx:wx + wn] = prgb[wy:wy + wn, wx:wx + wn]
        view = PhotoView(wbase, WH_C, WH_BOX, WH_BOX, win=WH_WIN)
        view.check_ignore = True
        cur = PRect(view, wx, wy, wn, wn, stroke_color=YELLOW, stroke_width=5)
        refs = PRect(view, wx - 1, wy, 1, 2 * wn, stroke_color=CYAN, stroke_width=4, fill_color=CYAN, fill_opacity=0.15)
        refs.check_ignore = True
        orig = PhotoView(pixels("cat")[..., :3], WH_O, WH_BOX, WH_BOX, win=WH_WIN)
        orig.check_ignore = True
        ocur = PRect(orig, wx, wy, wn, wn, stroke_color=YELLOW, stroke_width=5)
        lab_pr = jp("予想", 36, CYAN).move_to(px(WH_C[0], WH_C[1] - WH_BOX / 2 - 36))
        lab_or = jp("元", 36, INK).move_to(px(WH_O[0], WH_O[1] - WH_BOX / 2 - 36))
        lab_pr.check_ignore = lab_or.check_ignore = True     # S04 の終わりから続けて出ている文字
        self.add(view, orig, cur, refs, ocur, lab_pr, lab_or)

        # ---- 向きの番号は 6 ビット ----
        self.at("s05_01", -0.05)
        fin = rgb_decoded().astype(np.float32)
        blk0 = wbase[wy:wy + wn, wx:wx + wn].copy()

        def back(t):
            wbase[wy:wy + wn, wx:wx + wn] = blk0 * (1 - t) + fin[wy:wy + wn, wx:wx + wn] * t
        self.play(orig.animate.set_opacity(0), FadeOut(VGroup(ocur, lab_pr, lab_or, refs)), run_time=0.6)
        self.remove(orig)
        self.play(move_view(view, VWIN, VBOX), ViewAnim(view, back), run_time=1.2)

        pp = view.px_per_pixel()

        def center(p):
            return view.to_point(p["x"] + p["size"] / 2, p["y"] + p["size"] / 2)
        # 見える予想のブロックすべて
        vis = [p for p in pus if p["x"] >= VWIN[0] and p["y"] >= VWIN[1] and p["x"] + p["size"] <= VWIN[2]
               and p["y"] + p["size"] <= VWIN[3]]
        glyphs = {}
        for p in vis:
            g = mode_glyph(p["mode"], p["size"] * pp * 0.62, INK, 4.5 if p["size"] == 4 else 6).move_to(center(p))
            glyphs[(p["x"], p["y"])] = g
        frames = VGroup(*[PRect(view, p["x"], p["y"], p["size"], p["size"], stroke_color="#f08a5d" if p["size"] == 4 else
                                "#e8c36a", stroke_width=2) for p in vis])
        frames.check_ignore = True
        backs = VGroup(*[Square(u(p["size"] * pp), stroke_width=0, fill_color=BG, fill_opacity=0.45).move_to(center(p))
                         for p in vis])
        backs.check_ignore = True

        my = glyphs[(wx, wy)]
        my.set_color(YELLOW)
        self.at("bits", -0.1)
        num = mono(str(wpu["mode"]), 48, YELLOW).move_to(px(PX - 50, 190))
        big = mode_glyph(wpu["mode"], 60, YELLOW, 7).move_to(px(PX + 40, 190))
        self.play(FadeIn(backs[[i for i, p in enumerate(vis) if (p["x"], p["y"]) == (wx, wy)][0]]), GrowArrow(my),
                  ReplacementTransform(my.copy(), big), FadeIn(num, shift=UP * u(8)), run_time=0.7)
        self.at("six", -0.1)
        six = chip_row(format(wpu["mode"], "06b"), (PX, 290))
        lab6 = mix("6ビット", 36, INK).move_to(px(PX, 362))
        self.play(LaggedStart(*[FadeIn(c, shift=DOWN * u(10)) for c in six], lag_ratio=0.1), FadeIn(lab6), run_time=0.8)

        # ブロックごとに 6 ビット
        self.at("each", -0.1)
        others = [glyphs[(p["x"], p["y"])] for p in vis if (p["x"], p["y"]) != (wx, wy)]
        self.play(FadeIn(backs), LaggedStart(*[GrowArrow(g) if isinstance(g, Arrow) else Create(g) for g in others],
                                             lag_ratio=0.03), run_time=1.3)
        self.play(pop(six, 1.12, 0.6), run_time=0.6)

        # ---- 左と上を見る ----
        self.at("nb", -0.1)
        my.set_color(INK)
        self.play(FadeOut(VGroup(six, lab6, num, big)), my.animate.set_color(INK),
                  MoveRect(cur, (EX[0], EX[1], EX[2], EX[2])), run_time=0.7)
        exg = glyphs[(ex["x"], ex["y"])]
        hl = [PRect(view, q["x"], q["y"], q["size"], q["size"], stroke_color=CYAN, stroke_width=5) for q in (lnb, anb)]
        ng = [glyphs[(q["x"], q["y"])] for q in (lnb, anb)]
        exq = jp("？", 64, YELLOW).move_to(center(ex))
        self.play(FadeOut(exg), FadeIn(exq), *[Create(h) for h in hl], *[g.animate.set_color(CYAN) for g in ng],
                  run_time=0.8)
        self.at("similar", -0.1)
        self.play(*[pop(g, 1.35, 0.7) for g in ng], run_time=0.7)

        # 候補 3 つ
        self.at("cand", -0.1)
        head = jp("候補", 34, INK).move_to(px(PX, 150))
        slots, sg, sn = VGroup(), [], []
        for i, m in enumerate(cand):
            c = (PX + (i - 1) * 130, 250)
            box = RoundedRectangle(corner_radius=u(14), width=u(110), height=u(110), stroke_color=DIM, stroke_width=3,
                                   fill_color="#232833", fill_opacity=1).move_to(px(*c))
            slots.add(box)
            sg.append(mode_glyph(m, 72, CYAN, 7).move_to(px(c[0], c[1] - 6)))
            sn.append(mono(str(m), 30, DIM).next_to(box, DOWN, buff=u(8)))
        self.play(FadeIn(head), LaggedStart(*[FadeIn(b, scale=0.8) for b in slots], lag_ratio=0.15), run_time=0.7)
        twin = sg[0].copy()
        self.play(ReplacementTransform(ng[0].copy(), sg[0]), ReplacementTransform(ng[1].copy(), twin),
                  FadeIn(sn[0]), run_time=0.8)
        self.remove(twin)
        self.play(ReplacementTransform(sg[0].copy(), sg[1]), ReplacementTransform(sg[0].copy(), sg[2]),
                  FadeIn(sn[1]), FadeIn(sn[2]), run_time=0.8)

        # ---- 書き方の決まり ----
        RX_L, RX_C = 1182, 1325
        self.at("hit", -0.1)
        r1t = jp("候補にある", 36, INK)
        r1t.move_to(px(RX_L - 20, 470), aligned_edge=RIGHT)
        r1c = VGroup(chip("1"), mix("＋ 何番目", 36, DIM)).arrange(RIGHT, buff=u(14))
        r1c.move_to(px(RX_L, 470), aligned_edge=LEFT)
        self.play(FadeIn(r1t, shift=UP * u(8)), FadeIn(r1c, shift=UP * u(8)), run_time=0.6)
        self.at("which", -0.1)
        self.play(slots[1].animate.set_stroke(YELLOW, 5), FadeOut(exq), run_time=0.5)
        arr_in = sg[1].copy()
        arr_in.generate_target()
        arr_in.target.set_color(YELLOW).scale(0.85).move_to(center(ex))
        self.play(MoveToTarget(arr_in, path_arc=0.6), run_time=0.8)
        ex_bits = chip_row("1" + idx_bits[ex["mpm_idx"]], (PX, 400), {1: CYAN, 2: CYAN})
        self.play(ReplacementTransform(r1c[0].copy(), ex_bits[0]), FadeIn(VGroup(*ex_bits[1:]), shift=DOWN * u(8)),
                  run_time=0.6)

        self.at("miss", -0.1)
        r2t = jp("候補にない", 36, INK)
        r2t.move_to(px(RX_L - 20, 600), aligned_edge=RIGHT)
        r2c = chip_row("0?????", (RX_C, 600), {i: "#3a3f4c" for i in range(1, 6)})
        r2c.move_to(px(RX_L, 600), aligned_edge=LEFT)
        self.play(FadeIn(r2t, shift=UP * u(8)), FadeIn(r2c[0], shift=UP * u(8)), run_time=0.6)
        self.at("rest", -0.1)
        lab32 = mix("32通り", 36, DIM).next_to(VGroup(*r2c[1:]), DOWN, buff=u(12))
        self.play(LaggedStart(*[FadeIn(c, shift=DOWN * u(8)) for c in r2c[1:]], lag_ratio=0.1), FadeIn(lab32),
                  run_time=0.8)

        # ---- この写真では ----
        self.at("real", -0.1)
        stuff = VGroup(cur, frames, backs, *glyphs.values(), *hl, arr_in, head, slots, *sg, *sn, r1t, r1c, r2t, r2c, lab32, ex_bits)
        self.play(FadeOut(stuff), view.animate.set_opacity(0), run_time=0.5)
        self.remove(view, *stuff)
        BX0, BX1, BY, BH = 480, 1440, 470, 72
        tot = len(pus)
        xs = BX0 + (BX1 - BX0) * len(hits) / tot
        full = Rectangle(width=u(BX1 - BX0), height=u(BH), stroke_width=0, fill_color="#3a3f4c", fill_opacity=1)
        full.move_to(px((BX0 + BX1) / 2, BY))
        lab_t = mix(f"{fmt(tot)}個", 36, INK).next_to(full, UP, buff=u(16))
        self.play(GrowFromEdge(full, LEFT), FadeIn(lab_t), run_time=0.7)
        self.at("rate", -0.1)
        hseg = Rectangle(width=u(xs - BX0 - 3), height=u(BH), stroke_width=0, fill_color=CYAN, fill_opacity=1)
        hseg.move_to(px((BX0 + xs) / 2 - 1.5, BY))
        mseg = Rectangle(width=u(BX1 - xs - 3), height=u(BH), stroke_width=0, fill_color=CORAL, fill_opacity=1)
        mseg.move_to(px((xs + BX1) / 2 + 1.5, BY))
        lh = mix(f"当たり {fmt(len(hits))}", 36, CYAN).move_to(px((BX0 + xs) / 2, BY + 74))
        lm = mix(f"外れ {fmt(tot - len(hits))}", 36, CORAL).move_to(px((xs + BX1) / 2, BY + 74))
        self.play(GrowFromEdge(hseg, LEFT), GrowFromEdge(mseg, RIGHT), run_time=0.9)
        self.remove(full)
        self.play(FadeIn(lh, shift=UP * u(8)), FadeIn(lm, shift=UP * u(8)), run_time=0.5)
        self.play(pop(VGroup(hseg, lh), 1.05, 0.6), run_time=0.6)

        # ---- 平均のビット数 ----
        self.at("avg", -0.1)
        UNIT_B, AX = 125, 650
        rows = []
        for i, (val, lab, col) in enumerate(((6, "6ビット", DIM), (avg, f"平均 {avg:.1f}", CYAN))):
            y = 720 + i * 90
            r = Rectangle(width=u(UNIT_B * val), height=u(48), stroke_width=0, fill_color=col, fill_opacity=1)
            r.move_to(px(AX + UNIT_B * val / 2, y))
            t = mix(lab, 36, INK if i == 0 else CYAN).move_to(px(AX - 20, y), aligned_edge=RIGHT)
            t.next_to(px(AX - 18, y), LEFT, buff=0)
            rows.append((r, t))
        ticks = VGroup(*[Line(px(AX + UNIT_B * k, 680), px(AX + UNIT_B * k, 850), stroke_color="#2a2e38",
                              stroke_width=2) for k in range(1, 7)])
        ticks.check_ignore = True
        self.play(FadeIn(ticks), GrowFromEdge(rows[0][0], LEFT), FadeIn(rows[0][1]), run_time=0.8)
        self.play(GrowFromEdge(rows[1][0], LEFT), FadeIn(rows[1][1]), run_time=1.0)
        self.at("four", -0.1)
        self.play(pop(VGroup(*rows[1]), 1.08, 0.7), run_time=0.7)

        self.at("wow", 0.4)
        self.play(Indicate(rows[1][0], color=YELLOW, scale_factor=1.04), run_time=0.9)

        # ---- 終わり：空に ----
        self.at(self.tl["duration"] - 0.9)
        self.play(FadeOut(VGroup(hseg, mseg, lh, lm, lab_t, ticks, *[m for r in rows for m in r])), run_time=0.7)
        self.finish()
