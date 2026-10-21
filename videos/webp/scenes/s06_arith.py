import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import heapq  # noqa: E402
import math  # noqa: E402

import numpy as np  # noqa: E402

from vlib.catview import CatView, window_around, zoom  # noqa: E402
from vlib.data import MAIN_MB, all_levels, bits_of, decisions, fmt, mb, vp8_info, y_orig  # noqa: E402
from zunda.fx import pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NEUTRAL = "#2c3240"
BX0, BX1, BY, BH = 510, 1410, 560, 80      # 算術符号の帯
GY, GH = 680, 24                           # 実際に残った幅 (もとの帯の尺度)
VIEW_C, VIEW_W, VIEW_H = (700, 230), 420, 280
STRIP_W, STRIP_C = 1040, (960, 520)        # S05 の終わりの帯
BANDS = [0, 1, 2, 3, 6, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 7]
MX, MY = MAIN_MB
X0, Y0 = MX * 16, MY * 16


def bx(f):
    return BX0 + (BX1 - BX0) * f


def rect(x0, x1, y, h, color, op=1.0):
    w = max(x1 - x0, 0.5)
    return Rectangle(width=u(w), height=u(h), stroke_width=0, fill_color=color, fill_opacity=op).move_to(
        px((x0 + x1) / 2, y))


def huffman(freqs):
    """記号の出る数 → 符号 (長さはハフマン、並びは正準の割り当て)"""
    heap = [(f, i, [i]) for i, f in enumerate(freqs)]
    heapq.heapify(heap)
    n = [0] * len(freqs)
    cnt = len(freqs)
    while len(heap) > 1:
        f1, _, a = heapq.heappop(heap)
        f2, _, b = heapq.heappop(heap)
        for s in a + b:
            n[s] += 1
        heapq.heappush(heap, (f1 + f2, cnt, a + b))
        cnt += 1
    order = sorted(range(len(freqs)), key=lambda i: (n[i], i))
    codes, code, prev = {}, 0, n[order[0]]
    for i in order:
        code <<= n[i] - prev
        prev = n[i]
        codes[i] = format(code, f"0{n[i]}b")
        code += 1
    return [codes[i] for i in range(len(freqs))]


def mixc(a, b, t):
    return interpolate_color(ManimColor(a), ManimColor(b), float(np.clip(t, 0, 1)))


class DecAnim(Animation):
    """判定の列 log[i0:i1] にそって、帯を分けて・選んで・選んだ所を全体に拡大する。下に実際の幅、右に数"""

    def __init__(self, bar, gauge, counters, log, cum, i0, i1, **kw):
        self.bar, self.gauge, self.counters = bar, gauge, counters
        self.log, self.cum, self.i0, self.i1 = log, cum, i0, i1
        super().__init__(Group(bar, gauge, counters), rate_func=linear, **kw)

    def interpolate_mobject(self, alpha):
        n = self.i1 - self.i0
        a = alpha * n
        i = min(self.i0 + int(a), self.i1 - 1)
        s = a - (i - self.i0) if alpha < 1 else 1.0
        p, bit = self.log[i][0], self.log[i][1]
        f = p / 256
        lo, w = self.cum[i]
        lo2, w2 = self.cum[i + 1]
        c_in = smooth(min(s / 0.35, 1))
        dim = smooth(np.clip((s - 0.38) / 0.17, 0, 1))
        e = smooth(np.clip((s - 0.55) / 0.45, 0, 1))
        a_, b_ = (0, f) if bit == 0 else (f, 1)

        def mp(x):
            return x + e * ((x - a_) / (b_ - a_) - x)
        parts = [(0, f, BLUE, bit == 0), (f, 1, CORAL, bit == 1)]
        for r, (x0, x1, col, chosen) in zip(self.bar, parts):
            y0, y1 = np.clip(mp(x0), 0, 1), np.clip(mp(x1), 0, 1)
            c = mixc(NEUTRAL, col, c_in)
            if chosen:
                c = mixc(c, NEUTRAL, e)
            op = 1 - 0.75 * dim if not chosen else 1.0
            if not chosen:
                op *= 1 - e
            r.become(rect(bx(y0), bx(y1), BY, BH, c, op))
        glo, gw = lo + (lo2 - lo) * e, w * (w2 / w) ** e
        self.gauge[0].become(rect(bx(glo), bx(glo) + max((BX1 - BX0) * gw, 3), GY, GH, YELLOW))
        cx = bx(glo + gw / 2)
        self.gauge[1].move_to(px(cx, GY - GH / 2 - 22))
        bits = max(0.0, -math.log2(gw)) + 0.0
        k = i + (1 if s > 0.55 else 0)
        self.counters[0].become(jp(f"判定 {k} 回", 40, INK).move_to(self.counters[0]))
        self.counters[1].become(jp(f"{bits:.1f} ビット", 40, YELLOW).move_to(self.counters[1]))


