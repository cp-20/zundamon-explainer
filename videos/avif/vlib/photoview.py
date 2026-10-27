"""写真を「窓」で映す部品と、写真の上に重ねる線 (ブロックの境目)。S03〜S09 で同じ見た目で使う (HEIC 編の vlib/photoview.py と同じ)。

- PhotoView(rgb, center, w, h)：写真 rgb のうち窓 win (L, T, R, B) (画素の座標) を、箱 w×h px に映す。
  - lit：画素ごとの明るさの倍率 (注目していない所を暗く沈める)
  - set_box(center, w, h)：箱の位置と大きさを変える (窓と一緒に動かすと「寄る」動きになる)
- PLine(view, (x0, y0), (x1, y1))：写真の画素の座標で引いた線。窓が動いてもついてくる。frac で真ん中から伸びる
- PRect(view, x, y, w, h)：写真の画素の範囲を囲む四角。窓が動いてもついてくる
- ViewAnim(view, fn)：fn(t) で状態を変えて描き直す。Grow(line)：線を真ん中から伸ばす
- move_view(view, win, box)：窓と箱を一緒に動かす (拡大率が一定の速さで変わる)
"""
import numpy as np
from manim import *  # noqa
from PIL import Image

from zunda.scene import px, u


PAD = 256
BG_RGB = np.array([0x14, 0x16, 0x1c], np.float32)


class PhotoView(ImageMobject):
    def __init__(self, rgb, center=(960, 386), w=1040, h=692, win=None, **kw):
        self.base = np.asarray(rgb, np.float32)[..., :3]
        H, W = self.base.shape[:2]
        self.size = (W, H)
        self.win = tuple(win) if win is not None else (0, 0, W, H)
        self.lit = None
        self.box = (center, w, h)
        super().__init__(self._render(), **kw)
        self.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        self._place()

    # ---- 描画 ----
    def _out_size(self):
        (_, w, h) = self.box
        k = config.pixel_height / 1080
        return max(2, round(w * k)), max(2, round(h * k))

    def _render(self):
        L, T, R, B = self.win
        img = self.base if self.lit is None else self.base * self.lit[..., None]
        ow, oh = self._out_size()
        # 窓が写真の外にかかるときは、まわりを背景の色で埋めてから切り出す
        P = PAD
        H, W = img.shape[:2]
        canvas = np.empty((H + 2 * P, W + 2 * P, 3), np.float32)
        canvas[:] = BG_RGB
        canvas[P:P + H, P:P + W] = img
        out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8)).resize(
            (ow, oh), Image.NEAREST, box=(L + P, T + P, R + P, B + P))
        a = np.asarray(out)
        return np.dstack([a, np.full(a.shape[:2], 255, np.uint8)])

    def _place(self):
        (c, w, h) = self.box
        self.stretch_to_fit_width(u(w))
        self.stretch_to_fit_height(u(h))
        self.move_to(px(*c))

    def refresh(self):
        op = self.pixel_array[0, 0, 3] / 255 if hasattr(self, "pixel_array") else 1.0   # set_opacity の値を保つ
        self.pixel_array = self._render()
        self.pixel_array[:, :, 3] = round(255 * op)
        self.orig_alpha_pixel_array = np.full(self.pixel_array.shape[:2], 255, np.uint8)
        self._place()
        return self

    # ---- 座標 ----
    def to_point(self, x, y):
        """写真の画素座標 (小数可。画素の左上が整数) → Manim の座標"""
        L, T, R, B = self.win
        (c, w, h) = self.box
        left, top = px(c[0] - w / 2, c[1] - h / 2)[:2]
        return np.array([left + (x - L) * u(w) / (R - L), top - (y - T) * u(h) / (B - T), 0])

    def to_px(self, x, y):
        """写真の画素座標 → 画面の px"""
        L, T, R, B = self.win
        (c, w, h) = self.box
        return c[0] - w / 2 + (x - L) * w / (R - L), c[1] - h / 2 + (y - T) * h / (B - T)

    def px_per_pixel(self):
        L, T, R, B = self.win
        return self.box[1] / (R - L)


