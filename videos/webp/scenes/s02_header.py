import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, fmt, pixels, size, webp  # noqa: E402
from zunda.fx import pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NAME = "cat_q80"
STEP, ROW_Y, CHAR_DY = 76, (150, 320), 80      # 16 バイトずつ 2 行 (大きさ・色は GIF 編の S02 と同じ)
BSIZE = 44
# 箱の図 (2 人の間)
OUT_L, OUT_T, OUT_R, OUT_B = 470, 470, 1450, 890
IN_L, IN_T, IN_R, IN_B = 510, 640, 1410, 860
# フィルム
FR_W, FR_H, FR_STEP, FR_Y, NFR = 270, 180, 300, 270, 6
# S02 の終わり (S03 の最初) の写真の位置と幅
PHOTO_C, PHOTO_W = (770, 360), 640


def bx(i):
    return 960 + STEP * (i % 16 - 7.5)


def by(i):
    return ROW_Y[i // 16]


def tr(old, new):
    """同じオブジェクトのまま new の形・位置・色へ (検査用の text も更新)"""
    old.text = getattr(new, "text", None)
    return Transform(old, new)


def img(arr, width_px, center):
    m = ImageMobject(arr)
    m.width = u(width_px)
    return m.move_to(px(*center))


def left_at(m, x, y):
    """左端を x、縦の中心を y に"""
    return m.move_to(px(x, y), aligned_edge=LEFT).set_y(px(0, y)[1])


class S02(PScene):
    def construct(self):
        fb = file_bytes(NAME)
        head = fb[:32]
        total = size(NAME)
        w = webp(NAME)
        # ---- 実データの確認 ----
        assert head[:4] == b"RIFF" and head[8:12] == b"WEBP" and head[12:16] == b"VP8 "
        riff = int.from_bytes(head[4:8], "little")
        assert list(head[4:8]) == [0x46, 0x42, 0x00, 0x00]
        assert riff == total - 8 == w["riff_size"] == 16966
        vlen = int.from_bytes(head[16:20], "little")
        assert [(t, n) for t, _, n in w["chunks"]] == [("VP8 ", vlen)] and vlen == 16954
        assert 12 + 8 + vlen == total
        cat = pixels(NAME)
        assert cat.shape[:2] == (300, 451)

        title = jp("WebPの中身をのぞく", 72).move_to(px(960, 300))
        title.check_ignore = True   # S01 から引き継ぐ画面 (S01 側で十分長く出ている)
        self.add(title)

        # ---- 先頭からのぞく ----
        self.at("s02_01", -0.1)
        fname = mix(f"{NAME}.webp　{fmt(total)} バイト", 32, DIM).move_to(px(960, 62))
        self.play(FadeOut(title, shift=UP * u(20)), FadeIn(fname, shift=DOWN * u(8)), run_time=0.6)

        self.at("hex", 0.0)
        hexes = VGroup(*[mono(f"{b:02X}", BSIZE).move_to(px(bx(i), by(i))) for i, b in enumerate(head)])
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(8)) for b in hexes], lag_ratio=0.04), run_time=1.4)

        # Z「いつものやつ」：いつもの並びが、端から順に小さく跳ねる
        self.at("usual", 0.0)
        self.play(LaggedStart(*[pop(b, 1.2, 0.4) for b in hexes], lag_ratio=0.03), run_time=1.3)

        def chars_of(i0, n, col=YELLOW):
            out = []
            for i in range(i0, i0 + n):
                c = chr(head[i])
                m_ = jp("空白", 26, col) if c == " " else mono(c, 40, col)
                out.append(m_.move_to(px(bx(i), by(i) + CHAR_DY)))
            return VGroup(*out)

        # ---- RIFF：箱の決まり ----
        self.at("riff", -0.1)
        self.play(*[hexes[i].animate.set_color(YELLOW) for i in range(4)], run_time=0.5)
        c_riff = chars_of(0, 4)
        self.play(LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_riff[i]) for i in range(4)], lag_ratio=0.12),
                  run_time=1.0)

        self.at("box", -0.1)
        outer = RoundedRectangle(corner_radius=u(18), width=u(OUT_R - OUT_L), height=u(OUT_B - OUT_T),
                                 stroke_color=YELLOW, stroke_width=3).move_to(px((OUT_L + OUT_R) / 2,
                                                                                 (OUT_T + OUT_B) / 2))
        tag_riff = left_at(mono("RIFF", 36, YELLOW), OUT_L + 30, OUT_T + 45)
        fly = c_riff.copy()
        fly.check_ignore = True
        self.play(Create(outer), ReplacementTransform(fly, tag_riff, path_arc=-PI / 6), run_time=1.0)

        self.at("wav", -0.1)
        wav = mix("WAV・AVI も同じ箱", 30, DIM)
        wav.move_to(px(OUT_R - 30, OUT_T + 45), aligned_edge=RIGHT).set_y(px(0, OUT_T + 45)[1])
        self.play(FadeIn(wav, shift=LEFT * u(10)), run_time=0.6)

        # ---- 箱の大きさ：小さい桁が先 ----
        self.at("size", -0.1)
        ul_size = underline(VGroup(*hexes[4:8]), CYAN)
        self.play(VGroup(*hexes[:4], c_riff).animate.set_color(DIM),
                  *[hexes[i].animate.set_color(CYAN) for i in range(4, 8)], Create(ul_size), run_time=0.7)
        FY, FSTEP, FX = 640, 96, 800
        pair = [mono(f"{head[4 + k]:02X}", 56, CYAN).move_to(px(FX + FSTEP * (k - 1.5), FY)) for k in range(4)]
        cps = [hexes[4 + k].copy() for k in range(4)]
        for c in cps:
            c.check_ignore = True
        self.play(LaggedStart(*[ReplacementTransform(c, p) for c, p in zip(cps, pair)], lag_ratio=0.1), run_time=0.9)

        self.at("little", -0.1)
        # 4 つが同時に入れ替わる (後ろから読む)
        self.play(*[pair[k].animate.move_to(px(FX + FSTEP * (1.5 - k), FY)) for k in range(4)],
                  path_arc=PI, run_time=1.1)
        val = mix(f"＝ {fmt(riff)}", 56, CYAN)
        left_at(val, FX + FSTEP * 2 + 10, FY)
        minus8 = mix(f"(全体 {fmt(total)} − 8)", 28, DIM)
        left_at(minus8, FX + FSTEP * 2 + 10, FY + 62)
        self.play(FadeIn(val, shift=RIGHT * u(10)), FadeIn(minus8, shift=UP * u(6)), run_time=0.6)

        # ---- WEBP ----
        self.at("webp", -0.1)
        size_lab = left_at(mix(f"{fmt(riff)} バイト", 36, CYAN), OUT_L + 150, OUT_T + 45)
        self.play(tr(val, size_lab), FadeOut(VGroup(*pair, minus8)), ul_size.animate.set_opacity(0),
                  *[hexes[i].animate.set_color(DIM) for i in range(4, 8)],
                  *[hexes[i].animate.set_color(YELLOW) for i in range(8, 12)], run_time=0.8)
        self.remove(ul_size)
        c_webp = chars_of(8, 4)
        self.play(LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_webp[i - 8]) for i in range(8, 12)],
                              lag_ratio=0.12), run_time=1.0)
        tag_webp = left_at(mono("WEBP", 36, YELLOW), OUT_L + 30, OUT_T + 115)
        fly = c_webp.copy()
        fly.check_ignore = True
        self.play(ReplacementTransform(fly, tag_webp, path_arc=-PI / 6), run_time=0.9)

        # ---- VP8 の小箱 ----
        self.at("vp8", -0.1)
        self.play(VGroup(*hexes[8:12], c_webp).animate.set_color(DIM),
                  *[hexes[i].animate.set_color(YELLOW) for i in range(12, 16)], run_time=0.5)
        c_vp8 = chars_of(12, 4)
        self.play(LaggedStart(*[ReplacementTransform(hexes[i].copy(), c_vp8[i - 12]) for i in range(12, 16)],
                              lag_ratio=0.12), run_time=1.0)
        inner = RoundedRectangle(corner_radius=u(14), width=u(IN_R - IN_L), height=u(IN_B - IN_T),
                                 stroke_color=CYAN, stroke_width=3).move_to(px((IN_L + IN_R) / 2, (IN_T + IN_B) / 2))
        tag_vp8 = left_at(mono("VP8", 36, YELLOW), IN_L + 30, IN_T + 45)
        fly = c_vp8.copy()
        fly.check_ignore = True
        self.play(Create(inner), ReplacementTransform(fly, tag_vp8, path_arc=-PI / 6), run_time=1.0)

        self.at("len", -0.1)
        ul_len = underline(VGroup(*hexes[16:20]), CYAN)
        self.play(*[hexes[i].animate.set_color(CYAN) for i in range(16, 20)], Create(ul_len),
                  VGroup(*hexes[12:16], c_vp8).animate.set_color(DIM), run_time=0.6)
        len_lab = left_at(mix(f"{fmt(vlen)} バイト", 36, CYAN), IN_L + 120, IN_T + 45)
        cp = VGroup(*[hexes[i].copy() for i in range(16, 20)])
        cp.check_ignore = True
        self.play(ReplacementTransform(cp, len_lab, path_arc=-PI / 6), run_time=0.9)
        body = jp("画像の本体", 36, INK).move_to(px((IN_L + IN_R) / 2, IN_T + 140))
        self.play(FadeIn(body, scale=0.9), run_time=0.6)

        # Z「何の名前なのだ？」：VP8 の名札が拡大
        self.at("what", 0.2)
        self.play(pop(tag_vp8, 1.3, 0.7), run_time=0.7)

        # ---- VP8 はもともと動画の形式 ----
        self.at("video", -0.1)
        vlabel = mix("VP8 ＝ 動画の形式", 40, YELLOW).move_to(px(960, 80))
        gone = VGroup(fname, hexes, c_riff, c_webp, c_vp8, ul_len, outer, inner, tag_riff, tag_webp, val, wav,
                      len_lab, body)
        self.play(FadeOut(gone, shift=UP * u(30)), tr(tag_vp8, vlabel), run_time=1.1)
        self.remove(*hexes)

        self.at("frames", -0.1)
        strip = Rectangle(width=u(1864), height=u(FR_H + 66), stroke_width=0, fill_color="#0b0c10",
                          fill_opacity=1).move_to(px(960, FR_Y))
        holes = VGroup(*[RoundedRectangle(corner_radius=u(3), width=u(20), height=u(12), stroke_width=0,
                                          fill_color="#2c303b", fill_opacity=1).move_to(px(x, FR_Y + s * (FR_H / 2 + 18)))
                         for x in range(56, 1880, 48) for s in (-1, 1)])
        film = VGroup(strip, holes)
        film.check_ignore = True
        fx = lambda k: 960 + FR_STEP * (k - (NFR - 1) / 2)            # noqa: E731
        bg = np.array([0x14, 0x16, 0x1c], float)
        faded = (cat.astype(float) * 0.38 + bg * 0.62).astype(np.uint8)
        frames = [img(cat, FR_W, (fx(0), FR_Y))] + [img(faded, FR_W, (fx(k), FR_Y)) for k in range(1, NFR)]
        for f in frames:
            f.check_ignore = True                               # 上に印を重ねる下敷き
        self.play(FadeIn(film), run_time=0.6)
        self.play(FadeIn(frames[0], scale=0.85), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(f, shift=LEFT * u(40)) for f in frames[1:]], lag_ratio=0.25), run_time=1.6)

        # ---- 2 枚目からは前との違いだけ ----
        self.at("diff", -0.1)
        diffs = [jp("前との違い", 28, CORAL).move_to(frames[k]) for k in range(1, NFR)]
        arrows = [Arrow(px(fx(k - 1) + FR_W / 2 - 40, FR_Y), px(fx(k) - FR_W / 2 + 40, FR_Y), buff=0, color=CORAL,
                        stroke_width=5, max_tip_length_to_length_ratio=0.35) for k in range(1, NFR)]
        for a in arrows:
            a.check_ignore = True                               # 写真の端に少しかかる
        self.play(LaggedStart(*[AnimationGroup(GrowArrow(a), FadeIn(d, shift=RIGHT * u(8)))
                                for a, d in zip(arrows, diffs)], lag_ratio=0.25), run_time=1.8)

        self.at("first", -0.1)
        border = Rectangle(width=u(FR_W + 12), height=u(FR_H + 12), stroke_color=YELLOW,
                           stroke_width=5).move_to(frames[0])
        self.play(Create(border), run_time=0.6)
        self.play(pop(Group(frames[0], border), 1.1, 0.7), run_time=0.7)

        self.at("alone", -0.1)
        self.play(FadeOut(film), FadeOut(VGroup(*arrows, *diffs)), *[f.animate.set_opacity(0) for f in frames[1:]],
                  run_time=0.9)
        self.remove(*frames[1:])

        # ---- その 1 枚の縮め方を、写真に ----
        photo = frames[0]
        self.at("one", -0.1)
        self.play(FadeOut(border), FadeOut(tag_vp8), photo.animate.set(width=u(800)).move_to(px(960, 360)),
                  run_time=1.2)

        self.at("borrow", 0.3)
        self.play(pop(photo, 1.05, 0.7), run_time=0.7)

        # ---- VP8 と VP8L ----
        self.at("s02_09", -0.1)
        card_c = [(1330, 285), (1330, 385)]

        def card(tag, text, col, c):
            t = mix(f"{tag}：{text}", 36, col)
            box = RoundedRectangle(corner_radius=u(14), width=u(420), height=u(80), stroke_color=col,
                                   stroke_width=3, fill_color="#1c1f27", fill_opacity=1).move_to(px(*c))
            t.move_to(box)
            return VGroup(box, t)
        k1 = card("VP8 ", "捨てて縮める", YELLOW, card_c[0])
        k2 = card("VP8L", "捨てずに縮める", CYAN, card_c[1])
        self.play(photo.animate.set(width=u(PHOTO_W)).move_to(px(*PHOTO_C)), run_time=1.0)
        self.play(FadeIn(k1, shift=LEFT * u(14)), run_time=0.6)
        self.at("vp8l", -0.1)
        self.play(FadeIn(k2, shift=LEFT * u(14)), run_time=0.6)

        self.at("later", 1.6)
        self.play(FadeOut(VGroup(k1, k2)), run_time=0.6)
        self.finish()
