import colorsys
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import chunks, fmt, info, pixels  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from vlib.pmap import ORDER, STAGE_COL, PipelineMap  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

X0, W, YB, BH = 210, 1500, 290, 72  # zlib の帯（px）
HW = 10  # 表の印の幅（見えるよう実際より太くしてある）
IMG_H, IMG_CX, IMG_CY = 520, 760, 645


class S08(PScene):
    def construct(self):
        z = info("zundamon")
        blocks = z["blocks"]
        cks = chunks("zundamon")
        idat = [c for c in cks if c["type"] == "IDAT"]
        zdata = b"".join(c["data"] for c in idat)
        assert len(blocks) == 11 and len(zdata) == z["idat_bytes"] == 332957
        assert [len(c["data"]) for c in idat] == [65536] * 5 + [5277]
        assert zdata[:2].hex(" ").upper() == z["zlib_header"].upper() == "78 DA"
        assert zdata[-4:].hex() == z["adler32"]
        DEFB = len(zdata) - 6  # DEFLATE 本体のバイト数
        cum = [0.0]
        for b in blocks:
            cum.append(cum[-1] + b["bits"] / 8)
        assert abs(cum[-1] - DEFB) < 1
        cum[-1] = DEFB
        H_ = z["height"]
        stride = 1 + z["width"] * z["channels"]
        assert sum(b["out_bytes"] for b in blocks) == stride * H_
        rows = [0]
        for b in blocks:
            rows.append(rows[-1] + b["out_bytes"] / stride)
        hdr_bytes = [b["header_bits"] / 8 for b in blocks]
        blk_bytes = [int(round(b["bits"] / 8)) for b in blocks]

        def bx(v):  # DEFLATE のバイト位置 → 帯の x（px）
            return X0 + W * v / DEFB

        COLS = [rgb_to_color(colorsys.hsv_to_rgb(i / 11, 0.55, 0.92)) for i in range(11)]

        # ---- S08_01：LZ77 + ハフマン = DEFLATE ----
        m = PipelineMap("full", done=("filter", "lz77", "huff"))
        self.add(m)
        self.at("deflate", -0.2)
        br, lab = m.deflate
        self.play(br.animate.set_color(YELLOW), lab.animate.scale(1.3).set_color(YELLOW),
                  m.parts["lz77"][0].animate.set_fill(STAGE_COL["lz77"], 0.6),
                  m.parts["huff"][0].animate.set_fill(STAGE_COL["huff"], 0.6),
                  run_time=0.7)
        self.play(pop(m.parts["lz77"], 1.12, 0.5), pop(m.parts["huff"], 1.12, 0.5), run_time=0.5)

        # ---- S08_02：zlib の帯が 11 ブロックに割れる ----
        self.at("S08_02", 0.1)
        self.play(pop(m.parts["lz77"], 1.15, 0.6), pop(m.parts["huff"], 1.15, 0.6), pop(m.deflate[1], 1.15, 0.6),
                  run_time=0.6)
        self.at("s08_02", 0.05)
        grey = Rectangle(width=u(W), height=u(BH), stroke_width=0, fill_color="#3a4150", fill_opacity=1)
        grey.move_to(px(X0 + W / 2, YB))
        zlab = mix(f"zlib {fmt(z['idat_bytes'])} バイト", 38, INK)
        zlab.move_to(px(X0 + W / 2, YB - 150))
        self.play(Transform(m, m.state("strip", active=None, done=("filter", "lz77", "huff"))),
                  GrowFromEdge(grey, LEFT), FadeIn(zlab, shift=DOWN * u(8)), run_time=1.2)

        self.at("blocks")
        rects = []
        for i in range(11):
            r = Rectangle(width=u(bx(cum[i + 1]) - bx(cum[i])), height=u(BH), stroke_width=0,
                          fill_color=COLS[i], fill_opacity=1)
            r.move_to(px((bx(cum[i]) + bx(cum[i + 1])) / 2, YB))
            rects.append(r)
        nums = VGroup(*[jp(str(i + 1), 28, COLS[i]).move_to(px((bx(cum[i]) + bx(cum[i + 1])) / 2, YB + 66))
                        for i in range(11)])
        self.play(LaggedStart(*[AnimationGroup(FadeIn(r), FadeIn(n, shift=DOWN * u(6)))
                                for r, n in zip(rects, nums)], lag_ratio=0.1), run_time=1.4)
        self.remove(grey)

        self.at("table")
        slivers = VGroup(*[Rectangle(width=u(HW), height=u(BH), stroke_width=0, fill_color=INK, fill_opacity=0.92)
                           .move_to(px(bx(cum[i]) + HW / 2, YB)) for i in range(11)])
        tl = jp("ハフマンの表", 32, INK).move_to(px(X0 - 6, YB - 90), aligned_edge=LEFT)
        ptr = Line(px(X0 + HW / 2, YB - 70), px(X0 + HW / 2, YB - BH / 2 - 2), stroke_width=3, color=INK)
        self.play(LaggedStart(*[FadeIn(s, scale=2.2) for s in slivers], lag_ratio=0.08),
                  FadeIn(tl, shift=DOWN * u(6)), Create(ptr), run_time=1.3)

        # ---- S08_03：場所ごとに表が違う（表の印を順に光らせる）----
        self.at("S08_04", 0.1)
        self.play(Shake(slivers, 7), run_time=0.7)
        self.at("local")
        self.play(LaggedStart(*[sl.animate(rate_func=there_and_back).set_fill(YELLOW) for sl in slivers],
                              lag_ratio=0.12), run_time=1.6)

        # ---- S08_04：Z「もったいなくないのだ？」→ 実寸で見る ----
        self.at("waste")
        ZW = 1000
        zx0, zy = 460, 545
        k0 = 0
        zb = Rectangle(width=u(ZW), height=u(56), stroke_width=0, fill_color=COLS[k0], fill_opacity=1)
        zb.move_to(px(zx0 + ZW / 2, zy))
        zs = Rectangle(width=u(ZW * hdr_bytes[k0] / blk_bytes[k0]), height=u(56), stroke_width=0, fill_color=INK,
                       fill_opacity=0.95)
        zs.move_to(px(zx0 + ZW * hdr_bytes[k0] / blk_bytes[k0] / 2, zy))
        zt1 = mix(f"表 {round(hdr_bytes[k0])} バイト", 36, INK)
        zt1.move_to(px(zx0, zy - 78), aligned_edge=LEFT)
        zptr = Line(px(zx0 + 2, zy - 60), px(zx0 + 2, zy - 28), stroke_width=3, color=INK)
        zt2 = mix(f"ブロック{k0 + 1} {fmt(blk_bytes[k0])} バイト", 36, INK).move_to(px(zx0 + ZW, zy + 62), aligned_edge=RIGHT)
        self.play(TransformFromCopy(rects[k0], zb), run_time=0.9)
        self.play(FadeIn(zs), FadeIn(zt1, shift=DOWN * u(6)), Create(zptr), FadeIn(zt2, shift=UP * u(6)),
                  Shake(slivers, 7), run_time=0.8)
        self.at("small")
        lo, hi = min(hdr_bytes), max(hdr_bytes)
        t1 = mix(f"表 {round(lo)}〜{round(hi)} バイト", 40, YELLOW)
        t2 = mix(f"ブロック {fmt(min(blk_bytes))}〜{fmt(max(blk_bytes))} バイト", 40, INK)
        info_t = VGroup(t1, t2).arrange(DOWN, buff=u(16), aligned_edge=LEFT).move_to(px(960, 745))
        self.play(FadeIn(info_t, shift=UP * u(8)), run_time=0.7)
        self.at("gain")
        self.play(pop(t2, 1.12, 0.6), run_time=0.6)

        # ---- S08_06：ブロックごとの担当範囲を画像の横に ----
        self.at("s08_06", 0.5)
        zimg = png_mob(pixels('zundamon'), IMG_H)
        zimg.move_to(px(IMG_CX, IMG_CY))
        self.play(FadeOut(Group(info_t, zb, zs, zt1, zt2, zptr, tl, ptr)), FadeIn(zimg, shift=UP * u(14)), run_time=0.7)
        self.at("bands")
        ztop, zh = zimg.get_top()[1], zimg.height
        bandx = zimg.get_right()[0] + u(40)
        bands, bnums = VGroup(), VGroup()
        for i in range(11):
            r0, r1 = rows[i], rows[i + 1]
            b = Rectangle(width=u(40), height=zh * (r1 - r0) / H_, stroke_width=0, fill_color=COLS[i], fill_opacity=1)
            b.move_to([bandx, ztop - zh * (r0 + r1) / 2 / H_, 0])
            bands.add(b)
            bnums.add(jp(str(i + 1), 24, COLS[i]).move_to([bandx + u(48), b.get_center()[1], 0]))
        bands.check_group = True
        self.play(LaggedStart(*[TransformFromCopy(rects[i], bands[i]) for i in range(11)], lag_ratio=0.07),
                  FadeIn(bnums, shift=RIGHT * u(8)), run_time=1.6)

        self.at("order")
        grp = [VGroup(rects[i], slivers[i], bands[i], bnums[i]) for i in range(11)]
        self.play(*[g.animate.set_opacity(0.22) for g in grp], run_time=0.4)
        self.play(LaggedStart(*[g.animate(rate_func=smooth).set_opacity(1) for g in grp], lag_ratio=0.55),
                  run_time=min(3.0, self.until("s08_08", -0.1) - 0.5))

        # ---- S08_08：zlib = 2バイトの頭 + DEFLATE + 4バイトの尻 ----
        self.at("head", -0.2)
        hm = Rectangle(width=u(12), height=u(BH), stroke_width=0, fill_color=YELLOW, fill_opacity=1)
        hm.move_to(px(X0 - 6, YB))
        hchip = mix(f"{zdata[:2].hex(' ').upper()} 目印", 34, YELLOW)
        hchip.move_to(px(X0 - 12, YB - 90), aligned_edge=LEFT)
        self.play(GrowFromEdge(hm, RIGHT), FadeIn(hchip, shift=DOWN * u(8)), run_time=0.6)
        self.at("tail", -0.2)
        X1 = X0 + W
        tm = Rectangle(width=u(12), height=u(BH), stroke_width=0, fill_color=YELLOW, fill_opacity=1)
        tm.move_to(px(X1 + 6, YB))
        tchip = mix(f"検算用 {zdata[-4:].hex(' ').upper()}", 34, YELLOW)
        tchip.move_to(px(X1 + 12, YB - 90), aligned_edge=RIGHT)
        self.play(GrowFromEdge(tm, LEFT), FadeIn(tchip, shift=DOWN * u(8)), run_time=0.6)

        # ---- Z「検算用？」→ 元のデータ全部から計算した数 ----
        self.at("S08_11", 0.1)
        self.play(FadeOut(Group(bands, bnums)), pop(tchip, 1.12, 0.6),
                  zimg.animate.scale(0.3).move_to(px(590, 660)), run_time=0.9)
        raw = Rectangle(width=u(720), height=u(50), stroke_width=0, fill_color="#3a4150", fill_opacity=1)
        raw.move_to(px(1100, 660))
        rlab = mix(f"元のデータ全部 {fmt(z['raw_bytes'])} バイト", 34, INK).move_to(px(1100, 595))
        self.at("S08_12", 0.1)
        self.play(GrowFromEdge(raw, LEFT), FadeIn(rlab, shift=DOWN * u(8)), run_time=0.8)
        self.at("calc")
        ck = VGroup(jp("adler32", 28, DIM), jp(zdata[-4:].hex(" ").upper(), 36, YELLOW)).arrange(RIGHT, buff=u(16))
        ck.move_to(px(1100 + 360, 735), aligned_edge=RIGHT)
        fly = jp(zdata[-4:].hex(" ").upper(), 36, YELLOW)
        fly.move_to(tchip.get_right() + LEFT * fly.width / 2)
        fly.check_ignore = True
        self.add(fly)
        carr = Arrow(px(1400, 690), px(1400, 712), buff=0, stroke_width=4, color=DIM, max_tip_length_to_length_ratio=0.5)
        self.play(fly.animate(path_arc=-PI / 3).move_to(ck[1]), FadeIn(ck[0]), Create(carr), run_time=1.2)
        self.remove(fly)
        self.add(ck[1])
        self.at("open", -0.3)
        op = jp("開いたあと、もう一度計算", 34, INK).move_to(px(960, 800))
        self.play(FadeIn(op, shift=UP * u(8)), run_time=0.6)
        self.at("broken")
        self.play(retext(op, jp("合わなければ、壊れている", 36, CORAL)), Shake(ck[1], 8), run_time=0.8)

        # ---- S08_09：65,536 バイトごとに切って IDAT の箱へ ----
        self.at("split", -0.3)
        cuts = [bx(k * 65536 - 2) for k in range(1, 6)]
        cut_lines = VGroup(*[DashedLine(px(c, YB - 58), px(c, YB + 58), color=INK, stroke_width=4, dash_length=u(8))
                             for c in cuts])
        self.play(FadeOut(Group(zimg, nums, zlab, hchip, tchip, raw, rlab, ck, carr, op), run_time=0.6),
                  Create(cut_lines), run_time=0.7)
        # 切れ目をまたぐブロックを 2 つに分ける（見た目は同じ）
        allr = list(rects) + list(slivers) + [hm, tm]
        pieces = [[] for _ in range(6)]
        for r in allr:
            xa, xb = r.get_left()[0], r.get_right()[0]
            edges = [xa] + [px(c, 0)[0] for c in cuts if xa + 1e-3 < px(c, 0)[0] < xb - 1e-3] + [xb]
            self.remove(r)
            for s0, s1 in zip(edges, edges[1:]):
                seg = Rectangle(width=s1 - s0, height=r.height, stroke_width=0, fill_color=r.get_fill_color(),
                                fill_opacity=r.get_fill_opacity())
                seg.move_to([(s0 + s1) / 2, r.get_center()[1], 0])
                self.add(seg)
                cx = (s0 + s1) / 2
                pieces[sum(1 for c in cuts if px(c, 0)[0] < cx)].append(seg)
        pg = [VGroup(*p) for p in pieces]
        S = 0.85
        wid = [g.width / u(1) * S for g in pg]
        items = [("署名", 90), ("IHDR", 110)] + [("IDAT", w + 16) for w in wid] + [("IEND", 110)]
        GAP, RY = 12, 400
        total = sum(w for _, w in items) + GAP * (len(items) - 1)
        xs, x = [], 960 - total / 2
        for _, w in items:
            xs.append(x + w / 2); x += w + GAP
        boxes, labels = [], []
        for k in range(6):
            cxp = xs[2 + k]
            bxo = RoundedRectangle(corner_radius=u(10), width=u(wid[k] + 16), height=u(BH * S + 18), stroke_width=0,
                                   fill_color="#262b36", fill_opacity=1).move_to(px(cxp, RY))
            boxes.append(bxo)
            lb = VGroup(jp("IDAT", 24, DIM), jp(fmt(len(idat[k]["data"])), 28, INK)).arrange(DOWN, buff=u(4))
            lb.move_to(px(cxp, RY - 88))
            labels.append(lb)
        self.at("split", 0.9)
        for b_ in boxes:
            self.add(b_)
        for g in pg:
            self.bring_to_front(g)
        self.play(*[g.animate.scale(S).move_to(px(xs[2 + k], RY)) for k, g in enumerate(pg)],
                  *[FadeIn(b_, scale=0.9) for b_ in boxes], FadeOut(cut_lines),
                  LaggedStart(*[FadeIn(lb, shift=DOWN * u(6)) for lb in labels], lag_ratio=0.12),
                  run_time=1.6)

        self.at("done", -0.2)
        side = []
        for (name, w), cxp in [(items[0], xs[0]), (items[1], xs[1]), (items[-1], xs[-1])]:
            bxo = RoundedRectangle(corner_radius=u(10), width=u(w), height=u(BH * S + 18), stroke_width=0,
                                   fill_color="#262b36", fill_opacity=1).move_to(px(cxp, RY))
            t = (jp(name, 28, DIM) if name == "署名" else jp(name, 26, DIM)).move_to(bxo)
            side.append(VGroup(bxo, t))
        fl = mix(f"PNGファイル {fmt(z['file_size'])} バイト", 44, INK).move_to(px(960, 540))
        self.play(*[FadeIn(s, shift=(RIGHT if k == 0 else LEFT) * u(18)) for k, s in enumerate(side)] ,
                  FadeIn(fl, shift=UP * u(8)), run_time=0.9)
        self.play(pop(fl, 1.1, 0.5))

        # ---- S08_10：地図が端から端までつながる ----
        self.at("s08_09e", 0.2)
        file_all = VGroup(*pg, *boxes, *labels, *side, fl)
        self.play(FadeOut(file_all), Transform(m, m.state("full", active=None, done=("filter", "lz77", "huff"))),
                  run_time=1.1)
        self.at("link")
        dot = Dot(radius=u(11), color=YELLOW).move_to(m.parts["pixels"].get_center() + DOWN * u(46))
        dot.check_ignore = True
        self.add(dot)
        for k in ORDER:
            c = m.parts[k].get_center()
            self.play(dot.animate.move_to([c[0], dot.get_center()[1], 0]), pop(m.parts[k], 1.18, 0.28),
                      run_time=0.28)
        self.play(m.arrows.animate.set_color(INK), run_time=0.3)
        self.at(self.tl["duration"] - 1.7)
        self.play(FadeOut(m), FadeOut(dot), run_time=1.1)
        self.finish()
