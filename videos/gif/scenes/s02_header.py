import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402,F401

from vlib.data import file_bytes, info  # noqa: E402
from zunda.fx import Shake, pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

GREEN = "#7ee08a"
STEP, ROW_Y = 76, 240
NB = 13                       # ヘッダの 13 バイト


class S02(PScene):
    def construct(self):
        fb = file_bytes("zunda_anim")
        inf = info()
        head = fb[:NB]
        # ---- 実データの確認 ----
        assert head[:6] == b"GIF89a" == inf["version"].encode()
        w = int.from_bytes(head[6:8], "little")
        h = int.from_bytes(head[8:10], "little")
        assert (w, h) == (inf["width"], inf["height"]) == (181, 360)
        flag = head[10]
        bits = f"{flag:08b}"
        has_table = bits[0] == "1"
        tsize = 2 ** (int(bits[5:], 2) + 1)
        assert has_table == inf["gct"] and tsize == inf["gct_size"] == 256

        title = jp("GIFの中身をのぞく", 72).move_to(px(960, 300))
        self.add(title)

        bx = lambda i: 960 + STEP * (i - (NB - 1) / 2)
        hexes = VGroup(*[mono(f"{b:02x}".upper(), 44).move_to(px(bx(i), ROW_Y)) for i, b in enumerate(head)])

        # ---- 先頭から見てみる ----
        self.at("s02_01", 0.6)
        self.play(FadeOut(title, shift=UP * u(20)), run_time=0.7)
        self.at("hex")
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(8)) for b in hexes], lag_ratio=0.08), run_time=1.0)

        # ---- 名札 ----
        self.at("sig")
        self.play(*[hexes[i].animate.set_color(YELLOW) for i in range(6)], run_time=0.5)
        self.at("text")
        chars = VGroup(*[mono(chr(head[i]), 40, YELLOW).move_to(px(bx(i), ROW_Y + 90)) for i in range(6)])
        self.play(LaggedStart(*[ReplacementTransform(hexes[i].copy(), chars[i]) for i in range(6)], lag_ratio=0.12),
                  run_time=1.2)

        # ---- 幅と高さ ----
        self.at("wh")
        sig = VGroup(*hexes[:6], chars)
        ul_w = underline(VGroup(*hexes[6:8]), CYAN)
        ul_h = underline(VGroup(*hexes[8:10]), GREEN)
        self.play(sig.animate.set_color(DIM), *[hexes[i].animate.set_color(CYAN) for i in (6, 7)],
                  *[hexes[i].animate.set_color(GREEN) for i in (8, 9)], Create(ul_w), Create(ul_h), run_time=0.8)

        WY = 520
        wx, hx = 560, 1030
        self.at("b5")
        wcopy = VGroup(*[hexes[i].copy().set_color(CYAN) for i in (6, 7)])
        wcopy.check_ignore = True
        wpair = VGroup(*[mono(f"{head[i]:02x}".upper(), 56, CYAN) for i in (6, 7)]).arrange(RIGHT, buff=u(24))
        wpair.move_to(px(wx, WY))
        warrow = jp("→", 48, DIM).move_to(px(wx + 150, WY))
        wq = jp("？", 64, CYAN).move_to(px(wx + 250, WY))
        self.play(ReplacementTransform(wcopy, wpair), run_time=0.8)
        self.play(FadeIn(warrow), FadeIn(wq), run_time=0.5)

        self.at("hh", -0.1)
        hcopy = VGroup(*[hexes[i].copy().set_color(GREEN) for i in (8, 9)])
        hcopy.check_ignore = True
        hpair = VGroup(*[mono(f"{head[i]:02x}".upper(), 56, GREEN) for i in (8, 9)]).arrange(RIGHT, buff=u(24))
        hpair.move_to(px(hx, WY))
        harrow = jp("→", 48, DIM).move_to(px(hx + 150, WY))
        hq = jp("？", 64, GREEN).move_to(px(hx + 250, WY))
        self.play(ReplacementTransform(hcopy, hpair), run_time=0.8)
        self.play(FadeIn(harrow), FadeIn(hq), run_time=0.5)

        # ---- 小さい桁が先 ----
        self.at("little", -0.1)
        # 幅と高さの 2 組とも、同時に入れ替わる
        a, b = hpair[0], hpair[1]
        c, d = wpair[0], wpair[1]
        self.play(a.animate.move_to(b.get_center()), b.animate.move_to(a.get_center()),
                  c.animate.move_to(d.get_center()), d.animate.move_to(c.get_center()),
                  run_time=1.0, path_arc=PI / 2)
        self.at("w2", -0.1)
        wval = jp(str(w), 64, CYAN).move_to(wq)
        self.play(ReplacementTransform(wq, wval), run_time=0.6)
        self.at("h", -0.1)
        hval = jp(str(h), 64, GREEN).move_to(hq)
        self.play(ReplacementTransform(hq, hval), run_time=0.6)

        # ---- 順番が逆 ----
        self.at("rev", 0.2)
        self.play(Shake(wpair, 10), Shake(hpair, 10), run_time=0.7)

        # ---- 次の 1 バイト：ビットに分ける ----
        self.at("rev", 2.8)
        self.play(FadeOut(VGroup(wpair, warrow, wval, hpair, harrow, hval, ul_w, ul_h)),
                  *[hexes[i].animate.set_color(DIM) for i in range(6, 10)], run_time=0.8)
        self.at("flag")
        BY, BSTEP = 560, 96
        bitx = lambda i: 960 + BSTEP * (i - 3.5)
        cols = [YELLOW] + [DIM] * 4 + [CYAN] * 3
        bitm = VGroup(*[mono(c, 72, cols[i]).move_to(px(bitx(i), BY)) for i, c in enumerate(bits)])
        self.play(hexes[10].animate.set_color(YELLOW), run_time=0.4)
        fcopy = hexes[10].copy()
        fcopy.check_ignore = True
        self.play(ReplacementTransform(fcopy, bitm), run_time=1.0)

        self.at("table")
        lab1 = jp("色の表あり", 48, YELLOW).move_to(px(bitx(0) + 40, BY + 100))
        self.play(FadeIn(lab1, shift=UP * u(8)), run_time=0.6)
        self.at("table", 1.7)
        lab2 = jp(f"{tsize} 色", 48, CYAN).move_to(px((bitx(5) + bitx(7)) / 2, BY + 100))
        self.play(FadeIn(lab2, shift=UP * u(8)), run_time=0.6)

        # ---- 色の表（S03 の最初の画面へ）----
        self.at("s02_09")
        final = jp("色の表", 72, YELLOW).move_to(px(960, 300))
        self.play(Transform(lab1, final), FadeOut(VGroup(hexes, chars, bitm, lab2)), run_time=1.0)
        self.finish()
