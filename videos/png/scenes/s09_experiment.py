import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import filtered, fmt, info, pixels, path  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

BAR_X0, BAR_W = 740, 690  # 棒の左端と、いちばん長い棒の長さ（px）
BAR_H = 56
BAR_COL = "#c9d1e0"
HIST_W, HIST_H = 320, 80
ROW_Y = {"gradient": 160, "photoish": 455, "noise": 750}
THUMB = 250
TRACK = "#262b36"
SEG_COL = [BLUE, PURPLE, "#8a919e"]


def pct_str(p):
    """割合（0〜1）を文字に。0・小さい値・ほぼ100% を見やすく"""
    p *= 100
    if p == 0:
        return "0%"
    if p >= 99.5:
        return "100%"
    return f"{p:.1f}%" if p < 10 else f"{p:.0f}%"


def stats_of(name):
    inf = info(name)
    f = filtered(name)[:, 1:]
    cnt = np.bincount(f.ravel(), minlength=256)
    zero = cnt[0] / cnt.sum()
    out = sum(b["out_bytes"] for b in inf["blocks"])
    copied = sum(b["match_bytes"] for b in inf["blocks"])
    return dict(cnt=cnt, zero=zero, copy=copied / out, size=inf["file_size"], raw=inf["pixel_bytes"],
                stored=sum(1 for b in inf["blocks"] if b["btype"] == 0))


def bar_mob(size, y, color=BAR_COL, scale=None):
    w = BAR_W * size / scale
    r = Rectangle(width=u(w), height=u(BAR_H), stroke_width=0, fill_color=color, fill_opacity=1)
    return r.move_to(px(BAR_X0 + w / 2, y))


class Stats:
    """1 行ぶんの小さな図：フィルタ後の値の分布 と コピーで書いた割合"""

    def __init__(self, name, yc):
        st = stats_of(name)
        self.st = st
        base = yc + 112
        cnt = st["cnt"]
        fr = cnt[(np.arange(256) - 128) % 256] / cnt.sum()  # 真ん中が 0 の符号つき並び
        hs = HIST_H * fr / fr.max()
        bw = HIST_W / 256
        self.bars = VGroup(*[Rectangle(width=u(bw), height=u(max(h, 0.6)), stroke_width=0,
                                       fill_color=YELLOW if j == 128 else INK, fill_opacity=1 if j == 128 else 0.85)
                             .move_to(px(BAR_X0 + bw * (j + 0.5), base), aligned_edge=DOWN)
                             for j, h in enumerate(hs)])
        self.bars.check_group = True
        self.axis = Line(px(BAR_X0 - 4, base + 1), px(BAR_X0 + HIST_W + 4, base + 1), stroke_width=2, color=DIM)
        self.cap = mix("フィルタ後の値（真ん中が0）", 24, DIM).move_to(px(BAR_X0, yc + 136), aligned_edge=LEFT)
        zl = mix(f"0が {pct_str(st['zero'])}", 32, YELLOW)
        self.zero_lbl = zl.move_to(px(BAR_X0 + HIST_W / 2, yc + 4))
        self.copy_cap = jp("コピーで書いた", 28, DIM).move_to(px(1070, yc + 34), aligned_edge=LEFT)
        self.track = Rectangle(width=u(300), height=u(28), stroke_width=0, fill_color=TRACK, fill_opacity=1)
        self.track.move_to(px(1220, yc + 90))
        fw = 300 * st["copy"]
        self.fill = None
        if fw > 0:
            self.fill = Rectangle(width=u(fw), height=u(28), stroke_width=0, fill_color=CYAN, fill_opacity=1)
            self.fill.move_to(px(1070 + fw / 2, yc + 90))
        self.copy_pct = jp(pct_str(st["copy"]), 34, CYAN if st["copy"] > 0 else CORAL)
        self.copy_pct.move_to(px(1370, yc + 34), aligned_edge=RIGHT)

    def static(self):
        return VGroup(self.axis, self.cap, self.copy_cap, self.track)

    def everything(self):
        g = VGroup(self.static(), self.bars, self.zero_lbl, self.copy_pct)
        if self.fill is not None:
            g.add(self.fill)
        return g

    def grow_hist(self, run_time=1.4):
        order = sorted(range(256), key=lambda j: abs(j - 127.5))
        return LaggedStart(*[GrowFromEdge(self.bars[j], DOWN) for j in order], lag_ratio=0.006, run_time=run_time)


