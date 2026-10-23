import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import MAIN, SIZE_COLOR, boxes, ctx_trace, cus, dec, picture_size, rgb_decoded, size, splits  # noqa: E402
import hevctables as HT  # noqa: E402,I001  (vlib.data が tools/ を探す場所に入れる)
from vlib.photoview import Grow, PhotoView, ViewAnim, move_view, partition_lines  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.paths import video_config  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

# クレジット (WebP 編と同じ文言 ＋ この動画の写真。写真は video.yaml の extra_credits から)
CREDITS = [("音声", ["VOICEVOX:ずんだもん", "VOICEVOX:四国めたん"]), ("立ち絵", ["坂本アヒル 様"]),
           ("音楽", ["甘茶の音楽工房"]), ("効果音", ["効果音ラボ"]),
           ("フォント", ["Zen Maru Gothic", "M PLUS Rounded 1c", "JetBrains Mono"]),
           ("映像", ["Manim Community"])]

# ---- 配置 ----
SX0, SX1, SY, SH = 70, 900, 100, 72                 # 1：ファイルの帯 (S02 の帯を小さく)
SEG_COL = {"ftyp": YELLOW, "meta": BLUE, "mdat": "#4a5060"}
EQ_Y = 215
PHOTO_S = ((748, 668), 600, 400)                    # 2：写真と割れ方
PHOTO_L = ((960, 470), 960, 640)                    # 最後に大きく
FAN_O, R0, R1 = (1400, 225), 34, 205                # 3：35 通りの向き (S04 の扇)
RX0, RX1, RY, RH = 1100, 1462, 525, 60              # 4：確率の定規 (S07)
DOT_Y = 600
PX0, PY, PSTEP, PUNIT = 1112, 830, 26, 28           # 4：山と谷 (SAO)


def flow_dir(m):
    """角度の予想 m の、点の流れる向き (画面の px、下が +y)。S04 と同じ"""
    a = HT.INTRA_ANGLE[m] / 32
    return np.array([-a, 1.0]) if m >= 18 else np.array([1.0, -a])


def unit(d):
    d = np.asarray(d, float)
    return d / np.hypot(*d)


def arrow(a, b, color, width=4, tip=16):
    return Arrow(a, b, buff=0, color=color, stroke_width=width, tip_length=u(tip),
                 max_tip_length_to_length_ratio=0.5, max_stroke_width_to_length_ratio=40)


def rect(x0, x1, y, h, color):
    return Rectangle(width=u(max(x1 - x0, 0.5)), height=u(h), stroke_width=0, fill_color=color,
                     fill_opacity=1).move_to(px((x0 + x1) / 2, y))


def ruler(p):
    """左が「はい」(青・幅 p)、右が「いいえ」(珊瑚)。S07 と同じ"""
    xm = RX0 + (RX1 - RX0) * p
    return VGroup(rect(RX0, xm, RY, RH, BLUE), rect(xm, RX1, RY, RH, CORAL),
                  Rectangle(width=u(RX1 - RX0), height=u(RH), stroke_color=INK, stroke_width=3,
                            fill_opacity=0).move_to(px((RX0 + RX1) / 2, RY)))


class Ruler(Animation):
    """定規の境目を確率の列に沿って動かし、答えの点を 1 つずつ置く"""

    def __init__(self, bar, trace, dots, **kw):
        super().__init__(VGroup(bar, dots), rate_func=linear, **kw)
        self.bar, self.trace, self.dots = bar, trace, dots

    def interpolate_mobject(self, alpha):
        n = len(self.trace)
        f = alpha * n
        k = min(int(f), n - 1)
        p0 = self.trace[k][0]
        p1 = self.trace[k + 1][0] if k + 1 < n else p0
        t = smooth(min(1.0, (f - k) * 2.5))
        self.bar.become(ruler(p0 + (p1 - p0) * t))
        for i, d in enumerate(self.dots):
            d.set_opacity(1 if i < f else 0)


class LineOp(Animation):
    """PLine の不透明度を変える (s03 と同じ)"""

    def __init__(self, lines, to, **kw):
        self.lines = list(lines)
        super().__init__(VGroup(*self.lines), **kw)
        self.to = to
        self.start = [ln._op for ln in self.lines]

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        for ln, s in zip(self.lines, self.start):
            ln._op = s + (self.to - s) * a
            ln.sync()


