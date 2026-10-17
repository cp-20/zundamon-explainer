import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, frame_rgba, indices, info, palette  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

GREEN = "#7ee08a"
RC, GC, BC = "#ff8a8a", "#7ee08a", "#7fb0ff"
CELL = 32.5                  # 最初の 16×16 の 1 マス（全体 520px）
SMALL = 22.5                   # 縮めたあとの 1 マス
TCX, TCY = 1250, 255         # 縮めた表の中心
R0, C0, NW = 64, 38, 5       # 目のあたりの 7×7 画素
ZOOM = 90
ZCX, ZCY = 800, 645


def col(rgb):
    return rgb_to_color(np.array(rgb) / 255)


def light(rgb):
    return sum(int(c) for c in rgb) > 380


def checker_sq(side, pos):
    """透明を表す市松模様の 1 マス（2×2）"""
    g = VGroup()
    for k in range(4):
        s = Square(side / 2, stroke_width=0, fill_opacity=1,
                   fill_color="#3b3f4c" if (k % 2 == k // 2) else "#555b6c")
        g.add(s)
    g.arrange_in_grid(2, 2, buff=0)
    return g.move_to(pos)


class S03(PScene):
    def construct(self):
        inf = info()
        pal = palette()
        ix = indices()
        fb = file_bytes("zunda_anim")
        gct = [b for b in inf["blocks"] if b["kind"] == "gct"][0]
        assert gct["length"] == 768 == 256 * 3
        raw = fb[gct["offset"]:gct["offset"] + gct["length"]]
        assert np.array_equal(np.frombuffer(raw, np.uint8).reshape(256, 3), pal)
        tidx = inf["frames"][0]["gce"]["transparent_index"]
        assert tidx == 255 and (ix == tidx).sum() > 0

        title = jp("色の表", 72, YELLOW).move_to(px(960, 300))
        self.add(title)

        # ---- 768 バイト → 3 バイトずつ → 16×16 ----
        GY0 = 590
        grid = VGroup()
        for i in range(256):
            r, c = divmod(i, 16)
            sq = Square(u(CELL - 2), stroke_width=0, fill_opacity=1, fill_color=col(pal[i]))
            sq.move_to(px(960 + CELL * (c - 7.5), GY0 + CELL * (r - 7.5)))
            grid.add(sq)

        self.at("s03_01")
        head = jp("色の表", 44, YELLOW).move_to(px(900, 60))
        nbytes = jp(f"{gct['length']} バイト", 34, DIM).move_to(px(1120, 60))
        triples = VGroup(*[mono(" ".join(f"{b:02x}".upper() for b in raw[3 * k:3 * k + 3]), 40)
                           .move_to(px(585 + 250 * k, 215)) for k in range(4)])
        self.play(Transform(title, head), FadeIn(nbytes, shift=UP * u(8)),
                  FadeIn(triples, shift=UP * u(8)), run_time=0.9)

        self.at("list")
        firsts = []
        for k in range(4):
            t = triples[k].copy()
            t.check_ignore = True
            firsts.append(ReplacementTransform(t, grid[k]))
        self.play(*firsts, run_time=1.0)
        self.play(LaggedStart(*[FadeIn(grid[i]) for i in range(4, 256)], lag_ratio=0.012),
                  FadeOut(triples), run_time=2.4)

        self.at("colors")
        self.play(pop(grid, 1.06, 0.8))

        # ---- 画像には番号だけ ----
        self.at("index", -0.3)
        SX, SY, SH = 260, 245, 300
        stamp = png_mob(frame_rgba(), SH, nearest=True).move_to(px(SX, SY))
        pw = stamp.width / ix.shape[1]
        tl = stamp.get_corner(UL)
        eye = tl + RIGHT * pw * (C0 + NW / 2) + DOWN * pw * (R0 + NW / 2)
        box = Square(pw * NW + u(8), stroke_color=YELLOW, stroke_width=3).move_to(eye)
        self.play(grid.animate.scale(SMALL / CELL).move_to(px(TCX, TCY)),
                  title.animate.move_to(px(TCX, 45)).scale(0.8),
                  FadeOut(nbytes), FadeIn(stamp, shift=RIGHT * u(20)), run_time=0.7)
        self.play(Create(box), run_time=0.3)

        win = ix[R0:R0 + NW, C0:C0 + NW]
        zc = lambda r, c: px(ZCX + ZOOM * (c - (NW - 1) / 2), ZCY + ZOOM * (r - (NW - 1) / 2))
        zcells = VGroup(*[Square(u(ZOOM - 2), stroke_width=0, fill_opacity=1,
                                 fill_color=col(pal[win[r, c]])).move_to(zc(r, c))
                          for r in range(NW) for c in range(NW)])
        zframe = Square(u(ZOOM * NW), stroke_color=YELLOW, stroke_width=3).move_to(px(ZCX, ZCY))
        self.play(ReplacementTransform(box.copy(), zframe),
                  LaggedStart(*[FadeIn(c) for c in zcells], lag_ratio=0.01), run_time=0.5)

        self.at("num", -0.1)
        badges = VGroup()
        for r in range(NW):
            for c in range(NW):
                t = mono(str(win[r, c]), 32, CYAN)
                bg = Rectangle(width=u(68), height=u(44), stroke_width=0, fill_color=BG, fill_opacity=0.8)
                badges.add(VGroup(bg, t).move_to(zc(r, c)))
        badges.set_z_index(3)
        self.play(LaggedStart(*[FadeIn(b, scale=0.8) for b in badges], lag_ratio=0.02), run_time=1.2)

        # 右端の列から、違う番号を 3 つ選んで 1 本ずつ線を引く
        picks = {}
        for r in range(NW):
            picks.setdefault(int(win[r, NW - 1]), (r, NW - 1))
        lines, marks = [], []
        for v, (r, c) in list(picks.items())[:3]:
            ln = Line(zc(r, c) + RIGHT * u(ZOOM / 2), grid[v].get_center(), color=CYAN, stroke_width=4)
            ln.set_z_index(2)
            mk = Square(u(SMALL + 3), stroke_color=CYAN, stroke_width=3).move_to(grid[v])
            mk.set_z_index(2)
            lines.append(ln)
            marks.append(mk)
            self.play(Create(ln), Create(mk), run_time=0.7)
            self.wait(0.6)

        # ---- 3 バイト → 1 バイト ----
        self.at("three", -1.0)
        self.play(FadeOut(Group(stamp, box, zframe, zcells, badges, *lines)),
                  *[FadeOut(m) for m in marks], run_time=0.8)
        demo = int(np.bincount(win.flatten()).argmax())
        drgb = pal[demo]
        DY = 300
        swatch = Square(u(120), stroke_width=0, fill_opacity=1, fill_color=col(drgb)).move_to(px(540, DY))
        cx = [690, 790, 890]
        chips = VGroup()
        for k, cc in enumerate((RC, GC, BC)):
            bgc = Rectangle(width=u(80), height=u(100), stroke_color=cc, stroke_width=3)
            chips.add(VGroup(bgc, mono(str(int(drgb[k])), 40, cc)).move_to(px(cx[k], DY)))
        labs = VGroup(*[jp(n, 30, cc).move_to(px(cx[k], DY + 85)) for k, (n, cc) in
                        enumerate((("赤", RC), ("緑", GC), ("青", BC)))])
        mk_demo = Square(u(SMALL + 3), stroke_color=CYAN, stroke_width=3).move_to(grid[demo])
        self.at("three")
        self.play(FadeIn(swatch), FadeIn(mk_demo), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(c, shift=RIGHT * u(10)) for c in chips], lag_ratio=0.2),
                  FadeIn(labs), run_time=0.8)
        n3 = jp("3 バイト", 40, INK).move_to(px(790, DY + 160))
        self.play(FadeIn(n3, shift=UP * u(8)), run_time=0.5)

        self.at("one")
        one = VGroup(Rectangle(width=u(120), height=u(100), stroke_color=CYAN, stroke_width=3),
                     mono(str(demo), 40, CYAN)).move_to(px(790, DY))
        n1 = jp("1 バイト", 40, CYAN).move_to(n3)
        self.play(ReplacementTransform(chips, one), FadeOut(labs), Transform(n3, n1), run_time=1.0)

        self.at("third", -0.1)
        self.play(pop(one, 1.2, 0.6), pop(n3, 1.2, 0.6))

        # ---- 255 番は透明 ----
        self.at("clear", -1.0)
        self.play(FadeOut(VGroup(swatch, one, n3)), FadeOut(mk_demo), run_time=0.8)
        rgb_img = pal[ix]                                           # 色の表のとおりの色（255 番は表の色のまま）
        full = np.zeros((*ix.shape, 4), np.uint8)
        full[..., :3], full[..., 3] = rgb_img, 255
        bigh = 420
        solid = png_mob(full, bigh, nearest=True).move_to(px(740, 480))
        self.at("clear")
        self.play(FadeIn(solid), run_time=0.3)
        t255 = jp(f"{tidx}", 56, CYAN).move_to(px(1000, 760))
        c255 = grid[tidx]
        ln255 = Line(px(1000, 720), c255.get_center(), color=CYAN, stroke_width=3)
        mk255 = Square(u(SMALL + 3), stroke_color=CYAN, stroke_width=3).move_to(c255)
        self.play(FadeIn(t255), Create(ln255), Create(mk255), run_time=0.4)

        self.at("tp")
        real = png_mob(frame_rgba(), bigh, nearest=True).move_to(solid)
        ck = checker_sq(u(SMALL), c255.get_center())
        self.play(FadeIn(real), solid.animate.set_opacity(0), FadeIn(ck), run_time=0.9)
        self.remove(solid)
        self.play(pop(ck, 1.5, 0.6), run_time=0.6)

        # ---- 256 色まで ----
        self.at("limit")
        self.play(pop(grid, 1.08, 0.8))
        self.at("photo", -0.2)
        self.play(FadeOut(Group(grid, title, real, t255, ln255, mk255, ck)), run_time=1.0)
        self.finish()
