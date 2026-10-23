import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from vlib.data import HEIF, boxes, fmt, hevc, path, rgb_decoded, size  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

NAME = "zunda"
# ファイル全体の帯 (S02 と同じ位置・色。幅はバイト数に比例)
SX0, SX1, SY, SH = 60, 1860, 125, 64
LAB_Y = 52
SEG_COL = {"ftyp": YELLOW, "meta": BLUE, "mdat": "#4a5060"}
# 4 つの項目の色 (色の画像は緑、透明は灰。サムネイルは暗め)
ITEM_COL = {1: "#7cc35a", 2: "#c9ced8", 3: "#4f8f3c", 4: "#8a909c"}
ITEM_NAME = {1: "本体", 2: "透明", 3: "サムネイル", 4: "サムネイルの透明"}
BIG_C, BIG_H = (660, 575), 600          # 大きく出すずんだもん
ROW_Y = [300, 445, 590, 735]
IMG_X, IMG_H, TXT_X = 1010, 124, 1090


def left_at(m, x, y):
    return m.move_to(px(x, y), aligned_edge=LEFT).set_y(px(0, y)[1])


def shrink(arr, h_px):
    """縮めて置くときは LANCZOS で縮めてから (1080p の画素で h_px)"""
    hh = max(2, round(h_px * config.pixel_height / 1080))
    ww = max(2, round(arr.shape[1] * hh / arr.shape[0]))
    return np.asarray(Image.fromarray(arr).resize((ww, hh), Image.LANCZOS))


def img(arr, h_px, nearest=False):
    m = ImageMobject(np.ascontiguousarray(arr))
    if nearest:
        m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.height = u(h_px)
    m.check_ignore = True
    return m


def item_rgb(r, iid):
    """色の項目を自前の復号器で復号して RGB に (colr：BT.601、全範囲。vlib.data.rgb_decoded と同じ変換)"""
    it = r["items"][iid]
    d = hevc.Decoder(HEIF.item_nals(r, iid), keep_log=False).decode()
    Y, U, V = (np.asarray(p, np.float32) for p in d.cropped(d.final))
    h, w = Y.shape
    up = [np.asarray(Image.fromarray(c).resize((w, h), Image.BILINEAR), np.float32) - 128 for c in (U, V)]
    rgb = np.dstack([Y + 1.402 * up[1], Y - 0.344136 * up[0] - 0.714136 * up[1], Y + 1.772 * up[0]])
    c = HEIF.item_prop(it, "clap") or HEIF.item_prop(it, "ispe")
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8)[:c["height"], :c["width"]]


def item_alpha(r, iid):
    """透明の項目 (明るさだけの HEVC) を自前の復号器で。白黒の明るさがそのまま透明度"""
    it = r["items"][iid]
    d = hevc.Decoder(HEIF.item_nals(r, iid), keep_log=False).decode()
    Y, U, V = d.cropped(d.final)
    assert U is None and V is None
    c = HEIF.item_prop(it, "clap") or HEIF.item_prop(it, "ispe")
    return np.asarray(Y, np.uint8)[:c["height"], :c["width"]]


def alphas_libheif():
    """比べる用：pillow-heif (libheif) の透明度"""
    import pillow_heif
    h = pillow_heif.open_heif(path(NAME))
    return np.asarray(h.to_pillow())[..., 3], np.asarray(h[0].get_thumbnail(0).to_pillow())[..., 3]


def iref(r):
    """iref の中身 [(種類, 元の項目, [先の項目])] (version 0：番号は 2 バイト)"""
    b = r["bytes"]
    box = HEIF.find(r["tree"], "iref")[0]
    assert b[box["body"]] == 0
    o, end = box["body"] + 4, box["pos"] + box["size"]
    out = []
    while o < end:
        sz = int.from_bytes(b[o:o + 4], "big")
        typ = b[o + 4:o + 8].decode()
        src = int.from_bytes(b[o + 8:o + 10], "big")
        n = int.from_bytes(b[o + 10:o + 12], "big")
        out.append((typ, src, [int.from_bytes(b[o + 12 + 2 * k:o + 14 + 2 * k], "big") for k in range(n)]))
        o += sz
    return out


def gray(a):
    return np.repeat(a[..., None], 3, axis=2)


