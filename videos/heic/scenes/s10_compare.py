import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import DATA, cus, fmt, mean_abs_err, picture_size, pixels, size, splits  # noqa: E402
from vlib.data import SIZE_COLOR  # noqa: E402
from vlib.photoview import Grow, PhotoView, move_view, partition_lines  # noqa: E402
from zunda.fx import Shake, pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

KEYS = ("jpg", "webp", "heic")
FILES = {"jpg": "cat_q5.jpg", "webp": "cat_q10", "heic": "cat_q25"}
NAMES = {"jpg": "JPEG", "webp": "WebP", "heic": "HEIC"}
COLS = {"jpg": INK, "webp": "#aab1c0", "heic": YELLOW}          # S01 と同じ
PH_X, PH_Y, PH_W, PH_H = (330, 960, 1590), 235, 600, 400
ERR_Y = {"jpg": 610, "webp": 700, "heic": 790}                  # 元とのずれの棒 (2 人の間)
ERR_LX, ERR_X, ERR_MAX = 520, 610, 680
EYE_WIN = (112, 72, 232, 152)                                    # 目のあたり (画素の座標。3:2)
# 時間の棒
ROW_Y = {"jpg": 430, "webp": 560, "heic": 690}
LAB_X, BAR_X, BAR_MAX, BAR_H = 570, 640, 800, 60
# パソコンの窓 (S01 と同じ見た目)
PC_C, PC_W, PC_H = (960, 330), 600, 380


def ms(v):
    v *= 1000
    return f"{v:.2f}" if v < 1 else f"{v:.0f}"


class Race(Animation):
    """保存にかかった時間：3 本の棒が同じ速さで伸び、それぞれの時間で止まる"""

    def __init__(self, bars, times, t_max, **kw):
        self.bars, self.times, self.t_max = bars, times, t_max
        kw.setdefault("rate_func", linear)
        super().__init__(VGroup(*bars.values()), **kw)

    def interpolate_mobject(self, alpha):
        t = self.t_max * alpha
        for k, b in self.bars.items():
            w = max(BAR_MAX * min(t, self.times[k]) / self.t_max, 0.5)
            b.stretch_to_fit_width(u(w))
            b.move_to(px(BAR_X, ROW_Y[k]), aligned_edge=LEFT)
            b.set_fill(opacity=1 if t > 0 else 0)


