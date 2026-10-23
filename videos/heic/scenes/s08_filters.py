import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import DATA, MAIN, dec, fmt, picture_size, rgb_decoded, size  # noqa: E402
from vlib.photoview import LW, Grow, PhotoView, PLine, PRect, ViewAnim, grid64_lines, move_view  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

LOW = "cat_q15"
EYE_WIN = (104, 56, 232, 184)                 # 品質 15 の左目 (画素の座標。8 の倍数)
BIG = ((960, 440), 760, 760)                  # 目に寄ったとき
SIDE = {"a": ((700, 470), 510, 510), "b": ((1225, 470), 510, 510)}
STEP_MIN = 6                                  # 「段」として光らせる境目の差 (明るさ、4 点の平均)

# SAO の例：右目のふちを斜め (左上→右下) にまたぐ 10 点。64×64 の (4, 2) は「斜め」で比べる
ROW_X0, ROW_Y0, ROW_N = 296, 128, 10
SAO_CTB = (4, 2)
EYE2_WIN = (301 - 24 * 480 / 420, 109, 301 + 24 * 480 / 420, 157)
EYE2_BOX = ((272, 244), 480, 420)
PHOTO2 = ((960, 470), 840, 559)
BAR_X0, BAR_STEP, BAR_W, BASE_Y, HMAX = 660, 86, 58, 600, 360
SC0, SC1 = (0, 360 / 160), (54, 17.0)            # 棒の目盛り (下端の値, 1 あたりの px)。寄ると細かい波打ちが見える
SC = list(SC0)
GLYPH_X = (590, 830, 1070, 1310)
CAT_COL = {1: CYAN, 2: CYAN, 3: CORAL, 4: CORAL}
CAT_NAME = {1: "谷", 2: "谷の肩", 3: "山の肩", 4: "山"}


class LineOp(Animation):
    """PLine の不透明度を変える (s03 と同じ)"""

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


def lum(v):
    g = float(np.clip(v, 0, 255)) / 255
    return rgb_to_color([g, g, g])


def bar_x(i):
    return BAR_X0 + i * BAR_STEP


def val_h(v):
    return (v - SC[0]) * SC[1]


def bar_rect(v, i):
    """棒 (目盛りの上にはみ出す所は切って、薄くする)"""
    h = val_h(v)
    cut = h > HMAX
    h = min(h, HMAX)
    r = Rectangle(width=u(BAR_W), height=u(h), stroke_width=2, stroke_color="#9aa0ae", fill_color=lum(v),
                  fill_opacity=0.35 if cut else 1).move_to(px(bar_x(i), BASE_Y - h / 2))
    if cut:
        r.set_stroke(opacity=0.35)
    return r


def tick_line(v, i):
    h = val_h(v)
    ln = Line(px(bar_x(i) - 38, BASE_Y - min(h, HMAX)), px(bar_x(i) + 38, BASE_Y - min(h, HMAX)),
              stroke_color=INK, stroke_width=5)
    if h > HMAX:
        ln.set_stroke(opacity=0)
    return ln


class Rescale(Animation):
    """棒の目盛りを変える (縦に寄る)"""

    def __init__(self, bars, vals, ticks, ovals, sc, extra=None, **kw):
        self.bars, self.vals, self.ticks, self.ovals, self.sc, self.extra = bars, vals, ticks, ovals, sc, extra
        self.sc0 = tuple(SC)
        super().__init__(VGroup(bars, ticks), **kw)

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        SC[0] = self.sc0[0] + (self.sc[0] - self.sc0[0]) * a
        SC[1] = self.sc0[1] * (self.sc[1] / self.sc0[1]) ** a
        for i, (b, v) in enumerate(zip(self.bars, self.vals)):
            b.become(bar_rect(v, i))
        for i, (t, v) in enumerate(zip(self.ticks, self.ovals)):
            t.become(tick_line(v, i))
        if self.extra:
            self.extra(a)


def bar_num(v, i):
    return mono(str(int(v)), 30, INK).move_to(px(bar_x(i), BASE_Y + 28))


