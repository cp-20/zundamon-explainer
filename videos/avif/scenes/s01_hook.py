import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import MAIN, fmt, mean_abs_err, pixels, size  # noqa: E402
from vlib.ui import CARD_ROWS, HEIC_COL  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

KEYS = ("jpg", "webp", "heic", "avif")
FILES = {"jpg": "cat_q80.jpg", "webp": "cat_q80.webp", "heic": "cat_q45.heic", "avif": MAIN}
NAMES = {"jpg": "JPEG", "webp": "WebP", "heic": "HEIC", "avif": "AVIF"}
COLS = {"jpg": DIM, "webp": "#aab1c0", "heic": HEIC_COL, "avif": YELLOW}

# ---- パソコンの画面 (HEIC 編の S01 と同じ見た目) ----
MON_C, MON_W, MON_H, BAR_H = (960, 352), 900, 580, 58
MON_TOP = MON_C[1] - MON_H / 2
CONTENT_C = (MON_C[0], (MON_TOP + BAR_H + MON_C[1] + MON_H / 2) / 2)
SHOT_H = 492                                     # 画面に映った写真の高さ
MON_C2, MON_K = (240, 200), 0.36                 # 縮んで左上へ (幅 324px)
# ---- 左の写真 ----
PIC_C, PIC_W = (270, 250), 400
# ---- ブラウザの名前 ----
BR_X, BR_Y, YEAR_Y = (640, 960, 1280), 760, 818
# ---- 棒 ----
ROW_Y = {"jpg": 400, "webp": 515, "heic": 630, "avif": 745}
LAB_X, BAR_X, BAR_MAX, BAR_H2 = 460, 650, 560, 56
# ---- 会社の輪 ----
RING_C, RING_RX, RING_RY = (960, 505), 390, 232
FOUNDERS = ("Google", "Netflix", "Microsoft", "Amazon", "Cisco", "Intel", "Mozilla")   # AOMedia の設立時の会員 (2015 年)
SPOKEN = 3                                       # 台詞で名前を言う会社 (先に集まる)
# ---- AV1 から 2 つへ ----
AV1_C, AV1_C2 = (960, 200), (1225, 470)
SUB_X, SUB_Y, SUB_W = (700, 1220), 520, 400
HEVC_C = (695, 470)
AV1_C3 = (960, 150)                              # 工夫を並べるとき、AV1 の札は上へ
TOOL_X, TOOL_Y0, TOOL_DY, TOOL_W = (750, 1170), 330, 112, 380   # 工夫の札 (左に 4 つ、右に 3 つ)

BROWSERS = (("Chrome", 2020), ("Firefox", 2021), ("Safari", 2022))     # AVIF に対応した年 (Chrome 85・Firefox 93・Safari 16)
AOM_YEAR = 2015


def left_at(m, x, y):
    return m.move_to(px(x, y), aligned_edge=LEFT).set_y(px(0, y)[1])


def card_box(c, w, h, col, fill="#1c1f27", sw=4):
    return RoundedRectangle(corner_radius=u(18), width=u(w), height=u(h), stroke_color=col, stroke_width=sw,
                            fill_color=fill, fill_opacity=1).move_to(px(*c))