class S10(PScene):
    def construct(self):
        # ---- 台詞の数字 ----
        n = {k: size(FILES[k]) for k in KEYS}
        assert (n["jpg"], n["webp"], n["heic"]) == (3797, 3898, 3791)
        assert all(abs(v - 4000) < 300 for v in n.values())                       # 4 千バイトくらい
        err = {k: mean_abs_err(FILES[k]) for k in KEYS}
        errs = {k: f"{err[k]:.1f}" for k in KEYS}
        assert (errs["jpg"], errs["webp"], errs["heic"]) == ("11.0", "5.6", "4.9")
        et = json.loads((DATA / "encode_time.json").read_text())
        tm = {"jpg": et["jpeg"]["median_s"], "webp": et["webp"]["median_s"], "heic": et["heic"]["median_s"]}
        ratio = tm["heic"] / tm["jpg"]
        assert ratio >= 200                                                       # JPEG の 200 倍以上
        W, H = picture_size(FILES["heic"])
        assert (W, H) == (451, 300)

        # ---- 3 枚の写真 ----
        views = {}
        for i, k in enumerate(KEYS):
            v = PhotoView(pixels(FILES[k]), (PH_X[i], PH_Y), PH_W, PH_H, win=(0, 0, 450, 300))
            v.check_ignore = True
            v.set_opacity(0)
            v.refresh()
            views[k] = v
            self.add(v)
        labs = {}
        for i, k in enumerate(KEYS):
            t = jp(f"{NAMES[k]}  {fmt(n[k])} バイト", 32, COLS[k])
            bg = RoundedRectangle(corner_radius=u(10), width=t.width + u(28), height=t.height + u(20), stroke_width=0,
                                  fill_color=BG, fill_opacity=0.85)
            bg.move_to(px(PH_X[i] - PH_W / 2 + 12, PH_Y - PH_H / 2 + 12), aligned_edge=UL)
            t.move_to(bg)
            labs[k] = VGroup(bg, t)
        self.at("s10_01", -0.1)
        self.play(*[views[k].animate.set_opacity(1) for k in KEYS],
                  LaggedStart(*[FadeIn(labs[k], shift=UP * u(8)) for k in KEYS], lag_ratio=0.2), run_time=1.0)

        # 3 枚とも同じ窓・同じ倍率で目へ
        self.at("tiny", 0.2)
        self.play(*[move_view(views[k], EYE_WIN, ((PH_X[i], PH_Y), PH_W, PH_H)) for i, k in enumerate(KEYS)],
                  run_time=2.4)

        # ---- 元とのずれ (棒の長さで比べる) ----
        head = jp("元とのずれ", 34, DIM).move_to(px(960, 535))
        elab = {k: jp(NAMES[k], 38, COLS[k]).move_to(px(ERR_LX, ERR_Y[k])) for k in KEYS}
        ebar, enum = {}, {}
        for k in KEYS:
            w = ERR_MAX * err[k] / err["jpg"]
            ebar[k] = Rectangle(width=u(w), height=u(56), stroke_width=0, fill_color=CORAL if k == "jpg" else COLS[k],
                                fill_opacity=1).move_to(px(ERR_X, ERR_Y[k]), aligned_edge=LEFT)
            enum[k] = jp(errs[k], 38, INK).move_to(px(ERR_X + w + 20, ERR_Y[k]), aligned_edge=LEFT)
        for j, (k, cue) in enumerate((("jpg", "jb"), ("webp", "wb"), ("heic", "hb"))):
            self.at(cue, -0.1)
            extra = [FadeIn(head)] if j == 0 else []
            self.play(FadeIn(elab[k], shift=RIGHT * u(8)), GrowFromEdge(ebar[k], LEFT), *extra, run_time=0.6)
            self.play(FadeIn(enum[k], shift=LEFT * u(6)), pop(views[k], 1.04, 0.6), run_time=0.6)
        self.play(pop(VGroup(elab["heic"], ebar["heic"], enum["heic"]), 1.06, 0.6), run_time=0.6)

        # ---- ブロックの大きさ (HEIC 品質 25 の実際の割れ方) ----
        self.at("why", -0.1)
        lv = partition_lines(views["heic"], splits(FILES["heic"]), cus(FILES["heic"]), W, H, SIZE_COLOR, frac=0)
        lines = [ln for k in (64, 32, 16, 8, 4) for ln in lv[k]]
        self.add(*lines)
        self.play(LaggedStart(*[Grow(ln, run_time=0.6) for ln in lines], lag_ratio=0.004), Animation(labs["heic"]),
                  run_time=1.6)

        # ---- 弱点 ----
        weak = jp("弱点", 48, CORAL).move_to(px(960, 100))
        self.at("s10_04", -0.1)
        for ln in lines:
            ln.clear_updaters()
        self.play(*[views[k].animate.set_opacity(0) for k in KEYS], FadeOut(VGroup(*lines)),
                  FadeOut(VGroup(*labs.values(), head, *elab.values(), *ebar.values(), *enum.values())), FadeIn(weak, scale=0.8), run_time=0.8)
        self.remove(*views.values(), *lines)

        # ---- 縮めるのにかかる時間 ----
        rlabs = {k: jp(NAMES[k], 40, COLS[k]).move_to(px(LAB_X, ROW_Y[k])) for k in KEYS}
        axis = Line(px(BAR_X, ROW_Y["jpg"] - 60), px(BAR_X, ROW_Y["heic"] + 60), stroke_color=DIM, stroke_width=3)
        self.at("slow", -0.1)
        self.play(LaggedStart(*[FadeIn(rlabs[k], shift=RIGHT * u(10)) for k in KEYS], lag_ratio=0.15), Create(axis),
                  run_time=0.9)
        bars = {k: Rectangle(width=u(1), height=u(BAR_H), stroke_width=0, fill_color=COLS[k], fill_opacity=0)
                .move_to(px(BAR_X, ROW_Y[k]), aligned_edge=LEFT) for k in KEYS}
        self.add(*bars.values())
        vals = {k: jp(f"{ms(tm[k])} ミリ秒", 40, COLS[k]) for k in KEYS}
        for k in KEYS:
            if k == "heic":     # 棒の端の内側 (右に場所がない)
                vals[k].set_color(BG).move_to(px(BAR_X + BAR_MAX - 20, ROW_Y[k]), aligned_edge=RIGHT)
            else:               # JPEG の棒は 2px ほどなので、軸のすぐ右
                vals[k].move_to(px(BAR_X + BAR_MAX * tm[k] / tm["heic"] + 20, ROW_Y[k]), aligned_edge=LEFT)
        T = 1.8
        self.at("time", -0.1)
        # 棒は同じ速さで伸びる。JPEG・WebP はすぐ止まり、数字が出る
        t_w = T * tm["webp"] / tm["heic"]
        self.play(Race(bars, tm, tm["heic"], run_time=T),
                  Succession(Wait(0.05), FadeIn(vals["jpg"], shift=LEFT * u(8), run_time=0.4)),
                  Succession(Wait(t_w), FadeIn(vals["webp"], shift=LEFT * u(8), run_time=0.4)), run_time=T)
        rt = jp(f"JPEGの {ratio:.0f}倍", 48, CORAL).move_to(px(1040, 800))
        self.play(FadeIn(vals["heic"], shift=LEFT * u(8)), FadeIn(rt, shift=UP * u(10)), run_time=0.5)
        self.play(pop(VGroup(rlabs["heic"], bars["heic"], vals["heic"]), 1.05, 0.6), run_time=0.6)

        # ---- 特許 ----
        self.at("patent", 0.6)
        chart = VGroup(*rlabs.values(), *bars.values(), *vals.values(), axis, rt)
        hevc = jp("HEVC", 56, YELLOW).move_to(px(960, 420))
        self.play(FadeOut(chart), FadeIn(hevc, scale=0.8), run_time=0.7)
        docs = VGroup()
        for j in range(12):
            ang = TAU * j / 12 + 0.2
            c = px(960 + 330 * np.cos(ang), 420 + 210 * np.sin(ang))
            paper = Rectangle(width=u(70), height=u(90), stroke_color=DIM, stroke_width=3, fill_color="#232833",
                              fill_opacity=1)
            rows = VGroup(*[Line(LEFT * u(22), RIGHT * u(22), stroke_color=DIM, stroke_width=3).shift(UP * u(dy))
                            for dy in (22, 7, -8, -23)])
            docs.add(VGroup(paper, rows).move_to(c))
        self.at("many", -0.1)
        self.play(LaggedStart(*[FadeIn(dd, scale=0.5) for dd in docs], lag_ratio=0.08), run_time=1.4)
        coins = VGroup()
        for j in range(3):
            cc = Circle(radius=u(38), stroke_color="#b38f2c", stroke_width=4, fill_color=YELLOW, fill_opacity=1)
            coins.add(VGroup(cc, jp("¥", 40, BG).move_to(cc)))
        self.at("pay", -0.1)
        for j, cn in enumerate(coins):
            cn.move_to(px(860 + j * 100, 760))
        self.play(LaggedStart(*[FadeIn(cn, shift=UP * u(30)) for cn in coins], lag_ratio=0.2), run_time=0.9)
        self.play(*[cn.animate(path_arc=-0.6).move_to(hevc.get_center() + DOWN * u(80) + RIGHT * u((j - 1) * 100))
                    for j, cn in enumerate(coins)], run_time=1.0)

        # ---- 開けない (S01 と同じ窓) ----
        self.at("cant", -0.1)
        mon = RoundedRectangle(corner_radius=u(16), width=u(PC_W), height=u(PC_H), stroke_color="#596075",
                               stroke_width=6, fill_color="#1c1f27", fill_opacity=1).move_to(px(*PC_C))
        neck = Rectangle(width=u(40), height=u(26), stroke_width=0, fill_color="#596075", fill_opacity=1)
        neck.move_to(px(PC_C[0], PC_C[1] + PC_H / 2 + 13))
        base = RoundedRectangle(corner_radius=u(6), width=u(200), height=u(12), stroke_width=0, fill_color="#596075",
                                fill_opacity=1).move_to(px(PC_C[0], PC_C[1] + PC_H / 2 + 30))
        card_c = (PC_C[0], PC_C[1] - 30)
        card = RoundedRectangle(corner_radius=u(14), width=u(268), height=u(178), stroke_width=0,
                                fill_color="#3a3f4c", fill_opacity=1).move_to(px(*card_c))
        qm = jp("？", 96, DIM).move_to(card)
        fname = jp("cat.heic", 40, INK).move_to(px(PC_C[0], PC_C[1] + 118))
        win = VGroup(mon, neck, base, card, qm, fname)
        self.play(FadeOut(VGroup(docs, coins, hevc), scale=0.8), FadeIn(win, scale=0.94), run_time=0.9)
        self.play(pop(qm, 1.25, 0.7), run_time=0.7)

        self.at("hook", -0.1)
        self.play(Shake(win, amp=12, run_time=0.6))

        # ---- AVIF ----
        t1 = mix("HEIFの箱", 56, BLUE)
        plus = mix("＋", 56, DIM)
        t2 = mix("HEVCの中身", 56, YELLOW)
        eqs = VGroup(*[Line(LEFT * u(20), RIGHT * u(20), stroke_color=DIM, stroke_width=5).shift(UP * u(d))
                       for d in (8, -8)])
        t3 = mix("HEIC", 64, INK)
        row = VGroup(t1, plus, t2, eqs, t3).arrange(RIGHT, buff=u(34)).move_to(px(960, 430))
        self.at("avif", -0.1)
        self.play(FadeOut(VGroup(win, weak)), LaggedStart(*[FadeIn(m, shift=DOWN * u(14)) for m in row], lag_ratio=0.12),
                  run_time=1.2)
        t2b = mix("AV1の中身", 56, CYAN)
        t3b = mix("AVIF", 64, CYAN)
        row2 = VGroup(t1.copy(), plus.copy(), t2b, eqs.copy(), t3b).arrange(RIGHT, buff=u(34)).move_to(px(960, 430))
        self.at("free", 1.0)
        self.play(*[m.animate.move_to(m2) for m, m2 in zip((t1, plus, eqs), (row2[0], row2[1], row2[3]))],
                  FadeOut(t2, shift=UP * u(40)), FadeIn(t2b, shift=UP * u(40)), run_time=0.9)
        self.play(ReplacementTransform(t3, t3b), run_time=0.7)
        self.wait(0.4)
        self.play(pop(t3b, 1.15, 0.7), run_time=0.7)

        self.at("next", 0.0)
        self.play(pop(VGroup(t1, plus, t2b, eqs, t3b), 1.05, 0.6), run_time=0.6)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 0.8)
        self.play(FadeOut(VGroup(t1, plus, t2b, eqs, t3b)), run_time=0.7)
        self.finish()

