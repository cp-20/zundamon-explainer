import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import MAIN_CTB, SIZE_COLOR, area_shares, ctb_grid, ctb_size, ctb_splits, cus, picture_size, rgb_decoded, splits  # noqa: E402
from vlib.photoview import LW, Grow, PhotoView, PLine, PRect, TrackFade, ViewAnim, cross_lines, move_view  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)          # 写真の定位置 (S02 の終わり・S04 の始まりと同じ)
ZBOX = ((800, 405), 700, 700)            # 64×64 に寄ったときの箱
MARGIN = 10                              # 寄ったときに 64×64 のまわりに見せる画素
CARD_C = (1315, 165)
LEG_Y = (290, 365)
BIT_Y, BIT_X0, BIT_W, BIT_GAP = 815, 470, 46, 7
PANEL_X = 225                            # 左上の札の中心


class LineOp(Animation):
    """PLine の不透明度を変える (PLine は窓で切るときに不透明度を持ち直すので、FadeIn/Out ではなくこれで)"""

    def __init__(self, lines, to, **kw):
        self.lines = list(lines)
        super().__init__(VGroup(*self.lines), **kw)
        self.to = to
        self.start = [ln._op if hasattr(ln, "_op") else ln.get_stroke_opacity() for ln in self.lines]

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        for ln, s in zip(self.lines, self.start):
            ln._op = s + (self.to - s) * a
            ln.sync()


class MoveRect(Animation):
    """PRect の囲む範囲を別の範囲へ"""

    def __init__(self, rect, r, **kw):
        super().__init__(rect, **kw)
        self.r0, self.r1 = np.array(rect.r, float), np.array(r, float)

    def interpolate_mobject(self, alpha):
        self.mobject.r = tuple(self.r0 + (self.r1 - self.r0) * self.rate_func(alpha))
        self.mobject.sync()


def bit_chip(b, size=34):
    box = RoundedRectangle(corner_radius=u(8), width=u(BIT_W), height=u(56), stroke_width=0,
                           fill_color=YELLOW if b else "#3a3f4c", fill_opacity=1)
    t = mono(str(b), size, BG if b else INK)
    t.move_to(box)
    return VGroup(box, t)


