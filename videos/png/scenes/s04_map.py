import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import json  # noqa: E402

from vlib.data import ROOT, fmt, info, pixels  # noqa: E402
from zunda.fx import Shake, retext, underline  # noqa: E402
from zunda.fx import pop  # noqa: E402
from vlib.pmap import STAGE_COL, PipelineMap  # noqa: E402
from zunda.scene import *  # noqa: E402,F403


def glow(m, col, a=0.45):
    """段の札を一瞬だけ濃くして戻す"""
    pill = m[0]
    return pill.animate(rate_func=there_and_back, run_time=0.7).set_fill(col, a + 0.35)


CELL = 76
PITCH = 84


def cell(color="#262b36", w=CELL):
    return Rectangle(width=u(w), height=u(CELL), stroke_width=0, fill_color=color, fill_opacity=1)


def num(v, size=38, color=INK):
    return mono(str(v), size, color)


def boxes(vals, cx, y, size=38):
    cs = VGroup(*[cell().move_to(px(cx + (i - (len(vals) - 1) / 2) * PITCH, y)) for i in range(len(vals))])
    ns = VGroup(*[num(v, size).move_to(c) for v, c in zip(vals, cs)])
    return cs, ns


def fold(group, pill):
    """プレビューを段の札に吸い込ませる"""
    return group.animate(rate_func=smooth).scale(0.12).move_to(pill.get_center()).set_opacity(0)


