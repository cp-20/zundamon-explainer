"""猫の明るさ (Y) の画像を、拡大の窓・明るさの塗り分け・格子つきで映す部品 (S03〜S07 で同じ見た目で使う)。

- CatView(base, center, w, h)：画像 base (2 次元の明るさ) のうち窓 win (L, T, R, B) (画素の座標) を、箱 w×h px に映す
  - lit：画素ごとの明るさの倍率 (まだ作っていない所を暗く沈める)
  - layers：画素の上に重ねる値 [(x0, y0, 値の配列, 見えている割合の配列)]。予想を流し込むのに使う
  - grid_mb：16×16 の格子の濃さ、grid_sb：4×4 の格子の濃さ (sb_mb の MB の中だけ)
- ViewAnim(view, fn)：fn(t) で view の状態を変えて描き直すアニメーション
- zoom(view, win)：窓を、拡大率が一定の速さで変わるように動かす
"""
import numpy as np
from manim import *  # noqa
from PIL import Image

from zunda.scene import px, u

LINE = np.array([20, 22, 28], np.float32)     # 格子の線の色
SB_LINE = np.array([125, 132, 148], np.float32)
DIM_LIT = 0.16                                # まだ作っていない所の明るさ


class CatView(ImageMobject):
    def __init__(self, base, center=(960, 340), w=902, h=600, win=None, **kw):
        self.base = np.asarray(base, np.float32)
        H, W = self.base.shape
        self.size = (W, H)
        self.OW, self.OH = w, h
        self.win = tuple(win) if win is not None else (0, 0, W, H)
        self.lit = np.ones_like(self.base)
        self.layers = []
        self.grid_mb = 0.0
        self.grid_sb = 0.0
        self.sb_mb = None
        self.pix_grid = True
        super().__init__(self._render(), **kw)
        self.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        self.width = u(w)
        self.move_to(px(*center))

    # ---- 描画 ----
    def _render(self):
        L, T, R, B = self.win
        disp = self.base * self.lit
        for x0, y0, arr, mask in self.layers:
            h, w = arr.shape
            reg = disp[y0:y0 + h, x0:x0 + w]
            disp[y0:y0 + h, x0:x0 + w] = reg * (1 - mask) + arr * mask
        img = Image.fromarray(np.clip(disp, 0, 255).astype(np.uint8))
        out = np.asarray(img.resize((self.OW, self.OH), Image.NEAREST, box=(L, T, R, B))).astype(np.float32)
        out = np.repeat(out[..., None], 3, -1)
        sx = self.OW / (R - L)
        sy = self.OH / (B - T)

        def vline(x, a, col, wpx):
            c = int(round((x - L) * sx))
            if -wpx < c < self.OW + wpx:
                lo, hi = max(0, c - wpx // 2), min(self.OW, c + (wpx + 1) // 2)
                out[:, lo:hi] = out[:, lo:hi] * (1 - a) + col * a

        def hline(y, a, col, wpx):
            r = int(round((y - T) * sy))
            if -wpx < r < self.OH + wpx:
                lo, hi = max(0, r - wpx // 2), min(self.OH, r + (wpx + 1) // 2)
                out[lo:hi] = out[lo:hi] * (1 - a) + col * a
        # 画素の格子 (十分に拡大したときだけ)
        if self.pix_grid and sx >= 12:
            a = min(1.0, (sx - 12) / 24) * 0.45
            for x in range(int(np.ceil(L)), int(R) + 1):
                vline(x, a, LINE, 1 if sx < 40 else 2)
            for y in range(int(np.ceil(T)), int(B) + 1):
                hline(y, a, LINE, 1 if sx < 40 else 2)
        if self.grid_mb > 0:
            wpx = 2 if sx < 8 else 4
            for x in range(0, self.size[0] + 1, 16):
                if L - 1 <= x <= R + 1:
                    vline(x, 0.8 * self.grid_mb, LINE, wpx)
            for y in range(0, self.size[1] + 1, 16):
                if T - 1 <= y <= B + 1:
                    hline(y, 0.8 * self.grid_mb, LINE, wpx)
        if self.grid_sb > 0 and self.sb_mb is not None:
            mx, my = self.sb_mb
            x0, y0 = mx * 16, my * 16
            c0, c1 = int(round((x0 - L) * sx)), int(round((x0 + 16 - L) * sx))
            r0, r1 = int(round((y0 - T) * sy)), int(round((y0 + 16 - T) * sy))
            for k in (4, 8, 12):
                c = int(round((x0 + k - L) * sx))
                r = int(round((y0 + k - T) * sy))
                a = 0.9 * self.grid_sb
                if 0 <= c < self.OW:
                    ra, rb = max(0, r0), min(self.OH, r1)
                    out[ra:rb, max(0, c - 1):c + 2] = out[ra:rb, max(0, c - 1):c + 2] * (1 - a) + SB_LINE * a
                if 0 <= r < self.OH:
                    ca, cb = max(0, c0), min(self.OW, c1)
                    out[max(0, r - 1):r + 2, ca:cb] = out[max(0, r - 1):r + 2, ca:cb] * (1 - a) + SB_LINE * a
        rgb = np.clip(out, 0, 255).astype(np.uint8)
        return np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])

    def refresh(self):
        op = self.pixel_array[0, 0, 3] / 255 if hasattr(self, "pixel_array") else 1.0   # set_opacity の値を保つ
        self.pixel_array = self._render()
        self.pixel_array[:, :, 3] = round(255 * op)
        self.orig_alpha_pixel_array = np.full(self.pixel_array.shape[:2], 255, np.uint8)
        return self

    # ---- 座標 ----
    def to_point(self, x, y):
        """画像の画素座標 (小数可。画素の左上が整数) → Manim の座標"""
        L, T, R, B = self.win
        left, top = self.get_left()[0], self.get_top()[1]
        return np.array([left + (x - L) * self.width / (R - L), top - (y - T) * self.height / (B - T), 0])

    def pix(self):
        """1 画素の大きさ (Manim の単位)"""
        L, T, R, B = self.win
        return self.width / (R - L)

    # ---- 状態 ----
    def set_mb_lit(self, v):
        """MB ごとの明るさの倍率 v (縦 × 横 の配列) を画素に広げる"""
        H, W = self.size[1], self.size[0]
        big = np.kron(np.asarray(v, np.float32), np.ones((16, 16), np.float32))
        self.lit = big[:H, :W].copy()

    def track_rect(self, x0, y0, w, h, **style):
        """画素の範囲 (x0, y0, w, h) を囲む四角。窓が動いてもついてくる"""
        r = Rectangle(width=1, height=1, **style)

        def upd(m):
            a, b = self.to_point(x0, y0), self.to_point(x0 + w, y0 + h)
            m.stretch_to_fit_width(max(b[0] - a[0], 1e-3))
            m.stretch_to_fit_height(max(a[1] - b[1], 1e-3))
            m.move_to((a + b) / 2)
        upd(r)
        r.add_updater(upd)
        return r