class S03(PScene):
    def construct(self):
        W, H = picture_size()
        N = ctb_size()
        assert (W, H) == (451, 300) and N == 64 and ctb_grid() == (8, 5)
        rx, ry = MAIN_CTB
        X0, Y0 = rx * N, ry * N
        sp = ctb_splits(rx, ry)
        coded = [s for s in sp if s["coded"]]
        bits = [s["split"] for s in coded]
        assert bits == [1, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0]
        assert [s["size"] for s in coded] == [64, 32, 16, 16, 16, 16, 32, 16, 16, 16, 16, 32, 32]
        shares = area_shares()
        pct = {k: round(v * 100) for k, v in shares.items()}
        assert pct == {32: 52, 16: 31, 8: 10, 4: 7} and 0.45 < shares[32] < 0.55   # 「半分が 32×32」
        cu_all = cus()
        nxn_here = [c for c in cu_all if c["nxn"] and X0 <= c["x"] < X0 + N and Y0 <= c["y"] < Y0 + N]
        assert len(nxn_here) == 6

        # ---- S02 の終わり：写真 ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True          # 線や札を上に重ねる下敷き
        self.add(view)

        # ---- WebP の 16×16 ----
        self.at("webp16", -0.1)
        g16 = []
        for x in range(16, W, 16):
            g16.append(PLine(view, (x, 0), (x, H), frac=0, stroke_color=INK, stroke_width=1.5, stroke_opacity=0.55))
        for y in range(16, H, 16):
            g16.append(PLine(view, (0, y), (W, y), frac=0, stroke_color=INK, stroke_width=1.5, stroke_opacity=0.55))
        self.add(*g16)
        lab_fmt = jp("WebP", 38, DIM).move_to(px(PANEL_X, 150))
        lab_sz = mono("16×16", 56, INK).move_to(px(PANEL_X, 225))
        order = sorted(range(len(g16)), key=lambda i: (g16[i].a[0] + g16[i].a[1]))
        self.play(LaggedStart(*[Grow(g16[i], run_time=0.9) for i in order], lag_ratio=0.04),
                  FadeIn(lab_fmt, shift=RIGHT * u(10)), FadeIn(lab_sz, shift=RIGHT * u(10)), run_time=2.2)

        # ---- HEIC の 64×64 ----
        self.at("heic64", -0.1)
        self.play(LineOp(g16, 0), lab_fmt.animate.set_opacity(0.0), run_time=0.8)
        self.remove(*g16)
        lab_fmt2 = jp("HEIC", 38, DIM).move_to(lab_fmt)
        lab_sz2 = mono("64×64", 56, SIZE_COLOR[64]).move_to(lab_sz)
        g64 = []
        for x in range(N, W, N):
            g64.append(PLine(view, (x, 0), (x, H), frac=0, stroke_color=SIZE_COLOR[64], stroke_width=LW[64]))
        for y in range(N, H, N):
            g64.append(PLine(view, (0, y), (W, y), frac=0, stroke_color=SIZE_COLOR[64], stroke_width=LW[64]))
        self.add(*g64)
        self.at("c64", -0.15)
        self.play(LaggedStart(*[Grow(ln, run_time=0.9) for ln in g64], lag_ratio=0.08),
                  FadeIn(lab_fmt2), Transform(lab_sz, lab_sz2), run_time=1.6)
        lab_sz.text = "64×64"
        self.remove(lab_fmt)

        # ---- 目のあたり ----
        self.at("eye", -0.1)
        eyes = [PRect(view, rx * N, (ry - 1) * N, N, N, stroke_color=YELLOW, stroke_width=6),
                PRect(view, X0, Y0, N, N, stroke_color=YELLOW, stroke_width=6)]
        self.play(*[Create(e) for e in eyes], run_time=0.7)
        self.play(*[Indicate(e, color=YELLOW, scale_factor=1.04) for e in eyes], run_time=0.9)

        # ---- 主役の 64×64 へ寄る ----
        self.at("ask", -0.05)
        win = (X0 - MARGIN, Y0 - MARGIN, X0 + N + MARGIN, Y0 + N + MARGIN)
        lit = np.ones((H, W), np.float32)

        def dim_out(t):
            lit[:] = 1 - 0.68 * t
            lit[Y0:Y0 + N, X0:X0 + N] = 1
            view.lit = lit
        self.play(move_view(view, win, ZBOX), ViewAnim(view, dim_out), TrackFade(eyes[0], 1, 0),
                  FadeOut(VGroup(lab_fmt2, lab_sz), shift=LEFT * u(10)), run_time=1.6)
        self.remove(eyes[0])
        cur = eyes[1]

        # 問いのカードと答えの決まり
        card = RoundedRectangle(corner_radius=u(18), width=u(310), height=u(104), stroke_color=YELLOW, stroke_width=3,
                                fill_color="#232833", fill_opacity=1).move_to(px(*CARD_C))
        card_t = jp("4つに割る？", 46, INK).move_to(card)
        self.at("q", -0.1)
        self.play(FadeIn(card, shift=LEFT * u(14)), FadeIn(card_t, shift=LEFT * u(14)), run_time=0.6)
        leg = []
        for b, y, word in ((1, LEG_Y[0], "はい"), (0, LEG_Y[1], "いいえ")):
            w = jp(word, 40, INK)
            arr = jp("→", 40, DIM)
            chip = bit_chip(b)
            row = VGroup(w, arr, chip).arrange(RIGHT, buff=u(18)).move_to(px(CARD_C[0], y))
            row.word, row.chip = w, chip
            leg.append(row)
        self.at("yes", -0.1)
        self.play(FadeIn(leg[0], shift=UP * u(8)), run_time=0.5)
        self.at("no", -0.1)
        self.play(FadeIn(leg[1], shift=UP * u(8)), run_time=0.5)

        # ---- 1 つずつ聞いていく ----
        slots = [px(BIT_X0 + BIT_W / 2 + i * (BIT_W + BIT_GAP), BIT_Y) for i in range(len(bits))]
        placed = []
        split_lines = {}

        def crosses(k):
            s = coded[k]
            ls = cross_lines(view, s["x"], s["y"], s["size"], W, H, SIZE_COLOR[s["size"] // 2], LW[s["size"] // 2])
            self.add(*ls)
            self.bring_to_front(cur)      # いま聞いているブロックの黄色い枠は、割れ方の線より手前に
            return [Grow(ln) for ln in ls]

        def answer(k, rt=0.7, grow_rt=0.8, grow=True, focus_rt=0.0):
            """k 番目の問いに答える：(枠が移り) 答えの行が光り、ビットが飛んで並び、割るなら十字が伸びる。
            focus_rt > 0 なら枠の移動・ビット・十字を 1 つの動きにまとめる (速く進めるとき)"""
            s = coded[k]
            b = s["split"]
            row = leg[0 if b else 1]
            chip = row.chip.copy()
            self.add(chip)
            anims = [chip.animate(path_arc=-0.6).move_to(slots[k]), Indicate(row.word, color=YELLOW if b else INK, scale_factor=1.15)]
            placed.append(chip)
            if focus_rt:
                mv = MoveRect(cur, (s["x"], s["y"], s["size"], s["size"]), run_time=focus_rt)
                seq = [mv, AnimationGroup(*anims, run_time=rt)]
                if b:
                    seq.append(AnimationGroup(*crosses(k), run_time=grow_rt))
                self.play(Succession(*seq), run_time=focus_rt + rt + (grow_rt if b else 0))
                return
            self.play(*anims, run_time=rt)
            if b and grow:
                self.play(*crosses(k), run_time=grow_rt)

        self.at("a64", -0.1)
        answer(0, rt=0.6, grow=False)
        self.at("four", -0.05)
        self.play(*crosses(0), run_time=0.8)

        # 4 つの 32×32 に順番の番号
        self.at("each", -0.1)
        nums = VGroup()
        for i, (dx, dy) in enumerate(((0, 0), (32, 0), (0, 32), (32, 32))):
            c = view.to_point(X0 + dx + 16, Y0 + dy + 16)
            disc = Circle(radius=u(30), stroke_width=0, fill_color=BG, fill_opacity=0.82).move_to(c)
            nums.add(VGroup(disc, mono(str(i + 1), 40, INK).move_to(c)))
        self.play(LaggedStart(*[FadeIn(n, scale=0.6) for n in nums], lag_ratio=0.25), run_time=1.4)

        self.at("tl", -0.1)
        self.play(FadeOut(nums, scale=0.8), MoveRect(cur, (X0, Y0, 32, 32)), run_time=0.6)
        self.at("a32", -0.25)
        answer(1, rt=0.5, grow_rt=0.6)

        # 左上の 32×32 の中の 16×16 (目のふち)
        self.at("deep", 0.1)
        for k in range(2, 6):
            answer(k, rt=0.4, grow_rt=0.4, focus_rt=0.3)

        # 右上の 32×32 と、下の 2 つ
        self.at("fur", -0.05)
        for k in range(6, 13):
            answer(k, rt=0.28, grow_rt=0.25, focus_rt=0.18)
        # 割らなかった 32×32 (下の毛)
        keep = [PRect(view, s["x"], s["y"], s["size"], s["size"], stroke_color=SIZE_COLOR[32], stroke_width=7)
                for s in coded[11:]]
        self.play(FadeOut(cur), *[Create(r) for r in keep], run_time=0.4)
        self.play(*[Indicate(r, color=SIZE_COLOR[32], scale_factor=1.02) for r in keep], run_time=0.5)

        self.at("result", -0.1)
        self.play(*[FadeOut(r) for r in keep], VGroup(*placed).animate.shift(UP * u(4)), run_time=0.5)
        self.play(LaggedStart(*[Indicate(c, scale_factor=1.12, color=YELLOW) for c in placed], lag_ratio=0.08), run_time=1.4)

        # ---- 8×8 の中の 4×4 ----
        self.at("small8", -0.1)
        c0 = nxn_here[0]
        hi8 = PRect(view, c0["x"], c0["y"], 8, 8, stroke_color=YELLOW, stroke_width=5)
        self.play(Create(hi8), run_time=0.5)
        self.at("p4", -0.1)
        l4 = []
        for c in nxn_here:
            l4 += cross_lines(view, c["x"], c["y"], 8, W, H, SIZE_COLOR[4], LW[4])
        self.add(*l4)
        self.play(LaggedStart(*[Grow(ln) for ln in l4], lag_ratio=0.1), run_time=1.2)
        self.play(FadeOut(hi8), run_time=0.4)

        # ---- 写真全体へ ----
        self.at("s03_11", -0.1)
        ui = VGroup(card, card_t, *leg, *placed)

        def undim(t):
            lit[:] = 0.32 + 0.68 * t
            lit[Y0:Y0 + N, X0:X0 + N] = 1
            view.lit = lit
        self.play(move_view(view, (0, 0, W, H), PHOTO), ViewAnim(view, undim),
                  FadeOut(ui, shift=RIGHT * u(20)), run_time=1.6)
        view.lit = None

        # 全部の 64×64 が段ごとに割れていく
        self.at("all", -0.1)
        mine = set((s["x"], s["y"], s["size"]) for s in sp)
        levels = {32: [], 16: [], 8: [], 4: []}
        for s in splits():
            if s["split"] and (s["x"], s["y"], s["size"]) not in mine:
                levels[s["size"] // 2] += cross_lines(view, s["x"], s["y"], s["size"], W, H, SIZE_COLOR[s["size"] // 2],
                                                      LW[s["size"] // 2])
        for c in cu_all:
            if c["nxn"] and (c["x"], c["y"], 8) not in mine and not (X0 <= c["x"] < X0 + N and Y0 <= c["y"] < Y0 + N):
                levels[4] += cross_lines(view, c["x"], c["y"], 8, W, H, SIZE_COLOR[4], LW[4])
        for k in (32, 16, 8, 4):
            self.add(*levels[k])
            self.play(*[Grow(ln) for ln in levels[k]], run_time=0.62, rate_func=rate_functions.ease_out_cubic)

        # 大きいまま / 小さく
        size_of = np.zeros((H, W), np.int32)
        for c in cu_all:
            x, y, s = c["x"], c["y"], c["size"]
            size_of[y:y + s, x:x + s] = 4 if c["nxn"] else s
        size_of = size_of[:H, :W]
        lit = np.ones((H, W), np.float32)

        def spot(target):
            src = lit.copy()

            def fn(t):
                lit[:] = src + (target - src) * t
                view.lit = lit
            return ViewAnim(view, fn)
        self.at("flat", -0.1)
        self.play(spot(np.where(size_of == 32, 1.0, 0.3).astype(np.float32)), run_time=0.8)
        self.at("detail", -0.1)
        self.play(spot(np.where(size_of <= 8, 1.0, 0.3).astype(np.float32)), run_time=0.8)
        self.at("why", -0.1)
        self.play(spot(np.ones((H, W), np.float32)), run_time=0.7)
        view.lit = None

        # ---- 大きいブロック 1 つ と 小さいブロック 64 個 ----
        flat = next(c for c in cu_all if c["size"] == 32 and c["x"] >= 384 and c["y"] >= 128 and c["y"] + 32 <= H)
        fx, fy = flat["x"], flat["y"]
        crop = rgb_decoded()[fy:fy + 32, fx:fx + 32]
        SQ = 180
        cx = [PANEL_X - 98, PANEL_X + 98]
        cy = 205
        imgs = []
        for x in cx:
            m = ImageMobject(np.dstack([crop, np.full((32, 32), 255, np.uint8)]))
            m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
            m.width = u(SQ)
            m.move_to(px(x, cy))
            m.check_ignore = True
            imgs.append(m)
        src_rect = PRect(view, fx, fy, 32, 32, stroke_color=SIZE_COLOR[32], stroke_width=5)
        self.at("cost", -0.1)
        self.play(Create(src_rect), run_time=0.4)
        frames = [Square(u(SQ), stroke_color=SIZE_COLOR[32], stroke_width=4).move_to(px(x, cy)) for x in cx]
        small = VGroup()
        for k in range(1, 8):
            small.add(Line(px(cx[1] - SQ / 2 + k * SQ / 8, cy - SQ / 2), px(cx[1] - SQ / 2 + k * SQ / 8, cy + SQ / 2),
                           stroke_color=SIZE_COLOR[4], stroke_width=1.6))
            small.add(Line(px(cx[1] - SQ / 2, cy - SQ / 2 + k * SQ / 8), px(cx[1] + SQ / 2, cy - SQ / 2 + k * SQ / 8),
                           stroke_color=SIZE_COLOR[4], stroke_width=1.6))
        self.play(*[FadeIn(m) for m in imgs], *[Create(f) for f in frames],
                  *[TransformFromCopy(src_rect, f) for f in frames], run_time=0.8)
        self.play(Create(small), run_time=0.3)
        # 書くこと (予想の向き・差の波) の印
        self.at("write", -0.1)
        dot_big = Dot(px(cx[0], cy), radius=u(13), color=YELLOW)
        dots = VGroup(*[Dot(px(cx[1] - SQ / 2 + (i + 0.5) * SQ / 8, cy - SQ / 2 + (j + 0.5) * SQ / 8), radius=u(5),
                            color=YELLOW) for j in range(8) for i in range(8)])
        head = jp("書くこと", 34, YELLOW).move_to(px(PANEL_X, 72))
        n1 = mix("1組", 38, INK).move_to(px(cx[0], cy + SQ / 2 + 40))
        n64 = mix("64組", 38, INK).move_to(px(cx[1], cy + SQ / 2 + 40))
        self.play(FadeIn(dot_big, scale=0.4), LaggedStart(*[FadeIn(d, scale=0.4) for d in dots], lag_ratio=0.02),
                  FadeIn(head), FadeIn(n1), FadeIn(n64), run_time=1.4)
        self.at("merge", -0.1)
        self.play(pop(VGroup(frames[0], dot_big), 1.12, 0.7), run_time=0.7)

        # ---- 面積の帯 ----
        self.at("area", -0.1)
        BX0, BX1, BY, BH = 460, 1460, 790, 46
        segs, labs = VGroup(), VGroup()
        x = BX0
        for k in (32, 16, 8, 4):
            w = (BX1 - BX0) * shares[k]
            r = Rectangle(width=u(w - 4), height=u(BH), stroke_width=0, fill_color=SIZE_COLOR[k], fill_opacity=1)
            r.move_to(px(x + w / 2, BY))
            segs.add(r)
            name = f"{k}×{k}"
            if w > 200:
                t = mix(f"{name}  {pct[k]}%", 30, BG).move_to(r)
            else:
                t = VGroup(mix(name, 26, SIZE_COLOR[k]), mix(f"{pct[k]}%", 26, SIZE_COLOR[k])).arrange(DOWN, buff=u(4))
                t.next_to(r, DOWN, buff=u(8))
            labs.add(t)
            x += w
        self.play(LaggedStart(*[GrowFromEdge(s, LEFT) for s in segs], lag_ratio=0.35), run_time=1.4)
        self.play(LaggedStart(*[FadeIn(t, shift=UP * u(6)) for t in labs], lag_ratio=0.2), run_time=0.8)
        self.at("half", -0.1)
        self.play(pop(VGroup(segs[0], labs[0]), 1.08, 0.7), run_time=0.7)

        # ---- 終わり：写真と割れ方だけを残す (S04 の最初の画面) ----
        self.at("fit", 2.6)
        self.play(FadeOut(VGroup(segs, labs, frames[0], frames[1], small, dot_big, dots, head, n1, n64)),
                  *[m.animate.set_opacity(0) for m in imgs], FadeOut(src_rect), run_time=0.8)
        self.remove(*imgs)
        self.finish()