def glyph(kind, cx, cy=748):
    """4 つの形の見本 (点と両どなりの 3 本)"""
    hs = {1: (54, 22, 54), 2: (54, 22, 22), 3: (22, 54, 54), 4: (22, 54, 22)}[kind]
    g = VGroup()
    for j, h in enumerate(hs):
        col = CAT_COL[kind] if j == 1 else "#5b6170"
        g.add(Rectangle(width=u(30), height=u(h), stroke_width=0, fill_color=col, fill_opacity=1)
              .move_to(px(cx + (j - 1) * 38, cy + 27 - h / 2)))
    return g


class S08(PScene):
    def construct(self):
        W, H = picture_size()
        # ---- 実データ ----
        assert size(LOW) == 2077
        dl = dec(LOW)
        Yr = dl.recon[0].astype(int)
        d = dec(MAIN)
        a = np.asarray(Image.open(DATA / "cat.png").convert("RGB")).astype(float)[:H, :W]
        Yo = np.round(0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(int)
        Yd = d.cropped(d.deblocked)[0].astype(int)[:H, :W]
        Yf = d.cropped(d.final)[0].astype(int)[:H, :W]
        e_db, e_fin = np.abs(Yo - Yd).mean(), np.abs(Yo - Yf).mean()
        assert (f"{e_db:.3f}", f"{e_fin:.3f}") == ("1.958", "1.934")
        prm = d.sao[SAO_CTB][0]
        assert prm["type"] == 2 and prm["eo_class"] == 2          # 端の SAO、斜め (左上と右下) と比べる
        offs = prm["offsets"]
        assert offs == [1, 1, -1, -1]                              # 谷 +1・谷の肩 +1・山の肩 −1・山 −1
        allv = [abs(v) for p in d.sao.values() for c in (0, 1, 2) if p[c]["type"] for v in p[c]["offsets"]]
        assert max(allv) == 2                                      # 「1 や 2」
        xs = ROW_X0 + np.arange(ROW_N)
        ys = ROW_Y0 + np.arange(ROW_N)
        assert all(x // 64 == SAO_CTB[0] and y // 64 == SAO_CTB[1] for x, y in zip(xs, ys))
        r_o, r_d, r_f = Yo[ys, xs], Yd[ys, xs], Yf[ys, xs]
        cls = [int(c) for c in d.sao_class[0][ys, xs]]
        assert (d.recon[0][ys, xs] == d.deblocked[0][ys, xs]).all()      # この 10 点はデブロッキングでは変わらない
        changed = [i for i in range(ROW_N) if r_d[i] != r_f[i]]
        assert changed == [0, 4, 5, 7, 9]
        assert all(abs(r_f[i] - r_o[i]) < abs(r_d[i] - r_o[i]) for i in changed)   # どれも元に近づく
        assert all(r_f[i] - r_d[i] == offs[cls[i] - 1] for i in changed)
        assert min(r_d[3:]) > SC1[0] and max(max(r_d[3:]), max(r_o[3:]), max(r_f[3:])) < SC1[0] + HMAX / SC1[1]
        assert max(r_d) * SC0[1] <= HMAX
        mid = 4                                                    # 「両どなりと比べる」の例 (谷)
        assert cls[mid] == 1 and r_d[mid] < r_d[mid - 1] and r_d[mid] < r_d[mid + 1]

        # ================= デブロッキング (品質 15) =================
        va = PhotoView(rgb_decoded(LOW, "recon"), (960, 420), 1000, 665)
        va.check_ignore = True
        va.set_opacity(0)
        self.add(va)
        lab_q = jp("品質15", 40, INK).move_to(px(235, 120))
        lab_n = jp(f"{fmt(size(LOW))} バイト", 36, DIM).move_to(px(235, 180))
        self.at("s08_01", -0.1)
        self.play(va.animate.set_opacity(1), FadeIn(lab_q, shift=DOWN * u(8)), FadeIn(lab_n, shift=DOWN * u(8)),
                  run_time=0.8)
        self.at("low", -0.1)
        self.play(move_view(va, EYE_WIN, BIG), run_time=2.0)

        # 段の線：デブロッキングで実際にならされた境目のうち、段が大きい所
        L, T, R, B = EYE_WIN
        segs = []
        for r in dl.deblock_log:
            e, s, v = r["e"], r["s"], r["vertical"]
            if r["mode"] == 0:
                continue
            if v and L < e < R and T <= s < B:
                st = np.mean([abs(Yr[s + i, e] - Yr[s + i, e - 1]) for i in range(4)])
                ab = ((e, s), (e, s + 4))
            elif not v and T < e < B and L <= s < R:
                st = np.mean([abs(Yr[e, s + i] - Yr[e - 1, s + i]) for i in range(4)])
                ab = ((s, e), (s + 4, e))
            else:
                continue
            if st >= STEP_MIN:
                segs.append(PLine(va, *ab, frac=0, stroke_color=YELLOW, stroke_width=5))
        assert len(segs) > 40
        self.add(*segs)
        self.at("edge", -0.1)
        order = sorted(range(len(segs)), key=lambda i: segs[i].a[0] + segs[i].a[1])
        self.play(LaggedStart(*[Grow(segs[i], run_time=0.5) for i in order], lag_ratio=0.01), run_time=1.0)

        # 同じ窓・同じ倍率で、ならしたあとを右に
        vb = PhotoView(rgb_decoded(LOW, "deblocked"), *SIDE["b"], win=EYE_WIN)
        vb.check_ignore = True
        vb.set_opacity(0)
        vb.refresh()
        self.add(vb)
        t_a = jp("ならす前", 36, INK).move_to(px(SIDE["a"][0][0], 178))
        t_b = jp("ならした後", 36, CYAN).move_to(px(SIDE["b"][0][0], 178))
        self.at("db", -0.1)
        self.play(move_view(va, EYE_WIN, SIDE["a"]), LineOp(segs, 0.45), FadeIn(t_a, shift=DOWN * u(8)),
                  run_time=1.0)
        self.play(vb.animate.set_opacity(1), FadeIn(t_b, shift=DOWN * u(8)), run_time=0.8)
        self.wait(0.6)
        self.play(pop(vb, 1.04, 0.7), run_time=0.7)

        # ================= SAO (本編の品質 45) =================
        self.at("s08_03", -0.1)
        self.play(va.animate.set_opacity(0), vb.animate.set_opacity(0), LineOp(segs, 0),
                  FadeOut(VGroup(t_a, t_b, lab_q, lab_n)), run_time=0.7)
        self.remove(va, vb, *segs)

        vm = PhotoView(rgb_decoded(MAIN, "deblocked"), *PHOTO2)
        vm.check_ignore = True
        vm.set_opacity(0)
        self.add(vm)
        self.at("sao", -0.1)
        self.play(vm.animate.set_opacity(1), run_time=0.6)

        # 右目のふちへ寄って、斜めの 10 点
        self.play(move_view(vm, EYE2_WIN, EYE2_BOX), run_time=1.0)
        self.at("ring", -0.1)
        pp = vm.px_per_pixel()
        cells = VGroup(*[Square(u(pp), stroke_color=YELLOW, stroke_width=3).move_to(vm.to_point(x + 0.5, y + 0.5))
                         for x, y in zip(xs, ys)])
        bars = VGroup(*[bar_rect(v, i) for i, v in enumerate(r_d)])
        nums = VGroup(*[bar_num(v, i) for i, v in enumerate(r_d)])
        ticks = VGroup(*[tick_line(v, i) for i, v in enumerate(r_o)])
        base = Line(px(BAR_X0 - 50, BASE_Y), px(bar_x(ROW_N - 1) + 50, BASE_Y), stroke_color=DIM, stroke_width=2)
        leg_t = Line(px(1180, 120), px(1240, 120), stroke_color=INK, stroke_width=5)
        leg = VGroup(leg_t, jp("元の写真", 32, INK).next_to(leg_t, RIGHT, buff=u(16)))
        srcs = []
        for x, y, v in zip(xs, ys, r_d):
            s = Square(u(pp), stroke_width=0, fill_color=lum(v), fill_opacity=1).move_to(vm.to_point(x + 0.5, y + 0.5))
            s.check_ignore = True
            srcs.append(s)
        self.play(Create(cells), run_time=0.4)
        self.play(LaggedStart(*[ReplacementTransform(s, b) for s, b in zip(srcs, bars)], lag_ratio=0.06),
                  FadeIn(nums), Create(base), run_time=1.1)
        self.play(LaggedStart(*[Create(t) for t in ticks], lag_ratio=0.06), FadeIn(leg), run_time=0.7)
        # 縦に寄ると、元にない小さな山と谷 (暗い側の波打ち) が見える
        grid = VGroup()
        for gv in (60, 70):
            y = BASE_Y - (gv - SC1[0]) * SC1[1]
            grid.add(VGroup(DashedLine(px(BAR_X0 - 40, y), px(bar_x(ROW_N - 1) + 40, y), dash_length=u(8),
                                       stroke_color=DIM, stroke_width=2, stroke_opacity=0.7),
                            mono(str(gv), 28, DIM).move_to(px(BAR_X0 - 70, y))))
        vals_now = list(r_d)
        self.play(Rescale(bars, vals_now, ticks, list(r_o), SC1), FadeIn(grid), run_time=1.0)

        # ---- 点を両どなりと比べる ----
        self.at("class", -0.1)
        sel = VGroup(*[SurroundingRectangle(bars[i], buff=u(6), stroke_color=YELLOW if i == mid else DIM,
                                            stroke_width=4) for i in (mid - 1, mid, mid + 1)])
        self.play(Create(sel), cells[mid].animate.set_stroke(width=7),
                  cells[mid - 1].animate.set_stroke(DIM), cells[mid + 1].animate.set_stroke(DIM), run_time=0.8)

        # 4 つの形の見本
        glyphs = VGroup(*[glyph(k, x) for k, x in zip((1, 2, 3, 4), GLYPH_X)])
        names = VGroup(*[jp(CAT_NAME[k], 32, CAT_COL[k]).move_to(px(x, 812)) for k, x in zip((1, 2, 3, 4), GLYPH_X)])
        self.at("v", -0.1)
        self.play(LaggedStart(*[FadeIn(VGroup(g, n), shift=UP * u(10)) for g, n in zip(glyphs, names)],
                              lag_ratio=0.3), run_time=1.6)
        # 10 点それぞれの種類
        assert all(c in (0, 1, 4) for c in cls)
        tags = VGroup(*[jp(CAT_NAME[c], 28, CAT_COL[c]).move_to(px(bar_x(i), 672)) for i, c in enumerate(cls) if c])
        self.play(FadeOut(sel), cells[mid - 1].animate.set_stroke(YELLOW), cells[mid + 1].animate.set_stroke(YELLOW),
                  cells[mid].animate.set_stroke(width=3),
                  LaggedStart(*[FadeIn(t, shift=UP * u(6)) for t in tags], lag_ratio=0.12), run_time=1.2)

        # ---- 種類ごとに決まった数を足す ----
        offt = VGroup(*[mono(f"{v:+d}".replace("-", "−"), 40, CAT_COL[k]).move_to(px(x, 860))
                        for k, x, v in zip((1, 2, 3, 4), GLYPH_X, offs)])
        self.at("off", -0.1)
        self.play(LaggedStart(*[FadeIn(t, scale=0.6) for t in offt], lag_ratio=0.15), run_time=0.8)
        chips = []
        for i in changed:
            ch = offt[cls[i] - 1].copy()
            ch.check_ignore = True
            chips.append(ch)
        self.add(*chips)
        self.play(*[c.animate(path_arc=-0.5).scale(0.8).move_to(bars[i].get_top() + UP * u(30))
                    for c, i in zip(chips, changed)], run_time=0.9)
        self.play(*[Transform(bars[i], bar_rect(r_f[i], i)) for i in changed],
                  *[c.animate.move_to(bars[i].get_top()).set_opacity(0) for c, i in zip(chips, changed)],
                  *[nums[i].animate.set_color(YELLOW) for i in changed], run_time=0.9)
        for i in changed:
            nums[i].become(bar_num(r_f[i], i).set_color(YELLOW))
            nums[i].text = str(int(r_f[i]))
        self.remove(*chips)
        self.play(*[Indicate(nums[i], color=YELLOW, scale_factor=1.25) for i in changed], run_time=0.8)

        # ---- SAO という名前 ----
        sao_t = mono("SAO", 56, YELLOW).move_to(px(bar_x(4.5), 92))
        sao_s = jp("Sample Adaptive Offset", 30, DIM).move_to(px(bar_x(4.5), 150))
        self.at("sao2", -0.1)
        self.play(FadeOut(leg), FadeIn(sao_t, shift=DOWN * u(8)), FadeIn(sao_s, shift=DOWN * u(8)), run_time=0.7)

        # ---- 足す数は 64×64 ごと ----
        self.at("per", -0.1)
        chart = VGroup(bars, nums, ticks, base, tags, glyphs, names, offt, grid)
        self.play(FadeOut(chart), FadeOut(cells), run_time=0.45)
        self.play(move_view(vm, (0, 0, W, H), PHOTO2), run_time=1.1)
        g64 = grid64_lines(vm, W, H, frac=0)
        self.add(*g64)
        self.play(LaggedStart(*[Grow(ln) for ln in g64], lag_ratio=0.08), run_time=1.0)
        picks = [SAO_CTB, (3, 0), (2, 4)]
        cards = VGroup()
        boxes = []
        for (rx, ry) in picks:
            q = d.sao[(rx, ry)][0]
            assert q["type"] == 2
            boxes.append(PRect(vm, rx * 64, ry * 64, min(64, W - rx * 64), min(64, H - ry * 64),
                               stroke_color=YELLOW, stroke_width=5))
            t = mono("  ".join(f"{v:+d}".replace("-", "−") for v in q["offsets"]), 30, INK)
            bg = RoundedRectangle(corner_radius=u(10), width=t.width + u(28), height=t.height + u(22), stroke_width=0,
                                  fill_color=BG, fill_opacity=0.88)
            c = vm.to_point(rx * 64 + 32, ry * 64 + 32)
            VGroup(bg, t).move_to(c)
            cards.add(VGroup(bg, t))
        assert d.sao[(3, 0)][0]["offsets"] == [1, 1, -2, -1] and d.sao[(2, 4)][0]["offsets"] == [2, 1, -1, -1]
        for b_, c_ in zip(boxes, cards):
            self.play(Create(b_), FadeIn(c_, scale=0.8), run_time=0.6)

        self.at("fix", 0.0)
        self.play(LaggedStart(*[pop(c_, 1.12, 0.6) for c_ in cards], lag_ratio=0.2), run_time=1.0)

        # ---- 写真全体で、元とのずれが少し減る ----
        self.at("small", -0.1)
        self.play(LaggedStart(*[Indicate(c_[1], color=YELLOW, scale_factor=1.15) for c_ in cards], lag_ratio=0.2),
                  run_time=1.0)
        tot = jp(f"元とのずれ  {e_db:.3f} → {e_fin:.3f}", 44, INK, t2c={f"{e_fin:.3f}": YELLOW}).move_to(px(960, 800))
        cap = jp("(明るさの平均)", 30, DIM).move_to(px(960, 856))
        self.at("total", -0.1)
        self.play(FadeIn(tot, shift=UP * u(10)), FadeIn(cap, shift=UP * u(10)), run_time=0.8)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 0.8)
        for b_ in boxes:
            b_.clear_updaters()
        self.play(vm.animate.set_opacity(0), LineOp(g64, 0), FadeOut(VGroup(*boxes, cards, tot, cap, sao_t, sao_s)),
                  run_time=0.7)
        self.remove(vm, *g64)
        self.finish()
