import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import pixels, summary, ycc  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import StageMap  # noqa: E402

CC_LO, CC_HI = 80, 176          # Cb・Cr を白黒で見せる範囲（S02 と同じ）
PATCH = (88, 182)               # 2×2 にまとめる例（行, 列。偶数）
CELL = 110
L, BAR_H, BAR_X0, ROW_Y = 300, 80, 530, 450   # 棒1本の長さ（=数字1つ）, 高さ, 左端, 合計の行の y


def gray8(a, lo=0, hi=255):
    g = np.clip((a - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return np.dstack([g, g, g])


def img(arr, width_px, center, nearest=False):
    m = ImageMobject(arr)
    if nearest:
        m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.width = u(width_px)
    return m.move_to(px(*center))


def to_rgb(Y, Cb, Cr):
    rgb = np.stack([Y + 1.402 * (Cr - 128),
                    Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128),
                    Y + 1.772 * (Cb - 128)], -1)
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)


def subsample(a):
    """2×2 の平均で縦横半分に → 配り直して元の大きさに"""
    h, w = a.shape
    p = np.pad(a, ((0, h % 2), (0, w % 2)), mode="edge")
    half = p.reshape(p.shape[0] // 2, 2, p.shape[1] // 2, 2).mean((1, 3))
    return half, half.repeat(2, 0).repeat(2, 1)[:h, :w]


def cell_color(v):
    return rgb_to_color([float(np.clip((v - CC_LO) / (CC_HI - CC_LO), 0, 1))] * 3)


class S03(PScene):
    def construct(self):
        cat = pixels("cat")[..., :3]
        Y, Cb, Cr = [ycc("cat")[..., i] for i in range(3)]
        half_cb, up_cb = subsample(Cb)
        half_cr, up_cr = subsample(Cr)

        # JPEG ファイルの実際の間引き：Y は 2×2、Cb・Cr は 1×1（= Y の 4 点に 1 つ）
        cs = summary()["comps"]
        assert (cs[0]["h"], cs[0]["v"]) == (2, 2) and (cs[1]["h"], cs[1]["v"]) == (1, 1) == (cs[2]["h"], cs[2]["v"])
        ratio = cs[1]["blocks"] / cs[0]["blocks"]
        assert ratio == 0.25
        total = 1 + 2 * ratio
        assert total == 1.5 and (cs[0]["blocks"] + cs[1]["blocks"] + cs[2]["blocks"]) / (3 * cs[0]["blocks"]) == total / 3

        # ---- 始まり：S02 の終わり ----
        m = StageMap("full", done=("color",))
        self.add(m)

        self.at("s03_01")
        strip = m.state("strip", active="sub", done=("color",))
        strip.lossy["sub"].set_opacity(0)      # 「捨てる」の印は最後（lost）に
        self.play(Transform(m, strip), run_time=0.7)

        # ---- Cb の画像 ----
        self.at("sub", -0.1)
        cb = img(gray8(Cb, CC_LO, CC_HI), 570, (730, 340))
        cb_lbl = jp("Cb（青み）", 32, BLUE).move_to(px(730, 590))
        self.play(FadeIn(cb), FadeIn(cb_lbl, shift=UP * u(8)), run_time=0.8)

        # ---- 縦横 2 つずつ、4 つの点 ----
        self.at("grid", -0.1)
        r0, c0 = PATCH
        patch = Cb[r0:r0 + 2, c0:c0 + 2]
        vals = np.round(patch).astype(int)
        avg = float(patch.mean())
        assert int(round(avg)) == vals.sum() / 4          # 見せる数字だけで、平均が合う
        sc = 570 / cb.pixel_array.shape[1]
        marker = Square(side_length=u(16), stroke_color=YELLOW, stroke_width=3)
        marker.move_to(cb.get_corner(UL) + RIGHT * u((c0 + 1) * sc) + DOWN * u((r0 + 1) * sc))
        self.play(FadeIn(marker, scale=2), run_time=0.4)
        cells, nums = VGroup(), VGroup()
        for i in range(2):
            for j in range(2):
                sq = Square(side_length=u(CELL), stroke_width=2, stroke_color="#2a2e38",
                            fill_color=cell_color(vals[i, j]), fill_opacity=1)
                sq.move_to(px(1260 + CELL * (j - 0.5), 340 + CELL * (i - 0.5)))
                cells.add(sq)
                nums.add(jp(str(vals[i, j]), 40).move_to(sq))
        panel = VGroup(cells, nums)
        self.play(GrowFromPoint(panel, marker.get_center()), run_time=1.2)

        # ---- 平均の 1 つに ----
        self.at("one", -0.1)
        centre = px(1260, 340)
        avg_num = jp(str(int(round(avg))), 40).move_to(centre)
        avg_num.set_opacity(0)
        self.add(avg_num)
        self.play(*[sq.animate.move_to(centre).set_fill(cell_color(avg)) for sq in cells],
                  *[n.animate.move_to(centre).set_opacity(0) for n in nums],
                  avg_num.animate.set_opacity(1), run_time=1.0)
        self.remove(nums, *nums, *cells[1:])
        for n in nums:
            n.check_ignore = True

        # ---- 画像が縦横半分に（Cr も同じ）----
        self.at("quarter", -0.1)
        cr = img(gray8(Cr, CC_LO, CC_HI), 510, (1220, 340))
        cr_lbl = jp("Cr（赤み）", 32, CORAL).move_to(px(1220, 560))

        self.play(FadeOut(VGroup(cells[0], avg_num, marker)), FadeIn(cr), FadeIn(cr_lbl, shift=UP * u(8)),
                  run_time=0.6)
        cb_h = img(gray8(up_cb, CC_LO, CC_HI), 255, (700, 340), nearest=True)
        cr_h = img(gray8(up_cr, CC_LO, CC_HI), 255, (1220, 340), nearest=True)
        ghosts = [DashedVMobject(Rectangle(width=u(510), height=u(340), stroke_color=DIM, stroke_width=3)
                                 .move_to(px(x, 340)), num_dashes=60) for x in (700, 1220)]
        self.play(Transform(cb, cb_h), Transform(cr, cr_h), *[Create(g) for g in ghosts], run_time=1.2)

        # ---- 配り直して、Y と重ねる ----
        self.at("back", -0.1)
        cb_f = img(gray8(up_cb, CC_LO, CC_HI), 510, (700, 340), nearest=True)
        cr_f = img(gray8(up_cr, CC_LO, CC_HI), 510, (1220, 340), nearest=True)
        self.play(Transform(cb, cb_f), Transform(cr, cr_f), *[FadeOut(g) for g in ghosts], run_time=1.0)
        y_img = img(gray8(Y), 510, (960, 340))
        cb.check_ignore = cr.check_ignore = y_img.check_ignore = True   # 重ねている途中
        self.add(y_img)
        y_img.set_opacity(0)
        self.play(cb.animate.move_to(px(960, 340)), cr.animate.move_to(px(960, 340)),
                  y_img.animate.set_opacity(1), FadeOut(cb_lbl), FadeOut(cr_lbl), run_time=1.1)
        comp_arr = to_rgb(Y, up_cb, up_cr)
        comp = img(comp_arr, 510, (960, 340))
        comp.set_opacity(0)
        self.add(comp)
        self.play(comp.animate.set_opacity(1), run_time=0.8)
        self.remove(cb, cr, y_img)

        # ---- 元の写真と並べる ----
        self.at("check", -0.1)
        orig = img(cat, 510, (1220, 340))
        lbl_a = jp("色を間引いた写真", 32).move_to(px(700, 560))
        lbl_b = jp("元の写真", 32).move_to(px(1220, 560))
        orig.set_opacity(0)
        self.add(orig)
        self.play(comp.animate.move_to(px(700, 340)), orig.animate.set_opacity(1),
                  FadeIn(lbl_a, shift=UP * u(8)), FadeIn(lbl_b, shift=UP * u(8)), run_time=1.0)

        # ---- 数で比べる：点ごとに 3 つ → 1 つと 4 分の 1 が 2 つ ----
        self.at("count", -0.1)
        self.play(FadeOut(Group(comp, orig, lbl_a, lbl_b)), run_time=0.4)

        def seg(name, color, x, y, w=L):
            rect = Rectangle(width=u(w), height=u(BAR_H), stroke_width=0, fill_color=color, fill_opacity=1)
            rect.move_to(px(x, y), aligned_edge=LEFT)
            lab = jp(name, 32, BG).move_to(px(x + w / 2, y))
            return VGroup(rect, lab)

        rows = [seg("Y", INK, BAR_X0, 320), seg("Cb", BLUE, BAR_X0, 440), seg("Cr", CORAL, BAR_X0, 560)]
        self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * u(20)) for r in rows], lag_ratio=0.2), run_time=0.9)

        self.at("before", -0.1)
        line = [seg("Y", INK, BAR_X0, ROW_Y), seg("Cb", BLUE, BAR_X0 + L, ROW_Y), seg("Cr", CORAL, BAR_X0 + 2 * L, ROW_Y)]
        n3 = jp("3", 40, YELLOW).move_to(px(BAR_X0 + 3 * L + 40, ROW_Y))
        self.play(*[Transform(r, s) for r, s in zip(rows, line)], FadeIn(n3, shift=LEFT * u(8)), run_time=1.0)

        self.at("after", -0.1)
        w = L * ratio
        small = [seg("Y", INK, BAR_X0, ROW_Y), seg("Cb", BLUE, BAR_X0 + L, ROW_Y, w),
                 seg("Cr", CORAL, BAR_X0 + L + w, ROW_Y, w)]
        ghost = DashedVMobject(Rectangle(width=u(3 * L), height=u(BAR_H + 16), stroke_color=DIM, stroke_width=3)
                               .move_to(px(BAR_X0 + 1.5 * L, ROW_Y)), num_dashes=60)
        n15 = jp("1.5", 40, YELLOW).move_to(px(BAR_X0 + total * L + 45, ROW_Y))
        self.play(*[Transform(r, s) for r, s in zip(rows, small)], Create(ghost),
                  FadeIn(n15, shift=LEFT * u(8)), run_time=1.2)

        self.at("half", -0.1)
        half = jp("半分", 48, YELLOW).move_to(px(BAR_X0 + total * L / 2, 570))
        self.play(FadeIn(half, shift=UP * u(8)), pop(n15, 1.25, 0.6), run_time=0.8)

        # ---- 捨てた色はもう戻らない：地図に印 ----
        self.at("lost", -0.1)
        self.play(FadeOut(Group(*rows, n3, n15, half, ghost)),
                  Transform(m, m.state("full", done=("color", "sub"))), run_time=1.2)
        self.play(pop(m.lossy["sub"], 1.4, 0.6), run_time=0.6)
        self.finish()
