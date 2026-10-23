import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import math  # noqa: E402

import numpy as np  # noqa: E402

from vlib.data import cabac_costs, ctx_trace, fmt  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NEUTRAL = "#2c3240"
UNREAD = "#4a5060"
RX0, RX1, RY, RH = 460, 1460, 330, 80          # 思い出しの定規 (WebP 編と同じ大きさ)
COLS = {"webp": 700, "heic": 1220}             # WebP と HEIC の列の真ん中
CW = 440                                       # 列の定規と帯の幅
CRY, CRH = 350, 70                             # 列の定規
CSY, CSH = 540, 70                             # 列のファイルの帯
MX0, MX1, MY, MH = 460, 1460, 290, 90          # 確率のメーター
SX0, SX1, SY, SH, HEAD = 460, 1460, 480, 48, 960   # 答えの流れ (左が読んだもの)
G0 = 56                                        # 答えの点の間隔 (ゆっくりの間)
GX0, GX1, GY0, GY1, PMAX = 540, 1440, 590, 850, 0.7   # 確率の移り変わりのグラフ


def rgb(c):
    return np.array(ManimColor(c).to_rgb(), np.float32)


def rect(x0, x1, y, h, color, op=1.0):
    w = max(x1 - x0, 0.5)
    return Rectangle(width=u(w), height=u(h), stroke_width=0, fill_color=color, fill_opacity=op).move_to(
        px((x0 + x1) / 2, y))


def ruler(x0, x1, y, h, p, frame=True):
    """左が「はい」(青・幅 p)、右が「いいえ」(珊瑚)"""
    xm = x0 + (x1 - x0) * p
    g = VGroup(rect(x0, xm, y, h, BLUE), rect(xm, x1, y, h, CORAL))
    if frame:
        g.add(Rectangle(width=u(x1 - x0), height=u(h), stroke_color=INK, stroke_width=3, fill_opacity=0)
              .move_to(px((x0 + x1) / 2, y)))
    return g


class Drive(Animation):
    """f(t) で場面の部品を描き直す (t はこのアニメーションの中の秒)"""

    def __init__(self, mobs, f, run_time, **kw):
        self.f, self.T = f, run_time
        super().__init__(Group(*mobs), run_time=run_time, rate_func=linear, **kw)

    def interpolate_mobject(self, alpha):
        self.f(alpha * self.T)


