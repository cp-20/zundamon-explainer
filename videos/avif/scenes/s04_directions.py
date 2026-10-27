import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import dec, picture_size, planes, rgb_decoded, source_yuv  # noqa: E402
import av1  # noqa: E402  (vlib.data が tools/ を探す場所に入れる)
import av1tables as T  # noqa: E402
from vlib.photoview import PhotoView, PLine, PRect, TrackFade, ViewAnim, move_view  # noqa: E402
from vlib.ui import HEIC_COL, add_row, compare_card  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

PHOTO = ((960, 386), 1040, 692)          # 写真の定位置 (S03 の終わり・S05 の始まり)
BX, BY, N = 208, 128, 16                 # 目の外側の輪郭の 16×16 (明るさ)
FAN_C = (900, 490)                       # 寄ったときのブロックの真ん中 (画面)
ZBOX = (FAN_C, 600, 600)
ZHALF = 15                               # 寄ったときの窓 (ブロックの真ん中から ±画素)
R0, R1 = 215, 385                        # 扇の矢印 (先 / 元) の半径
PANEL_X, PANEL_Y = 1690, (150, 235, 330)
SLOT_X, SLOT_Y, SLOT_W = (520, 960, 1400), 252, 400     # 予測 2 つと元 (上の帯いっぱい)
SWIN = (BX - 1, BY - 1, BX + N + 1, BY + N + 1)        # 並べるときの窓 (上の行と左の列も見せる)
LAB_Y, ERR_Y = 500, 572                  # 枠の下の角度 (矢印つき) とずれ
CNT_C, CNT_R0, CNT_R1 = (960, 520), 70, 450             # 使われた回数の扇
BASE = [45, 67, 90, 113, 135, 157, 180, 203]
MODE_OF = {a: m for m, a in enumerate(T.Mode_To_Angle) if 1 <= m <= 8}


def gray3(a):
    a = np.asarray(a, np.float32)
    return np.dstack([a, a, a])


def inward(c, ang, r_tail, r_tip, color, width, tip):
    """角度 ang (AV1 の度。90 が真上) の方向から、真ん中へ向かう矢印 (画素の流れる向き)"""
    v = np.array([np.cos(np.radians(ang)), np.sin(np.radians(ang)), 0.0])
    o = px(*c)
    return Arrow(o + v * u(r_tail), o + v * u(r_tip), buff=0, color=color, stroke_width=width, tip_length=u(tip),
                 max_tip_length_to_length_ratio=0.5, max_stroke_width_to_length_ratio=40)


def flow_arrow(center, ang, length=70, color=CYAN, width=9):
    v = -np.array([np.cos(np.radians(ang)), np.sin(np.radians(ang)), 0.0])
    o = px(*center)
    return Arrow(o - v * u(length / 2), o + v * u(length / 2), buff=0, color=color, stroke_width=width,
                 tip_length=u(26), max_tip_length_to_length_ratio=0.5, max_stroke_width_to_length_ratio=40)


