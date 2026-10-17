"""Manim（cairo）の描画を速くする差し替え。zunda/scene.py が読み込むと有効になる。

- 画像（ImageMobject）は、変形した画像を「画面いっぱいの画像」に貼ってから全体を重ねていた。
  変形した範囲だけを、画面の配列のその部分に直接重ねる（1 枚あたり画面全体の変換が 2 回減る）。
- 不透明度 0 の画像は描かない（動く画像を opacity で切り替えるとき、隠れているコマを描かない）。
- Text の 1 文字ごとの SVG のパスは読むだけなので、図形の deepcopy のときに共有する。
"""
import numpy as np
import svgelements
from manim.camera.camera import Camera
from PIL import Image

svgelements.Path.__deepcopy__ = lambda self, memo: self

_orig_display = Camera.display_image_mobject


def _display_image_mobject(self, image_mobject, pixel_array):
    if getattr(image_mobject, "stroke_opacity", 1) <= 0:
        return
    sub = Image.fromarray(image_mobject.get_pixel_array(), mode="RGBA")
    W0, H0 = sub.width, sub.height
    tc = self.points_to_subpixel_coords(image_mobject, image_mobject.points).astype(np.float64)
    # 回転・ゆがみのない、ふつうの置き方なら単純な拡大縮小（いちばん多い）
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = tc
    axis = abs(y0 - y1) < 1e-6 and abs(x0 - x2) < 1e-6 and abs(x1 - x3) < 1e-6 and abs(y2 - y3) < 1e-6
    if not axis:
        return _orig_display(self, image_mobject, pixel_array)
    left, top, right, bottom = x0, y0, x1, y2
    if right <= left or bottom <= top:
        return
    ix0, iy0, ix1, iy1 = round(left), round(top), round(right), round(bottom)
    ph, pw = pixel_array.shape[:2]
    cx0, cy0, cx1, cy1 = max(ix0, 0), max(iy0, 0), min(ix1, pw), min(iy1, ph)
    if cx0 >= cx1 or cy0 >= cy1:
        return
    # 画面の (cx0..cx1, cy0..cy1) に入る部分だけを、元の画像から切り出して拡大縮小する
    sx = W0 / (right - left)
    sy = H0 / (bottom - top)
    box = (min(max((cx0 - left) * sx, 0), W0), min(max((cy0 - top) * sy, 0), H0),
           min(max((cx1 - left) * sx, 0), W0), min(max((cy1 - top) * sy, 0), H0))
    if box[2] <= box[0] or box[3] <= box[1]:
        return
    piece = sub.resize((cx1 - cx0, cy1 - cy0), resample=image_mobject.resampling_algorithm, box=box)
    region = pixel_array[cy0:cy1, cx0:cx1]
    bg = Image.fromarray(np.ascontiguousarray(region), mode="RGBA")
    region[...] = np.asarray(Image.alpha_composite(bg, piece))


Camera.display_image_mobject = _display_image_mobject
