import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import colorsys  # noqa: E402
import math  # noqa: E402
from collections import Counter  # noqa: E402

import numpy as np  # noqa: E402

from vlib.data import MODE_NAMES, dec, fmt, picture_size, rgb_decoded  # noqa: E402
import av1  # noqa: E402,I001  (vlib.data が tools/ を読み込みの道に入れる)
from vlib.photoview import PhotoView, ViewAnim  # noqa: E402
from vlib.ui import add_row, compare_card  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)
NEUTRAL = "#2c3240"
RX0, RX1, RY, RH = 460, 1460, 460, 130          # 定規 (WebP 編・HEIC 編と同じ見た目)
QX, QW, QY, QRY, QRH = (600, 960, 1320), 280, 300, 450, 90    # 3 つの問いのカードと 2 択の定規
CARD_Y = 260
CB_KEY = ("CoeffBase", 2, 0, 24)               # 4 択の例の文脈 (区間の幅がいちばんそろっている)
YM_A, YM_B = 249, 258                          # 予測の種類の例のブロック (上・左が H / 上・左が V)
CTX_C, CTX_S = (960, 770), 120                 # 上と左のブロックの図
BAR_Y, BAR_H = 620, 120                        # 読み取り回数の帯
COL4 = ["#5b7fa6", "#5f9a7c", "#a58a55", "#8b6fa3"]


def calm(i, n=13):
    h = (0.58 + i * 0.382) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.38, 0.62)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


COL13 = [calm(i) for i in range(13)]


def rx(f):
    return RX0 + (RX1 - RX0) * f


def rect(x0, x1, y, h, color, op=1.0):
    return Rectangle(width=u(max(x1 - x0, 0.5)), height=u(h), stroke_width=0, fill_color=color,
                     fill_opacity=op).move_to(px((x0 + x1) / 2, y))


def probs(cdf):
    return [av1.symbol_prob(cdf, v) for v in range(len(cdf))]


def multi(ps, colors, n=13, y=RY, h=RH, hot=None):
    """区間 n 個の定規 (ps が短いときは右端に幅 0 の区間を足す。Transform で何択でも変形できるように)"""
    g, x = VGroup(), 0.0
    for i in range(n):
        p = ps[i] if i < len(ps) else 0.0
        c = YELLOW if i == hot else colors[i % len(colors)]
        g.add(rect(rx(x) + (1 if p > 0 else 0), rx(x + p) - (1 if p > 0 else 0), y, h, c, 1.0 if p > 0 else 0.0))
        x += p
    return g


def edges(ps):
    e = np.concatenate([[0.0], np.cumsum(ps)])
    return [(rx(e[i]), rx(e[i + 1])) for i in range(len(ps))]


def binary(xc, w, y, h, p):
    """左が「はい」(青・幅 p)、右が「いいえ」(珊瑚)"""
    x0, x1 = xc - w / 2, xc + w / 2
    xm = x0 + w * p
    return VGroup(rect(x0, xm, y, h, BLUE), rect(xm, x1, y, h, CORAL))


