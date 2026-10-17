import json
import sys
from collections import Counter
from pathlib import Path

ROOT_ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_))
sys.path.insert(0, str(ROOT_ / "tools"))

import numpy as np  # noqa: E402
import pnganalyze as pa  # noqa: E402

from vlib.data import file_bytes, fmt, info, pixels, path  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from vlib.pmap import STAGE_COL, PipelineMap  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

DARK = "#262b36"
USED = "#1a1d25"


def stats():
    """zundamon.png の本物のトークン列から、このシーンで使う数字と実例を取り出す（結果は build/ に保存）"""
    cache = ROOT_ / "build" / "analysis" / "s06_stats.json"
    if cache.exists():
        return json.loads(cache.read_text())
    idat = b"".join(c["data"] for c in pa.chunks(file_bytes("zundamon")) if c["type"] == "IDAT")
    raw, blocks, _ = pa.inflate(idat[2:])
    toks = [t for bl in blocks for t in bl["tokens"]]
    pos, pl = 0, []
    for t in toks:
        pl.append(pos)
        pos += 1 if isinstance(t, int) else t[0]
    assert pos == len(raw)
    matches = [(p, t) for p, t in zip(pl, toks) if isinstance(t, tuple)]
    # 例：リテラル4つのあとに (長さ8, 距離4)
    ex = None
    for i, (p, t) in enumerate(zip(pl, toks)):
        if t == (8, 4) and all(isinstance(toks[i - j], int) for j in range(1, 5)):
            ex = p
            break
    # くり返し：距離4で一番長いもの
    p2, t2 = max(((p, t) for p, t in matches if t[1] == 4), key=lambda x: x[1][0])
    c258 = Counter(t[1] for p, t in matches if t[0] == 258)
    out = dict(
        raw=len(raw), n_matches=len(matches), n258=sum(c258.values()), d258=c258.most_common(1)[0][0],
        top=Counter(t[1] for p, t in matches).most_common(6),
        copy_share=sum(t[0] for p, t in matches) / len(raw),
        ex_pos=ex, ex_bytes=list(raw[ex - 4:ex + 8]),
        rep_pos=p2, rep_len=t2[0], rep_bytes=list(raw[p2 - 4:p2 + 20]),
    )
    cache.write_text(json.dumps(out))
    return out


def bx(v, size, fs, fill=DARK, col=INK):
    sq = Square(u(size), stroke_width=0, fill_color=fill, fill_opacity=1)
    t = mono(str(v), fs, col).move_to(sq)
    return VGroup(sq, t)


def card(d, l, w=380, h=78, fs=34):
    r = RoundedRectangle(corner_radius=u(14), width=u(w), height=u(h), stroke_width=0, fill_color=CYAN,
                         fill_opacity=1)
    tl = mix(f"距離{d}", fs, BG).move_to(r.get_center() + LEFT * u(w / 4))
    tr = mix(f"長さ{l}", fs, BG).move_to(r.get_center() + RIGHT * u(w / 4))
    dv = Line(r.get_top() + DOWN * u(14), r.get_bottom() + UP * u(14), stroke_width=2, color=BG, stroke_opacity=0.5)
    return VGroup(r, tl, tr, dv)


def tri(color=YELLOW, up=True):
    t = Triangle(color=color, fill_opacity=1, stroke_width=0)
    t.stretch_to_fit_width(u(28)).stretch_to_fit_height(u(22))
    if not up:
        t.rotate(PI)
    return t