class S09(PScene):
    def construct(self):
        # ---- 実データ ----
        names = [("gradient", "グラデーション"), ("photoish", "空"), ("noise", "砂嵐")]
        S = {n: stats_of(n) for n, _ in names}
        raw = S["gradient"]["raw"]
        assert raw == S["photoish"]["raw"] == S["noise"]["raw"] == 786432
        assert S["gradient"]["size"] == 8575 and S["photoish"]["size"] == 414139 and S["noise"]["size"] == 788086
        assert round(S["gradient"]["size"] / raw * 100) == 1
        assert 0.45 < S["photoish"]["size"] / raw < 0.55
        assert S["noise"]["size"] > raw
        assert S["noise"]["copy"] == 0 and S["gradient"]["copy"] > 0.999 and S["photoish"]["copy"] < 0.03
        assert S["gradient"]["zero"] > 0.9
        z = info("zundamon")
        zr, zs = z["pixel_bytes"], z["file_size"]
        assert (zr, zs) == (6898832, 333074) and round(zr / zs) == 21
        scale = S["noise"]["size"]  # 3 つの棒で共通の物差し（最大は砂嵐）
        x_ref = BAR_X0 + BAR_W * raw / scale
        # 砂嵐が生より増えた内訳
        d_filter = info("noise")["raw_bytes"] - raw
        d_deflate = info("noise")["idat_bytes"] - info("noise")["raw_bytes"]
        d_other = S["noise"]["size"] - info("noise")["idat_bytes"]
        excess = S["noise"]["size"] - raw
        assert d_filter + d_deflate + d_other == excess

        # ---- S09_01：3 つの画像 ----
        QX, QY, QH = (600, 960, 1320), 240, 320
        imgs = {}
        for (n, _), x in zip(names, QX):
            im = ImageMobject(str(path(n)))
            im.height = u(QH)
            imgs[n] = im.move_to(px(x, QY))
        self.at("three")
        self.play(LaggedStart(*[FadeIn(imgs[n], scale=0.92) for n, _ in names], lag_ratio=0.3), run_time=1.4)
        raw_lbl = {n: mix(f"{fmt(raw)} バイト", 34)
                   .move_to(px(x, 50)) for (n, _), x in zip(names, QX)}
        self.at("raw")
        self.play(LaggedStart(*[FadeIn(raw_lbl[n], shift=DOWN * u(8)) for n, _ in names], lag_ratio=0.2),
                  run_time=0.9)

        # ---- S09_02：名前 ----
        self.at("names")
        name_lbl = {n: jp(jn, 40).move_to(px(x, 432)) for (n, jn), x in zip(names, QX)}
        self.play(LaggedStart(*[FadeIn(name_lbl[n], shift=UP * u(8)) for n, _ in names], lag_ratio=0.5),
                  run_time=1.6)

        # ---- S09_03：どれが一番小さい？ ----
        self.at("guess", -0.4)
        q = jp("どれが一番小さくなる？", 72).move_to(px(960, 660))
        self.play(FadeIn(q, shift=UP * u(10)), run_time=0.8)

        # ---- S09_04：ずんだもんの予想 ----
        self.at("zguess")
        ul = underline(name_lbl["gradient"], YELLOW)
        self.play(name_lbl["gradient"].animate.set_color(YELLOW), Create(ul),
                  pop(imgs["gradient"], 1.12), run_time=0.7)

        # ---- S09_05：正解 ----
        self.at("right", -0.05)
        self.se("ding")
        self.play(retext(q, jp("正解！", 80, YELLOW)), pop(q, 1.25), run_time=0.7)

        # 間のあいだに、画像を行に並べ直す
        self.at("right", 1.2)
        ref = DashedLine(px(x_ref, 66), px(x_ref, 885), dash_length=u(10), stroke_width=3, color=DIM)
        ref.check_ignore = True  # 棒をまたぐ物差しの線
        ref_lbl = mix(f"生 {fmt(raw)}", 30, DIM)
        ref_lbl.move_to(px(x_ref - 130, 46))
        mid = raw_lbl["photoish"]
        anims = []
        for n, jn in names:
            yc = ROW_Y[n]
            anims.append(imgs[n].animate.scale(THUMB / QH).move_to(px(590, yc)))
            anims.append(name_lbl[n].animate.scale(32 / 40).move_to(px(BAR_X0, yc - 112), aligned_edge=LEFT).set_color(INK))
        self.play(*anims, FadeOut(q), FadeOut(ul),
                  FadeOut(raw_lbl["gradient"]), FadeOut(raw_lbl["noise"]), Transform(mid, ref_lbl),
                  Create(ref), run_time=1.2)

        # ---- S09_06：グラデーション ----
        bars, bar_lbl = {}, {}
        for n, _ in names:
            bars[n] = bar_mob(S[n]["size"], ROW_Y[n] - 50, scale=scale)
        self.at("grad")
        bar_lbl["gradient"] = mix(f"{fmt(S['gradient']['size'])} ({S['gradient']['size'] / raw * 100:.1f}%)", 40)
        bar_lbl["gradient"].next_to(bars["gradient"], RIGHT, buff=u(16))
        self.play(GrowFromEdge(bars["gradient"], LEFT), run_time=0.7)
        self.play(FadeIn(bar_lbl["gradient"], shift=RIGHT * u(8)), run_time=0.5)
        self.at("pct")
        self.play(pop(bar_lbl["gradient"], 1.2), run_time=0.6)

        self.at("S09_07")
        self.play(pop(VGroup(bars["gradient"], bar_lbl["gradient"]), 1.2), run_time=0.6)

        # ---- S09_07：空 ----
        self.at("sky", -0.1)
        bar_lbl["photoish"] = mix(f"{fmt(S['photoish']['size'])} ({S['photoish']['size'] / raw * 100:.1f}%)", 40)
        bar_lbl["photoish"].next_to(bars["photoish"], RIGHT, buff=u(16))
        self.play(GrowFromEdge(bars["photoish"], LEFT), run_time=1.3, rate_func=smooth)
        self.play(FadeIn(bar_lbl["photoish"], shift=RIGHT * u(8)), run_time=0.4)
        self.at("half")
        self.play(pop(bar_lbl["photoish"], 1.2), run_time=0.6)

        # ---- S09_08：砂嵐。生の線を越える ----
        self.at("noise", -0.2)
        nb = bars["noise"]
        self.play(GrowFromEdge(nb, LEFT), run_time=1.6, rate_func=rate_functions.ease_in_out_cubic)
        n_num = jp(fmt(S["noise"]["size"]), 40, BG).move_to(px(BAR_X0 + 20, ROW_Y["noise"] - 50), aligned_edge=LEFT)
        n_pct = jp(f"({S['noise']['size'] / raw * 100:.1f}%)", 32, BG).move_to(
            px(BAR_X0 + BAR_W - 16, ROW_Y["noise"] - 50), aligned_edge=RIGHT)
        self.play(FadeIn(n_num), FadeIn(n_pct), run_time=0.4)

        # ---- S09_09：生より大きい ----
        self.at("bigger", -0.1)
        self.se("surprise")
        self.play(nb.animate.set_color(CORAL), ref.animate.set_color(CORAL), Shake(VGroup(nb, n_num, n_pct), 12),
                  run_time=0.8)
        ex_lbl = mix(f"生より +{fmt(excess)}", 36, CORAL)
        ex_lbl.move_to(px(1300, ROW_Y["noise"] - 122))
        ex_arrow = Arrow(px(1400, ROW_Y["noise"] - 98), px(x_ref + 2, ROW_Y["noise"] - 80), buff=0, stroke_width=4,
                         color=CORAL, tip_length=u(14), max_tip_length_to_length_ratio=0.5)
        self.play(FadeIn(ex_lbl, shift=DOWN * u(8)), Create(ex_arrow), run_time=0.6)
        self.play(ref.animate.set_color(DIM), run_time=0.5)

        # ---- S09_11：砂嵐は関係がない ----
        st = {n: Stats(n, ROW_Y[n]) for n, _ in names}
        self.at("s09_11", 0.1)
        self.play(FadeIn(st["noise"].static()), FadeIn(st["noise"].zero_lbl), run_time=0.6)
        self.at("random")
        self.play(st["noise"].grow_hist(1.5), run_time=1.5)
        self.at("nocopy")
        self.play(FadeIn(st["noise"].copy_pct, scale=1.4), Shake(st["noise"].copy_pct, 8), run_time=0.7)

        self.at("S09_14")
        self.play(Shake(st["noise"].copy_pct, 8), pop(st["noise"].zero_lbl, 1.25), run_time=0.7)

        # ---- S09_12：ほんの少し大きくなる内訳 ----
        self.at("extra", -0.2)
        yc = ROW_Y["noise"]
        parts = [(d_filter, "フィルタの番号"), (d_deflate, "箱の印など"), (d_other, "ヘッダなど")]
        sy = yc + 62
        x = BAR_X0
        segs, nums_, caps = VGroup(), VGroup(), VGroup()
        for (v, cap_), col in zip(parts, SEG_COL):
            w = 640 * v / excess
            seg = Rectangle(width=u(w), height=u(44), stroke_width=0, fill_color=col, fill_opacity=1)
            seg.move_to(px(x + w / 2, sy))
            nums_.add(jp(f"+{v}", 30 if w > 100 else 26, BG).move_to(seg))
            caps.add(mix(cap_, 26, col if col != "#8a919e" else INK).move_to(px(x + w / 2, sy + 48)))
            segs.add(seg)
            x += w
        self.play(FadeOut(st["noise"].everything()), run_time=0.4)
        self.play(LaggedStart(*[GrowFromEdge(s, LEFT) for s in segs], lag_ratio=0.35),
                  LaggedStart(*[FadeIn(n_) for n_ in nums_], lag_ratio=0.35),
                  LaggedStart(*[FadeIn(c_, shift=UP * u(6)) for c_ in caps], lag_ratio=0.35), run_time=1.6)
        self.play(pop(ex_lbl, 1.2), run_time=0.6)

        # ---- S09_13：空 ----
        self.at("s09_13", -0.1)
        self.play(FadeOut(VGroup(segs, nums_, caps)), FadeIn(st["noise"].everything()),
                  FadeIn(st["photoish"].static()), FadeIn(st["photoish"].zero_lbl), run_time=0.6)
        self.at("small")
        self.play(st["photoish"].grow_hist(1.5), run_time=1.5)
        self.at("few")
        sp = st["photoish"]
        self.play(GrowFromEdge(sp.fill, LEFT), FadeIn(sp.copy_pct, shift=LEFT * u(6)), run_time=0.7)
        self.play(pop(sp.copy_pct, 1.25), run_time=0.5)

        self.at("S09_17")
        self.play(pop(imgs["photoish"], 1.12), run_time=0.7)

        # ---- S09_14：グラデーション ----
        self.at("s09_14", -0.1)
        sg = st["gradient"]
        self.play(FadeIn(sg.static()), FadeIn(sg.zero_lbl), run_time=0.6)
        self.at("allzero")
        self.play(sg.grow_hist(1.0), run_time=1.0)
        self.play(pop(sg.zero_lbl, 1.2), run_time=0.5)
        self.at("copies")
        self.play(GrowFromEdge(sg.fill, LEFT), FadeIn(sg.copy_pct, shift=LEFT * u(6)), run_time=1.1)
        self.play(pop(sg.copy_pct, 1.25), run_time=0.5)

        # ---- S09_15：ずんだもんの画像 ----
        self.at("s09_15", -0.1)
        zarr = pixels("zundamon")
        zimg = png_mob(zarr, 400)
        zimg.move_to(px(590, 270))
        raw_bar = Rectangle(width=u(BAR_W), height=u(BAR_H), stroke_width=0, fill_color=BAR_COL, fill_opacity=1)
        raw_bar.move_to(px(BAR_X0 + BAR_W / 2, 130))
        z_raw_lbl = mix(f"生 {fmt(zr)}", 38, BG)
        z_raw_lbl.move_to(px(BAR_X0 + 16, 130), aligned_edge=LEFT)
        ref2 = DashedLine(px(BAR_X0 + BAR_W, 70), px(BAR_X0 + BAR_W, 300), dash_length=u(10), stroke_width=3, color=DIM)
        ref2.check_ignore = True
        gone = Group(*[imgs[n] for n, _ in names], *[name_lbl[n] for n, _ in names],
                      *[st[n].everything() for n, _ in names], bars["photoish"], bars["noise"],
                      bar_lbl["gradient"], bar_lbl["photoish"], n_num, n_pct, ex_lbl, ex_arrow, mid)
        self.play(FadeOut(gone), FadeOut(ref), Transform(bars["gradient"], raw_bar), FadeIn(zimg, scale=0.95),
                  run_time=1.0)
        self.play(FadeIn(z_raw_lbl), Create(ref2), run_time=0.5)

        # ---- S09_16：背景が透明 → 0 がずっと続く ----
        self.at("s09_16", -0.1)
        r = 1000
        fz = filtered("zundamon")
        row = fz[r, 1:]
        run = best = 0
        for v in row:
            run = run + 1 if v == 0 else 0
            best = max(best, run)
        strip = ImageMobject(checker_composite(zarr[r:r + 1], 24))
        strip.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        strip.stretch_to_fit_width(u(640)).stretch_to_fit_height(u(50)).move_to(px(BAR_X0 + 320, 545))
        strip_cap = mix(f"画像の1行（{zarr.shape[1]}画素）", 28, DIM).move_to(px(BAR_X0, 490), aligned_edge=LEFT)
        zeros = mono(" ".join("0" for _ in range(16)), 34, YELLOW).move_to(px(BAR_X0 + 320, 610))
        zeros_cap = mix(f"フィルタ後は、0 が最長 {fmt(best)} 個つづく", 30, YELLOW).move_to(px(BAR_X0, 662),
                                                                                   aligned_edge=LEFT)
        zst = Stats("zundamon", 755)
        self.play(FadeIn(strip_cap), FadeIn(strip, shift=UP * u(6)), run_time=0.8)
        self.at("bg", -0.2)
        self.play(LaggedStart(*[FadeIn(c, scale=0.6) for c in zeros], lag_ratio=0.05),
                  FadeIn(zeros_cap, shift=UP * u(6)), run_time=0.7)
        # S06 のコピー（距離1・長さ258）の再登場
        self.at("S09_21", 0.5)
        cyan_ul = underline(zeros, CYAN)
        arc = CurvedArrow(zeros[0].get_top() + UP * u(6), zeros[1].get_top() + UP * u(6), angle=-PI / 2,
                          stroke_width=4, color=CYAN, tip_length=u(12))
        copy_cap = mix("距離1・長さ258 のコピー", 30, CYAN).move_to(zeros_cap, aligned_edge=LEFT)
        self.play(Create(cyan_ul), Create(arc), zeros.animate.set_color(CYAN), retext(zeros_cap, copy_cap),
                  run_time=0.9)
        self.play(pop(zeros_cap, 1.15), run_time=0.6)
        self.at("S09_21", 3.0)
        self.play(FadeIn(zst.static()), FadeIn(zst.zero_lbl), zst.grow_hist(0.9), run_time=0.9)

        # ---- 約21分の1 ----
        self.at("ratio", -0.2)
        pw = BAR_W * zs / zr
        png_bar = Rectangle(width=u(pw), height=u(BAR_H), stroke_width=0, fill_color=YELLOW, fill_opacity=1)
        png_bar.move_to(px(BAR_X0 + pw / 2, 230))
        png_lbl = mix(f"PNG {fmt(zs)}", 38)
        png_lbl.next_to(png_bar, RIGHT, buff=u(18))
        k = round(zr / zs)
        big = mix(f"約1/{k}", 72, YELLOW)
        big.move_to(px(1240, 320))
        self.se("shine")
        self.play(GrowFromEdge(png_bar, LEFT), GrowFromEdge(zst.fill, LEFT), FadeIn(zst.copy_pct), run_time=1.0,
                  rate_func=rate_functions.ease_out_cubic)
        self.play(FadeIn(png_lbl, shift=RIGHT * u(8)), FadeIn(big, scale=0.7), run_time=0.7)
        self.play(pop(big, 1.2), run_time=0.7)

        self.at("s09_16e", 0.1)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.9)
        self.finish()
