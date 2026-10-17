"""JPEG の工程の「地図」。S02 の終わりで作り、以降のシーンで同じ配置のまま戻ってくる。

    m = StageMap()                                   # 全体表示
    self.play(Transform(m, m.state("strip", active="sub")))

段：color（色を分ける）→ sub（色を間引く）→ block（8×8に切る）→ dct（波に分ける）
    → quant（割って丸める）→ code（並べて符号に）。sub と quant は「捨てる」段で、珊瑚の印 m.lossy[key] が付く。
"""
from manim import *  # noqa

from zunda.scene import BG, CORAL, DIM, INK, jp, px, u

ORDER = ["color", "sub", "block", "dct", "quant", "code"]
LABEL = {"color": "色を分ける", "sub": "色を間引く", "block": "8×8に切る", "dct": "波に分ける",
         "quant": "割って丸める", "code": "並べて符号に"}
STAGE_COL = {"color": "#f2c14e", "sub": "#6fb7ff", "block": "#9aa4b8", "dct": "#c792ea",
             "quant": "#ff7a6b", "code": "#4fd1e8"}
LOSSY = ("sub", "quant")


class StageMap(VGroup):
    def __init__(self, mode="full", active=None, done=(), **kw):
        super().__init__(**kw)
        self.mode, self.active, self.done = mode, active, tuple(done)
        self.parts = {}
        for key in ORDER:
            t = jp(LABEL[key], 36)
            pill = RoundedRectangle(corner_radius=u(32), width=t.width + u(52), height=u(72),
                                    fill_color=STAGE_COL[key], fill_opacity=0.22, stroke_width=0)
            t.move_to(pill)
            self.parts[key] = VGroup(pill, t)
        row = VGroup(*[self.parts[k] for k in ORDER]).arrange(RIGHT, buff=u(54))
        self.arrows = VGroup(*[
            Arrow(self.parts[a].get_right(), self.parts[b].get_left(), buff=u(8), stroke_width=4,
                  max_tip_length_to_length_ratio=0.4, color=DIM)
            for a, b in zip(ORDER, ORDER[1:])])
        # 捨てる段の印（下に珊瑚の「捨てる」）
        self.lossy = {k: jp("捨てる", 26, CORAL).next_to(self.parts[k], DOWN, buff=u(14)) for k in LOSSY}
        # 済んだ段の点
        self.checks = VGroup(*[Dot(radius=u(9), color=STAGE_COL[k]).next_to(self.parts[k], UP, buff=u(12))
                               for k in ORDER])
        self.add(row, self.arrows, *self.lossy.values(), self.checks)
        self.row = row
        self._place()
        self._style()

    def _place(self):
        if self.mode == "full":
            self.scale_to_fit_width(u(1760)).move_to(px(960, 250))
        else:  # strip：画面上端の細い帯
            self.scale_to_fit_width(u(1180)).move_to(px(960, 56))

    def _style(self):
        for k in ORDER:
            pill, t = self.parts[k]
            if self.active == k:
                pill.set_fill(STAGE_COL[k], 0.9); t.set_color(BG)
            elif self.active and self.mode == "strip":
                pill.set_fill(STAGE_COL[k], 0.12); t.set_color(DIM)
        for d, k in zip(self.checks, ORDER):
            d.set_opacity(1 if k in self.done else 0)
        for k, m in self.lossy.items():
            # 捨てる印は、その段まで話が進んでから（済み or 今いる段）
            m.set_opacity(1 if (k in self.done or k == self.active) else 0)
        if self.mode == "strip":
            self.checks.set_opacity(0)
            for k, m in self.lossy.items():
                m.set_opacity(0.0 if self.active != k else 1)

    def state(self, mode=None, active=None, done=None):
        return StageMap(mode or self.mode, active, self.done if done is None else done)
