import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, full_trace, info  # noqa: E402
from zunda.fx import Shake, pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

LZW_COL = PURPLE
GRAY = "#7d8494"
BIT_COLS = [PURPLE, BLUE]          # 符号ごとに交互の色
NC = 4                             # 見せる符号の数（4 × 9 = 36 ビット）
BP, CP, GAP = 25, 9 * 25, 70       # ビットの間隔、1 符号の幅、符号の間
ROW_L = 960 - (NC * CP + (NC - 1) * GAP) / 2
Y_CODE, Y_BITS, Y_BYTES, Y_HEX = 130, 215, 320, 400
BAND_OP = {9: 0.3, 10: 0.45, 11: 0.6, 12: 0.8}


def bit_x(g, j):                   # g 番目の符号の、左から j 文字目
    return ROW_L + g * (CP + GAP) + BP * j + BP / 2


def pack_lsb_first(codes, size=9):
    """GIF の詰め方：各符号を下位ビットから順に、各バイトの下位ビットから埋める"""
    out, acc, n = [], 0, 0
    for c in codes:
        acc |= c << n
        n += size
        while n >= 8:
            out.append(acc & 255)
            acc >>= 8
            n -= 8
    return out, n


class S06(PScene):
    def construct(self):
        inf = info()
        fr0 = inf["frames"][0]
        lz = fr0["lzw"]
        tr = full_trace()
        data_off = fr0["data_offset"]
        fb = file_bytes("zunda_anim")
        codes = [t["code"] for t in tr[:NC]]
        assert all(t["size"] == 9 for t in tr[:NC]) and codes[0] == 256
        packed, rest = pack_lsb_first(codes)
        assert rest == 4 and len(packed) == 4
        assert list(fb[data_off + 1:data_off + 1 + len(packed)]) == packed, (list(fb[data_off + 1:data_off + 10]), packed)
        assert tr[NC]["size"] == 9
        assert fb[data_off] == 255                     # 最初の小分けは 255 バイト
        sizes = [t["size"] for t in tr]
        sc = lz["size_changes"]
        assert sc[:3] == [dict(at_code=256, size=10), dict(at_code=768, size=11), dict(at_code=1792, size=12)]
        assert [s["at_code"] + 256 for s in sc[:3]] == [512, 1024, 2048]   # 辞書が 512・1024・2048 個になる所
        assert max(sizes) == lz["max_size"] == 12
        clears = [i for i, t in enumerate(tr) if t["kind"] == "clear"]
        assert len(clears) == lz["clears"] == 4 and len(tr) == lz["codes"]
        assert fr0["sub_blocks"] == 69
        sbs = fr0["data_bytes"]
        n_full, last = divmod(sbs, 255)
        assert n_full + 1 == 69

        # ---- 符号の列 ----
        self.at("s06_01", 0.1)
        chips, bits, bit_groups = VGroup(), VGroup(), []
        for g, c in enumerate(codes):
            ch = mono(str(c), 44, LZW_COL).move_to(px(bit_x(g, 4), Y_CODE))
            chips.add(ch)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * u(8)) for c in chips], lag_ratio=0.1), run_time=1.4)

        # ---- 9 ビットのビット列に ----
        self.at("bits9", -0.1)
        for g, c in enumerate(codes):
            s = format(c, "09b")
            grp = VGroup(*[mono(s[j], 40, BIT_COLS[g % 2]).move_to(px(bit_x(g, j), Y_BITS)) for j in range(9)])
            bit_groups.append(grp)
            bits.add(grp)
        srcs = [ch.copy() for ch in chips]
        for s_ in srcs:
            s_.check_ignore = True
        self.play(LaggedStart(*[ReplacementTransform(s_, grp) for s_, grp in zip(srcs, bit_groups)], lag_ratio=0.1),
                  run_time=self.until("nine", -0.3))

        # ---- 9 ビット？ ----
        self.at("nine", -0.1)
        g0 = bit_groups[0]
        ul = underline(VGroup(*g0[1:]), GRAY)
        ninth = g0[0]
        self.play(Create(ul), ninth.animate.set_color(YELLOW), run_time=0.5)
        self.play(pop(ninth, 2.0, 0.8), run_time=0.8)

        # ---- 0〜255 の色 ＋ 新しい番号 ----
        self.at("why9", -0.35)
        self.play(FadeOut(ul), ninth.animate.set_color(BIT_COLS[0]), run_time=0.3)
        X0, SW = 490, 188                       # 数直線：5 つの区間（それぞれ 2 倍）
        Y_STRIP, Y_SEG, Y_TICK = 480, 560, 630
        edges = [0, 256, 512, 1024, 2048, 4096]
        ex = [X0 + SW * k for k in range(6)]

        def seg(k, col, op):
            r = Rectangle(width=u(SW), height=u(80), stroke_color=BG, stroke_width=3, fill_color=col, fill_opacity=op)
            return r.move_to(px(ex[k] + SW / 2, Y_SEG))

        def tick(k):
            return mono(str(edges[k]), 30, DIM).move_to(px(ex[k], Y_TICK))

        def strip(k0, k1, n, op, label=None):
            r = Rectangle(width=u(ex[k1] - ex[k0]), height=u(56), stroke_color=BG, stroke_width=3,
                          fill_color=LZW_COL if n > 8 else GRAY, fill_opacity=op)
            r.move_to(px((ex[k0] + ex[k1]) / 2, Y_STRIP))
            t = jp(f"{n}ビット", 32, INK).move_to(r)
            return r, t

        s1 = seg(0, CYAN, 0.75)
        l1 = jp("色", 38, BG).move_to(s1)
        t0, t1 = tick(0), tick(1)
        self.play(VGroup(chips, bits).animate.set_opacity(0.25), FadeIn(s1), FadeIn(l1), FadeIn(t0),
                  run_time=0.6)
        self.remove(chips)
        self.at("newn", -0.1)
        s2 = seg(1, LZW_COL, 0.75)
        l2 = jp("新しい番号", 34, BG).move_to(s2)
        self.play(FadeIn(s2, shift=LEFT * u(10)), FadeIn(l2), FadeIn(t1), run_time=0.6)
        self.at("b8", -0.1)
        r8, t8 = strip(0, 1, 8, 0.3)
        self.play(FadeIn(r8), FadeIn(t8), run_time=0.5)
        self.at("b9", -0.1)
        r9, t9 = strip(0, 2, 9, BAND_OP[9])
        self.play(Transform(r8, r9), Transform(t8, t9), run_time=0.6)

        # ---- 512 を超えたら 10、1024 を超えたら 11 ----
        self.at("grow", 0.3)
        s3 = seg(2, LZW_COL, 0.55)
        t2 = tick(2)
        self.play(FadeIn(s3, shift=LEFT * u(10)), FadeIn(t2), run_time=0.6)
        self.at("g10", -0.1)
        r10, t10 = strip(2, 3, 10, BAND_OP[10])
        self.play(FadeIn(r10), FadeIn(t10), run_time=0.4)
        self.play(pop(t10, 1.2, 0.4), run_time=0.4)
        self.at("grow2", 0.4)
        s4 = seg(3, LZW_COL, 0.4)
        t3 = tick(3)
        self.play(FadeIn(s4, shift=LEFT * u(10)), FadeIn(t3), run_time=0.6)
        self.at("g11", -0.1)
        r11, t11 = strip(3, 4, 11, BAND_OP[11])
        self.play(FadeIn(r11), FadeIn(t11), run_time=0.4)
        self.play(pop(t11, 1.2, 0.4), run_time=0.4)

        # ---- ずっと伸びたら ----
        self.at("max", 0.2)
        arrow = Arrow(px(ex[4] + 10, Y_SEG), px(ex[4] + 120, Y_SEG), color=DIM, stroke_width=6, buff=0)
        self.play(GrowArrow(arrow), run_time=0.7)

        # ---- 12 ビットで打ち止め ----
        self.at("limit", -0.1)
        s5 = seg(4, LZW_COL, 0.25)
        t4 = tick(4)
        t5 = tick(5)
        r12, t12 = strip(4, 5, 12, BAND_OP[12])
        self.play(ReplacementTransform(arrow, s5), FadeIn(t4), FadeIn(r12), FadeIn(t12), run_time=0.7)
        self.play(FadeIn(t5, shift=LEFT * u(8)), pop(t12, 1.2, 0.5), run_time=0.6)
        stop = Line(px(ex[5], Y_SEG - 55), px(ex[5], Y_SEG + 55), color=CORAL, stroke_width=8)
        self.at("stop", -0.1)
        self.play(Create(stop), t5.animate.set_color(CORAL), run_time=0.4)

        # ---- 辞書のリセット：1 コマ目の実際の位置 ----
        self.at("reset", -0.1)
        TX, TW, TY = 460, 1000, 560
        k = TW / len(tr)
        runs, i = [], 0
        while i < len(tr):
            j = i
            while j < len(tr) and (j == i or (sizes[j] == sizes[i] and tr[j]["kind"] != "clear")):
                j += 1
            runs.append((i, j, sizes[i]))
            i = j
        tl_rects = []
        for a, b, n in runs:
            r = Rectangle(width=u(k * (b - a)), height=u(60), stroke_width=0, fill_color=LZW_COL, fill_opacity=BAND_OP[n])
            r.move_to(px(TX + k * (a + b) / 2, TY))
            tl_rects.append((n, a, r))
        firsts = {}
        for n, a, r in tl_rects:
            if a < clears[1] and n not in firsts:
                firsts[n] = r
        others = [r for n, a, r in tl_rects if r not in firsts.values()]
        strip_olds = {9: r8, 10: r10, 11: r11, 12: r12}
        for r in others:
            r.set_opacity(0)
        gone = VGroup(s1, l1, s2, l2, s3, s4, s5, t0, t1, t2, t3, t4, t5, stop, t8, t10, t11, t12)
        self.play(*[ReplacementTransform(strip_olds[n], firsts[n]) for n in strip_olds],
                  FadeOut(gone), run_time=1.0)
        self.remove(*gone)
        for n, a, r in tl_rects:
            if r in others:
                r.set_fill(LZW_COL, opacity=BAND_OP[n])
        lvl = VGroup(*[jp(str(n), 26, INK).move_to(px(TX + k * (a_ + b_) / 2, TY - 50))
                       for n, (a_, b_) in [(n, (a, b)) for a, b, n in runs if a < clears[1]]])
        self.play(LaggedStart(*[FadeIn(r) for r in others], lag_ratio=0.1), FadeIn(lvl), run_time=0.8)
        ticks = VGroup(*[Line(px(TX + k * c, TY - 45), px(TX + k * c, TY + 45), color=CORAL, stroke_width=6) for c in clears])
        self.play(LaggedStart(*[Create(t) for t in ticks], lag_ratio=0.35), run_time=1.5)
        lab = jp(f"リセット {lz['clears']} 回", 36, CORAL).move_to(px(960, 455))
        self.play(FadeIn(lab, shift=UP * u(8)), run_time=0.6)

        # ---- ビット列 → バイト ----
        self.at("s06_06", -0.1)
        timeline = VGroup(*[r for _, _, r in tl_rects], ticks, lab, lvl)
        self.play(FadeOut(timeline), VGroup(bits).animate.set_opacity(1), run_time=0.8)
        self.remove(*[r for _, _, r in tl_rects], *ticks, lvl)
        self.at("bytes", -0.1)
        BP2, BGAP = 26, 30
        row_l = 960 - (5 * 8 * BP2 + 4 * BGAP) / 2

        def byte_x(b, c):
            return row_l + b * (8 * BP2 + BGAP) + BP2 * c + BP2 / 2

        stream = []
        for g, code in enumerate(codes):
            for j in range(9):               # j = 0 が最上位（左端）
                p = 9 * g + (8 - j)          # ストリーム内の位置（下位から詰める）
                b, c = divmod(p, 8)
                dst = mono(format(code, "09b")[j], 36, BIT_COLS[g % 2]).move_to(px(byte_x(b, 7 - c), Y_BYTES))
                cp = bit_groups[g][j].copy()
                cp.check_ignore = True
                stream.append((p, cp, dst))
        stream.sort(key=lambda t: t[0])
        # 4 つ目の符号の残り 4 ビットが入る 5 バイト目の、まだ空の所
        holes = VGroup(*[mono("·", 36, DIM).move_to(px(byte_x(4, 7 - c), Y_BYTES)) for c in range(rest, 8)])
        self.play(LaggedStart(*[ReplacementTransform(cp, dst) for _, cp, dst in stream], lag_ratio=0.045),
                  FadeIn(holes), run_time=1.6)
        byte_chars = [d for _, _, d in stream]
        # 各バイトの値（実データ）
        hexes = VGroup(*[mono(f"{v:02X}", 40, INK).move_to(px(byte_x(b, 3.5), Y_HEX)) for b, v in enumerate(packed)])
        self.play(LaggedStart(*[FadeIn(h, shift=UP * u(6)) for h in hexes], lag_ratio=0.1), run_time=0.6)

        # ---- 255 バイトずつの小分け ----
        self.at("sub", -0.1)
        SX, SW2, SY = 460, 1000, 560
        unit = SW2 / (n_full + last / 255)
        blocks = VGroup()
        for b in range(n_full + 1):
            w = unit * (1 if b < n_full else last / 255)
            r = Rectangle(width=u(w), height=u(70), stroke_color=BG, stroke_width=2, fill_color=LZW_COL, fill_opacity=0.7)
            r.move_to(px(SX + unit * b + w / 2, SY))
            blocks.add(r)
        self.play(LaggedStart(*[FadeIn(r) for r in blocks], lag_ratio=0.02), run_time=1.2)
        l255 = mix("255 バイト", 36, INK).move_to(px(SX, SY + 60), aligned_edge=LEFT)
        cnt = mix(f"{fr0['sub_blocks']} 個", 36, YELLOW).move_to(px(SX + SW2, SY + 60), aligned_edge=RIGHT)
        self.play(FadeIn(l255, shift=UP * u(6)), FadeIn(cnt, shift=UP * u(6)), run_time=0.6)

        self.at("pack", -0.1)
        self.play(pop(blocks, 1.06, 0.7), run_time=0.7)

        # ---- 終わり：空に ----
        self.at(self.tl["duration"] - 1.2)
        self.play(FadeOut(Group(blocks, l255, cnt, hexes, holes, bits, *byte_chars)), run_time=0.9)
        self.finish()
