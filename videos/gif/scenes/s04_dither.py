import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402

from vlib.data import file_bytes, fmt, pixels  # noqa: E402
from zunda.fx import pop, retext  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

Y0, X0, N = 4, 400, 48           # 写真の右上、なめらかに色が変わる背景（データから選んだ窓）
PN = 6                           # ディザの点を見る 6×6 画素
PH = 300                         # 写真の高さ
ZH = 500                         # 拡大の高さ
LX, RX = 695, 1225               # 左右の中心
PCY, ZCY, LAB_Y = 340, 385, 112
BW, BH = 900, 80                 # 1 列の帯


def rgb(c):
    return rgb_to_color(np.asarray(c) / 255)


class S04(PScene):
    def construct(self):
        orig, g256, dth = pixels("cat"), pixels("cat_nodither"), pixels("cat_dither")
        a, b = len(file_bytes("cat_nodither")), len(file_bytes("cat_dither"))
        assert b > a and (a, b) == (105204, 112823)
        assert len(np.unique(g256.reshape(-1, 3), axis=0)) <= 256
        assert len(np.unique(pixels("cat8_nodither").reshape(-1, 3), axis=0)) <= 8
        assert len(np.unique(pixels("cat8_dither").reshape(-1, 3), axis=0)) <= 8

        # 窓の色の幅を、元の窓の最小・最大で 0〜255 に引き伸ばす。元も GIF も同じ変換（段が見えるように）
        sl_ = (slice(Y0, Y0 + N), slice(X0, X0 + N))
        lo = orig[sl_].reshape(-1, 3).min(0).astype(float)
        hi = orig[sl_].reshape(-1, 3).max(0).astype(float)

        def st(arr):
            return np.clip((arr.astype(float) - lo) / (hi - lo) * 255, 0, 255).round().astype(np.uint8)

        zo, zg, zd_ = st(orig[sl_]), st(g256[sl_]), st(dth[sl_])
        # 帯にする 1 列：窓の中で、元の色が一番なめらかに変わる列
        lum = orig[sl_].astype(float).sum(2)
        COL = int(np.argmin(np.abs(np.diff(lum, 2, axis=0)).mean(0)))
        colo, colg = zo[:, COL], zg[:, COL]
        assert len(np.unique(colg, axis=0)) < len(np.unique(colo, axis=0))
        # ディザで 2 色だけの 8×8（色の差が一番大きいところ）
        best = None
        for yy in range(N - PN):
            for xx in range(N - PN):
                p = zd_[yy:yy + PN, xx:xx + PN].reshape(-1, 3)
                uq, k = np.unique(p, axis=0, return_counts=True)
                if len(uq) == 2 and k.min() >= PN * PN // 4:
                    d = int(np.abs(uq[0].astype(int) - uq[1].astype(int)).sum())
                    if best is None or d > best[0]:
                        best = (d, yy, xx)
        _, PYr, PXr = best
        patch = zd_[PYr:PYr + PN, PXr:PXr + PN]
        pmean = patch.reshape(-1, 3).mean(0).round().astype(np.uint8)

        # ---- 元の写真 ----
        photoL = png_mob(orig, PH).move_to(px(960, PCY))
        labL = jp("元の写真", 36, INK).move_to(px(960, LAB_Y))
        self.at("s04_01", -0.1)
        self.play(FadeIn(photoL, shift=UP * u(10)), FadeIn(labL), run_time=0.8)

        # ---- 256 色に ----
        self.at("cut", -0.1)
        photoR = png_mob(g256, PH).move_to(px(RX, PCY))
        labR = jp("256色", 36, INK).move_to(px(RX, LAB_Y))
        self.play(photoL.animate.move_to(px(LX, PCY)), labL.animate.move_to(px(LX, LAB_Y)),
                  FadeIn(photoR, shift=LEFT * u(30)), FadeIn(labR, shift=LEFT * u(30)), run_time=0.9)

        # ---- 空のところを拡大 ----
        self.at("zoom", -0.1)
        pw = photoL.width / orig.shape[1]
        boxes = []
        for ph in (photoL, photoR):
            c = ph.get_corner(UL) + RIGHT * pw * (X0 + N / 2) + DOWN * pw * (Y0 + N / 2)
            boxes.append(Square(pw * N, stroke_color=YELLOW, stroke_width=4).move_to(c))
        self.play(*[Create(r) for r in boxes], run_time=0.5)
        zl = png_mob(zo, ZH, nearest=True)
        zr = png_mob(zg, ZH, nearest=True)
        for z, r in ((zl, boxes[0]), (zr, boxes[1])):
            z.set_height(r.height).move_to(r)
        self.add(zl, zr)
        self.play(zl.animate.set_height(u(ZH)).move_to(px(LX, ZCY)), zr.animate.set_height(u(ZH)).move_to(px(RX, ZCY)),
                  photoL.animate.set_opacity(0), photoR.animate.set_opacity(0),
                  *[FadeOut(r) for r in boxes], run_time=1.2)
        self.remove(photoL, photoR)

        self.at("band", 0.1)
        self.play(pop(zr, 1.06, 0.7), run_time=0.7)

        # ---- 1 列を取り出す：元はなめらか、GIF は階段 ----
        self.at("gap", -2.0)
        zp = ZH / N
        lines = []
        for cx in (LX, RX):
            x = cx - ZH / 2 + zp * (COL + 0.5)
            lines.append(Line(px(x, ZCY - ZH / 2), px(x, ZCY + ZH / 2), color=YELLOW, stroke_width=4))
        self.play(*[Create(l) for l in lines], run_time=0.6)

        def strip(col):
            return png_mob(np.repeat(col[:, None, :], 4, axis=1), ZH, nearest=True)

        sl, sr = strip(colo), strip(colg)
        for s, k in ((sl, 0), (sr, 1)):
            s.stretch_to_fit_width(u(zp)).move_to(lines[k])
        BY1, BY2 = 330, 500
        self.at("gap", -0.1)
        self.add(sl, sr)
        self.play(sl.animate.rotate(PI / 2).move_to(px(960, BY1)), sr.animate.rotate(PI / 2).move_to(px(960, BY2)),
                  zl.animate.set_opacity(0), zr.animate.set_opacity(0), *[FadeOut(l) for l in lines], run_time=0.8)
        self.remove(zl, zr)
        self.play(sl.animate.stretch_to_fit_width(u(BW)).stretch_to_fit_height(u(BH)),
                  sr.animate.stretch_to_fit_width(u(BW)).stretch_to_fit_height(u(BH)),
                  labL.animate.move_to(px(960, BY1 - 70)), labR.animate.move_to(px(960, BY2 - 70)), run_time=0.7)

        # ---- ディザ ----
        self.at("s04_06", -0.2)
        self.play(sl.animate.set_opacity(0), sr.animate.set_opacity(0),
                  labL.animate.move_to(px(LX, LAB_Y)), labR.animate.move_to(px(RX, LAB_Y)), run_time=0.5)
        self.add(zl, zr)
        self.play(zl.animate.set_opacity(1), zr.animate.set_opacity(1), run_time=0.4)
        self.remove(sl, sr)
        self.at("dither", -0.1)
        zd = png_mob(zd_, ZH, nearest=True).move_to(px(RX, ZCY))
        zd.set_opacity(0)
        self.add(zd)
        self.play(zd.animate.set_opacity(1), retext(labR, jp("256色＋ディザ", 36, INK)), run_time=0.8)
        self.remove(zr)

        self.at("dots", -0.1)
        self.play(pop(zd, 1.06, 0.6), run_time=0.6)

        # ---- 2 色の点を混ぜる ----
        self.at("mix", -0.1)
        sq = zp * PN
        corner = px(RX - ZH / 2 + zp * PXr, ZCY - ZH / 2 + zp * PYr)
        box = Square(u(sq), stroke_color=YELLOW, stroke_width=4)
        box.move_to(corner + RIGHT * u(sq / 2) + DOWN * u(sq / 2))
        self.play(Create(box), run_time=0.4)
        big = png_mob(patch, sq, nearest=True).move_to(box)
        self.add(big)
        self.play(big.animate.set_height(u(420)).move_to(px(960, 400)),
                  zl.animate.set_opacity(0), zd.animate.set_opacity(0), FadeOut(box),
                  FadeOut(labL), FadeOut(labR), run_time=1.2)
        self.remove(zl, zd)

        self.at("far", -0.1)
        swatch = Square(u(60), stroke_width=0, fill_color=rgb(pmean), fill_opacity=1).move_to(px(1000, 400))
        self.play(big.animate.set_height(u(60)).move_to(px(900, 400)), run_time=1.0)
        self.play(FadeIn(swatch, shift=LEFT * u(10)), run_time=0.5)

        # ---- 16 色 ----
        self.at("less", -0.1)
        # 顔のまわりを正方形に切り出して大きく（ディザの点が見えるように）
        p16l = png_mob(pixels("cat8_nodither")[:, 60:360], 440, nearest=True).move_to(px(LX - 10, 400))
        p16r = png_mob(pixels("cat8_dither")[:, 60:360], 440, nearest=True).move_to(px(RX + 10, 400))
        labL = jp("8色", 36, INK).move_to(px(LX, LAB_Y))
        labR = jp("8色＋ディザ", 36, INK).move_to(px(RX, LAB_Y))
        for m in (p16l, p16r):
            m.set_opacity(0)
        self.add(p16l, p16r)
        self.play(p16l.animate.set_opacity(1), p16r.animate.set_opacity(1), FadeIn(labL), FadeIn(labR),
                  FadeOut(Group(big, swatch)), run_time=0.9)
        self.remove(big)

        self.at("wow", -0.1)
        self.play(pop(p16r, 1.06, 0.7), run_time=0.7)

        # ---- ファイルの大きさ ----
        self.at("cost", -0.9)
        self.play(p16l.animate.set_opacity(0), p16r.animate.set_opacity(0), FadeOut(labL), FadeOut(labR), run_time=0.6)
        self.remove(p16l, p16r)
        self.at("cost", -0.1)
        sizes = VGroup(jp(f"ディザなし  {fmt(a)} バイト", 44, INK), jp(f"ディザあり  {fmt(b)} バイト", 44, CORAL))
        sizes.arrange(DOWN, buff=u(24), aligned_edge=LEFT).move_to(px(960, 420))
        self.play(FadeIn(sizes, shift=UP * u(8)), run_time=0.8)

        self.at(self.tl["duration"] - 1.2)
        self.play(FadeOut(sizes), run_time=0.9)
        self.finish()
