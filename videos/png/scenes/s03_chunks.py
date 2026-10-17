import struct
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import chunks, file_bytes, fmt, info, pixels  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from scenes.s02_signature import RAW, SIG, bx, by, byte_mob, dump_final, hx, morph  # noqa: E402

# ---- 色 ----
C_LEN, C_TYPE, C_DATA, C_CRC = BLUE, PURPLE, "#f0a868", "#62d2b0"
CK = {"sig": DIM, "IHDR": BLUE, "IDAT": "#b7c0d6", "IEND": "#f0a868", "tEXt": YELLOW, "tIME": YELLOW}

# ---- 横一列に切り出した IHDR（25 バイト）----
SY = 330
SX0 = 222


def sx(k):
    seg = 0 if k < 4 else 1 if k < 8 else 2 if k < 21 else 3
    return SX0 + k * 58 + 28 * seg


# ---- ファイル全体の帯 ----
RIB_X0, RIB_W, RIB_Y, RIB_H = 310, 1300, 340, 110


def layout(items):
    """[(名前, バイト数)] → [(x0, 幅)]。細すぎるチャンクは最小幅にして、残りを長さに比例させる"""
    total = sum(n for _, n in items)
    tiny = {i for i, (_, n) in enumerate(items) if n / total * RIB_W < 10}
    mw = lambda nm: 7 if nm == "sig" else 10  # noqa: E731
    fixed = sum(mw(items[i][0]) for i in tiny)
    s = (RIB_W - fixed) / sum(n for i, (_, n) in enumerate(items) if i not in tiny)
    out, x = [], RIB_X0
    for i, (nm, n) in enumerate(items):
        w = mw(nm) if i in tiny else n * s
        out.append((x, w))
        x += w
    return out


def items_of(name):
    return [("sig", 8)] + [(c["type"], c["length"] + 12) for c in chunks(name)]


def make_rect(nm, x, w):
    gap = 2 if w > 20 else 0
    r = Rectangle(width=u(w - gap), height=u(RIB_H), stroke_width=0, fill_color=CK[nm], fill_opacity=1)
    return r.move_to(px(x + w / 2, RIB_Y))


def idat_label(x, w):
    return jp("IDAT", 36, BG).move_to(px(x + w / 2, RIB_Y)) if w > 110 else None


