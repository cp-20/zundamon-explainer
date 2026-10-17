import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from pnganalyze import analyze, build_decoder  # noqa: E402
from vlib.data import path  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from vlib.pmap import STAGE_COL, PipelineMap  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

HUFF = STAGE_COL["huff"]
NODE_R = 44
LEAF_Y = 760
DY = 98
PANEL = "#262b36"
GREY = "#3a4150"


def real_block():
    info, raw, blocks = analyze(str(path("zundamon")))
    return blocks[0]


def sym_col(s):
    return {0: YELLOW, 2: BLUE, 255: CORAL}.get(s, CYAN)


class S07(PScene):
    def construct(self):
        blk = real_block()
        toks, ll = blk["tokens"], blk["lit_lengths"]
        # ---- 実データ ----
        cnt = Counter(t for t in toks if isinstance(t, int))
        total = sum(cnt.values())  # バイトの値（リテラル）だけの合計。コピーはこのシーンでは扱わない
        order = [s for s, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))]
        top = order[:8]
        top6 = order[:6]
        assert top6 == [0, 1, 255, 254, 2, 253] and ll[0] == 2
        other_cnt = total - sum(cnt[s] for s in top6)
        # 実際の符号（正準ハフマン）：値0の符号
        dec = build_decoder(ll)
        code0 = [format(c, f"0{l}b") for (l, c), s in dec.items() if s == 0][0]
        assert len(code0) == 2 == ll[0]

        # ---- 記号の並び（実際のブロックの途中）----
        st = next(i for i in range(3000, len(toks) - 9)
                  if sum(1 for x in toks[i:i + 9] if not isinstance(x, int)) == 1
                  and len({x for x in toks[i:i + 9] if isinstance(x, int)}) >= 3)
        window = toks[st:st + 9]

        m = PipelineMap(done=("filter", "lz77"))
        self.add(m)
        self.at("title")
        self.play(Transform(m, m.state("strip", active="huff")), run_time=1.2)

        # ---- S07_02：記号の並び ----
        self.at("symbols")
        CW, CY = 96, 400
        chips = VGroup()
        for k, t in enumerate(window):
            if isinstance(t, int):
                bx = RoundedRectangle(corner_radius=u(10), width=u(CW - 8), height=u(76), stroke_width=0,
                                      fill_color=PANEL, fill_opacity=1)
                lab = mono(str(t), 38, INK)
            else:
                bx = RoundedRectangle(corner_radius=u(10), width=u(CW + 70), height=u(76), stroke_width=0,
                                      fill_color=CYAN, fill_opacity=0.25)
                lab = jp(f"({t[0]},{t[1]})", 28, CYAN)
            lab.move_to(bx)
            chips.add(VGroup(bx, lab))
        chips.arrange(RIGHT, buff=u(8)).move_to(px(960, CY))
        self.play(LaggedStart(*[FadeIn(c, shift=UP * u(10)) for c in chips], lag_ratio=0.08), run_time=1.2)

        self.at("only")
        copy_chips = [c for c, t in zip(chips, window) if not isinstance(t, int)]
        self.play(*[c.animate.set_opacity(0.0) for c in copy_chips], run_time=0.8)
        self.at("S07_04", 0.2)
        self.play(pop(chips, 1.05), run_time=0.7)
        self.at("fixed")
        strips = VGroup()
        for c, t in zip(chips, window):
            if isinstance(t, int):
                cells = VGroup(*[Rectangle(width=u(10), height=u(28), stroke_width=0, fill_color=DIM,
                                           fill_opacity=0.8) for _ in range(8)]).arrange(RIGHT, buff=u(1.5))
                cells.next_to(c, DOWN, buff=u(14))
                strips.add(cells)
        lbl8 = mix("どの値も 8ビット", 34, DIM).move_to(px(960, CY + 140))
        self.play(LaggedStart(*[FadeIn(s, shift=DOWN * u(8)) for s in strips], lag_ratio=0.07),
                  FadeIn(lbl8), run_time=1.2)

        # ---- 棒グラフ：記号ごとの出現回数 ----
        self.at("freq")
        BX = [960 + (i - 3.5) * 112 for i in range(8)]
        BASE, HMAX, BW = 790, 480, 72
        vals = [cnt[s] for s in top]
        names = [str(s) for s in top]
        axis = Line(px(BX[0] - 60, BASE), px(BX[-1] + 60, BASE), stroke_width=3, color=DIM)
        bars, cnts, labs = VGroup(), VGroup(), VGroup()
        for i, v in enumerate(vals):
            col = YELLOW if i == 0 else INK
            r = Rectangle(width=u(BW), height=u(HMAX * v / vals[0]), stroke_width=0, fill_color=col,
                          fill_opacity=0.9).move_to(px(BX[i], BASE), aligned_edge=DOWN)
            bars.add(r)
            cnts.add(jp(str(v), 28, DIM).next_to(r, UP, buff=u(8)))
            labs.add(jp(names[i], 34, col).move_to(px(BX[i], BASE + 36)))
        self.play(FadeOut(chips, shift=UP * u(20)), FadeOut(strips, shift=UP * u(20)), FadeOut(lbl8),
                  Create(axis), FadeIn(labs), run_time=0.9)
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in bars], lag_ratio=0.09),
                  LaggedStart(*[FadeIn(c, shift=UP * u(6)) for c in cnts], lag_ratio=0.09), run_time=1.6)

        self.at("wow")
        self.play(pop(VGroup(bars[0], cnts[0]), 1.08), cnts[0].animate.set_color(YELLOW), run_time=0.7)
        self.at("runner")
        self.play(*[bars[i].animate.set_fill(YELLOW, 0.9) for i in (1, 2)],
                  *[pop(VGroup(bars[i], cnts[i]), 1.25) for i in (1, 2)],
                  *[labs[i].animate.set_color(YELLOW) for i in (1, 2)], run_time=0.8)

        self.at("S07_08", 0.1)
        self.play(pop(VGroup(bars[2], cnts[2], labs[2]), 1.12), run_time=0.6)
        self.at("neg")
        neg = jp("= −1", 34, CORAL).next_to(cnts[2], UP, buff=u(14))
        self.play(FadeIn(neg, shift=DOWN * u(8)), labs[2].animate.set_color(CORAL), bars[2].animate.set_fill(CORAL, 0.9),
                  run_time=0.6)
        self.at("short")
        self.play(FadeOut(neg), labs[2].animate.set_color(YELLOW), bars[2].animate.set_fill(YELLOW, 0.9),
                  run_time=0.4)
        sh = jp("短いビット", 34, YELLOW).move_to(px(BX[0] - 10, BASE + 100), aligned_edge=LEFT)
        lg = jp("長いビット", 34, DIM).move_to(px(BX[-1] + 30, BASE + 100), aligned_edge=RIGHT)
        arrow = Arrow(sh.get_right() + RIGHT * u(16), lg.get_left() + LEFT * u(16), buff=0, stroke_width=4,
                      color=DIM, max_tip_length_to_length_ratio=0.1)
        self.play(FadeIn(sh, shift=UP * u(6)), run_time=0.6)
        self.at("long")
        self.play(Create(arrow), FadeIn(lg, shift=UP * u(6)), run_time=0.8)

        # ---- 上位6つと「その他」----
        self.at("simple")
        self.play(FadeOut(VGroup(sh, lg, arrow)), run_time=0.4)
        ul_top = underline(VGroup(labs[0], labs[5]), HUFF, buff=14)
        ul_oth = underline(VGroup(labs[6], labs[7]), DIM, buff=14)
        t_top = jp("上位6つ", 32, HUFF).next_to(ul_top, DOWN, buff=u(14))
        t_oth = jp("その他", 32, DIM).next_to(ul_oth, DOWN, buff=u(14))
        self.play(Create(ul_top), Create(ul_oth), FadeIn(t_top), FadeIn(t_oth),
                  *[bars[i].animate.set_fill(DIM, 0.5) for i in (6, 7)], run_time=0.9)

        # ---- 木：葉になる ----
        self.at("tree")
        leaf_order = [0, 253, 2, 1, 254, 255, "other"]
        LX = {s: 960 + (i - 3) * 145 for i, s in enumerate(leaf_order)}
        bar_idx = {s: i for i, s in enumerate(top)}

        def mknode(circ_col, text, stroke=None):
            c = Circle(radius=u(NODE_R), stroke_width=0 if stroke is None else 3, fill_color=circ_col,
                       fill_opacity=1)
            if stroke:
                c.set_stroke(stroke)
            c.set_z_index(2)
            return c

        nodes = {}  # key -> dict(c=circle, pos, count, kids, grp)

        def leaf(s):
            col = YELLOW if s == 0 else GREY
            c = mknode(col, None)
            c.move_to(px(LX[s], LEAF_Y))
            lab = (jp(str(s), 28, BG if s == 0 else INK) if s != "other" else jp("他", 30, INK))
            lab.set_z_index(3)
            lab.move_to(c)
            n = cnt[s] if s != "other" else other_cnt
            ct = jp(str(n), 28, DIM).move_to(px(LX[s], LEAF_Y + NODE_R + 24))
            nodes[s] = dict(c=c, lab=lab, ct=ct, pos=px(LX[s], LEAF_Y), count=n, kids=None, sym=s)

        for s in leaf_order:
            leaf(s)
        # 棒 → 葉
        anims, fades = [], []
        for s in top6:
            i = bar_idx[s]
            nd = nodes[s]
            anims += [Transform(bars[i], nd["c"]), labs[i].animate.move_to(nd["lab"]).set_color(
                BG if s == 0 else INK), cnts[i].animate.move_to(nd["ct"]).set_color(DIM)]
        oc = nodes["other"]
        for i in (6, 7):
            fades += [bars[i].animate.scale(0.3).move_to(oc["c"]).set_opacity(0),
                      labs[i].animate.scale(0.3).move_to(oc["c"]).set_opacity(0),
                      cnts[i].animate.move_to(oc["c"]).set_opacity(0)]
        self.play(*anims, *fades, FadeOut(VGroup(axis, ul_top, ul_oth, t_top, t_oth)),
                  FadeIn(oc["c"], scale=0.4), FadeIn(oc["lab"], scale=0.4), FadeIn(oc["ct"], shift=UP * u(6)),
                  run_time=1.3)
        # ここから棒の代わりに葉のオブジェクトを使う
        for s in top6:
            i = bar_idx[s]
            nodes[s]["c"], nodes[s]["lab"], nodes[s]["ct"] = bars[i], labs[i], cnts[i]
        self.remove(*[bars[i] for i in (6, 7)], *[labs[i] for i in (6, 7)], *[cnts[i] for i in (6, 7)])
        for s in top6:
            nodes[s]["c"].set_z_index(2)
            nodes[s]["lab"].set_z_index(3)
        name_oth = jp("その他", 28, DIM).move_to(px(LX["other"] + 4, LEAF_Y - 74))
        self.play(FadeIn(name_oth), run_time=0.4)

        # ---- 木：くっつける ----
        edges = {}

        def merge(a, b, key, cue):
            A, B = nodes[a], nodes[b]
            pos = np.array([(A["pos"][0] + B["pos"][0]) / 2, max(A["pos"][1], B["pos"][1]) + u(DY), 0])
            total_ = A["count"] + B["count"]
            c = Circle(radius=u(NODE_R), stroke_width=3, stroke_color=HUFF, fill_color=PANEL, fill_opacity=1)
            c.set_z_index(2)
            c.move_to(pos)
            lab = jp(str(total_), 26, INK).move_to(pos)
            lab.set_z_index(3)
            eA = Line(pos, A["pos"], stroke_width=4, color=DIM)
            eB = Line(pos, B["pos"], stroke_width=4, color=DIM)
            eA.set_z_index(0); eB.set_z_index(0)
            edges[a], edges[b] = eA, eB
            nodes[key] = dict(c=c, lab=lab, pos=pos, count=total_, kids=(a, b), sym=None)
            return c, lab, eA, eB

        def do_merge(a, b, key, cue, rt=0.85):
            self.at(cue)
            c, lab, eA, eB = merge(a, b, key, cue)
            fl = []
            for k in (a, b):
                src = nodes[k]["lab"] if nodes[k]["kids"] else nodes[k]["ct"]
                g = src.copy().set_color(YELLOW)
                g.check_ignore = True
                self.add(g)
                fl.append(g)
            self.play(Create(eA), Create(eB), FadeIn(c, scale=0.5),
                      nodes[a]["c"].animate.set_stroke(HUFF, 4), nodes[b]["c"].animate.set_stroke(HUFF, 4),
                      *[g.animate(path_arc=PI / 3 if j else -PI / 3).move_to(lab).scale(0.9) for j, g in enumerate(fl)],
                      run_time=rt * 0.7)
            self.remove(*fl)
            lab.set_color(YELLOW)
            self.play(FadeIn(lab, scale=1.4), run_time=rt * 0.3)
            self.play(lab.animate.set_color(INK), run_time=0.01)

        do_merge(253, 2, "m1", "m1")
        do_merge(254, 255, "m2", "m2")
        do_merge("m1", 1, "m3", "m3")
        do_merge("m3", "m2", "m4", "m4")
        do_merge(0, "m4", "m5", "m5")
        do_merge("m5", "other", "m6", "m6")
        root = "m6"
        assert nodes[root]["count"] == total
        self.play(pop(nodes[root]["c"], 1.15), run_time=0.5)

        # ---- 符号を読む ----
        def children(k):
            return nodes[k]["kids"]

        codes = {}

        def walk(k, pre):
            if nodes[k]["kids"] is None:
                codes[k] = pre
            else:
                walk(nodes[k]["kids"][0], pre + "0")
                walk(nodes[k]["kids"][1], pre + "1")

        walk(root, "")
        assert codes[0] == code0, (codes[0], code0)
        ebl = {}
        elab = VGroup()
        for p_, kids in [(k, nodes[k]["kids"]) for k in nodes if nodes[k]["kids"]]:
            for bit, ck in zip("01", kids):
                a_, b_ = nodes[p_]["pos"], nodes[ck]["pos"]
                mid = (a_ + b_) / 2
                off = LEFT if bit == "0" else RIGHT
                t = mono(bit, 36, CYAN if bit == "0" else CORAL)
                # 辺の近くでノードに重ならない位置（親から 45% の所）
                pt = a_ + (b_ - a_) * 0.45
                t.move_to(pt + off * u(22))
                ebl[ck] = t
                elab.add(t)
        self.at("codes")
        self.play(LaggedStart(*[FadeIn(t, scale=0.6) for t in elab], lag_ratio=0.05), run_time=1.2)
        code_txt = {}
        char_of = {}
        for s in leaf_order:
            # 根から葉までの辺ラベルを順に集める
            chain, k = [], s
            parent = {c: p for p, nn in nodes.items() if nn["kids"] for c in nn["kids"]}
            while k != root:
                chain.append(ebl[k]); k = parent[k]
            chain.reverse()
            tx = VGroup(*[mono(ch, 36, sym_col(s) if s != "other" else INK) for ch in codes[s]])
            tx.arrange(RIGHT, buff=u(2)).move_to(px(LX[s], LEAF_Y + NODE_R + 78))
            code_txt[s] = tx
            char_of[s] = chain
        # 値0の符号だけ先に、根から葉へ
        trace = Dot(radius=u(10), color=YELLOW).move_to(nodes[root]["pos"])
        trace.set_z_index(5)
        self.add(trace)
        pth = []
        k = 0
        while k != root:
            pth.append(k); k = parent[k]
        pth.append(root)
        pth.reverse()
        pts = [nodes[k]["pos"] for k in pth]
        for j in range(1, len(pts)):
            self.play(trace.animate.move_to(pts[j]), edges[pth[j]].animate.set_color(YELLOW), run_time=0.4)
        self.play(*[TransformFromCopy(char_of[0][i], code_txt[0][i]) for i in range(2)], run_time=0.6)
        self.play(FadeOut(trace), run_time=0.2)
        rest = [s for s in leaf_order if s != 0]
        self.play(LaggedStart(*[AnimationGroup(*[TransformFromCopy(char_of[s][i], code_txt[s][i])
                                                 for i in range(len(codes[s]))]) for s in rest],
                              lag_ratio=0.12), *[e.animate.set_color(DIM) for e in edges.values()], run_time=1.6)

        self.at("z0")
        self.play(pop(code_txt[0], 1.4), run_time=0.7)
        self.at("z253")
        self.play(pop(code_txt[253], 1.3), run_time=0.7)

        self.at("S07_16", 0.1)
        self.play(Shake(code_txt[253], 8), run_time=0.6)
        # ---- なぜ短くなるか ----
        self.at("why")
        pop_set = [0, "other"]
        self.play(*[pop(VGroup(nodes[s]["c"], nodes[s]["lab"], code_txt[s]), 1.2) for s in pop_set], run_time=0.8)
        self.play(*[pop(VGroup(nodes[s]["c"], nodes[s]["lab"], code_txt[s]), 1.2) for s in (253, 2)], run_time=0.8)

        # ---- どこで区切る？ ----
        self.at("boundary")
        # 復号する実データ（最初のブロックの途中にある並び）
        dec_syms = [0, 2, 0, 0, 0, 255, 0]
        j0 = next(i for i in range(len(toks) - 7) if toks[i:i + 7] == dec_syms)
        bits = "".join(codes[s] for s in dec_syms)
        BXs = [960 + (i - (len(bits) - 1) / 2) * 52 for i in range(len(bits))]
        boxes = VGroup()
        for i, b in enumerate(bits):
            sq = Square(u(44), stroke_width=0, fill_color=PANEL, fill_opacity=1).move_to(px(BXs[i], 150))
            t = mono(b, 34, INK).move_to(sq)
            boxes.add(VGroup(sq, t))
        q = jp("どこで区切る？", 34, CORAL).move_to(px(960, 215))
        self.play(LaggedStart(*[FadeIn(b, shift=DOWN * u(8)) for b in boxes], lag_ratio=0.03), FadeIn(q), run_time=1.0)

        self.at("prefix")
        self.play(*[pop(code_txt[s], 1.25) for s in leaf_order], FadeOut(q), run_time=0.8)

        self.at("decode")
        dot = Dot(radius=u(11), color=YELLOW).move_to(nodes[root]["pos"])
        dot.set_z_index(5)
        self.play(FadeIn(dot, scale=2), *[e.animate.set_color(DIM) for e in edges.values()], run_time=0.5)

        # 復号：1ビットずつ木をたどる
        def decode_step(syms_range, step=0.32, hold=0.5):
            pos_bit = start_bit[0]
            for si in syms_range:
                s = dec_syms[si]
                k = root
                nb = len(codes[s])
                for bi in range(nb):
                    b = bits[pos_bit + bi]
                    k = nodes[k]["kids"][int(b)]
                    self.play(dot.animate.move_to(nodes[k]["pos"]),
                              boxes[pos_bit + bi][0].animate.set_fill(sym_col(s), 1),
                              boxes[pos_bit + bi][1].animate.set_color(BG),
                              edges[k].animate.set_color(YELLOW), run_time=step)
                grp = VGroup(*boxes[pos_bit:pos_bit + nb])
                lbl = jp(str(s), 34, sym_col(s)).move_to(px((BXs[pos_bit] + BXs[pos_bit + nb - 1]) / 2, 205))
                self.play(pop(VGroup(nodes[s]["c"], nodes[s]["lab"]), 1.25), FadeIn(lbl, shift=DOWN * u(6)),
                          grp.animate.shift(RIGHT * 0),  # 区切りを示すため一瞬だけ強調
                          run_time=hold * 0.6)
                self.play(dot.animate.move_to(nodes[root]["pos"]),
                          *[e.animate.set_color(DIM) for e in edges.values()], run_time=hold * 0.4)
                pos_bit += nb
            start_bit[0] = pos_bit

        start_bit = [0]
        self.at("d1")
        decode_step([0], step=0.5, hold=0.9)
        self.at("d2")
        decode_step([1], step=0.38, hold=0.9)
        self.at("d3")
        decode_step([2, 3, 4, 5, 6], step=0.22, hold=0.5)

        self.at("zok")
        self.play(pop(boxes, 1.04), run_time=0.6)

        # ---- 値0は2ビット ----
        self.at("s07_17", 0.1)
        zbox = lambda b, col: VGroup(Square(u(96), stroke_width=0, fill_color=col, fill_opacity=1),
                                     mono(b, 56, BG if col == YELLOW else INK))
        eight = VGroup(*[zbox("0", PANEL) for _ in range(8)]).arrange(RIGHT, buff=u(12))
        for g in eight:
            g[1].move_to(g[0])
        eight.move_to(px(960, 520))
        cap = mix("値0 を、ふつうに書くと", 44, DIM).move_to(px(960, 360))
        others_ = Group(*[mm for mm in self.mobjects if mm is not m])
        self.play(FadeOut(others_), run_time=0.6)
        self.remove(*[mm for mm in self.mobjects if mm is not m])
        self.play(FadeIn(cap), LaggedStart(*[FadeIn(g, scale=0.7) for g in eight], lag_ratio=0.06), run_time=1.0)

        self.at("zero")
        self.play(pop(eight, 1.06), run_time=0.7)
        self.at("bits")
        keep = [0, 1]
        shrink = [i for i in range(8) if i not in keep]
        cap2 = jp("このブロックでは", 44, YELLOW).move_to(px(960, 360))
        two = VGroup(*[eight[i] for i in keep])
        self.play(*[eight[i].animate.scale(0.2).set_opacity(0).move_to(eight[1].get_center() + RIGHT * u(40))
                    for i in shrink],
                  retext(cap, cap2),
                  *[eight[i][0].animate.set_fill(YELLOW) for i in keep],
                  *[eight[i][1].animate.set_color(BG) for i in keep],
                  run_time=0.7)
        self.play(two.animate.arrange(RIGHT, buff=u(12)).move_to(px(960, 520)), run_time=0.4)

        self.at("z8")
        self.play(pop(two, 1.25), run_time=0.7)

        self.at("S07_24", 0.1)
        many = mix(f"{cnt[0]} 回", 48, YELLOW).move_to(px(960, 680))
        self.play(FadeIn(many, shift=UP * u(10)), run_time=0.6)
        self.play(pop(many, 1.2), run_time=0.6)
        self.at("S07_24.end", -0.6)
        self.play(FadeOut(VGroup(two, cap, many)), run_time=0.4)
        self.play(Transform(m, m.state("full", active=None, done=("filter", "lz77", "huff"))), run_time=1.2)
        self.finish()
