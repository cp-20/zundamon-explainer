import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, fmt, frame_rgba, indices, info, palette  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

LZW_COL = PURPLE
SRC = "cat16_nodither"
ROW, X0, N = 196, 205, 10
LX, VX = 470, 1130              # 左：ラベル、右：図の中心
ROWY = [130, 350, 650]

# クレジット（tools/description.py と同じ文言）
CREDITS = [("音声", ["VOICEVOX:ずんだもん", "VOICEVOX:四国めたん"]), ("立ち絵", ["坂本アヒル 様"]),
           ("音楽", ["甘茶の音楽工房"]), ("効果音", ["効果音ラボ"]),
           ("フォント", ["Zen Maru Gothic", "M PLUS Rounded 1c", "JetBrains Mono"]),
           ("映像", ["Manim Community"]), ("写真", ["Chelsea the cat（Stefan van der Walt, CC0）"])]


def sq(v, rgb, size, fs):
    light = sum(int(c) for c in rgb) > 380
    b = Square(u(size), stroke_width=0, fill_color=rgb_to_color(np.array(rgb) / 255), fill_opacity=1)
    return VGroup(b, mono(str(v), fs, BG if light else INK))


def lzw_adds(seq):
    d = {(v,): v for v in range(256)}
    nxt, i, adds = 258, 0, []
    while i < len(seq):
        n = 1
        while i + n < len(seq) and tuple(seq[i:i + n + 1]) in d:
            n += 1
        if i + n < len(seq):
            d[tuple(seq[i:i + n + 1])] = nxt
            adds.append((nxt, tuple(seq[i:i + n + 1])))
            nxt += 1
        i += n
    return adds


class S09(PScene):
    def construct(self):
        pal = palette(SRC)
        seq = [int(v) for v in indices(SRC)[ROW, X0:X0 + N]]
        adds = lzw_adds(seq)
        assert [a[0] for a in adds] == [258, 259, 260, 261, 262] and adds[1][1] == (14, 12)

        # 欄 1：色 → 表の番号
        cells = VGroup(*[sq(v, pal[v], 60, 30) for v in seq[:6]]).arrange(RIGHT, buff=u(8))
        cells.move_to(px(VX, ROWY[0]))
        lab1 = jp("色の番号", 32, CYAN).move_to(px(LX, ROWY[0]), aligned_edge=LEFT)

        # 欄 2：辞書
        rows = VGroup()
        for code, s in adds[:4]:
            minis = VGroup(*[sq(v, pal[v], 44, 24) for v in s]).arrange(RIGHT, buff=u(4))
            rows.add(VGroup(mono(str(code), 30, LZW_COL), minis).arrange(RIGHT, buff=u(16)))
        rows.arrange(DOWN, buff=u(10), aligned_edge=LEFT).move_to(px(VX, ROWY[1]))
        lab2 = jp("辞書", 32, LZW_COL).move_to(px(LX, ROWY[1]), aligned_edge=LEFT)

        # 欄 3：1 コマ目は全部、2 コマ目からは変わったところだけ
        inf = info()
        f1 = inf["frames"][1]
        full = png_mob(frame_rgba(k=0), 300, nearest=True)
        canvas = Rectangle(width=full.width, height=full.height, stroke_color=DIM, stroke_width=2)
        scale = full.height / inf["height"]
        pimg = np.zeros((f1["height"], f1["width"], 4), np.uint8)
        ix = indices(k=1)
        pal0 = palette()
        pimg[..., :3] = pal0[ix]
        pimg[..., 3] = np.where(ix == f1["gce"]["transparent_index"], 0, 255)
        patch = png_mob(pimg, f1["height"] * 300 / inf["height"], cell_px=4, nearest=True)
        arrow = jp("→", 44, DIM)
        pair = Group(full, arrow, canvas).arrange(RIGHT, buff=u(36)).move_to(px(VX, ROWY[2]))
        patch.move_to(canvas.get_corner(UL) + RIGHT * (f1["left"] + f1["width"] / 2) * scale
                      + DOWN * (f1["top"] + f1["height"] / 2) * scale)
        frame = Rectangle(width=patch.width + u(8), height=patch.height + u(8), stroke_color=YELLOW,
                          stroke_width=3).move_to(patch)
        lab3 = jp("変わったところだけ", 32, YELLOW).move_to(px(LX, ROWY[2]), aligned_edge=LEFT)

        self.at("t1", -0.1)
        self.play(FadeIn(cells, shift=UP * u(10)), FadeIn(lab1, shift=UP * u(6)), run_time=0.8)
        self.at("t2", -0.1)
        self.play(FadeIn(rows, shift=UP * u(10)), FadeIn(lab2, shift=UP * u(6)), run_time=0.8)
        self.at("t3", -0.1)
        self.play(FadeIn(full), FadeIn(arrow), Create(canvas), FadeIn(lab3, shift=UP * u(6)), run_time=0.8)
        self.play(FadeIn(patch), Create(frame), run_time=0.7)

        # ---- 8 枚あっても小さい ----
        self.at("s09_05", 0.2)
        n = len(inf["frames"])
        total = mix(f"{n} コマ ＝ {fmt(len(file_bytes('zunda_anim')))} バイト", 44, YELLOW).move_to(px(960, 850))
        assert (n, len(file_bytes("zunda_anim"))) == (8, 28615)
        self.play(FadeIn(total, shift=UP * u(8)), run_time=0.7)

        # ---- 想像してみてね → 図が消えて、クレジット ----
        diagram = Group(cells, lab1, rows, lab2, full, arrow, canvas, patch, frame, lab3, total)
        self.at("S09_06.end", 0.3)
        self.play(FadeOut(diagram), run_time=1.4)
        self.remove(*diagram)
        title = jp("クレジット", 44, INK).move_to(px(960, 70))
        cred = Group(title)
        y = 150
        for cat, vals in CREDITS:
            cred.add(jp(cat, 34, DIM).move_to(px(470, y), aligned_edge=LEFT))
            for v in vals:
                cred.add(mix(v, 34, INK).move_to(px(710, y), aligned_edge=LEFT))
                y += 56
            y += 18
        self.at("S09_06.end", 2.0)
        self.play(FadeIn(cred, shift=UP * u(10)), run_time=1.0)

        # ---- 「ありがとう」「またね」のあと、ゆっくり消える ----
        self.at("S09_08.end", 0.8)
        self.play(FadeOut(cred), run_time=self.until(self.tl["duration"], -0.3))
        self.finish()