class ViewAnim(Animation):
    def __init__(self, view, fn, **kw):
        super().__init__(view, **kw)
        self.fn = fn

    def interpolate_mobject(self, alpha):
        self.fn(self.rate_func(alpha))
        self.mobject.refresh()


def zoom(view, win, **kw):
    w0 = np.array(view.win, float)
    w1 = np.array(win, float)
    r = (w1[2] - w1[0]) / (w0[2] - w0[0])

    def fn(a):
        g = a if abs(r - 1) < 1e-9 else (1 - r ** a) / (1 - r)
        view.win = tuple(w0 + (w1 - w0) * g)
    kw.setdefault("rate_func", smooth)
    return ViewAnim(view, fn, **kw)


def window_around(cx, cy, h, aspect=1.5):
    """中心 (cx, cy) (画素) と高さ h の窓"""
    w = h * aspect
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def gray_img(a, size_px, vmin=0, vmax=255):
    """明るさ配列 → ドットのままの白黒 ImageMobject (幅 size_px)"""
    g = np.clip((np.asarray(a, float) - vmin) / (vmax - vmin) * 255, 0, 255).astype(np.uint8)
    k = max(1, 128 // max(g.shape))
    g = g.repeat(k, 0).repeat(k, 1)
    m = ImageMobject(np.dstack([g, g, g]))
    m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.width = u(size_px)
    return m
