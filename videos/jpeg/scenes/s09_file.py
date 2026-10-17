import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import ZIGZAG, file_bytes, qtable, summary  # noqa: E402
from zunda.fx import Shake, pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import STAGE_COL  # noqa: E402

NAME = "cat_q80"
BYTE_COL = "#c3c8d4"
QCOL, SCOL = STAGE_COL["quant"], STAGE_COL["code"]
# 16進ダンプ
COLS, STEP, RH, DX0, DY0, WIN = 12, 66, 48, 960 - 5.5 * 66, 140, 8
NROWS = 56
# 全体の帯
BAR_X0, BAR_W, BAR_Y, BAR_H = 460, 1000, 370, 60
# 本体の中のようす
SN_Y, SN_STEP = 700, 70


def hx(v):
    return f"{v:02X}"


class S09(PScene):
    def construct(self):
        data = file_bytes(NAME)
        S = summary(NAME)
        segs = S["segments"]
        sos = next(s for s in segs if s["name"] == "SOS")
        scan0, scan_n = sos["scan_offset"], S["scan_bytes"]
        scan = data[scan0:scan0 + scan_n]
        assert data[-2:] == b"\xff\xd9" and data[:2] == b"\xff\xd8"
        marks = [s["offset"] for s in segs]          # 区切りの位置（FF xx）
        assert all(data[o] == 0xFF for o in marks)
        dqt0 = next(s["offset"] for s in segs if s["name"] == "DQT")
        sof0 = next(s["offset"] for s in segs if s["name"] == "SOF0")
        dhts = [s["offset"] for s in segs if s["name"] == "DHT"]
        assert len(dhts) == 4 and all(data[o + 1] == 0xC4 for o in dhts)
        assert data[dqt0 + 1] == 0xDB and data[sof0 + 1] == 0xC0 and data[sos["offset"] + 1] == 0xDA

        # ---- 16進ダンプ（行ごとに、位置はトラッカーで滑らかに動かす）----
        rows = VGroup()
        for r in range(NROWS):
            row = VGroup(*[mono(hx(data[r * COLS + c]), 34, BYTE_COL).move_to(px(DX0 + STEP * c, 0))
                           for c in range(COLS)])
            row._y = 0.0
            rows.add(row)
        pos = ValueTracker(-WIN)
        pos.check_ignore = True
        gl = ValueTracker(1)
        gl.check_ignore = True

        def byte(o):
            return rows[o // COLS][o % COLS]

        def layout(_=None):
            p = pos.get_value()
            for i, row in enumerate(rows):
                rel = i - p
                y = DY0 + RH * rel - 20 * (1 - gl.get_value())
                row.shift(DOWN * u(y - row._y))
                row._y = y
                op = float(np.clip(rel + 1, 0, 1) * np.clip(WIN - rel, 0, 1)) * gl.get_value()
                row.set_opacity(op)
            return None

        pos.add_updater(layout)
        layout()
        self.add(pos, gl, *rows)

        def scroll(p, rt):
            return pos.animate(run_time=rt, rate_func=smooth).set_value(p)

        # ---- 先頭が流れるように現れる ----
        self.at("s09_01")
        self.play(scroll(0, self.until("open")), run_time=self.until("open"))

        # ---- 区切り FF xx が黄色に ----
        self.at("soi", -0.1)
        vis = [o for o in marks if o < NROWS * COLS]
        self.play(LaggedStart(*[AnimationGroup(byte(o).animate.set_color(YELLOW), byte(o + 1).animate.set_color(YELLOW))
                                for o in vis], lag_ratio=0.12), run_time=1.6)
        self.at("start", -0.1)
        start_lbl = jp("始まり", 38, YELLOW).move_to(px(DX0 + STEP * 0.5, DY0 - 56))
        self.play(pop(VGroup(byte(0), byte(1)), 1.5, 0.7), FadeIn(start_lbl, shift=DOWN * u(8)), run_time=0.7)

        # ---- DQT：中の 64 バイトが 8×8 の表に ----
        self.at("dqt", -0.1)
        self.play(FadeOut(start_lbl), pop(VGroup(byte(dqt0), byte(dqt0 + 1)), 1.5, 0.7), run_time=0.7)
        self.at("table", -0.1)
        t0 = dqt0 + 5                                    # FF DB, 長さ 2 バイト, 表の番号 1 バイトのあと
        raw = list(data[t0:t0 + 64])
        assert data[t0 - 1] == 0 and len(raw) == 64
        Q = np.zeros((8, 8), int)
        for k, (r, c) in enumerate(ZIGZAG):
            Q[r, c] = raw[k]
        assert np.array_equal(Q, qtable(NAME, 0))
        CELL, GX, GY = 46, 960, 705
        gp = lambda r, c: px(GX + CELL * (c - 3.5), GY + CELL * (r - 3.5))  # noqa: E731
        frame = VGroup(*[Square(side_length=u(CELL), stroke_width=1.5, stroke_color="#333846")
                         .move_to(gp(r, c)) for r in range(8) for c in range(8)])
        src = [byte(t0 + k) for k in range(64)]
        self.play(*[b.animate.set_color(QCOL) for b in src], FadeIn(frame), run_time=0.6)
        flies, nums = [], []
        for k, (r, c) in enumerate(ZIGZAG):
            f = src[k].copy()
            f.check_ignore = True
            n = mono(str(Q[r, c]), 26, QCOL).move_to(gp(r, c))
            flies.append(f)
            nums.append(n)
        self.add(*flies)
        self.play(LaggedStart(*[Transform(f, n) for f, n in zip(flies, nums)], lag_ratio=0.03), run_time=2.4)
        self.remove(*flies)
        self.add(*nums)
        table = VGroup(frame, *nums)
        self.at("same", -0.1)
        self.play(*[n.animate.set_color(YELLOW) for n in nums], run_time=0.6)

        # ---- SOF0：大きさと、色の間引き方 ----
        self.at("sof", -0.1)
        self.play(FadeOut(table, shift=DOWN * u(20)), *[b.animate.set_color(BYTE_COL) for b in src],
                  scroll(sof0 // COLS, 0.9), run_time=0.9)
        self.play(pop(VGroup(byte(sof0), byte(sof0 + 1)), 1.5, 0.6), run_time=0.6)
        self.at("size", -0.1)
        hh, ww = int.from_bytes(data[sof0 + 5:sof0 + 7], "big"), int.from_bytes(data[sof0 + 7:sof0 + 9], "big")
        assert (ww, hh) == (S["width"], S["height"]) == (451, 300)
        ul_h = underline(VGroup(byte(sof0 + 5), byte(sof0 + 6)), YELLOW)
        ul_w = underline(VGroup(byte(sof0 + 7), byte(sof0 + 8)), YELLOW)
        read = jp(f"高さ {hh}　幅 {ww}", 40, YELLOW).move_to(px(960, 545))
        self.play(Create(ul_h), Create(ul_w), FadeIn(read, shift=UP * u(8)), run_time=0.7)
        self.at("samp", -0.1)
        comps = S["comps"]
        sb = [data[sof0 + 10 + 3 * i + 1] for i in range(3)]
        assert [(b >> 4, b & 15) for b in sb] == [(c["h"], c["v"]) for c in comps] == [(2, 2), (1, 1), (1, 1)]
        samp_ul = VGroup(*[underline(byte(sof0 + 10 + 3 * i + 1), YELLOW) for i in range(3)])
        read2 = jp(f"Y は {sb[0] >> 4}×{sb[0] & 15}、Cb・Cr は {sb[1] >> 4}", 40, YELLOW).move_to(read)
        self.play(FadeOut(VGroup(ul_h, ul_w)), Create(samp_ul), Transform(read, read2), run_time=0.7)

        # ---- DHT：4つ ----
        self.at("dht", -0.1)
        self.play(FadeOut(VGroup(samp_ul, read)), scroll(dhts[0] // COLS, 0.6), run_time=0.6)
        for o in dhts[:2]:
            self.play(pop(VGroup(byte(o), byte(o + 1)), 1.5, 0.5), run_time=0.5)
        self.play(scroll(dhts[2] // COLS - 2, 0.6), run_time=0.6)
        for o in dhts[2:]:
            self.play(pop(VGroup(byte(o), byte(o + 1)), 1.5, 0.5), run_time=0.5)

        # ---- SOS：このあとが本体 ----
        self.at("sos", -0.1)
        self.play(scroll(sos["offset"] // COLS - 3, 0.8), run_time=0.8)
        self.play(pop(VGroup(byte(sos["offset"]), byte(sos["offset"] + 1)), 1.5, 0.6), run_time=0.6)

        # ---- 本体：ファイル全体の帯 ----
        self.at("data", -0.1)
        total = len(data)
        bx = lambda o: BAR_X0 + BAR_W * o / total  # noqa: E731
        head = Rectangle(width=u(bx(scan0) - BAR_X0), height=u(BAR_H), stroke_width=0, fill_color=YELLOW, fill_opacity=1)
        head.move_to(px((BAR_X0 + bx(scan0)) / 2, BAR_Y))
        body = Rectangle(width=u(bx(scan0 + scan_n) - bx(scan0)), height=u(BAR_H), stroke_width=0, fill_color=SCOL,
                         fill_opacity=0.85)
        body.move_to(px((bx(scan0) + bx(scan0 + scan_n)) / 2, BAR_Y))
        pct = round(100 * scan_n / total)
        body_lbl = jp(f"本体 {pct}%", 40, SCOL).move_to(px((bx(scan0) + bx(scan0 + scan_n)) / 2, BAR_Y + 62))
        scan_bytes = [byte(o) for o in range(scan0, NROWS * COLS)]
        self.play(*[b.animate.set_color(SCOL) for b in scan_bytes], run_time=0.5)
        self.play(gl.animate.set_value(0), FadeIn(head), GrowFromEdge(body, LEFT), FadeIn(body_lbl, shift=UP * u(8)),
                  run_time=1.3)
        pos.remove_updater(layout)
        self.remove(pos, gl, *rows)
        self.at("most", -0.1)
        self.play(pop(body_lbl, 1.2, 0.6), run_time=0.6)

        # ---- 本体の中の FF ----
        idx = [i for i in range(len(scan) - 1) if scan[i] == 0xFF and scan[i + 1] == 0x00]
        assert scan.count(b"\xff") == len(idx) == 76     # 本体の FF は、すべて FF 00
        first = idx[0]
        sn = list(scan[first - 6:first + 8])
        k_ff = 6
        sn_x = lambda j: 960 + SN_STEP * (j - 6.5)  # noqa: E731
        sn_bytes = []
        for j, v in enumerate(sn):
            if j == k_ff + 1:
                assert v == 0
            sn_bytes.append(mono(hx(v), 48, SCOL if v != 0xFF else YELLOW).move_to(px(sn_x(j), SN_Y)))
        zero = sn_bytes[k_ff + 1]
        zero.set_color(INK)
        xs = lambda i: bx(scan0 + i + 0.5)  # noqa: E731
        ticks = VGroup(*[Line(px(xs(i), BAR_Y - BAR_H / 2 - 44), px(xs(i), BAR_Y - BAR_H / 2), stroke_width=2.5,
                              color=YELLOW) for i in idx])
        self.at("ffq", -0.1)
        shown = [b for j, b in enumerate(sn_bytes) if j != k_ff + 1]
        self.play(FadeIn(VGroup(*shown), shift=UP * u(12)), FadeIn(ticks[0]), run_time=0.7)
        self.play(Shake(sn_bytes[k_ff], 10, 0.6), pop(sn_bytes[k_ff], 1.4, 0.6), run_time=0.6)

        self.at("stuff", -0.1)
        zero.save_state()
        self.play(FadeIn(zero, scale=1.6), run_time=0.5)
        self.play(pop(VGroup(sn_bytes[k_ff], zero), 1.25, 0.5), run_time=0.5)
        self.at("skip", -0.1)
        tail = VGroup(*sn_bytes[k_ff + 2:])
        self.play(zero.animate.set_color(CORAL).shift(DOWN * u(30)).set_opacity(0),
                  tail.animate.shift(LEFT * u(SN_STEP)), run_time=0.8)
        self.remove(zero)

        # ---- 76 か所 ----
        self.at("count", -0.1)
        cnt = jp(f"{len(idx)} か所", 40, YELLOW).move_to(px(960, BAR_Y - BAR_H / 2 - 80))
        self.play(LaggedStart(*[Create(t) for t in ticks[1:]], lag_ratio=0.02), FadeIn(cnt, shift=UP * u(8)),
                  run_time=1.6)

        # ---- EOI ----
        self.at("eoi", -0.1)
        end = list(data[-6:])
        assert end[-2:] == [0xFF, 0xD9]
        end_m = VGroup(*[mono(hx(v), 48, YELLOW if j >= 4 else SCOL).move_to(px(960 + SN_STEP * (j - 2.5), SN_Y))
                         for j, v in enumerate(end)])
        self.play(FadeOut(VGroup(*sn_bytes[:k_ff + 1], tail), shift=UP * u(12)), FadeIn(end_m, shift=UP * u(12)),
                  run_time=0.6)
        self.play(pop(end_m[4:], 1.4, 0.6), run_time=0.6)

        # ---- 終わり：空 ----
        self.at(self.tl["duration"] - 1.9)
        self.play(FadeOut(Group(head, body, body_lbl, ticks, cnt, end_m)), run_time=1.0)
        self.finish()
