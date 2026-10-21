import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.catview import DIM_LIT, CatView, ViewAnim, gray_img, window_around, zoom  # noqa: E402
from vlib.data import (BMODE_NAME, MAIN_MB, MAIN_SB, big_preds, mb, sub_block, vp8_info, y_decoded,  # noqa: E402
                       y_orig, y_pred)
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

VIEW_C, VIEW_W, VIEW_H = (960, 340), 902, 600     # 明るさの画像の定位置 (S03 の終わりと同じ)
MX, MY = MAIN_MB
X0, Y0 = MX * 16, MY * 16
WIN_MB = window_around(X0 + 9.5, Y0 + 7.5, 19)    # 主役の MB と、その上の行・左の列・右上
CARD, CARD_C = 140, [(1610, 160), (1790, 160), (1610, 340), (1790, 340)]   # 16×16 の予想の札
ICON = 70
ICON_C = {"DC": (1575, 150), "TM": (1655, 150), "VE": (1735, 150), "HE": (1815, 150),
          "LD": (1615, 240), "VL": (1695, 240), "VR": (1775, 240),
          "RD": (1615, 330), "HD": (1695, 330), "HU": (1775, 330)}
# 予想の向き (画面の下向きが +y)。上の行から流れるもの・左の列から流れるもの
DIRS = {"VE": (0, 1), "HE": (1, 0), "LD": (-1, 1), "RD": (1, 1), "VR": (0.5, 1), "VL": (-0.5, 1),
        "HD": (1, 0.5), "HU": (1, -0.5)}
EQ_CELL = 72
EQ_C = {"orig": (590, 450), "pred": (960, 450), "diff": (1330, 450)}
SIDE_W = 600
SIDE_H = round(SIDE_W * 300 / 451)
SIDE_C = {"L": (640, 245), "R": (1280, 245)}


def lum(v):
    """明るさの値 → 塗る色"""
    g = float(np.clip(v, 0, 255)) / 255
    return rgb_to_color([g, g, g])


def num_color(v):
    return BG if v > 120 else INK


def glyph(mode, size=ICON, color=CYAN):
    """予想の向きの印。矢印、または「平均」「TM」の文字"""
    if mode == "DC":
        return jp("平均", 24, color)
    if mode == "TM":
        return jp("TM", 28, color)
    dx, dy = DIRS[mode]
    n = np.hypot(dx, dy)
    v = np.array([dx / n, -dy / n, 0]) * u(size * 0.62)
    return Arrow(-v / 2, v / 2, buff=0, color=color, stroke_width=6, max_tip_length_to_length_ratio=0.38,
                 max_stroke_width_to_length_ratio=12)


def icon(mode):
    box = RoundedRectangle(corner_radius=u(10), width=u(ICON), height=u(ICON), stroke_width=2, stroke_color=DIM,
                           fill_color="#232833", fill_opacity=1)
    g = glyph(mode).move_to(box)
    grp = VGroup(box, g).move_to(px(*ICON_C[mode]))
    grp.box, grp.g = box, g
    return grp


def cell_grid(vals, cell, center, colors=None, signed=False, size=34):
    """4×4 のマス。値で塗って数字を載せる。signed=True は差 (暗いマスに紫の数字)"""
    g = VGroup()
    for r in range(4):
        for c in range(4):
            v = int(vals[r][c])
            if signed:
                sq = Square(u(cell), stroke_width=2, stroke_color="#3a3f4c", fill_color="#232833", fill_opacity=1)
                t = mono(str(v).replace("-", "−"), size, PURPLE)
            else:
                sq = Square(u(cell), stroke_width=2, stroke_color="#2a2e38", fill_color=lum(v), fill_opacity=1)
                t = mono(str(v), size, num_color(v))
            sq.move_to(px(center[0] + (c - 1.5) * cell, center[1] + (r - 1.5) * cell))
            t.move_to(sq)
            g.add(VGroup(sq, t))
    return g


