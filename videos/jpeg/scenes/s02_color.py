import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402

from vlib.data import pixels, ycc  # noqa: E402
from zunda.fx import pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import StageMap  # noqa: E402

CC_LO, CC_HI = 80, 176          # Cb・Cr を白黒で見せる範囲（128 を真ん中に）
SIGMA = 4                        # ぼかしの強さ（画素）
PIX = (110, 150)                 # 例の1画素（行, 列）
RGB_COL = ("#e5534b", "#57ab5a", BLUE)
BASE_Y, BAR_W = 730, 100          # 棒の底の y と棒の幅
BAR_X = (900, 1090, 1280)


def to_rgb(Y, Cb, Cr):
    """JFIF の式で RGB に戻す（tools/jpeganalyze.py と同じ式）"""
    rgb = np.stack([Y + 1.402 * (Cr - 128),
                    Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128),
                    Y + 1.772 * (Cb - 128)], -1)
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)


def gray8(a, lo=0, hi=255):
    g = np.clip((a - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return np.dstack([g, g, g])


def img(arr, width_px, center):
    m = ImageMobject(arr)
    m.width = u(width_px)
    return m.move_to(px(*center))


def tr(old, new):
    """文字の書き換え（位置も new のものに）。検査用の text も更新"""
    old.text = getattr(new, "text", None)
    return Transform(old, new)


class S02(PScene):
    def construct(self):
        cat = pixels("cat")[..., :3]
        Y, Cb, Cr = [ycc("cat")[..., i] for i in range(3)]
        assert np.abs(to_rgb(Y, Cb, Cr).astype(int) - cat).max() <= 2   # 式の確認

        # 2通りのぼかし（実データ）
        left_arr = to_rgb(gaussian_filter(Y, SIGMA), Cb, Cr)                                # 明るさだけぼかす
        right_arr = to_rgb(Y, gaussian_filter(Cb, SIGMA), gaussian_filter(Cr, SIGMA))      # 色だけぼかす

        # ---- 始まり：S01 の終わり（タイトル）----
        title = jp("JPEGは何を捨てている？", 72).move_to(px(960, 300))
        title.check_ignore = True   # S01 から続くタイトル（最初の台詞で消える）
        self.add(title)

        self.at("s02_01")
        self.play(FadeOut(title, shift=UP * u(10)), run_time=0.6)
        photo = img(cat, 510, (960, 340))
        self.play(FadeIn(photo), run_time=0.8)

        # ---- 写真が2つに複製されて左右へ ----
        self.at("blur", -0.1)
        right = photo.copy()
        self.play(photo.animate.move_to(px(700, 340)), right.animate.move_to(px(1220, 340)), run_time=0.9)

        self.at("left", -0.1)
        lbl_l = jp("明るさだけぼかす", 32).move_to(px(700, 565))
        self.play(Transform(photo, img(left_arr, 510, (700, 340))), FadeIn(lbl_l, shift=UP * u(8)), run_time=1.4)
        self.at("right", -0.1)
        lbl_r = jp("色だけぼかす", 32).move_to(px(1220, 565))
        self.play(Transform(right, img(right_arr, 510, (1220, 340))), FadeIn(lbl_r, shift=UP * u(8)), run_time=1.4)

        # ---- 人の目の性質 ----
        self.at("bright", -0.1)
        sens_l = jp("明るさ：敏感", 40, YELLOW).move_to(px(700, 650))
        self.play(FadeIn(sens_l, shift=UP * u(8)), run_time=0.6)
        self.at("color", -0.1)
        sens_r = jp("色：鈍い", 40, BLUE).move_to(px(1220, 650))
        self.play(FadeIn(sens_r, shift=UP * u(8)), run_time=0.6)

        self.at(31.0)
        self.play(pop(sens_r, 1.25, 0.6), run_time=0.6)
        self.at("split", -0.1)
        self.play(pop(sens_l, 1.2, 0.6), pop(sens_r, 1.2, 0.6), run_time=0.6)

        # ---- 1画素 = 赤・緑・青の3つの数字 ----
        self.at("s02_08", -0.1)
        pic = img(cat, 360, (620, 190))
        self.play(Transform(photo, pic), FadeOut(right), FadeOut(lbl_l), FadeOut(lbl_r), FadeOut(sens_l),
                  FadeOut(sens_r), run_time=0.8)
        self.at("rgb", -0.1)
        r, c = PIX
        R, G, B = [int(v) for v in cat[r, c]]
        sc = 360 / cat.shape[1]
        col = rgb_to_color(np.array([R, G, B]) / 255)
        marker = Square(side_length=u(14), stroke_color=YELLOW, stroke_width=3, fill_color=col, fill_opacity=1)
        marker.move_to(photo.get_corner(UL) + RIGHT * u((c + 0.5) * sc) + DOWN * u((r + 0.5) * sc))
        swatch = Square(side_length=u(120), stroke_width=0, fill_color=col, fill_opacity=1).move_to(px(620, 400))
        self.play(FadeIn(marker, scale=2), run_time=0.4)
        sw_src = marker.copy()
        sw_src.check_ignore = True
        self.add(sw_src)
        self.play(ReplacementTransform(sw_src, swatch), run_time=0.8)

        def bar(i, val, color, name, name_col=INK):
            rect = Rectangle(width=u(BAR_W), height=u(2 * val), stroke_width=0, fill_color=color, fill_opacity=1)
            rect.move_to(px(BAR_X[i], BASE_Y), aligned_edge=DOWN)
            num = jp(str(val), 32).next_to(rect, UP, buff=u(10))
            nm = jp(name, 32, name_col).move_to(px(BAR_X[i], BASE_Y + 36))
            return VGroup(rect, num, nm)

        bars = [bar(i, v, RGB_COL[i], n, RGB_COL[i]) for i, (v, n) in enumerate(zip((R, G, B), "RGB"))]
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(12)) for b in bars], lag_ratio=0.25), run_time=1.5)

        # ---- 3本が、Y・Cb・Cr に作り直される ----
        self.at("ycc", -0.1)
        yv = 0.299 * R + 0.587 * G + 0.114 * B
        cbv = -0.168736 * R - 0.331264 * G + 0.5 * B + 128
        crv = 0.5 * R - 0.418688 * G - 0.081312 * B + 128
        y0, cb0, cr0 = ycc("cat")[r, c]
        assert np.allclose([yv, cbv, crv], [y0, cb0, cr0])
        Yi, Cbi, Cri = int(round(yv)), int(round(cbv)), int(round(crv))
        new = [bar(0, Yi, INK, "Y", INK), bar(1, Cbi, BLUE, "Cb", BLUE), bar(2, Cri, CORAL, "Cr", CORAL)]
        anims = []
        for old, nw in zip(bars, new):
            old[1].text = nw[1].text
            old[2].text = nw[2].text
            anims.append(Transform(old, nw))
        self.play(LaggedStart(*anims, lag_ratio=0.15), run_time=1.6)

        # ---- Y = 0.299R + 0.587G + 0.114B ----
        self.at("y", -0.1)
        assert abs(0.299 * R + 0.587 * G + 0.114 * B - Yi) < 0.5
        t1, t2, t3 = f"0.299×{R}", f"0.587×{G}", f"0.114×{B}"
        formula = jp(f"Y ＝ {t1} ＋ {t2}\n　＋ {t3} ＝ {Yi}", 42,
                     t2c={t1: RGB_COL[0], t2: RGB_COL[1], t3: RGB_COL[2]}).move_to(px(1000, 845))
        self.play(pop(bars[0], 1.12, 0.5), FadeIn(formula, shift=UP * u(8)), run_time=0.8)

        self.at("cb", -0.1)
        ul_b = underline(bars[1][2], BLUE)
        self.play(Create(ul_b), run_time=0.5)
        self.at("cr", -0.1)
        ul_r = underline(bars[2][2], CORAL)
        self.play(Create(ul_r), run_time=0.5)

        # ---- 写真全体を3枚に分ける ----
        self.at("planes", -0.1)
        pos = [(520, 320), (960, 320), (1400, 320)]
        planes = [gray8(Y), gray8(Cb, CC_LO, CC_HI), gray8(Cr, CC_LO, CC_HI)]
        cb_img, cr_img = photo.copy(), photo.copy()
        self.add(cb_img, cr_img)
        gone = Group(*bars, formula, ul_b, ul_r, swatch, marker)
        self.play(FadeOut(gone), run_time=0.5)
        self.play(Transform(photo, img(planes[0], 390, pos[0])), Transform(cb_img, img(planes[1], 390, pos[1])),
                  Transform(cr_img, img(planes[2], 390, pos[2])), run_time=1.4)
        names = [jp("Y（明るさ）", 32), jp("Cb（青み）", 32, BLUE), jp("Cr（赤み）", 32, CORAL)]
        for n, p in zip(names, pos):
            n.move_to(px(p[0], 500))
        self.play(LaggedStart(*[FadeIn(n, shift=UP * u(8)) for n in names], lag_ratio=0.2), run_time=0.8)

        # ---- 地図 ----
        self.at("s02_13", 0.3)
        m = StageMap("full")
        first = m.parts["color"].get_center()
        thumbs = Group(photo, cb_img, cr_img)
        self.play(FadeOut(Group(*names)),
                  *[t.animate.scale(0.18).move_to(first).set_opacity(0) for t in thumbs], run_time=1.3)
        self.remove(*thumbs)
        self.at("map", -0.1)
        self.play(FadeIn(m), run_time=0.9)
        self.play(Transform(m, m.state("full", done=("color",))), run_time=0.5)
        self.finish()
