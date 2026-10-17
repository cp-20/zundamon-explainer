import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import file_bytes, fmt, pixels  # noqa: E402
from zunda.fx import Shake, pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

# 写真の枠（px）。ズームしても枠は変えず、中に見える範囲だけを変える
BOX_W, BOX_H = 495, 330        # ズーム時の写真の大きさ
HOOK_H = 420
PHOTO_L, PHOTO_R, PHOTO_Y = 630, 1290, 270
EYE = (104, 161)          # 拡大する場所（猫の左目の瞳のふち）の 行, 列
NC, NR = 6, 4             # 拡大したとき見える画素数（横, 縦）
CELL = BOX_W / NC
SRC_W, SRC_H = 450, 300   # 写真の全体（右端の 1 列は使わない：枠と同じ 3:2 にそろえる）

# ファイルの大きさの横棒
ROW_Y = (610, 740)
BAR_X0, BAR_MAX, BAR_H = 760, 700, 64


def luma(rgb):
    return np.round(rgb[..., :3].astype(float) @ [0.299, 0.587, 0.114]).astype(int)


def window(a):
    """ズームの進み具合 a（0=全体, 1=目のあたり）での、見える範囲 (左, 上, 幅, 高さ)"""
    w = SRC_W * (NC / SRC_W) ** a
    f = (1 - w / SRC_W) / (1 - NC / SRC_W)
    return EYE[1] * f, EYE[0] * f, w, w * SRC_H / SRC_W


def view(src, a):
    L, T, w, h = window(a)
    im = Image.fromarray(src[..., :3])
    res = Image.BICUBIC if w >= 150 else Image.NEAREST
    return np.asarray(im.resize((BOX_W * 2, BOX_H * 2), res, box=(L, T, L + w, T + h)))


def photo(src, x):
    m = ImageMobject(view(src, 0))
    m.height = u(HOOK_H)
    return m.move_to(px(x, PHOTO_Y))


class Zoom(Animation):
    """2 枚の写真を、同じ場所へ同時にズーム（a0→a1）。枠は変えず、見える範囲だけを変える"""

    def __init__(self, left, right, a0, a1, **kw):
        self.srcs = [(left, pixels("cat")), (right, pixels("cat_q80"))]
        self.a0, self.a1 = a0, a1
        super().__init__(Group(left, right), rate_func=smooth, **kw)

    def interpolate_mobject(self, alpha):
        a = self.a0 + (self.a1 - self.a0) * alpha
        for m, src in self.srcs:
            m.pixel_array = np.dstack([view(src, a), np.full((BOX_H * 2, BOX_W * 2), 255, np.uint8)])