class S08(PScene):
    def construct(self):
        d = dec()
        W, H = picture_size()
        S = d.symbols
        n_all = len(S)
        kinds = Counter(s[1][0] if s[1] else None for s in S)
        assert n_all == 95319 and kinds[None] == 24391 and round(n_all / 1000) == 95     # 約9万5千
        n_cb = kinds["CoeffBase"]
        assert n_cb == 53280 and n_cb > n_all / 2                                          # 半分以上
        assert all(len(s[2]) == 4 for s in S if s[1] and s[1][0] == "CoeffBase")            # 4 択
        ym = [s for s in S if s[1] and s[1][0] == "IntraFrameYMode"]
        assert all(len(s[2]) == 13 for s in ym)                                              # 13 択
        assert len({d.initial_cdf(("IntraFrameYMode", a, b)) for a in range(5) for b in range(5)}) == 25   # 5×5 通り

        # 4 択の例の文脈と、その読み取りの列
        seq = [s for s in S if s[1] == CB_KEY]
        p4 = probs(seq[0][2])
        assert seq[0][2] == d.initial_cdf(CB_KEY) and min(p4) > 0.1
        assert abs(sum(p4) - 1) < 1e-9
        # HEIC 式の 3 つの 2 択 (同じ確率を「0じゃない？」「1より大きい？」「2より大きい？」に分けたもの)
        q = [1 - p4[0], (p4[2] + p4[3]) / (1 - p4[0]), p4[3] / (p4[2] + p4[3])]

        # 予測の種類の例 (上と左が H / 上と左が V)
        B = d.blocks
        assert len(B) == len(ym) and all(B[i]["y_mode"] == ym[i][3] for i in range(len(ym)))

        def at_block(x, y):
            return next(b for b in B if b["x"] <= x < b["x"] + b["w"] and b["y"] <= y < b["y"] + b["h"])

        def nb(i):
            b = B[i]
            return MODE_NAMES[at_block(b["x"], b["y"] - 1)["y_mode"]], MODE_NAMES[at_block(b["x"] - 1, b["y"])["y_mode"]]
        pa, pb = probs(ym[YM_A][2]), probs(ym[YM_B][2])
        assert nb(YM_A) == ("H", "H") and nb(YM_B) == ("V", "V")
        assert ym[YM_A][1] != ym[YM_B][1]
        assert int(np.argmax(pa)) == MODE_NAMES.index("H") and int(np.argmax(pb)) == MODE_NAMES.index("V")

        # ---- 写真 (S07 の終わり) を消して、定規 ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)
        self.at("s08_01", -0.05)
        self.play(view.animate.set_opacity(0), run_time=0.8)
        self.remove(view)

        self.at("ruler", -0.1)
        frame = Rectangle(width=u(RX1 - RX0), height=u(RH), stroke_color=INK, stroke_width=3, fill_color=NEUTRAL,
                          fill_opacity=1).move_to(px(960, RY))
        r0 = jp("0", 30, DIM).move_to(px(RX0, RY + RH / 2 + 28))
        r1 = jp("1", 30, DIM).move_to(px(RX1, RY + RH / 2 + 28))
        self.play(GrowFromEdge(frame, LEFT), FadeIn(r0), FadeIn(r1), run_time=0.9)
        self.at("two", -0.1)
        big = binary(960, RX1 - RX0, RY, RH, 0.5)
        tyes = jp("はい", 44, INK).move_to(px((RX0 + 960) / 2, RY))
        tno = jp("いいえ", 44, INK).move_to(px((960 + RX1) / 2, RY))
        self.play(FadeIn(big), FadeIn(tyes), FadeIn(tno), frame.animate.set_fill(opacity=0), run_time=0.8)
        self.bring_to_front(tyes, tno)

        # ---- HEIC：3 つの 2 択 ----
        self.at("heic", -0.1)
        rulers = [binary(x, QW, QRY, QRH, p) for x, p in zip(QX, q)]
        self.play(FadeOut(VGroup(tyes, tno, r0, r1)), FadeOut(frame), ReplacementTransform(big, rulers[0]),
                  run_time=1.0)

        def qcard(i, s):
            c = RoundedRectangle(corner_radius=u(16), width=u(QW + 10), height=u(90), stroke_color=INK, stroke_width=2,
                                 fill_color="#232833", fill_opacity=1).move_to(px(QX[i], QY))
            return VGroup(c, jp(s, 36, INK).move_to(c))
        cards = [qcard(0, "0じゃない？"), qcard(1, "1より大きい？"), qcard(2, "2より大きい？")]
        for i, cue in enumerate(("q1", "q2", "q3")):
            self.at(cue, -0.1)
            anims = [FadeIn(cards[i], shift=DOWN * u(10))]
            if i > 0:
                anims.append(ReplacementTransform(rulers[i - 1].copy(), rulers[i], path_arc=-0.5))
            self.play(*anims, run_time=0.8)
        arrows = VGroup(*[Arrow(px(QX[i] + QW / 2 + 6, QY), px(QX[i + 1] - QW / 2 - 6, QY), buff=0, color=DIM,
                                stroke_width=5, max_tip_length_to_length_ratio=0.5) for i in range(2)])
        self.at("times", -0.1)
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.5), run_time=0.8)
        self.play(LaggedStart(*[pop(VGroup(c, r), 1.08, 0.5) for c, r in zip(cards, rulers)], lag_ratio=0.5),
                  run_time=1.4)

        # ---- AV1：1 回で 4 択 ----
        self.at("once", -0.1)
        one = RoundedRectangle(corner_radius=u(16), width=u(640), height=u(96), stroke_color=YELLOW, stroke_width=3,
                               fill_color="#232833", fill_opacity=1).move_to(px(960, CARD_Y))
        one_t = jp("0・1・2・3以上のどれ？", 44, INK).move_to(one)
        frame4 = Rectangle(width=u(RX1 - RX0), height=u(RH), stroke_width=0, fill_color=NEUTRAL,
                           fill_opacity=1).move_to(px(960, RY))
        self.play(*[ReplacementTransform(c[0], one) for c in cards], *[FadeOut(c[1]) for c in cards],
                  FadeOut(arrows), *[ReplacementTransform(r, frame4) for r in rulers], run_time=1.2)
        self.play(FadeIn(one_t, scale=0.9), run_time=0.6)
        self.at("one", -0.1)
        self.play(pop(VGroup(one, one_t), 1.08, 0.7), run_time=0.7)

        self.at("cut4", -0.1)
        ruler = multi(p4, COL4)
        e4 = edges(p4)
        names4 = ["0", "1", "2", "3以上"]
        labs = VGroup(*[jp(s, 36, INK).move_to(px((a + b) / 2, RY)) for s, (a, b) in zip(names4, e4)])
        pcts = VGroup(*[jp(f"{round(p * 100)}%", 32, DIM).move_to(px((a + b) / 2, RY + RH / 2 + 32))
                        for p, (a, b) in zip(p4, e4)])
        self.add(ruler)
        self.remove(frame4)
        self.play(LaggedStart(*[GrowFromEdge(r, LEFT) for r in ruler[:4]], lag_ratio=0.3),
                  LaggedStart(*[FadeIn(t) for t in labs], lag_ratio=0.3), run_time=1.3)
        self.play(FadeIn(pcts, shift=UP * u(6)), run_time=0.6)
        self.at("four", -0.1)
        self.play(LaggedStart(*[pop(t, 1.3, 0.5) for t in labs], lag_ratio=0.25), run_time=1.2)

        # ---- 予測の種類：13 に区切る ----
        self.at("modes", -0.1)
        one_t2 = jp("予測の種類は？", 44, INK)
        self.play(retext(one_t, one_t2), FadeOut(labs), FadeOut(pcts), run_time=0.7)

        names = VGroup(*[mono(MODE_NAMES[i], 30, INK) for i in range(13)])

        def fit13(ps):
            """区間に収まる名前だけ見せる (区間の真ん中へ)"""
            out = []
            for t, (a, b) in zip(names, edges(ps)):
                ok = t.width / u(1) + 14 < b - a
                out.append(t.animate.move_to(px((a + b) / 2, RY)).set_opacity(1 if ok else 0))
            return out
        for t, (a, b) in zip(names, edges(pa)):
            t.move_to(px((a + b) / 2, RY)).set_opacity(0)
        self.add(names)
        self.at("cut13", -0.1)
        self.play(Transform(ruler, multi(pa, COL13)), run_time=1.2)
        self.play(*fit13(pa), run_time=0.4)

        self.at("ctx", -0.1)
        cx, cy = CTX_C
        gap = CTX_S + 14
        sq_cur = Square(u(CTX_S), stroke_color=YELLOW, stroke_width=5, fill_color="#232833", fill_opacity=1).move_to(
            px(cx, cy))
        cur_t = jp("？", 48, YELLOW).move_to(sq_cur)
        sq_up = Square(u(CTX_S), stroke_color=INK, stroke_width=3, fill_color=NEUTRAL, fill_opacity=1).move_to(
            px(cx, cy - gap))
        sq_lf = Square(u(CTX_S), stroke_color=INK, stroke_width=3, fill_color=NEUTRAL, fill_opacity=1).move_to(
            px(cx - gap, cy))
        ua, la = nb(YM_A)
        up_t = mix(f"上 {ua}", 34, INK).move_to(sq_up)
        lf_t = mix(f"左 {la}", 34, INK).move_to(sq_lf)
        self.play(FadeIn(sq_cur), FadeIn(cur_t), run_time=0.5)
        self.play(FadeIn(sq_up, shift=DOWN * u(10)), FadeIn(up_t, shift=DOWN * u(10)),
                  FadeIn(sq_lf, shift=RIGHT * u(10)), FadeIn(lf_t, shift=RIGHT * u(10)), run_time=0.7)
        self.play(sq_up.animate.set_stroke(YELLOW), sq_lf.animate.set_stroke(YELLOW), run_time=0.4)

        self.at("width", -0.1)
        ub, lb = nb(YM_B)
        self.play(retext(up_t, mix(f"上 {ub}", 34, INK)), retext(lf_t, mix(f"左 {lb}", 34, INK)),
                  Transform(ruler, multi(pb, COL13)), *fit13(pb), run_time=1.2)

        # ---- 読むたびに幅を更新 ----
        self.at("s08_06", -0.1)
        one_t3 = jp("0・1・2・3以上のどれ？", 44, INK)
        e4 = edges(p4)
        labs = VGroup(*[jp(s, 36, INK).move_to(px((a + b) / 2, RY)) for s, (a, b) in zip(names4, e4)])
        self.play(retext(one_t, one_t3), FadeOut(VGroup(sq_cur, cur_t, sq_up, up_t, sq_lf, lf_t)), FadeOut(names),
                  Transform(ruler, multi(p4, COL4)), Succession(Wait(0.5), FadeIn(labs, run_time=0.4)), run_time=0.9)

        def place(ps, hot=None):
            ruler.become(multi(ps, COL4, hot=hot))
            for t, (a, b) in zip(labs, edges(ps)):
                t.move_to(px((a + b) / 2, RY))

        self.at("learn", -0.1)
        N = len(seq)
        assert N == 1747 and fmt(N) == "1,747"
        K_SLOW = 5
        for i in range(K_SLOW):
            v = seq[i][3]
            a, b = edges(probs(seq[i][2]))[v]
            dot = Circle(radius=u(24), stroke_width=0, fill_color=YELLOW, fill_opacity=1).move_to(px((a + b) / 2, 720))
            dt = jp(names4[v], 30, BG).move_to(dot)
            dot.check_ignore = True
            dt.check_ignore = True
            self.add(dot, dt)
            hot = ruler[v].copy().set_fill(YELLOW, 1)
            self.play(VGroup(dot, dt).animate.move_to(px((a + b) / 2, RY)).set_opacity(0), FadeIn(hot), run_time=0.3)
            self.remove(dot, dt)
            nxt = probs(seq[i + 1][2])
            self.play(FadeOut(hot), Transform(ruler, multi(nxt, COL4)),
                      *[t.animate.move_to(px((a_ + b_) / 2, RY)) for t, (a_, b_) in zip(labs, edges(nxt))],
                      run_time=0.18)
        T_fast = self.cue("S08_06.end") + 0.35 - self.now
        P = np.array([probs(s[2]) for s in seq[K_SLOW:]])
        M = len(P)

        class Fast(Animation):
            def __init__(s_, **kw):
                super().__init__(Group(ruler, labs), rate_func=linear, **kw)

            def interpolate_mobject(s_, alpha):
                e = smooth(alpha)
                f = (math.exp(5 * e) - 1) / (math.exp(5) - 1) * (M - 1)
                j = int(f)
                w = f - j
                ps = P[j] * (1 - w) + P[min(j + 1, M - 1)] * w
                place(list(ps))
        self.play(Fast(run_time=T_fast), run_time=T_fast)
        assert abs(P[-1][0] - p4[0]) > 0.05                       # 最初と最後で幅が目に見えて変わる

        # ---- 読み取り回数の帯 ----
        self.at("count", -0.1)
        title = jp(f"読み取り {fmt(n_all)} 回", 44, INK).move_to(px(960, BAR_Y - BAR_H / 2 - 44))
        band = rect(RX0, RX1, BAR_Y, BAR_H, "#4a5060")
        self.play(FadeOut(VGroup(ruler, labs)), Succession(Wait(0.3), GrowFromEdge(band, LEFT, run_time=0.8)),
                  run_time=1.1)
        self.at("n", -0.1)
        self.play(FadeIn(title, shift=DOWN * u(8)), run_time=0.7)
        self.at("half", -0.1)
        xh = rx(n_cb / n_all)
        seg = rect(RX0, xh, BAR_Y, BAR_H, YELLOW)
        mid = DashedLine(px(960, BAR_Y - BAR_H / 2 - 12), px(960, BAR_Y + BAR_H / 2 + 12), color=INK, stroke_width=3,
                         dash_length=u(10))
        seg_t = jp(f"4択の判定 {fmt(n_cb)} 回", 40, YELLOW).move_to(px((RX0 + xh) / 2, BAR_Y + BAR_H / 2 + 46))
        self.play(GrowFromEdge(seg, LEFT), FadeIn(seg_t, shift=UP * u(8)), Create(mid), run_time=1.0)
        self.at("this", -0.1)
        self.play(Indicate(VGroup(one, one_t), color=YELLOW, scale_factor=1.06), run_time=0.9)
        self.at("fewer", -0.1)
        self.play(pop(VGroup(seg, seg_t), 1.05, 0.8), run_time=0.8)

        # ---- 比較表 ----
        self.at("card", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        lit = np.full((H, W), 0.55, np.float32)
        view.lit = lit
        view.refresh()
        view.set_opacity(0)
        self.add(view)
        card = compare_card(6, center=(960, 420), new=5)
        self.play(FadeOut(VGroup(one, one_t, title, band, seg, seg_t, mid)), view.animate.set_opacity(1),
                  FadeIn(card, shift=UP * u(30)), run_time=0.8)
        self.play(add_row(card, run_time=1.1), run_time=1.1)

        # 終わり：写真だけ (S09 の最初の画面)
        self.at(self.tl["duration"] - 1.3)
        lit0 = lit.copy()

        def undim(t):
            lit[:] = lit0 + (1 - lit0) * t
            view.lit = lit
        self.play(FadeOut(card), ViewAnim(view, undim), run_time=1.0)
        view.lit = None
        self.finish()
