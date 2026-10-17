import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, fmt, frame_rgba, indices, info, palette, pixels  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

LZW_COL = PURPLE           # 辞書・番号の色
GREEN = "#7ee08a"          # いま見ている並び
SRC = "cat16_nodither"     # 練習用の並びを取る画像
ROW, X0, N = 196, 205, 10  # その 196 行目の 205 列から 10 画素
CELL, STEP, CELL_Y = 92, 100, 300
CHIP_Y = 410
DICT_X, DICT_Y0, DICT_DY = 1486, 214, 46     # 書くほうの辞書（右上）。最初からある行の下に少し間をあける
MINI = 44                                     # 辞書の行の、色の小さなマス
RDICT_X, RDICT_Y0 = 40, 150                               # 読むほうの辞書（左上）


def lzw_encode(seq):
    """書くほう：一番長い並びの番号を書き、その並び＋次の 1 色を新しい番号で辞書へ。
    返り値：[(開始位置, 長さ, 書いた番号, 足した (番号, 並び) または None)]"""
    d = {(v,): v for v in range(256)}
    nxt, steps, i = 258, [], 0
    while i < len(seq):
        n = 1
        while i + n < len(seq) and tuple(seq[i:i + n + 1]) in d:
            n += 1
        code = d[tuple(seq[i:i + n])]
        add = None
        if i + n < len(seq):
            add = (nxt, tuple(seq[i:i + n + 1]))
            d[add[1]] = nxt
            nxt += 1
        steps.append((i, n, code, add))
        i += n
    return steps


def lzw_decode(codes):
    """読むほう：さっき読んだ並び＋いま読んだ並びの最初の 1 色を、次の番号で辞書へ"""
    d = {v: (v,) for v in range(256)}
    nxt, out, prev, adds = 258, [], None, []
    for c in codes:
        cur = d[c]              # この練習の並びでは、まだない番号は出てこない（辞書にないと KeyError）
        if prev is not None:
            d[nxt] = prev + (cur[0],)
            adds.append((nxt, d[nxt]))
            nxt += 1
        else:
            adds.append(None)
        out.extend(cur)
        prev = cur
    return out, adds


def cell(v, rgb):
    light = sum(int(c) for c in rgb) > 380
    bg = Square(u(CELL), stroke_width=0, fill_color=rgb_to_color(np.array(rgb) / 255), fill_opacity=1)
    return VGroup(bg, mono(str(v), 36, BG if light else INK))


def entry_row(code, sq, x, y):
    """辞書の 1 行：紫の番号と、並びの色の小さなマス"""
    minis = VGroup()
    for v, rgb in sq:
        light = sum(int(c) for c in rgb) > 380
        b = Square(u(MINI), stroke_width=0, fill_color=rgb_to_color(np.array(rgb) / 255), fill_opacity=1)
        minis.add(VGroup(b, mono(str(v), 22, BG if light else INK)))
    minis.arrange(RIGHT, buff=u(4))
    lab = mono(str(code), 30, LZW_COL)
    row = VGroup(lab, minis).arrange(RIGHT, buff=u(14))
    row.move_to(px(x, y), aligned_edge=LEFT)
    row.seq = tuple(v for v, _ in sq)
    row.lab, row.minis = lab, minis
    return row


def seq_str(seq):
    return " ".join(str(v) for v in seq)