class S04(PScene):
    def construct(self):
        v8 = vp8_info()
        assert (v8["mbw"], v8["mbh"]) == (29, 19)
        Yo, Yd, PY = y_orig(), y_decoded(), y_pred()
        sb = sub_block()
        mode = BMODE_NAME[sb["mode"]]
        assert mode == "VR" and (sb["x"], sb["y"]) == (164, 124)
        sx, sy = sb["x"], sb["y"]
        # 使った点は、ループフィルタの前の復号の値
        assert list(Yd[sy - 1, sx:sx + 8]) == sb["top"] and list(Yd[sy:sy + 4, sx - 1]) == sb["left"]
        assert Yd[sy - 1, sx - 1] == sb["X"]
        pred, orig = sb["pred"], sb["orig"]
        diff = orig - pred
        assert (pred == Yd[sy:sy + 4, sx:sx + 4]).all()          # 差は丸めると全部 0 (この 4×4 は予想そのまま)
        assert diff.min() == -3 and diff.max() == 7
        bmodes = [BMODE_NAME[b] for b in mb()["bmodes"]]
        preds16, top16, left16, X16 = big_preds()
        n_before = MY * 29 + MX

        # ---- S03 の終わり：格子のついた明るさ ----
        view = CatView(Yo, VIEW_C, VIEW_W, VIEW_H)
        view.grid_mb = 1.0
        view.refresh()
        view.check_ignore = True        # 数字や印を上に重ねる下敷き
        self.add(view)

        # ---- 左上から順に作っていく ----
        self.at("order", -0.1)
        lit0 = np.ones((19, 29), np.float32)

        def dim_all(t):
            view.set_mb_lit(1 - (1 - DIM_LIT) * t * lit0)
        self.play(ViewAnim(view, dim_all), run_time=0.5)
        view.base = Yd.astype(np.float32)        # ここからは「作った」画像 (見た目は元とほぼ同じ)
        order = np.arange(19 * 29).reshape(19, 29)

        def sweep(t):
            k = t * (n_before + 6)
            on = np.clip((k - order) / 6, 0, 1) * (order < n_before)
            view.set_mb_lit(DIM_LIT + (1 - DIM_LIT) * on)
        self.play(ViewAnim(view, sweep, rate_func=linear), run_time=2.8)

        self.at("known", -0.1)
        cur = view.track_rect(X0, Y0, 16, 16, stroke_color=YELLOW, stroke_width=4)
        topbar = view.track_rect(X0 - 1, Y0 - 1, 21, 1, stroke_width=0, fill_color=CYAN, fill_opacity=0.85)
        leftbar = view.track_rect(X0 - 1, Y0, 1, 16, stroke_width=0, fill_color=CYAN, fill_opacity=0.85)
        self.play(Create(cur), run_time=0.5)
        self.play(FadeIn(topbar), FadeIn(leftbar), run_time=0.6)
        self.at("so", -0.1)
        self.play(Indicate(VGroup(topbar, leftbar), color=CYAN, scale_factor=1.0), run_time=0.8)

        # ---- 主役の MB へ ----
        self.at("guess", -0.1)
        self.play(zoom(view, WIN_MB), run_time=1.7)
        q = jp("？", 150, DIM).move_to(view.to_point(X0 + 8, Y0 + 8))
        self.at("predict", -0.1)
        self.play(FadeIn(q, scale=0.8), run_time=0.6)

        # ---- 16×16 の予想のしかた ----
        self.at("s04_04", -0.1)
        head = jp("予想のしかた", 30, INK).move_to(px(1695, 55))
        self.play(FadeIn(head, shift=DOWN * u(6)), run_time=0.6)

        def mb_layer(arr):
            mask = np.zeros((16, 16), np.float32)
            view.layers = [(X0, Y0, arr.astype(np.float32), mask)]
            return mask

        def fill_anim(arr, kind):
            mask = mb_layer(arr)
            yy, xx = np.mgrid[0:16, 0:16]
            key = {"V": yy, "H": xx, "DC": np.zeros((16, 16)), "TM": xx + yy}[kind].astype(np.float32)
            span = key.max() + 4

            def fn(t):
                mask[:] = np.clip((t * span - key) / 4, 0, 1) if kind != "DC" else t
            return ViewAnim(view, fn, rate_func=linear if kind != "DC" else smooth)

        cards, labels = [], []

        def to_card(k, name, slot):
            """MB の中の予想を写して、札の場所へ縮める"""
            a, b = view.to_point(X0, Y0), view.to_point(X0 + 16, Y0 + 16)
            img = gray_img(preds16[k], CARD)
            img.width = b[0] - a[0]
            img.move_to((a + b) / 2)
            lab = jp(name, 28, CYAN).move_to(px(CARD_C[slot][0], CARD_C[slot][1] + CARD / 2 + 20))

            def clear(t):
                view.layers[0][3][:] = 1 - t
            img.check_ignore = True
            self.add(img)
            self.play(img.animate.set(width=u(CARD)).move_to(px(*CARD_C[slot])), FadeIn(lab),
                      ViewAnim(view, clear), run_time=0.8)
            view.layers = []
            cards.append(img)
            labels.append(lab)

        self.at("v", -0.1)
        self.play(FadeOut(q), fill_anim(preds16["V"], "V"), run_time=1.2)
        self.wait(0.3)
        to_card("V", "縦", 0)
        self.at("h", -0.1)
        self.play(fill_anim(preds16["H"], "H"), run_time=1.1)
        self.wait(0.3)
        to_card("H", "横", 1)
        self.at("dc", -0.1)
        self.play(fill_anim(preds16["DC"], "DC"), run_time=0.9)
        self.wait(0.5)
        to_card("DC", "平均", 2)

        # TM：左 ＋ (上 − 左上)
        self.at("tmrule", -0.1)
        rule = mix("左 ＋ (上 − 左上)", 36, CYAN).move_to(px(960, 690))
        self.play(FadeIn(rule, shift=UP * u(8)), fill_anim(preds16["TM"], "TM"), run_time=1.6)
        self.at("tmname", -0.4)
        to_card("TM", "TM", 3)
        self.play(FadeOut(rule), run_time=0.4)

        # ---- 4×4 に分けて、10 通りの向き ----
        self.at("four", -0.1)
        view.sb_mb = (MX, MY)

        def sb_on(t):
            view.grid_sb = t
        self.play(ViewAnim(view, sb_on), run_time=0.8)

        self.at("ten", -0.1)
        icons = {m_: icon(m_) for m_ in ICON_C}
        basic = ["VE", "HE", "DC", "TM"]           # 札の順 (縦・横・平均・TM)
        self.play(*[c.animate.set(width=u(ICON)).move_to(px(*ICON_C[m_])).set_opacity(0)
                    for c, m_ in zip(cards, basic)],
                  *[FadeOut(lb) for lb in labels],
                  *[FadeIn(icons[m_]) for m_ in basic], run_time=0.8)
        self.remove(*cards)
        diag = ["LD", "VL", "VR", "RD", "HD", "HU"]
        self.play(LaggedStart(*[FadeIn(icons[m_], scale=0.8) for m_ in diag], lag_ratio=0.15), run_time=1.2)
        self.at("diag", -0.1)
        self.play(*[icons[m_].box.animate.set_stroke(YELLOW, 4) for m_ in diag], run_time=0.5)
        self.play(LaggedStart(*[pop(icons[m_], 1.15, 0.5) for m_ in diag], lag_ratio=0.12), run_time=1.1)
        self.play(*[icons[m_].box.animate.set_stroke(DIM, 2) for m_ in diag], run_time=0.4)

        self.at("many", -0.1)
        self.play(LaggedStart(*[pop(icons[m_], 1.12, 0.5) for m_ in ICON_C], lag_ratio=0.08), run_time=1.3)

        # ---- 目のふちの 4×4 で：MB の中も左上から順に ----
        self.at("s04_08", -0.6)
        sbk = SB = MAIN_SB
        base_lit = view.lit.copy()

        def sb_sweep(t):
            lit = base_lit.copy()
            k = t * (sbk + 2)
            for b in range(sbk):
                on = float(np.clip((k - b) / 2, 0, 1))
                bx, by = X0 + 4 * (b % 4), Y0 + 4 * (b // 4)
                lit[by:by + 4, bx:bx + 4] = DIM_LIT + (1 - DIM_LIT) * on
            view.lit = lit
        self.play(ViewAnim(view, sb_sweep, rate_func=linear), FadeOut(VGroup(cur, topbar, leftbar)), run_time=0.9)
        self.remove(cur, topbar, leftbar)
        win_sb = window_around(sx + 3.5, sy + 2.5, 7)
        self.at("eyeb", -0.1)
        self.play(zoom(view, win_sb), run_time=1.3)
        p = view.pix()
        q2 = jp("？", 120, DIM).move_to(view.to_point(sx + 2, sy + 2))
        self.play(FadeIn(q2), run_time=0.3)

        def nb_cell(x, y, val):
            sq = Square(p * 0.92, stroke_color=CYAN, stroke_width=5).move_to(view.to_point(x + 0.5, y + 0.5))
            t = mono(str(val), 34, num_color(val)).move_to(sq)
            return VGroup(sq, t)
        tops = VGroup(*[nb_cell(sx + i, sy - 1, sb["top"][i]) for i in range(8)])
        lefts = VGroup(*[nb_cell(sx - 1, sy + i, sb["left"][i]) for i in range(4)])
        corner = nb_cell(sx - 1, sy - 1, sb["X"])
        self.at("top", -0.1)
        self.play(LaggedStart(*[FadeIn(c) for c in tops], lag_ratio=0.1), run_time=0.7)
        self.at("left", -0.1)
        self.play(LaggedStart(*[FadeIn(c) for c in lefts], lag_ratio=0.12), run_time=0.7)
        self.at("corner", -0.1)
        self.play(FadeIn(corner), run_time=0.5)

        # ---- VR：下へ、少し右にずれながら ----
        self.at("vr", -0.1)
        self.play(icons["VR"].box.animate.set_stroke(YELLOW, 5), pop(icons["VR"], 1.25, 0.7), run_time=0.7)
        self.at("vrdir", -0.1)
        # 各マスの値は、上 (と左) の点の平均。その点たちの重心から、マスへ流れ込む
        A = list(sb["top"])
        srcpos = {}
        tx = {i: (sx + i + 0.5, sy - 0.5) for i in range(8)}
        tx["X"] = (sx - 0.5, sy - 0.5)
        for i in range(4):
            tx["L%d" % i] = (sx - 0.5, sy + i + 0.5)
        # VR の式 (RFC 6386) と同じ重み
        X, I, J, K = "X", "L0", "L1", "L2"
        a2 = lambda a, b: {a: 1, b: 1}                                         # noqa: E731
        a3 = lambda a, b, c: {a: 1, b: 2, c: 1}                                # noqa: E731
        w = {(0, 0): a2(X, 0), (1, 2): a2(X, 0), (1, 0): a2(0, 1), (2, 2): a2(0, 1), (2, 0): a2(1, 2),
             (3, 2): a2(1, 2), (3, 0): a2(2, 3), (0, 3): a3(K, J, I), (0, 2): a3(J, I, X), (0, 1): a3(I, X, 0),
             (1, 3): a3(I, X, 0), (1, 1): a3(X, 0, 1), (2, 3): a3(X, 0, 1), (2, 1): a3(0, 1, 2), (3, 3): a3(0, 1, 2),
             (3, 1): a3(1, 2, 3)}
        vals = {X: sb["X"], **{i: A[i] for i in range(8)}, **{"L%d" % i: sb["left"][i] for i in range(4)}}
        for (cx, cy), ws in w.items():
            tot = sum(ws.values())
            chk = (sum(vals[k] * n for k, n in ws.items()) + tot // 2) // tot
            assert chk == pred[cy][cx], (cx, cy)
            srcpos[(cx, cy)] = (sum(tx[k][0] * n for k, n in ws.items()) / tot,
                                sum(tx[k][1] * n for k, n in ws.items()) / tot)
        guides = VGroup(*[DashedLine(view.to_point(sx + o, sy - 0.5), view.to_point(sx + o + 2.25, sy + 4),
                                     color=CYAN, stroke_width=3, dash_length=u(10)).set_opacity(0.7)
                          for o in (-0.5, 0.5, 1.5, 2.5)])
        cells = {}
        flows = []
        for (cx, cy) in sorted(w, key=lambda k: (k[1], k[0])):
            v_ = int(pred[cy][cx])
            sq = Square(p, stroke_width=2, stroke_color="#2a2e38", fill_color=lum(v_), fill_opacity=1)
            sq.move_to(view.to_point(sx + cx + 0.5, sy + cy + 0.5))
            t = mono(str(v_), 34, num_color(v_)).move_to(sq)
            cell = VGroup(sq, t)
            start = cell.copy().scale(0.35).move_to(view.to_point(*srcpos[(cx, cy)]))
            start[1].set_opacity(0)
            cells[(cx, cy)] = cell
            flows.append((start, cell, cy * 2 + cx * 0.6))
        self.play(FadeOut(q2), Create(guides), run_time=0.6)
        flows.sort(key=lambda f: f[2])
        self.play(LaggedStart(*[ReplacementTransform(s_, c_, path_arc=0) for s_, c_, _ in flows], lag_ratio=0.12),
                  run_time=2.2)
        pgrid = VGroup(*[cells[(c, r)] for r in range(4) for c in range(4)])
        self.play(FadeOut(guides), run_time=0.4)

        self.at("fill", -0.1)
        self.play(pop(pgrid, 1.08, 0.6), run_time=0.6)

        # ---- 元と並べる → 差 ----
        self.at("cmp", -0.1)
        ogrid = cell_grid(orig, EQ_CELL, EQ_C["orig"])
        lab_o = jp("元", 32, INK).move_to(px(EQ_C["orig"][0], 275))
        lab_p = jp("予想", 32, CYAN).move_to(px(EQ_C["pred"][0], 275))
        pg_target = cell_grid(pred, EQ_CELL, EQ_C["pred"])
        self.play(view.animate.set_opacity(0), FadeOut(VGroup(tops, lefts, corner, head, *icons.values())),
                  Transform(pgrid, pg_target), run_time=1.0)
        self.play(FadeIn(ogrid, shift=RIGHT * u(20)), FadeIn(lab_o), FadeIn(lab_p), run_time=0.8)

        self.at("near", -0.1)
        self.play(pop(ogrid, 1.05, 0.6), pop(pgrid, 1.05, 0.6), run_time=0.6)

        self.at("diffs", -0.3)
        minus = jp("−", 56, DIM).move_to(px((EQ_C["orig"][0] + EQ_C["pred"][0]) / 2, 450))
        eq = jp("＝", 56, DIM).move_to(px((EQ_C["pred"][0] + EQ_C["diff"][0]) / 2, 450))
        dgrid = cell_grid(diff, EQ_CELL, EQ_C["diff"], signed=True)
        self.play(FadeIn(minus), FadeIn(eq), run_time=0.4)
        flies = []
        for i in range(16):
            a_, b_ = ogrid[i].copy(), pgrid[i].copy()
            a_.check_ignore = b_.check_ignore = True
            flies.append(AnimationGroup(ReplacementTransform(VGroup(a_, b_), dgrid[i])))
        self.play(LaggedStart(*flies, lag_ratio=0.06), run_time=1.0)
        self.at("d", -0.1)
        lab_d = jp("差", 32, PURPLE).move_to(px(EQ_C["diff"][0], 275))
        self.play(FadeIn(lab_d, shift=DOWN * u(6)), run_time=0.5)

        self.at("tiny", -0.1)
        self.play(pop(dgrid, 1.1, 0.6), run_time=0.6)

        # ---- ブロックごとに選び直せる ----
        self.at("s04_16", -0.1)
        eqg = VGroup(ogrid, pgrid, dgrid, minus, eq, lab_o, lab_p, lab_d)
        self.play(FadeOut(eqg), run_time=0.7)
        self.remove(*pgrid)
        view.win = WIN_MB
        lit_mb = np.kron((order <= n_before).astype(np.float32), np.ones((16, 16), np.float32))[:300, :451]
        view.lit = DIM_LIT + (1 - DIM_LIT) * lit_mb
        view.refresh()
        self.play(view.animate.set_opacity(1), run_time=0.8)
        self.at("every", -0.1)
        marks = VGroup()
        for b, m_ in enumerate(bmodes):
            c = view.to_point(X0 + 4 * (b % 4) + 2, Y0 + 4 * (b // 4) + 2)
            back = RoundedRectangle(corner_radius=u(8), width=u(78), height=u(78), stroke_width=0, fill_color=BG,
                                    fill_opacity=0.6).move_to(c)
            g = glyph(m_, 78, YELLOW if b == SB else CYAN).move_to(c)
            marks.add(VGroup(back, g))
        self.play(LaggedStart(*[FadeIn(m_, scale=0.7) for m_ in marks], lag_ratio=0.06), run_time=1.6)

        # ---- 写真全体の「予想だけ」 ----
        self.at("s04_17", -0.6)
        self.play(FadeOut(marks), run_time=0.4)

        def sb_off(t):
            view.grid_sb = 1 - t
        self.play(zoom(view, (0, 0, 451, 300)), ViewAnim(view, sb_off), run_time=1.0)
        self.at("all", -0.1)
        full = np.ones((19, 29), np.float32)
        lit_now = view.lit.copy()

        def to_left(t):
            view.lit = lit_now + (1 - lit_now) * t
            view.grid_mb = 1 - t
        self.play(ViewAnim(view, to_left), run_time=0.5)
        self.play(view.animate.set(width=u(SIDE_W)).move_to(px(*SIDE_C["L"])), run_time=0.9)
        view.base = Yo.astype(np.float32)          # 左は元の明るさ
        view.refresh()
        pv = CatView(PY, SIDE_C["R"], VIEW_W, VIEW_H)
        pv.width = u(SIDE_W)
        pv.move_to(px(*SIDE_C["R"]))
        pv.set_mb_lit(full * 0)
        pv.refresh()
        pv.check_ignore = True
        lab_l = jp("元", 30, INK).move_to(px(SIDE_C["L"][0], 482))
        lab_r = jp("予想だけ", 30, CYAN).move_to(px(SIDE_C["R"][0], 482))
        self.play(FadeIn(pv), FadeIn(lab_l), FadeIn(lab_r), run_time=0.5)

        def build(t):
            k = t * (19 * 29 + 12)
            pv.set_mb_lit(np.clip((k - order) / 12, 0, 1))
        self.play(ViewAnim(pv, build, rate_func=linear), run_time=2.0)

        self.at("already", -0.1)
        self.play(pop(pv, 1.04, 0.7), run_time=0.7)

        # ---- 元 − 予想 ----
        self.at("rest", -0.1)
        lab_r2 = jp("元 − 予想", 30, PURPLE)
        self.play(retext(lab_r, lab_r2), run_time=0.6)
        res = np.clip(128 + (Yo - PY), 0, 255).astype(np.float32)
        py0 = PY.astype(np.float32)
        self.at("residual", -0.1)

        def to_res(t):
            pv.base = py0 * (1 - t) + res * t
        self.play(ViewAnim(pv, to_res), run_time=1.4)

        self.at("zero", -0.1)
        near0 = np.abs(Yo - PY) <= 2
        ov = np.zeros((300, 451, 4), np.uint8)
        ov[near0] = (242, 193, 78, 150)
        ovm = ImageMobject(ov)
        ovm.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        ovm.width = pv.width
        ovm.move_to(pv)
        ovm.check_ignore = True
        self.play(FadeIn(ovm), run_time=0.8)

        self.at("get", -0.1)
        self.play(pop(lab_r, 1.15, 0.6), run_time=0.6)

        # ---- PNG のフィルタと同じ考え方 ----
        self.at("png", -0.1)
        t1 = mix("PNG：1行ずつ、左や上との差", 36, DIM).move_to(px(960, 610))
        self.play(FadeIn(t1, shift=UP * u(8)), run_time=0.6)
        self.at("same2", -0.1)
        t2 = mix("WebP：ブロックごとに、向きを選ぶ", 40, CYAN).move_to(px(960, 690))
        self.play(FadeIn(t2, shift=UP * u(8)), run_time=0.6)

        self.at(self.tl["duration"] - 0.75)
        self.play(view.animate.set_opacity(0), pv.animate.set_opacity(0), ovm.animate.set_opacity(0),
                  FadeOut(VGroup(lab_l, lab_r, t1, t2)), run_time=0.6)
        self.finish()