class S01(PScene):
    def construct(self):
        # ---- 台詞の数字 ----
        n = {k: size(FILES[k]) for k in KEYS}
        assert (n["jpg"], n["webp"], n["heic"], n["avif"]) == (23693, 16974, 13368, 13179)
        assert n["heic"] - n["avif"] == 189
        err = {k: mean_abs_err(FILES[k]) for k in KEYS}
        assert [f"{err[k]:.2f}" for k in KEYS] == ["2.61", "2.72", "2.65", "2.69"]
        assert max(err.values()) - min(err.values()) < 0.15                          # 元とのずれが同じくらい
        photo = pixels(MAIN)
        assert photo.shape[:2] == (300, 451)

        def pic(h):
            m = png_mob(photo, h, nearest=False)
            m.check_ignore = True          # 上に札や枠を重ねる下敷き
            return m

        # ---- パソコンで開けない HEIC ----
        self.at("pc", -0.1)
        mon = RoundedRectangle(corner_radius=u(16), width=u(MON_W), height=u(MON_H), stroke_color="#596075",
                               stroke_width=6, fill_color="#1c1f27", fill_opacity=1).move_to(px(*MON_C))
        neck = Rectangle(width=u(44), height=u(30), stroke_width=0, fill_color="#596075", fill_opacity=1)
        neck.move_to(px(MON_C[0], MON_C[1] + MON_H / 2 + 15))
        base = RoundedRectangle(corner_radius=u(6), width=u(220), height=u(14), stroke_width=0, fill_color="#596075",
                                fill_opacity=1).move_to(px(MON_C[0], MON_C[1] + MON_H / 2 + 36))
        # 窓の上の帯 (ファイルを見るソフト：左に丸が 3 つ)
        bar = Rectangle(width=u(MON_W - 12), height=u(BAR_H), stroke_width=0, fill_color="#2a2e39", fill_opacity=1)
        bar.move_to(px(MON_C[0], MON_TOP + 6 + BAR_H / 2))
        dots = VGroup(*[Circle(radius=u(9), stroke_width=0, fill_color=c, fill_opacity=1)
                        .move_to(px(MON_C[0] - MON_W / 2 + 40 + 30 * i, MON_TOP + 6 + BAR_H / 2))
                        for i, c in enumerate(("#ff6b6b", "#f0c05a", "#5ccf7a"))])
        pc = VGroup(mon, neck, base, bar, dots)
        card_c = (CONTENT_C[0], CONTENT_C[1] - 30)
        card = RoundedRectangle(corner_radius=u(14), width=u(400), height=u(260), stroke_width=0,
                                fill_color="#3a3f4c", fill_opacity=1).move_to(px(*card_c))
        qm = jp("？", 130, DIM).move_to(card)
        fname_h = jp("cat.heic", 48, INK).move_to(px(CONTENT_C[0], card_c[1] + 185))
        self.play(FadeIn(pc, shift=LEFT * u(30)), run_time=0.8)
        self.play(FadeIn(card), FadeIn(qm, scale=0.7), FadeIn(fname_h, shift=UP * u(8)), run_time=0.6)
        self.at("still", -0.1)
        self.play(Shake(VGroup(pc, card, qm, fname_h), amp=12, run_time=0.6))

        # ---- AVIF で保存した写真 ----
        self.at("avif", -0.1)
        ph = pic(PIC_W * 300 / 451).move_to(px(*PIC_C))
        fname_a = jp("cat.avif", 44, INK, t2c={".avif": YELLOW}).move_to(px(PIC_C[0], PIC_C[1] + 170))
        self.play(FadeIn(ph, shift=RIGHT * u(20)), FadeIn(fname_a, shift=RIGHT * u(20)), run_time=0.8)

        # ---- ブラウザにドラッグ ----
        self.at("drop", -0.1)
        # 上の帯がブラウザのタブとアドレス欄の形に
        bar_y = MON_TOP + 6 + BAR_H / 2
        tab_l = MON_C[0] - MON_W / 2 + 20
        tab = RoundedRectangle(corner_radius=u(10), width=u(230), height=u(BAR_H - 8), stroke_width=0,
                               fill_color="#3a3f4c", fill_opacity=1).move_to(px(tab_l + 115, bar_y + 4))
        tab_t = jp("cat.avif", 28, INK).move_to(tab)
        addr = RoundedRectangle(corner_radius=u(14), width=u(400), height=u(30), stroke_width=0,
                                fill_color="#3a3f4c", fill_opacity=1).move_to(px(tab_l + 230 + 40 + 200, bar_y))
        shot = pic(SHOT_H).move_to(px(*CONTENT_C))
        self.add(shot.set_opacity(0))
        self.play(ph.animate(path_arc=-0.6).set(height=u(SHOT_H)).move_to(px(*CONTENT_C)),
                  ReplacementTransform(fname_a, tab_t, path_arc=-0.6),
                  FadeOut(VGroup(card, qm, fname_h), scale=0.8), FadeOut(dots), FadeIn(tab), FadeIn(addr),
                  run_time=1.2)
        self.remove(shot)
        browser = VGroup(tab, tab_t, addr)

        # ---- 開いた ----
        self.at("open", -0.1)
        self.play(pop(ph, 1.05, 0.7), run_time=0.7)

        # ---- 主なブラウザ ----
        self.at("all", 0.2)
        brs = []
        for (name, year), x in zip(BROWSERS, BR_X):
            brs.append(VGroup(jp(name, 44, INK).move_to(px(x, BR_Y)), mix(f"{year}年", 40, DIM).move_to(px(x, YEAR_Y))))
        self.play(LaggedStart(*[FadeIn(b, shift=UP * u(10)) for b in brs], lag_ratio=0.55), run_time=3.0)
        self.at("now", -0.1)
        self.play(LaggedStart(*[pop(b, 1.12, 0.6) for b in brs], lag_ratio=0.2), run_time=1.0)

        # Z「ファイルサイズは？」
        self.at("size", 0.0)
        self.play(pop(tab_t, 1.25, 0.7), run_time=0.7)

        # ---- 元とのずれが同じくらいに保存した 4 つ ----
        self.at("same", -0.1)
        browser.remove(tab_t)
        pcg = Group(pc, browser, ph)
        labs = {k: left_at(jp(NAMES[k], 40, COLS[k] if k != "jpg" else INK), LAB_X, ROW_Y[k] - 16) for k in KEYS}
        errs = {k: left_at(mix(f"ずれ {err[k]:.1f}", 30, DIM), LAB_X, ROW_Y[k] + 26) for k in KEYS}
        self.play(pcg.animate.scale(MON_K).move_to(px(*MON_C2)), FadeOut(VGroup(*brs), shift=DOWN * u(10)),
                  FadeOut(tab_t),
                  run_time=1.0)
        self.play(LaggedStart(*[FadeIn(VGroup(labs[k], errs[k]), shift=UP * u(8)) for k in KEYS], lag_ratio=0.25),
                  run_time=1.3)

        # ---- 大きさ：数字が出て、そのまま棒になる ----
        self.at("bars", -0.1)

        def bar_w(k):
            return BAR_MAX * n[k] / n["jpg"]
        nums = {k: left_at(mix(f"{fmt(n[k])} バイト", 38, COLS[k] if k != "jpg" else INK), BAR_X, ROW_Y[k]) for k in KEYS}
        self.play(LaggedStart(*[FadeIn(nums[k], shift=UP * u(8)) for k in KEYS], lag_ratio=0.15), run_time=0.7)
        bars = {k: Rectangle(width=u(bar_w(k)), height=u(BAR_H2), stroke_width=0, fill_color=COLS[k],
                             fill_opacity=1).move_to(px(BAR_X, ROW_Y[k]), aligned_edge=LEFT) for k in KEYS}
        anims = []
        for k in KEYS:
            cp = nums[k].copy()
            cp.check_ignore = True
            anims += [ReplacementTransform(cp, bars[k]),
                      nums[k].animate.move_to(px(BAR_X + bar_w(k) + 22, ROW_Y[k]), aligned_edge=LEFT)]
        self.play(*anims, run_time=1.1)

        # ---- HEIC とほとんど同じ ----
        self.at("tie", -0.1)
        xh = BAR_X + bar_w("heic")
        tick = DashedLine(px(xh, ROW_Y["heic"] - BAR_H2 / 2 - 10), px(xh, ROW_Y["avif"] + BAR_H2 / 2 + 10),
                          dash_length=u(9), stroke_color=INK, stroke_width=3)
        diff = mix(f"差 {n['heic'] - n['avif']} バイト", 34, INK).move_to(px(xh, ROW_Y["avif"] + BAR_H2 / 2 + 40))
        self.play(Create(tick), pop(VGroup(bars["heic"], bars["avif"]), 1.04, 0.7), run_time=0.7)
        self.play(FadeIn(diff, shift=UP * u(6)), run_time=0.5)

        # ---- 特許料 ----
        def fee_chip(text, col, k):
            t = mix(text, 30, col)
            box = RoundedRectangle(corner_radius=u(12), width=t.width + u(30), height=u(50), stroke_color=col,
                                   stroke_width=3, fill_color="#1c1f27", fill_opacity=1)
            g = VGroup(box, t.move_to(box))
            return g.move_to(nums[k].get_right() + RIGHT * (u(20) + g.width / 2))
        self.at("pay", -0.1)
        fee_a = fee_chip("特許料 0円", YELLOW, "avif")
        self.play(FadeOut(VGroup(tick, diff)), FadeIn(fee_a, shift=LEFT * u(14)), run_time=0.7)
        self.play(pop(fee_a, 1.12, 0.6), run_time=0.6)

        # Z「HEVC に特許があるから開けない」
        self.at("hevc", -0.1)
        fee_h = fee_chip("特許料", CORAL, "heic")
        self.play(FadeIn(fee_h, shift=LEFT * u(14)), run_time=0.6)

        # ---- 2015 年：会社が集まって AV1 ----
        self.at("aom", -0.1)
        gone = VGroup(*labs.values(), *errs.values(), *bars.values(), *nums.values(), fee_a, fee_h)
        year = mix(f"{AOM_YEAR}年", 48, INK).move_to(px(RING_C[0], 132))
        self.play(FadeOut(gone, shift=DOWN * u(20)), pc.animate.set_opacity(0), browser.animate.set_opacity(0),
                  ph.animate.set_opacity(0), run_time=0.8)
        self.remove(pcg, *pcg)
        self.play(FadeIn(year, shift=DOWN * u(10)), run_time=0.6)
        self.at("who", -0.1)
        names = []
        for i, nm in enumerate(FOUNDERS):
            a = PI / 2 - TAU * i / len(FOUNDERS)
            x, y = RING_C[0] + RING_RX * np.cos(a), RING_C[1] - RING_RY * np.sin(a)
            t = jp(nm, 38, INK)
            box = RoundedRectangle(corner_radius=u(14), width=t.width + u(36), height=u(64), stroke_color=DIM,
                                   stroke_width=3, fill_color="#1c1f27", fill_opacity=1)
            names.append(VGroup(box, t.move_to(box)).move_to(px(x, y)))
        out = [(t.get_center() - px(*RING_C)) * 0.45 for t in names]
        self.play(LaggedStart(*[FadeIn(t, shift=-o) for t, o in zip(names[:SPOKEN], out)], lag_ratio=0.6),
                  run_time=2.2)
        self.play(LaggedStart(*[FadeIn(t, shift=-o) for t, o in zip(names[SPOKEN:], out[SPOKEN:])], lag_ratio=0.2),
                  run_time=1.0)

        self.at("av1", -0.1)
        av1_box = card_box(RING_C, 380, 160, YELLOW)
        av1_t = jp("動画の規格", 40, INK).move_to(av1_box)
        self.play(GrowFromCenter(av1_box), FadeIn(av1_t), run_time=0.8)
        self.at("name", -0.1)
        self.play(retext(av1_t, mix("AV1", 84, YELLOW)), run_time=0.7)
        self.play(pop(VGroup(av1_box, av1_t), 1.1, 0.6), run_time=0.6)

        # ---- AVIF は AV1 で圧縮した画像 ----
        self.at("photo", -0.1)
        av1 = VGroup(av1_box, av1_t)
        self.play(FadeOut(VGroup(*names), scale=0.8), year.animate.set_opacity(0), av1.animate.move_to(px(*AV1_C)),
                  run_time=0.9)
        self.remove(year)
        sub_h = SUB_W * 300 / 451
        ph2 = pic(sub_h).move_to(px(SUB_X[0], SUB_Y))
        tag_a = jp("AVIF", 44, YELLOW).move_to(px(SUB_X[0], SUB_Y + sub_h / 2 + 40))
        arr_a = Arrow(px(AV1_C[0] - 120, AV1_C[1] + 86), px(SUB_X[0] + 40, SUB_Y - sub_h / 2 - 12), buff=0,
                      stroke_width=5, color=DIM, max_tip_length_to_length_ratio=0.18)
        self.play(GrowArrow(arr_a), FadeIn(ph2, shift=DOWN * u(20)), FadeIn(tag_a, shift=DOWN * u(20)), run_time=0.9)

        # Z「動画の形式？」
        self.at("video", 0.0)
        self.play(pop(av1, 1.1, 0.7), run_time=0.7)

        # ---- 動画の配信 ----
        self.at("yt", -0.1)
        scr = card_box((SUB_X[1], SUB_Y), SUB_W, sub_h, INK, fill="#0c0d11", sw=4)
        tri = Triangle(stroke_width=0, fill_color=INK, fill_opacity=1).scale(u(38)).rotate(-PI / 2)
        tri.move_to(px(SUB_X[1], SUB_Y - 10))
        prog = Line(px(SUB_X[1] - SUB_W / 2 + 30, SUB_Y + sub_h / 2 - 28),
                    px(SUB_X[1] + SUB_W / 2 - 30, SUB_Y + sub_h / 2 - 28), stroke_color="#3a3f4c", stroke_width=6)
        prog_on = Line(prog.get_start(), prog.point_from_proportion(0.38), stroke_color=CORAL, stroke_width=6)
        player = VGroup(scr, tri, prog, prog_on)
        tag_v = jp("YouTube・Netflix", 40, INK).move_to(px(SUB_X[1], SUB_Y + sub_h / 2 + 40))
        arr_v = Arrow(px(AV1_C[0] + 120, AV1_C[1] + 86), px(SUB_X[1] - 40, SUB_Y - sub_h / 2 - 12), buff=0,
                      stroke_width=5, color=DIM, max_tip_length_to_length_ratio=0.18)
        self.play(GrowArrow(arr_v), FadeIn(player, shift=DOWN * u(20)), FadeIn(tag_v, shift=DOWN * u(20)),
                  run_time=0.9)
        prog_full = Line(prog.point_from_proportion(0.38), prog.get_end(), stroke_color=CORAL, stroke_width=6)
        self.play(Create(prog_full, rate_func=linear), run_time=3.5)      # 動画が流れている

        # ---- 特許料のかかる技術を避けた ----
        self.at("avoid", -0.1)
        hevc_box = card_box(HEVC_C, 380, 160, HEIC_COL)
        hevc_t = mix("HEVC", 76, HEIC_COL).move_to(hevc_box)
        hevc = VGroup(hevc_box, hevc_t)
        fee = VGroup(RoundedRectangle(corner_radius=u(12), width=u(150), height=u(52), stroke_color=CORAL,
                                      stroke_width=3, fill_color="#1c1f27", fill_opacity=1))
        fee.add(mix("特許料", 30, CORAL).move_to(fee[0]))
        fee.move_to(px(HEVC_C[0], HEVC_C[1] + 128))
        self.play(FadeOut(VGroup(arr_a, arr_v, player, prog_full, tag_v, tag_a), shift=DOWN * u(20)),
                  ph2.animate.set_opacity(0), av1.animate.move_to(px(*AV1_C2)),
                  FadeIn(hevc, shift=RIGHT * u(30)), run_time=1.0)
        self.remove(ph2)
        self.play(FadeIn(fee, shift=UP * u(8)), run_time=0.6)

        # ---- 同じ仕組みは使えない ----
        self.at("nouse", -0.1)
        a0, a1 = px(HEVC_C[0] + 195, HEVC_C[1]), px(AV1_C2[0] - 195, AV1_C2[1])
        link = Arrow(a0, a1, buff=u(8), stroke_width=6, color=DIM, max_tip_length_to_length_ratio=0.2)
        mid = (a0 + a1) / 2
        cross = VGroup(Line(mid + u(26) * (UL), mid + u(26) * (DR), stroke_color=CORAL, stroke_width=9),
                       Line(mid + u(26) * (UR), mid + u(26) * (DL), stroke_color=CORAL, stroke_width=9))
        self.play(GrowArrow(link), run_time=0.7)
        self.play(Create(cross), run_time=0.5)

        # Z「同じくらい小さくできた？」
        self.at("how", -0.1)
        sz_h = mix(f"HEIC {fmt(n['heic'])} バイト", 40, HEIC_COL).move_to(px(HEVC_C[0], HEVC_C[1] + 230))
        sz_a = mix(f"AVIF {fmt(n['avif'])} バイト", 40, YELLOW).move_to(px(AV1_C2[0], AV1_C2[1] + 230))
        self.play(FadeIn(sz_h, shift=UP * u(8)), FadeIn(sz_a, shift=UP * u(8)), run_time=0.7)

        # ---- 別の工夫：これからのぞく 7 つ (比較表の項目) ----
        self.at("yes", 0.0)
        self.play(pop(VGroup(sz_h, sz_a), 1.08, 0.6), run_time=0.6)
        self.at("tools", -0.1)
        chips = VGroup()
        for k, (name, _, _) in enumerate(CARD_ROWS):
            col, row = (0, k) if k < 4 else (1, k - 4)
            c = (TOOL_X[col], TOOL_Y0 + row * TOOL_DY)
            box = RoundedRectangle(corner_radius=u(16), width=u(TOOL_W), height=u(74), stroke_color=YELLOW,
                                   stroke_width=3, fill_color="#1c1f27", fill_opacity=1).move_to(px(*c))
            chips.add(VGroup(box, jp(name, 38, INK).move_to(box)))
        self.play(FadeOut(VGroup(link, cross, fee, sz_h, sz_a, hevc)), av1.animate.scale(0.8).move_to(px(*AV1_C3)),
                  run_time=0.6)
        self.play(LaggedStart(*[FadeIn(ch, target_position=av1.get_center(), scale=0.4) for ch in chips],
                              lag_ratio=0.18), run_time=1.6)

        # ---- タイトル ----
        self.at("title", -0.1)
        title = jp("AVIFの中身をのぞく", 72).move_to(px(960, 300))
        c = px(960, 300)
        rest = VGroup(av1, chips)
        self.play(rest.animate.scale(0.3).move_to(c).set_opacity(0), FadeIn(title, scale=0.9), run_time=1.0)
        self.remove(rest, *rest)
        self.finish()