class ViewAnim(Animation):
    def __init__(self, view, fn, **kw):
        super().__init__(view, **kw)
        self.fn = fn

    def interpolate_mobject(self, alpha):
        self.fn(self.rate_func(alpha))
        self.mobject.refresh()


def move_view(view, win=None, box=None, **kw):
    """窓と箱を一緒に動かす。拡大率 (箱の px ÷ 窓の画素) は等比で変え、
    注目する点 (寄るときは行き先の窓の中心、引くときは今の窓の中心) が、画面の上をまっすぐ行き先へ進むようにする
    (窓の中心をそのまま補間すると、注目する点がいったん外へ振れてから戻ってくる)"""
    w0 = np.array(view.win, float)
    w1 = np.array(win if win is not None else view.win, float)
    (c0, bw0, bh0) = view.box
    (c1, bw1, bh1) = box if box is not None else view.box
    c0, c1 = np.array(c0, float), np.array(c1, float)
    s0 = bw0 / (w0[2] - w0[0])
    s1 = bw1 / (w1[2] - w1[0])
    r = s1 / s0
    m0, m1 = (w0[:2] + w0[2:]) / 2, (w1[:2] + w1[2:]) / 2
    P = m1 if r >= 1 else m0                       # 注目する点 (写真の画素の座標)
    S0 = c0 + (P - m0) * s0                        # その点の、最初と最後の画面の位置 (px)
    S1 = c1 + (P - m1) * s1

    def fn(a):
        g = a if abs(r - 1) < 1e-9 else (r ** a - 1) / (r - 1)
        c = c0 + (c1 - c0) * g
        bw = bw0 + (bw1 - bw0) * g
        bh = bh0 + (bh1 - bh0) * g
        sc = s0 * r ** a
        S = S0 + (S1 - S0) * g
        wc = P - (S - c) / sc
        view.box = ((c[0], c[1]), bw, bh)
        view.win = (wc[0] - bw / sc / 2, wc[1] - bh / sc / 2, wc[0] + bw / sc / 2, wc[1] + bh / sc / 2)
    kw.setdefault("rate_func", smooth)
    return ViewAnim(view, fn, **kw)


class PLine(Line):
    """写真の画素の座標で引いた線。frac (0〜1) で真ん中から伸びる"""

    def __init__(self, view, a, b, frac=1.0, **style):
        style.setdefault("stroke_width", 4)
        super().__init__(ORIGIN, RIGHT, **style)
        self.view, self.a, self.b, self.frac = view, a, b, frac
        self.sync()
        self.add_updater(lambda m: m.sync())

    def sync(self):
        (ax, ay), (bx, by) = self.a, self.b
        mx, my = (ax + bx) / 2, (ay + by) / 2
        f = max(self.frac, 1e-4)
        ax, ay, bx, by = mx + (ax - mx) * f, my + (ay - my) * f, mx + (bx - mx) * f, my + (by - my) * f
        # 窓の外に出る所は切る (縦か横の線だけ)
        L, T, R, B = self.view.win
        ax, bx = max(min(ax, bx), L), min(max(ax, bx), R)
        ay, by = max(min(ay, by), T), min(max(ay, by), B)
        if not hasattr(self, "_op"):
            self._op = self.get_stroke_opacity()
        if ax > bx + 1e-6 or ay > by + 1e-6:
            self.set_stroke(opacity=0)
            ax, ay, bx, by = L, T, L + 1e-3, T
        else:
            self.set_stroke(opacity=self._op)
        p, q = self.view.to_point(ax, ay), self.view.to_point(bx, by)
        if np.allclose(p, q):
            q = q + RIGHT * 1e-4
        self.put_start_and_end_on(p, q)
        return self