class S11(PScene):
    def construct(self):
        # ================= データ =================
        r = boxes(MAIN)
        total = size(MAIN)
        tree = r["tree"]
        assert [(b["type"], b["size"]) for b in tree] == [("ftyp", 24), ("meta", 385), ("mdat", 12959)]
        assert sum(b["size"] for b in tree) == total
        W, H = picture_size()
        assert (W, H) == (451, 300)
        assert len(HT.INTRA_ANGLE) == 35 and sum(a is not None for a in HT.INTRA_ANGLE) == 33     # 35 通り
        ex = next(p for c in cus() for p in c["pus"] if p["cand"] == [5, 4, 6] and p["mode"] == 4)  # S05 の見本
        assert ex["mpm"] and ex["mpm_idx"] == 1
        trace = ctx_trace("significant_coeff_flag", 24)[:14]                                  # S07 と同じ文脈
        assert len(trace) == 14
        d = dec()
        sao_x, sao_y, L = 306, 104, 14                                                        # 縦の端の補正 (縦に並ぶ 14 点)
        before = [int(v) for v in np.asarray(d.deblocked[0])[sao_y:sao_y + L, sao_x]]
        after = [int(v) for v in np.asarray(d.final[0])[sao_y:sao_y + L, sao_x]]
        sao = d.sao[(sao_x // 64, sao_y // 64)][0]
        assert sao["type"] == 2 and sao["eo_class"] == 1
        assert before == [143, 142, 144, 144, 145, 145, 144, 143, 144, 144, 144, 141, 142, 143]
        assert after == [143, 143, 143, 144, 144, 144, 144, 144, 143, 144, 143, 142, 142, 142]
        assert max(after) - min(after) < max(before) - min(before)                            # 山と谷がならされる
        photo = [x for k, v in video_config()["extra_credits"] if k == "写真" for x in v][0]
        credits = CREDITS + [("写真", [s.strip() for s in photo.split(" / ")])]

        # ================= 1：HEIF の箱 ＋ HEVC の中身 =================
        def xb(b):
            return SX0 + (SX1 - SX0) * b / total
        seg = VGroup()
        for b in tree:
            x0, x1 = xb(b["pos"]), xb(b["pos"] + b["size"])
            seg.add(Rectangle(width=u(max(x1 - x0, 3)), height=u(SH), stroke_width=0, fill_color=SEG_COL[b["type"]],
                              fill_opacity=1).move_to(px(x0, SY), aligned_edge=LEFT))
        tag = mix("HEVC", 44, YELLOW).move_to(seg[2])
        e1, e2, e3, e4, e5 = (mix("HEIFの箱", 52, BLUE), mix("＋", 56, DIM), mix("HEVCの中身", 52, YELLOW),
                              mix("＝", 64, DIM), mix("HEIC", 56, INK))
        eq = VGroup(e1, e2, e3, e4, e5).arrange(RIGHT, buff=u(18)).move_to(px((SX0 + SX1) / 2, EQ_Y))
        self.at("t1", -0.1)
        self.play(Succession(GrowFromEdge(seg[0], LEFT, run_time=0.1), GrowFromEdge(seg[1], LEFT, run_time=0.2),
                             GrowFromEdge(seg[2], LEFT, run_time=0.8, rate_func=rate_functions.ease_out_cubic)),
                  run_time=1.1)
        self.play(FadeIn(tag, scale=0.8), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(e, shift=RIGHT * u(12)) for e in eq], lag_ratio=0.3), run_time=1.6)
        part1 = VGroup(seg, tag, eq)

        # ================= 2：大きさを選ぶブロック =================
        view = PhotoView(rgb_decoded(), *PHOTO_S)
        view.check_ignore = True
        levels = partition_lines(view, splits(), cus(), W, H, SIZE_COLOR, frac=0)
        allines = [ln for k in (64, 32, 16, 8, 4) for ln in levels[k]]
        self.at("t2", -0.2)
        self.play(FadeIn(view, shift=UP * u(10)), run_time=0.6)
        self.add(*allines)
        self.play(Succession(*[AnimationGroup(*[Grow(ln) for ln in levels[k]], run_time=0.5) for k in (64, 32, 16, 8, 4)]),
                  run_time=2.5)

        # ================= 3：35 通りの向きと、向きの予想 =================
        O = np.array(FAN_O, float)

        def ray(m, color=CYAN, width=3.5, r1=R1):
            v = unit(flow_dir(m))
            return arrow(px(*(O + R0 * v)), px(*(O + r1 * v)), color, width=width, tip=15)
        modes = list(range(2, 35))
        fan = VGroup(*[ray(m) for m in modes])
        blk = Square(u(36), stroke_color=INK, stroke_width=3).move_to(px(*O))
        lab35 = mix("35通り", 52, CYAN).move_to(px(1760, 225))
        self.at("t3", -0.1)
        self.play(Create(blk), FadeIn(lab35, shift=LEFT * u(10)),
                  LaggedStart(*[GrowArrow(a) for a in fan], lag_ratio=0.06), run_time=1.8)
        # その向きまで予想：候補 3 つ (S05 の見本)
        self.at("t3", 2.3)
        cand = [fan[modes.index(m)] for m in ex["cand"]]
        self.play(fan.animate.set_opacity(0.3), *[c.animate.set_color(YELLOW).set_opacity(1) for c in cand], run_time=0.6)
        hit = fan[modes.index(ex["mode"])]
        self.play(pop(hit, 1.15, 0.6), run_time=0.6)
        part3 = VGroup(fan, blk, lab35)

        # ================= 4：確率を覚えながら書く (S07 の定規) =================
        bar = ruler(trace[0][0])
        dots = VGroup(*[Dot(px(RX0 + 14 + i * ((RX1 - RX0 - 28) / (len(trace) - 1)), DOT_Y), radius=u(11),
                            color=BLUE if b else CORAL) for i, (_, b) in enumerate(trace)])
        dots.set_opacity(0)
        self.at("t4", -0.1)
        self.play(FadeIn(bar, shift=UP * u(8)), run_time=0.4)
        self.add(dots)
        self.play(Ruler(bar, trace, dots), run_time=1.7)

        # ---- 最後に山と谷をならす (SAO) ----
        vmin = min(before)

        def pts(vals):
            return [px(PX0 + i * PSTEP, PY - (v - vmin) * PUNIT) for i, v in enumerate(vals)]
        base = Line(px(PX0 - 10, PY + 14), px(PX0 + (L - 1) * PSTEP + 10, PY + 14), stroke_color=DIM, stroke_width=2)
        poly = VMobject(stroke_color=CORAL, stroke_width=4).set_points_as_corners(pts(before))
        pdots = VGroup(*[Dot(p, radius=u(7), color=CORAL) for p in pts(before)])
        self.at("t4", 2.15)
        self.play(Create(base), Create(poly), LaggedStart(*[FadeIn(p, scale=0.5) for p in pdots], lag_ratio=0.05),
                  run_time=0.6)
        poly2 = VMobject(stroke_color=CYAN, stroke_width=4).set_points_as_corners(pts(after))
        pdots2 = VGroup(*[Dot(p, radius=u(7), color=CYAN) for p in pts(after)])
        self.play(Transform(poly, poly2), Transform(pdots, pdots2), run_time=1.0)
        part4 = VGroup(bar, dots, base, poly, pdots)

        # ================= 場所ごとに選んでいる =================
        size_of = np.zeros((dec().H, dec().W), np.int32)
        for c in cus():
            size_of[c["y"]:c["y"] + c["size"], c["x"]:c["x"] + c["size"]] = 4 if c["nxn"] else c["size"]
        size_of = size_of[:H, :W]
        lit = np.ones((H, W), np.float32)

        def spot(target):
            src = lit.copy()

            def fn(t):
                lit[:] = src + (target - src) * t
                view.lit = lit
            return ViewAnim(view, fn)
        small_m = np.where(size_of <= 8, 1.0, 0.3).astype(np.float32)
        big_m = np.where(size_of == 32, 1.0, 0.3).astype(np.float32)
        self.at("s11_06", -0.3)
        self.play(FadeOut(part1), FadeOut(part3), FadeOut(part4), move_view(view, (0, 0, W, H), PHOTO_L), run_time=1.1)
        self.at("s11_06", 0.8)
        self.play(spot(small_m), run_time=0.6)
        self.at("s11_06", 1.7)
        self.play(spot(big_m), run_time=0.6)
        self.at("s11_06", 3.0)
        self.play(spot(np.ones((H, W), np.float32)), run_time=0.7)

        # ================= どこが大きなブロックになるか =================
        self.at("think", -0.1)
        self.play(spot(big_m), run_time=0.8)
        self.at("S11_07.end", -0.6)
        self.play(spot(np.ones((H, W), np.float32)), run_time=0.6)

        # ---- 図が消えて、クレジット ----
        self.at("S11_07.end", 0.3)
        self.play(view.animate.set_opacity(0), LineOp(allines, 0), run_time=1.4)
        for ln in allines:
            ln.clear_updaters()
        self.remove(view, *allines)
        title = jp("クレジット", 44, INK).move_to(px(960, 70))
        cred = VGroup(title)
        y = 150
        for cat_, vals in credits:
            cred.add(jp(cat_, 34, DIM).move_to(px(470, y), aligned_edge=LEFT))
            for v_ in vals:
                cred.add(mix(v_, 34, INK).move_to(px(710, y), aligned_edge=LEFT))
                y += 52
            y += 16
        assert y < 880
        self.at("S11_07.end", 1.9)
        self.play(FadeIn(cred, shift=UP * u(10)), run_time=1.0)

        # ---- 「ありがとう」「またね」のあと、ゆっくり消える ----
        self.at("S11_09.end", 0.8)
        self.play(FadeOut(cred), run_time=self.until(self.tl["duration"], -0.3))
        self.finish()
