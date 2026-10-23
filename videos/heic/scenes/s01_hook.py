import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import fmt, mean_abs_err, pixels, size  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

KEYS = ("jpg", "webp", "heic")
FILES = {"jpg": "cat_q80.jpg", "webp": "cat_q80.webp", "heic": "cat_q45"}
NAMES = {"jpg": "JPEG", "webp": "WebP", "heic": "HEIC"}
COLS = {"jpg": DIM, "webp": "#aab1c0", "heic": YELLOW}

# ---- スマホとパソコン ----
PHONE_C, PHONE_W, PHONE_H, PHONE_PH = (960, 360), 820, 560, 700      # 最初の大きいスマホ (写真の幅 700)
PHONE_C2, PHONE_K = (652, 290), 0.56                                 # パソコンの横に寄ったスマホ
PC_C, PC_W, PC_H = (1195, 300), 568, 400
# ---- 3 枚の写真と棒 ----
PH_X, PH_Y, PH_W = (420, 960, 1500), 178, 451
TAG_Y, ERR_Y = 368, 422
ROW_Y = {"jpg": 580, "webp": 700, "heic": 820}
LAB_X, BAR_X, BAR_MAX, BAR_H = 460, 600, 560, 52


def left_at(m, x, y):
    return m.move_to(px(x, y), aligned_edge=LEFT).set_y(px(0, y)[1])


