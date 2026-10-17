"""強調と動きの小道具。強調は 拡大(pop)・下線(underline)・文字色(tint)・揺らす(shake) を使い分ける。"""
import numpy as np
from manim import *  # noqa

from .scene import u


def pop(m, scale=1.25, run_time=0.6):
    """拡大して戻る（今から話す1つを示す）"""
    return m.animate(rate_func=there_and_back, run_time=run_time).scale(scale)


def underline(m, color, buff=6, width=4):
    return Line(m.get_corner(DL) + DOWN * u(buff), m.get_corner(DR) + DOWN * u(buff),
                color=color, stroke_width=width)


class Shake(Animation):
    """左右に揺らして止まる（意外・異常）"""

    def __init__(self, m, amp=10, run_time=0.5, **kw):
        super().__init__(m, run_time=run_time, rate_func=linear, **kw)
        self.amp = u(amp)

    def interpolate_mobject(self, alpha):
        self.mobject.become(self.starting_mobject)
        self.mobject.shift(RIGHT * self.amp * np.sin(alpha * 4 * TAU) * (1 - alpha))


def retext(old, new, **kw):
    """数字などの書き換え。同じオブジェクトのまま形を変え、検査用の text も更新する"""
    new.move_to(old)
    old.text = getattr(new, "text", None)
    return Transform(old, new, **kw)
