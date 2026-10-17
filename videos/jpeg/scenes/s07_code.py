import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import BLOCK, ZIGZAG, block_coef, codes_of, file_bytes, jpeg  # noqa: E402
from zunda.fx import pop, underline  # noqa: E402
from vlib.jparts import QGrid  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import ORDER, STAGE_COL, StageMap  # noqa: E402

CODE = STAGE_COL["code"]
ZERO = "#4a5060"
SLOT_PITCH, SLOT = 62, 56           # 並べた数字の列（16 個で改行）
LIST_Y0 = 665
GRID_C = px(960, 366)
CARD_W, CARD_H, CARD_DX, CARD_DY, CARD_Y0, CARD_COLS = 330, 88, 340, 94, 175, 3


QGRID_CELL = 66


def minus(v):
    return str(v).replace("-", "−")


def encode_block():
    """主役のブロックを、ファイルのハフマン表でそのまま符号にする。
    DC は、ファイルの並び順で 1 つ前の輝度ブロックとの差。返り値は記号ごとの dict のリスト"""
    s, info, coef, _ = jpeg()
    ht = info["ht"]
    ac, dc = codes_of(*ht[(1, 0)]), codes_of(*ht[(0, 0)])
    H, Wd = coef[0].shape[:2]
    order = [(my * 2 + by, mx * 2 + bx) for my in range(H // 2) for mx in range(Wd // 2)
             for by in range(2) for bx in range(2)]       # 輝度は 2×2 ブロックずつ（MCU）の順
    i = order.index(BLOCK)
    prev = order[i - 1]
    z = [int(v) for v in coef[0][BLOCK]]
    assert z == [int(block_coef()[r, c]) for r, c in ZIGZAG]

    def mag(v):
        t = abs(v).bit_length()
        return t, (format(v if v > 0 else v + (1 << t) - 1, f"0{t}b") if t else "")

    diff = z[0] - int(coef[0][prev][0])
    t, b = mag(diff)
    items = [dict(kind="dc", label=f"差 {minus(diff)}", code=dc[t], mag=b, idx=[0], anchor=0)]
    run = 0
    last = max(k for k in range(1, 64) if z[k])
    for k in range(1, last + 1):
        if z[k] == 0:
            run += 1
            continue
        t, b = mag(z[k])
        items.append(dict(kind="ac", label=f"({run}, {minus(z[k])})", code=ac[run << 4 | t], mag=b,
                          idx=list(range(k - run, k + 1)), anchor=k, run=run))
        run = 0
    items.append(dict(kind="eob", label="EOB", code=ac[0], mag="", idx=list(range(last + 1, 64)), anchor=None))
    bits = "".join(it["code"] + it["mag"] for it in items)

    # ---- 検算：符号を読み戻すと係数に戻る／ファイルの符号の列の中にこのビット列がある ----
    tabs = {k: {v_: s_ for s_, v_ in codes_of(*ht[k]).items()} for k in ((0, 0), (1, 0))}
    pos = 0

    def sym(tab):
        nonlocal pos
        for L in range(1, 17):
            if bits[pos:pos + L] in tab:
                r = tab[bits[pos:pos + L]]
                pos += L
                return r
        raise AssertionError

    def ext(t):
        nonlocal pos
        if t == 0:
            return 0
        v = int(bits[pos:pos + t], 2)
        pos += t
        return v if v >= 1 << (t - 1) else v - (1 << t) + 1

    back = [ext(sym(tabs[(0, 0)])) + int(coef[0][prev][0])]
    while len(back) < 64:
        rs = sym(tabs[(1, 0)])
        if rs == 0:
            back += [0] * (64 - len(back))
            break
        back += [0] * (rs >> 4) + [ext(rs & 15)]
    assert back == z and pos == len(bits)
    a, b_ = info["scan"]
    scan = file_bytes("cat_q80")[a:b_].replace(b"\xff\x00", b"\xff")
    stream = "".join(format(x, "08b") for x in scan)
    assert bits in stream
    return items, bits, z


class S07(PScene):
    def construct(self):
        items, bits, z = encode_block()
        total = len(bits)
        raw_bits = 64 * 8
        assert (total, raw_bits) == (122, 512)  # 台詞の「512ビット」と一致。総ビット数はファイルの符号から
        last = max(k for k in range(64) if z[k])

        # ---- 始まり：S06 の終わり ----
        m = StageMap("strip", active="quant", done=("color", "sub", "block", "dct"))
        q = QGrid(block_coef())
        q.cells.set_z_index(0)
        q.nums.set_z_index(2)
        self.add(m, q)

        self.at("s07_01")
        self.play(Transform(m, m.state("strip", active="code", done=("color", "sub", "block", "dct", "quant"))),
                  run_time=0.8)

        # ---- 8×8 を小さく：下に列を作る場所 ----
        self.at("pack", -0.1)
        self.play(q.animate.move_to(GRID_C), run_time=1.2)

        # ---- ジグザグに読む：線が走り、数字が下に並ぶ ----
        def slot(k):
            return px(960 + (k % 16 - 7.5) * SLOT_PITCH, LIST_Y0 + (k // 16) * SLOT_PITCH)

        toks, starts, cur = [], [], []
        for k, (r, c) in enumerate(ZIGZAG):
            sq = Square(side_length=u(SLOT), stroke_width=1.5, stroke_color="#2a2e38",
                        fill_color="#1d212b", fill_opacity=1)
            num = jp(minus(z[k]), 28, INK if z[k] else ZERO)
            tok = VGroup(sq, num).move_to(slot(k))
            tok.set_z_index(3)
            tok.set_opacity(0)
            toks.append(tok)
            starts.append(q.cell(r, c).get_center())
            cur.append(1.0)
        ends = [t.get_center() for t in toks]
        pts = [q.cell(r, c).get_center() for r, c in ZIGZAG]
        path = VMobject(stroke_color=CODE, stroke_width=3, stroke_opacity=0.85).set_points_as_corners([pts[0], pts[1]])
        path.set_z_index(1)
        head = Dot(radius=u(8), color=CODE).move_to(pts[0]).set_z_index(4)
        for t in (*toks, path, head):
            t.check_ignore = True  # 飛んでいる途中（列に着いてから検査する）
        sc0 = QGRID_CELL / SLOT
        driver = VMobject()

        def walk(_, a):
            x = a * 65                      # 線が着いたあと 2 マスぶん、数字が落ち着くまで
            xs = min(x, 63)
            i = min(int(xs), 62)
            f = xs - i
            tip = pts[i] + (pts[i + 1] - pts[i]) * f
            path.set_points_as_corners([*pts[:i + 1], tip])
            head.move_to(tip)
            for k, t in enumerate(toks):
                if x < k:
                    t.set_opacity(0)
                    continue
                p = min(max((x - k) / 2.0, 0), 1)
                e = p * p * (3 - 2 * p)
                t.set_opacity(1)
                sc = sc0 + (1 - sc0) * e
                t.scale(sc / cur[k])
                cur[k] = sc
                t.move_to(starts[k] + (ends[k] - starts[k]) * e)

        self.at("zig", -0.05)
        self.add(*toks, path, head)
        self.play(UpdateFromAlphaFunc(driver, walk, rate_func=linear), run_time=3.1)
        for t in toks:
            t.check_ignore = False
        segs = [path, head]

        # ---- 0 でない数字は左上に集まる ----
        self.at("S07_04", 0.5)
        nz = [k for k in range(64) if z[k]]
        self.play(LaggedStart(*[pop(toks[k], 1.1, 0.5) for k in nz], lag_ratio=0.07), run_time=2.4)

        # ---- 後ろは 0 の連なり：暗くなる ----
        self.at("tail", -0.1)
        tail = list(range(last + 1, 64))
        self.play(*[toks[k].animate.set_opacity(0.3) for k in tail], run_time=0.8)

        # ---- EOB の札 ----
        self.at("eob", -0.1)
        tag_t = jp("EOB（ここから全部0）", 30, YELLOW)
        tag = VGroup(RoundedRectangle(corner_radius=u(14), width=tag_t.width + u(36), height=u(SLOT),
                                      stroke_width=0, fill_color="#1d212b", fill_opacity=1), tag_t)
        tag.move_to(slot(last + 1) + RIGHT * (tag.width / 2 - u(SLOT / 2)))
        for k in tail:
            toks[k].check_ignore = True  # 縮んで消える途中
        self.play(*[toks[k].animate.move_to(tag.get_left() + RIGHT * u(SLOT / 2)).scale(0.3).set_opacity(0)
                    for k in tail], FadeIn(tag, scale=0.6), run_time=1.0)
        self.remove(*[toks[k] for k in tail])
        self.at("gone", -0.1)
        self.play(pop(tag, 1.2, 0.6), run_time=0.6)

        # ---- 途中の 0 は「0がいくつ続いて、次の数」の組に ----
        self.at("run", -0.1)
        cards = []
        for i, it in enumerate(items):
            c, r = i % CARD_COLS, i // CARD_COLS
            ctr = px(960 + (c - 1) * CARD_DX, CARD_Y0 + r * CARD_DY)
            bg = RoundedRectangle(corner_radius=u(14), width=u(CARD_W), height=u(CARD_H), stroke_width=0,
                                  fill_color="#1d212b", fill_opacity=1).move_to(ctr)
            lab = jp(it["label"], 32, YELLOW if it["kind"] == "eob" else INK).move_to(ctr + UP * u(20))
            cards.append(VGroup(bg, lab))
        anims = []
        for it, cd in zip(items, cards):
            if it["kind"] == "eob":
                src = tag
            else:
                src = toks[it["anchor"]]
            for k in it["idx"]:
                if k != it["anchor"] and it["kind"] != "eob":
                    toks[k].check_ignore = True
                    anims.append(toks[k].animate.move_to(cd).scale(0.3).set_opacity(0))
            src.check_ignore = True
            anims.append(Transform(src, cd))
        self.play(FadeOut(VGroup(q, *segs)), LaggedStart(*anims, lag_ratio=0.03), run_time=2.4)
        for it in items:
            if it["kind"] != "eob":
                for k in it["idx"]:
                    if k != it["anchor"]:
                        self.remove(toks[k])
        srcs = [tag if it["kind"] == "eob" else toks[it["anchor"]] for it in items]
        for s_ in srcs:
            s_.check_ignore = False
        dc_note = jp("DCだけは前のブロックとの差", 28, DIM)
        dc_note.move_to(cards[0][0].get_corner(UL) + UP * u(22), aligned_edge=LEFT)
        dc_note.shift(RIGHT * (dc_note.width / 2 - dc_note.width / 2))
        dc_note.align_to(cards[0][0], LEFT)
        self.play(FadeIn(dc_note, shift=DOWN * u(6)), run_time=0.6)
        ex = [i for i, it in enumerate(items) if it["kind"] == "ac" and it["run"]]
        self.at(29.6)
        self.play(LaggedStart(*[pop(srcs[i], 1.2, 0.6) for i in ex], lag_ratio=0.5), run_time=2.6)

        # ---- ハフマン符号：各組の下に実際のビット列 ----
        self.at("huff", -0.1)
        bit_mobs = []
        for it, cd in zip(items, cards):
            code_t = mono(it["code"], 28, CODE)
            parts = [code_t]
            if it["mag"]:
                parts.append(mono(it["mag"], 28, INK))
            g = VGroup(*parts).arrange(RIGHT, buff=u(6)).move_to(cd[0].get_center() + DOWN * u(20))
            g.set_z_index(5)
            bit_mobs.append(g)
        self.play(LaggedStart(*[FadeIn(g, shift=UP * u(6)) for g in bit_mobs], lag_ratio=0.1), run_time=2.4)

        # ---- よく出る組ほど短い ----
        self.at("bits", -0.1)
        shortest = min(len(it["code"]) for it in items)
        short = [i for i, it in enumerate(items) if len(it["code"]) == shortest]
        uls = [underline(bit_mobs[i][0], YELLOW, buff=4, width=3) for i in short]
        self.play(LaggedStart(*[Create(l) for l in uls], lag_ratio=0.12), run_time=1.6)

        self.at("know", 0.1)
        self.play(LaggedStart(*[pop(bit_mobs[i][0], 1.3, 0.6) for i in short], lag_ratio=0.2), run_time=3.0)

        # ---- 符号がつながって 1 本に ----
        self.at("total", -0.1)
        lines, cur, curw = [], [], 0
        maxw = u(900)
        for g in bit_mobs:
            if cur and curw + g.width > maxw:
                lines.append(cur)
                cur, curw = [], 0
            cur.append(g)
            curw += g.width + u(4)
        lines.append(cur)
        dest = []
        for li, ln in enumerate(lines):
            row = VGroup(*[g.copy() for g in ln]).arrange(RIGHT, buff=u(4))
            row.move_to(px(960, 170 + 54 * li))
            row.align_to(px(960 - 450, 0), LEFT)
            for g, gd in zip(ln, row):
                dest.append((g, gd.get_center()))
        for g in bit_mobs:
            g.check_ignore = True
        self.play(FadeOut(VGroup(*srcs, dc_note, *uls)),
                  *[g.animate.move_to(c) for g, c in dest], run_time=1.6)
        for g in bit_mobs:
            g.check_ignore = False

        # ---- ビット数（実際の値）と、元の 64 バイトとの比較 ----
        self.at(48.1)
        BX0, BW = 520, 880
        y1, y2 = 560, 700
        bar1 = Rectangle(width=u(BW), height=u(80), stroke_width=0, fill_color=DIM, fill_opacity=0.55)
        bar1.move_to(px(BX0, y1), aligned_edge=LEFT)
        bar2 = Rectangle(width=u(BW * total / raw_bits), height=u(80), stroke_width=0, fill_color=CODE,
                         fill_opacity=1).move_to(px(BX0, y2), aligned_edge=LEFT)
        lab1 = jp(f"元は {raw_bits}ビット（{raw_bits // 8}バイト）", 38, INK).move_to(px(BX0, y1 - 64), aligned_edge=LEFT)
        lab2 = jp(f"{total}ビット", 48, CODE).next_to(bar2, RIGHT, buff=u(24))
        self.play(FadeIn(lab1, shift=UP * u(6)), GrowFromEdge(bar1, LEFT), run_time=0.5)
        self.play(GrowFromEdge(bar2, LEFT), FadeIn(lab2, shift=RIGHT * u(10)), run_time=0.5)
        self.at("ratio", -0.1)
        self.play(pop(VGroup(bar2, lab2), 1.12, 0.7), run_time=0.7)

        # ---- 終わり：S08 の始まり（地図が全体表示）----
        self.at(self.tl["duration"] - 1.4)
        self.play(FadeOut(VGroup(*bit_mobs, bar1, bar2, lab1, lab2), shift=UP * u(10)),
                  Transform(m, m.state("full", active=None, done=tuple(ORDER))), run_time=1.3)
        self.finish()