class S06(PScene):
    def construct(self):
        m = mb()
        log14, log15 = m["tok_log"][14], m["tok_log"][15]
        assert len(log14) == 1 and log14[0][:2] == (183, 0)          # 「全部0？」→ はい
        assert list(m["levels"][14]) == [0] * 16
        assert list(m["levels"][10]) == [0] * 16 and list(m["levels"][13]) == [0] * 16   # 上と左
        assert list(m["levels"][11]) == [0] * 16                      # 15 番の上 (左は 14 番)
        assert round(10 * 183 / 256) == 7                             # 10 回に 7 回くらい
        assert len(log15) == 44
        b15 = bits_of(log15)
        assert b15 < len(log15) and f"{b15:.1f}" == "35.3"
        probs = np.array(vp8_info()["probs"])
        assert log15[0][0] == probs[3][0][0][0] == 183                 # 4×4 (明るさ) の表、最初の数、となりは両方 0
        nb = [int(probs[3][0][c][0]) for c in range(3)]
        pos = [(i + 1, int(probs[3][BANDS[i]][1][0])) for i in range(1, 8)]
        n_dec, n_bits = decisions()
        assert (n_dec, n_bits) == (143022, 114128)
        assert n_dec // 10000 == 14 and round(n_bits / 10000) == 11 and n_bits < n_dec
        # 実際の幅の移り変わり
        cum = [(0.0, 1.0)]
        for p, bit, *_ in log15:
            lo, w = cum[-1]
            f = p / 256
            cum.append((lo, w * f) if bit == 0 else (lo + w * f, w * (1 - f)))
        assert abs(-math.log2(cum[-1][1]) - b15) < 1e-6

        # ハフマン符号 (写真全体の数で作る)
        L = all_levels().ravel()
        syms = ["0", "1", "−1", "2", "−2", "その他"]
        freqs = [int((L == 0).sum()), int((L == 1).sum()), int((L == -1).sum()), int((L == 2).sum()),
                 int((L == -2).sum()), int((np.abs(L) >= 3).sum())]
        assert sum(freqs) == L.size
        codes = huffman(freqs)
        assert codes[0] == "0"
        share = [100 * f / L.size for f in freqs]
        assert 85 < share[0] < 90

        # ---- 始まり：S05 の終わり (写真全体の数の帯) ----
        H = -(-L.size // STRIP_W)
        base = np.zeros((H * STRIP_W, 4), np.uint8)
        base[:L.size] = (70, 76, 92, 255)
        hi = np.zeros((H * STRIP_W, 4), np.uint8)
        hi[:L.size][L != 0] = (242, 193, 78, 255)
        imgs = []
        for a in (base, hi):
            im = ImageMobject(a.reshape(H, STRIP_W, 4))
            im.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
            im.width = u(STRIP_W)
            im.move_to(px(*STRIP_C))
            im.check_ignore = True
            imgs.append(im)
        self.add(*imgs)

        self.at("s06_01", -0.1)
        self.play(*[im.animate.set_opacity(0) for im in imgs], run_time=0.7)
        self.remove(*imgs)

        # ---- ハフマン符号の表 ----
        self.at("huff", -0.1)
        CX = (760, 960, 1120)
        RY = [460 + 52 * i for i in range(6)]
        head = VGroup(jp("数", 30, DIM).move_to(px(CX[0], 400)), jp("割合", 30, DIM).move_to(px(CX[1], 400)),
                      jp("符号", 30, DIM).move_to(px(CX[2] + 50, 400)))
        rows = VGroup()
        for i in range(6):
            r = VGroup(jp(syms[i], 34, INK).move_to(px(CX[0], RY[i])),
                       jp(f"{share[i]:.1f}%", 34, INK).move_to(px(CX[1], RY[i])),
                       mono(codes[i], 34, CYAN))
            r[2].move_to(px(CX[2], RY[i]), aligned_edge=LEFT)
            rows.add(r)
        self.play(FadeIn(head), LaggedStart(*[FadeIn(r, shift=UP * u(8)) for r in rows], lag_ratio=0.1), run_time=1.2)
        self.at("often", -0.1)
        rule = jp("よく出る → 短い", 40, INK).move_to(px(960, 330))
        self.play(FadeIn(rule, shift=DOWN * u(8)), run_time=0.6)
        self.play(LaggedStart(*[pop(rows[i][2], 1.2, 0.5) for i in range(6)], lag_ratio=0.12), run_time=1.1)

        self.at("onebit", -0.1)
        ul = underline(rows[0][2], YELLOW, buff=8, width=5)
        onelab = jp("1ビット", 32, YELLOW).move_to(px(CX[2] + 130, RY[0]))
        self.play(Create(ul), rows[0][2].animate.set_color(YELLOW), FadeIn(onelab, shift=LEFT * u(8)), run_time=0.7)

        self.at("zero", -0.1)
        self.play(rows[0][1].animate.set_color(YELLOW), run_time=0.4)
        self.play(pop(rows[0][1], 1.3, 0.7), run_time=0.7)

        # ---- 算術符号 ----
        self.at("arith", -0.1)
        title = jp("算術符号", 56, INK).move_to(px(960, 545))
        self.play(FadeOut(VGroup(head, rows, rule, ul, onelab)), run_time=0.6)
        self.play(FadeIn(title, scale=0.9), run_time=0.6)

        # ---- ほっぺの 3 つのブロック (MB (8, 13) の 0・1・2 番) ----
        self.at("ex", -0.1)
        CM = (8, 13)
        cm = mb(*CM)
        for b in range(3):
            lg = cm["tok_log"][b]
            assert len(lg) == 1 and lg[0][:2] == (183, 0) and list(cm["levels"][b]) == [0] * 16
        above = mb(CM[0], CM[1] - 1)
        assert all(list(above["levels"][b]) == [0] * 16 for b in (12, 13, 14))     # 上
        assert list(mb(CM[0] - 1, CM[1])["levels"][3]) == [0] * 16                  # 左
        cx0, cy0 = CM[0] * 16, CM[1] * 16
        assert (cx0, cy0) == (128, 208)
        CV_W, CV_H = 684, 456
        cview = CatView(y_orig(), (960, 260), CV_W, CV_H)        # まず写真全体
        cview.check_ignore = True
        cview.set_opacity(0)
        WIN3 = (86, 166, 182, 230)                                 # 3 つのまわり (96×64)

        def cbox(x, y, col, w=4):
            return cview.track_rect(x + 0.3, y + 0.3, 3.4, 3.4, stroke_color=col, stroke_width=w)
        self.add(cview)
        grp = cview.track_rect(cx0 - 1, cy0 - 1, 14, 6, stroke_color=YELLOW, stroke_width=4)
        self.play(cview.animate.set_opacity(1), run_time=0.6)
        self.play(Create(grp), run_time=0.5)
        self.play(zoom(cview, WIN3), run_time=1.3)
        boxes3 = VGroup(*[cbox(cx0 + 4 * b, cy0, YELLOW) for b in range(3)])
        self.play(FadeOut(grp), LaggedStart(*[Create(b_) for b_ in boxes3], lag_ratio=0.2), run_time=0.6)

        # 問いのカード (答えは下の段に入る)
        CW, CH = 170, 110
        cxs = [760, 960, 1160]

        def card_at(x, y):
            r = RoundedRectangle(corner_radius=u(14), width=u(CW), height=u(CH), stroke_color=INK, stroke_width=3,
                                 fill_color="#232833", fill_opacity=1).move_to(px(x, y))
            t = jp("全部0？", 32, INK).move_to(px(x, y - 24))
            return VGroup(r, t)
        self.at("ask", -0.1)
        cards = [card_at(cxs[b], 580) for b in range(3)]
        conn = VGroup(*[Line(cview.to_point(cx0 + 4 * b + 2, cy0 + 4) + DOWN * u(4), cards[b].get_top(),
                             color=YELLOW, stroke_width=2) for b in range(3)])
        self.play(FadeOut(title), run_time=0.3)
        self.play(LaggedStart(*[AnimationGroup(Create(conn[b]), FadeIn(cards[b], shift=DOWN * u(10)))
                                for b in range(3)], lag_ratio=0.2), run_time=1.0)

        def ans_pos(b):
            return cards[b][0].get_center() + DOWN * u(24)

        self.at("plain", -0.1)
        legend2 = jp("はい → 0　　いいえ → 1", 36, INK, t2c={"はい": BLUE, "いいえ": CORAL}).move_to(px(960, 740))
        self.play(FadeIn(legend2, shift=UP * u(8)), run_time=0.6)
        self.at("three", -0.1)
        ones = VGroup(*[jp("1ビット", 30, DIM).move_to(px(cxs[b], 670)) for b in range(3)])
        tot3 = jp("合わせて 3 ビット", 40, INK).move_to(px(960, 820))
        self.play(LaggedStart(*[FadeIn(o, shift=DOWN * u(6)) for o in ones], lag_ratio=0.2), run_time=0.7)
        self.play(FadeIn(tot3, shift=UP * u(6)), run_time=0.5)

        self.at("foresee", -0.1)
        self.play(FadeOut(VGroup(ones, tot3, legend2)), run_time=0.6)
        self.at("likely", -0.1)
        nbs3 = VGroup(*[cbox(cx0 + 4 * b, cy0 - 4, BLUE) for b in range(3)], cbox(cx0 - 4, cy0, BLUE))
        self.play(LaggedStart(*[Create(b_) for b_ in nbs3], lag_ratio=0.15), run_time=0.9)

        self.at("p", -0.1)
        f = 183 / 256
        n_yes = round(10 * f)
        assert n_yes == 7
        dots = VGroup(*[Circle(radius=u(22), stroke_width=0, fill_color=BLUE if i < n_yes else CORAL, fill_opacity=1)
                        .move_to(px(960 + (i - 4.5) * 62, 710)) for i in range(10)])
        prob = jp("183 / 256", 36, BLUE).move_to(px(960, 790))
        self.play(LaggedStart(*[FadeIn(d, scale=0.5) for d in dots], lag_ratio=0.08), FadeIn(prob, shift=UP * u(6)),
                  run_time=1.0)

        # ---- 0〜1 の定規 ----
        RX0, RX1 = 460, 1460

        def rx(t):
            return RX0 + (RX1 - RX0) * t
        RY_, RH = 330, 80          # 定規
        AY, AH = 480, 70           # 答えの帯
        CY = 120                   # カードの段
        self.at("ruler", -0.1)
        self.play(FadeOut(VGroup(dots, prob, conn)), cview.animate.set_opacity(0),
                  *[FadeOut(b_) for b_ in [*boxes3, *nbs3]],
                  *[c.animate.move_to(px(cxs[b], CY)) for b, c in enumerate(cards)], run_time=0.9)
        self.remove(cview)
        ruler = Rectangle(width=u(RX1 - RX0), height=u(RH), stroke_color=INK, stroke_width=3, fill_color="#232833",
                          fill_opacity=1).move_to(px(960, RY_))
        r0 = jp("0", 30, DIM).move_to(px(RX0 + 16, RY_ + RH / 2 + 22))
        r1_ = jp("1", 30, DIM).move_to(px(RX1 - 16, RY_ + RH / 2 + 22))
        self.play(GrowFromEdge(ruler, LEFT), FadeIn(r0), FadeIn(r1_), run_time=0.9)

        def tick(t, h=RH):
            return Line(px(rx(t), RY_ - h / 2), px(rx(t), RY_ + h / 2), color=INK, stroke_width=3)
        self.at("bit1", -0.1)
        t50 = tick(0.5)
        b1 = VGroup(mono("0", 40, CYAN).move_to(px(rx(0.25), RY_)), mono("1", 40, CYAN).move_to(px(rx(0.75), RY_)))
        self.play(Create(t50), run_time=0.5)
        self.play(FadeIn(b1, scale=0.8), run_time=0.5)
        self.at("bit2", -0.1)
        t25, t75 = tick(0.25), tick(0.75)
        codes2 = ["00", "01", "10", "11"]
        b2 = VGroup(*[mono(c_, 40, CYAN).move_to(px(rx(0.125 + 0.25 * i), RY_)) for i, c_ in enumerate(codes2)])
        self.play(Create(t25), Create(t75), run_time=0.5)
        self.play(ReplacementTransform(b1[0].copy(), b2[0]), ReplacementTransform(b1[0].copy(), b2[1]),
                  ReplacementTransform(b1[1].copy(), b2[2]), ReplacementTransform(b1[1].copy(), b2[3]),
                  FadeOut(b1), run_time=0.8)
        self.at("quarter", -0.1)
        q00 = rect(rx(0), rx(0.25), RY_, RH - 6, YELLOW, 0.35)
        self.add(q00)
        self.bring_to_front(b2)
        q00.set_opacity(0)
        self.play(q00.animate.set_fill(YELLOW, 0.35), b2[0].animate.set_color(YELLOW), run_time=0.6)
        self.play(pop(b2[0], 1.3, 0.6), run_time=0.6)

        # ---- 答えで切っていく (定規と同じ尺度) ----
        self.at("cut", -0.1)
        aframe = Rectangle(width=u(RX1 - RX0), height=u(AH), stroke_color=DIM, stroke_width=2,
                           fill_opacity=0).move_to(px(960, AY))
        abar = VGroup(rect(RX0, RX1, AY, AH, NEUTRAL), rect(RX1, RX1, AY, AH, CORAL, 0))
        self.play(q00.animate.set_fill(YELLOW, 0), b2[0].animate.set_color(CYAN), GrowFromEdge(abar[0], LEFT),
                  Create(aframe), run_time=0.9)
        self.add(abar)
        self.bring_to_front(aframe)
        ws = [f ** k for k in range(4)]
        assert [f"{w:.2f}" for w in ws[1:]] == ["0.71", "0.51", "0.37"]
        tyes = jp("はい", 32, INK).move_to(px(rx(f / 2), AY))
        tno = jp("いいえ", 32, INK).move_to(px(rx((1 + f) / 2), AY))
        answers = [jp("はい", 32, BLUE).move_to(ans_pos(b)) for b in range(3)]
        wlab = None
        for k in range(3):
            w0, w1 = ws[k], ws[k + 1]
            self.at("rule" if k == 0 else f"a{k + 1}", -0.1)
            anims = [abar[0].animate.become(rect(rx(0), rx(w1), AY, AH, BLUE)),
                     abar[1].animate.become(rect(rx(w1), rx(w0), AY, AH, CORAL))]
            if k == 0:
                tyes.move_to(px(rx(w1 / 2), AY))
                tno.move_to(px(rx((w1 + w0) / 2), AY))
                self.play(*anims, run_time=0.8)
                self.bring_to_front(aframe)
                self.play(FadeIn(tyes), FadeIn(tno), run_time=0.5)
                self.at("a1", -0.1)
                self.play(FadeIn(answers[0], scale=0.7), pop(tyes, 1.2, 0.6), run_time=0.6)
            else:
                self.play(*anims, FadeIn(answers[k], scale=0.7),
                          tyes.animate.move_to(px(rx(w1 / 2), AY)), run_time=0.8)
                self.bring_to_front(aframe, tyes)
            self.at(f"w{k + 1}", -0.1)
            nl = jp(f"{w1:.2f}", 34, BLUE).move_to(px(rx(w1), AY + AH / 2 + 26))
            out = [abar[1].animate.set_opacity(0)]
            if k == 0:
                out.append(FadeOut(tno))
            if wlab is None:
                out.append(FadeIn(nl, shift=UP * u(6)))
                wlab = nl
            else:
                wlab.text = nl.text
                out.append(Transform(wlab, nl))
            self.play(*out, run_time=0.7)
        self.at("narrow", -0.1)
        self.play(pop(VGroup(abar[0], tyes), 1.05, 0.7), run_time=0.7)

        # ---- 定規と並べる：「00」はすっぽり入る ----
        self.at("look", -0.1)
        self.play(pop(ruler, 1.03, 0.6), pop(VGroup(t25, t50, t75, b2), 1.03, 0.6), run_time=0.6)
        self.at("p00", -0.1)
        l25 = jp("0.25", 30, YELLOW).move_to(px(rx(0.25) + 38, RY_ + RH / 2 + 22))
        self.play(q00.animate.set_fill(YELLOW, 0.35), b2[0].animate.set_color(YELLOW), FadeIn(l25), run_time=0.6)
        self.at("inside", -0.1)
        d25 = DashedLine(px(rx(0.25), RY_ - RH / 2), px(rx(0.25), AY + AH / 2), color=YELLOW, stroke_width=4,
                         dash_length=u(10))
        d0 = DashedLine(px(rx(0), RY_ - RH / 2), px(rx(0), AY + AH / 2), color=YELLOW, stroke_width=4,
                        dash_length=u(10))
        ghost = rect(rx(0), rx(0.25), AY, AH - 14, YELLOW, 0.8)
        self.play(Create(d0), Create(d25), run_time=0.8)
        self.add(ghost)
        ghost.set_opacity(0)
        self.play(ghost.animate.set_fill(YELLOW, 0.8), FadeOut(tyes), run_time=0.6)

        # ---- 書くのは「00」だけ ----
        self.at("two", -0.1)
        tgt = b2[0].get_top() + UP * u(4)
        links = VGroup(*[Line(answers[b].get_bottom() + DOWN * u(26), tgt, color=YELLOW, stroke_width=4)
                         for b in range(3)])
        self.play(LaggedStart(*[Create(l_) for l_ in links], lag_ratio=0.15), run_time=1.0)
        self.play(pop(b2[0], 1.4, 0.6), run_time=0.6)
        self.at("lt", -0.1)
        lt = jp("3 つの答え → 2 ビット", 40, YELLOW).move_to(px(960, 760))
        self.play(FadeIn(lt, shift=UP * u(8)), run_time=0.6)

        # ---- 読むほう ----
        self.at("read", -0.1)
        self.play(FadeOut(VGroup(links, lt, d0, d25, ghost, wlab, *answers)),
                  abar[0].animate.become(rect(RX0, RX1, AY, AH, NEUTRAL)), run_time=0.8)
        self.bring_to_front(aframe)
        self.at("r1", -0.1)
        ptr = rect(rx(0), rx(0.25), AY, AH - 14, YELLOW, 0.8)
        self.play(ReplacementTransform(q00.copy(), ptr), pop(b2[0], 1.3, 0.6), run_time=0.8)
        answers = [jp("はい", 32, BLUE).move_to(ans_pos(b)) for b in range(3)]
        wl = None
        for k in range(3):
            self.at(f"r{k + 2}", -0.1)
            w1 = ws[k + 1]
            nl = jp(f"{w1:.2f}", 34, BLUE).move_to(px(rx(w1), AY + AH / 2 + 26))
            anims = [abar[0].animate.become(rect(rx(0), rx(w1), AY, AH, BLUE)),
                     ReplacementTransform(ptr.copy().set_opacity(0), answers[k])]
            if wl is None:
                anims.append(FadeIn(nl))
            else:
                wl.text = nl.text
                anims.append(Transform(wl, nl))
            self.play(*anims, run_time=0.9)
            if wl is None:
                wl = nl
            self.bring_to_front(aframe, ptr)
        self.at("rall", -0.1)
        self.play(LaggedStart(*[pop(VGroup(cards[b], answers[b]), 1.12, 0.6) for b in range(3)], lag_ratio=0.15),
                  run_time=1.0)

        # ---- もし「いいえ」が混ざったら ----
        self.at("miss", -0.1)
        lo, hi_ = f * f, f                  # 1 つ目「はい」: [0, f)。2 つ目「いいえ」: [f², f)
        lo, hi_ = lo, lo + (hi_ - lo) * f   # 3 つ目「はい」: その左 7 割
        assert f"{lo:.3f}" == "0.511" and f"{hi_:.3f}" == "0.657"
        best = None
        for nbit in range(1, 12):
            for k in range(2 ** nbit):
                a_, b_ = k / 2 ** nbit, (k + 1) / 2 ** nbit
                if lo <= a_ and b_ <= hi_:
                    best = (nbit, k, a_, b_)
                    break
            if best:
                break
        nbit, kk, a_, b_ = best
        code = format(kk, f"0{nbit}b")
        assert code == "1001" and (a_, b_) == (0.5625, 0.625)
        MY_, MH = 620, 70
        mlab = jp("もし：はい・いいえ・はい", 34, INK, t2c={"いいえ": CORAL}).move_to(px(RX1, MY_ - MH / 2 - 26),
                                                                          aligned_edge=RIGHT)
        mval = jp(f"{lo:.3f}〜{hi_:.3f}", 34, PURPLE).move_to(px(rx((lo + hi_) / 2), MY_ + MH / 2 + 26))
        mframe = Rectangle(width=u(RX1 - RX0), height=u(MH), stroke_color=DIM, stroke_width=2,
                           fill_opacity=0).move_to(px(960, MY_))
        mint = rect(rx(lo), rx(hi_), MY_, MH, PURPLE)
        self.play(FadeIn(mlab, shift=UP * u(6)), Create(mframe), run_time=0.6)
        self.play(GrowFromCenter(mint), FadeIn(mval, shift=UP * u(6)), run_time=0.7)
        self.at("thin", -0.1)
        mptr = rect(rx(a_), rx(b_), MY_, MH - 12, YELLOW, 0.9)
        mcode = jp(f"{code} → {nbit} ビット", 40, YELLOW).move_to(px(RX1, 760), aligned_edge=RIGHT)
        self.play(GrowFromCenter(mptr), run_time=0.6)
        self.play(FadeIn(mcode, shift=UP * u(6)), run_time=0.6)
        self.at("hit", -0.1)
        hitl = jp("はい・はい・はい → 2 ビット", 40, YELLOW).move_to(px(RX0, 760), aligned_edge=LEFT)
        self.play(FadeIn(hitl, shift=UP * u(6)), run_time=0.6)
        ulh = underline(hitl, YELLOW, buff=8, width=5)
        self.play(Create(ulh), run_time=0.6)
        self.at("again", -0.1)
        self.play(pop(VGroup(hitl, ulh), 1.1, 0.7), run_time=0.7)

        # ---- 問いが続くと：主役の MB の 15 番の 44 回の判定 ----
        self.at("s06_07", -0.1)
        self.play(FadeOut(VGroup(*cards, *answers, ruler, r0, r1_, t25, t50, t75, b2, q00, l25, abar, aframe, ptr,
                                 wl, mlab, mval, mframe, mint, mptr, mcode, hitl, ulh)), run_time=0.6)
        view = CatView(y_orig(), VIEW_C, VIEW_W, VIEW_H, win=window_around(X0 + 8, Y0 + 8, 22))
        view.grid_mb = 1.0
        view.sb_mb = (MX, MY)
        view.grid_sb = 1.0
        view.refresh()
        view.check_ignore = True
        view.set_opacity(0)

        def box(b, col, w=4):
            return view.track_rect(X0 + 4 * (b % 4) + 0.3, Y0 + 4 * (b // 4) + 0.3, 3.4, 3.4, stroke_color=col,
                                   stroke_width=w)       # となりの枠と線が重ならないように少し内側
        frame = Rectangle(width=u(BX1 - BX0), height=u(BH), stroke_color=DIM, stroke_width=2, fill_opacity=0)
        frame.move_to(px((BX0 + BX1) / 2, BY))
        bar = VGroup(rect(BX0, BX1, BY, BH, NEUTRAL), rect(BX1, BX1, BY, BH, CORAL, 0))
        e0 = jp("0", 28, DIM).move_to(px(BX0, BY + BH / 2 + 24))
        e1 = jp("256", 28, DIM).move_to(px(BX1, BY + BH / 2 + 24))
        cur2 = box(15, YELLOW)
        self.add(view)
        self.play(view.animate.set_opacity(1), FadeIn(bar), FadeIn(frame), FadeIn(e0), FadeIn(e1), Create(cur2),
                  run_time=0.6)
        gframe = Rectangle(width=u(BX1 - BX0), height=u(GH), stroke_color=DIM, stroke_width=2, fill_opacity=0)
        gframe.move_to(px((BX0 + BX1) / 2, GY))
        gfill = rect(BX0, BX1, GY, GH, YELLOW)
        mark = Triangle(color=YELLOW, fill_opacity=1, stroke_width=0).rotate(PI).scale_to_fit_width(u(22))
        mark.move_to(px(960, GY - GH / 2 - 22))
        gauge = VGroup(gfill, mark)
        cnt = VGroup(jp("判定 0 回", 40, INK).move_to(px(760, 770)),
                     jp("0.0 ビット", 40, YELLOW).move_to(px(1160, 770)))
        for c in cnt:
            c.check_ignore = True
        self.play(FadeIn(gframe), FadeIn(gauge), FadeIn(cnt), run_time=0.4)
        self.add(gauge)

        self.at("seq", -0.1)
        for i0, i1, rt in ((0, 3, 1.9), (3, 44, 2.6)):
            an = DecAnim(bar, gauge, cnt, log15, cum, i0, i1)
            self.play(an, run_time=rt)
            self.remove(an.mobject)
            self.add(bar, gauge, cnt)
        self.bring_to_front(frame)
        fin = VGroup(jp(f"判定 {len(log15)} 回", 40, INK).move_to(cnt[0]),
                     jp(f"{b15:.1f} ビット", 40, YELLOW).move_to(cnt[1]))
        self.remove(cnt)
        self.add(fin)
        self.play(pop(mark, 1.6, 0.6), pop(fin[1], 1.2, 0.6), run_time=0.6)

        # ---- 確率の使い分け ----
        self.at("ctx", 0.65)
        self.play(FadeOut(VGroup(bar, frame, e0, e1, gframe, gauge, fin)), run_time=0.5)
        legend = VGroup()
        for j, (col, s) in enumerate([(BLUE, "全部0 / 終わり"), (CORAL, "まだある")]):
            sq = Square(u(30), stroke_width=0, fill_color=col, fill_opacity=1).move_to(px(1080, 215 + 60 * j))
            legend.add(VGroup(sq, jp(s, 32, INK).next_to(sq, RIGHT, buff=u(14))))

        def mini(p, x0, x1, y, h=36):
            ff = p / 256
            return VGroup(rect(x0, x0 + (x1 - x0) * ff, y, h, BLUE), rect(x0 + (x1 - x0) * ff, x1, y, h, CORAL))

        self.at("neighbor", -0.1)
        lhead = jp("となりに0じゃない数", 34, INK).move_to(px(700, 440))
        lrows = VGroup()
        for j, (name, p) in enumerate(zip(["なし", "片方", "両方"], nb)):
            y = 520 + 70 * j
            lrows.add(VGroup(jp(name, 30, YELLOW if j == 0 else INK).move_to(px(505, y)), mini(p, 555, 865, y),
                             jp(str(p), 30, INK).move_to(px(905, y))))
        nbs = VGroup(box(11, BLUE), box(14, BLUE))
        self.play(Create(nbs), FadeIn(lhead), FadeIn(legend), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * u(10)) for r in lrows], lag_ratio=0.2), run_time=1.0)

        self.at("pos", -0.1)
        rhead = jp("何番目の数か", 34, INK).move_to(px(1220, 440))
        rnote = jp("(1つ前が ±1 のとき)", 26, DIM).move_to(px(1220, 480))
        rrows = VGroup()
        for j, (k, p) in enumerate(pos):
            y = 535 + 50 * j
            rrows.add(VGroup(jp(f"{k}番目", 30, INK).move_to(px(1030, y)), mini(p, 1080, 1385, y, 32),
                             jp(str(p), 30, INK).move_to(px(1428, y))))
        self.play(FadeIn(rhead), FadeIn(rnote), LaggedStart(*[FadeIn(r, shift=RIGHT * u(10)) for r in rrows], lag_ratio=0.12),
                  run_time=1.3)

        self.at("smart", -0.1)
        self.play(LaggedStart(*[pop(r[1], 1.08, 0.5) for r in [*lrows, *rrows]], lag_ratio=0.08), run_time=1.6)

        # ---- 写真全体 ----
        self.at("s06_10", -0.1)
        self.play(FadeOut(VGroup(lhead, lrows, rhead, rnote, rrows, legend, nbs, cur2)), view.animate.set_opacity(0),
                  run_time=0.8)
        self.remove(view)
        W0 = 900
        self.at("dec", -0.1)
        ld = jp(f"はい・いいえ {fmt(n_dec)} 回", 38, INK).move_to(px(510, 480), aligned_edge=LEFT)
        bd = rect(510, 510 + W0, 545, 60, "#5a6070")
        self.play(FadeIn(ld, shift=UP * u(8)), GrowFromEdge(bd, LEFT), run_time=1.0)
        self.at("bits", -0.1)
        lb = jp(f"{fmt(n_bits)} ビット", 38, YELLOW).move_to(px(510, 640), aligned_edge=LEFT)
        bb = rect(510, 510 + W0 * n_bits / n_dec, 705, 60, YELLOW)
        self.play(FadeIn(lb, shift=UP * u(8)), GrowFromEdge(bb, LEFT), run_time=1.0)

        self.at("saving", -0.1)
        self.play(pop(VGroup(lb, bb), 1.06, 0.7), run_time=0.7)

        self.at(self.tl["duration"] - 0.8)
        self.play(FadeOut(VGroup(ld, bd, lb, bb)), run_time=0.6)
        self.finish()
