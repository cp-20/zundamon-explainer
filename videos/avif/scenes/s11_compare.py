import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import DATA, fmt, mean_abs_err, pixels, rgb_decoded, size  # noqa: E402
from vlib.photoview import PhotoView, move_view  # noqa: E402
from vlib.ui import HEIC_COL  # noqa: E402
from zunda.fx import Shake, pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

KEYS = ("jpg", "webp", "heic", "avif")
FILES = {"jpg": "cat_q5.jpg", "webp": "cat_q10.webp", "heic": "cat_q25.heic", "avif": "cat_q30.avif"}
NAMES = {"jpg": "JPEG", "webp": "WebP", "heic": "HEIC", "avif": "AVIF"}
COLS = {"jpg": INK, "webp": "#aab1c0", "heic": HEIC_COL, "avif": YELLOW}
# ---- 4 枚の写真 (上の帯いっぱい) ----
PH_X, PH_Y, PH_W, PH_H = (264, 728, 1192, 1656), 200, 450, 300
EYE_WIN = (112, 72, 232, 152)                                    # 目のあたり (画素の座標。3:2)
# ---- 元とのずれの棒 (2 人の間) ----
ERR_HEAD_Y = 420
ERR_Y = {"jpg": 510, "webp": 600, "heic": 690, "avif": 780}
ERR_LX, ERR_X, ERR_MAX, ERR_H = 540, 620, 700, 56
# ---- 保存にかかる時間の棒 ----
ROW_Y = {"jpg": 300, "webp": 425, "heic": 550, "avif": 675}
LAB_X, BAR_X, BAR_MAX, BAR_H = 560, 640, 800, 64
# ---- ブラウザの窓 (HEIC 編の S01 の窓と同じ大きさ・色。上の帯がタブ) ----
PC_C, PC_W, PC_H = (960, 380), 568, 400
TAB_H = 52
BROWSERS = (("Chrome", 2020), ("Firefox", 2021), ("Safari", 2022))     # 対応した年 (S01 と同じ)
YR_X, YR_NAME_Y, YR_Y = (660, 960, 1260), 684, 748


def ms(v):
    v *= 1000
    return f"{v:.2f}" if v < 1 else f"{v:.0f}"


class Race(Animation):
    """保存にかかった時間：棒が同じ速さで伸び、それぞれの時間で止まる (HEIC 編の S10 と同じ)"""

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


def browser_window():
    """モニターと、上の帯のタブ。戻り値は (全体, 中身の中心 px)"""
    mon = RoundedRectangle(corner_radius=u(16), width=u(PC_W), height=u(PC_H), stroke_color="#596075",
                           stroke_width=6, fill_color="#1c1f27", fill_opacity=1).move_to(px(*PC_C))
    neck = Rectangle(width=u(40), height=u(26), stroke_width=0, fill_color="#596075", fill_opacity=1)
    neck.move_to(px(PC_C[0], PC_C[1] + PC_H / 2 + 13))
    base = RoundedRectangle(corner_radius=u(6), width=u(200), height=u(12), stroke_width=0, fill_color="#596075",
                            fill_opacity=1).move_to(px(PC_C[0], PC_C[1] + PC_H / 2 + 30))
    top = PC_C[1] - PC_H / 2
    band = Rectangle(width=u(PC_W - 22), height=u(TAB_H), stroke_width=0, fill_color="#2a2f3a", fill_opacity=1)
    band.move_to(px(PC_C[0], top + 10 + TAB_H / 2))
    tab = RoundedRectangle(corner_radius=u(10), width=u(220), height=u(TAB_H - 10), stroke_width=0,
                           fill_color="#1c1f27", fill_opacity=1)
    tab.move_to(px(PC_C[0] - PC_W / 2 + 22 + 110, top + 10 + TAB_H / 2 + 5))
    tname = jp("cat.avif", 28, INK).move_to(tab)
    content_c = (PC_C[0], (top + 10 + TAB_H + PC_C[1] + PC_H / 2) / 2)
    return VGroup(mon, neck, base, band, tab, tname), content_c


