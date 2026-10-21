import struct
import sys
import zlib
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import distance_map, file_bytes, fmt, pixels, size, vp8l_info  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403
from zunda.scene import checker_composite  # noqa: E402

W_, H_ = 541, 797
ILL_C, ILL_H = (960, 495), 800          # イラストを 1 枚で大きく
ILL_L, ILL_LH = (705, 485), 770         # 左に寄せる (右に図を置くとき)
ILL_R, ILL_RH = (1220, 485), 760        # PNG と並べるときの右
ILL_P = (700, 485)
CACHE_C, CACHE_H = (705, 465), 740      # 最近の色の表のときの絵 (下に注記)
STAT_C, STAT_H = (960, 240), 400        # 点の数のときの絵 (上の帯)                      # その左 (PNG)
RX0, RX1 = 1010, 1470                   # 右の図の左右の端
DARKC = "#232833"
# 予想のしかた 14 通りの色。PNG 編のフィルタの色に合わせる (左 = Sub の青、上 = Up の黄、平均 = 紫、Select = Paeth の珊瑚)
MODE_COL = ["#4a5160", BLUE, YELLOW, "#e8964a", "#5cc48c", "#8f7be8", "#c39cf2", PURPLE, "#d7a9ea",
            "#7a6ad0", "#b6a3ff", CORAL, CYAN, "#3aa0b0"]
PNG_COL = {0: "#8a919e", 1: BLUE, 2: YELLOW, 3: PURPLE, 4: CORAL}     # PNG 編 vlib/style.py と同じ
PNG_NAME = {0: "None", 1: "Sub", 2: "Up", 3: "Average", 4: "Paeth"}
TYPE_COL = {"copy": CYAN, "cache": PURPLE, "lit": INK}
C1, C2 = CYAN, BLUE                      # 距離の番号 1 (上)・2 (左)


def rgb01(h):
    c = color_to_rgb(h)
    return np.array(c, np.float32) * 255


def hexrgb(r, g, b):
    return rgb_to_color([r / 255, g / 255, b / 255])


class Illust(ImageMobject):
    """イラスト (透明は市松模様)。lit で暗く沈め、layers [(色の配列, 濃さ)] を重ねる"""

    def __init__(self, rgba, center, h, **kw):
        self.rgba = rgba
        self.base = checker_composite(rgba, 14).astype(np.float32)
        self.lit = np.ones(rgba.shape[:2], np.float32)
        self.layers = []
        self.disp_h = h
        super().__init__(self._render(), **kw)
        self.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
        self.height = u(h)
        self.move_to(px(*center))
        self.check_ignore = True

    def _render(self):
        out = self.base * self.lit[..., None]
        for col, m in self.layers:
            out = out * (1 - m[..., None]) + col * m[..., None]
        rgb = np.clip(out, 0, 255).astype(np.uint8)
        th = int(round(self.disp_h))
        if th < H_:          # 小さく映すときは、先に LANCZOS で縮める (ドットのまま縮めると線がギザギザ)
            rgb = np.asarray(Image.fromarray(rgb).resize((max(1, round(W_ * th / H_)), th), Image.LANCZOS))
        return np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])

    def refresh(self):
        op = self.pixel_array[0, 0, 3] / 255
        self.disp_h = self.height / u(1)
        self.pixel_array = self._render()
        self.pixel_array[:, :, 3] = round(255 * op)
        self.orig_alpha_pixel_array = np.full(self.pixel_array.shape[:2], 255, np.uint8)
        return self

    def to_point(self, x, y):
        left, top = self.get_left()[0], self.get_top()[1]
        return np.array([left + x * self.width / W_, top - y * self.height / H_, 0])


class Fn(Animation):
    """fn(t) で状態を変える (画像の描き直し・位置)"""

    def __init__(self, mob, fn, **kw):
        super().__init__(mob, **kw)
        self.fn = fn

    def interpolate_mobject(self, alpha):
        self.fn(self.rate_func(alpha))


def move(ill, center, h, **kw):
    c0, h0 = ill.get_center().copy(), ill.height
    c1, h1 = px(*center), u(h)

    def fn(t):
        ill.height = h0 + (h1 - h0) * t
        ill.move_to(c0 + (c1 - c0) * t)
        ill.refresh()
    kw.setdefault("rate_func", smooth)
    return Fn(ill, fn, **kw)


def png_filters():
    """zunda.png の各行のフィルタの種類 (IDAT を展開して、各行の先頭の 1 バイト)"""
    b = file_bytes("zunda.png")
    i, idat, ihdr = 8, b"", None
    while i < len(b):
        n, = struct.unpack(">I", b[i:i + 4])
        t, d = b[i + 4:i + 8], b[i + 8:i + 8 + n]
        if t == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", d)
        elif t == b"IDAT":
            idat += d
        i += 12 + n
    assert ihdr == (W_, H_, 8, 6, 0, 0, 0)            # 8 ビットの RGBA、インターレースなし
    raw = zlib.decompress(idat)
    st = 1 + W_ * 4
    assert len(raw) == st * H_
    return [raw[r * st] for r in range(H_)]


def heading(n, name):
    c = Circle(radius=u(21), stroke_width=0, fill_color=YELLOW, fill_opacity=1)
    num = jp(str(n), 26, BG).move_to(c)
    t = jp(name, 34, INK).next_to(c, RIGHT, buff=u(14))
    g = VGroup(c, num, t)
    g.move_to(px(60, 70), aligned_edge=LEFT)
    return g


def reheading(head, n, name):
    new = heading(n, name)
    head[1].text, head[2].text = new[1].text, new[2].text      # 検査用の文字も更新
    return Transform(head, new)