class S01(PScene):
    def construct(self):
        # ---- 台詞の数字 ----
        n = {k: size(FILES[k]) for k in KEYS}
        assert (n["jpg"], n["webp"], n["heic"]) == (23693, 16974, 13368)
        err = {k: f"{mean_abs_err(FILES[k]):.1f}" for k in KEYS}
        assert (err["jpg"], err["webp"], err["heic"]) == ("2.6", "2.7", "2.6")      # 元とのずれが同じくらい
        assert n["heic"] < n["jpg"] * 0.6                                         # JPEG の 6 割もない
        assert 0.18 < 1 - n["heic"] / n["webp"] < 0.25                            # WebP よりさらに 2 割小さい
        photos = {k: pixels(FILES[k]) for k in KEYS}
        assert all(p.shape[:2] == (300, 451) for p in photos.values())

        def photo(k, w):
            m = png_mob(photos[k], w * 300 / 451, nearest=True)
            m.check_ignore = True          # 上に札を重ねる下敷き
            return m

        # ---- スマホで撮った猫 ----
        self.at("photo", -0.2)
        phone = RoundedRectangle(corner_radius=u(48), width=u(PHONE_W), height=u(PHONE_H), stroke_color="#596075",
                                 stroke_width=6, fill_color="#0c0d11", fill_opacity=1).move_to(px(*PHONE_C))
        cam = Circle(radius=u(9), stroke_width=0, fill_color="#2c303b", fill_opacity=1)
        cam.move_to(px(PHONE_C[0] + PHONE_W / 2 - 30, PHONE_C[1]))
        phone_g = VGroup(phone, cam)
        ph = photo("heic", PHONE_PH).move_to(px(*PHONE_C))
        self.play(FadeIn(phone_g, scale=0.92), FadeIn(ph, scale=0.92), run_time=0.9)

        # ---- パソコンに送る ----
        self.at("pc", -0.1)
        mon = RoundedRectangle(corner_radius=u(16), width=u(PC_W), height=u(PC_H), stroke_color="#596075",
                               stroke_width=6, fill_color="#1c1f27", fill_opacity=1).move_to(px(*PC_C))
        neck = Rectangle(width=u(40), height=u(26), stroke_width=0, fill_color="#596075", fill_opacity=1)
        neck.move_to(px(PC_C[0], PC_C[1] + PC_H / 2 + 13))
        base = RoundedRectangle(corner_radius=u(6), width=u(200), height=u(12), stroke_width=0, fill_color="#596075",
                                fill_opacity=1).move_to(px(PC_C[0], PC_C[1] + PC_H / 2 + 30))
        pc = VGroup(mon, neck, base)
        sent = photo("heic", PHONE_PH).move_to(px(*PHONE_C))
        self.add(sent)
        k = PHONE_K
        card_c = (PC_C[0], PC_C[1] - 30)
        self.play(phone_g.animate.scale(k).move_to(px(*PHONE_C2)), ph.animate.scale(k).move_to(px(*PHONE_C2)),
                  sent.animate(path_arc=-0.7).scale(300 / PHONE_PH).move_to(px(*card_c)), FadeIn(pc, shift=LEFT * u(30)),
                  run_time=1.1)

        # ---- 開けない ----
        self.at("name", -0.1)
        card = RoundedRectangle(corner_radius=u(14), width=u(300), height=u(200), stroke_width=0,
                                fill_color="#3a3f4c", fill_opacity=1).move_to(px(*card_c))
        qm = jp("？", 110, DIM).move_to(card)
        fname = jp("cat.heic", 44, INK).move_to(px(PC_C[0], PC_C[1] + 132))
        self.play(sent.animate.set_opacity(0), FadeIn(card), FadeIn(qm, scale=0.7), FadeIn(fname, shift=UP * u(8)),
                  run_time=0.6)
        self.remove(sent)
        win = VGroup(pc, card, qm, fname)
        self.play(Shake(win, amp=12, run_time=0.6))

        # ---- .heic ----
        self.at("heic", -0.1)
        ul = underline(VGroup(*fname[3:]), YELLOW)
        self.play(Create(ul), retext(fname, jp("cat.heic", 44, INK, t2c={".heic": YELLOW})), run_time=0.5)
        self.at("iphone", 0.0)
        self.play(pop(Group(phone_g, ph), 1.06, 0.7), run_time=0.7)

        # Z「どうして JPEG じゃないのだ？」：開けなかった「？」
        self.at("why", 0.0)
        self.play(pop(qm, 1.25, 0.7), run_time=0.7)

        # ---- 3 つの形式で保存：写真が 3 枚に分かれる ----
        self.at("three", -0.1)
        pics = {kk: photo(kk, PH_W).scale(PHONE_PH * PHONE_K / PH_W).move_to(px(*PHONE_C2)) for kk in ("jpg", "webp")}
        self.add(pics["jpg"], pics["webp"])
        self.bring_to_front(ph)
        pics["heic"] = ph
        tags = {kk: jp(NAMES[kk], 40, COLS[kk] if kk != "jpg" else INK).move_to(px(PH_X[i], TAG_Y))
                for i, kk in enumerate(KEYS)}
        self.play(*[pics[kk].animate.set(width=u(PH_W)).move_to(px(PH_X[i], PH_Y)) for i, kk in enumerate(KEYS)],
                  FadeOut(phone_g), FadeOut(VGroup(pc, card, qm, ul), shift=RIGHT * u(30)),
                  ReplacementTransform(fname, tags["heic"]),
                  FadeIn(tags["jpg"], shift=UP * u(8)), FadeIn(tags["webp"], shift=UP * u(8)), run_time=1.3)

        # ---- 元とのずれ ----
        self.at("same", -0.1)
        errs = {kk: jp(f"元とのずれ {err[kk]}", 32, INK, t2c={err[kk]: CORAL}).move_to(px(PH_X[i], ERR_Y))
                for i, kk in enumerate(KEYS)}
        self.play(LaggedStart(*[FadeIn(errs[kk], shift=UP * u(8)) for kk in KEYS], lag_ratio=0.25), run_time=1.0)

        # ---- 大きさ：数字が出て、そのまま棒になる ----
        self.at("size", -0.1)
        labs = {kk: left_at(jp(NAMES[kk], 40, COLS[kk] if kk != "jpg" else INK), LAB_X, ROW_Y[kk]) for kk in KEYS}
        nums = {kk: left_at(jp(f"{fmt(n[kk])} バイト", 40, COLS[kk] if kk != "jpg" else INK), BAR_X, ROW_Y[kk])
                for kk in KEYS}
        self.play(*[TransformFromCopy(tags[kk], labs[kk], path_arc=0.4) for kk in KEYS],
                  LaggedStart(*[FadeIn(nums[kk], shift=UP * u(8)) for kk in KEYS], lag_ratio=0.2), run_time=1.0)
        self.wait(0.5)

        def bar_w(kk):
            return BAR_MAX * n[kk] / n["jpg"]
        bars = {kk: Rectangle(width=u(bar_w(kk)), height=u(BAR_H), stroke_width=0, fill_color=COLS[kk],
                              fill_opacity=1).move_to(px(BAR_X, ROW_Y[kk]), aligned_edge=LEFT) for kk in KEYS}
        anims = []
        for kk in KEYS:
            cp = nums[kk].copy()
            cp.check_ignore = True
            anims += [ReplacementTransform(cp, bars[kk]),
                      nums[kk].animate.move_to(px(BAR_X + bar_w(kk) + 24, ROW_Y[kk]), aligned_edge=LEFT)]
        self.play(*anims, run_time=1.2)

        # ---- HEIC がいちばん小さい ----
        self.at("small", -0.1)
        self.play(pop(VGroup(labs["heic"], bars["heic"], nums["heic"]), 1.08, 0.7), run_time=0.7)

        # ---- JPEG の 6 割 ----
        self.at("half", -0.1)
        x6 = BAR_X + BAR_MAX * 0.6
        tick = DashedLine(px(x6, ROW_Y["jpg"] - BAR_H / 2 - 8), px(x6, ROW_Y["heic"] + BAR_H / 2 + 8),
                          dash_length=u(10), stroke_color=INK, stroke_width=3)
        t6 = jp("6割", 34, INK).move_to(px(x6, ROW_Y["jpg"] - BAR_H / 2 - 34))
        self.play(Create(tick), FadeIn(t6, shift=DOWN * u(6)), run_time=0.7)
        self.play(pop(bars["heic"], 1.05, 0.6), run_time=0.6)

        # ---- WebP と比べても 2 割小さい ----
        self.at("webp", -0.1)
        self.play(FadeOut(VGroup(tick, t6)), pop(VGroup(labs["webp"], bars["webp"], nums["webp"]), 1.08, 0.7),
                  run_time=0.7)
        self.at("less", -0.1)
        xw, xh = BAR_X + bar_w("webp"), BAR_X + bar_w("heic")
        guide = DashedLine(px(xw, ROW_Y["webp"] - BAR_H / 2), px(xw, ROW_Y["heic"] + BAR_H / 2), dash_length=u(8),
                           stroke_color=COLS["webp"], stroke_width=3)
        gap = Rectangle(width=u(xw - xh), height=u(BAR_H), stroke_width=0, fill_color=YELLOW,
                        fill_opacity=0.4).move_to(px(xh, ROW_Y["heic"]), aligned_edge=LEFT)
        gap.check_ignore = True    # 数字の下に敷く (差の部分)
        self.bring_to_front(nums["heic"])
        self.play(Create(guide), GrowFromEdge(gap, LEFT), run_time=0.7)
        self.play(gap.animate.set_fill(opacity=0.18), run_time=0.6)

        # ---- 動画の技術 ----
        self.at("video", 0.0)
        self.play(pop(VGroup(tags["webp"]), 1.2, 0.7), run_time=0.7)
        self.at("diff", 0.0)
        self.play(pop(VGroup(tags["heic"]), 1.2, 0.7), run_time=0.7)
        self.at("new", 0.0)
        self.play(pop(pics["heic"], 1.05, 0.7), run_time=0.7)

        # 開けなかった理由：HEIC の写真に「？」
        self.at("reason", -0.1)
        bc = (PH_X[2] + PH_W / 2 - 46, PH_Y - 150 + 46)
        badge = Circle(radius=u(34), stroke_width=0, fill_color=CORAL, fill_opacity=1).move_to(px(*bc))
        bq = jp("？", 44, BG).move_to(badge)
        self.play(FadeIn(badge, scale=0.4), FadeIn(bq, scale=0.4), run_time=0.6)

        # ---- 並んだものが縮んで消え、タイトル ----
        self.at("title", -0.2)
        title = jp("HEICの中身をのぞく", 72).move_to(px(960, 300))
        c = px(960, 300)
        vm = VGroup(*tags.values(), *errs.values(), *labs.values(), *bars.values(), *nums.values(), guide, gap, badge, bq)
        self.play(*[pics[kk].animate.scale(0.3).move_to(c).set_opacity(0) for kk in KEYS],
                  FadeOut(vm, target_position=c, scale=0.3), FadeIn(title, scale=0.9), run_time=1.0)
        self.remove(*pics.values(), vm, *vm)
        self.finish()
