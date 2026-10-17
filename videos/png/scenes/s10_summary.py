import io
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from PIL import Image  # noqa: E402

from vlib.data import chunks, file_bytes, fmt, info, path, pixels  # noqa: E402
from zunda.fx import Shake, pop, underline  # noqa: E402
from vlib.pmap import STAGE_COL, PipelineMap  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

SIG = [int(h, 16) for h in info("zundamon")["signature"].split()]
assert SIG == [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]
BOX = "#262b36"
GRAY = "#4a5160"
BODY = "#cfd4de"
RY = 320  # 帯の y


class S10(PScene):
    def construct(self):
        z = info("zundamon")
        files = [("gradient", "グラデーション"), ("photoish", "空"), ("noise", "砂嵐"), ("zundamon", "ずんだもん")]

        # ---- S10_01〜02：シグネチャ 8 バイト ----
        CW, GAP = 100, 12
        xs = [960 + (i - 3.5) * (CW + GAP) for i in range(8)]
        cells = VGroup(*[VGroup(Rectangle(width=u(CW), height=u(130), stroke_width=0, fill_color=BOX, fill_opacity=1),
                                mono(f"{b:02X}", 48, INK)) for b in SIG])
        for c, x in zip(cells, xs):
            c[0].move_to(px(x, RY)); c[1].move_to(c[0])
        asc = VGroup(*[mono(ch, 34, DIM).move_to(px(xs[i + 1], RY + 100)) for i, ch in enumerate("PNG")])
        sig_lbl = jp("シグネチャ", 42, YELLOW).move_to(px(960, RY - 120))
        self.at("s10_01", 0.5)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * u(14)) for c in cells], lag_ratio=0.1), run_time=1.4)
        self.at("sig", -0.3)
        ul = underline(VGroup(*[c[0] for c in cells]), YELLOW)
        self.play(Create(ul), FadeIn(sig_lbl, shift=DOWN * u(8)), FadeIn(asc), run_time=0.7)
        self.play(*[c[1].animate.set_color(YELLOW) for c in cells], run_time=0.5)

        # ---- チャンクの並び（長さは実データ）----
        ch = chunks("zundamon")
        sizes = [c["length"] + 12 for c in ch]
        idats = [s for c, s in zip(ch, sizes) if c["type"] == "IDAT"]
        idat_total = sum(idats)
        assert [c["type"] for c in ch][0] == "IHDR" and ch[-1]["type"] == "IEND"
        UNIT_W = 160 / max(idats)  # 最大の IDAT が 160px
        FIX, G = 150, 5
        x_cur = 960 - (FIX * 3 + sum(s * UNIT_W for s in idats) + G * (len(ch) + 1 - 1)) / 2
        pos = {}

        def put(w):
            nonlocal x_cur
            r = (x_cur, x_cur + w)
            x_cur += w + G
            return r

        sig_r = put(FIX)
        ihdr_r = put(FIX)
        idat_r = [put(s * UNIT_W) for s in idats]
        iend_r = put(FIX)

        def rect(r, col, y=RY, h=64):
            return Rectangle(width=u(r[1] - r[0]), height=u(h), stroke_width=0, fill_color=col, fill_opacity=1)\
                .move_to(px((r[0] + r[1]) / 2, y))

        # シグネチャの 8 マスが、リボンの先頭の細い帯になる
        sw = (FIX - 7 * 2.5) / 8
        slivers = [Rectangle(width=u(sw), height=u(64), stroke_width=0, fill_color=GRAY, fill_opacity=1)
                   .move_to(px(sig_r[0] + sw / 2 + i * (sw + 2.5), RY)) for i in range(8)]
        ihdr = rect(ihdr_r, GRAY)
        idat_bars = VGroup(*[rect(r, BODY) for r in idat_r])
        iend = rect(iend_r, GRAY)

        def label2(name, nbytes, cx, col=INK):
            a = mix(name, 28, col).move_to(px(cx, RY + 62))
            b = mix(f"{fmt(nbytes)} バイト", 24, DIM).move_to(px(cx, RY + 98))
            return VGroup(a, b)

        sig_cx, ihdr_cx, iend_cx = sum(sig_r) / 2, sum(ihdr_r) / 2, sum(iend_r) / 2
        idat_cx = (idat_r[0][0] + idat_r[-1][1]) / 2
        l_ihdr, l_iend = label2("IHDR", sizes[0], ihdr_cx), label2("IEND", sizes[-1], iend_cx)
        l_idat = label2(f"IDAT ×{len(idats)}", idat_total, idat_cx)
        sig_bytes = mix("8 バイト", 24, DIM).move_to(px(sig_cx, RY + 98))

        self.at("chunks", -0.2)
        self.play(*[c[0].animate.become(s) for c, s in zip(cells, slivers)],
                  *[FadeOut(c[1]) for c in cells], FadeOut(asc), FadeOut(ul),
                  sig_lbl.animate.scale(28 / 42).set_color(INK).move_to(px(sig_cx, RY + 62)),
                  run_time=1.1)
        self.play(LaggedStart(FadeIn(ihdr, shift=LEFT * u(10)), *[FadeIn(b, shift=LEFT * u(10)) for b in idat_bars],
                              FadeIn(iend, shift=LEFT * u(10)), lag_ratio=0.15),
                  FadeIn(sig_bytes), FadeIn(l_ihdr, shift=UP * u(6)), FadeIn(l_idat, shift=UP * u(6)),
                  FadeIn(l_iend, shift=UP * u(6)), run_time=1.3)

        # ---- S10_03：IDAT の中身（地図）----
        m = PipelineMap()
        ribbon_parts = VGroup(*[c[0] for c in cells], sig_lbl, sig_bytes, ihdr, iend, l_ihdr, l_iend)
        self.at("idat", -0.2)
        everything = VGroup(idat_bars, l_idat)
        idat_mid = (idat_r[0][0] + idat_r[-1][1]) / 2
        self.play(everything.animate.shift(px(960, 660) - px(idat_mid, RY)),
                  FadeOut(ribbon_parts), FadeIn(m, shift=DOWN * u(12)), run_time=1.1)
        self.play(pop(m.parts["idat"], 1.3), run_time=0.6)

        for cue, stage in (("f", "filter"), ("lz", "lz77"), ("hf", "huff")):
            self.at(cue, -0.2)
            self.play(Transform(m, m.state("full", active=stage)), run_time=0.5)
        self.at("s10_03e", 0.1)
        self.play(Transform(m, m.state("full", active=None, done=("filter", "lz77", "huff"))), run_time=0.6)

        # ---- S10_04：画像が地図を通って、戻ってくる（実データ）----
        self.at("s10_04", 0.0)
        # 画素を復元して、元と 1 バイトも違わないことを確かめる
        back = np.asarray(Image.open(io.BytesIO(file_bytes("zundamon"))))
        assert np.array_equal(back, pixels("zundamon")) and back.nbytes == z["pixel_bytes"]
        IH, yy = 420, 630
        pm = m.parts
        orig = png_mob(pixels("zundamon"), IH)
        orig.move_to(px(620, yy))
        trav = png_mob(pixels("zundamon"), IH)
        trav.move_to(orig)
        self.play(FadeOut(everything), FadeIn(orig, shift=UP * u(8)), run_time=0.5)
        self.add(trav)
        DONE = ("filter", "lz77", "huff")
        SH = 0.34  # 333KB / 6.9MB の面積比のおよそ平方根
        fwd = [("filter", 810, 1.0), ("lz77", 1000, 1.0), ("huff", 1190, 1.0), ("zlib", 1390, SH)]
        for k, x, sc in fwd:
            st = m.state("full", active=k if k != "zlib" else None, done=DONE if k == "zlib" else ())
            a = trav.animate.move_to(px(x, yy))
            self.play(a.scale(sc) if sc != 1.0 else a, Transform(m, st), run_time=0.4)
        self.at("lossless", 0.25)
        LAND = 1100
        for k, x in [("huff", 1300), ("lz77", 1220), ("filter", 1150), ("pixels", LAND)]:
            if k == "pixels":
                st = m.state("full", active=None, done=DONE)
                a = trav.animate.move_to(px(x, yy)).scale(1 / SH)
            else:
                st = m.state("full", active=k)
                a = trav.animate.move_to(px(x, yy))
            self.play(a, Transform(m, st), run_time=0.55)
        eq = mix("=", 90, YELLOW).move_to(px((620 + LAND) / 2, yy))
        same = mix(f"{fmt(z['pixel_bytes'])} バイト すべて元のまま", 38, YELLOW)
        same.move_to(px(960, 880))
        self.play(FadeIn(eq, scale=0.6), FadeIn(same, shift=UP * u(10)), run_time=0.6)
        self.play(pop(same, 1.08), run_time=0.5)

        # ---- S10_05：画像の性質で効き方が違う（実データ）----
        self.at("kind", -0.1)
        rows_y = [540, 630, 720, 810]
        BX0, BW = 790, 420
        vals = []
        for name, _ in files:
            inf = info(name)
            vals.append((inf["file_size"], inf["pixel_bytes"]))
        assert [v[0] for v in vals] == [8575, 414139, 788086, 333074]
        raw_line = DashedLine(px(BX0 + BW, 500), px(BX0 + BW, 855), color=DIM, stroke_width=2, dash_length=u(8))
        raw_lbl = jp("元の大きさ", 28, DIM).move_to(px(BX0 + BW, 470))
        base = Line(px(BX0, 500), px(BX0, 855), color=DIM, stroke_width=2)
        rows = []
        for (name, jname), (fs, pb), y in zip(files, vals, rows_y):
            r = fs / pb
            col = CORAL if r > 1 else CYAN
            thumb = png_mob(pixels(name), 64, 8) if name == "zundamon" else ImageMobject(str(path(name)))
            if name != "zundamon":
                thumb.height = u(60)
            thumb.move_to(px(495, y))
            nm = jp(jname, 30, INK).move_to(px(540, y), aligned_edge=LEFT)
            bar = Rectangle(width=u(max(BW * r, 3)), height=u(40), stroke_width=0, fill_color=col, fill_opacity=0.9)
            bar.move_to(px(BX0, y), aligned_edge=LEFT)
            lab = mix(f"{fmt(fs)} {r * 100:.1f}%", 28, col)
            lab.move_to(px(BX0 + max(BW * r, 3) + 18, y), aligned_edge=LEFT)
            rows.append(Group(thumb, nm, bar, lab))
        self.play(FadeOut(Group(same, eq, orig, trav)),
                  FadeIn(raw_line), FadeIn(raw_lbl), FadeIn(base), run_time=0.7)
        grown = []
        anims = []
        for i, rw in enumerate(rows):
            bar_final = rw[2].copy()
            bar0 = bar_final.copy().stretch_to_fit_width(0.001).move_to(bar_final.get_left(), aligned_edge=LEFT)
            rw[2].become(bar0)
            grown.append(bar_final)
        for i, rw in enumerate(rows):
            fin = grown[i]
            self.play(FadeIn(rw[0], shift=RIGHT * u(10)), FadeIn(rw[1], shift=RIGHT * u(10)),
                      rw[2].animate.become(fin), FadeIn(rw[3], shift=RIGHT * u(10)), run_time=0.45)
            self.wait(0.1)
        self.at("fun")
        self.play(pop(rows[2][3], 1.15), Shake(rows[2][2], 6), run_time=0.7)

        # ---- S10_06：僕の画像 → ありがとう ----
        self.at("mine")
        self.play(*[p.animate.set_opacity(0.3) for i in (0, 1, 2) for p in rows[i]], pop(rows[3], 1.1, 0.8), run_time=0.8)

        # ---- エンドクレジット ----
        title = jp("クレジット", 44, INK).move_to(px(960, 190))
        rows = [("音声", ["VOICEVOX:ずんだもん", "VOICEVOX:四国めたん"]), ("立ち絵", ["坂本アヒル"]),
                ("音楽", ["甘茶の音楽工房"]), ("効果音", ["効果音ラボ"]),
                ("フォント", ["Zen Maru Gothic", "M PLUS Rounded 1c", "JetBrains Mono"]),
                ("映像", ["Manim Community"])]
        cred = Group(title)
        y = 280
        for cat, vals in rows:
            cred.add(jp(cat, 32, DIM).move_to(px(520, y), aligned_edge=LEFT))
            for v in vals:
                cred.add(mix(v, 32, INK).move_to(px(780, y), aligned_edge=LEFT))
                y += 58
            y += 14
        self.at("S10_09.end", 0.3)
        self.play(FadeOut(*self.mobjects), run_time=1.7, rate_func=smooth)
        self.play(FadeIn(cred, shift=UP * u(10)), run_time=1.0)
        # クレジットの上で「ありがとう」「またね」
        self.at("S10_11.end", 1.2)
        self.play(FadeOut(cred), run_time=3.2)
        self.finish()