class S08(PScene):
    def construct(self):
        # ================= データ =================
        P = pixels("zunda.png")
        assert P.shape == (H_, W_, 4)
        L = vp8l_info("zunda_lossless")
        assert (L["width"], L["height"]) == (W_, H_)
        n_png, n_webp = size("zunda.png"), size("zunda_lossless")
        assert (n_png, n_webp) == (162613, 113786)
        assert round(1 - n_webp / n_png, 1) == 0.3                       # 「3割くらい小さかった」
        # 変換：緑を引く → 予想 (16×16) → 色の相関
        trs = L["transforms"]
        assert [t["type"] for t in trs] == [2, 0, 1]
        pred = trs[1]
        assert pred["bits"] == 4
        bw, bh = -(-W_ // 16), -(-H_ // 16)
        modes = np.array([(d >> 8) & 15 for d in pred["data"]], np.int32).reshape(bh, bw)
        assert modes.max() <= 13 and len(MODE_COL) == 14                  # 14 通り
        pf = png_filters()
        assert set(pf) <= set(range(5))                                   # PNG は 5 通り
        # 透明でない点は、自前の復号と Pillow が一致
        RGBA = L["rgba"]
        assert (RGBA[..., 3] == P[..., 3]).all() and (RGBA[P[..., 3] > 0] == P[P[..., 3] > 0]).all()

        # 緑を引く：明るい点と暗い点 (イラストの中で一番多い白と線の色)
        Pi = P.astype(np.int32)
        opaque = Pi[..., 3] == 255
        cnt = Counter(map(tuple, Pi[opaque][:, :3]))

        def pick(cond, near):
            col = max((c for c in cnt if cond(c)), key=lambda c: cnt[c])
            m = opaque & (Pi[..., 0] == col[0]) & (Pi[..., 1] == col[1]) & (Pi[..., 2] == col[2])
            ys, xs = np.nonzero(m)
            k = int(np.argmin((ys - near[1]) ** 2 + (xs - near[0]) ** 2))
            return (int(xs[k]), int(ys[k])), tuple(int(v) for v in col)
        small = lambda c, d: abs(c[0] - c[1]) <= d and abs(c[2] - c[1]) <= d   # noqa: E731
        (bx_, by_), bright = pick(lambda c: min(c) >= 200 and small(c, 10), (260, 330))
        (dx_, dy_), dark = pick(lambda c: max(c) <= 90 and c[1] >= 40 and small(c, 25), (165, 470))
        assert bright == (247, 242, 236) and dark == (75, 54, 56), (bright, dark)

        # コピー
        dm = distance_map()
        assert dm[0] == (0, 1) and dm[1] == (1, 0)                       # 1 番 = すぐ上、2 番 = すぐ左
        toks = L["tokens"]
        copies = [t for t in toks if t[0] == "copy"]
        ccount = Counter(t[4] for t in copies)
        assert len(copies) == 4353 and set(ccount) == {1, 2}
        assert (ccount[1], ccount[2]) == (2777, 1576)
        npx = Counter()
        for t in toks:
            npx[t[0]] += t[2]
        assert (npx["copy"], npx["cache"], npx["lit"]) == (367400, 29365, 34412)
        N = sum(npx.values())
        assert N == 431177 == W_ * H_
        assert round(npx["copy"], -4) == 370000 and round(npx["cache"], -3) == 29000 \
            and round(npx["lit"], -3) == 34000                              # 37万・2万9千・3万4千
        assert 541 * 4 == 2164
        # 例のコピー：1 番 (すぐ上) で写す所のうち、まわりの 15×7 が不透明で、縦の境目 (線と服) がはっきりした所
        def edge_score(t):
            y, x = divmod(t[1], W_)
            if not (4 <= y < H_ - 3 and 7 <= x < W_ - 7 and t[2] >= 3):
                return -1e9
            c = Pi[y - 4:y + 3, x - 7:x + 8]
            if not (c[..., 3] == 255).all() or not (Pi[y, x:x + t[2]] == Pi[y - 1, x:x + t[2]]).all():
                return -1e9
            c = c[..., :3].astype(float)
            return c.mean(0).std(0).sum() - 3 * c.std(0).mean()
        ex = max((t for t in copies if t[4] == 1), key=edge_score)
        assert divmod(ex[1], W_) == (343, 223) and ex[2] == 43
        assert ex[5] == W_ and ex[6] == (0, 1)
        cy, cx = divmod(ex[1], W_)
        # 写すのは書く差 (変換したあとの値) だが、この例は色も上の行と同じ
        assert (Pi[cy, cx:cx + ex[2]] == Pi[cy - 1, cx:cx + ex[2]]).all()
        # 最近の色の表：中に入るのは、書く差 (緑を引いて、予想して、色の相関をとったあとの値)
        cache_n = 1 << L["cache_bits"]
        assert cache_n == 1024
        res = np.array(L["residual"], np.uint64)
        slot = (((np.uint64(0x1E35A7BD) * res) & np.uint64(0xFFFFFFFF)) >> np.uint64(32 - L["cache_bits"]))
        slot = slot.astype(np.int64)
        keys = slot * N + np.arange(N)
        skeys = np.sort(keys)

        def cache_at(k):
            """先頭から k 点を読んだあとの表：各マスの、最後に入った点の位置 (なければ −1)"""
            q = np.searchsorted(skeys, np.arange(cache_n) * N + k) - 1
            ok = (q >= 0) & (skeys[np.clip(q, 0, None)] // N == np.arange(cache_n))
            return np.where(ok, skeys[np.clip(q, 0, None)] % N, -1)
        flat = res.astype(np.int64)
        for t in [t for t in toks if t[0] == "cache"][::997]:
            assert slot[t[1]] == t[4] and flat[cache_at(t[1])[t[4]]] == flat[t[1]]   # 表のそのマスの値 = その点の差
        sg = lambda v: np.where(v >= 128, v - 256, v)                    # noqa: E731
        dARGB = np.stack([sg((flat >> s_) & 255) for s_ in (16, 8, 0, 24)], -1)   # R G B A の差 (符号つき)
        KD = 12                                                          # 差を見せる強調 (絵と表で同じ)
        dshow = np.clip(128 + dARGB[:, :3] * KD, 0, 255).astype(np.float32)
        # 表の番号の例：ズボンの中。最後の表にもその値が残っている所、R・G・B の差が 0 でない
        final = cache_at(N)
        cex = None
        for t in toks:
            if t[0] != "cache":
                continue
            p_ = t[1]
            y_, x_ = divmod(p_, W_)
            d_ = dARGB[p_]
            if 380 <= y_ <= 520 and Pi[y_, x_, 3] == 255 and flat[final[t[4]]] == flat[p_] \
                    and (d_[:3] != 0).sum() >= 2 and np.abs(d_).max() <= 3:
                cex = t
                break
        assert cex is not None and flat[cache_at(cex[1])[cex[4]]] == flat[cex[1]]
        ey, exx = divmod(cex[1], W_)
        edif = [int(v) for v in dARGB[cex[1]]]
        # 点ごとの書き方
        kind = np.zeros(N, np.int8)
        for t in toks:
            kind[t[1]:t[1] + t[2]] = {"copy": 0, "cache": 1, "lit": 2}[t[0]]
        kind = kind.reshape(H_, W_)

        # ================= S08_01：可逆の WebP =================
        title = jp("可逆のWebP", 48, INK).move_to(px(960, 60))
        self.at("lossless", -0.1)
        self.play(FadeIn(title, shift=DOWN * u(8)), run_time=0.7)
        ill = Illust(P, ILL_C, ILL_H)
        ill.set_opacity(0)
        self.add(ill)
        self.at("illust", -0.1)
        self.play(ill.animate.set_opacity(1), run_time=0.9)

        # ================= S08_02：大きさ =================
        self.at("sizes", -0.1)

        def bar_row(name, n, y, col):
            lab = jp(name, 34, col).move_to(px(RX0, y), aligned_edge=LEFT)
            num = mix(f"{fmt(n)}バイト", 38, INK).move_to(px(RX1, y), aligned_edge=RIGHT)
            w = (RX1 - RX0) * n / n_png
            bar = Rectangle(width=u(w), height=u(48), stroke_width=0, fill_color=col, fill_opacity=0.9)
            bar.move_to(px(RX0 + w / 2, y + 62))
            return VGroup(lab, num, bar)
        r_png = bar_row("PNG", n_png, 330, PNG_COL[0])
        r_wp = bar_row("WebP", n_webp, 500, CYAN)
        wgap = (RX1 - RX0) * (1 - n_webp / n_png)
        gap = DashedVMobject(Rectangle(width=u(wgap), height=u(48), stroke_color=DIM, stroke_width=3),
                             num_dashes=24).move_to(px(RX1 - wgap / 2, 562))
        self.play(FadeOut(title), move(ill, ILL_L, ILL_LH), run_time=0.9)
        self.play(FadeIn(r_png[:2]), GrowFromEdge(r_png[2], LEFT), run_time=0.7)
        self.play(FadeIn(r_wp[:2]), GrowFromEdge(r_wp[2], LEFT), run_time=0.7)
        self.play(Create(gap), run_time=0.6)

        self.at("inside", -0.1)
        self.play(FadeOut(VGroup(r_png, r_wp, gap)), run_time=0.6)
        self.play(move(ill, ILL_C, ILL_H), run_time=0.9)

        # ================= S08_03 =================
        self.at("s08_04", -0.1)
        self.play(move(ill, ILL_L, ILL_LH), run_time=1.0)

        # ================= S08_04：緑を引く =================
        self.at("green", -0.1)
        head = heading(1, "緑を引く")
        self.play(FadeIn(head, shift=RIGHT * u(10)), run_time=0.6)

        BAR_X = [1190, 1300, 1410]
        BMAX = 270

        def panel(col, at_px, base_y):
            """1 つの点：色のマス、R・G・B の棒と値、点の印"""
            sw = Square(u(96), stroke_color=YELLOW, stroke_width=4, fill_color=hexrgb(*col), fill_opacity=1)
            sw.move_to(px(1060, base_y - BMAX / 2))
            ring = Circle(radius=u(16), stroke_color=YELLOW, stroke_width=5).move_to(ill.to_point(*at_px))
            link = Line(ring.get_right(), sw.get_left(), stroke_color=YELLOW, stroke_width=2, stroke_opacity=0.7)
            bars, vals, labs = [], [], []
            for k, (v, nm, cc) in enumerate(zip(col, "RGB", ("#ef6f6f", "#6fd08a", "#6fa0ef"))):
                h = BMAX * v / 255
                b = Rectangle(width=u(70), height=u(max(h, 1)), stroke_width=0, fill_color=cc, fill_opacity=0.95)
                b.move_to(px(BAR_X[k], base_y - h / 2))
                t = mono(str(v), 30, INK).move_to(px(BAR_X[k], base_y - h - 24))
                lb = jp(nm, 28, cc).move_to(px(BAR_X[k], base_y + 28))
                bars.append(b)
                vals.append(t)
                labs.append(lb)
            base = Line(px(BAR_X[0] - 50, base_y), px(BAR_X[2] + 50, base_y), stroke_color=DIM, stroke_width=2)
            return dict(sw=sw, ring=ring, link=link, bars=bars, vals=vals, labs=labs, base=base, y=base_y)
        pa = panel(bright, (bx_ + 0.5, by_ + 0.5), 410)
        pb = panel(dark, (dx_ + 0.5, dy_ + 0.5), 840)

        def show(p):
            return [Create(p["ring"]), Create(p["link"]), FadeIn(p["sw"]), Create(p["base"]),
                    *[GrowFromEdge(b, DOWN) for b in p["bars"]], *[FadeIn(t) for t in p["vals"] + p["labs"]]]
        self.at("rgb", -0.1)
        self.play(*show(pa), run_time=1.0)
        self.at("together", -0.1)
        self.play(*show(pb), run_time=1.0)
        self.play(pop(VGroup(*pa["bars"]), 1.06, 0.6), pop(VGroup(*pb["bars"]), 1.06, 0.6), run_time=0.6)

        # R と B から G を引く：G の棒の写しが R・B の棒に重なって、その長さだけ縮む
        self.at("minus", -0.1)
        ghosts, anims1, anims2 = [], [], []
        for p, col in ((pa, bright), (pb, dark)):
            g = p["bars"][1]
            for k in (0, 2):
                gh = g.copy().set_fill(opacity=0.45).set_stroke(INK, 2, 0.8)
                ghosts.append(gh)
                self.add(gh)
                tgt = gh.copy().move_to(px(BAR_X[k], p["y"]), aligned_edge=DOWN)
                tgt.align_to(p["bars"][k], UP)
                anims1.append(gh.animate(path_arc=-PI / 4 if k == 0 else PI / 4).become(tgt))
                d = col[k] - col[1]
                h = BMAX * abs(d) / 255
                nb = p["bars"][k].copy().stretch_to_fit_height(u(max(h, 2)))
                if d >= 0:
                    nb.move_to(px(BAR_X[k], p["y"] - h / 2))
                else:
                    nb.move_to(px(BAR_X[k], p["y"] + h / 2))
                nt = mono(str(d).replace("-", "−"), 30, YELLOW).move_to(px(BAR_X[k], p["y"] - max(h, 0) * (d > 0) - 24))
                nl = jp(("R", "", "B")[k] + "−G", 28, p["labs"][k].get_color()).move_to(p["labs"][k])
                if d < 0:
                    nl.shift(DOWN * u(h))
                anims2 += [Transform(p["bars"][k], nb), retext(p["vals"][k], nt), retext(p["labs"][k], nl)]
                for gq in [gh]:
                    anims2.append(FadeOut(gq))
        self.play(*anims1, run_time=1.0)
        self.play(*anims2, run_time=0.9)
        self.remove(*ghosts)

        self.at("smallv", -0.1)
        self.play(*[pop(p["vals"][k], 1.4, 0.7) for p in (pa, pb) for k in (0, 2)], run_time=0.7)

        # ================= S08_05：予想 =================
        self.at("s08_06", -0.1)
        pan = VGroup(*[VGroup(p["sw"], p["ring"], p["link"], p["base"], *p["bars"], *p["vals"], *p["labs"])
                       for p in (pa, pb)])
        self.play(FadeOut(pan), move(ill, ILL_C, ILL_H), run_time=0.55)
        self.at("pred", -0.1)
        self.play(reheading(head, 2, "予想"), run_time=0.6)

        # PNG と同じ：左や上
        self.at("png", -0.1)
        CELLN = 70
        nb_pos = {"TL": (-1, -1), "T": (0, -1), "TR": (1, -1), "L": (-1, 0), "X": (0, 0)}
        nb_col = {"TL": DARKC, "T": YELLOW, "TR": DARKC, "L": BLUE, "X": "#4a5160"}
        nbs = {}
        for k_, (ddx, ddy) in nb_pos.items():
            sq = Square(u(CELLN), stroke_width=2, stroke_color="#3a3f4c", fill_color=DARKC, fill_opacity=1)
            sq.move_to(px(1690 + ddx * (CELLN + 4), 200 + (ddy + 0.5) * (CELLN + 4)))
            nbs[k_] = sq
        qm = jp("？", 40, INK).move_to(nbs["X"])
        nbg = VGroup(*nbs.values())
        self.play(FadeIn(nbg), FadeIn(qm), run_time=0.6)
        self.play(nbs["L"].animate.set_fill(nb_col["L"]), nbs["T"].animate.set_fill(nb_col["T"]), run_time=0.6)

        # 14 通り：左・上・右上・左上のマスが、そのまま 1〜4 番の札になる
        self.at("kinds", -0.1)
        TILE = 55

        def tile_pos(m):
            return px(1688 + (m % 7 - 3) * (TILE + 3), 175 + (m // 7) * (TILE + 8))
        tiles = []
        for m in range(14):
            sq = Square(u(TILE), stroke_width=0, fill_color=MODE_COL[m], fill_opacity=1).move_to(tile_pos(m))
            t = mono(str(m), 28, BG).move_to(sq)
            tiles.append(VGroup(sq, t))
        src = {1: "L", 2: "T", 3: "TR", 4: "TL"}
        for m, k_ in src.items():
            nbs[k_].generate_target()
        self.play(*[ReplacementTransform(nbs[k_], tiles[m]) for m, k_ in src.items()],
                  FadeOut(nbs["X"]), FadeOut(qm), run_time=0.8)
        rest = [m for m in range(14) if m not in src]
        self.play(LaggedStart(*[FadeIn(tiles[m], scale=0.7) for m in rest], lag_ratio=0.1), run_time=1.2)
        tileg = VGroup(*tiles)

        # 16×16 ごとの予想の番号 (実際の値)
        self.at("area", -0.1)
        col_blk = np.array([rgb01(MODE_COL[m]) for m in range(14)], np.float32)[modes]
        mcol = np.kron(col_blk, np.ones((16, 16, 1), np.float32))[:H_, :W_].copy()
        yy, xx = np.mgrid[0:H_, 0:W_]
        edge = (yy % 16 == 0) | (xx % 16 == 0)
        mcol[edge] *= 0.55
        mmask = np.zeros((H_, W_), np.float32)
        ill.layers = [(mcol, mmask)]
        border = np.where(edge, 0.85, 0.62).astype(np.float32)
        blk_order = (yy // 16) * bw + (xx // 16)

        def sweep(t):
            k = t * (bw * bh + 30)
            mmask[:] = np.clip((k - blk_order) / 30, 0, 1) * border
            ill.refresh()
        self.play(Fn(ill, sweep, rate_func=linear), run_time=2.2)

        # ずんだもん：PNG は 1 行ずつ 5 通り (zunda.png の実際のフィルタ)
        self.at("png2", -0.1)
        pill = Illust(P, ILL_P, ILL_RH)
        prow = np.array([rgb01(PNG_COL[f]) for f in pf], np.float32)
        pcol = np.repeat(prow[:, None, :], W_, 1)
        pmask = np.zeros((H_, W_), np.float32)
        pill.layers = [(pcol, pmask)]
        pill.refresh()
        pill.set_opacity(0)
        self.add(pill)
        lab_p = jp("PNG", 34, INK).move_to(px(ILL_P[0], 75))
        lab_w = jp("WebP", 34, INK).move_to(px(ILL_R[0], 75))
        pleg = VGroup()
        for f in range(5):
            sq = Square(u(40), stroke_width=0, fill_color=PNG_COL[f], fill_opacity=1).move_to(px(84, 160 + f * 58))
            nm = jp(PNG_NAME[f], 28, PNG_COL[f]).next_to(sq, RIGHT, buff=u(14))
            pleg.add(VGroup(sq, nm))
        self.play(move(ill, ILL_R, ILL_RH), run_time=0.7)
        self.play(pill.animate.set_opacity(1), FadeIn(lab_p), FadeIn(lab_w), FadeIn(pleg, shift=RIGHT * u(10)),
                  run_time=0.5)

        def rows(t):
            k = t * (H_ + 40)
            pmask[:] = (np.clip((k - np.arange(H_)) / 40, 0, 1) * 0.62)[:, None]
            pill.refresh()
        self.play(Fn(pill, rows, rate_func=linear), run_time=1.4)

        # ================= S08_07：コピー =================
        self.at("s08_09", -0.1)
        def unmap(t):
            mmask[:] = border * (1 - t)
            ill.refresh()
        self.play(pill.animate.set_opacity(0), FadeOut(VGroup(lab_p, lab_w, pleg, tileg)),
                  reheading(head, 3, "コピー"), move(ill, ILL_C, ILL_H), Fn(Mobject(), unmap), run_time=0.55)
        self.remove(pill)
        ill.layers = []
        ill.refresh()

        # いまの点のまわりを拡大した格子
        GC, GCOLS, GROWS = 64, 15, 7
        X0c, Y0r = cx - 7, cy - 4                       # 格子の左上の点
        gx = lambda c: 960 + (c - 7) * GC               # noqa: E731
        gy = lambda r: 330 + (r - 3) * GC               # noqa: E731
        cells = {}
        for r in range(GROWS):
            for c in range(GCOLS):
                x, y = X0c + c, Y0r + r
                rgb = Pi[y, x, :3]
                made = (y < cy) or (y == cy and x < cx)
                f = 1.0 if made else 0.22
                sq = Square(u(GC), stroke_width=1.5, stroke_color="#14161c",
                            fill_color=hexrgb(*(rgb * f)), fill_opacity=1).move_to(px(gx(c), gy(r)))
                cells[(c, r)] = sq
        grid = VGroup(*cells.values())
        assert (Pi[Y0r:Y0r + GROWS, X0c:X0c + GCOLS, 3] == 255).all()
        self.at("copy", -0.1)
        zr = Rectangle(width=ill.width * GCOLS / W_, height=ill.height * GROWS / H_, stroke_color=YELLOW,
                       stroke_width=4).move_to(ill.to_point(X0c + GCOLS / 2, Y0r + GROWS / 2))
        self.play(Create(zr), run_time=0.3)
        gsmall = grid.copy().replace(zr, stretch=True)
        self.play(ill.animate.set_opacity(0.0), ReplacementTransform(gsmall, grid), FadeOut(zr), run_time=0.7)

        # PNG の LZ77 の札
        self.at("lz", -0.1)
        CW, CHh = 380, 78
        cardr = RoundedRectangle(corner_radius=u(14), width=u(CW), height=u(CHh), stroke_width=0, fill_color=CYAN,
                                 fill_opacity=1).move_to(px(1690, 150))
        dval = mix("距離？", 30, BG).move_to(cardr.get_center() + LEFT * u(CW / 4))
        lval = mix("長さ？", 30, BG).move_to(cardr.get_center() + RIGHT * u(CW / 4))
        dv = Line(cardr.get_top() + DOWN * u(14), cardr.get_bottom() + UP * u(14), stroke_width=2, color=BG,
                  stroke_opacity=0.5)
        capL = jp("何バイト前から", 26, DIM).move_to(px(1690 - 95, 212))
        capR = jp("何バイトコピー", 26, DIM).move_to(px(1690 + 95, 212))
        lzlab = jp("PNGのLZ77", 30, DIM).move_to(px(1690, 88))
        card = VGroup(cardr, dval, lval, dv, capL, capR, lzlab)
        self.play(FadeIn(card, shift=DOWN * u(8)), run_time=0.6)

        # すぐ上の点
        self.at("up", -0.1)
        cur = Square(u(GC), stroke_color=YELLOW, stroke_width=6).move_to(cells[(7, 4)])
        upm = Square(u(GC), stroke_color=C1, stroke_width=6).move_to(cells[(7, 3)])
        self.play(Create(cur), run_time=0.5)
        self.play(Create(upm), run_time=0.5)

        # 一列に並べ直すと、541 画素前
        self.at("far", -0.1)
        SC, SY = 40, 740
        sx0 = 960 - (15 * SC + 60 + 8 * SC) / 2 + SC / 2
        sA = [sx0 + i * SC for i in range(15)]
        sB = [sx0 + 15 * SC + 60 + j * SC for j in range(8)]
        flyA = [cells[(c, 3)].copy() for c in range(15)]
        flyB = [cells[(c, 4)].copy() for c in range(8)]
        anims = []
        for i, m in enumerate(flyA):
            anims.append(m.animate(path_arc=-PI / 6).set(width=u(SC)).move_to(px(sA[i], SY)))
        for j, m in enumerate(flyB):
            anims.append(m.animate(path_arc=-PI / 6).set(width=u(SC)).move_to(px(sB[j], SY)))
        dots = VGroup(*[Dot(radius=u(4), color=DIM) for _ in range(3)]).arrange(RIGHT, buff=u(8))
        dots.move_to(px(sx0 + 15 * SC + 30 - SC / 2, SY))
        self.add(*flyA, *flyB)
        self.play(LaggedStart(*anims, lag_ratio=0.02), FadeIn(dots), run_time=1.0)
        scur = Square(u(SC), stroke_color=YELLOW, stroke_width=5).move_to(px(sB[7], SY))
        sup = Square(u(SC), stroke_color=C1, stroke_width=5).move_to(px(sA[7], SY))
        arc = CurvedArrow(px(sB[7], SY - 26), px(sA[7], SY - 26), angle=PI / 3.2, color=C1, stroke_width=4,
                          tip_length=u(16))
        alab = mix(f"{W_}画素前 = {fmt(W_ * 4)}バイト前", 36, C1).move_to(px((sA[7] + sB[7]) / 2, SY - 125))
        self.play(Create(scur), Create(sup), Create(arc), FadeIn(alab, shift=UP * u(6)),
                  retext(dval, mix(f"距離{fmt(W_ * 4)}", 30, BG)), run_time=0.6)
        # いまの点に、すぐ上の色が入る
        cfill = cells[(7, 3)].get_fill_color()
        self.play(cells[(7, 4)].animate.set_fill(cfill), flyB[7].animate.set_fill(cfill), run_time=0.5)

        # WebP：近くの場所に短い番号
        self.at("code", -0.1)
        strip = VGroup(*flyA, *flyB, dots, scur, sup, arc, alab)
        self.at("near", -0.1)
        nums = {}
        for k in range(1, 25):
            xi, yi = dm[k - 1]
            c, r = 7 - xi, 4 - yi
            bk = RoundedRectangle(corner_radius=u(6), width=u(46), height=u(38), stroke_width=0, fill_color=BG,
                                  fill_opacity=0.7).move_to(cells[(c, r)])
            t = mono(str(k), 30, INK).move_to(bk)
            nums[k] = VGroup(bk, t)
        self.play(LaggedStart(*[FadeIn(nums[k], scale=0.6) for k in range(1, 25)], lag_ratio=0.12), run_time=2.6)
        self.at("c1", -0.1)
        self.play(nums[1][0].animate.set_fill(C1, 1), nums[1][1].animate.set_color(BG), run_time=0.4)
        self.play(pop(nums[1], 1.35, 0.6), run_time=0.6)
        self.at("c2", -0.1)
        self.play(nums[2][0].animate.set_fill(C2, 1), nums[2][1].animate.set_color(BG), run_time=0.4)
        self.play(pop(nums[2], 1.35, 0.6), run_time=0.6)

        # コピー 6,130 回 → 1 番と 2 番
        self.at("result", -0.1)
        BX0, BX1, BY = 510, 1410, 720
        bw_ = BX1 - BX0
        cbar = Rectangle(width=u(bw_), height=u(60), stroke_width=0, fill_color=C1, fill_opacity=0.9)
        cbar.move_to(px(960, BY))
        clab = mix(f"コピー {fmt(len(copies))}回", 36, INK).move_to(px(960, BY - 70))
        self.play(FadeOut(strip), FadeOut(card), FadeOut(upm), run_time=0.5)
        self.remove(*flyA, *flyB)
        self.play(GrowFromEdge(cbar, LEFT), FadeIn(clab), run_time=0.8)
        self.at("all12", -0.1)
        w1 = bw_ * ccount[1] / len(copies)
        b1 = Rectangle(width=u(w1 - 4), height=u(60), stroke_width=0, fill_color=C1, fill_opacity=0.9)
        b1.move_to(px(BX0 + w1 / 2 - 2, BY))
        b2 = Rectangle(width=u(bw_ - w1 - 4), height=u(60), stroke_width=0, fill_color=C2, fill_opacity=0.9)
        b2.move_to(px(BX0 + w1 + (bw_ - w1) / 2 + 2, BY))
        cbar2 = VGroup(b1, b2)
        l1 = mix(f"1番 {fmt(ccount[1])}回", 32, C1).move_to(px(BX0 + w1 / 2, BY + 66))
        l2 = mix(f"2番 {fmt(ccount[2])}回", 32, C2).move_to(px(BX0 + w1 + (bw_ - w1) / 2, BY + 66))
        self.play(ReplacementTransform(cbar, cbar2), run_time=0.7)
        self.play(FadeIn(l1, shift=DOWN * u(6)), FadeIn(l2, shift=DOWN * u(6)), run_time=0.5)

        self.at("simple", -0.1)
        self.play(pop(VGroup(nums[1], cells[(7, 3)]), 1.15, 0.7), pop(VGroup(nums[2], cells[(6, 4)]), 1.15, 0.7),
                  run_time=0.7)

        # ================= S08_11：最近の色の表 =================
        self.at("s08_14", -0.1)
        gridall = VGroup(grid, cur, *nums.values())
        ill.lit[:] = 1.0
        ill.height = u(CACHE_H)
        ill.move_to(px(*CACHE_C))
        ill.refresh()
        self.play(FadeOut(gridall), FadeOut(VGroup(cbar2, clab, l1, l2)), reheading(head, 4, "最近の色の表"),
                  ill.animate.set_opacity(1), run_time=0.5)
        self.remove(*cells.values())

        # 書く差の絵 (緑を引いて、予想したあと)。表に入るのはこの値
        drgba = np.dstack([dshow.reshape(H_, W_, 3).astype(np.uint8), np.full((H_, W_), 255, np.uint8)])
        rill = Illust(drgba, CACHE_C, CACHE_H)
        rill.set_opacity(0)
        self.add(rill)
        rlab = jp("書く差", 32, PURPLE).move_to(px(CACHE_C[0], 72))
        rnote = jp("差は見やすく強めて表示", 26, DIM).move_to(px(CACHE_C[0], CACHE_C[1] + CACHE_H / 2 + 24))

        self.at("cache", -0.1)
        TC, TG = 13, 1                                     # 1 マスの大きさと隙間 (画像の画素)
        TS = 32 * (TC + TG)
        TW = 440
        TCEN = (1240, 380)
        empty = rgb01(DARKC)
        tmask = np.zeros(TS, bool)
        for i in range(32):
            tmask[i * (TC + TG):i * (TC + TG) + TC] = True
        cellmask = tmask[:, None] & tmask[None, :]
        yy2, xx2 = np.mgrid[0:TS, 0:TS]
        cell_id = ((yy2 // (TC + TG)) * 32 + xx2 // (TC + TG))[cellmask]

        def table_img(state):
            cols = np.where(state[:, None] >= 0, dshow[np.clip(state, 0, None)], empty)
            img = np.zeros((TS, TS, 3), np.float32) + rgb01(BG)
            img[cellmask] = cols[cell_id]
            return np.dstack([img.astype(np.uint8), np.full((TS, TS), 255, np.uint8)])
        table = ImageMobject(table_img(np.full(cache_n, -1)))
        table.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        table.width = u(TW)
        table.move_to(px(*TCEN))
        table.check_ignore = True
        tlab = mix(f"{fmt(cache_n)}マス", 32, DIM).move_to(px(TCEN[0], TCEN[1] - TW / 2 - 30))

        def cell_point(s_):
            k = TW / TS
            return px(TCEN[0] - TW / 2 + ((s_ % 32) * (TC + TG) + TC / 2) * k,
                      TCEN[1] - TW / 2 + ((s_ // 32) * (TC + TG) + TC / 2) * k)
        self.play(FadeIn(table, scale=0.9), FadeIn(tlab), rill.animate.set_opacity(1), FadeIn(rlab), FadeIn(rnote), run_time=0.9)

        def dim_r(t):
            rill.lit[:] = 1 - 0.84 * t
            rill.refresh()
        self.play(Fn(rill, dim_r), run_time=0.5)

        # 書いた差が流れ込んで、たまっていく (読んだ順に。表は実際の中身)
        self.at("recent", -0.1)
        # 表が埋まっていく速さが一定に見えるように、時間を読んだ点の数へ写す (埋まったら残りは一気に)
        ks = np.linspace(0, N, 400).astype(np.int64)
        filled = np.array([(cache_at(k_) >= 0).sum() for k_ in ks], np.float64)
        k_full = ks[np.searchsorted(filled, filled[-1])]

        def warp(t):
            if t < 0.8:
                return int(np.interp(t / 0.8 * filled[-1], filled, ks))
            return int(k_full + (N - k_full) * (t - 0.8) / 0.2)

        seen, evs = set(), []
        for i in np.nonzero((P[..., 3].reshape(-1) == 255) & (flat != 0))[0]:
            if flat[i] not in seen:
                seen.add(flat[i])
                evs.append(int(i))
        evs = [e for e in evs if e < k_full]
        evs = [evs[int(j)] for j in np.linspace(0, len(evs) - 1, 14)]
        tev = {i: 0.8 * float(np.interp(i, ks, filled)) / filled[-1] for i in evs}
        flyers = []
        for i in evs:
            f = Square(u(18), stroke_width=1.5, stroke_color=INK, fill_color=hexrgb(*dshow[i]), fill_opacity=1)
            f.set_opacity(0)
            flyers.append(f)
        flyg = VGroup(*flyers)
        self.add(flyg)
        rowsY = np.arange(H_)
        RT = self.until("num", -0.15)
        FLY = 0.2

        def scan(t):
            k = min(N, warp(t))
            ry, rx = divmod(k, W_)
            lit = np.repeat(np.where(rowsY < ry, 1.0, 0.16).astype(np.float32)[:, None], W_, 1)
            if ry < H_:
                lit[ry, :rx] = 1.0
            rill.lit = lit
            rill.refresh()
            table.pixel_array = table_img(cache_at(k))
            for f, i in zip(flyers, evs):
                a = (t - tev[i]) / FLY
                if 0 <= a <= 1:
                    y, x = divmod(i, W_)
                    p0, p1 = rill.to_point(x + 0.5, y + 0.5), cell_point(int(slot[i]))
                    mid = (p0 + p1) / 2 + UP * u(90)
                    f.move_to((1 - a) ** 2 * p0 + 2 * (1 - a) * a * mid + a ** 2 * p1)
                    f.set_opacity(1)
                else:
                    f.set_opacity(0)
        self.play(Fn(Group(rill, table, flyg), scan, rate_func=linear), run_time=RT)
        self.remove(flyg)

        # 差の代わりに表の番号
        self.at("num", -0.1)
        ering = Circle(radius=u(16), stroke_color=YELLOW, stroke_width=5).move_to(rill.to_point(exx + 0.5, ey + 0.5))
        EX, EY = 1138, 690
        ecells = VGroup()
        for j, (nm, v) in enumerate(zip("RGBA", edif)):
            sq = Square(u(64), stroke_width=2, stroke_color="#3a3f4c", fill_color=DARKC, fill_opacity=1)
            sq.move_to(px(EX + j * 68, EY))
            t = mono(("+" if v > 0 else "") + str(v).replace("-", "−"), 30, PURPLE).move_to(sq)
            lb = jp(nm, 26, DIM).move_to(px(EX + j * 68, EY - 56))
            ecells.add(VGroup(sq, t, lb))
        cpt = cell_point(cex[4])
        tcell = Square(u(TW / TS * (TC + 8)), stroke_color=YELLOW, stroke_width=4).move_to(cpt)
        enum_ = mix(f"表の{cex[4]}番", 44, YELLOW).move_to(px(EX + 102, EY + 130))
        earr = Arrow(px(EX + 102, EY + 38), px(EX + 102, EY + 100), buff=0, color=YELLOW, stroke_width=5,
                     max_tip_length_to_length_ratio=0.35)
        self.play(Create(ering), FadeIn(ecells, shift=RIGHT * u(10)), Create(tcell), run_time=0.6)
        self.play(GrowArrow(earr), FadeIn(enum_, shift=DOWN * u(8)), run_time=0.5)

        # ================= S08_12：点の数 =================
        self.at("stat", -0.1)
        self.play(FadeOut(VGroup(ering, enum_, earr, ecells, tcell, tlab, head, rlab, rnote)), table.animate.set_opacity(0),
                  rill.animate.set_opacity(0), run_time=0.4)
        self.remove(table, rill)
        self.play(move(ill, STAT_C, STAT_H), run_time=0.5)
        SX0, SX1, SY_, SH = 510, 1410, 560, 60
        SW = SX1 - SX0
        tl_ = mix(f"{fmt(N)}個の点", 40, INK).move_to(px(960, SY_ - 68))
        segs, x = {}, SX0
        for k in ("copy", "cache", "lit"):
            w = SW * npx[k] / N
            s_ = Rectangle(width=u(w), height=u(SH), stroke_width=0, fill_color=DIM, fill_opacity=0.9)
            s_.move_to(px(x + w / 2, SY_))
            segs[k] = s_
            x += w
        self.play(FadeIn(tl_), *[GrowFromEdge(s_, LEFT) for s_ in segs.values()], run_time=0.5)

        # イラストの点を、書き方で塗り分ける
        lum = (ill.base.mean(-1, keepdims=True) / 255)
        tmasks = {}
        for k, kid in (("copy", 0), ("cache", 1), ("lit", 2)):
            col = rgb01(TYPE_COL[k])[None, None, :] * (0.3 + 0.7 * lum)
            m = np.zeros((H_, W_), np.float32)
            ill.layers.append((col, m))
            tmasks[k] = (m, (kind == kid).astype(np.float32) * 0.85)
        names = {"copy": "コピー", "cache": "表の番号", "lit": "そのまま"}
        shift_ = {"copy": -10, "cache": 0, "lit": 10}           # 分かれて隙間があく
        labs, ticks = {}, {}

        def split(k, cue):
            self.at(cue, -0.1)
            s_ = segs[k]
            cxp = s_.get_center()[0] / u(1) + 960 + shift_[k]       # 動いたあとの中心 (px)
            lb = mix(f"{names[k]} {fmt(npx[k])}", 36, TYPE_COL[k])
            extra = []
            if k == "copy":
                lb.move_to(px(cxp, SY_ + 66))
            else:
                ly = SY_ + 66 if k == "cache" else SY_ + 136
                right = s_.get_right()[0] / u(1) + 960 + shift_[k]
                lb.move_to(px(right, ly), aligned_edge=RIGHT)
                tk = Line(px(cxp, SY_ + SH / 2 + 4), px(cxp, ly - 24), stroke_color=TYPE_COL[k], stroke_width=3)
                ticks[k] = tk
                extra.append(Create(tk))
            labs[k] = lb
            m, tgt = tmasks[k]

            def tint(t):
                m[:] = tgt * t
                ill.refresh()
            self.play(s_.animate.set_fill(TYPE_COL[k]).shift(RIGHT * u(shift_[k])), *extra,
                      FadeIn(lb, shift=DOWN * u(6)), Fn(ill, tint), run_time=0.9)
        split("copy", "copy2")
        split("cache", "cache2")
        split("lit", "raw")

        self.at("mostly", -0.1)
        self.play(pop(VGroup(segs["copy"], labs["copy"]), 1.08, 0.7), run_time=0.7)

        # 透明な背景・同じ色が続く所
        shade = np.zeros((H_, W_), np.float32)
        ill.layers.append((np.full((H_, W_, 3), 14, np.float32), shade))

        def flash(sel):
            def fn(t):
                shade[:] = np.where(sel, 0.0, 0.7 * t)
                ill.refresh()
            return fn
        bgsel = (P[..., 3] == 0) & (kind == 0)
        insel = (P[..., 3] > 0) & (kind == 0)
        self.at("bg", -0.1)
        self.play(Fn(ill, flash(bgsel), rate_func=there_and_back), run_time=1.6)
        self.at("lines", -0.1)
        self.play(Fn(ill, flash(insel), rate_func=there_and_back), run_time=1.6)

        self.at(self.tl["duration"] - 0.75)
        self.play(ill.animate.set_opacity(0), FadeOut(VGroup(tl_, *segs.values(), *labs.values(), *ticks.values())),
                  run_time=0.6)
        self.finish()
