import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.catview import CatView, ViewAnim  # noqa: E402
from vlib.data import pixels, vp8_info, y_orig, y_planes  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NAME = "cat_q80"
PHOTO_C, PHOTO_W = (770, 360), 640          # S02 の最後の写真
VIEW_C, VIEW_W, VIEW_H = (960, 340), 902, 600  # S04 の最初の画面
CC_LO, CC_HI = 80, 176                      # U・V を白黒で見せる範囲 (JPEG 編の S02 と同じ)
POS, PW = [(360, 262), (960, 262), (1560, 262)], 525
LAB_Y = 55


def gray8(a, lo=0, hi=255):
    g = np.clip((np.asarray(a, float) - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return np.dstack([g, g, g])


def img(arr, width_px, center):
    m = ImageMobject(arr)
    m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.width = u(width_px)
    return m.move_to(px(*center))


def tr(old, new):
    """同じオブジェクトのまま new の形・位置・色へ (検査用の text も更新)"""
    old.text = getattr(new, "text", None)
    return Transform(old, new)


class SweepView(CatView):
    """16×16 の格子が左上から広がる CatView。front=None なら CatView と同じ描画"""
    front = None

    def _render(self):
        if self.front is None:
            return super()._render()
        g = self.grid_mb
        self.grid_mb = 0.0
        a = super()._render().astype(np.float32)
        self.grid_mb = 1.0
        b = super()._render().astype(np.float32)
        self.grid_mb = g
        yy, xx = np.mgrid[0:self.OH, 0:self.OW]
        m = np.clip((self.front - (xx + yy)) / 120.0, 0, 1)[..., None]
        return (a * (1 - m) + b * m).astype(np.uint8)


class S03(PScene):
    def construct(self):
        v8 = vp8_info(NAME)
        mbw, mbh = v8["mbw"], v8["mbh"]
        assert (mbw, mbh) == (29, 19) and mbw * mbh == 551
        assert (mbw * 16 >= v8["width"] > (mbw - 1) * 16) and (mbh * 16 >= v8["height"] > (mbh - 1) * 16)
        Yp, Up, Vp = y_planes(NAME)
        H, W = Yp.shape
        assert Up.shape == ((H + 1) // 2, (W + 1) // 2) == Vp.shape
        assert CC_LO <= min(Up.min(), Vp.min()) and max(Up.max(), Vp.max()) <= CC_HI
        cat = pixels(NAME)
        Yo = y_orig()

        # ---- S02 の終わり：写真 ----
        photo = img(cat, PHOTO_W, PHOTO_C)
        photo.check_ignore = True
        self.add(photo)

        # ---- 明るさと色に分ける ----
        self.at("jpeg", -0.1)
        self.play(photo.animate.set(width=u(PW)).move_to(px(*POS[0])), run_time=1.0)
        u_img, v_img = photo.copy(), photo.copy()
        self.add(u_img, v_img)
        up2 = Up.repeat(2, 0).repeat(2, 1)[:H, :W]          # 半分の大きさの U・V を、元と同じ大きさに並べて見せる
        vp2 = Vp.repeat(2, 0).repeat(2, 1)[:H, :W]
        planes = [img(gray8(Yp), PW, POS[0]), img(gray8(up2, CC_LO, CC_HI), PW, POS[1]),
                  img(gray8(vp2, CC_LO, CC_HI), PW, POS[2])]
        names = [jp("Y（明るさ）", 34), jp("U（青み）", 34, BLUE), jp("V（赤み）", 34, CORAL)]
        for n, p in zip(names, POS):
            n.move_to(px(p[0], LAB_Y))
        self.at("ycc", -0.1)
        self.play(Transform(photo, planes[0]), Transform(u_img, planes[1]), Transform(v_img, planes[2]),
                  LaggedStart(*[FadeIn(n, shift=DOWN * u(8)) for n in names], lag_ratio=0.3), run_time=1.4)
        for m_ in (u_img, v_img):
            m_.check_ignore = True

        # ---- 色は縦横半分 ----
        self.at("half", -0.1)
        ph = PW * H / W
        outlines = VGroup(*[DashedVMobject(Rectangle(width=u(PW), height=u(ph), stroke_color=DIM, stroke_width=2),
                                           num_dashes=40).move_to(px(*p)) for p in POS[1:]])
        self.add(outlines)
        self.play(u_img.animate.scale(0.5), v_img.animate.scale(0.5), run_time=1.1)

        # Z「目は色の違いに鈍い」：小さくした色
        self.at("remember", 1.7)
        self.play(pop(u_img, 1.12, 0.7), pop(v_img, 1.12, 0.7), run_time=0.7)

        # ---- 明るさを 16×16 に切る ----
        self.at("s03_03", -0.75)
        view = SweepView(Yp, VIEW_C, VIEW_W, VIEW_H)
        view.width = photo.width
        view.move_to(photo)
        view.check_ignore = True
        self.remove(photo)
        self.add(view)
        self.play(u_img.animate.set_opacity(0), v_img.animate.set_opacity(0),
                  FadeOut(VGroup(*names, outlines)), view.animate.set(width=u(VIEW_W)).move_to(px(*VIEW_C)),
                  run_time=1.0)
        self.remove(u_img, v_img)

        self.at("grid", -0.1)
        y0, y1 = Yp.astype(np.float32), Yo.astype(np.float32)
        view.front = 0.0
        span = VIEW_W + VIEW_H + 120

        def sweep(t):
            view.front = t * span
            view.base = y0 * (1 - t) + y1 * t          # 見た目はほぼ同じ。ここから先は元の明るさ (S04 と同じ)
        self.play(ViewAnim(view, sweep, rate_func=linear), run_time=2.0)
        view.front = None
        view.grid_mb = 1.0
        view.base = y1
        view.refresh()

        # ---- 横に 29 個、縦に 19 個 ----
        self.at("count", -0.1)
        LO = 0.35
        row = np.zeros((mbh, mbw), np.float32)
        row[0, :] = 1
        col = np.zeros((mbh, mbw), np.float32)
        col[:, 0] = 1
        xs = np.arange(mbw, dtype=np.float32)[None, :].repeat(mbh, 0)
        ys = np.arange(mbh, dtype=np.float32)[:, None].repeat(mbw, 1)

        def dim(t):
            view.set_mb_lit(1 - (1 - LO) * t * np.ones((mbh, mbw)))
        self.play(ViewAnim(view, dim), run_time=0.4)
        f_txt = mix(f"{mbw} × {mbh} ＝ {mbw * mbh} ブロック", 42)
        f_txt.move_to(px(960, 715))
        # 横の 29 個 → 縦の 19 個 を光らせてから「29 × 19」(途中の「29」だけの状態は出さない)
        t29 = mix(f"{mbw} × {mbh}", 42, YELLOW)
        t29.move_to(f_txt.get_left(), aligned_edge=LEFT)

        def run_row(t):
            on = np.clip(t * (mbw + 3) - xs, 0, 1) * row
            view.set_mb_lit(LO + (1 - LO) * on)
        self.at("count", 0.5)
        self.play(ViewAnim(view, run_row, rate_func=linear), run_time=1.2)

        def run_col(t):
            on = np.maximum(row, np.clip(t * (mbh + 3) - ys, 0, 1) * col)
            view.set_mb_lit(LO + (1 - LO) * on)
        self.at("count", 1.8)
        self.play(ViewAnim(view, run_col, rate_func=linear, run_time=1.0), FadeIn(t29, shift=UP * u(8), run_time=0.4))

        self.at("count", 3.8)
        lit_now = view.lit.copy()

        def all_on(t):
            view.lit = lit_now + (1 - lit_now) * t
        self.play(ViewAnim(view, all_on), tr(t29, f_txt.copy()), run_time=0.8)
        view.set_mb_lit(np.ones((mbh, mbw)))
        view.refresh()

        # Z「JPEG は 8×8」
        self.at("jpeg8", 0.2)
        j8 = mix("JPEG は 8×8", 32, DIM).move_to(px(960, 790))
        self.play(FadeIn(j8, shift=UP * u(8)), run_time=0.6)

        # ---- その前に、JPEG にない工夫 (S04 の最初の画面へ) ----
        self.at("s03_05", -0.1)
        self.play(FadeOut(VGroup(t29, j8)), run_time=0.7)

        # S04 の最初と同じもの (同じ作り方) に置き換える
        final = CatView(Yo, VIEW_C, VIEW_W, VIEW_H)
        final.grid_mb = 1.0
        final.refresh()
        final.check_ignore = True
        assert np.array_equal(final.pixel_array, view.pixel_array)
        self.remove(view)
        self.add(final)
        self.finish()