class S01(PScene):
    def construct(self):
        png_n, jpg_n = len(file_bytes("cat")), len(file_bytes("cat_q80"))
        assert (png_n, jpg_n) == (218916, 23693) and round(png_n / jpg_n) == 9
        a_rgb, b_rgb = pixels("cat"), pixels("cat_q80")

        # ---- 猫の写真と、PNG の札 ----
        left = photo(a_rgb, 960)
        self.at("photo", -0.2)
        self.play(FadeIn(left, scale=0.96), run_time=0.9)

        tag_png = jp("cat.png", 36, INK).move_to(px(960, 530))
        self.at("png", -0.1)
        self.play(FadeIn(tag_png, shift=UP * u(10)), run_time=0.5)

        self.at("jpg", -0.1)
        tag_jpg = jp("cat.jpg", 36, INK).move_to(px(1140, 530))
        self.play(tag_png.animate.move_to(px(780, 530)), FadeIn(tag_jpg, shift=UP * u(10)), run_time=0.7)

        # ---- 大きさ：札の数字が横棒に ----
        self.at("size", -0.1)
        num_png = jp(f"{fmt(png_n)} バイト", 34, INK).move_to(px(780, 580))
        num_jpg = jp(f"{fmt(jpg_n)} バイト", 34, INK).move_to(px(1140, 580))
        self.play(FadeIn(num_png, shift=UP * u(8)), FadeIn(num_jpg, shift=UP * u(8)), run_time=0.6)

        def bar(n, color, y):
            b = Rectangle(width=u(BAR_MAX * n / png_n), height=u(BAR_H), stroke_width=0, fill_color=color, fill_opacity=1)
            return b.move_to(px(BAR_X0, y), aligned_edge=LEFT)

        bar_png, bar_jpg = bar(png_n, CYAN, ROW_Y[0] + 23), bar(jpg_n, YELLOW, ROW_Y[1] + 23)
        anims = []
        for tg, nm, y in [(tag_png, num_png, ROW_Y[0]), (tag_jpg, num_jpg, ROW_Y[1])]:
            anims += [tg.animate.move_to(px(470, y), aligned_edge=LEFT),
                      nm.animate.move_to(px(470, y + 46), aligned_edge=LEFT)]
        self.play(*anims, GrowFromEdge(bar_png, LEFT), GrowFromEdge(bar_jpg, LEFT), run_time=1.4)

        self.at("small", -0.1)
        small = jp(f"約 1/{round(png_n / jpg_n)}", 48, YELLOW).move_to(
            px(BAR_X0 + BAR_MAX * jpg_n / png_n + 28, ROW_Y[1] + 23), aligned_edge=LEFT)
        self.play(FadeIn(small, shift=RIGHT * u(10)), run_time=0.5)
        self.play(pop(small, 1.2, 0.5))

        # ---- PNG は消さずに小さく / JPEG はもっとすごい ----
        self.at("lossless", -0.1)
        self.play(pop(VGroup(tag_png, num_png, bar_png), 1.06, 0.8))
        self.at(25.6)
        self.play(pop(VGroup(tag_jpg, num_jpg, bar_jpg), 1.12, 0.8))

        # ---- 捨てている ----
        self.at("throw", -0.2)
        throw = jp("捨てている", 48, CORAL).move_to(px(1100, ROW_Y[1] + 23), aligned_edge=LEFT)
        self.play(Shake(VGroup(tag_jpg, num_jpg, bar_jpg), amp=8, run_time=0.6), FadeIn(throw, shift=RIGHT * u(10)))

        # ---- 同じ場所を拡大：写真が 2 枚に ----
        self.at("s01_07", -0.1)
        right = photo(b_rgb, 960)
        self.add(right)
        self.remove(left)
        self.add(left)
        lbl_a = jp("元の画像", 32, INK).move_to(px(PHOTO_L, 66))
        lbl_b = jp("JPEG", 32, INK).move_to(px(PHOTO_R, 66))
        rows = Group(tag_png, num_png, bar_png, tag_jpg, num_jpg, bar_jpg, small, throw)
        self.play(FadeOut(rows), left.animate.scale(BOX_H / HOOK_H).move_to(px(PHOTO_L, PHOTO_Y)),
                  right.animate.scale(BOX_H / HOOK_H).move_to(px(PHOTO_R, PHOTO_Y)),
                  FadeIn(lbl_a), FadeIn(lbl_b), run_time=1.0)

        def grid_for(cx):
            x0, y0 = cx - BOX_W / 2, PHOTO_Y - BOX_H / 2
            ls = [Line(px(x0 + CELL * i, y0), px(x0 + CELL * i, y0 + BOX_H), stroke_width=1.5) for i in range(NC + 1)]
            ls += [Line(px(x0, y0 + CELL * j), px(x0 + BOX_W, y0 + CELL * j), stroke_width=1.5) for j in range(NR + 1)]
            return VGroup(*ls).set_color(INK).set_stroke(opacity=0.45)

        grids = VGroup(grid_for(PHOTO_L), grid_for(PHOTO_R))

        self.at("zoom", -0.1)
        self.play(Zoom(left, right, 0, 1), run_time=2.0)
        self.play(FadeIn(grids), run_time=0.4)

        # ---- 画素の明るさの数字 ----
        self.at("num")
        ya = luma(a_rgb)[EYE[0]:EYE[0] + NR, EYE[1]:EYE[1] + NC]
        yb = luma(b_rgb)[EYE[0]:EYE[0] + NR, EYE[1]:EYE[1] + NC]
        diff = yb - ya

        def cell_xy(cx, r, c):
            return px(cx - BOX_W / 2 + CELL * (c + 0.5), PHOTO_Y - BOX_H / 2 + CELL * (r + 0.5))

        def stroked(t):
            t.set_stroke(BG, 6, background=True)
            t.check_ignore = True  # 写真の画素の上に重ねる数字
            return t

        nums_a = VGroup(*[stroked(jp(str(ya[r, c]), 40, INK).move_to(cell_xy(PHOTO_L, r, c))) for r in range(NR) for c in range(NC)])
        nums_b = VGroup(*[stroked(jp(str(yb[r, c]), 40, INK).move_to(cell_xy(PHOTO_R, r, c))) for r in range(NR) for c in range(NC)])
        self.play(LaggedStart(*[FadeIn(t) for t in nums_a], lag_ratio=0.03), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(t) for t in nums_b], lag_ratio=0.03), run_time=1.2)

        # ---- ずれている画素だけ珊瑚色に、差の数字 ----
        self.at("diff", -0.1)
        diffs, shifts = VGroup(), []
        for r in range(NR):
            for c in range(NC):
                d = int(diff[r, c])
                if d:
                    t = stroked(jp(("+" if d > 0 else "−") + str(abs(d)), 30, CORAL).move_to(cell_xy(PHOTO_R, r, c) + DOWN * u(27)))
                    diffs.add(t)
                    n = nums_b[r * NC + c]
                    shifts.append(n.animate.set_color(CORAL).shift(UP * u(15)))
        assert len(diffs) > 0
        self.play(*shifts, LaggedStart(*[FadeIn(t, shift=UP * u(6)) for t in diffs], lag_ratio=0.04), run_time=1.6)

        # ---- 元の大きさに戻す ----
        self.at("back", -0.1)
        self.play(FadeOut(VGroup(nums_a, nums_b, diffs, grids)), Zoom(left, right, 1, 0), run_time=1.8)

        # ---- 人の目が気づきにくいところ ----
        self.at("eye", -0.1)
        eq = jp("＝？", 56, YELLOW).move_to(px(960, PHOTO_Y))
        self.play(FadeIn(eq, scale=0.7), run_time=0.6)
        self.play(pop(eq, 1.25, 0.5))

        # ---- タイトル ----
        self.at("title", -0.2)
        title = jp("JPEGは何を捨てている？", 72).move_to(px(960, 300))
        self.play(FadeOut(Group(left, right, eq, lbl_a, lbl_b), scale=0.6), FadeIn(title), run_time=1.2)
        self.finish()