class S05(PScene):
    def construct(self):
        idx = indices(SRC)
        pal = palette(SRC)
        seq = [int(v) for v in idx[ROW, X0:X0 + N]]
        steps = lzw_encode(seq)
        codes = [s[2] for s in steps]
        out, dadds = lzw_decode(codes)
        assert seq == [15, 14, 12, 14, 12, 12, 14, 14, 12, 12] and codes == [15, 14, 12, 259, 260, 261], (seq, codes)
        assert out == seq
        # 読むほうが足す番号と並びは、書くほうが足したものと同じ（1 つずれて足される）
        assert dadds[1:] == [s[3] for s in steps[:-1]]

        # ---- LZW：考えた 3 人の頭文字 ----
        title = jp("LZW", 120, LZW_COL).move_to(px(960, 270))
        self.at("s05_01", 0.3)
        self.play(FadeIn(title, scale=0.9), run_time=0.8)
        self.at("name", -0.1)
        names = jp("Lempel・Ziv・Welch", 40, INK, t2c={"L": YELLOW, "Z": YELLOW, "W": YELLOW})
        names.next_to(title, DOWN, buff=u(30))
        self.play(FadeIn(names, shift=UP * u(8)), run_time=0.7)

        # ---- 猫の写真の 10 個の点で練習 ----
        self.at("s05_02", -0.1)
        photo = png_mob(pixels(SRC), 240, nearest=True).move_to(px(230, 170))
        self.play(FadeOut(VGroup(title, names), shift=UP * u(20)), FadeIn(photo, shift=RIGHT * u(20)), run_time=0.9)
        self.at("pick", -0.1)
        pw = photo.width / idx.shape[1]
        tl = photo.get_corner(UL)
        mid = tl + RIGHT * pw * (X0 + N / 2) + DOWN * pw * (ROW + 0.5)
        big = Rectangle(width=pw * N + u(16), height=pw + u(16), stroke_color=YELLOW, stroke_width=3).move_to(mid)
        cells = VGroup(*[cell(v, pal[v]) for v in seq])
        for i, c in enumerate(cells):
            c.move_to(px(960 + STEP * (i - (N - 1) / 2), CELL_Y))
        seeds = VGroup(*[Square(pw, stroke_width=0, fill_color=rgb_to_color(pal[v] / 255), fill_opacity=1)
                         .move_to(tl + RIGHT * pw * (X0 + i + 0.5) + DOWN * pw * (ROW + 0.5)) for i, v in enumerate(seq)])
        self.play(Create(big), run_time=0.5)
        self.add(seeds)
        self.play(LaggedStart(*[ReplacementTransform(s, c) for s, c in zip(seeds, cells)], lag_ratio=0.08), run_time=1.6)
        self.remove(*seeds)

        self.at("three", -0.1)
        kinds = sorted(set(seq), reverse=True)
        self.play(LaggedStart(*[AnimationGroup(*[pop(cells[i], 1.15, 0.5) for i in range(N) if seq[i] == v])
                                for v in kinds], lag_ratio=0.5), run_time=1.8)

        # ---- 辞書の欄 ----
        self.at("dict", -0.1)
        head = jp("辞書", 36, LZW_COL).move_to(px(DICT_X, 70), aligned_edge=LEFT)
        hrule = Line(px(DICT_X, 98), px(1886, 98), stroke_width=2, color=LZW_COL)
        self.play(FadeIn(head), Create(hrule), run_time=0.6)
        self.at("base", -0.1)
        base1 = mix("0〜255：1色ずつ", 28, DIM).move_to(px(DICT_X, 124), aligned_edge=LEFT)
        self.play(FadeIn(base1, shift=DOWN * u(6)), run_time=0.6)
        # 256・257 は合図。新しい並びは 258 番から
        self.at("sig", -0.1)
        base2 = mix("256・257：合図", 28, DIM).move_to(px(DICT_X, 160), aligned_edge=LEFT)
        self.play(FadeIn(base2, shift=DOWN * u(6)), run_time=0.6)
        self.at("from258", -0.1)
        slot = DashedLine(px(DICT_X, DICT_Y0 - 22), px(1880, DICT_Y0 - 22), stroke_width=2, color=LZW_COL,
                          dash_length=u(10))
        n258 = mono("258", 30, LZW_COL).move_to(px(DICT_X, DICT_Y0), aligned_edge=LEFT)
        self.play(Create(slot), FadeIn(n258, shift=DOWN * u(6)), run_time=0.7)
        self.wait(0.6)
        self.play(FadeOut(n258), run_time=0.4)
        base = VGroup(base1, base2, slot)

        # ---- 書くときの決まり 2 つ ----
        self.at("rule", -0.1)
        r1 = jp("① 辞書にある一番長い並び → その番号を書く", 32, INK)
        r2 = jp("② その並び ＋ 次の1色 → 新しい番号で辞書へ", 32, INK)
        rules = VGroup(r1, r2).arrange(DOWN, buff=u(18), aligned_edge=LEFT).move_to(px(960, 600))
        self.at("r1", -0.1)
        self.play(FadeIn(r1, shift=UP * u(8)), run_time=0.6)
        self.at("r2", -0.1)
        self.play(FadeIn(r2, shift=UP * u(8)), run_time=0.6)

        # ---- 書いていく ----
        wrows, chips, frames = {}, [], []

        def span(i, n):
            return VGroup(*cells[i:i + n])

        def look(k, rt=0.5):
            i, n, *_ = steps[k]
            f = SurroundingRectangle(span(i, n), color=GREEN, buff=u(4), stroke_width=5)
            self.play(Create(f), r1.animate.set_color(GREEN), run_time=rt)
            frames.append(f)

        def write(k, rt=0.7):
            i, n, code, _ = steps[k]
            sp = span(i, n)
            c = mono(str(code), 40, LZW_COL).move_to(np.array([sp.get_center()[0], px(0, CHIP_Y)[1], 0]))
            br = Line(sp.get_corner(DL) + DOWN * u(10), sp.get_corner(DR) + DOWN * u(10), stroke_width=3, color=LZW_COL)
            fly = sp.copy()
            fly.check_ignore = True
            self.play(ReplacementTransform(fly, c), Create(br), r1.animate.set_color(INK), run_time=rt)
            chips.append(VGroup(c, br))

        def register(k, rt=0.8):
            i, n, code, add = steps[k]
            nc = cells[i + n]
            hl = SurroundingRectangle(nc, color=YELLOW, buff=u(4), stroke_width=5)
            row = entry_row(add[0], [(v, pal[v]) for v in add[1]], DICT_X, DICT_Y0 + DICT_DY * len(wrows))
            src = VGroup(span(i, n), nc).copy()
            src.check_ignore = True
            self.play(Create(hl), r2.animate.set_color(YELLOW), run_time=0.4)
            self.play(ReplacementTransform(src, row), FadeOut(hl), FadeOut(frames[-1]), r2.animate.set_color(INK),
                      run_time=rt)
            wrows[add[0]] = row

        self.at("w1", -0.1)
        look(0)
        self.at("c1", -0.1)
        write(0)
        self.at("d1", -0.1)
        register(0)
        self.at("w2", -0.1)
        look(1, 0.4)
        self.at("c2", -0.1)
        write(1, 0.6)
        self.at("d2", -0.1)
        register(1, 0.7)
        self.at("w3", -0.1)
        look(2, 0.4)
        self.at("c3", -0.1)
        write(2, 0.6)
        self.at("d3", -0.1)
        register(2, 0.7)

        self.at("slow", -0.1)
        self.play(LaggedStart(*[pop(chips[k], 1.2, 0.5) for k in range(3)], lag_ratio=0.3), run_time=1.0)

        # ---- ここから：辞書にある並びが使える ----
        self.at("w4", -0.1)
        look(3)
        self.at("hit", -0.1)
        hit = SurroundingRectangle(wrows[259], color=GREEN, buff=u(6), stroke_width=4)
        self.play(Create(hit), pop(wrows[259], 1.15, 0.6), run_time=0.7)
        self.at("yes", -0.1)
        self.play(Indicate(frames[-1], color=GREEN, scale_factor=1.05), run_time=0.6)
        self.at("c4", -0.1)
        write(3)
        self.play(FadeOut(hit), run_time=0.3)
        self.at("d4", -0.1)
        register(3)
        self.at("w5", -0.1)
        look(4)
        self.at("c5", -0.1)
        write(4)
        self.at("d5", -0.1)
        register(4)
        self.at("w6", -0.1)
        look(5)
        self.at("c6", -0.1)
        write(5)
        self.play(FadeOut(frames[-1]), run_time=0.3)
        self.at("three2", -0.1)
        self.play(pop(chips[5], 1.35, 0.6), run_time=0.6)

        # ---- 10 個 → 6 個 ----
        self.at("tally", -0.1)
        tally = mix(f"{N} 個 → {len(codes)} 個", 48, YELLOW).move_to(px(960, 750))
        self.play(FadeOut(rules), FadeIn(tally, shift=UP * u(8)), run_time=0.7)
        self.at("longer", -0.1)
        self.play(LaggedStart(*[pop(wrows[c], 1.12, 0.5) for c in sorted(wrows)], lag_ratio=0.2), run_time=1.2)

        # ---- LZ77 は「何バイト前」、LZW は「辞書の何番」----
        self.at("lz77", -0.1)
        l77 = mix("LZ77：何バイト前から、何バイト", 36, DIM).move_to(px(960, 600))
        self.play(FadeOut(tally), FadeIn(l77, shift=UP * u(8)), run_time=0.6)
        self.at("lzw", -0.1)
        lzw = mix("LZW：辞書の何番", 44, LZW_COL).move_to(px(960, 680))
        self.play(FadeIn(lzw, shift=UP * u(8)), run_time=0.6)
        self.at("get", -0.1)
        ul = underline(lzw, LZW_COL)
        self.play(Create(ul), run_time=0.5)

        # ---- 辞書はファイルに入れない。書くのは 6 個の番号だけ ----
        self.at("s05_r", -0.1)
        wdict = VGroup(head, hrule, base, *wrows.values())
        self.play(FadeOut(VGroup(l77, lzw, ul)), run_time=0.6)
        self.at("nofile", -0.1)
        nof = jp("ファイルには入れない", 28, CORAL).move_to(px(DICT_X + 96, 72), aligned_edge=LEFT)   # 「辞書」の見出しの横
        self.play(wdict.animate.set_opacity(0.3), FadeIn(nof, shift=UP * u(6)), FadeOut(Group(photo, big)), run_time=0.8)
        self.at("codes", -0.1)
        line = VGroup(*[mono(str(c), 48, LZW_COL) for c in codes]).arrange(RIGHT, buff=u(64)).move_to(px(960, 450))
        self.play(*[ReplacementTransform(ch[0], t) for ch, t in zip(chips, line)], *[FadeOut(ch[1]) for ch in chips],
                  cells.animate.set_opacity(0), run_time=1.0)
        chips = list(line)

        self.at("huh", -0.1)
        self.play(Shake(chips[3], 10), chips[3].animate.set_color(YELLOW), run_time=0.7)
        self.play(chips[3].animate.set_color(LZW_COL), run_time=0.3)

        # ---- 読むほうの決まり：式の形で、毎回ここに当てはめる ----
        self.at("rrule", -0.1)
        rhead = jp("読むほうの辞書", 32, LZW_COL).move_to(px(RDICT_X, 70), aligned_edge=LEFT)
        rline = Line(px(RDICT_X, 98), px(420, 98), stroke_width=2, color=LZW_COL)
        FY, LY = 615, 690                       # 式の段と、その下のラベルの段
        slotA = Rectangle(width=u(2 * 78 + 24), height=u(96), stroke_color=GREEN, stroke_width=4).move_to(px(700, FY))
        plus = jp("＋", 48, DIM).move_to(px(840, FY))
        slotB = Rectangle(width=u(78 + 24), height=u(96), stroke_color=YELLOW, stroke_width=4).move_to(px(960, FY))
        arrow = jp("→", 48, DIM).move_to(px(1075, FY))
        slotC = Rectangle(width=u(150), height=u(96), stroke_color=LZW_COL, stroke_width=4).move_to(px(1220, FY))
        labA = jp("さっき読んだ並び", 26, GREEN).move_to(px(700, LY))
        labB = jp("いまの最初の1色", 26, YELLOW).move_to(px(960, LY))
        labC = jp("次の番号", 26, LZW_COL).move_to(px(1220, LY))
        self.play(FadeIn(rhead), Create(rline), run_time=0.6)
        self.at("rp", -0.1)
        self.play(Create(slotA), FadeIn(labA, shift=UP * u(6)), run_time=0.6)
        self.at("rh", -0.1)
        self.play(FadeIn(plus), Create(slotB), FadeIn(labB, shift=UP * u(6)), run_time=0.6)
        self.play(FadeIn(arrow), Create(slotC), FadeIn(labC, shift=UP * u(6)), run_time=0.6)

        # ---- 読んでいく ----
        rrows = {}
        pos = [s_[0] for s_ in steps]
        lens = [s_[1] for s_ in steps]
        pointer = Triangle(fill_color=YELLOW, fill_opacity=1, stroke_width=0).scale(u(14)).rotate(PI)
        pointer.next_to(chips[0], UP, buff=u(14))

        def read_lookup(k, rt=0.6):
            """k 番目の番号を指す。辞書にある番号なら、その行を光らせる"""
            anims = [pointer.animate.next_to(chips[k], UP, buff=u(14)), chips[k].animate.set_color(YELLOW)]
            if k == 0:
                anims = [FadeIn(pointer), chips[k].animate.set_color(YELLOW)]
            fr_ = None
            if codes[k] in rrows:
                fr_ = SurroundingRectangle(rrows[codes[k]], color=GREEN, buff=u(6), stroke_width=4)
                anims.append(Create(fr_))
            self.play(*anims, run_time=rt)
            return fr_

        def read_out(k, fr_=None, rt=0.8):
            """番号の中身（1 色、または辞書の並び）が、上の帯の正しい場所に戻る"""
            sp = span(pos[k], lens[k])
            src = (rrows[codes[k]].minis if codes[k] in rrows else chips[k]).copy()
            src.check_ignore = True
            target = sp.copy().set_opacity(1)
            target.check_ignore = True   # 戻ってくる途中の写し（着いたら本物のマスに置き換える）
            anims = [ReplacementTransform(src, target), chips[k].animate.set_color(LZW_COL)]
            if fr_ is not None:
                anims.append(FadeOut(fr_))
            self.play(*anims, run_time=rt)
            self.remove(target)
            sp.set_opacity(1)

        def radd(k, rt=0.8, fast=1.0):
            """さっき読んだ並び（緑）＋ いまの最初の 1 色（黄）→ 次の番号。式に当てはめてから辞書へ"""
            code, sq = dadds[k]
            a = span(pos[k - 1], lens[k - 1]).copy()
            b = cells[pos[k]].copy()
            a.check_ignore = b.check_ignore = True
            a_t = a.copy().scale(78 / CELL).arrange(RIGHT, buff=u(6)).move_to(slotA)
            b_t = b.copy().scale(78 / CELL).move_to(slotB)
            num = mono(str(code), 44, LZW_COL).move_to(slotC)
            num.check_ignore = True      # このあと辞書の行になる
            self.play(Transform(a, a_t), Transform(b, b_t), run_time=0.7 * fast)
            self.play(FadeIn(num, scale=1.3), run_time=0.4 * fast)
            self.wait(1.0 * fast)                # 式が埋まった状態を見せる
            row = entry_row(code, [(v, pal[v]) for v in sq], RDICT_X, RDICT_Y0 + DICT_DY * len(rrows))
            self.play(ReplacementTransform(VGroup(num, a, b), row), run_time=rt)
            rrows[code] = row

        self.at("d_1", -0.1)
        read_lookup(0, 0.5)
        read_out(0, rt=0.6)
        self.at("d_2", -0.1)
        read_lookup(1, 0.5)
        read_out(1, rt=0.6)
        self.at("dd2", -0.3)
        radd(1)
        self.at("d_3", -0.1)
        read_lookup(2, 0.5)
        read_out(2, rt=0.6)
        self.at("dd3", -0.3)
        radd(2)
        self.at("d_4", -0.1)
        f259 = read_lookup(3, 0.7)
        self.at("dd4", -0.1)
        read_out(3, f259, 0.9)
        self.at("dd5", -0.3)
        radd(3)

        self.at("same", -0.1)
        self.play(*[pop(rrows[c], 1.1, 0.5) for c in rrows],
                  *[wrows[c].animate.set_opacity(1) for c in rrows], run_time=0.7)

        self.at("dfast", -0.8)
        read_out(4, read_lookup(4, 0.3), 0.35)
        radd(4, 0.4, fast=0.4)
        read_out(5, read_lookup(5, 0.3), 0.35)
        self.at("dall", 0.2)
        unused = [c for c in wrows if c not in rrows]   # 最後に書いた並びの後ろには色がないので、使われない番号
        self.play(wdict.animate.set_opacity(1), FadeOut(nof), FadeOut(pointer), run_time=0.6)
        self.play(*[wrows[c].animate.set_opacity(0.3) for c in unused],
                  *[r.lab.animate.set_color(GREEN) for r in rrows.values()],
                  *[wrows[c].lab.animate.set_color(GREEN) for c in rrows], run_time=0.6)
        assert all(rrows[c].seq == wrows[c].seq for c in rrows)
        assert [int(v) for v in seq] == [int(x) for x in out]

        self.at("get3", -0.1)
        self.play(*[pop(r, 1.1, 0.5) for r in rrows.values()], run_time=0.6)
        qrule = VGroup(slotA, plus, slotB, arrow, slotC, labA, labB, labC)

        # ---- 本物のスタンプでも ----
        self.at("real", -0.1)
        self.play(FadeOut(VGroup(cells, *chips, wdict, rhead, rline, *rrows.values(), qrule)), run_time=0.8)
        inf = info()
        fr0 = inf["frames"][0]
        stamp = png_mob(frame_rgba(), 380, nearest=True).move_to(px(620, 300))
        self.play(FadeIn(stamp, shift=UP * u(10)), run_time=0.8)
        W_, H_ = inf["width"], inf["height"]
        npix, ncode = W_ * H_, fr0["lzw"]["codes"]
        assert (npix, ncode) == (65160, 12495)
        self.at("pix", -0.1)
        p1 = mix(f"{W_} × {H_} ＝ {fmt(npix)} 画素", 44, CYAN).move_to(px(1150, 250))
        self.play(FadeIn(p1, shift=UP * u(8)), run_time=0.7)
        self.at("codes2", -0.1)
        p2 = mix(f"番号 {fmt(ncode)} 個", 48, LZW_COL).move_to(px(1150, 350))
        self.play(FadeIn(p2, shift=UP * u(8)), run_time=0.7)

        # ---- つぶつぶの写真は大きくなった（S04 の 2 つのファイル）----
        self.at("dither2", -0.1)
        a, b = len(file_bytes("cat_nodither")), len(file_bytes("cat_dither"))
        assert b > a
        sizes = VGroup(mix(f"ディザなし  {fmt(a)} バイト", 36, INK), mix(f"ディザあり  {fmt(b)} バイト", 36, CORAL))
        sizes.arrange(DOWN, buff=u(20), aligned_edge=LEFT).move_to(px(960, 640))
        self.play(FadeIn(sizes, shift=UP * u(8)), run_time=0.7)

        # ---- 終わり：空に ----
        self.at(self.tl["duration"] - 1.2)
        self.play(FadeOut(Group(stamp, p1, p2, sizes)), run_time=0.9)
        self.finish()