class S11(PScene):
    def construct(self):
        # ---- 台詞の数字 ----
        n = {k: size(FILES[k]) for k in KEYS}
        assert tuple(n[k] for k in KEYS) == (3797, 3898, 3791, 3750)
        assert all(abs(v - 4000) < 300 for v in n.values())                       # 4 キロバイトくらい
        err = {k: mean_abs_err(FILES[k]) for k in KEYS}
        errs = {k: f"{err[k]:.1f}" for k in KEYS}
        assert tuple(errs[k] for k in KEYS) == ("11.0", "5.6", "4.9", "4.9")       # HEIC と AVIF はほぼ同じ
        et = json.loads((DATA / "encode_time.json").read_text())
        tm = {"jpg": et["jpeg"]["median_s"], "webp": et["webp"]["median_s"], "heic": et["heic"]["median_s"],
              "avif": et["avif"]["median_s"]}
        ratio = tm["avif"] / tm["jpg"]
        assert ratio >= 100 and f"{ratio:.0f}" == "159"                           # JPEG の 100 倍以上
        assert tm["heic"] == max(tm.values())                                     # 棒の長さの基準は HEIC
        photos = {k: pixels(FILES[k]) for k in KEYS}
        assert all(p.shape[:2] == (300, 451) for p in photos.values())

        # ================= 4 枚の写真 =================
        views = {}
        for i, k in enumerate(KEYS):
            v = PhotoView(photos[k], (PH_X[i], PH_Y), PH_W, PH_H, win=(0, 0, 450, 300))
            v.check_ignore = True
            v.set_opacity(0)
            v.refresh()
            views[k] = v
            self.add(v)
        labs = {}
        for i, k in enumerate(KEYS):
            t = jp(f"{NAMES[k]}  {fmt(n[k])} バイト", 30, COLS[k])
            bg = RoundedRectangle(corner_radius=u(10), width=t.width + u(24), height=t.height + u(18), stroke_width=0,
                                  fill_color=BG, fill_opacity=0.85)
            bg.move_to(px(PH_X[i] - PH_W / 2 + 10, PH_Y - PH_H / 2 + 10), aligned_edge=UL)
            t.move_to(bg)
            labs[k] = VGroup(bg, t)
        self.at("s11_01", -0.1)
        self.play(*[views[k].animate.set_opacity(1) for k in KEYS],
                  LaggedStart(*[FadeIn(labs[k], shift=UP * u(8)) for k in KEYS], lag_ratio=0.2), run_time=1.0)

        # 4 枚とも同じ窓・同じ倍率で目へ
        self.at("tiny", 0.1)
        self.play(*[move_view(views[k], EYE_WIN, ((PH_X[i], PH_Y), PH_W, PH_H)) for i, k in enumerate(KEYS)],
                  Animation(VGroup(*labs.values())), run_time=2.4)

        # ================= 元とのずれ (棒の長さで比べる) =================
        head = jp("元とのずれ", 34, DIM).move_to(px(960, ERR_HEAD_Y))
        elab = {k: jp(NAMES[k], 40, COLS[k]).move_to(px(ERR_LX, ERR_Y[k])) for k in KEYS}
        ebar, enum = {}, {}
        for k in KEYS:
            w = ERR_MAX * err[k] / err["jpg"]
            ebar[k] = Rectangle(width=u(w), height=u(ERR_H), stroke_width=0, fill_color=CORAL,
                                fill_opacity=1).move_to(px(ERR_X, ERR_Y[k]), aligned_edge=LEFT)
            enum[k] = jp(errs[k], 40, INK).move_to(px(ERR_X + w + 20, ERR_Y[k]), aligned_edge=LEFT)
        for j, (ks, cue) in enumerate(((("jpg",), "jb"), (("webp",), "wb"), (("heic", "avif"), "tie"))):
            self.at(cue, -0.1)
            extra = [FadeIn(head)] if j == 0 else []
            self.play(*[FadeIn(elab[k], shift=RIGHT * u(8)) for k in ks], *[GrowFromEdge(ebar[k], LEFT) for k in ks],
                      *extra, run_time=0.6)
            self.play(*[FadeIn(enum[k], shift=LEFT * u(6)) for k in ks],
                      *[pop(views[k], 1.04, 0.6) for k in ks], run_time=0.6)

        # HEIC と AVIF の棒の右端は同じ所
        self.at("same", -0.1)
        xe = ERR_X + ERR_MAX * err["avif"] / err["jpg"]
        tie = DashedLine(px(xe, ERR_Y["heic"] - 44), px(xe, ERR_Y["avif"] + 44), stroke_color=YELLOW, stroke_width=4,
                         dash_length=u(12))
        self.play(Create(tie), run_time=0.6)
        self.play(pop(VGroup(elab["heic"], ebar["heic"], enum["heic"], elab["avif"], ebar["avif"], enum["avif"]),
                      1.06, 0.7), run_time=0.7)

        # ================= 弱点 1：保存にかかる時間 =================
        weak = jp("弱点", 52, CORAL).move_to(px(960, 110))
        self.at("s11_04", -0.1)
        self.play(*[views[k].animate.set_opacity(0) for k in KEYS],
                  FadeOut(VGroup(*labs.values(), head, *elab.values(), *ebar.values(), *enum.values(), tie)),
                  FadeIn(weak, scale=0.8), run_time=0.8)
        self.remove(*views.values())

        rlabs = {k: jp(NAMES[k], 40, COLS[k]).move_to(px(LAB_X, ROW_Y[k])) for k in KEYS}
        axis = Line(px(BAR_X, ROW_Y["jpg"] - 60), px(BAR_X, ROW_Y["avif"] + 60), stroke_color=DIM, stroke_width=3)
        thead = jp("保存にかかる時間", 34, DIM).move_to(px(BAR_X + BAR_MAX / 2, ROW_Y["jpg"] - 90))
        self.at("slow", -0.1)
        self.play(LaggedStart(*[FadeIn(rlabs[k], shift=RIGHT * u(10)) for k in KEYS], lag_ratio=0.15), Create(axis),
                  FadeIn(thead, shift=DOWN * u(6)), run_time=0.9)
        self.at("time", -0.1)
        bars = {k: Rectangle(width=u(1), height=u(BAR_H), stroke_width=0, fill_color=COLS[k], fill_opacity=0)
                .move_to(px(BAR_X, ROW_Y[k]), aligned_edge=LEFT) for k in KEYS}
        self.add(*bars.values())
        vals = {k: jp(f"{ms(tm[k])} ミリ秒", 40, COLS[k]) for k in KEYS}
        for k in KEYS:
            if k == "heic":     # いちばん長い棒：端の内側
                vals[k].set_color(BG).move_to(px(BAR_X + BAR_MAX - 20, ROW_Y[k]), aligned_edge=RIGHT)
            else:               # JPEG の棒は 3px ほどなので、軸のすぐ右
                vals[k].move_to(px(BAR_X + BAR_MAX * tm[k] / tm["heic"] + 20, ROW_Y[k]), aligned_edge=LEFT)
        T = 1.8
        t_of = {k: T * tm[k] / tm["heic"] for k in KEYS}
        self.play(Race(bars, tm, tm["heic"], run_time=T),
                  *[Succession(Wait(max(t_of[k], 0.05)), FadeIn(vals[k], shift=LEFT * u(8), run_time=0.4))
                    for k in ("jpg", "webp", "avif")], run_time=T + 0.1)
        self.play(FadeIn(vals["heic"], shift=LEFT * u(8)), run_time=0.3)

        # AVIF は JPEG の 159 倍
        self.at("jpg", -0.1)
        rt = jp(f"AVIF は JPEGの {ratio:.0f}倍", 48, CORAL).move_to(px(960, 810))
        self.play(FadeIn(rt, shift=UP * u(10)), run_time=0.6)
        self.play(pop(VGroup(rlabs["avif"], bars["avif"], vals["avif"]), 1.06, 0.7), run_time=0.7)

        # ================= 弱点 2：古いブラウザでは開けない =================
        win, content_c = browser_window()
        card = RoundedRectangle(corner_radius=u(14), width=u(300), height=u(200), stroke_width=0,
                                fill_color="#3a3f4c", fill_opacity=1).move_to(px(*content_c))
        qm = jp("？", 110, DIM).move_to(card)
        chart = VGroup(*rlabs.values(), *bars.values(), *vals.values(), axis, thead, rt)
        self.at("old", -0.1)
        self.play(FadeOut(chart), FadeIn(VGroup(win, card, qm), scale=0.94), run_time=0.9)
        self.at("old", 2.2)
        self.play(Shake(VGroup(win, card, qm), amp=12, run_time=0.6))
        self.play(pop(qm, 1.25, 0.7), run_time=0.7)

        # 比較的新しい：対応した年
        yrs = VGroup()
        for (name, yr), x in zip(BROWSERS, YR_X):
            yrs.add(VGroup(jp(name, 40, INK).move_to(px(x, YR_NAME_Y)), mix(f"{yr}年", 48, YELLOW).move_to(px(x, YR_Y))))
        self.at("new", -0.1)
        self.play(LaggedStart(*[FadeIn(g, shift=UP * u(10)) for g in yrs], lag_ratio=0.2), run_time=1.1)

        # 特許料がかからない：いまのブラウザなら開ける (S01 の窓)
        ph = ImageMobject(rgb_decoded())
        ph.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        ph.width = u(450)
        ph.move_to(px(*content_c))
        ph.check_ignore = True
        ph.set_opacity(0)
        self.add(ph)
        self.at("free", -0.1)
        self.play(FadeOut(weak), FadeOut(VGroup(card, qm), scale=0.9), ph.animate.set_opacity(1), run_time=0.9)
        self.at("spread", -0.1)
        self.play(LaggedStart(*[Indicate(g[1], color=YELLOW, scale_factor=1.2) for g in yrs], lag_ratio=0.3),
                  run_time=1.4)
        self.remove(*[g[1] for g in yrs])         # Indicate が場面に入れた文字を外して、まとまりに戻す
        self.add(yrs)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 0.9)
        self.play(FadeOut(VGroup(win, yrs)), ph.animate.set_opacity(0), run_time=0.7)
        self.remove(ph)
        self.finish()