class S09(PScene):
    def construct(self):
        # ================= データ =================
        r = boxes(NAME)
        total = size(NAME)
        tree = r["tree"]
        assert [b["type"] for b in tree] == ["ftyp", "meta", "mdat"] and sum(b["size"] for b in tree) == total
        items = r["items"]
        assert sorted(items) == [1, 2, 3, 4] and all(it["type"] == "hvc1" for it in items.values())
        assert r["primary"] == 1
        aux = {iid for iid, it in items.items() if HEIF.item_prop(it, "auxC")}
        assert aux == {2, 4}
        refs = iref(r)
        assert sorted(refs) == [("auxl", 2, [1]), ("auxl", 4, [3]), ("thmb", 3, [1])]
        mdat = tree[2]
        ext = {iid: it["extents"] for iid, it in items.items()}
        assert all(len(e) == 1 for e in ext.values())
        nbytes = {iid: e[0][1] for iid, e in ext.items()}
        pos = [ext[i][0][0] for i in (1, 2, 3, 4)]
        assert pos[0] == mdat["body"] and all(pos[k] + nbytes[k + 1] == pos[k + 1] for k in range(3))
        assert pos[3] + nbytes[4] == mdat["pos"] + mdat["size"]
        assert [nbytes[i] for i in (1, 2, 3, 4)] == [19954, 6870, 1919, 1059]
        color = item_rgb(r, 1)           # 自前の復号 (透明の所は黒)
        thumb = item_rgb(r, 3)
        a_main, a_th = item_alpha(r, 2), item_alpha(r, 4)
        ref_main, ref_th = alphas_libheif()
        assert (a_main == ref_main).all() and (a_th == ref_th).all()
        assert color.shape[:2] == a_main.shape == (797, 541) and thumb.shape[:2] == a_th.shape == (128, 86)
        rgba = np.dstack([color, a_main])

        def xb(b):
            return SX0 + (SX1 - SX0) * b / total

        # ================= ファイルの帯 (S02 と同じ見た目) =================
        seg = {}
        for b in tree:
            x0, x1 = xb(b["pos"]), xb(b["pos"] + b["size"])
            seg[b["type"]] = Rectangle(width=u(max(x1 - x0, 3)), height=u(SH), stroke_width=0,
                                       fill_color=SEG_COL[b["type"]], fill_opacity=1).move_to(px(x0, SY), aligned_edge=LEFT)
        lab_f = left_at(mix("ftyp", 32, YELLOW), SX0, LAB_Y)
        lead_f = Line(px(xb(12), LAB_Y + 20), px(xb(12), SY - SH / 2), stroke_color=YELLOW, stroke_width=2)
        meta = tree[1]
        lab_m = left_at(mix(f"meta {fmt(meta['size'])}", 32, BLUE), 180, LAB_Y)
        lead_m = Line(px(174, LAB_Y + 12), px(xb(meta["pos"] + meta["size"] / 2), SY - SH / 2), stroke_color=BLUE,
                      stroke_width=2)
        lab_d = mix(f"mdat {fmt(mdat['size'])}", 32, INK).move_to(px(960, LAB_Y))
        fname = left_at(mono(f"{NAME}.heic", 32, DIM), 1500, LAB_Y)

        self.at("s09_01", -0.1)
        self.play(GrowFromEdge(seg["ftyp"], LEFT, run_time=0.2), run_time=0.2)
        self.play(Succession(GrowFromEdge(seg["meta"], LEFT, run_time=0.25),
                             GrowFromEdge(seg["mdat"], LEFT, run_time=1.0, rate_func=rate_functions.ease_out_cubic)),
                  FadeIn(fname, shift=LEFT * u(10)), run_time=1.25)
        self.play(Create(lead_f), Create(lead_m), FadeIn(lab_f), FadeIn(lab_m), FadeIn(lab_d, scale=0.9), run_time=0.5)

        # ---- mdat の中が 4 つに分かれる (iloc の置き場所どおり) ----
        self.at("many", -0.1)
        parts = {}
        for iid in (1, 2, 3, 4):
            p0, n = ext[iid][0]
            x0, x1 = xb(p0), xb(p0 + n)
            parts[iid] = Rectangle(width=u(x1 - x0 - 4), height=u(SH), stroke_width=0, fill_color=ITEM_COL[iid],
                                   fill_opacity=1).move_to(px(x0 + 2, SY), aligned_edge=LEFT)
        self.play(LaggedStart(*[GrowFromEdge(parts[i], LEFT) for i in (1, 2, 3, 4)], lag_ratio=0.3), run_time=1.5)
        self.remove(seg["mdat"])

        # ================= 透明のあるずんだもん =================
        big = png_mob(shrink(rgba, BIG_H), BIG_H, cell_px=18).move_to(px(*BIG_C))
        big.check_ignore = True
        self.at("alpha", -0.1)
        self.play(FadeIn(big, shift=UP * u(14)), run_time=0.9)

        # ================= 4 つの項目 (iinf の目録) =================
        self.at("thumb", -0.1)
        aspect = 541 / 797
        slots, names, sizes = {}, {}, {}
        for k, iid in enumerate((1, 2, 3, 4)):
            y = ROW_Y[k]
            slots[iid] = Rectangle(width=u(IMG_H * aspect), height=u(IMG_H), stroke_color=ITEM_COL[iid], stroke_width=4,
                                   fill_color="#1c1f27", fill_opacity=1).move_to(px(IMG_X, y))
            names[iid] = left_at(jp(ITEM_NAME[iid], 40, INK), TXT_X, y - 24)
            sizes[iid] = left_at(mix(f"{fmt(nbytes[iid])} バイト", 36, "#aab0bc"), TXT_X, y + 30)
        self.play(LaggedStart(*[AnimationGroup(ReplacementTransform(parts[i].copy(), slots[i], path_arc=-0.5),
                                               FadeIn(names[i], shift=LEFT * u(10)), FadeIn(sizes[i], shift=LEFT * u(10)))
                                for i in (1, 2, 3, 4)], lag_ratio=0.22), run_time=2.0)

        # ================= 透明は白黒の画像をもう 1 枚 =================
        self.at("mask", -0.1)
        big_col = img(shrink(color, BIG_H), BIG_H).move_to(big)
        big_msk = img(shrink(gray(a_main), BIG_H), BIG_H).move_to(big).set_opacity(0)
        self.add(big_msk)
        self.play(big_msk.animate.set_opacity(1), slots[2].animate.set_stroke(YELLOW, 6), run_time=0.8)
        self.wait(0.2)
        # 白黒が抜け出して「透明」の枠へ。残るのは透明のない本体 (透明の所は黒)
        big_col.set_opacity(0)
        self.add(big_col)
        self.bring_to_front(big_msk)
        small_msk = img(shrink(gray(a_main), IMG_H), IMG_H).move_to(slots[2])
        self.play(big_msk.animate(path_arc=-0.4).replace(small_msk), big.animate.set_opacity(0),
                  big_col.animate.set_opacity(1), run_time=1.0)
        self.add(small_msk)
        self.remove(big_msk, big)
        small_col = img(shrink(color, IMG_H), IMG_H).move_to(slots[1])
        fly = img(shrink(color, BIG_H), BIG_H).move_to(big_col)
        self.add(fly)
        self.play(fly.animate(path_arc=-0.4).replace(small_col), slots[2].animate.set_stroke(ITEM_COL[2], 4),
                  slots[1].animate.set_stroke(YELLOW, 6), run_time=0.7)
        self.add(small_col)
        self.remove(fly)
        self.bring_to_front(slots[1].set_fill(opacity=0), slots[2].set_fill(opacity=0))

        # ================= 一覧に出す小さな見本 =================
        self.at("small", -0.1)
        th_h = BIG_H * thumb.shape[0] / color.shape[0]          # 本体と同じ倍率で置いたときの大きさ
        tiny = img(thumb, th_h, nearest=True).move_to(big_col)
        tiny.set_opacity(0)
        self.add(tiny)
        self.play(big_col.animate.set_opacity(0.25), tiny.animate.set_opacity(1), slots[1].animate.set_stroke(ITEM_COL[1], 4),
                  slots[3].animate.set_stroke(YELLOW, 6), run_time=0.8)
        self.wait(0.3)
        small_th = img(thumb, IMG_H, nearest=True).move_to(slots[3])
        small_tha = img(gray(a_th), IMG_H, nearest=True).move_to(slots[4])
        fly_a = img(gray(a_th), IMG_H, nearest=True).move_to(slots[2])
        fly_a.set_opacity(0)
        self.add(fly_a)
        self.play(tiny.animate(path_arc=-0.4).replace(small_th), big_col.animate.set_opacity(1),
                  fly_a.animate.set_opacity(1), run_time=0.9)
        self.add(small_th)
        self.remove(tiny)
        self.play(fly_a.animate(path_arc=0.5).move_to(slots[4]), slots[3].animate.set_stroke(ITEM_COL[3], 4), run_time=0.7)
        self.add(small_tha)
        self.remove(fly_a)
        self.bring_to_front(slots[3].set_fill(opacity=0), slots[4].set_fill(opacity=0))

        # iref：どの画像の透明か・サムネイルか
        def link(src, dst, ang):
            a = slots[src].get_left() + LEFT * u(6)
            b = slots[dst].get_left() + LEFT * u(6)
            return CurvedArrow(a, b, angle=ang, color=YELLOW, stroke_width=5, tip_length=u(18))
        arrows = [link(2, 1, -1.6), link(3, 1, -2.0), link(4, 3, -1.6)]
        self.play(LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.3), run_time=1.3)

        # ================= 1 つのファイルに 4 枚 =================
        self.at("box", -0.1)
        smalls = {1: small_col, 2: small_msk, 3: small_th, 4: small_tha}
        self.play(LaggedStart(*[pop(Group(smalls[i], slots[i]), 1.15, 0.6) for i in (1, 2, 3, 4)], lag_ratio=0.25),
                  run_time=1.5)

        # ================= iPhone の写真 =================
        self.at("phone", -0.25)
        imgs = [big_col, small_col, small_msk, small_th, small_tha]
        self.play(*[m.animate.set_opacity(0) for m in imgs],
                  FadeOut(VGroup(seg["ftyp"], seg["meta"], *parts.values(), lab_f, lead_f, lab_m, lead_m, lab_d, fname, *arrows,
                                 *[VGroup(slots[i], names[i], sizes[i]) for i in (1, 2, 3, 4)])), run_time=0.7)
        self.remove(*imgs)

        cat = rgb_decoded()
        CW, CH_ = 600, 400
        CC = (790, 520)
        cont = RoundedRectangle(corner_radius=u(24), width=u(1000), height=u(620), stroke_color=BLUE, stroke_width=4,
                                fill_color="#1c1f27", fill_opacity=1).move_to(px(960, 540))
        ctitle = left_at(mix("iPhoneの写真", 40, BLUE), 490, 268)
        # 本体：タイルに分けて入っている (3×2)
        tiles = []
        H, W = cat.shape[:2]
        xs, ys = [0, 151, 301, W], [0, 150, H]
        for j in range(2):
            for i in range(3):
                crop = cat[ys[j]:ys[j + 1], xs[i]:xs[i + 1]]
                t = img(shrink(crop, CH_ * crop.shape[0] / H), CH_ * crop.shape[0] / H)
                cx = CC[0] - CW / 2 + CW * (xs[i] + xs[i + 1]) / 2 / W
                cy = CC[1] - CH_ / 2 + CH_ * (ys[j] + ys[j + 1]) / 2 / H
                t.move_to(px(cx, cy))
                t.home = (cx, cy)
                t.ij = (i, j)
                tiles.append(t)
        th_cat = img(shrink(cat, 100), 100).move_to(px(1290, 360))
        self.play(FadeIn(cont), FadeIn(ctitle), *[FadeIn(t) for t in tiles], FadeIn(th_cat), run_time=0.9)

        # 奥行きの画像 (絵だけ。手前ほど白い)
        self.at("depth", -0.1)
        yy, xx = np.mgrid[0:200, 0:300]
        dep = np.clip(255 - np.hypot((xx - 140) / 1.2, (yy - 120)) * 2.2, 30, 255)
        dep = (dep * (0.55 + 0.45 * (yy / 200))).astype(np.uint8)
        dimg = img(gray(dep), 140).move_to(px(1290, 600))
        dlab = jp("奥行き", 34, INK).next_to(dimg, DOWN, buff=u(12))
        self.play(FadeIn(dimg, shift=UP * u(12)), FadeIn(dlab), run_time=0.8)

        # 大きな写真を小さく切ったタイル
        self.at("tile", -0.1)
        tlab = jp("タイル", 34, INK).move_to(px(CC[0], CC[1] + CH_ / 2 + 48))
        GAP = 14
        anims = []
        for t in tiles:
            cx, cy = t.home
            dx = (t.ij[0] - 1) * GAP
            dy = (t.ij[1] - 0.5) * GAP
            anims.append(t.animate.move_to(px(cx + dx, cy + dy)))
        self.play(*anims, FadeIn(tlab, shift=UP * u(8)), run_time=1.0)

        # ---- 終わりは空 ----
        self.at("S09_05.end", 0.05)
        pics = [*tiles, th_cat, dimg]
        self.play(*[m.animate.set_opacity(0) for m in pics], *[FadeOut(m) for m in (cont, ctitle, dlab, tlab)],
                  run_time=self.until(self.tl["duration"], -0.1))
        self.remove(*pics)
        self.finish()
