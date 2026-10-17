import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from vlib.smap import StageMap  # noqa: E402

ALL = ("color", "sub", "block", "dct", "quant", "code")

# クレジット（tools/description.py と同じ文言）
CREDITS = [("音声", ["VOICEVOX:ずんだもん", "VOICEVOX:四国めたん"]), ("立ち絵", ["坂本アヒル 様"]),
           ("音楽", ["甘茶の音楽工房"]), ("効果音", ["効果音ラボ"]),
           ("フォント", ["Zen Maru Gothic", "M PLUS Rounded 1c", "JetBrains Mono"]),
           ("映像", ["Manim Community"]), ("写真", ["Chelsea the cat（Stefan van der Walt, CC0）"])]


class S11(PScene):
    def construct(self):
        # ---- 始まりは空。地図が全体に ----
        m = StageMap("full", done=())
        self.at("eye", -0.1)
        self.play(FadeIn(m, shift=DOWN * u(12)), run_time=0.8)

        # ---- 4つの要約。話した段に点（と、捨てる段の印）が付く ----
        steps = [("c1", ("color", "sub"), ("sub",)), ("c2", ("color", "sub", "block", "dct"), ("block", "dct")),
                 ("c3", ("color", "sub", "block", "dct", "quant"), ("quant",)), ("c4", ALL, ("code",))]
        for cue, done, hot in steps:
            self.at(cue, -0.1)
            self.play(Transform(m, m.state("full", active=None, done=done)),
                      *[pop(m.parts[k], 1.2, 0.8) for k in hot], run_time=0.8)

        # ---- PNG は何も捨てない（印を薄く）→ JPEG は上手に捨てる（印が戻る）----
        lossy = [m.lossy[k] for k in ("sub", "quant")]
        self.at("s11_06")
        self.play(*[x.animate.set_opacity(0.2) for x in lossy], run_time=0.6)
        self.at(26.0)
        self.play(*[x.animate.set_opacity(1) for x in lossy], run_time=0.5)
        self.at(27.1)
        self.play(*[pop(x, 1.3, 0.6) for x in lossy], run_time=0.6)

        # ---- 図が消えて、クレジット ----
        title = jp("クレジット", 44, INK).move_to(px(960, 90))
        cred = Group(title)
        y = 170
        for cat, vals in CREDITS:
            cred.add(jp(cat, 30, DIM).move_to(px(470, y), aligned_edge=LEFT))
            for v in vals:
                cred.add(mix(v, 30, INK).move_to(px(660, y), aligned_edge=LEFT))
                y += 50
            y += 12
        self.at("S11_08.end", 0.3)  # めたんの「思い出してみてね」のあとの間で、図が消えてクレジット
        self.play(FadeOut(m), run_time=1.4, rate_func=smooth)
        self.play(FadeIn(cred, shift=UP * u(10)), run_time=1.0)

        # ---- 「ありがとう」「またね」のあと、ゆっくり消える ----
        self.at("S11_10.end", 0.8)
        self.play(FadeOut(cred), run_time=self.until(self.tl["duration"], -0.3))
        self.finish()