class S04(PScene):
    def construct(self):
        W, H = picture_size()
        assert (W, H) == (451, 300)
        d = dec()
        b = next(b for b in d.blocks if (b["x"], b["y"]) == (BX, BY))
        assert (b["w"], b["h"], b["y_mode"], b["angle_delta_y"]) == (N, N, 1, 3)        # V (90°) ＋ 3 段
        assert T.Mode_To_Angle[1] == 90 and T.ANGLE_STEP == 3
        assert sorted(MODE_OF) == BASE
        t = next(t for t in d.txbs if t["plane"] == 0 and (t["x"], t["y"], t["w"], t["h"]) == (BX, BY, N, N))
        k = {}
        pred99 = d.intra_pred(t, k)
        assert k["p_angle"] == 99 and (pred99 == d.pred[0][BY:BY + N, BX:BX + N]).all()
        F = d.recon[0].astype(np.int64)
        preds = {}
        for dl in range(4):                     # 傾き 0〜3 段を作り直す
            p = dict(t["pred"])
            p["angle_delta"] = dl
            preds[dl] = av1.intra_predict(F, p).astype(np.float32)
        assert (preds[3] == pred99).all()
        src = source_yuv()[0]
        sblk = src[BY:BY + N, BX:BX + N]
        e90 = float(np.abs(sblk - preds[0]).mean())
        e99 = float(np.abs(sblk - preds[3]).mean())
        assert f"{e90:.1f}" == "14.1" and f"{e99:.1f}" == "5.9"
        assert (preds[0] == np.asarray(k["above"][1:N + 1])[None, :]).all()    # 真上：上の行をそのまま下へ
        used = Counter((bb["y_mode"], bb["angle_delta_y"]) for bb in d.blocks if 1 <= bb["y_mode"] <= 8)
        assert len(used) == 46 and 8 * 7 == 56
        top = max(used.values())
        # 元の明暗の境目 (明るさ 100 をまたぐ所) を行ごとに求め、直線を当てる
        xs = []
        for r in sblk:
            i = int(np.argmax(r >= 100))
            xs.append(i - 1 + (100 - r[i - 1]) / (r[i] - r[i - 1]) + 0.5)
        slope, icpt = np.polyfit(np.arange(N) + 0.5, xs, 1)
        assert 0.1 < slope < 0.3              # 右下へ少し斜め

        # ---- 写真 (S03 の終わり) ----
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        self.add(view)

        # ---- 目の外側の輪郭の 16×16 へ寄る ----
        self.at("s04_01", -0.05)
        cx, cy = BX + N / 2, BY + N / 2
        win = (cx - ZHALF, cy - ZHALF, cx + ZHALF, cy + ZHALF)
        lit = np.ones((H, W), np.float32)

        def dim(t):
            lit[:] = 1 - 0.5 * t
            lit[BY - 1:BY + N, BX - 1:BX + N] = 1
            view.lit = lit
        cur = PRect(view, BX, BY, N, N, stroke_color=YELLOW, stroke_width=5)
        cur.set_stroke(opacity=0)
        self.add(cur)
        self.play(move_view(view, win, ZBOX), ViewAnim(view, dim), TrackFade(cur, 0, 1), run_time=1.3)

        self.at("edge", -0.1)
        e_top = PRect(view, BX - 1, BY - 1, N + 1, 1, stroke_color=CYAN, stroke_width=4, fill_color=CYAN, fill_opacity=0.2)
        e_left = PRect(view, BX - 1, BY, 1, N, stroke_color=CYAN, stroke_width=4, fill_color=CYAN, fill_opacity=0.2)
        e_top.check_ignore = e_left.check_ignore = True
        blk = np.ones((N, N), np.float32)

        def dark(t):
            lit[BY:BY + N, BX:BX + N] = 1 - 0.8 * t * blk
            view.lit = lit
        self.play(ViewAnim(view, dark), GrowFromEdge(e_top, LEFT), GrowFromEdge(e_left, UP), run_time=0.9)
        self.play(Indicate(VGroup(e_top, e_left), color=CYAN, scale_factor=1.0), run_time=0.8)

        # ---- HEIC は 33 方向、AV1 はまず 8 方向 ----
        self.at("heic", -0.1)
        lab_h = mix("HEIC  33方向", 42, HEIC_COL).move_to(px(PANEL_X, PANEL_Y[0]))
        self.play(FadeIn(lab_h, shift=LEFT * u(10)), run_time=0.6)
        self.at("av1", -0.1)
        lab_a = mix("AV1  8方向", 42, YELLOW).move_to(px(PANEL_X, PANEL_Y[1]))
        self.play(FadeIn(lab_a, shift=LEFT * u(10)), run_time=0.6)
        self.at("rough", -0.1)
        base = {a: inward(FAN_C, a, R1, R0, YELLOW, 9, 26) for a in BASE}
        self.play(LaggedStart(*[GrowArrow(base[a]) for a in BASE], lag_ratio=0.12), run_time=1.4)

        # ---- 3 度ずつ、左右に 3 段 ----
        thin = {}
        for a in BASE:
            for dl in (-3, -2, -1, 1, 2, 3):
                thin[(a, dl)] = inward(FAN_C, a + 3 * dl, R1, R0, CYAN, 4, 16)
        self.at("tilt", -0.1)
        self.play(*[ReplacementTransform(base[90].copy().set_stroke(width=4), thin[(90, dl)]) for dl in (-3, -2, -1, 1, 2, 3)],
                  run_time=0.8)
        self.at("step", -0.1)
        arc = Arc(radius=u(R1 + 18), start_angle=np.radians(90), angle=np.radians(3), arc_center=px(*FAN_C),
                  stroke_color=INK, stroke_width=4)
        a_lab = mix("3°", 34, INK).move_to(px(FAN_C[0] - 22, FAN_C[1] - R1 - 52))
        self.play(Create(arc), FadeIn(a_lab), thin[(90, 1)].animate.set_color(YELLOW), run_time=0.6)
        self.at("three", -0.1)
        rest = [a for a in BASE if a != 90]
        self.play(*[ReplacementTransform(base[a].copy().set_stroke(width=4), thin[(a, dl)])
                    for a in rest for dl in (-3, -2, -1, 1, 2, 3)],
                  thin[(90, 1)].animate.set_color(CYAN), run_time=1.2)
        fan = VGroup(*[base[a] for a in BASE], *thin.values(), arc, a_lab)

        self.at("n56", -0.1)
        lab_n = mix("8 × 7 = 56通り", 42, YELLOW).move_to(px(PANEL_X, PANEL_Y[2]))
        self.play(FadeIn(lab_n, shift=UP * u(8)), run_time=0.6)
        self.play(pop(lab_n, 1.15, 0.6), run_time=0.6)

        # ---- このブロックで試す：明るさだけで比べる ----
        self.at("try", -0.1)
        rec = planes(stage="recon")[0]
        gbase = gray3(rec)
        gbase[BY:BY + N, BX:BX + N] = 30          # まだ作っていないブロックは暗く
        b0 = view.base.copy()
        labs = [mix("真上 90°", 40, INK).move_to(px(SLOT_X[0] + 60, LAB_Y)),
                mix("99°", 40, YELLOW).move_to(px(SLOT_X[1] + 28, LAB_Y)),
                mix("元", 40, INK).move_to(px(SLOT_X[2], LAB_Y))]

        def arrow_pos(lab):
            return ((lab.get_left()[0] / u(1)) + 960 - 44, LAB_Y)
        v_arrow = flow_arrow(arrow_pos(labs[0]), 90)

        def to_gray(t):
            view.base[:] = b0 * (1 - t) + gbase * t
        self.play(FadeOut(VGroup(*[m for m in fan if m is not base[90]])), FadeOut(VGroup(lab_h, lab_a, lab_n)),
                  run_time=0.6)
        lit[:] = np.where(lit < 1, lit, 1)
        lit0 = lit.copy()

        def undim(t):
            lit[:] = lit0 + (1 - lit0) * t
            view.lit = lit
        self.play(move_view(view, SWIN, ((SLOT_X[0], SLOT_Y), SLOT_W, SLOT_W)), ViewAnim(view, to_gray),
                  ViewAnim(view, undim), ReplacementTransform(base[90], v_arrow), run_time=1.3)
        view.base[:] = gbase

        # 真上：上の行の点が、そのまま下へ流れる
        self.at("up", -0.1)
        self.play(pop(v_arrow, 1.15, 0.6), Indicate(e_top, color=CYAN, scale_factor=1.0), run_time=0.7)
        self.at("stripe", -0.1)

        def fill(img, key, v, x0=BX, y0=BY):
            src0 = v.base[y0:y0 + N, x0:x0 + N].copy()
            l0 = lit[y0:y0 + N, x0:x0 + N].copy()

            def fn(t):
                m = np.clip((t * (1 + 3 / N) - key) * N / 3, 0, 1)
                v.base[y0:y0 + N, x0:x0 + N] = src0 * (1 - m[..., None]) + gray3(img) * m[..., None]
                lit[y0:y0 + N, x0:x0 + N] = l0 * (1 - m) + m
                v.lit = lit
            return ViewAnim(v, fn, rate_func=linear)
        Yk = np.repeat(np.arange(N)[:, None], N, 1) / N
        self.play(fill(preds[0], Yk, view), run_time=1.4)
        view.lit = None
        # 元を右に並べる
        orig = PhotoView(gray3(src), (SLOT_X[2], SLOT_Y), SLOT_W, SLOT_W, win=SWIN)
        orig.check_ignore = True
        o_cur = PRect(orig, BX, BY, N, N, stroke_color=YELLOW, stroke_width=5)
        orig.set_opacity(0)
        self.add(orig)
        self.play(orig.animate.set_opacity(1), Create(o_cur), FadeIn(labs[0]), FadeIn(labs[2]), run_time=0.8)

        # 元の境目は少し斜め
        self.at("slant", -0.1)
        sl = PLine(orig, (BX + icpt, BY), (BX + icpt + slope * N, BY + N), stroke_color=YELLOW, stroke_width=6)
        sl.check_ignore = True
        self.play(Create(sl), run_time=0.8)

        # ---- 右へ 3 段 (9°) 傾ける ----
        self.at("tilt3", -0.1)
        v2 = PhotoView(view.base.copy(), (SLOT_X[0], SLOT_Y), SLOT_W, SLOT_W, win=SWIN)
        v2.check_ignore = True
        c2 = PRect(v2, BX, BY, N, N, stroke_color=YELLOW, stroke_width=5)
        self.mobjects.insert(self.mobjects.index(view), v2)
        self.mobjects.insert(self.mobjects.index(view), c2)
        a2 = v_arrow.copy()
        self.add(a2)
        self.play(move_view(v2, SWIN, ((SLOT_X[1], SLOT_Y), SLOT_W, SLOT_W)), a2.animate.move_to(px(*arrow_pos(labs[1]))),
                  FadeIn(labs[1]), run_time=0.8)
        for dl in (1, 2, 3):
            frm = v2.base[BY:BY + N, BX:BX + N].copy()
            to = gray3(preds[dl])

            def morph(t, frm=frm, to=to):
                v2.base[BY:BY + N, BX:BX + N] = frm * (1 - t) + to * t
            self.play(Rotate(a2, angle=np.radians(3), about_point=a2.get_center()), ViewAnim(v2, morph), run_time=0.55)
        self.play(Indicate(labs[1], color=YELLOW, scale_factor=1.15), run_time=0.6)

        self.at("match", -0.1)
        self.play(pop(c2, 1.08, 0.6), pop(o_cur, 1.08, 0.6), run_time=0.6)

        # ---- 元とのずれ ----
        self.at("before", -0.1)
        err0 = mix(f"ずれ {e90:.1f}", 42, CORAL).move_to(px(SLOT_X[0] + 60, ERR_Y))
        self.play(FadeIn(err0, shift=UP * u(8)), run_time=0.6)
        self.at("after", -0.1)
        err1 = mix(f"ずれ {e99:.1f}", 42, YELLOW).move_to(px(SLOT_X[1] + 28, ERR_Y))
        self.play(FadeIn(err1, shift=UP * u(8)), run_time=0.6)
        self.play(pop(err1, 1.2, 0.7), run_time=0.7)

        # ---- 56 通りのうち、使われたもの ----
        self.at("count", -0.1)
        trio = VGroup(cur, c2, o_cur, sl, e_top, e_left, v_arrow, a2, *labs, err0, err1)
        self.play(FadeOut(trio), *[m.animate.set_opacity(0) for m in (view, v2, orig)], run_time=0.45)
        self.remove(view, v2, orig)
        angs = [(a, dl) for a in BASE for dl in range(-3, 4)]
        eq = VGroup(*[inward(CNT_C, a + 3 * dl, CNT_R0 + 90, CNT_R0, YELLOW if dl == 0 else CYAN, 6 if dl == 0 else 5, 14)
                      for a, dl in angs])
        hub = Square(u(64), stroke_color=INK, stroke_width=4).move_to(px(*CNT_C))
        self.play(FadeIn(hub), LaggedStart(*[GrowArrow(a) for a in eq], lag_ratio=0.01), run_time=0.6)
        self.at("used", -0.1)
        tgt = []
        for (a, dl), ar in zip(angs, eq):
            n = used.get((MODE_OF[a], dl), 0)
            if n:
                L = (CNT_R1 - CNT_R0) * n / top
                tgt.append(inward(CNT_C, a + 3 * dl, CNT_R0 + L, CNT_R0, ar.get_color(), 6 if dl == 0 else 5,
                                  min(16, 0.7 * L)))   # 長さは回数にそのまま比べる
            else:
                v = np.array([np.cos(np.radians(a + 3 * dl)), np.sin(np.radians(a + 3 * dl)), 0.0])
                tgt.append(Dot(px(*CNT_C) + v * u(CNT_R0 + 10), radius=u(8), color=CORAL))
        cnt = mix(f"使われた角度  {len(used)} / {len(angs)}", 40, YELLOW).move_to(px(1170, 640))
        self.play(*[Transform(a, b_) for a, b_ in zip(eq, tgt)], run_time=1.5)
        self.play(FadeIn(cnt, shift=UP * u(8)), run_time=0.6)

        # ---- 比較表 ----
        self.at("card", -0.1)
        view = PhotoView(rgb_decoded(), *PHOTO)
        view.check_ignore = True
        plit = np.full((H, W), 0.55, np.float32)
        view.lit = plit
        view.refresh()
        view.set_opacity(0)
        self.add(view)
        self.bring_to_front(eq, hub, cnt)
        card = compare_card(2, center=(960, 420), new=1)
        self.play(FadeOut(VGroup(eq, hub, cnt)), view.animate.set_opacity(1), run_time=0.5)
        self.play(FadeIn(card, shift=UP * u(30)), run_time=0.8)
        self.play(add_row(card), run_time=1.4)

        # 終わり：写真だけ (S05 の最初の画面)
        self.at(self.tl["duration"] - 1.3)

        def back(t):
            plit[:] = 0.55 + 0.45 * t
            view.lit = plit
        self.play(FadeOut(card), ViewAnim(view, back), run_time=1.0)
        view.lit = None
        self.finish()