class S07(PScene):
    def construct(self):
        # ---- データ ----
        trace = ctx_trace("significant_coeff_flag", 24)
        N = len(trace)
        P = np.array([p for p, _ in trace])
        A = np.array([b for _, b in trace], np.float32)
        share = float(A.mean())
        assert N == 6929 and fmt(N) == "6,929"
        assert round(P[0] * 100) == 6 and abs(P[0] - 0.062) < 0.001     # 最初は「はい」6%くらい
        assert round(share * 100) == 27                                  # 実際の「はい」は 27%
        assert P.max() < PMAX
        costs = cabac_costs()
        n, fixed, adapt = costs["n"], costs["fixed"], costs["adapt"]
        assert (n, costs["one_bit"], fixed, adapt) == (75349, 75349, 65210, 59759)
        assert n // 1000 == 75 and fixed // 1000 == 65 and round(adapt / 10000) == 6     # 7万5千 / 6万5千 / 6万
        CUM = np.concatenate([[0.0], np.cumsum(A)])
        p_wide = 0.8                                  # 思い出しの定規 (例)
        bits_wide = -math.log2(p_wide)
        assert f"{bits_wide:.2f}" == "0.32"

        # ================= 算術符号の定規 (WebP 編の思い出し) =================
        self.at("ruler", -0.1)
        frame = Rectangle(width=u(RX1 - RX0), height=u(RH), stroke_color=INK, stroke_width=3, fill_color=NEUTRAL,
                          fill_opacity=1).move_to(px(960, RY))
        r0 = jp("0", 30, DIM).move_to(px(RX0, RY + RH / 2 + 26))
        r1 = jp("1", 30, DIM).move_to(px(RX1, RY + RH / 2 + 26))
        self.play(GrowFromEdge(frame, LEFT), FadeIn(r0), FadeIn(r1), run_time=0.9)
        big = ruler(RX0, RX1, RY, RH, 0.5)
        tyes = jp("はい", 40, INK).move_to(px((RX0 + 960) / 2, RY))
        tno = jp("いいえ", 40, INK).move_to(px((960 + RX1) / 2, RY))
        self.play(FadeIn(big[:2]), FadeIn(tyes), FadeIn(tno), run_time=0.7)
        self.add(big)
        self.remove(frame)
        self.bring_to_front(tyes, tno)

        self.at("wide", -0.1)
        xm = RX0 + (RX1 - RX0) * p_wide
        self.play(Transform(big, ruler(RX0, RX1, RY, RH, p_wide)),
                  tyes.animate.move_to(px((RX0 + xm) / 2, RY)), tno.animate.move_to(px((xm + RX1) / 2, RY)),
                  run_time=1.1)
        self.play(pop(tyes, 1.2, 0.6), run_time=0.6)

        self.at("p", -0.1)
        cost = jp(f"はい → {bits_wide:.2f}ビット", 44, INK, t2c={"はい": BLUE}).move_to(px((RX0 + xm) / 2, RY + 120))
        self.play(FadeIn(cost, shift=UP * u(10)), run_time=0.6)
        self.play(pop(cost, 1.12, 0.6), run_time=0.6)

        # ================= WebP と HEIC =================
        def col_ruler(c, p):
            x = COLS[c]
            return ruler(x - CW / 2, x + CW / 2, CRY, CRH, p)

        self.at("webp", -0.1)
        lab_w = jp("WebP", 48, INK).move_to(px(COLS["webp"], 240))
        wx0 = COLS["webp"] - CW / 2
        wcells = VGroup(*[RoundedRectangle(corner_radius=u(6), width=u(38), height=u(CSH), stroke_width=0,
                                           fill_color=UNREAD, fill_opacity=1).move_to(px(wx0 + 125 + 44 * i, CSY))
                          for i in range(8)])
        self.play(Transform(big, col_ruler("webp", p_wide)), FadeOut(VGroup(tyes, tno, r0, r1, cost)),
                  FadeIn(lab_w, shift=DOWN * u(8)),
                  LaggedStart(*[FadeIn(c, shift=LEFT * u(10)) for c in wcells], lag_ratio=0.08), run_time=0.85)

        self.at("head", -0.1)
        tbl = RoundedRectangle(corner_radius=u(6), width=u(96), height=u(CSH), stroke_width=0, fill_color=YELLOW,
                               fill_opacity=1).move_to(px(wx0 + 48, CSY))
        tbl_t = jp("確率", 30, BG).move_to(tbl)
        arr_w = Arrow(px(wx0 + 48, CSY - CSH / 2 - 4), px(wx0 + 48, CRY + CRH / 2 + 4), buff=0, color=YELLOW,
                      stroke_width=6, max_tip_length_to_length_ratio=0.3)
        cap_w = jp("確率の表を先に書く", 40, INK).move_to(px(COLS["webp"], 640))
        self.play(FadeIn(VGroup(tbl, tbl_t), shift=RIGHT * u(16)), run_time=0.6)
        self.play(GrowArrow(arr_w), FadeIn(cap_w, shift=UP * u(8)), run_time=0.7)
        self.play(pop(big, 1.04, 0.6), run_time=0.6)

        self.at("heic", -0.1)
        lab_h = jp("HEIC", 48, INK).move_to(px(COLS["heic"], 240))
        hx0 = COLS["heic"] - CW / 2
        hcells = [RoundedRectangle(corner_radius=u(6), width=u(38), height=u(CSH), stroke_width=0,
                                   fill_color=UNREAD, fill_opacity=1).move_to(px(hx0 + 19 + 44 * i, CSY))
                  for i in range(10)]
        hr = col_ruler("heic", p_wide)
        self.play(ReplacementTransform(big.copy(), hr, path_arc=-0.6), FadeIn(lab_h, shift=DOWN * u(8)),
                  LaggedStart(*[FadeIn(c, shift=LEFT * u(10)) for c in hcells], lag_ratio=0.06), run_time=0.8)

        self.at("learn", -0.1)
        cap_h = jp("読むたびに確率を直す", 40, INK).move_to(px(COLS["heic"], 640))
        mark = Triangle(color=YELLOW, fill_opacity=1, stroke_width=0).rotate(PI).scale_to_fit_width(u(24))
        mark.move_to(hcells[0].get_top() + UP * u(20))
        self.play(FadeIn(cap_h, shift=UP * u(8)), FadeIn(mark), run_time=0.4)
        pattern = [1, 1, 0, 1, 1, 0, 1, 1]          # 例の答え (はい・いいえ)
        p = p_wide
        dt = (self.cue("name") - 0.15 - self.now) / len(pattern)
        for i, b in enumerate(pattern):
            p = p + 0.09 * (b - p)
            xm_h = hx0 + CW * p
            fly = Dot(hcells[i].get_center(), radius=u(10), color=BLUE if b else CORAL)
            fly.check_ignore = True
            self.add(fly)
            self.play(hcells[i].animate.set_fill(BLUE if b else CORAL),
                      mark.animate.move_to(hcells[min(i + 1, len(hcells) - 1)].get_top() + UP * u(20)),
                      fly.animate(path_arc=-0.9).move_to(px(xm_h, CRY)).set_opacity(0),
                      Transform(hr, col_ruler("heic", p)), run_time=dt)
            self.remove(fly)

        self.at("name", -0.1)
        cab = jp("CABAC", 72, YELLOW).move_to(px(COLS["heic"], 770))
        self.play(FadeIn(cab, scale=0.8), run_time=0.6)
        self.play(pop(cab, 1.15, 0.6), run_time=0.6)

        # ================= 1 つの問いで、確率のメーター =================
        self.at("ex", -0.1)
        meter = hr
        lab_y = jp("はい", 40, BLUE).move_to(px(MX0 - 60, MY))
        lab_n = jp("いいえ", 40, CORAL).move_to(px(MX1 + 80, MY))
        self.play(FadeOut(VGroup(lab_w, big, *wcells, tbl, tbl_t, arr_w, cap_w, lab_h, *hcells, cap_h, mark)),
                  Transform(meter, ruler(MX0, MX1, MY, MH, p)), run_time=1.0)
        self.play(FadeIn(lab_y, shift=RIGHT * u(8)), FadeIn(lab_n, shift=LEFT * u(8)), run_time=0.5)

        self.at("q", -0.1)
        card = RoundedRectangle(corner_radius=u(18), width=u(580), height=u(100), stroke_color=YELLOW, stroke_width=3,
                                fill_color="#232833", fill_opacity=1).move_to(px(960, 100))
        card_t = jp("この数は0じゃない？", 46, INK).move_to(card)
        self.play(FadeIn(card, shift=DOWN * u(12)), FadeIn(card_t, shift=DOWN * u(12)), FadeOut(cab), run_time=0.7)

        def mx(q):
            return MX0 + (MX1 - MX0) * q

        self.at("start", -0.1)
        tick6 = Line(px(mx(P[0]), MY + MH / 2), px(mx(P[0]), MY + MH / 2 + 18), color=BLUE, stroke_width=4)
        lab6 = jp(f"{round(P[0] * 100)}%", 44, BLUE).move_to(px(mx(P[0]), MY + MH / 2 + 46))
        self.play(Transform(meter, ruler(MX0, MX1, MY, MH, P[0])),
                  Succession(Wait(0.45), AnimationGroup(Create(tick6), FadeIn(lab6, shift=UP * u(8)))), run_time=0.85)
        self.at("p6", -0.05)
        self.play(pop(lab6, 1.25, 0.6), run_time=0.6)

        # ---- 答えの流れ ----
        SW = SX1 - SX0
        SS = 4                                       # 横の重ね取り
        xs = SX0 + (np.arange(SW * SS) + 0.5) / SS   # 標本の x (px)
        dy = np.arange(SH) + 0.5 - SH / 2            # 行の y (真ん中から)
        C_YES, C_NO, C_UN = rgb(BLUE), rgb(CORAL), rgb(UNREAD)
        R = 20

        def cum(x):
            x = np.clip(x, 0, N)
            i = np.minimum(np.floor(x).astype(int), N - 1)
            return CUM[i] + (x - i) * A[i]

        def strip_rgba(s, g, fade=1.0):
            # 点の並び (g が大きいとき)
            t = (xs - HEAD) / g + s - 0.5
            k = np.round(t).astype(int)
            dx = (t - k) * g
            ok = (k >= 0) & (k < N)
            kk = np.clip(k, 0, N - 1)
            hw = min(R, 0.4 * g)
            lim = R - hw + np.sqrt(np.maximum(hw * hw - dx * dx, 0))
            lim[np.abs(dx) > hw] = -1
            a = np.clip(lim[None, :] - np.abs(dy)[:, None] + 0.5, 0, 1) * ok[None, :]
            rd = np.clip((s - (kk + 0.5)) * 5 + 0.5, 0, 1)
            ans = A[kk][:, None]
            col = (rd[:, None] * (ans * C_YES + (1 - ans) * C_NO) + (1 - rd[:, None]) * C_UN)
            pm = a[..., None] * col[None, :, :]                       # 前掛けの色
            pm = pm.reshape(SH, SW, SS, 3).mean(2)
            am = a.reshape(SH, SW, SS).mean(2)
            w = float(np.clip((g - 2) / 2, 0, 1))
            if w < 1:
                # 点が細かいときは、1 列に入る答えの割合で塗る
                xc = SX0 + np.arange(SW + 1)
                ia = (xc - HEAD) / g + s - 0.5 + 0.5           # 列の端 → 答えの番号
                lo, hi = ia[:-1], ia[1:]
                tot = np.clip(hi, 0, N) - np.clip(lo, 0, N)
                rlo, rhi = np.clip(lo, 0, min(s, N)), np.clip(hi, 0, min(s, N))
                rtot = np.maximum(rhi - rlo, 0)
                yes = np.maximum(cum(rhi) - cum(rlo), 0)
                no = rtot - yes
                un = np.maximum(tot - rtot, 0)
                cov = 0.8 * np.clip(tot / (hi - lo), 0, 1)
                den = np.maximum(tot, 1e-9)
                dcol = (yes[:, None] * C_YES + no[:, None] * C_NO + un[:, None] * C_UN) / den[:, None]
                da = np.clip(R + 0.5 - np.abs(dy), 0, 1)[:, None] * cov[None, :]
                pm = w * pm + (1 - w) * da[..., None] * dcol[None, :, :]
                am = w * am + (1 - w) * da
            out = np.zeros((SH, SW, 4), np.uint8)
            am_ = np.maximum(am, 1e-6)
            out[..., :3] = np.clip(pm / am_[..., None] * 255, 0, 255).astype(np.uint8)
            out[..., 3] = np.clip(am * fade * 255, 0, 255).astype(np.uint8)
            return out

        strip = ImageMobject(strip_rgba(0, G0, 0))
        strip.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
        strip.width = u(SW)
        strip.move_to(px((SX0 + SX1) / 2, SY))
        strip.check_ignore = True
        head = Triangle(color=YELLOW, fill_opacity=1, stroke_width=0).rotate(PI).scale_to_fit_width(u(26))
        head.move_to(px(HEAD, SY - SH / 2 - 18))

        def p_at(s):
            k = int(min(math.floor(s), N - 1))
            if k >= N - 1:
                return P[N - 1]
            fr = s - k
            w = smooth(float(np.clip((fr - 0.5) / 0.45, 0, 1)))
            return P[k] + (P[k + 1] - P[k]) * w

        # グラフ (確率の移り変わり)
        GW, GH = GX1 - GX0, GY1 - GY0
        gimg_full = np.zeros((GH, GW, 4), np.float32)
        gy = GH - P / PMAX * GH
        cidx = np.arange(N) / (N - 1) * (GW - 1)
        for c in range(GW):
            i0 = int(np.searchsorted(cidx, c - 0.5))
            i1 = int(np.searchsorted(cidx, c + 0.5))
            i0, i1 = max(i0 - 1, 0), min(max(i1, i0 + 1) + 1, N)
            y_lo, y_hi = gy[i0:i1].min() - 1.3, gy[i0:i1].max() + 1.3
            yy = np.arange(GH) + 0.5
            a = np.clip(np.minimum(yy - y_lo, y_hi - yy) + 0.5, 0, 1)
            gimg_full[:, c, 3] = a
        gimg_full[..., :3] = C_YES

        def graph_rgba(s, fade=1.0):
            xcut = s / (N - 1) * (GW - 1)
            m = np.clip(xcut + 1 - np.arange(GW), 0, 1)
            out = np.zeros((GH, GW, 4), np.uint8)
            out[..., :3] = (gimg_full[..., :3] * 255).astype(np.uint8)
            out[..., 3] = np.clip(gimg_full[..., 3] * m[None, :] * fade * 255, 0, 255).astype(np.uint8)
            return out

        graph = ImageMobject(graph_rgba(0))
        graph.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
        graph.width = u(GW)
        graph.move_to(px((GX0 + GX1) / 2, (GY0 + GY1) / 2))
        graph.check_ignore = True
        gdot = Dot(px(GX0, GY1 - P[0] / PMAX * GH), radius=u(8), color=YELLOW)
        gdot.check_ignore = True

        def gyp(q):
            return GY1 - q / PMAX * GH

        state = {"s": 0.0, "g": G0}

        def show(s, g, fade=1.0, gfade=None):
            state["s"], state["g"] = s, g
            q = p_at(s)
            meter.become(ruler(MX0, MX1, MY, MH, q))
            strip.pixel_array = strip_rgba(s, g, fade)
            if gfade is not None:
                graph.pixel_array = graph_rgba(s, gfade)
                gdot.move_to(px(GX0 + s / (N - 1) * GW, gyp(q)))

        # グラフの台と、実際の割合
        axes = VGroup(Line(px(GX0, GY0 - 10), px(GX0, GY1), color=DIM, stroke_width=3),
                      Line(px(GX0, GY1), px(GX1, GY1), color=DIM, stroke_width=3))
        gtitle = jp("「はい」の確率", 30, DIM).move_to(px(GX0 + 12, GY0 - 30), aligned_edge=LEFT)
        g6 = jp(f"{round(P[0] * 100)}%", 30, BLUE).move_to(px(GX0 - 40, gyp(P[0])))
        glast = jp(f"{fmt(N)} 回", 30, DIM).move_to(px(GX1, GY1 + 28), aligned_edge=RIGHT)
        ref_g = DashedLine(px(GX0, gyp(share)), px(GX1, gyp(share)), color=YELLOW, stroke_width=3, dash_length=u(12))
        ref_gl = jp(f"{round(share * 100)}%", 30, YELLOW).move_to(px(GX0 - 44, gyp(share)))
        ref_m = Line(px(mx(share), MY - MH / 2 - 14), px(mx(share), MY + MH / 2 + 14), color=YELLOW, stroke_width=5)
        ref_ml = jp(f"実際 {round(share * 100)}%", 34, YELLOW).move_to(px(mx(share) + 8, MY - MH / 2 - 36))
        ref_ml.align_to(ref_m, LEFT)

        self.at("read", -0.1)
        self.add(strip, graph)
        self.play(Drive([strip, graph], lambda t: show(0, G0, smooth(t / 0.7), smooth(t / 0.7)), 0.7),
                  FadeIn(head, shift=DOWN * u(8)), Create(axes), FadeIn(gtitle), FadeIn(g6), FadeIn(glast),
                  run_time=0.7)
        self.add(gdot)
        self.play(FadeIn(gdot, scale=0.5), run_time=0.3)
        self.bring_to_front(lab6, tick6)

        # 最初の数個はゆっくり：1 つずつ読み、読んだらメーターが動く
        K_SLOW = 12
        steps = np.array([0.95, 0.75, 0.6, 0.5, 0.45, 0.42, 0.38, 0.35, 0.32, 0.3, 0.28, 0.26])
        assert len(steps) == K_SLOW
        t_slow0 = self.now
        T_slow = self.cue("fix") + 2.4 - t_slow0
        steps = steps / steps.sum() * T_slow
        edges = np.concatenate([[0], np.cumsum(steps)])
        assert A[:K_SLOW].sum() == 3 and A[0] == 1                      # 最初の答えは「はい」。12 個に 3 個

        def slow(t):
            j = int(np.clip(np.searchsorted(edges, t, side="right") - 1, 0, K_SLOW - 1))
            fr = np.clip((t - edges[j]) / steps[j], 0, 1)
            show(j + smooth(fr), G0, 1, 1)
        self.play(Drive([strip, meter, graph, gdot], slow, T_slow), run_time=T_slow)

        self.play(Create(ref_m), FadeIn(ref_ml, shift=DOWN * u(6)), Create(ref_g), FadeIn(ref_gl), run_time=0.6)

        # 残りを早送り
        S_END = N - 1
        T_fast = self.cue("learn2") + 2.6 - self.now
        a_ = 6.0

        def fast(t):
            e = smooth(t / T_fast)
            s = K_SLOW + (S_END - K_SLOW) * (math.exp(a_ * e) - 1) / (math.exp(a_) - 1)
            g = 1 / (1 / G0 + (s - K_SLOW) / (HEAD - SX0 - 4))
            show(s, g, 1, 1)
        self.play(Drive([strip, meter, graph, gdot], fast, T_fast), run_time=T_fast)
        self.play(pop(gdot, 1.6, 0.6), run_time=0.6)

        # ================= 写真全体のビット数 =================
        def fade_imgs(s_, g_, f_):
            strip.pixel_array = strip_rgba(s_, g_, f_)
            graph.pixel_array = graph_rgba(s_, f_)

        self.at("s07_06", -0.1)
        sg, gg = state["s"], state["g"]
        self.play(FadeOut(VGroup(card, card_t, meter, lab_y, lab_n, tick6, lab6, head, ref_m, ref_ml, axes, gtitle, g6,
                                 ref_g, ref_gl, gdot, glast)),
                  Drive([strip, graph], lambda t: fade_imgs(sg, gg, 1 - t / 0.7), 0.7), run_time=0.7)
        self.remove(strip, graph)

        BX0, BW = 520, 900
        rows = [(340, "1回1ビット", n, "#5a6070", "one"), (550, "最初の確率のまま", fixed, "#8a93a6", "fixed"),
                (760, "覚えながら", adapt, YELLOW, "adapt")]
        self.at("n", -0.1)
        qn = jp(f"確率を使う問い {fmt(n)} 回", 48, INK).move_to(px(960, 170))
        self.play(FadeIn(qn, shift=DOWN * u(10)), run_time=0.7)
        bars = []
        for y, name, v, col, cue in rows:
            self.at(cue, -0.1)
            lab = jp(name, 40, INK).move_to(px(BX0, y - 46), aligned_edge=LEFT)
            val = jp(f"{fmt(v)} ビット", 40, YELLOW if col == YELLOW else INK).move_to(px(BX0 + BW, y - 46),
                                                                                    aligned_edge=RIGHT)
            bar = rect(BX0, BX0 + BW * v / n, y + 18, 70, col)
            self.play(FadeIn(lab, shift=UP * u(8)), GrowFromEdge(bar, LEFT), FadeIn(val, shift=UP * u(8)), run_time=1.0)
            bars.append((lab, val, bar))

        self.at("save", -0.1)
        xa = BX0 + BW * adapt / n
        gap = rect(xa, BX0 + BW, rows[2][0] + 18, 70, CORAL, 0.0)
        gap_f = Rectangle(width=u(BX0 + BW - xa), height=u(70), stroke_color=CORAL, stroke_width=3,
                          fill_color=CORAL, fill_opacity=0.25).move_to(gap)
        gap_f.check_ignore = True
        self.play(FadeIn(gap_f), run_time=0.5)
        self.play(pop(VGroup(bars[2][1], bars[2][2]), 1.08, 0.7), run_time=0.7)

        self.at(self.tl["duration"] - 0.8)
        self.play(FadeOut(VGroup(qn, gap_f, *[m for b in bars for m in b])), run_time=0.6)
        self.finish()