class S06(PScene):
    def construct(self):
        st = stats()
        zi = info("zundamon")
        zp = pixels("zundamon")
        STRIDE = 1 + zi["width"] * 4
        assert STRIDE == 4329 and st["raw"] == zi["raw_bytes"]
        top = [tuple(x) for x in st["top"]]
        assert top[0][0] == 1 and top[1][0] == 4329
        assert round(st["n258"], -4) == 20000, st["n258"]
        assert round(st["copy_share"] * 100) == 96 and round(st["raw"], -4) == 6900000
        assert st["ex_bytes"][4:] == st["ex_bytes"][:4] * 2

        # ---- S06_01：地図のLZ77段へ ----
        m = PipelineMap(done=("filter",))
        self.add(m)
        self.at("title")
        self.play(Transform(m, m.state("strip", active="lz77")), run_time=1.0)

        # ---- S06_02：前に出てきた並びがまた出てきたら ----
        BP, IY, TY = 88, 330, 570
        BOX, FS = 80, 38

        def xs(i):
            return 960 + (i - 5.5) * BP

        vals = st["ex_bytes"]
        row = VGroup(*[bx(v, BOX, FS).move_to(px(xs(i), IY)) for i, v in enumerate(vals)])
        row.check_group = True
        r, c = divmod(st["ex_pos"], STRIDE)
        cap = mix(f"フィルタ後のデータ（{r + 1}行目の一部）", 26, DIM).move_to(px(xs(0) - BOX / 2, IY - 150), aligned_edge=LEFT)
        self.at("s06_02", 0.3)
        self.play(LaggedStart(*[FadeIn(b, shift=DOWN * u(10)) for b in row], lag_ratio=0.05), FadeIn(cap),
                  run_time=1.2)

        def grp_arc(a, b, color=CYAN, angle=-PI / 3):
            ca, cb = (xs(a) + xs(a + 3)) / 2, (xs(b) + xs(b + 3)) / 2
            return CurvedArrow(px(ca, IY - 48), px(cb, IY - 48), angle=angle, color=color, stroke_width=4,
                               tip_length=u(14))

        self.at("seen")
        uls = VGroup(*[Line(px(xs(g) - BOX / 2, IY + 50), px(xs(g + 3) + BOX / 2, IY + 50), color=CYAN,
                            stroke_width=5) for g in (0, 4, 8)])
        arcs = VGroup(grp_arc(0, 4), grp_arc(4, 8))
        self.play(LaggedStart(*[Create(x) for x in uls], lag_ratio=0.25), Create(arcs), run_time=1.0)

        # 空の札（距離？・長さ？）
        self.at("ref")
        CX = (xs(4) + xs(11)) / 2
        tok = card("？", "？")
        tok.move_to(px(CX, TY))
        capL = jp("何バイト前から", 26, DIM).move_to(px(CX - 95, TY + 62))
        capR = jp("何バイトコピー", 26, DIM).move_to(px(CX + 95, TY + 62))
        self.play(FadeIn(tok, scale=0.9), FadeIn(capL, shift=UP * u(6)),
                  FadeIn(capR, shift=UP * u(6)), run_time=0.8)
        # ずんだもん：「さっきと同じ」って書けばいい？ → 2つ目の並びと札がはねる
        self.at("z_same", 0.3)
        self.play(*[pop(row[i], 1.2) for i in range(4, 8)], pop(tok, 1.12), run_time=0.7)

        # ---- S06_03：リテラルはそのまま、マッチはコピー ----
        self.at("s06_03", 0.05)
        cur = tri().move_to(px(xs(0), IY + BOX / 2 + 22))
        tcap = jp("トークン（圧縮後）", 26, DIM).move_to(px(xs(0) + 60, TY + 62), aligned_edge=LEFT)
        self.play(FadeOut(arcs), FadeOut(uls), FadeOut(capL), FadeOut(capR), FadeIn(cur, shift=UP * u(8)), FadeIn(tcap), run_time=0.6)
        self.at("lit", -0.1)
        lits = []
        for i in range(4):
            cp = row[i].copy()
            cp.check_ignore = True
            self.add(cp)
            self.play(cp.animate.move_to(px(xs(i), TY)),
                      row[i][0].animate.set_fill(USED), row[i][1].animate.set_color(DIM),
                      cur.animate.move_to(px(xs(i + 1), IY + BOX / 2 + 22)), run_time=0.38)
            cp.check_ignore = False
            lits.append(cp)

        self.at("match")
        a1 = grp_arc(0, 4)
        lab4 = mix("4バイト前", 28, CYAN).next_to(a1, UP, buff=u(6))
        self.play(Create(a1), FadeIn(lab4, shift=DOWN * u(6)),
                  *[row[i][0].animate.set_fill(CYAN, 0.25) for i in range(4, 12)], run_time=0.6)

        def fly(src, dst):
            cps = []
            for s in src:
                cp = bx(vals[s], BOX, FS, CYAN, BG)
                cp.move_to(px(xs(s), IY))
                cp.check_ignore = True
                cps.append(cp)
            self.add(*cps)
            self.play(*[cp.animate(path_arc=-PI / 3).move_to(px(xs(d), IY)) for cp, d in zip(cps, dst)],
                      run_time=0.8)
            for d in dst:
                row[d][0].set_fill(CYAN, 0.9)
                row[d][1].set_color(BG)
            self.wait(0.01)
            self.remove(*cps)

        fly(range(0, 4), range(4, 8))
        a2 = grp_arc(4, 8)
        self.play(Create(a2), run_time=0.3)
        fly(range(4, 8), range(8, 12))

        # ---- S06_04：8バイトが1つの札に ----
        self.at("token")
        gp = VGroup(*[row[i].copy() for i in range(4, 12)])
        gp.check_ignore = True
        self.add(gp)
        tcenter = px(CX, TY)
        self.play(LaggedStart(*[g.animate.scale(0.5).move_to(tcenter).set_opacity(0) for g in gp], lag_ratio=0.06),
                  FadeOut(VGroup(a1, a2, lab4)),
                  *[row[i][0].animate.set_fill(USED) for i in range(4, 12)],
                  *[row[i][1].animate.set_color(DIM) for i in range(4, 12)],
                  cur.animate.move_to(px(xs(12), IY + BOX / 2 + 22)), run_time=1.1)
        self.play(retext(tok[1], mix("距離4", 34, BG)), retext(tok[2], mix("長さ8", 34, BG)), run_time=0.5)
        self.remove(gp)
        self.at("wow")
        self.se("pop")
        self.play(pop(tok, 1.18), run_time=0.7)

        # ---- S06_06：重なるコピー（距離4・長さ41）----
        self.at("s06_06", 0.1)
        self.play(FadeOut(VGroup(row, cap, cur, tcap, tok, *lits)), run_time=0.8)
        L = st["rep_len"]
        rb = st["rep_bytes"]
        OB, OP, OY = 60, 65, 420

        def ox(i):
            return 960 + (i - 7.5) * OP

        slots = VGroup(*[bx(rb[i], OB, 28, DARK, INK).move_to(px(ox(i), OY)) for i in range(16)])
        slots.check_group = True
        for i in range(4, 16):
            slots[i][1].set_opacity(0)
            slots[i][0].set_fill("#1c2029")
        otok = card(4, "？", 380, 78).move_to(px(960, 215))
        self.at("overlap")
        self.play(FadeIn(slots, shift=DOWN * u(8)), FadeIn(otok, shift=DOWN * u(8)), run_time=0.8)
        dist_arr = CurvedArrow(px(ox(0), OY - 36), px(ox(4), OY - 36), angle=-PI / 2.5, color=CYAN,
                               stroke_width=4, tip_length=u(12))
        dlab = mix("1画素（4バイト）前", 26, CYAN).next_to(dist_arr, UP, buff=u(6))
        self.play(Create(dist_arr), FadeIn(dlab, shift=DOWN * u(6)), run_time=0.7)

        self.at("grow")
        for k in range(3):
            cps = []
            for j in range(4):
                cp = bx(rb[4 * k + j], OB, 28, CYAN, BG).move_to(px(ox(4 * k + j), OY))
                cp.check_ignore = True
                cps.append(cp)
            self.add(*cps)
            dst = [4 * k + 4 + j for j in range(4)]
            self.play(*[cp.animate(path_arc=-PI / 3).move_to(px(ox(d), OY)) for cp, d in zip(cps, dst)],
                      retext(otok[2], mix(f"長さ{4 * (k + 1)}", 34, BG)), run_time=1.0)
            for d in dst:
                slots[d][0].set_fill(CYAN, 0.9)
                slots[d][1].set_color(BG).set_opacity(1)
            self.wait(0.01)
            self.remove(*cps)
        dots = mono("…", 40, CYAN).move_to(px(ox(16) + 10, OY))
        self.play(FadeIn(dots), retext(otok[2], mix(f"長さ{L}", 34, BG)), pop(otok, 1.12), run_time=0.8)

        # ---- S06_07：まだ書いてない所を？ ----
        self.at("q")
        qs = VGroup(*[jp("？", 34, CORAL).move_to(px(ox(i), OY - 58)) for i in range(8, 12)])
        self.play(FadeIn(qs, shift=DOWN * u(6)), Shake(VGroup(*[slots[i] for i in range(8, 12)]), 6), run_time=0.7)
        self.at("chain")
        ch_arr = CurvedArrow(px(ox(5.5), OY + 36), px(ox(9.5), OY + 36), angle=PI / 2.5, color=YELLOW,
                             stroke_width=4, tip_length=u(12))
        clab = jp("書いた分が、次のコピー元", 28, YELLOW).next_to(ch_arr, DOWN, buff=u(6))
        self.play(FadeOut(qs), Create(ch_arr), FadeIn(clab, shift=UP * u(6)),
                  *[slots[i].animate.scale(1.0) for i in range(4, 8)], run_time=0.8)
        self.play(*[pop(slots[i], 1.25) for i in range(4, 8)], run_time=0.6)
        # ずんだもん：自分で自分をコピーして伸びていく
        self.at("z_self")
        self.play(LaggedStart(*[pop(slots[i], 1.25, 0.5) for i in range(4, 16)], lag_ratio=0.1), run_time=1.6)

        # ---- S06_09：窓 32768、最大 258 ----
        self.at("s06_09", 0.05)
        self.play(FadeOut(VGroup(slots, otok, dist_arr, dlab, dots, ch_arr, clab)), run_time=0.6)
        BX0, BX1, BY = 500, 1440, 520
        curx = 1360
        bar = Rectangle(width=u(BX1 - BX0), height=u(70), stroke_width=0, fill_color=DARK, fill_opacity=1)
        bar.move_to(px((BX0 + BX1) / 2, BY))
        done_ = Rectangle(width=u(curx - BX0), height=u(70), stroke_width=0, fill_color="#3a4150", fill_opacity=1)
        done_.move_to(px((BX0 + curx) / 2, BY))
        wcur = tri(YELLOW, up=False).move_to(px(curx, BY - 35 - 22))
        wcap = jp("これまでに書いたデータ", 26, DIM).move_to(px(BX0, BY + 62), aligned_edge=LEFT)
        self.at("window", -0.4)
        self.play(FadeIn(VGroup(bar, done_), shift=UP * u(8)), FadeIn(wcur, shift=DOWN * u(8)), FadeIn(wcap),
                  run_time=0.6)
        brace = BraceBetweenPoints(px(curx, BY - 75), px(BX0, BY - 75), color=YELLOW)
        wl = mix(f"{fmt(32768)} バイト前まで", 52, YELLOW)
        wl.next_to(brace, UP, buff=u(10))
        self.play(GrowFromCenter(brace), FadeIn(wl, shift=DOWN * u(8)), run_time=0.9)
        self.at("max")
        blk = Rectangle(width=u(BX1 - curx), height=u(70), stroke_width=0, fill_color=CYAN, fill_opacity=1)
        blk.move_to(px((curx + BX1) / 2, BY))
        ml = mix("258 バイトまで", 52, CYAN).move_to(px(1230, BY + 150))
        mline = Line(px(1400, BY + 40), px(1400, BY + 100), color=CYAN, stroke_width=3)
        self.play(FadeIn(blk, scale=0.6), FadeIn(ml, shift=UP * u(8)), Create(mline), run_time=0.8)

        # ずんだもん：もっと長く続いていたら？ → 同じコピーを何回も続ける
        self.at("z_long", 0.2)
        chain_c = VGroup(*[card(1, 258, 300, 64, 30).move_to(px(660 + 300 * k, 790)) for k in range(3)])
        for cc in chain_c:
            cc[0].set_fill(CYAN, 0.9)
        self.play(LaggedStart(*[FadeIn(cc, shift=RIGHT * u(30)) for cc in chain_c], lag_ratio=0.3), run_time=1.4)

        # ---- S06_10：透明な背景は 0 の連続 → 長さ258のコピー ----
        self.at("s06_10", 0.05)
        self.play(FadeOut(VGroup(bar, done_, wcur, wcap, brace, wl, blk, ml, mline, chain_c)), run_time=0.6)
        IMH = 460
        assert zp[100, 100, 3] == 0
        timg = png_mob(zp, IMH).move_to(px(640, 340))
        self.play(FadeIn(timg, scale=0.97), run_time=0.7)
        self.at("bg")
        spot = Square(u(16), stroke_width=3, color=YELLOW, fill_opacity=0)
        spot.move_to([timg.get_left()[0] + timg.width * 100.5 / zp.shape[1],
                      timg.get_top()[1] - timg.height * 100.5 / zp.shape[0], 0])
        zrow = VGroup(*[bx(0, 76, 38).move_to(px(940 + 84 * i, 300)) for i in range(6)])
        zrow.check_group = True
        zdots = mono("…", 40, DIM).move_to(px(940 + 84 * 6 - 10, 300))
        con = Line(spot.get_right(), px(940 - 48, 300), color=YELLOW, stroke_width=2, stroke_opacity=0.6)
        self.play(Create(spot), run_time=0.3)
        self.play(Create(con), LaggedStart(*[FadeIn(b, shift=RIGHT * u(10)) for b in zrow], lag_ratio=0.06),
                  FadeIn(zdots), run_time=0.9)
        self.at("n258")
        d258 = st["d258"]
        ctok = card(d258, 258, 400).move_to(px(1180, 470))
        self.play(FadeIn(ctok, shift=DOWN * u(10)), *[b[0].animate.set_fill(CYAN, 0.9) for b in zrow],
                  *[b[1].animate.set_color(BG) for b in zrow], run_time=0.7)
        n258 = st["n258"]
        cx0 = 960
        cnt = mix("0 回", 72, CYAN).move_to(px(cx0, 640), aligned_edge=LEFT)
        xmark = jp("使われた数", 28, DIM).move_to(px(cx0, 715), aligned_edge=LEFT)

        def upd(mob, a):
            new = mix(f"{fmt(int(round(n258 * a)))} 回", 72, CYAN)
            new.move_to(px(cx0, 640), aligned_edge=LEFT)
            mob.become(new)

        self.add(cnt)
        self.play(UpdateFromAlphaFunc(cnt, upd), FadeIn(xmark), run_time=1.6, rate_func=rush_from)
        self.play(pop(cnt, 1.08), run_time=0.5)
        self.at("z_2man", 0.1)
        self.play(pop(cnt, 1.2), pop(ctok, 1.12), run_time=0.7)

        # ---- S06_11：距離の多い順 ----
        self.at("s06_11", -0.1)
        self.play(FadeOut(Group(timg, spot, con, zrow, zdots, ctok, cnt, xmark)), run_time=0.6)
        maxc = top[0][1]
        TX, BX = 680, 740
        hdr1 = jp("距離", 32, DIM).move_to(px(TX, 190), aligned_edge=RIGHT)
        hdr2 = jp("使われた回数", 32, DIM).move_to(px(BX, 190), aligned_edge=LEFT)
        rows_ = []
        for k, (d, n) in enumerate(top):
            y = 280 + 100 * k
            lab = mix(str(d), 48, INK)
            lab.move_to(px(TX, y), aligned_edge=RIGHT)
            bw = 480 * n / maxc
            bar_ = Rectangle(width=u(bw), height=u(56), stroke_width=0, fill_color=CYAN, fill_opacity=0.9)
            bar_.move_to(px(BX + bw / 2, y))
            ct = mix(fmt(n), 40, DIM).next_to(bar_, RIGHT, buff=u(14))
            rows_.append(VGroup(lab, bar_, ct))
        self.play(FadeIn(VGroup(hdr1, hdr2)), LaggedStart(*[AnimationGroup(FadeIn(r_[0]), GrowFromEdge(r_[1], LEFT),
                                                                          FadeIn(r_[2])) for r_ in rows_],
                                                         lag_ratio=0.15), run_time=1.0)
        self.at("d4329", 1.5)
        self.play(rows_[1][0].animate.set_color(YELLOW), pop(rows_[1][0], 1.3), run_time=0.7)

        # ---- S06_12：4329 = 1 + 1082×4 ----
        self.at("s06_12", 0.1)
        self.play(FadeOut(VGroup(hdr1, hdr2, *[rows_[k] for k in range(6) if k != 1])), run_time=0.7)
        EY = 700
        parts = [("1", None, "フィルタ番号", 0), ("+", None, None, 0), (str(zi["width"]), None, "画素の数", 0),
                 ("×4", None, "1画素 4バイト", 0), ("=", None, None, 0)]
        eqs = [mix(s, 72, INK) for s, _, _, _ in parts]
        e4329 = mix("4329", 72, YELLOW)
        grp = VGroup(*eqs, e4329).arrange(RIGHT, buff=u(64))
        grp.move_to(px(960, EY))
        labs = {}
        for idx, (s, _, lab, _) in enumerate(parts):
            if lab:
                labs[idx] = jp(lab, 30, DIM).next_to(eqs[idx], DOWN, buff=u(18))
        self.at("s06_12", 1.3)
        self.play(FadeIn(eqs[0], scale=0.7), FadeIn(labs[0], shift=UP * u(6)), run_time=0.5)
        self.at("stride")
        self.play(FadeIn(eqs[1]), FadeIn(eqs[2], scale=0.7), FadeIn(labs[2], shift=UP * u(6)), run_time=0.6)
        self.play(FadeIn(eqs[3], scale=0.7), FadeIn(labs[3], shift=UP * u(6)), run_time=0.6)
        self.at("stride", 2.4)
        src_lab = rows_[1][0]
        flyer = src_lab.copy()
        flyer.check_ignore = True
        self.add(flyer)
        self.play(FadeIn(eqs[4]), flyer.animate(path_arc=-PI / 3).become(e4329),
                  FadeOut(VGroup(rows_[1][1], rows_[1][2], src_lab)), run_time=0.9)
        self.remove(flyer)
        self.add(e4329)

        # ---- 1行上の同じ場所 ----
        self.at("above")
        eqall = VGroup(*eqs, e4329, *labs.values())
        SW, SX0 = 1000, 460
        hy = {862: 340, 863: 450}
        r0 = st["ex_pos"] // STRIDE
        assert (r0 - 1, r0) == (862, 863)
        strips = {}
        for rr in (r0 - 1, r0):
            img_ = ImageMobject(checker_composite(zp[rr:rr + 1], 12))
            img_.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
            img_.stretch_to_fit_width(u(SW)).stretch_to_fit_height(u(70)).move_to(px(SX0 + SW / 2, hy[rr]))
            strips[rr] = img_
        rl = {rr: mix(f"{rr + 1}行目", 26, DIM).move_to(px(SX0 - 12, hy[rr]), aligned_edge=RIGHT) for rr in strips}
        pxx = (st["ex_pos"] % STRIDE - 1) // 4
        mx = SX0 + SW * (pxx + 0.5) / zp.shape[1]
        mk = {rr: Square(u(14), stroke_width=3, color=YELLOW, fill_opacity=0).move_to(px(mx, hy[rr]))
              for rr in strips}
        ab = Arrow(mk[r0].get_top() + UP * u(2), mk[r0 - 1].get_bottom() + DOWN * u(2), buff=0, color=CYAN,
                   stroke_width=5, tip_length=u(16))
        alab = mix("4329バイト前＝1行上", 38, CYAN).move_to(px(mx + 20, 520), aligned_edge=LEFT)
        alab.move_to(px(960, 570))
        self.play(eqall.animate.scale(0.8).move_to(px(960, 185)),
                  FadeIn(Group(*strips.values(), *rl.values()), shift=UP * u(10)), run_time=0.9)
        self.play(Create(mk[r0]), Create(mk[r0 - 1]), run_time=0.4)
        self.play(Create(ab), FadeIn(alab, shift=RIGHT * u(8)), run_time=0.8)
        # ずんだもん：上の行と同じ所はまるごとコピー → 上の行の写しが下の行へ重なる
        self.at("z_row", 0.1)
        whole = Rectangle(width=u(SW), height=u(70), stroke_width=0, fill_color=CYAN, fill_opacity=0.45)
        whole.move_to(px(SX0 + SW / 2, hy[862]))
        whole.check_ignore = True
        self.add(whole)
        self.play(whole.animate(path_arc=-PI / 6).move_to(px(SX0 + SW / 2, hy[863])), run_time=1.0)
        self.play(FadeOut(whole), run_time=0.4)

        # ---- S06_13：全体の96% ----
        self.at("s06_13", 0.1)
        self.play(FadeOut(Group(eqall, *strips.values(), *rl.values(), *mk.values(), ab, alab)), run_time=0.6)
        PX0, PX1, PY = 480, 1440, 420
        full = Rectangle(width=u(PX1 - PX0), height=u(90), stroke_width=0, fill_color="#3a4150", fill_opacity=1)
        full.move_to(px((PX0 + PX1) / 2, PY))
        tot = mix(f"{fmt(st['raw'])} バイト", 56, INK)
        tot.move_to(px(960, 270))
        self.play(FadeIn(full, scale=0.9), FadeIn(tot, shift=DOWN * u(8)), run_time=0.7)
        self.at("pct")
        share = st["copy_share"]
        cw = (PX1 - PX0) * share
        fillb = Rectangle(width=u(cw), height=u(90), stroke_width=0, fill_color=CYAN, fill_opacity=1)
        fillb.move_to(px(PX0 + cw / 2, PY))
        big = mix(f"{round(share * 100)}%", 130, CYAN).move_to(px(960, 640))
        cl = jp("コピーで書けた", 40, CYAN).move_to(px(PX0, PY + 85), aligned_edge=LEFT)
        ll = jp("そのまま", 30, DIM).move_to(px(PX1, PY + 85), aligned_edge=RIGHT)
        self.se("pop")
        self.play(GrowFromEdge(fillb, LEFT), FadeIn(big, scale=0.7), FadeIn(cl, shift=UP * u(6)), FadeIn(ll),
                  run_time=1.0)
        self.at("z_all", 0.1)
        self.play(pop(big, 1.15), Shake(full, 6), run_time=0.7)

        # ---- 地図へ ----
        self.at(self.tl["duration"] - 1.5)
        self.play(FadeOut(VGroup(full, tot, fillb, big, cl, ll)), run_time=0.4)
        self.play(Transform(m, m.state("full", active=None, done=("filter", "lz77"))), run_time=1.0)
        self.finish()
