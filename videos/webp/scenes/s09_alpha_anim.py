import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import alpha_info, anim_canvas, anim_frames, fmt, gif_stamp_size, pixels, size, webp  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

# ---- 透明 ----
ILL_C, ILL_H = (700, 515), 660          # ずんだもんのイラスト
ALP_C = (1220, 515)                     # 抜き出した透明度
CHUNK_Y, CHUNK_W, CHUNK_X = 82, 240, [690, 960, 1230]
CROP = (350, 322, 48, 48)               # くっきりを見る所 (ひじのふち)
# ---- 動き ----
STAGE_C, STAGE_H = (700, 500), 700
PATCH_C, PATCH_H = (1180, 300), 252
THUMB_Y, THUMB_H, STEP = 175, 219, 205


def img(arr, h, nearest=True):
    """透明をそのまま透かす画像 (市松模様なし)"""
    m = ImageMobject(np.ascontiguousarray(arr))
    if nearest:
        m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.height = u(h)
    return m


def at_px(m, shape, x, y):
    """画像 m (配列の形 shape) の中の点 (x, y) → 画面の点"""
    s = m.height / shape[0]
    return m.get_corner(UL) + RIGHT * s * x + DOWN * s * y


def mask_img(mask, rgba):
    a = np.zeros(mask.shape + (4,), np.uint8)
    a[mask] = rgba
    return a


class Player:
    """動くスタンプ：本物の待ち時間 (ms) でコマを切り替える updater"""

    def __init__(self, mobs, durs):
        self.mobs, self.durs, self.k, self.t = mobs, durs, 0, 0.0

    def show(self, k):
        self.k = k
        for j, m in enumerate(self.mobs):
            m.set_opacity(1 if j == k else 0)

    def __call__(self, _m, dt):
        self.t += dt
        while self.t >= self.durs[self.k] / 1000:
            self.t -= self.durs[self.k] / 1000
            self.show((self.k + 1) % len(self.mobs))