class S03(PScene):
    def construct(self):
        z = info("zundamon")
        ch = chunks("zundamon")
        ihdr = ch[0]
        assert ihdr["type"] == "IHDR" and ihdr["length"] == 13
        raw = file_bytes("zundamon")[8:33]  # 長さ4 + 種類4 + データ13 + CRC4
        assert raw == RAW[8:33]
        W_, H_ = int.from_bytes(raw[8:12], "big"), int.from_bytes(raw[12:16], "big")
        assert (W_, H_, raw[16], raw[17]) == (z["width"], z["height"], 8, 6) == (1082, 1594, 8, 6)
        assert int.from_bytes(raw[0:4], "big") == 13 and raw[4:8] == b"IHDR"

        # ---- S02 の最後の画面 ----
        B = dump_final()
        self.add(*B)

        # ---- S03_01：シグネチャの後ろ、最初のチャンクを切り出す ----
        self.at("s03_01", 0.1)
        self.at("chunk", -0.1)
        strip = [B[8 + k] for k in range(25)]
        self.play(*[Transform(strip[k], byte_mob(hx(raw[k]), sx(k), SY, 42, INK)) for k in range(25)],
                  *[B[i].animate.set_color(DIM) for i in range(8)], run_time=1.2)

        # Z「箱？ 中には何が？」：切り出した箱が拡大
        self.at("S03_02", 0.4)
        self.play(pop(VGroup(*strip), 1.05), run_time=0.7)

        # ---- S03_02：長さ・種類・データ・CRC ----
        segs = [("len", 0, 4, C_LEN, "長さ"), ("type", 4, 8, C_TYPE, "種類"), ("data", 8, 21, C_DATA, "データ"),
                ("crc", 21, 25, C_CRC, "CRC")]
        uls, lbls = {}, {}
        for key, a, b, col, name in segs:
            self.at(key)
            uls[key] = Line(px(sx(a) - 29, SY + 38), px(sx(b - 1) + 29, SY + 38), color=col, stroke_width=5)
            lbls[key] = (jp(name, 38, col) if key == "crc" else jp(name, 38, col)).move_to(
                px((sx(a) + sx(b - 1)) / 2, SY + 86))
            self.play(*[strip[k].animate.set_color(col) for k in range(a, b)], Create(uls[key]),
                      FadeIn(lbls[key], shift=DOWN * u(8)), run_time=0.6)

        # ---- S03_03：長さ 0D = 13、種類 = IHDR ----
        self.at("n13")
        cl = (sx(0) + sx(3)) / 2
        self.play(*[strip[k].animate.move_to(px(sx(3), SY)).set_opacity(0) for k in range(3)],
                  morph(strip[3], byte_mob("13", cl, SY, 56, C_LEN)),
                  retext(lbls["data"], mix("データ（13バイト）", 38, C_DATA)), run_time=0.9)
        self.at("ihdr")
        self.play(*[morph(strip[4 + i], byte_mob(c, sx(4 + i), SY, 56, C_TYPE)) for i, c in enumerate("IHDR")],
                  run_time=0.9)

        # ---- S03_04：データ13バイト = 幅・高さ・ビット数・色の形式 ----
        def merge(ks, text, color):
            cx = (sx(ks[0]) + sx(ks[-1])) / 2
            new = byte_mob(text, cx, SY, 56, color)
            return [morph(strip[ks[0]], new)] + [strip[k].animate.move_to(new.get_center()).set_opacity(0)
                                                 for k in ks[1:]], cx

        self.at("s03_04", 0.1)
        self.play(*[strip[k].animate.set_color(DIM) for k in (18, 19, 20)], run_time=0.5)
        self.at("w")
        a, cx_w = merge([8, 9, 10, 11], str(W_), C_DATA)
        fl_w = jp("幅", 36, C_DATA).move_to(px(cx_w, SY + 86))
        self.play(*a, FadeOut(lbls["data"]), FadeIn(fl_w, shift=DOWN * u(8)), run_time=0.8)
        self.at("h")
        a, cx_h = merge([12, 13, 14, 15], str(H_), C_DATA)
        fl_h = jp("高さ", 36, C_DATA).move_to(px(cx_h, SY + 86))
        self.play(*a, FadeIn(fl_h, shift=DOWN * u(8)), run_time=0.8)
        # Z「僕の画像の大きさなのだ！」：幅と高さが拡大
        self.at("S03_06", 0.2)
        self.play(pop(strip[8], 1.35), pop(strip[12], 1.35), run_time=0.7)
        self.at("depth")
        a, cx_d = merge([16], str(raw[16]), C_DATA)
        fl_d = jp("ビット数", 34, C_DATA).move_to(px(sx(16), SY + 150))
        tick_d = Line(px(sx(16), SY + 46), px(sx(16), SY + 122), color=C_DATA, stroke_width=3)
        self.play(*a, FadeIn(fl_d, shift=DOWN * u(8)), Create(tick_d), run_time=0.6)
        self.at("ctype")
        a, cx_c = merge([17], str(raw[17]), C_DATA)
        fl_c = jp("色の形式", 34, C_DATA).move_to(px(sx(17) - 14 + 30, SY + 86), aligned_edge=LEFT)
        rgb = mix("6 ＝ RGB＋透明度", 56, INK).move_to(px(960, 620))
        self.play(*a, FadeIn(fl_c, shift=DOWN * u(8)), FadeIn(rgb, shift=UP * u(10)), run_time=0.8)
        self.at("four")
        bpp = z["bpp"]
        assert bpp == 4
        rgb4 = mix("6 ＝ RGB＋透明度 → 1画素 4バイト", 52, INK).move_to(px(960, 620))
        self.play(retext(rgb, rgb4), run_time=0.8)

        # ---- S03_05：Z「大きさまで書いてある」----
        self.at("s03_05", 0.15)
        self.play(*[B[i].animate.set_color(INK) for i in range(8)], pop(strip[8], 1.2), pop(strip[12], 1.2),
                  run_time=0.7)

        # ---- S03_06：ファイル全体の帯へ ----
        self.at("s03_06", 0.1)
        decor = VGroup(*uls.values(), lbls["len"], lbls["type"], lbls["crc"], fl_w, fl_h, fl_d, fl_c, tick_d, rgb)
        rest = VGroup(*[B[i] for i in list(range(8)) + list(range(33, 64))])
        self.play(FadeOut(decor), FadeOut(rest), run_time=0.7)
        items = items_of("zundamon")
        assert sum(n for _, n in items) == len(file_bytes("zundamon"))
        lay = layout(items)
        rects = [make_rect(nm, x, w) for (nm, _), (x, w) in zip(items, lay)]
        labels = [idat_label(x, w) if nm == "IDAT" else None for (nm, _), (x, w) in zip(items, lay)]
        self.at("ribbon", -0.2)
        ih_pos = px(lay[1][0] + lay[1][1] / 2, RIB_Y)
        strip_all = [strip[k] for k in range(25)]
        self.play(*[s.animate.move_to(ih_pos).scale(0.1).set_opacity(0) for s in strip_all],
                  FadeIn(rects[0]), FadeIn(rects[1]),
                  LaggedStart(*[GrowFromEdge(r, LEFT) for r in rects[2:]], lag_ratio=0.12), run_time=1.6)
        self.add(*[l for l in labels if l])
        self.play(*[FadeIn(l) for l in labels if l], run_time=0.4)
        # 細いチャンクは引き出しラベル
        L_Y = 225
        ihdr_lbl = jp("IHDR", 34, CK["IHDR"]).move_to(px(RIB_X0 - 70, L_Y))
        ihdr_ld = Line(px(RIB_X0 - 70, L_Y + 24), px(lay[1][0] + lay[1][1] / 2, RIB_Y - RIB_H / 2 - 2), color=CK["IHDR"],
                       stroke_width=2.5)
        iend_x = lay[-1][0] + lay[-1][1] / 2
        iend_lbl = jp("IEND", 34, CK["IEND"]).move_to(px(iend_x - 6, L_Y))
        iend_ld = Line(px(iend_x - 6, L_Y + 24), px(iend_x, RIB_Y - RIB_H / 2 - 2), color=CK["IEND"], stroke_width=2.5)
        self.play(FadeIn(ihdr_lbl), Create(ihdr_ld), FadeIn(iend_lbl), Create(iend_ld), run_time=0.5)

        # ---- S03_07：ほとんど IDAT ----
        self.at("most")
        idat_ix = [i for i, (nm, _) in enumerate(items) if nm == "IDAT"]
        assert len(idat_ix) == 6
        idat_bytes = sum(items[i][1] for i in idat_ix)
        pct = idat_bytes / sum(n for _, n in items) * 100
        pct_lbl = mix(f"IDAT：ファイルの {pct:.2f}%", 36, CK["IDAT"]).move_to(px(960, RIB_Y + 105))
        self.play(*[r.animate.set_opacity(0.3) for i, r in enumerate(rects) if i not in idat_ix],
                  *[pop(rects[i], 1.0 + 0.0) for i in ()],
                  FadeIn(pct_lbl, shift=UP * u(8)), run_time=0.7)

        # ---- S03_08：6つの IDAT → 1本 ----
        self.at("six")
        lens = [chunks("zundamon")[i - 1]["length"] for i in idat_ix]
        assert sum(lens) == 332957 == z["idat_bytes"] if "idat_bytes" in z else sum(lens) == 332957
        GAP, BY = 18, 650
        SC = (940 - 5 * GAP) / sum(lay[i][1] for i in idat_ix)
        wid = [lay[i][1] * SC for i in idat_ix]
        total_w = sum(wid) + GAP * 5
        xs, x = [], 960 - total_w / 2
        for w in wid:
            xs.append(x + w / 2)
            x += w + GAP
        cps = []
        for k, i in enumerate(idat_ix):
            c = rects[i].copy()
            c.check_ignore = True
            cps.append(c)
        self.add(*cps)
        nums = [jp(fmt(L), 30, CK["IDAT"]).move_to(px(xs[k], BY + 80 if k < 5 else BY - 80)) for k, L in enumerate(lens)]
        self.play(*[c.animate(path_arc=-PI / 6).stretch_to_fit_width(u(wid[k] - 2)).move_to(px(xs[k], BY))
                    for k, c in enumerate(cps)], FadeOut(pct_lbl),
                  run_time=0.8)
        for c in cps:
            c.check_ignore = False
        self.play(LaggedStart(*[FadeIn(n, shift=UP * u(6)) for n in nums], lag_ratio=0.08), run_time=0.6)
        self.at("join")
        bar_x0 = 960 - sum(wid) / 2
        big = mix(f"{fmt(sum(lens))} バイト", 56, INK).move_to(px(960, BY + 150))
        pos = bar_x0
        anims = []
        for k, c in enumerate(cps):
            anims.append(c.animate.stretch_to_fit_width(u(wid[k])).move_to(px(pos + wid[k] / 2, BY)))
            pos += wid[k]
        self.play(*anims, *[FadeOut(n) for n in nums], FadeIn(big, shift=UP * u(8)), run_time=1.0)
        self.play(pop(big, 1.15), run_time=0.5)
        # Z「なんで分けているのだ？」：1本の帯が拡大 → 書く側の都合：切れ目が現れ、意味はないので元に戻る
        self.at("S03_12", 0.3)
        self.play(pop(VGroup(*cps), 1.04), run_time=0.7)
        G = 10
        gx0 = bar_x0 - 5 * G / 2
        self.at("S03_13", 0.4)
        self.play(*[c.animate.move_to(px(gx0 + sum(wid[:k]) + k * G + wid[k] / 2, BY)) for k, c in enumerate(cps)],
                  run_time=0.6)
        self.at("S03_13", 3.4)
        self.play(*[c.animate.move_to(px(bar_x0 + sum(wid[:k]) + wid[k] / 2, BY)) for k, c in enumerate(cps)],
                  run_time=0.6)
        self.at("iend")
        iend_note = jp("ここで終わり", 34, CK["IEND"]).move_to(px(iend_x - 90, L_Y - 60))
        self.play(rects[-1].animate.set_opacity(1), pop(iend_lbl, 1.3), FadeIn(iend_note, shift=DOWN * u(8)),
                  run_time=0.7)

        # ---- S03_09：飛ばしてもいいチャンク ----
        self.at("s03_09", 0.0)
        self.play(FadeOut(VGroup(*cps, big)), FadeOut(iend_note),
                  *[r.animate.set_opacity(1) for r in rects], run_time=0.8)

        # ---- S03_10：tEXt と tIME を入れた本物のファイル ----
        self.at("s03_10", 0.1)
        mch = chunks("zundamon_meta")
        assert [c["type"] for c in mch[:4]] == ["IHDR", "tEXt", "tIME", "IDAT"]
        kw, txt = mch[1]["data"].split(b"\0")
        yy, mo, dd, hh, mi, ss = struct.unpack(">HBBBBB", mch[2]["data"])
        mitems = items_of("zundamon_meta")
        assert sum(n for _, n in mitems) == len(file_bytes("zundamon_meta"))

        def relayout(item_list, mapping):
            """mapping: 新しい並びの各位置に対応する既存 index（なければ None）。新規なら矩形を作って返す"""
            lay_ = layout(item_list)
            anims, new = [], {}
            for j, ((nm, _), (x, w)) in enumerate(zip(item_list, lay_)):
                tgt = make_rect(nm, x, w)
                if mapping[j] is None:
                    new[j] = tgt
                else:
                    anims.append(Transform(rects[mapping[j]], tgt))
                    if labels[mapping[j]] is not None:
                        anims.append(labels[mapping[j]].animate.move_to(px(x + w / 2, RIB_Y)))
            return anims, new, lay_

        # tEXt を割り込ませる
        it1 = mitems[:2] + [mitems[2]] + [("sig_dummy", 0)] if False else None
        self.at("text")
        items_a = [mitems[0], mitems[1], mitems[2]] + [it for it in mitems[4:]]  # sig IHDR tEXt IDAT.. IEND
        assert [n for n, _ in items_a][:3] == ["sig", "IHDR", "tEXt"]
        map_a = [0, 1, None] + list(range(2, len(rects)))
        anims, new, lay_a = relayout(items_a, map_a)
        text_rect = new[2]
        text_rect.shift(DOWN * u(0))
        text_lbl = jp("tEXt", 34, YELLOW).move_to(px(RIB_X0 + 50, L_Y))
        text_ld = Line(px(RIB_X0 + 50, L_Y + 24), px(lay_a[2][0] + lay_a[2][1] / 2, RIB_Y - RIB_H / 2 - 2), color=YELLOW,
                       stroke_width=2.5)
        t_name = jp("tEXt", 48, YELLOW).move_to(px(470, 580), aligned_edge=LEFT)
        t_val = jp(f'{kw.decode()} = "{txt.decode()}"', 32, INK).next_to(t_name, RIGHT, buff=u(30))
        self.play(*anims, FadeIn(text_rect, shift=DOWN * u(60)), FadeIn(text_lbl), Create(text_ld),
                  FadeIn(t_name, shift=UP * u(8)), FadeIn(t_val, shift=UP * u(8)), run_time=1.0)
        rects.insert(2, text_rect)
        labels.insert(2, None)
        # tIME
        self.at("time")
        map_b = [0, 1, 2, None] + list(range(3, len(rects)))
        anims, new, lay_b = relayout(mitems, map_b)
        time_rect = new[3]
        time_lbl = jp("tIME", 34, YELLOW).move_to(px(RIB_X0 + 150, L_Y))
        time_ld = Line(px(RIB_X0 + 150, L_Y + 24), px(lay_b[3][0] + lay_b[3][1] / 2, RIB_Y - RIB_H / 2 - 2), color=YELLOW,
                       stroke_width=2.5)
        m_name = jp("tIME", 48, YELLOW).move_to(px(470, 680), aligned_edge=LEFT)
        m_val = jp(f"{yy}-{mo:02d}-{dd:02d} {hh:02d}:{mi:02d}:{ss:02d}", 34, INK).next_to(m_name, RIGHT, buff=u(30))
        self.play(*anims, FadeIn(time_rect, shift=DOWN * u(60)), FadeIn(time_lbl), Create(time_ld),
                  FadeIn(m_name, shift=UP * u(8)), FadeIn(m_val, shift=UP * u(8)), run_time=1.0)
        rects.insert(3, time_rect)
        labels.insert(3, None)

        # Z「知らない箱が増えた」：tEXt・tIME が拡大
        self.at("S03_18", 0.3)
        self.play(pop(VGroup(t_name, m_name), 1.12), pop(VGroup(text_lbl, time_lbl), 1.3), run_time=0.7)

        # ---- S03_11：1文字目が小文字 = なくてもよい ----
        self.at("s03_11", 0.0)
        names = ["IHDR", "IDAT", "IEND", "tEXt", "tIME"]
        ROW = [500 + 80 * k for k in range(5)]
        NX = 600

        def nm_mob(name, y, colored=False):
            col = (YELLOW if name[0].islower() else BLUE)
            m = jp(name, 64, INK, t2c={"[0:1]": col}) if colored else jp(name, 64, INK)
            return m.move_to(px(NX, y), aligned_edge=LEFT)

        name_mobs = {n: nm_mob(n, ROW[k]) for k, n in enumerate(names)}
        self.play(FadeOut(t_val), FadeOut(m_val),
                  Transform(t_name, name_mobs["tEXt"]), Transform(m_name, name_mobs["tIME"]),
                  *[FadeIn(name_mobs[n], shift=UP * u(8)) for n in ("IHDR", "IDAT", "IEND")], run_time=1.0)
        self.at("case")
        # 名前の1文字目: 大文字は BLUE、小文字は YELLOW
        objs = {"IHDR": name_mobs["IHDR"], "IDAT": name_mobs["IDAT"], "IEND": name_mobs["IEND"],
                "tEXt": t_name, "tIME": m_name}
        for n in names:
            assert (ord(n[0]) & 0x20 != 0) == n[0].islower()
        self.play(*[morph(objs[n], nm_mob(n, ROW[k], True)) for k, n in enumerate(names)], run_time=0.7)
        self.play(*[pop(objs[n], 1.12) for n in names], run_time=0.6)
        need = [jp("なくてはならない", 32, BLUE).move_to(px(960, ROW[0] + 2), aligned_edge=LEFT)]
        notes = VGroup(
            jp("必須", 42, BLUE).move_to(px(960, ROW[0]), aligned_edge=LEFT),
            jp("必須", 42, BLUE).move_to(px(960, ROW[1]), aligned_edge=LEFT),
            jp("必須", 42, BLUE).move_to(px(960, ROW[2]), aligned_edge=LEFT),
            jp("なくても絵は描ける", 42, YELLOW).move_to(px(960, ROW[3]), aligned_edge=LEFT),
            jp("なくても絵は描ける", 42, YELLOW).move_to(px(960, ROW[4]), aligned_edge=LEFT))
        self.play(LaggedStart(*[FadeIn(n, shift=LEFT * u(10)) for n in notes], lag_ratio=0.2), run_time=1.0)

        # ---- S03_12：長さを読んで飛ばす ----
        self.at("s03_12", 0.0)
        BLY = 650
        bw, bgap = 220, 40
        bx0 = 960 - (4 * bw + 3 * bgap) / 2
        bcx = [bx0 + bw / 2 + k * (bw + bgap) for k in range(4)]
        blk_ix = [1, 2, 3, 4]  # IHDR tEXt tIME IDAT(1)
        blk_nm = ["IHDR", "tEXt", "tIME", "IDAT"]
        assert [items_of("zundamon_meta")[i][0] for i in (1, 2, 3, 4)] == blk_nm
        mlens = [mch[k]["length"] for k in range(4)]
        blocks, blabels, blens = [], [], []
        for k in range(4):
            r = Rectangle(width=u(bw), height=u(110), stroke_width=0, fill_color=CK[blk_nm[k]], fill_opacity=1)
            r.move_to(px(bcx[k], BLY))
            blocks.append(r)
            blabels.append(jp(blk_nm[k], 38, BG).move_to(px(bcx[k], BLY)))
            blens.append(mix(f"長さ {fmt(mlens[k])}", 32, DIM).move_to(px(bcx[k], BLY + 88)))
        self.play(FadeOut(VGroup(*objs.values(), notes)),
                  *[TransformFromCopy(rects[blk_ix[k]], blocks[k]) for k in range(4)],
                  *[FadeIn(l, shift=UP * u(6)) for l in blabels], *[FadeIn(l, shift=UP * u(6)) for l in blens],
                  run_time=0.8)
        cur_y = BLY - 95

        def cursor_at(k):
            return px(bcx[k] - bw / 2 + 14, cur_y)

        cur = Triangle(fill_color=YELLOW, fill_opacity=1, stroke_width=0).scale(u(20)).rotate(PI)
        cur.move_to(cursor_at(0))
        self.add(cur)
        self.play(FadeIn(cur, shift=DOWN * u(14)), blens[0].animate.set_color(YELLOW), run_time=0.4)

        def hop(k0, k1, rt):
            arr = CurvedArrow(cursor_at(k0) + UP * u(24), cursor_at(k1) + UP * u(24), angle=-PI / 2, color=YELLOW,
                              stroke_width=3, tip_length=u(14))
            return arr, cur.animate(path_arc=-PI / 2).move_to(cursor_at(k1)), rt

        arr0, an0, _ = hop(0, 1, 0.6)
        self.play(an0, Create(arr0), run_time=0.6)
        self.at("skip")
        self.play(blens[1].animate.set_color(YELLOW), pop(blens[1], 1.25), run_time=0.6)
        arr1, an1, _ = hop(1, 2, 0.8)
        self.play(an1, Create(arr1), blocks[1].animate.set_opacity(0.3), blabels[1].animate.set_opacity(0.5),
                  run_time=0.9)
        self.play(blens[2].animate.set_color(YELLOW), pop(blens[2], 1.25), run_time=0.5)
        arr2, an2, _ = hop(2, 3, 0.8)
        self.play(an2, Create(arr2), blocks[2].animate.set_opacity(0.3), blabels[2].animate.set_opacity(0.5),
                  run_time=0.8)

        # ---- S03_13：長さが先頭 → 絵も同じ ----
        self.at("s03_13", 0.1)
        self.play(*[pop(blens[k], 1.2) for k in (0, 1, 2)], run_time=0.7)
        a, b = pixels("zundamon"), pixels("zundamon_meta")
        assert a.shape == b.shape and (a == b).all()
        self.at("same", -1.2)
        # objs / t_name / m_name は S03_12 で消え済み（ここに入れると FadeOut が一瞬再表示してしまう）
        ribbon_all = VGroup(*rects, *[l for l in labels if l], ihdr_lbl, ihdr_ld, iend_lbl, iend_ld, text_lbl, text_ld,
                            time_lbl, time_ld, *blocks, *blabels, *blens, cur, arr0, arr1, arr2)
        im1, im2 = png_mob(a, 660), png_mob(b, 660)
        im1.move_to(px(700, 460))
        im2.move_to(px(1220, 460))
        eqs = jp("＝", 80, YELLOW).move_to(px(960, 460))
        c1 = jp("zundamon.png", 30, DIM).move_to(px(700, 815))
        c2 = jp("zundamon_meta.png", 30, DIM).move_to(px(1220, 815))
        self.play(FadeOut(ribbon_all), FadeIn(im1, scale=0.96), FadeIn(im2, scale=0.96), FadeIn(c1), FadeIn(c2),
                  run_time=1.0)
        self.at("same")
        self.play(FadeIn(eqs, scale=1.4), run_time=0.5)
        self.at(self.tl["duration"] - 1.1)
        self.play(FadeOut(Group(im1, im2, eqs, c1, c2)), run_time=1.0)
        self.finish()
