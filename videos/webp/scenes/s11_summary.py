import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import BMODE_NAME, decisions, distance_map, mb, pixels, sub_block  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.paths import video_config  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

LX, FX = 445, 770                 # 左：ラベル、右：図の左端
ROWY = [110, 330, 585, 790]
C = 44                            # 予想の図のマス

# クレジット (GIF 編と同じ文言 ＋ この動画の写真。写真は video.yaml の extra_credits から)
CREDITS = [("音声", ["VOICEVOX:ずんだもん", "VOICEVOX:四国めたん"]), ("立ち絵", ["坂本アヒル 様"]),
           ("音楽", ["甘茶の音楽工房"]), ("効果音", ["効果音ラボ"]),
           ("フォント", ["Zen Maru Gothic", "M PLUS Rounded 1c", "JetBrains Mono"]),
           ("映像", ["Manim Community"])]


def lum(v):
    g = float(np.clip(v, 0, 255)) / 255
    return rgb_to_color([g, g, g])


def cell(x, y, v, size=C, stroke=None):
    return Square(u(size), stroke_width=3 if stroke else 1.5, stroke_color=stroke or "#2a2e38",
                  fill_color=lum(v), fill_opacity=1).move_to(px(x, y))


class S11(PScene):
    def construct(self):
        # ================= データ =================
        sb = sub_block()
        assert BMODE_NAME[sb["mode"]] == "VR"
        diff = sb["orig"] - sb["pred"]
        log = mb()["tok_log"][0][:3]
        # 帯は前の判定で選んだ側が、次の判定の幅になる
        for (p, b, r, z), nxt in zip(log, mb()["tok_log"][0][1:4]):
            w = z if b == 0 else r - z
            assert nxt[2] in (w, w * 2, w * 4), (w, nxt)
        n_dec, n_bits = decisions()
        per = n_bits / n_dec
        assert per < 1 and f"{per:.2f}" == "0.80"
        dm = distance_map()
        assert dm[0] == (0, 1) and dm[1] == (1, 0)          # 番号 1 ＝ すぐ上、番号 2 ＝ すぐ左
        photo = [x for k, v in video_config()["extra_credits"] if k == "写真" for x in v][0]
        credits = CREDITS + [("写真", [s.strip() for s in photo.split(" / ")])]

        labels = [jp(s, 36, INK).move_to(px(LX, y), aligned_edge=LEFT)
                  for s, y in zip(["動画の技術から", "上と左から予想", "細かく詰める", "コピーと表の番号"], ROWY)]

        # ---- 1：動画の技術 (VP8) ----
        cat = pixels("cat")
        SW, SH = 620, 170
        strip = Rectangle(width=u(SW), height=u(SH), stroke_width=0, fill_color="#0b0c10",
                          fill_opacity=1).move_to(px(FX + SW / 2, ROWY[0]))
        holes = VGroup(*[RoundedRectangle(corner_radius=u(4), width=u(18), height=u(13), stroke_width=0,
                                          fill_color="#3a3f4c", fill_opacity=1).move_to(px(FX + 17 + 31 * i, yy))
                         for i in range(20) for yy in (ROWY[0] - 70, ROWY[0] + 70)])
        frames = Group()
        for i in range(3):
            im = ImageMobject(cat[40 + 6 * i:40 + 6 * i + 200, 90 + 8 * i:90 + 8 * i + 300])
            im.height = u(118)
            im.move_to(px(FX + 108 + 202 * i, ROWY[0]))
            im.check_ignore = True
            frames.add(im)
        vp8 = mono("VP8", 44, CYAN).move_to(px(FX + SW + 65, ROWY[0]))
        row1 = Group(strip, holes, frames, vp8)

        # ---- 2：上と左から予想 → 差 ----
        x_l, y_t = FX + C / 2, ROWY[1] - 2 * C
        bx, by = x_l + C, y_t + C                      # 4×4 の左上のマスの中心
        nb = VGroup(cell(x_l, y_t, sb["X"], stroke=CYAN))
        nb.add(*[cell(bx + C * i, y_t, sb["top"][i], stroke=CYAN) for i in range(8)])
        nb.add(*[cell(x_l, by + C * i, sb["left"][i], stroke=CYAN) for i in range(4)])
        blk = VGroup(*[cell(bx + C * c, by + C * r, sb["pred"][r][c]) for r in range(4) for c in range(4)])
        mid = blk.get_center()
        v = np.array([0.5, -1, 0]) / np.hypot(0.5, 1) * u(C * 3.2)
        arrow = Arrow(mid - v / 2, mid + v / 2, buff=0, color=CYAN, stroke_width=10,
                      max_tip_length_to_length_ratio=0.3, max_stroke_width_to_length_ratio=12)
        D = C + 8
        dx0, dy0 = FX + 9 * C + 110, by + 1.5 * C - 1.5 * D
        to = jp("→", 48, DIM).move_to(px((x_l + 8.5 * C + dx0 - D / 2) / 2, by + 1.5 * C))
        dgrid = VGroup()
        for r in range(4):
            for c in range(4):
                sq = Square(u(D), stroke_width=1.5, stroke_color="#3a3f4c", fill_color="#232833",
                            fill_opacity=1).move_to(px(dx0 + D * c, dy0 + D * r))
                dgrid.add(VGroup(sq, mono(str(int(diff[r][c])).replace("-", "−"), 30, PURPLE).move_to(sq)))
        dlab = jp("差", 32, PURPLE).move_to(px(dx0 + 1.5 * D, dy0 - D / 2 - 26))
        row2 = VGroup(nb, blk, arrow, to, dgrid, dlab)

        # ---- 3：算術符号の帯 ----
        BW, BH = 690, 30
        bars = VGroup()
        for i, (p, b, r, z) in enumerate(log):
            y = ROWY[2] - 80 + 56 * i
            zero = Rectangle(width=u(BW * z / r), height=u(BH), stroke_width=0, fill_color=BLUE, fill_opacity=1)
            one = Rectangle(width=u(BW * (r - z) / r), height=u(BH), stroke_width=0, fill_color=CORAL, fill_opacity=1)
            zero.move_to(px(FX, y), aligned_edge=LEFT)
            one.next_to(zero, RIGHT, buff=0)
            (zero if b else one).set_fill(opacity=0.3)
            bars.add(VGroup(zero, one))
        zooms = VGroup()
        for i in range(len(log) - 1):
            pick = bars[i][log[i][1]]
            zooms.add(DashedLine(pick.get_corner(DL), bars[i + 1].get_corner(UL), color=DIM, stroke_width=2),
                      DashedLine(pick.get_corner(DR), bars[i + 1].get_corner(UR), color=DIM, stroke_width=2))
        ptxt = mix(f"判定 1 回 ≈ {per:.2f} ビット", 34, INK).move_to(px(FX + BW / 2, ROWY[2] + 88))
        row3 = VGroup(bars, zooms, ptxt)

        # ---- 4：上・左のコピー (距離の番号) と、最近の色の番号 ----
        G = 76
        gx, gy = FX + G / 2, ROWY[3] - G / 2
        grid = VGroup()
        for r in range(2):
            for c in range(4):
                col = YELLOW if (r, c) == (1, 2) else ("#3a3f4c" if (r, c) in ((0, 2), (1, 1)) else "#232833")
                grid.add(Square(u(G), stroke_width=1.5, stroke_color=DIM, fill_color=col,
                                fill_opacity=1).move_to(px(gx + G * c, gy + G * r)))
        cur = px(gx + 2 * G, gy + G)
        a_up = Arrow(px(gx + 2 * G, gy - G * 0.1), cur + UP * u(G * 0.12), buff=0, color=CYAN, stroke_width=9,
                     max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=14)
        a_lf = Arrow(px(gx + G * 0.9, gy + G), cur + LEFT * u(G * 0.12), buff=0, color=CYAN, stroke_width=9,
                     max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=14)
        c_up = mono("1", 32, CYAN).move_to(px(gx + 2 * G - 22, gy - 18))
        c_lf = mono("2", 32, CYAN).move_to(px(gx + G - 22, gy + G - 18))
        # 最近の表：中身の色は示さず、番号だけ (表に入るのは色そのものではなく、変換したあとの差)
        PICK = 2
        slots = VGroup()
        for i in range(5):
            x = FX + 4 * G + 70 + 72 * i
            sq = Square(u(58), stroke_width=2, stroke_color=DIM, fill_color="#232833",
                        fill_opacity=1).move_to(px(x, ROWY[3] + 12))
            slots.add(VGroup(sq, mono(str(i), 28, DIM).move_to(sq)))
        pk = slots[PICK]
        a_pk = Arrow(pk.get_top() + UP * u(52), pk.get_top() + UP * u(4), buff=0, color=YELLOW, stroke_width=7,
                     max_tip_length_to_length_ratio=0.4, max_stroke_width_to_length_ratio=14)
        row4 = VGroup(grid, a_up, a_lf, c_up, c_lf, slots, a_pk)

        # ================= 流れ =================
        self.at("t1", -0.2)
        self.play(FadeIn(labels[0], shift=UP * u(6)), FadeIn(strip), FadeIn(holes),
                  LaggedStart(*[FadeIn(f) for f in frames], lag_ratio=0.2), run_time=0.9)
        self.play(FadeIn(vp8, shift=LEFT * u(10)), run_time=0.5)

        self.at("t2", -0.1)
        self.play(FadeIn(labels[1], shift=UP * u(6)), LaggedStart(*[FadeIn(c) for c in nb], lag_ratio=0.05),
                  run_time=0.7)
        self.play(LaggedStart(*[FadeIn(c) for c in blk], lag_ratio=0.03), run_time=0.6)
        self.play(GrowArrow(arrow), run_time=0.5)
        self.play(FadeIn(to), LaggedStart(*[FadeIn(d, shift=RIGHT * u(6)) for d in dgrid], lag_ratio=0.03),
                  FadeIn(dlab), run_time=0.8)

        self.at("t3", -0.1)
        self.play(FadeIn(labels[2], shift=UP * u(6)), FadeIn(bars[0]), run_time=0.5)
        for i in range(1, len(log)):
            self.play(Create(zooms[2 * i - 2]), Create(zooms[2 * i - 1]), FadeIn(bars[i], shift=DOWN * u(6)),
                      run_time=0.5)
        self.play(FadeIn(ptxt, shift=UP * u(6)), run_time=0.5)

        self.at("t4", -0.1)
        self.play(FadeIn(labels[3], shift=UP * u(6)), FadeIn(grid), run_time=0.6)
        self.play(GrowArrow(a_up), FadeIn(c_up), run_time=0.6)
        self.play(GrowArrow(a_lf), FadeIn(c_lf), run_time=0.6)
        self.at("t4", 2.6)
        self.play(LaggedStart(*[FadeIn(s, shift=UP * u(6)) for s in slots], lag_ratio=0.12), run_time=0.9)
        self.play(pk[0].animate.set_stroke(YELLOW, 4), pk[1].animate.set_color(YELLOW), GrowArrow(a_pk), run_time=0.6)

        # ---- 予想が上手だと、書くことが減る ----
        self.at("s11_06", -0.1)
        self.play(pop(VGroup(blk, arrow), 1.08, 0.6), run_time=0.6)
        self.play(pop(dgrid, 1.12, 0.6), run_time=0.6)
        self.at("s11_06", 1.8)
        self.play(pop(ptxt, 1.12, 0.6), run_time=0.6)

        # ---- どんな予想をしているか、想像してみてね ----
        self.at("S11_07", 0.1)
        self.play(pop(row1, 1.04, 0.7), run_time=0.7)
        self.at("think", -0.1)
        self.play(pop(arrow, 1.25, 0.7), run_time=0.7)

        # ---- 図が消えて、クレジット ----
        figs = Group(*labels, row1, row2, row3, row4)
        self.at("S11_07.end", 0.3)
        self.play(*[f.animate.set_opacity(0) for f in frames], FadeOut(Group(*labels, strip, holes, vp8, row2, row3, row4)),
                  run_time=1.4)
        self.remove(*figs, *frames)
        title = jp("クレジット", 44, INK).move_to(px(960, 70))
        cred = VGroup(title)
        y = 150
        for cat_, vals in credits:
            cred.add(jp(cat_, 34, DIM).move_to(px(470, y), aligned_edge=LEFT))
            for v_ in vals:
                cred.add(mix(v_, 34, INK).move_to(px(710, y), aligned_edge=LEFT))
                y += 52
            y += 16
        assert y < 880
        self.at("S11_07.end", 1.9)
        self.play(FadeIn(cred, shift=UP * u(10)), run_time=1.0)

        # ---- 「ありがとう」「またね」のあと、ゆっくり消える ----
        self.at("S11_09.end", 0.8)
        self.play(FadeOut(cred), run_time=self.until(self.tl["duration"], -0.3))
        self.finish()