class S09(PScene):
    def construct(self):
        # ================= データ =================
        P = pixels("zunda_q80")
        chunks, alpha = alpha_info()
        alpha = np.array(alpha, np.uint8)
        assert chunks == [("VP8X", 10), ("ALPH", 16255), ("VP8 ", 25472)]
        assert (alpha == P[..., 3]).all() and (alpha == pixels("zunda")[..., 3]).all()   # 透明度は捨てずに、元のまま
        frames, canv = anim_frames(), anim_canvas()
        n = len(frames)
        durs = [f["duration"] for f in frames]
        g_sz, w_sz = gif_stamp_size(), size("zunda_anim")
        assert (g_sz, w_sz) == (28615, 21468)
        f1 = frames[1]
        L, T, RW, RH = f1["x"], f1["y"], f1["width"], f1["height"]
        assert (L, T, RW, RH) == (26, 50, 69, 31) and RW * RH == 2139
        a1 = f1["rgba"][..., 3]
        clear = a1 == 0
        assert clear.sum() == 999 and (~clear).sum() == 1140
        # 透明な点は前のコマと同じ (透かせば 1 コマ目が見える)、書いた点だけで 2 コマ目ができる
        assert (canv[1][T:T + RH, L:L + RW][clear] == canv[0][T:T + RH, L:L + RW][clear]).all()
        wf = webp("zunda_anim")["frames"]
        assert all([c[0] for c in fr["chunks"]] == ["VP8L"] for fr in wf)
        CH, CW = canv[0].shape[:2]

        # ================= 透明を持てる =================
        ill = png_mob(P, ILL_H).move_to(px(*ILL_C))
        self.at("alpha", -0.2)
        self.play(FadeIn(ill, shift=UP * u(12)), run_time=0.9)

        # JPEG は透明を持てない：背景が塗りつぶされる
        self.at("jpg", -0.1)
        a = P[..., 3:4].astype(np.float32) / 255
        jrgb = (P[..., :3] * a + 255 * (1 - a)).astype(np.uint8)
        jpg = png_mob(jrgb, ILL_H).move_to(px(*ALP_C))
        lab_w = mix("WebP", 32, INK).move_to(px(ILL_C[0], ILL_C[1] + ILL_H / 2 + 30))
        lab_j = mix("JPEG", 32, DIM).move_to(px(ALP_C[0], ALP_C[1] + ILL_H / 2 + 30))
        self.play(FadeIn(jpg, shift=LEFT * u(20)), FadeIn(lab_j), FadeIn(lab_w), run_time=0.8)

        self.at("lossy", -0.1)
        self.play(jpg.animate.set_opacity(0), FadeOut(lab_j), FadeOut(lab_w), run_time=0.7)
        self.remove(jpg)

        # ================= 箱の並びと ALPH =================
        self.at("alph", -0.3)
        boxes = VGroup()
        for (name, nb), x in zip(chunks, CHUNK_X):
            r = RoundedRectangle(corner_radius=u(12), width=u(CHUNK_W), height=u(96), stroke_width=3,
                                 stroke_color=DIM, fill_color="#232833", fill_opacity=1).move_to(px(x, CHUNK_Y))
            t = mono(name, 34, INK).move_to(px(x, CHUNK_Y - 19))
            s = mix(f"{fmt(nb)} バイト", 30, DIM).move_to(px(x, CHUNK_Y + 22))
            boxes.add(VGroup(r, t, s))
        self.play(LaggedStart(*[FadeIn(b, shift=DOWN * u(10)) for b in boxes], lag_ratio=0.2), run_time=1.0)

        self.at("box", -0.1)
        alph = boxes[1]
        gray = np.repeat(alpha[..., None], 3, axis=2)
        apl = png_mob(gray, ILL_H).move_to(px(*ILL_C)).set_opacity(0)
        ghost = png_mob(P, ILL_H).move_to(px(*ILL_C))
        ghost.check_ignore = True
        self.add(apl, ghost)
        lab_a = jp("透明度", 32, YELLOW).move_to(px(ALP_C[0], ALP_C[1] + ILL_H / 2 + 30))
        self.play(alph[0].animate.set_stroke(YELLOW, 5), alph[1].animate.set_color(YELLOW), run_time=0.4)
        self.play(apl.animate.move_to(px(*ALP_C)).set_opacity(1), ghost.animate.move_to(px(*ALP_C)).set_opacity(0),
                  FadeIn(lab_a, shift=UP * u(6)), run_time=1.4)
        self.remove(ghost)

        # ================= ふちは、くっきり =================
        self.at("sharp", -0.1)
        cx, cy, cw, chh = CROP
        sq = Rectangle(width=ill.height / P.shape[0] * cw, height=ill.height / P.shape[0] * chh,
                       stroke_color=YELLOW, stroke_width=4)
        sq.move_to((at_px(ill, P.shape, cx, cy) + at_px(ill, P.shape, cx + cw, cy + chh)) / 2)
        crop = png_mob(P[cy:cy + chh, cx:cx + cw], 440, cell_px=37, nearest=True).move_to(px(ALP_C[0], 500))
        frame = Rectangle(width=crop.width, height=crop.height, stroke_color=YELLOW, stroke_width=4).move_to(crop)
        links = VGroup(DashedLine(sq.get_corner(UR), frame.get_corner(UL), color=YELLOW, stroke_width=2),
                       DashedLine(sq.get_corner(DR), frame.get_corner(DL), color=YELLOW, stroke_width=2))
        links.set_opacity(0.6)
        self.play(apl.animate.set_opacity(0), FadeOut(lab_a), Create(sq), run_time=0.6)
        self.remove(apl)
        crop.check_ignore = True
        self.play(FadeIn(crop, scale=0.6), Create(frame), Create(links), run_time=0.9)

        # ================= 動き：スタンプ =================
        self.at("s09_04", -0.15)
        self.play(ill.animate.set_opacity(0), crop.animate.set_opacity(0), FadeOut(VGroup(boxes, sq, frame, links)),
                  run_time=0.5)
        self.remove(ill, crop)
        stamp = [png_mob(c, STAGE_H, nearest=True).move_to(px(*STAGE_C)) for c in canv]
        for m in stamp[1:]:
            m.set_opacity(0)
        self.add(*stamp[1:])
        self.at("anim", -0.1)
        self.play(FadeIn(stamp[0], shift=UP * u(12)), run_time=0.8)

        self.at("stamp", -0.1)
        player = Player(stamp, durs)
        holder = VGroup()
        holder.add_updater(player)
        self.add(holder)

        # 大きさの棒
        self.at("size", -0.1)
        BX, BW = 950, 500
        bars, labs = VGroup(), VGroup()
        for k, (name, s, col) in enumerate([("GIF", g_sz, DIM), ("WebP", w_sz, BLUE)]):
            y = 300 + 190 * k
            labs.add(mix(f"{name}　{fmt(s)} バイト", 36, INK if k else DIM).move_to(px(BX, y), aligned_edge=LEFT))
            bars.add(Rectangle(width=u(BW * s / g_sz), height=u(44), stroke_width=0, fill_color=col,
                               fill_opacity=1).move_to(px(BX, y + 66), aligned_edge=LEFT))
        self.play(FadeIn(labs), GrowFromEdge(bars[0], LEFT), GrowFromEdge(bars[1], LEFT), run_time=0.9)
        gap = Rectangle(width=bars[0].width - bars[1].width, height=u(44), stroke_width=0, fill_color=YELLOW,
                        fill_opacity=0.35).move_to(bars[1].get_right(), aligned_edge=LEFT)
        self.play(FadeIn(gap), run_time=0.6)

        # ================= 2 コマ目：変わったところの四角 =================
        self.at("rect", -0.4)
        holder.clear_updaters()
        self.remove(holder)
        player.show(0)
        self.play(FadeOut(VGroup(labs, bars, gap)), run_time=0.4)
        st = stamp[0]
        s_st = st.height / CH
        rbox = Rectangle(width=RW * s_st, height=RH * s_st, stroke_color=YELLOW, stroke_width=4)
        rbox.move_to((at_px(st, (CH, CW), L, T) + at_px(st, (CH, CW), L + RW, T + RH)) / 2)
        full = canv[1][T:T + RH, L:L + RW]                          # 四角の中を全部書いたとき
        p_full = png_mob(full, PATCH_H, cell_px=16).move_to(px(*PATCH_C))
        p_clr = png_mob(f1["rgba"], PATCH_H, cell_px=16).move_to(px(*PATCH_C))
        pfr = Rectangle(width=p_full.width, height=p_full.height, stroke_color=YELLOW, stroke_width=4).move_to(p_full)
        for m in (p_full, p_clr):
            m.check_ignore = True
        self.play(Create(rbox), run_time=0.5)
        src = p_full.copy().replace(rbox, stretch=True)
        self.add(src)
        self.play(src.animate.replace(p_full, stretch=True), ReplacementTransform(rbox.copy(), pfr), run_time=0.9)
        self.add(p_full, pfr)
        self.remove(src)
        t_n = mix(f"{RW}×{RH} ＝ {fmt(RW * RH)} 点", 40, INK).move_to(px(PATCH_C[0], 500))
        self.play(FadeIn(t_n, shift=UP * u(8)), run_time=0.6)

        # ---- 変わっていない点を透明に ----
        self.at("clear", -0.1)
        ov_c = img(mask_img(clear, (239, 111, 94, 200)), PATCH_H).move_to(p_full)
        ov_c.check_ignore = True
        t_c = mix(f"変わっていない {fmt(int(clear.sum()))} 点", 36, CORAL).move_to(px(PATCH_C[0], 580))
        self.play(FadeIn(ov_c), FadeIn(t_c, shift=UP * u(8)), run_time=0.7)
        self.wait(1.5)
        p_clr.set_opacity(0)
        self.add(p_clr)
        self.bring_to_front(ov_c, pfr)
        self.play(p_full.animate.set_opacity(0), p_clr.animate.set_opacity(1), ov_c.animate.set_opacity(0),
                  run_time=1.0)
        self.remove(p_full, ov_c)

        # ---- 前のコマを透かす ----
        self.at("through", -0.1)
        fly = png_mob(f1["rgba"], PATCH_H, cell_px=16).move_to(p_clr)
        raw = img(f1["rgba"], 50).replace(rbox, stretch=True)
        fly.check_ignore = raw.check_ignore = True
        self.add(fly)
        self.play(fly.animate.replace(rbox, stretch=True), run_time=1.0)
        self.add(raw)
        self.bring_to_front(fly, rbox)
        self.play(fly.animate.set_opacity(0), run_time=0.9)
        self.remove(fly)
        self.play(pop(rbox, 1.15, 0.6), run_time=0.6)

        # ---- 本当に変わった点だけ ----
        self.at("only", -0.1)
        ov_d = img(mask_img(~clear, (242, 193, 78, 170)), PATCH_H).move_to(p_clr)
        ov_d.check_ignore = True
        t_d = mix(f"書いたのは {fmt(int((~clear).sum()))} 点", 40, YELLOW).move_to(px(PATCH_C[0], 670))
        self.play(FadeIn(ov_d), FadeIn(t_d, shift=UP * u(8)), run_time=0.7)
        self.play(pop(t_d, 1.12, 0.6), run_time=0.6)

        # ================= 1 コマ 1 コマが普通の WebP =================
        self.at("each", -0.3)
        self.play(st.animate.set_opacity(0), raw.animate.set_opacity(0), p_clr.animate.set_opacity(0),
                  ov_d.animate.set_opacity(0), FadeOut(VGroup(rbox, pfr, t_n, t_c, t_d)), run_time=0.6)
        self.remove(*stamp, raw, p_clr, ov_d)
        thumbs, outlines, tags = Group(), VGroup(), VGroup()
        sc = THUMB_H / CH            # 画面の px / 画像の点
        for k, fr in enumerate(frames):
            x = 960 + STEP * (k - (n - 1) / 2)
            dimc = canv[k].copy()
            dimc[..., :3] = (dimc[..., :3] * 0.45).astype(np.uint8)
            t = png_mob(dimc, THUMB_H, cell_px=10).move_to(px(x, THUMB_Y))
            o = Rectangle(width=u(fr["width"] * sc), height=u(fr["height"] * sc), stroke_color=YELLOW, stroke_width=3)
            o.move_to(t.get_corner(UL) + RIGHT * u(sc * (fr["x"] + fr["width"] / 2))
                      + DOWN * u(sc * (fr["y"] + fr["height"] / 2)))
            t.check_ignore = True
            thumbs.add(t)
            outlines.add(o)
            tags.add(mono(wf[k]["chunks"][0][0], 26, BLUE).move_to(px(x, 315)))
        self.play(LaggedStart(*[FadeIn(Group(t, o), shift=UP * u(10)) for t, o in zip(thumbs, outlines)],
                              lag_ratio=0.1), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(t, shift=DOWN * u(6)) for t in tags], lag_ratio=0.08), run_time=0.9)

        # ---- 色の数・半透明：GIF (左) と WebP (右) を並べる ----
        def compare(cue, g_txt, w_txt, y):
            self.at(cue, -0.1)
            g = mix(g_txt, 40, DIM).move_to(px(450, y), aligned_edge=LEFT)
            ar = jp("→", 40, DIM).move_to(px(905, y))
            w = mix(w_txt, 40, INK).move_to(px(960, y), aligned_edge=LEFT)
            self.play(FadeIn(g, shift=UP * u(8)), run_time=0.5)
            self.wait(1.1)
            self.play(FadeIn(ar), FadeIn(w, shift=LEFT * u(12)), run_time=0.6)
            return VGroup(g, ar, w), w

        row_c, c_w = compare("color", "GIF：256 色まで", "WebP：色の数の制限なし", 400)
        row_h, h_w = compare("half", "GIF：透明か不透明か", "WebP：半透明も", 480)

        # ---- コマごとに選べる (例の図) ----
        self.at("mix", 0.45)
        cat = pixels("cat")
        face = canv[0][20:130, 35:145]
        kinds = ["VP8", "VP8L", "VP8", "VP8L"]
        cards, cframes, ctags = Group(), VGroup(), VGroup()
        ex = jp("たとえば", 30, DIM).move_to(px(560, 590), aligned_edge=LEFT)
        for i, kd in enumerate(kinds):
            x = 650 + 200 * i
            if kd == "VP8":
                c0 = 60 + 120 * i
                im = png_mob(cat[60:200, c0:c0 + 140], 180).move_to(px(x, 730))
            else:
                im = png_mob(face, 180, cell_px=10).move_to(px(x, 730))
            im.check_ignore = True
            cards.add(im)
            cframes.add(Rectangle(width=im.width, height=im.height, stroke_color=DIM, stroke_width=2).move_to(im))
            ctags.add(mono(kd, 28, CORAL if kd == "VP8" else BLUE).move_to(px(x, 848)))
        self.play(FadeIn(ex), LaggedStart(*[FadeIn(Group(c, f), shift=UP * u(8)) for c, f in zip(cards, cframes)],
                                          lag_ratio=0.12), run_time=1.2)
        self.at("choose", -0.1)
        self.play(LaggedStart(*[AnimationGroup(FadeIn(t, shift=DOWN * u(6)),
                                               f.animate.set_stroke(CORAL if kd == "VP8" else BLUE, 4))
                                for t, f, kd in zip(ctags, cframes, kinds)], lag_ratio=0.15), run_time=1.3)

        # ---- GIF の弱点がなくなった ----
        self.at("weak", -0.1)
        self.play(pop(c_w, 1.1, 0.6), run_time=0.6)
        self.play(pop(h_w, 1.1, 0.6), run_time=0.6)

        self.at(self.tl["duration"] - 0.9)
        self.play(*[m.animate.set_opacity(0) for m in (*thumbs, *cards)],
                  FadeOut(VGroup(outlines, tags, row_c, row_h, ex, cframes, ctags)), run_time=0.7)
        self.remove(*thumbs, *cards)
        self.finish()
