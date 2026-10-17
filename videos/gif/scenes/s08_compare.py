import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import file_bytes, fmt, frame_rgba, info, pixels  # noqa: E402
from zunda.fx import pop, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

FORMATS = [("PNG", "cat", BLUE), ("GIF", "cat_nodither", YELLOW), ("JPEG", "cat_q80", CORAL)]
PHOTO_H, PHOTO_Y = 240, 200                    # 写真の高さと中心
PHOTO_X = [400, 960, 1520]
BAR_X0, BAR_MAX, BAR_H = 640, 480, 60          # 棒の左端・最長・太さ
BAR_Y = [540, 640, 740]


class S08(PScene):
    def construct(self):
        sizes = [len(file_bytes(n)) for _, n, _ in FORMATS]
        assert sizes[1] < sizes[0] and sizes[2] < sizes[1]

        # ---- 猫の写真 3 枚 ----
        photos, names = [], []
        for (fm, name, col), x in zip(FORMATS, PHOTO_X):
            photos.append(png_mob(pixels(name), PHOTO_H).move_to(px(x, PHOTO_Y)))
            names.append(jp(fm, 36, col).move_to(px(x, 56)))
        self.at("s08_01", 0.3)
        self.play(LaggedStart(*[AnimationGroup(FadeIn(p, shift=UP * u(10)), FadeIn(n, shift=UP * u(6)))
                                for p, n in zip(photos, names)], lag_ratio=0.4), run_time=1.8)

        # ---- 大きさの棒（実際のバイト数）----
        bars, labels, rows = [], [], []
        for (fm, name, col), s, y in zip(FORMATS, sizes, BAR_Y):
            w = BAR_MAX * s / sizes[0]
            bar = Rectangle(width=u(w), height=u(BAR_H), stroke_width=0, fill_color=col, fill_opacity=1)
            bar.move_to(px(BAR_X0, y), aligned_edge=LEFT)
            nm = jp(fm, 40, col).move_to(px(BAR_X0 - 20, y), aligned_edge=RIGHT)
            lab = mix(f"{fmt(s)} バイト", 34, INK).next_to(bar, RIGHT, buff=u(20))
            bars.append(bar)
            labels.append(lab)
            rows.append(nm)

        def grow(k, rt=0.9):
            full = bars[k].copy()
            full.check_ignore = True
            bars[k].stretch_to_fit_width(u(2), about_edge=LEFT)
            self.add(rows[k])
            self.play(FadeIn(rows[k]), Transform(bars[k], full), FadeIn(labels[k], shift=RIGHT * u(10)), run_time=rt)

        self.at("gif", -0.2)
        grow(0)
        grow(1)
        self.play(pop(labels[1], 1.15, 0.5), run_time=0.5)

        # ---- 256 色に減らして色を捨てた ----
        self.at("colors", -0.1)
        c256 = mix("256 色", 34, CORAL).next_to(photos[1], DOWN, buff=u(14))
        self.play(FadeIn(c256, shift=UP * u(8)), run_time=0.6)
        self.play(pop(c256, 1.2, 0.5), run_time=0.5)

        # ---- JPEG のほうがずっと小さい ----
        self.at("jpeg", -0.3)
        grow(2)
        ul = underline(bars[2], CORAL)
        ul.shift(DOWN * u(4))
        self.play(Create(ul), run_time=0.5)

        # ---- GIF はいつ使う？：動くスタンプ ----
        self.at("s08_04", 1.6)
        self.play(FadeOut(Group(*photos, *names, c256, *bars, *rows, *labels, ul)), run_time=0.8)
        self.remove(*photos, *bars)
        inf = info()
        n = len(inf["frames"])
        delays = [f["gce"]["delay"] / 100 for f in inf["frames"]]
        assert n == 8 and abs(sum(delays) - 2.47) < 1e-6
        stamps = [png_mob(frame_rgba(k=k), 520, nearest=True).move_to(px(960, 460)) for k in range(n)]
        for s in stamps[1:]:
            s.set_opacity(0)
        self.at("when", -0.1)
        self.add(*stamps)
        self.play(FadeIn(stamps[0], shift=UP * u(10)), run_time=0.6)

        # ---- 動く：本物の待ち時間で入れ替える ----
        self.at("move", -0.1)
        end = self.tl["duration"] - 1.3
        k = 0
        while True:
            if self.now + delays[k] > end:
                break
            self.wait(delays[k])
            stamps[k].set_opacity(0)
            k = (k + 1) % n
            stamps[k].set_opacity(1)
        self.at(end)
        self.play(*[s.animate.set_opacity(0) for s in stamps], run_time=1.0)
        self.remove(*stamps)
        self.finish()
