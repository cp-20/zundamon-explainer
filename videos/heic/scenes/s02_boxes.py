import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import MAIN, boxes, file_bytes, fmt, rgb_decoded, size  # noqa: E402
from vlib.photoview import PhotoView  # noqa: E402
from zunda.fx import pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

STEP, ROW_Y, CHAR_DY, BSIZE = 76, (150, 320), 80, 44      # 16 バイトずつ 2 行 (WebP 編の S02 と同じ)
# ファイル全体の帯 (幅はバイト数に比例)
SX0, SX1, SY, SH = 60, 1860, 125, 64
LAB_Y = 52
# meta を開いた図 (2 人の間)
META = (450, 215, 1470, 700)
ROW_A_Y, NOTE_Y = 320, 395
IPRP = (480, 440, 1440, 680)
KIDS_Y = 610
SEG_COL = {"ftyp": YELLOW, "meta": BLUE, "mdat": "#4a5060"}
CHIP_FILL = "#1c1f27"
PHOTO = ((960, 386), 1040, 692)          # S03 の最初の写真


def bx(i):
    return 960 + STEP * (i % 16 - 7.5)


def by(i):
    return ROW_Y[i // 16]


def left_at(m, x, y):
    return m.move_to(px(x, y), aligned_edge=LEFT).set_y(px(0, y)[1])


def chip(name, c, w, h=72, col=BLUE):
    box = RoundedRectangle(corner_radius=u(12), width=u(w), height=u(h), stroke_color=col, stroke_width=3,
                           fill_color=CHIP_FILL, fill_opacity=1).move_to(px(*c))
    t = mono(name, 34, INK).move_to(box)
    g = VGroup(box, t)
    g.box, g.t = box, t
    return g


def frame(l, t, r, b, col, sw=3, rad=18):
    return RoundedRectangle(corner_radius=u(rad), width=u(r - l), height=u(b - t), stroke_color=col,
                            stroke_width=sw).move_to(px((l + r) / 2, (t + b) / 2))


class S02(PScene):
    def construct(self):
        fb = file_bytes(MAIN)
        head = fb[:32]
        total = size(MAIN)
        r = boxes(MAIN)
        tree = r["tree"]
        # ---- 実データの確認 ----
        assert [(b["type"], b["size"]) for b in tree] == [("ftyp", 24), ("meta", 385), ("mdat", 12959)]
        assert sum(b["size"] for b in tree) == total == 13368
        assert int.from_bytes(head[:4], "big") == 24 and head[4:8] == b"ftyp" and head[8:12] == b"heic"
        assert int.from_bytes(head[24:28], "big") == 385 and head[28:32] == b"meta"
        meta, mdat = tree[1], tree[2]
        kids_a = [b["type"] for b in meta["kids"] if b["type"] != "iprp"]
        assert kids_a == ["hdlr", "iloc", "iinf", "pitm"]
        iprp = next(b for b in meta["kids"] if b["type"] == "iprp")
        ipco = next(b for b in iprp["kids"] if b["type"] == "ipco")
        kids_p = [b["type"] for b in ipco["kids"]]
        assert kids_p == ["hvcC", "colr", "ispe", "clap", "pixi"]
        items = r["items"]
        assert len(items) == 1 and items[r["primary"]]["type"] == "hvc1"                # 画像 1 枚 (hvc1)
        ext = items[r["primary"]]["extents"]
        assert ext == [(417, 12951)] and ext[0][0] == mdat["body"] and sum(ext[0]) == total
        pct = round(mdat["size"] / total * 100)
        assert pct == 97

        def xb(b):
            return SX0 + (SX1 - SX0) * b / total

        title = jp("HEICの中身をのぞく", 72).move_to(px(960, 300))
        title.check_ignore = True   # S01 から引き継ぐ画面 (S01 側で十分長く出ている)
        self.add(title)

        # ---- 先頭からのぞく ----
        self.at("s02_01", -0.1)
        fname = mix(f"{MAIN}.heic　{fmt(total)} バイト", 32, DIM).move_to(px(960, 62))
        self.play(FadeOut(title, shift=UP * u(20)), FadeIn(fname, shift=DOWN * u(8)), run_time=0.6)

        self.at("hex", 0.0)
        hexes = VGroup(*[mono(f"{b:02X}", BSIZE).move_to(px(bx(i), by(i))) for i, b in enumerate(head)])
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(8)) for b in hexes], lag_ratio=0.04), run_time=1.4)

        def chars_of(i0, n, col):
            return VGroup(*[mono(chr(head[i]), 40, col).move_to(px(bx(i), by(i) + CHAR_DY)) for i in range(i0, i0 + n)])

        def fly(i0, n, target):
            cp = VGroup(*[hexes[i].copy() for i in range(i0, i0 + n)])
            cp.check_ignore = True
            return ReplacementTransform(cp, target, path_arc=-0.5)

        # ---- 大きさ ----
        self.at("size", -0.1)
        ul = underline(VGroup(*hexes[:4]), CYAN)
        self.play(*[hexes[i].animate.set_color(CYAN) for i in range(4)],
                  *[hexes[i].animate.set_color(DIM) for i in range(4, 32)], Create(ul), run_time=0.6)
        n24 = mix("24", 48, CYAN).move_to(px((bx(1) + bx(2)) / 2, ROW_Y[0] + CHAR_DY))
        self.play(fly(0, 4, n24), run_time=0.8)

        # ---- 名前 ftyp ----
        self.at("ftyp", -0.1)
        c_ftyp = chars_of(4, 4, YELLOW)
        self.play(*[hexes[i].animate.set_color(YELLOW) for i in range(4, 8)], run_time=0.4)
        self.play(LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_ftyp[i - 4]) for i in range(4, 8)],
                              lag_ratio=0.12), run_time=0.9)

        # ---- 中身の種類 heic ----
        self.at("heic", -0.1)
        c_heic = chars_of(8, 4, INK)
        self.play(*[hexes[i].animate.set_color(INK) for i in range(8, 12)], run_time=0.4)
        self.play(LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_heic[i - 8]) for i in range(8, 12)],
                              lag_ratio=0.12), run_time=0.9)

        # ---- 大きさと名前と中身：1 つの箱 ----
        self.at("box", -0.1)
        band1 = RoundedRectangle(corner_radius=u(12), width=u(STEP * 16 + 8), height=u(68), stroke_color=YELLOW,
                                 stroke_width=4).move_to(px(960, ROW_Y[0]))
        band2 = RoundedRectangle(corner_radius=u(12), width=u(STEP * 8 + 8), height=u(68), stroke_color=YELLOW,
                                 stroke_width=4).move_to(px((bx(16) + bx(23)) / 2, ROW_Y[1]))
        self.play(*[hexes[i].animate.set_color(INK) for i in range(12, 24)], Create(band1), Create(band2),
                  run_time=0.9)

        # ---- バイト列が縮んで、ファイル全体の帯に ----
        self.at("nest", -0.1)
        seg = {}
        for b in tree:
            x0, x1 = xb(b["pos"]), xb(b["pos"] + b["size"])
            seg[b["type"]] = Rectangle(width=u(x1 - x0), height=u(SH), stroke_width=0, fill_color=SEG_COL[b["type"]],
                                       fill_opacity=1).move_to(px(x0, SY), aligned_edge=LEFT)
        bytes_g = VGroup(hexes, n24, c_ftyp, c_heic, ul)
        lab_f = left_at(mix("ftyp 24", 32, YELLOW), SX0, LAB_Y)
        lead_f = Line(px(xb(12), LAB_Y + 20), px(xb(12), SY - SH / 2), stroke_color=YELLOW, stroke_width=2)
        lab_m = left_at(mix(f"meta {fmt(meta['size'])}", 32, BLUE), 250, LAB_Y)
        lead_m = Line(px(244, LAB_Y + 12), px(xb(meta["pos"] + meta["size"] / 2), SY - SH / 2), stroke_color=BLUE,
                      stroke_width=2)
        lab_d = mix(f"mdat {fmt(mdat['size'])}", 36, INK).move_to(px(960, SY))
        # バイト列が左端の数ピクセルへ縮むのと同時に、残りのファイル (meta・mdat) が右へ伸びる
        self.play(bytes_g.animate(rate_func=rate_functions.ease_in_out_cubic)
                  .stretch_to_fit_width(u(xb(32) - xb(0))).stretch_to_fit_height(u(SH))
                  .move_to(px((xb(0) + xb(32)) / 2, SY)).set_opacity(0),
                  ReplacementTransform(VGroup(band1, band2), seg["ftyp"], rate_func=rate_functions.ease_in_out_cubic),
                  FadeOut(fname),
                  Succession(Wait(0.7), GrowFromEdge(seg["meta"], LEFT, run_time=0.2),
                             GrowFromEdge(seg["mdat"], LEFT, run_time=0.9, rate_func=rate_functions.ease_out_cubic)),
                  run_time=1.8)
        self.remove(bytes_g, *bytes_g)
        self.play(Create(lead_f), Create(lead_m), FadeIn(lab_f), FadeIn(lab_m), FadeIn(lab_d, scale=0.9), run_time=0.5)
        strip = VGroup(*seg.values())

        # ---- meta が開く ----
        self.at("inner", -0.1)
        L, T, R, B = META
        fan = VGroup(Line(px(xb(meta["pos"]), SY + SH / 2), px(L, T), stroke_color=BLUE, stroke_width=2),
                     Line(px(xb(meta["pos"] + meta["size"]), SY + SH / 2), px(R, T), stroke_color=BLUE, stroke_width=2))
        panel = frame(L, T, R, B, BLUE)
        tag_meta = left_at(mono("meta", 32, BLUE), L + 32, T + 37)
        self.play(Create(fan), Create(panel), FadeIn(tag_meta), run_time=0.8)
        xs_a = [600, 840, 1080, 1320]
        chips_a = {nm: chip(nm, (x, ROW_A_Y), 224) for nm, x in zip(kids_a, xs_a)}
        il, it, ir, ib = IPRP
        iprp_box = frame(il, it, ir, ib, BLUE, rad=14)
        tag_iprp = left_at(mono("iprp", 32, BLUE), il + 30, it + 35)
        self.play(LaggedStart(*[FadeIn(c, shift=DOWN * u(10)) for c in chips_a.values()],
                              AnimationGroup(Create(iprp_box), FadeIn(tag_iprp)), lag_ratio=0.15), run_time=1.0)
        xs_p = [596, 778, 960, 1142, 1324]
        chips_p = {nm: chip(nm, (x, KIDS_Y), 170) for nm, x in zip(kids_p, xs_p)}
        self.play(LaggedStart(*[FadeIn(c, shift=DOWN * u(10)) for c in chips_p.values()], lag_ratio=0.12),
                  run_time=0.9)

        # Z「箱がいっぱい」
        self.at("many", 0.0)
        allc = list(chips_a.values()) + list(chips_p.values())
        self.play(LaggedStart(*[pop(c, 1.1, 0.4) for c in allc], lag_ratio=0.08), run_time=1.1)

        # ---- 目録 ----
        self.at("meta", -0.1)
        self.play(pop(tag_meta, 1.3, 0.7), run_time=0.7)

        def lit(c, on=True):
            return [c.box.animate.set_stroke(YELLOW if on else BLUE, width=5 if on else 3),
                    c.t.animate.set_color(YELLOW if on else INK)]

        self.at("iinf", -0.1)
        note_i = mix(f"画像 {len(items)}枚 ({items[r['primary']]['type']})", 32, YELLOW).move_to(px(xs_a[2], NOTE_Y))
        self.play(*lit(chips_a["iinf"]), FadeIn(note_i, shift=DOWN * u(6)), run_time=0.6)

        self.at("iloc", -0.1)
        x417 = xb(ext[0][0])
        arrow = CurvedArrow(px(xs_a[1], ROW_A_Y - 34), px(x417 + 6, SY + SH / 2 + 6), angle=PI / 5,
                            color=YELLOW, stroke_width=4, tip_length=u(18))
        span = Rectangle(width=u(xb(total) - x417 + 6), height=u(SH + 10), stroke_color=YELLOW, stroke_width=4)
        span.move_to(px((x417 + xb(total)) / 2, SY))
        note_l = left_at(mix(f"{ext[0][0]}バイト目から {fmt(ext[0][1])}バイト", 32, YELLOW), 440, LAB_Y)
        self.play(*lit(chips_a["iinf"], False), *lit(chips_a["iloc"]), Create(arrow), run_time=0.7)
        self.play(Create(span), FadeIn(note_l, shift=DOWN * u(6)), run_time=0.6)

        self.at("iprp", -0.1)
        self.play(*lit(chips_a["iloc"], False), iprp_box.animate.set_stroke(YELLOW, width=5),
                  tag_iprp.animate.set_color(YELLOW), run_time=0.5)
        self.play(*lit(chips_p["ispe"]), *lit(chips_p["colr"]), run_time=0.5)
        self.play(pop(chips_p["ispe"], 1.15, 0.6), pop(chips_p["colr"], 1.15, 0.6), run_time=0.6)

        # ---- 本体 mdat ----
        self.at("mdat", -0.1)
        gone = VGroup(fan, panel, tag_meta, *chips_a.values(), iprp_box, tag_iprp, *chips_p.values(), note_i, arrow,
                      span, note_l, lab_f, lead_f, lab_m, lead_m)
        self.play(FadeOut(gone), seg["mdat"].animate.set_fill("#6b7388"), run_time=0.8)
        self.at("body", 0.0)
        self.play(pop(VGroup(seg["mdat"], lab_d), 1.04, 0.6), run_time=0.6)
        self.at("ratio", -0.1)
        brace = Brace(seg["mdat"], DOWN, buff=u(10), color=YELLOW)
        p97 = mix(f"{pct}%", 64, YELLOW).move_to(px(960, 255))
        self.play(GrowFromCenter(brace), FadeIn(p97, shift=DOWN * u(10)), run_time=0.7)

        # Z「本体はどんな形？」
        self.at("what", 0.1)
        self.play(pop(p97, 1.15, 0.7), run_time=0.7)

        # ---- HEVC ----
        self.at("hevc", -0.1)
        card_c = (720, 450)
        card = RoundedRectangle(corner_radius=u(18), width=u(340), height=u(130), stroke_color=YELLOW, stroke_width=4,
                                fill_color=CHIP_FILL, fill_opacity=1).move_to(px(*card_c))
        card_t = mix("HEVC", 64, YELLOW).move_to(card)
        self.play(FadeOut(VGroup(brace, p97), shift=DOWN * u(10)), FadeIn(card, shift=DOWN * u(30)),
                  FadeIn(card_t, shift=DOWN * u(30)), run_time=0.8)
        self.at("h265", -0.1)
        h265 = mix("＝ H.265", 48, INK).move_to(px(card_c[0], 590))
        self.play(FadeIn(h265, shift=UP * u(8)), run_time=0.6)
        self.at("tv", -0.1)
        tv_c = (1200, 490)
        scr = RoundedRectangle(corner_radius=u(12), width=u(260), height=u(170), stroke_color=INK, stroke_width=5,
                               fill_color=CHIP_FILL, fill_opacity=1).move_to(px(*tv_c))
        legs = VGroup(*[Line(px(tv_c[0] + s * 55, tv_c[1] + 85), px(tv_c[0] + s * 85, tv_c[1] + 120), stroke_color=INK,
                             stroke_width=5) for s in (-1, 1)])
        tv_t = mix("4K 放送", 40, INK).move_to(px(*tv_c))
        tv = VGroup(scr, legs, tv_t)
        self.play(FadeIn(tv, shift=LEFT * u(20)), run_time=0.7)

        # Z「WebP と同じで動画の技術」
        self.at("same", 0.0)
        self.play(pop(VGroup(card, card_t), 1.1, 0.7), run_time=0.7)

        # ---- 式：HEIF の箱 ＋ HEVC の中身 ＝ HEIC ----
        self.at("eq", -0.1)
        self.play(FadeOut(VGroup(h265, tv)), run_time=0.6)
        t1 = mix("HEIFの箱", 56, BLUE)
        plus = mix("＋", 56, DIM)
        t2 = mix("HEVCの中身", 56, YELLOW)
        eqs = VGroup(*[Line(LEFT * u(20), RIGHT * u(20), stroke_color=DIM, stroke_width=5).shift(UP * u(d))
                       for d in (8, -8)])
        t3 = mix("HEIC", 64, INK)
        VGroup(t1, plus, t2, eqs, t3).arrange(RIGHT, buff=u(34)).move_to(px(960, 620))
        self.at("heif", -0.1)
        self.play(pop(VGroup(strip, lab_d), 1.03, 0.6), FadeIn(t1, shift=DOWN * u(20)), run_time=0.7)
        self.at("in", -0.1)
        cp = card_t.copy()
        cp.check_ignore = True
        self.play(FadeIn(plus), ReplacementTransform(cp, t2, path_arc=0.5), run_time=0.9)
        self.at("name", -0.1)
        self.play(FadeIn(eqs), FadeIn(t3, scale=0.8), run_time=0.6)
        self.play(pop(t3, 1.2, 0.6), run_time=0.6)

        # ---- 箱の話はあとで ----
        self.at("s02_11", 0.0)
        self.play(pop(t1, 1.12, 0.7), run_time=0.7)

        # ---- 本体の縮め方へ：HEVC の札から写真が出る ----
        self.at("first", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        k = 0.3
        view.scale(k).move_to(card).set_opacity(0)
        self.add(view)
        self.play(FadeOut(VGroup(strip, lab_d, card, card_t, t1, plus, t2, eqs, t3)),
                  view.animate.scale(1 / k).move_to(px(*PHOTO[0])).set_opacity(1), run_time=1.3)
        self.remove(strip, *strip)
        view.refresh()
        self.finish()