class PRect(Rectangle):
    """写真の画素の範囲 (x, y, w, h) を囲む四角。窓が動いてもついてくる"""

    def __init__(self, view, x, y, w, h, **style):
        super().__init__(width=1, height=1, **style)
        self.view, self.r = view, (x, y, w, h)
        self.sync()
        self.add_updater(lambda m: m.sync())

    def sync(self):
        x, y, w, h = self.r
        a, b = self.view.to_point(x, y), self.view.to_point(x + w, y + h)
        self.stretch_to_fit_width(max(b[0] - a[0], 1e-3))
        self.stretch_to_fit_height(max(a[1] - b[1], 1e-3))
        self.move_to((a + b) / 2)
        return self


class Grow(Animation):
    """PLine を真ん中から伸ばす (rev=True で縮めて消す)"""

    def __init__(self, line, rev=False, **kw):
        kw.setdefault("rate_func", smooth)
        super().__init__(line, **kw)
        self.rev = rev

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        self.mobject.frac = 1 - a if self.rev else a
        self.mobject.sync()


def cross_lines(view, x, y, s, W, H, color, width=4):
    """(x, y) からの s×s を 4 つに割る十字の 2 本 (写真の外にはみ出す所は切る)。写真の外なら None"""
    h = s / 2
    out = []
    if x + h < W:   # 縦の線
        out.append(PLine(view, (x + h, y), (x + h, min(y + s, H)), frac=0, stroke_color=color, stroke_width=width))
    if y + h < H:   # 横の線
        out.append(PLine(view, (x, y + h), (min(x + s, W), y + h), frac=0, stroke_color=color, stroke_width=width))
    return out


LW = {64: 4, 32: 3.5, 16: 3, 8: 2.5, 4: 1.6}   # 線の太さ (割ったあとの大きさごと)


def grid64_lines(view, W, H, n=64, color="#eef0f4", frac=1.0):
    """64×64 の格子の線 (写真の中だけ)"""
    out = []
    for x in range(n, W, n):
        out.append(PLine(view, (x, 0), (x, H), frac=frac, stroke_color=color, stroke_width=LW[64]))
    for y in range(n, H, n):
        out.append(PLine(view, (0, y), (W, y), frac=frac, stroke_color=color, stroke_width=LW[64]))
    return out


def partition_lines(view, splits, cus, W, H, colors, frac=1.0):
    """割れ方の線すべて {大きさ: [PLine]} (64 は格子、32〜8 は「割る」の十字、4 は 8×8 を 4×4 で予想する十字)。
    S03 の最後の画面・S04 の最初の画面はこれと 64 の格子"""
    levels = {64: grid64_lines(view, W, H, frac=frac), 32: [], 16: [], 8: [], 4: []}
    for s in splits:
        if s["split"]:
            k = s["size"] // 2
            levels[k] += cross_lines(view, s["x"], s["y"], s["size"], W, H, colors[k], LW[k])
    for c in cus:
        if c["nxn"]:
            levels[4] += cross_lines(view, c["x"], c["y"], 8, W, H, colors[4], LW[4])
    for k, ls in levels.items():
        for ln in ls:
            ln.frac = frac
            ln.sync()
    return levels


class TrackFade(Animation):
    """PRect・PLine を、窓についていかせたまま薄れさせる・現す (a0 → a1。1 が元の濃さ)。
    FadeIn/FadeOut/Create は、そのあいだ図形の updater を止めるので、写真が寄る・引く動きと重ねると図形だけ置いていかれる"""

    def __init__(self, m, a0, a1, **kw):
        kw.setdefault("rate_func", smooth)
        super().__init__(m, **kw)
        self.a0, self.a1 = a0, a1
        self.s0 = getattr(m, "_op", None) or m.get_stroke_opacity() or 1.0
        self.f0 = m.get_fill_opacity()
        m._fill0 = getattr(m, "_fill0", self.f0)

    def interpolate_mobject(self, alpha):
        a = self.a0 + (self.a1 - self.a0) * self.rate_func(alpha)
        m = self.mobject
        m.sync()
        if isinstance(m, PLine):
            m._op = self.s0 * a
            m.sync()
        else:
            m.set_stroke(opacity=self.s0 * a)
            m.set_fill(opacity=m._fill0 * a)