class S04(PScene):
    def construct(self):
        z = info("zundamon")
        assert fmt(z["pixel_bytes"]) == "6,898,832" and fmt(z["idat_bytes"]) == "332,957"

        # 最後にこの 1 個の PipelineMap を画面に置く。途中は部品を 1 つずつ出していく
        m = PipelineMap()
        P, A, S = m.parts, m.arrows, m.sizes
        shown = []

        def reveal(*mobs, **kw):
            shown.extend(mobs)
            return [FadeIn(x, scale=0.92) if isinstance(x, VGroup) and x in P.values() else FadeIn(x)
                    for x in mobs]

        # ---- S04_01：画素 → IDAT ----
        self.at("pixels", -0.1)
        self.play(*reveal(P["pixels"], S[0]), run_time=0.7)
        self.at("idat", -0.1)
        self.play(*reveal(P["idat"]), run_time=0.7)

        Y = 600
        # ---- S04_02：フィルタ（実データの 1 行） ----
        self.at("filter", -0.2)
        shown.append(A[0])
        self.play(*reveal(P["filter"]), GrowArrow(A[0]), run_time=0.8)
        self.play(pop(P["filter"], 1.12, 0.6))
        g = pixels("gradient").astype(int)
        R = [int(v) for v in g[0, :8, 0]]
        D = [R[0]] + [R[i] - R[i - 1] for i in range(1, 8)]
        fc, fn = boxes(R, 800, Y)
        lbl = jp("左との差", 34, STAGE_COL["filter"]).move_to(px(800, Y - 80))
        self.play(FadeIn(fc, shift=DOWN * u(10)), FadeIn(fn, shift=DOWN * u(10)), run_time=0.7)
        # ずんだもん「並べ替えるのだ？」：数字は動かさず「？」だけ出す
        self.at("shuffle", -0.1)
        qm = jp("？", 52, YELLOW).move_to(px(1190, Y))
        self.play(FadeIn(qm, scale=1.4), Shake(fn, 4), run_time=0.6)
        # めたん「書き方を変えるの」：同じ場所で数字が変わる
        self.at("rewrite", -0.1)
        self.play(FadeOut(qm), FadeIn(lbl, shift=DOWN * u(6)),
                  LaggedStart(*[retext(fn[i], num(D[i], 38, YELLOW if D[i] else DIM)) for i in range(8)],
                              lag_ratio=0.06), run_time=1.3)
        self.at("s04_03", -1.0)
        fg = VGroup(fc, fn, lbl)
        self.play(fold(fg, P["filter"][0]), glow(P["filter"], STAGE_COL["filter"]), run_time=0.8)
        self.remove(fg)

        # ---- S04_03：LZ77（実データの繰り返し） ----
        self.at("lz", -0.2)
        shown.append(A[1])
        self.play(*reveal(P["lz77"], S[1]), GrowArrow(A[1]), run_time=0.8)
        self.play(pop(P["lz77"], 1.12, 0.6))
        tk = json.loads((ROOT / "build" / "analysis" / "zundamon.tokens0.json").read_text())["tokens"]
        outb, pos = [], []
        for t in tk:
            pos.append(len(outb))
            if isinstance(t, int):
                outb.append(t)
            else:
                for _ in range(t[0]):
                    outb.append(outb[-t[1]])
        i0 = 2664
        ln, dist = tk[i0]
        assert tk[i0 - 4:i0] == [0, 0, 0, 7] and (ln, dist) == (7, 4)
        seq = outb[pos[i0] - 4:pos[i0] + ln]
        lc, ln_ = boxes(seq, 960, Y)
        self.play(FadeIn(lc, shift=DOWN * u(10)), FadeIn(ln_, shift=DOWN * u(10)), run_time=0.7)
        self.at("lz", 2.0)
        ul = underline(VGroup(*lc[0:4]), CYAN)
        self.play(Create(ul), run_time=0.4)
        ghost = VGroup(*lc[0:4], *ln_[0:4]).copy()
        ghost.set_color(CYAN)
        ghost.check_ignore = True
        self.add(ghost)
        rep = VGroup(*lc[4:11], *ln_[4:11])
        self.play(ghost.animate(path_arc=-PI / 2.5).move_to(VGroup(*lc[4:8], *ln_[4:8]).get_center()),
                  run_time=0.8)
        self.remove(ghost)
        self.play(*[c.animate.set_fill(CYAN, 0.35) for c in lc[4:]], run_time=0.4)
        self.at("lz", 4.4)
        card = RoundedRectangle(corner_radius=u(14), width=u(7 * PITCH - 8), height=u(CELL),
                                stroke_width=0, fill_color=CYAN, fill_opacity=0.95)
        card.move_to(VGroup(*lc[4:]).get_center())
        ctext = mix(f"{dist}つ前から{ln}つ", 34, BG).move_to(card)
        self.play(*[FadeOut(n_) for n_ in ln_[4:]], *[FadeOut(c) for c in lc[4:]], FadeOut(ul),
                  FadeIn(card, scale=0.9), FadeIn(ctext), run_time=0.9)
        # ずんだもん「ずるい」：カードが揺れる。めたん「賢い」：カードが大きくなって戻る
        self.at("zuru", -0.1)
        cg = VGroup(card, ctext)
        self.play(Shake(cg, 6), run_time=0.6)
        self.at("smart", -0.1)
        self.play(pop(cg, 1.2, 0.7))
        self.at("s04_04", -1.0)
        lg = VGroup(lc[:4], ln_[:4], card, ctext)
        self.remove(*lc[4:], *ln_[4:])
        self.play(fold(lg, P["lz77"][0]), glow(P["lz77"], STAGE_COL["lz77"]), run_time=0.8)
        self.remove(lg)

        # ---- S04_04：ハフマン（バイト 0 の 8 ビットが 2 ビットに） ----
        self.at("huff", -0.2)
        shown.append(A[2])
        self.play(*reveal(P["huff"]), GrowArrow(A[2]), run_time=0.8)
        self.play(pop(P["huff"], 1.12, 0.6))
        ll = json.loads((ROOT / "build" / "analysis" / "zundamon.tokens0.json").read_text())["lit_lengths"]
        L0 = ll[0]
        assert L0 == 2 and all(ll[k] > 2 for k in range(1, 286) if ll[k])  # 0 だけが最短の符号（00）
        code = "0" * L0  # 長さ 2 の最小の符号は正準ハフマンで 00
        bx = [cell("#262b36", 62).move_to(px(1060 + (i - 3.5) * 70, Y)) for i in range(8)]
        bt = [num(0, 38).move_to(b) for b in bx]
        zero = num(0, 48, YELLOW).move_to(px(660, Y))
        eq = jp("=", 44, DIM).move_to(px(730, Y))
        hl = mix("8ビット", 34, DIM).move_to(px(1060, Y + 80))
        hg = VGroup(zero, eq, *bx, *bt, hl)
        self.play(FadeIn(hg, shift=DOWN * u(10)), run_time=0.7)
        self.at("huff", 2.4)
        keep = [VGroup(bx[i], bt[i]) for i in range(L0)]
        gone = [VGroup(bx[i], bt[i]) for i in range(L0, 8)]
        tgt = [px(1060 + (i - (L0 - 1) / 2) * 70, Y) for i in range(L0)]
        self.play(*[FadeOut(x, scale=0.6) for x in gone],
                  *[k.animate.move_to(t_) for k, t_ in zip(keep, tgt)],
                  *[bx[i].animate.set_fill(STAGE_COL["huff"], 0.9) for i in range(L0)],
                  *[bt[i].animate.set_color(BG) for i in range(L0)],
                  retext(hl, mix(f"{L0}ビット", 34, STAGE_COL["huff"])), run_time=1.0)
        self.at("s04_05", -1.0)
        self.remove(*[x for x in gone])
        hg2 = VGroup(zero, eq, *keep, hl)
        self.play(fold(hg2, P["huff"][0]), glow(P["huff"], STAGE_COL["huff"]), run_time=0.8)
        self.remove(hg2)

        # ---- S04_05：DEFLATE、zlib ----
        self.at("deflate", -0.3)
        shown.append(m.deflate)
        self.play(Create(m.deflate[0]), FadeIn(m.deflate[1], shift=DOWN * u(6)), run_time=0.9)
        self.at("zlib", -0.2)
        shown.extend([A[3], A[4]])
        self.play(*reveal(P["zlib"], S[2]), GrowArrow(A[3]), GrowArrow(A[4]), run_time=0.9)
        self.play(pop(P["zlib"], 1.12, 0.6))

        # ---- 地図そのものに差し替える（見た目は変わらない） ----
        self.at("go", 0.3)
        self.remove(*shown)
        self.add(m)
        self.wait(0.01)

        # ---- S04_07：逆にたどる ----
        self.at("reverse", -0.1)
        y = P["pixels"].get_center()[1]
        x_r = P["idat"].get_left()[0]
        x_l = P["pixels"].get_right()[0]

        def particle():
            parts = VGroup(*[Dot(radius=u(10 - 2 * k), color=YELLOW).set_opacity(1 - 0.3 * k).shift(RIGHT * u(18 * k))
                             for k in range(3)])
            parts.move_to([x_r, y, 0], aligned_edge=LEFT)
            parts.check_ignore = True
            return parts

        waves = [particle() for _ in range(4)]
        shift = x_l - x_r
        self.remove(m)
        self.add(*waves, m)
        dur = min(3.6, 4.2)
        self.play(LaggedStart(*[w.animate(rate_func=linear).shift(RIGHT * shift)
                                for w in waves], lag_ratio=0.2),
                  A.animate(rate_func=there_and_back).set_color(YELLOW), run_time=dur)
        self.play(*[FadeOut(w) for w in waves], run_time=0.3)
        self.remove(*waves)
        self.finish()
