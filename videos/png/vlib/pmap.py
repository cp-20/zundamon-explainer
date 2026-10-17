"""全体像の「地図」。S04 で作り、以降のシーンで同じ配置のまま戻ってくる。

    m = PipelineMap()                       # 全体表示（S04 の終わりの状態）
    self.play(Transform(m, m.state("strip", active="filter")))
"""
from manim import *  # noqa

from vlib.data import fmt, info
from zunda.scene import BG, DIM, INK, jp, px, u

STAGE_COL = {"filter": "#f5a85b", "lz77": "#4fd1e8", "huff": "#c792ea"}
ORDER = ["pixels", "filter", "lz77", "huff", "zlib", "idat"]


class PipelineMap(VGroup):
    def __init__(self, mode="full", active=None, done=(), **kw):
        super().__init__(**kw)
        z = info("zundamon")
        self.mode, self.active, self.done = mode, active, tuple(done)
        self.parts = {}
        # 段（フィルタ・LZ77・ハフマン）は塗りだけの丸い札、データ（画素・zlib・IDAT）は文字だけ
        for key, label in [("filter", "フィルタ"), ("lz77", "LZ77"), ("huff", "ハフマン")]:
            t = jp(label, 40)
            pill = RoundedRectangle(corner_radius=u(34), width=t.width + u(64), height=u(76),
                                    fill_color=STAGE_COL[key], fill_opacity=0.22, stroke_width=0)
            t.move_to(pill)
            self.parts[key] = VGroup(pill, t)
        for key, label, size in [("pixels", "画素", z["pixel_bytes"]), ("zlib", "zlib", z["idat_bytes"]),
                                 ("idat", "IDAT", None)]:
            t = jp(label, 40)
            self.parts[key] = VGroup(t)
        row = VGroup(*[self.parts[k] for k in ORDER]).arrange(RIGHT, buff=u(96))
        self.arrows = VGroup(*[
            Arrow(self.parts[a].get_right(), self.parts[b].get_left(), buff=u(16), stroke_width=4,
                  max_tip_length_to_length_ratio=0.35, color=DIM)
            for a, b in zip(ORDER, ORDER[1:])])
        # 大きさのラベル（実データ）
        self.sizes = VGroup(
            jp(fmt(z["pixel_bytes"]), 26, DIM).next_to(self.parts["pixels"], DOWN, buff=u(18)),
            jp(fmt(z["raw_bytes"]), 26, DIM).next_to(self.arrows[1], DOWN, buff=u(26)),
            jp(fmt(z["idat_bytes"]), 26, DIM).next_to(self.parts["zlib"], DOWN, buff=u(18)),
        )
        lz, hf = self.parts["lz77"], self.parts["huff"]
        br = VGroup(Line(lz.get_corner(UL) + UP * u(22), hf.get_corner(UR) + UP * u(22), stroke_width=3, color=DIM))
        br.add(Line(br[0].get_start(), br[0].get_start() + DOWN * u(10), stroke_width=3, color=DIM),
               Line(br[0].get_end(), br[0].get_end() + DOWN * u(10), stroke_width=3, color=DIM))
        self.deflate = VGroup(br, jp("DEFLATE", 26, DIM).next_to(br, UP, buff=u(8)))
        self.sizes[1].align_to(self.sizes[0], DOWN)
        # 済んだ段に付ける印（小さな点）
        self.checks = VGroup(*[Dot(radius=u(9), color=STAGE_COL[k]).next_to(self.parts[k], UP, buff=u(12))
                               for k in ("filter", "lz77", "huff")])
        self.add(row, self.arrows, self.sizes, self.deflate, self.checks)
        self.row = row
        self._place()
        self._style()

    def _place(self):
        if self.mode == "full":
            self.scale_to_fit_width(u(1700)).move_to(px(960, 250))
        else:  # strip：画面上端の細い帯
            self.scale_to_fit_width(u(960)).move_to(px(960, 60))

    def _style(self):
        for k in ("filter", "lz77", "huff"):
            pill, t = self.parts[k]
            if self.active == k:
                pill.set_fill(STAGE_COL[k], 0.9); t.set_color(BG)
            elif self.active and self.mode == "strip":
                pill.set_fill(STAGE_COL[k], 0.12); t.set_color(DIM)
        for d, k in zip(self.checks, ("filter", "lz77", "huff")):
            d.set_opacity(1 if k in self.done else 0)
        if self.mode == "strip":
            self.sizes.set_opacity(0)
            self.deflate.set_opacity(0)
            self.checks.set_opacity(0)
            for k in ("pixels", "zlib", "idat"):
                self.parts[k].set_color(DIM)

    def state(self, mode=None, active=None, done=None):
        return PipelineMap(mode or self.mode, active, self.done if done is None else done)
