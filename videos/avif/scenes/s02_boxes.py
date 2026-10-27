import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import MAIN, boxes, dec, file_bytes, fmt, obus, pixels, rgb_decoded, size  # noqa: E402
from vlib.photoview import PhotoView  # noqa: E402
from vlib.ui import HEIC_COL  # noqa: E402
from zunda.fx import pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "heic" / "tools"))
import hevc  # noqa: E402  HEIC 編の自前の読み取り器 (HEVC の SPS から、圧縮した大きさを読む)

HEIC = "cat_q45.heic"
STEP, ROW_Y, CHAR_DY, BSIZE = 80, (215, 400), 88, 50      # 16 バイトずつ 2 行 (HEIC 編の S02 と同じ並べ方)
# ファイル全体の帯 (幅はバイト数に比例。HEIC と同じ尺)
SX0, SX1, SH = 200, 1860, 64
SY = {"heic": 175, "avif": 330}
LAB_Y = {"heic": 100, "avif": 405}
SEG_COL = {"ftyp": YELLOW, "meta": BLUE, "mdat": "#4a5060"}
CHIP_FILL = "#1c1f27"
# meta の中の箱 (上下 2 段)
ROWS_Y = {"heic": 520, "avif": 660}
COL_X0, COL_DX, CHIP_W, CHIP_H = 510, 100, 92, 60
EQ_Y, EQ_Y2 = 600, 862
# 写真 (切り取りの話)
PIC_C, PIC_W = (880, 655), 700
DIM_C = (1355, 655)
# OBU
OBU_Y, OBU_H, OBU_X0, OBU_X1, SEQ_W, TD_W = 600, 100, 460, 1460, 180, 8
# 設定の 10 バイトのビット
BIT, BYTE_GAP, PER_ROW, BITS_Y = 48, 8, 20, (330, 450, 570, 690)     # 2 人の間に 4 段 × 20
NUM_Y, PLUS_Y = 150, 86
SW_Y, SW_X = 790, (560, 720, 880, 1040, 1200, 1360)
SWITCHES = ("enable_filter_intra", "enable_intra_edge_filter", "enable_superres", "enable_cdef", "enable_restoration",
            "film_grain_params_present")
SW_NAMES = {"enable_cdef": "CDEF", "film_grain_params_present": "粒子"}     # この動画で出てくる機能だけ
PHOTO = ((960, 386), 1040, 692)          # S03 の最初の写真


def bx(i):
    return 960 + STEP * (i % 16 - 7.5)


def by(i):
    return ROW_Y[i // 16]


def left_at(m, x, y):
    return m.move_to(px(x, y), aligned_edge=LEFT).set_y(px(0, y)[1])


def chip(name, c, w, h, col=BLUE, size_=26):
    box = RoundedRectangle(corner_radius=u(10), width=u(w), height=u(h), stroke_color=col, stroke_width=3,
                           fill_color=CHIP_FILL, fill_opacity=1).move_to(px(*c))
    t = mono(name, size_, INK).move_to(box)
    g = VGroup(box, t)
    g.box, g.t = box, t
    return g


def meta_leaves(meta):
    """meta の中の箱を、入れ物 (iprp・ipco) を開いて並べる (iinf の中の infe は iinf に含める)"""
    out = []
    for b in meta["kids"]:
        if b["type"] == "iprp":
            for k in b["kids"]:
                out += k["kids"] if k["type"] == "ipco" else [k]
        else:
            out.append(b)
    return out


def bit_xy(i):
    r, j = divmod(i, PER_ROW)
    x0 = 960 - (PER_ROW * BIT + 2 * BYTE_GAP) / 2
    gaps = i // 8 - (r * PER_ROW) // 8           # この段の中のバイトの切れ目の数
    return x0 + j * BIT + gaps * BYTE_GAP + BIT / 2, BITS_Y[r]


def bit_runs(p, nb):
    """ビット p から nb 個を、段ごとの (最初, 最後) に分ける"""
    out, i = [], p
    while i < p + nb:
        last = min(p + nb, (i // PER_ROW + 1) * PER_ROW) - 1
        out.append((i, last))
        i = last + 1
    return out


class S02(PScene):
    def construct(self):
        fb = file_bytes(MAIN)
        head = fb[:32]
        total = size(MAIN)
        r = boxes(MAIN)
        rh = boxes(HEIC)
        tree, tree_h = r["tree"], rh["tree"]
        # ---- 実データの確認 ----
        assert [(b["type"], b["size"]) for b in tree] == [("ftyp", 32), ("meta", 235), ("mdat", 12912)]
        assert [(b["type"], b["size"]) for b in tree_h] == [("ftyp", 24), ("meta", 385), ("mdat", 12959)]
        assert sum(b["size"] for b in tree) == total == 13179
        total_h = size(HEIC)
        assert int.from_bytes(head[:4], "big") == 32 and head[4:8] == b"ftyp" and head[8:12] == b"avif"
        meta, mdat = tree[1], tree[2]
        meta_h = tree_h[1]
        assert meta_h["size"] - meta["size"] == 150
        leaves = {b["type"]: b for b in meta_leaves(meta)}
        leaves_h = {b["type"]: b for b in meta_leaves(meta_h)}
        cols = [b["type"] for b in meta_leaves(meta_h)]
        assert cols == ["hdlr", "iloc", "iinf", "pitm", "hvcC", "colr", "ispe", "clap", "pixi", "ipma"]
        assert set(leaves) == set(cols) - {"hvcC", "clap"} | {"av1C"}
        assert leaves_h["hvcC"]["size"] == 122 and leaves["av1C"]["size"] == 12 and leaves_h["clap"]["size"] == 40
        # HEVC は 8 の倍数に広げて圧縮し、clap で 451×300 に切り取る
        hvcc = next(p for p in rh["props"] if p["type"] == "hvcC")
        sps = hevc.parse_sps(hevc.unescape(next(nl["data"] for nl in hvcc["nals"] if nl["type"] == 33))[0])
        clap = next(p for p in rh["props"] if p["type"] == "clap")
        assert (sps["width"], sps["height"]) == (456, 304) and sps["width"] % 8 == 0 and sps["height"] % 8 == 0
        assert (clap["width"], clap["height"]) == (451, 300)
        # OBU
        ob = obus(MAIN)
        assert [o["type"] for o in ob] == [2, 1, 6]
        ob_n = [o["header"] + o["size"] for o in ob]
        assert ob_n == [2, 12, 12890] and sum(ob_n) == mdat["size"] - 8
        assert ob[1]["size"] == 10
        # 設定の 10 バイト：ビットの位置と値は復号器の記録から
        d = dec()
        base = (ob[1]["pos"] + ob[1]["header"]) * 8
        seq_bytes = fb[ob[1]["pos"] + ob[1]["header"]: ob[1]["pos"] + ob[1]["header"] + 10]
        bits = [(seq_bytes[i // 8] >> (7 - i % 8)) & 1 for i in range(80)]
        fields = [(nm, v, p - base, nb) for nm, v, p, nb in d.fields if p is not None and base <= p < base + 80 and nb > 0]
        F = {nm: (v, p, nb) for nm, v, p, nb in fields}
        for nm, (v, p, nb) in F.items():       # 記録の値とファイルのビットが一致する
            assert int("".join(map(str, bits[p:p + nb])), 2) == v, nm
        assert F["still_picture"][0] == 1
        assert F["max_frame_width_minus_1"][:3:2] == (450, 9) and F["max_frame_height_minus_1"][0] == 299
        sw_vals = [F[s][0] for s in SWITCHES]
        assert sw_vals == [1, 1, 0, 1, 0, 0]
        W, H = F["max_frame_width_minus_1"][0] + 1, F["max_frame_height_minus_1"][0] + 1
        assert (W, H) == (451, 300)

        def xb(b):
            return SX0 + (SX1 - SX0) * b / total_h

        title = jp("AVIFの中身をのぞく", 72).move_to(px(960, 300))
        title.check_ignore = True   # S01 から引き継ぐ画面
        self.add(title)

        # ---- 先頭からのぞく ----
        self.at("s02_01", -0.1)
        fname = mix(f"{MAIN}.avif　{fmt(total)} バイト", 32, DIM).move_to(px(960, 62))
        self.play(FadeOut(title, shift=UP * u(20)), FadeIn(fname, shift=DOWN * u(8)), run_time=0.6)

        self.at("hex", 0.0)
        hexes = VGroup(*[mono(f"{b:02X}", BSIZE).move_to(px(bx(i), by(i))) for i, b in enumerate(head)])
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(8)) for b in hexes], lag_ratio=0.04), run_time=1.3)

        def chars_of(i0, n, col):
            return VGroup(*[mono(chr(head[i]), 40, col).move_to(px(bx(i), by(i) + CHAR_DY)) for i in range(i0, i0 + n)])

        def fly(i0, n, target):
            cp = VGroup(*[hexes[i].copy() for i in range(i0, i0 + n)])
            cp.check_ignore = True
            return ReplacementTransform(cp, target, path_arc=-0.5)

        # ---- 大きさ ----
        self.at("ftyp", -0.1)
        ul = underline(VGroup(*hexes[:4]), CYAN)
        n32 = mix("32", 48, CYAN).move_to(px((bx(1) + bx(2)) / 2, ROW_Y[0] + CHAR_DY))
        self.play(*[hexes[i].animate.set_color(CYAN) for i in range(4)],
                  *[hexes[i].animate.set_color(DIM) for i in range(4, 32)], Create(ul), fly(0, 4, n32), run_time=0.8)

        # ---- 名前 ftyp ----
        self.at("name", -0.1)
        c_ftyp = chars_of(4, 4, YELLOW)
        self.play(*[hexes[i].animate.set_color(YELLOW) for i in range(4, 8)],
                  LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_ftyp[i - 4]) for i in range(4, 8)],
                              lag_ratio=0.12), run_time=0.8)

        # ---- 中身の種類 avif ----
        self.at("brand", -0.1)
        c_avif = chars_of(8, 4, INK)
        self.play(*[hexes[i].animate.set_color(INK) for i in range(8, 12)],
                  LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_avif[i - 8]) for i in range(8, 12)],
                              lag_ratio=0.12), run_time=0.8)

        # ---- バイト列が縮んで、ファイル全体の帯に ----
        def strip(t, key):
            seg = {}
            for b in t:
                x0, x1 = xb(b["pos"]), xb(b["pos"] + b["size"])
                seg[b["type"]] = Rectangle(width=u(x1 - x0), height=u(SH), stroke_width=0, fill_color=SEG_COL[b["type"]],
                                           fill_opacity=1).move_to(px(x0, SY[key]), aligned_edge=LEFT)
            return seg

        def strip_labels(t, key, up):
            ly, sy = LAB_Y[key], SY[key]
            edge = sy - SH / 2 if up else sy + SH / 2
            f, m, dt = t
            lab_f = left_at(mix(f"ftyp {f['size']}", 32, YELLOW), SX0, ly)
            lead_f = Line(px(xb(f["size"] / 2), ly + (16 if up else -16)), px(xb(f["size"] / 2), edge),
                          stroke_color=YELLOW, stroke_width=2)
            lab_m = left_at(mix(f"meta {m['size']}", 32, BLUE), 360, ly)
            lead_m = Line(px(354, ly), px(xb(m["pos"] + m["size"] / 2), edge), stroke_color=BLUE, stroke_width=2)
            lab_d = mix(f"mdat {fmt(dt['size'])}", 36, INK).move_to(px((xb(dt["pos"]) + xb(dt["pos"] + dt["size"])) / 2, sy))
            return lab_f, lead_f, lab_m, lead_m, lab_d

        self.at("bar", -0.1)
        seg_a = strip(tree, "avif")
        lf, lfl, lm, lml, ld = strip_labels(tree, "avif", False)
        tag_a = left_at(jp("AVIF", 40, YELLOW), 52, SY["avif"])
        bytes_g = VGroup(hexes, n32, c_ftyp, c_avif, ul)
        self.play(bytes_g.animate(rate_func=rate_functions.ease_in_out_cubic)
                  .stretch_to_fit_width(u(xb(32) - xb(0))).stretch_to_fit_height(u(SH))
                  .move_to(px((xb(0) + xb(32)) / 2, SY["avif"])).set_opacity(0),
                  FadeOut(fname),
                  Succession(Wait(0.4), FadeIn(seg_a["ftyp"], run_time=0.2), GrowFromEdge(seg_a["meta"], LEFT, run_time=0.2),
                             GrowFromEdge(seg_a["mdat"], LEFT, run_time=0.6, rate_func=rate_functions.ease_out_cubic)),
                  FadeIn(tag_a), run_time=1.1)
        self.remove(bytes_g, *bytes_g)

        # ---- HEIC の帯が同じ尺で上に ----
        self.at("heic", -0.1)
        seg_h = strip(tree_h, "heic")
        hf, hfl, hm, hml, hd = strip_labels(tree_h, "heic", True)
        tag_h = left_at(jp("HEIC", 40, HEIC_COL), 52, SY["heic"])
        self.play(LaggedStart(*[FadeIn(s, shift=DOWN * u(20)) for s in seg_h.values()], lag_ratio=0.15),
                  FadeIn(tag_h, shift=DOWN * u(20)), Create(lfl), Create(lml), FadeIn(lf), FadeIn(lm),
                  FadeIn(ld, scale=0.9), run_time=0.9)
        self.play(Create(hfl), Create(hml), FadeIn(hf), FadeIn(hm), FadeIn(hd, scale=0.9), run_time=0.5)
        strips = VGroup(*seg_h.values(), *seg_a.values())

        # Z「そっくり」
        self.at("twin", 0.0)
        self.play(LaggedStart(pop(VGroup(hf, lf), 1.15, 0.5), pop(VGroup(hm, lm), 1.15, 0.5),
                              pop(VGroup(hd, ld), 1.1, 0.5), lag_ratio=0.5), run_time=1.3)

        # ---- 式：HEIF の箱 ＋ HEVC の中身 ＝ HEIC → AV1・AVIF ----
        t1 = mix("HEIFの箱", 56, BLUE)
        plus = mix("＋", 56, DIM)
        t2 = mix("HEVCの中身", 56, HEIC_COL)
        eqs = VGroup(*[Line(LEFT * u(20), RIGHT * u(20), stroke_color=DIM, stroke_width=5).shift(UP * u(dd))
                       for dd in (8, -8)])
        t3 = mix("HEIC", 64, HEIC_COL)
        eq = VGroup(t1, plus, t2, eqs, t3).arrange(RIGHT, buff=u(30)).move_to(px(960, EQ_Y))
        self.at("heif", -0.1)
        self.play(pop(strips, 1.03, 0.6), FadeIn(t1, shift=DOWN * u(20)), run_time=0.7)
        self.at("eq", -0.1)
        self.play(FadeIn(plus), FadeIn(t2, shift=LEFT * u(10)), FadeIn(eqs), FadeIn(t3, shift=LEFT * u(10)),
                  run_time=0.6)
        self.wait(0.95)
        self.play(retext(t2, mix("AV1の中身", 56, YELLOW), path_arc=PI / 2),
                  retext(t3, mix("AVIF", 64, YELLOW), path_arc=PI / 2), run_time=0.6)

        # ---- meta が開く ----
        self.at("meta", -0.1)

        def col_x(i):
            return COL_X0 + COL_DX * i
        fx0, fx1 = col_x(0) - CHIP_W / 2 - 10, col_x(9) + CHIP_W / 2 + 10
        frames, chips, rtags = {}, {}, {}
        for key, lv, sg, col in (("heic", leaves_h, seg_h, HEIC_COL), ("avif", leaves, seg_a, YELLOW)):
            y = ROWS_Y[key]
            frames[key] = RoundedRectangle(corner_radius=u(14), width=u(fx1 - fx0), height=u(CHIP_H + 20),
                                           stroke_color=BLUE, stroke_width=3).move_to(px((fx0 + fx1) / 2, y))
            rtags[key] = left_at(jp(key.upper(), 30, col), fx0 + 6, y - (CHIP_H + 20) / 2 - 24)
            chips[key] = {}
            for i, c in enumerate(cols):
                nm = "av1C" if (key == "avif" and c == "hvcC") else c
                if nm in lv:
                    chips[key][c] = chip(nm, (col_x(i), y), CHIP_W, CHIP_H, size_=30)
        cps = {k: (seg_h if k == "heic" else seg_a)["meta"].copy() for k in frames}
        self.play(eq.animate.scale(0.8).move_to(px(960, EQ_Y2)),
                  *[ReplacementTransform(cps[k], frames[k]) for k in frames],
                  *[FadeIn(rtags[k]) for k in frames], run_time=0.7)
        self.play(*[LaggedStart(*[FadeIn(c, shift=DOWN * u(8)) for c in chips[k].values()], lag_ratio=0.08)
                    for k in frames], run_time=0.6)
        self.at("small", -0.1)
        d150 = mix(f"(−{meta_h['size'] - meta['size']})", 32, YELLOW)
        d150.next_to(lm, RIGHT, buff=u(14))
        self.play(FadeIn(d150, shift=LEFT * u(8)), pop(VGroup(hm, lm), 1.12, 0.6), run_time=0.7)

        def lit(c, col=YELLOW, on=True):
            return [c.box.animate.set_stroke(col if on else BLUE, width=5 if on else 3),
                    c.t.animate.set_color(col if on else INK)]

        # ---- 設定の箱 ----
        self.at("config", -0.1)
        self.play(*lit(chips["heic"]["hvcC"]), *lit(chips["avif"]["hvcC"]), run_time=0.6)
        self.at("hvcc", -0.1)
        ci = cols.index("hvcC")
        n122 = mix(f"{leaves_h['hvcC']['size']}", 36, YELLOW).move_to(px(col_x(ci), ROWS_Y["heic"] - CHIP_H / 2 - 38))
        self.play(FadeIn(n122, shift=DOWN * u(8)), run_time=0.6)
        self.at("av1c", -0.1)
        n12 = mix(f"{leaves['av1C']['size']}", 36, YELLOW).move_to(px(col_x(ci), ROWS_Y["avif"] + CHIP_H / 2 + 38))
        self.play(FadeIn(n12, shift=UP * u(8)), run_time=0.6)
        self.play(pop(n12, 1.3, 0.6), run_time=0.6)

        # ---- 切り取りの箱 clap ----
        self.at("clap", -0.1)
        cj = cols.index("clap")
        cut_t = jp("切り取り", 28, CORAL).move_to(px(col_x(cj), (ROWS_Y["heic"] + ROWS_Y["avif"]) / 2))
        self.play(*lit(chips["heic"]["hvcC"], on=False), *lit(chips["avif"]["hvcC"], on=False),
                  *lit(chips["heic"]["clap"], CORAL), FadeIn(cut_t, shift=UP * u(6)), run_time=0.7)

        # ---- 8 の倍数に広げて圧縮 ----
        self.at("pad", -0.1)
        panel = VGroup(*frames.values(), *rtags.values(), *[c for k in chips for c in chips[k].values()], cut_t,
                       n122, n12)
        ph_h = PIC_W * H / W
        ph = png_mob(pixels(HEIC), ph_h).move_to(px(*PIC_C))
        ph.check_ignore = True
        k = PIC_W / W
        L, T = PIC_C[0] - PIC_W / 2, PIC_C[1] - ph_h / 2
        pad_r = Rectangle(width=u((sps["width"] - W) * k), height=u(sps["height"] * k), stroke_width=0,
                          fill_color=CORAL, fill_opacity=0.9).move_to(px(L + PIC_W, T), aligned_edge=UL)
        pad_b = Rectangle(width=u(W * k), height=u((sps["height"] - H) * k), stroke_width=0,
                          fill_color=CORAL, fill_opacity=0.9).move_to(px(L, T + ph_h), aligned_edge=UL)
        pads = VGroup(pad_r, pad_b)
        pads.check_ignore = True        # 写真の縁 (写真の一部)
        dims = mix(f"{sps['width']}×{sps['height']}", 40, CORAL).move_to(px(*DIM_C))
        ph.set_opacity(0)
        self.add(ph)
        self.play(FadeOut(panel), FadeOut(eq), ph.animate.set_opacity(1), run_time=0.8)
        self.play(FadeIn(pad_r, shift=LEFT * u(6)), FadeIn(pad_b, shift=UP * u(6)), FadeIn(dims, shift=LEFT * u(8)),
                  run_time=0.8)

        # ---- あとで 451×300 に切り取る ----
        self.at("cut", -0.1)
        self.play(pad_r.animate.shift(RIGHT * u(40)).set_opacity(0), pad_b.animate.shift(DOWN * u(40)).set_opacity(0),
                  retext(dims, mix(f"{W}×{H}", 40, INK)), run_time=0.9)
        self.remove(pads)

        # ---- AV1 はそのまま記録 ----
        self.at("exact", -0.1)
        self.play(dims.animate.set_color(YELLOW), pop(dims, 1.25, 0.7), run_time=0.7)
        self.wait(1.2)
        empty = DashedVMobject(RoundedRectangle(corner_radius=u(10), width=u(CHIP_W), height=u(CHIP_H),
                                                stroke_color=YELLOW, stroke_width=3), num_dashes=24)
        empty.move_to(px(col_x(cj), ROWS_Y["avif"]))
        self.play(ph.animate.set_opacity(0), FadeOut(dims), FadeIn(panel), run_time=0.8)
        self.remove(ph)
        self.play(Create(empty), run_time=0.6)
        self.at("none", -0.1)
        self.play(pop(empty, 1.2, 0.7), pop(chips["heic"]["clap"], 1.12, 0.7), run_time=0.7)

        # ---- mdat を開くと OBU が 3 つ ----
        self.at("mdat", -0.1)
        self.play(FadeOut(VGroup(panel, empty, d150)), FadeOut(VGroup(*seg_h.values(), hf, hfl, hm, hml, hd, tag_h)),
                  seg_a["mdat"].animate.set_fill("#6b7388"), run_time=0.8)
        self.play(pop(VGroup(seg_a["mdat"], ld), 1.04, 0.6), run_time=0.6)
        self.at("obu", -0.1)
        span = OBU_X1 - OBU_X0
        rest = span - TD_W - SEQ_W - 8
        xs = [OBU_X0, OBU_X0 + TD_W + 4, OBU_X0 + TD_W + SEQ_W + 8]
        ws = [TD_W, SEQ_W, rest]
        cols_o = ["#9aa3b5", YELLOW, "#6b7388"]
        obu_r = [RoundedRectangle(corner_radius=u(4 if i == 0 else 12), width=u(w), height=u(OBU_H), stroke_color=c,
                                  stroke_width=0 if i == 0 else 3, fill_color=c if i == 0 else CHIP_FILL, fill_opacity=1)
                 .move_to(px(x, OBU_Y), aligned_edge=LEFT) for i, (x, w, c) in enumerate(zip(xs, ws, cols_o))]
        obu_r[2].set_stroke(INK)
        lab_td = left_at(mix(f"区切り {ob_n[0]}", 36, INK), OBU_X0, OBU_Y - OBU_H / 2 - 40)
        lead_td = Line(px(OBU_X0 + TD_W / 2, OBU_Y - OBU_H / 2 - 22), px(OBU_X0 + TD_W / 2, OBU_Y - OBU_H / 2),
                       stroke_color=INK, stroke_width=2)
        lab_sq = mix(f"設定 {ob_n[1]}", 36, YELLOW).move_to(obu_r[1])
        lab_fr = mix(f"画像データ {fmt(ob_n[2])}", 40, INK).move_to(obu_r[2])
        tag_obu = mono("OBU", 40, YELLOW).move_to(px(1300, OBU_Y - OBU_H / 2 - 40))
        md_cp = seg_a["mdat"].copy()
        self.play(ReplacementTransform(md_cp, VGroup(*obu_r)), run_time=0.9)
        self.play(FadeIn(lab_td), Create(lead_td), FadeIn(lab_sq), FadeIn(lab_fr), FadeIn(tag_obu, shift=DOWN * u(8)),
                  run_time=0.6)
        obu_g = VGroup(*obu_r, lab_td, lead_td, lab_sq, lab_fr, tag_obu)

        # ---- 設定の OBU：中身は 10 バイト ----
        self.at("seq", -0.1)
        self.play(obu_r[1].animate.set_stroke(YELLOW, width=6), pop(VGroup(obu_r[1], lab_sq), 1.15, 0.7), run_time=0.7)
        self.at("ten", -0.1)
        cells, nums = VGroup(), VGroup()
        for i, b in enumerate(bits):
            x, y = bit_xy(i)
            cells.add(RoundedRectangle(corner_radius=u(6), width=u(BIT - 6), height=u(BIT + 4), stroke_width=0,
                                       fill_color="#262a35", fill_opacity=1).move_to(px(x, y)))
            nums.add(mono(str(b), 32, INK if b else DIM).move_to(px(x, y)))
        cells.check_ignore = True
        sq_cp = VGroup(obu_r[1].copy(), lab_sq.copy())
        sq_cp.check_ignore = True
        self.play(FadeOut(VGroup(*seg_a.values(), lf, lfl, lm, lml, ld, tag_a)),
                  FadeOut(obu_g), ReplacementTransform(sq_cp, cells), run_time=1.0)
        self.play(LaggedStart(*[FadeIn(t) for t in nums], lag_ratio=0.01), run_time=0.8)

        # ---- ビット単位で ----
        self.at("bits", -0.1)
        self.play(LaggedStart(*[pop(t, 1.4, 0.4) for t in nums], lag_ratio=0.012), run_time=1.3)

        # ---- 区切り ----
        self.at("many", -0.1)
        marks = VGroup()
        for k_, (nm, v, p, nb) in enumerate(fields):
            if p >= 80:
                continue
            for a, b in bit_runs(p, nb):
                x0 = bit_xy(a)[0] - BIT / 2 + 5
                x1 = bit_xy(b)[0] + BIT / 2 - 5
                y = bit_xy(a)[1] + BIT / 2 + 12
                marks.add(Line(px(x0, y), px(x1, y), stroke_color=BLUE if k_ % 2 == 0 else "#7fd18b", stroke_width=5))
        self.play(LaggedStart(*[Create(m) for m in marks], lag_ratio=0.05), run_time=1.5)

        def field_cells(nm):
            v, p, nb = F[nm]
            return [cells[i] for i in range(p, p + nb)], [nums[i] for i in range(p, p + nb)]

        def light(nm):
            cs, ts = field_cells(nm)
            return [c.animate.set_fill("#4a4220") for c in cs] + [t.animate.set_color(YELLOW) for t in ts]

        def over(nm, text, col=YELLOW):
            v, p, nb = F[nm]
            a, b = max(bit_runs(p, nb), key=lambda ab: ab[1] - ab[0])     # いちばん長く並んだ段の上に
            x = (bit_xy(a)[0] + bit_xy(b)[0]) / 2
            return mix(text, 34, col).move_to(px(x, bit_xy(a)[1] - BIT / 2 - 36))

        # ---- 静止画・幅・高さ ----
        self.at("still", -0.1)
        l_still = over("still_picture", "静止画")
        self.play(*light("still_picture"), FadeIn(l_still, shift=DOWN * u(6)), run_time=0.6)
        self.at("w", -0.1)
        l_w = over("max_frame_width_minus_1", f"幅 {F['max_frame_width_minus_1'][0]}")
        self.play(*light("max_frame_width_minus_1"), FadeIn(l_w, shift=DOWN * u(6)), run_time=0.6)
        self.at("h", -0.1)
        l_h = over("max_frame_height_minus_1", f"高さ {F['max_frame_height_minus_1'][0]}")
        self.play(*light("max_frame_height_minus_1"), FadeIn(l_h, shift=DOWN * u(6)), run_time=0.6)

        # ---- ＋1 で 451×300 ----
        self.at("plus", -0.1)
        nw = mix(str(F["max_frame_width_minus_1"][0]), 64, INK).move_to(px(830, NUM_Y))
        times = mix("×", 56, DIM).move_to(px(960, NUM_Y))
        nh = mix(str(F["max_frame_height_minus_1"][0]), 64, INK).move_to(px(1090, NUM_Y))
        self.play(ReplacementTransform(l_w.copy(), nw, path_arc=0.5), ReplacementTransform(l_h.copy(), nh, path_arc=-0.5),
                  FadeIn(times), run_time=0.9)
        self.wait(0.7)
        p1 = VGroup(mix("＋1", 34, YELLOW).move_to(px(830, PLUS_Y)), mix("＋1", 34, YELLOW).move_to(px(1090, PLUS_Y)))
        self.play(FadeIn(p1, shift=DOWN * u(8)), retext(nw, mix(str(W), 64, YELLOW)), retext(nh, mix(str(H), 64, YELLOW)),
                  run_time=0.8)

        # ---- 機能のスイッチ ----
        self.at("sw", -0.1)
        sws = VGroup()
        flies, cps_sw = [], []
        for nm, x in zip(SWITCHES, SW_X):
            on = F[nm][0] == 1
            pill = RoundedRectangle(corner_radius=u(25), width=u(104), height=u(50), stroke_color=YELLOW if on else DIM,
                                    stroke_width=3, fill_color="#4a4220" if on else "#262a35", fill_opacity=1)
            pill.move_to(px(x, SW_Y))
            knob = Circle(radius=u(18), stroke_width=0, fill_color=YELLOW if on else DIM, fill_opacity=1)
            knob.move_to(px(x + (26 if on else -26), SW_Y))
            g = VGroup(pill, knob)
            if nm in SW_NAMES:
                g.add(mix(SW_NAMES[nm], 32, INK).move_to(px(x, SW_Y + 60)))
            sws.add(g)
            i = F[nm][1]
            cp = nums[i].copy()
            cp.check_ignore = True
            self.add(cp)
            flies.append(cp.animate(path_arc=0.4).move_to(knob).set_opacity(0))
            flies.append(FadeIn(knob, scale=0.5))
            cps_sw.append(cp)
        self.play(*[a for nm in SWITCHES for a in light(nm)], run_time=0.5)
        self.play(*[FadeIn(VGroup(g[0], *g[2:])) for g in sws], *flies, run_time=1.0)   # つまみを板の上に
        self.remove(*cps_sw)

        # Z「ぎっしり」
        self.at("packed", 0.0)
        self.play(LaggedStart(*[pop(VGroup(c, t), 1.2, 0.4) for c, t in zip(cells, nums)], lag_ratio=0.01),
                  run_time=1.5)
        self.remove(cells)
        self.add(cells)
        self.bring_to_front(nums)

        # ---- 残りが画像データの本体 ----
        self.at("frame", -0.1)
        bits_g = VGroup(cells, nums, marks, l_still, l_w, l_h)
        self.play(FadeOut(VGroup(nw, nh, times, p1, sws)),
                  bits_g.animate.scale(0.1).move_to(obu_r[1].get_center()).set_opacity(0), run_time=0.8)
        self.remove(bits_g, *bits_g, cells, nums)
        obu_r[1].set_stroke(YELLOW, width=3)
        obu_r[2].set_stroke(YELLOW, width=5)
        lab_fr.set_color(YELLOW)
        self.play(FadeIn(obu_g), run_time=0.7)
        self.play(pop(VGroup(obu_r[2], lab_fr), 1.04, 0.6), run_time=0.6)

        self.at("s02_09", -0.1)
        ac = jp("算術符号で記録", 40, YELLOW).move_to(px((xs[2] + OBU_X1) / 2, OBU_Y + OBU_H / 2 + 50))
        self.play(FadeIn(ac, shift=UP * u(8)), run_time=0.7)

        # ---- 分割の話へ：画像データから写真が出る ----
        self.at("first", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        kk = 0.3
        view.scale(kk).move_to(obu_r[2]).set_opacity(0)
        self.add(view)
        self.play(FadeOut(VGroup(obu_g, ac)),
                  view.animate.scale(1 / kk).move_to(px(*PHOTO[0])).set_opacity(1), run_time=1.3)
        self.remove(obu_g, *obu_g)
        view.refresh()
        self.finish()
