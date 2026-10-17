"""data/ の素材を作る（1回だけ）。

- zunda_anim.gif：ずんだもんが まばたき→にっこり→両手を挙げる をくり返す動くGIF（立ち絵から作る）
- cat{,16,8}_{dither,nodither}.gif：猫の写真（data/cat.png、CC0）を 256・16・8 色にしたもの（ディザあり／なし）。リポジトリにも入っている
- zunda_anim.gif は立ち絵から作るのでリポジトリには入れていない（立ち絵素材が必要）
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent   # 動画のフォルダ
sys.path.insert(0, str(ROOT.parents[1]))         # リポジトリ（zunda）
from zunda import character  # noqa: E402
from zunda.compose import BASE, BLINK, EXPR, MOUTH  # noqa: E402

H = 360


def frame(expr, mouth="closed", blink=False):
    st = dict(BASE["Z"]); st.update(EXPR["Z"][expr]); st["!口"] = MOUTH["Z"][mouth]
    if blink:
        st.update(BLINK["Z"])
    return character.render("zundamon", st)


def main():
    # 顔だけが変わる動き（まばたき・にっこり・おしゃべり）。変わった所だけを書く GIF の仕組みが見えるように
    seq = [("通常", "closed", False, 60), ("通常", "closed", True, 12), ("通常", "closed", False, 40),
           ("通常", "open", False, 15), ("通常", "half", False, 15), ("通常", "open", False, 15),
           ("笑", "open", False, 60), ("笑", "closed", False, 30)]
    ims = [frame(e, m, b) for e, m, b, _ in seq]
    box = ims[0].getbbox()
    for im in ims[1:]:
        b = im.getbbox()
        box = (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    ims = [im.crop(box) for im in ims]
    w = round(ims[0].width * H / ims[0].height)
    ims = [im.resize((w, H), Image.LANCZOS) for im in ims]
    # 半透明は GIF にないので、アルファは 0/255 に丸める。顔以外の小さな差（縮小のにじみ）は 1 枚目にそろえて、
    # 「変わった所だけ」が本当に顔だけになるようにする。色の表（パレット）は全コマ共通の 255 色＋透明 1 つ。
    import numpy as np
    arr = []
    for im in ims:
        a = np.asarray(im).copy()
        a[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
        arr.append(a)
    base = arr[0]
    for a in arr[1:]:
        d = (np.abs(a.astype(int) - base.astype(int)).max(-1) > 40)
        from scipy.ndimage import binary_dilation
        d = binary_dilation(d, iterations=2)
        a[~d] = base[~d]
    rgb = np.concatenate([np.where(a[..., 3:] > 0, a[..., :3], 255) for a in arr], 0).astype(np.uint8)
    pal = Image.fromarray(rgb).quantize(255, dither=Image.Dither.NONE)
    frames = []
    for a in arr:
        p = Image.fromarray(np.where(a[..., 3:] > 0, a[..., :3], 255).astype(np.uint8)).quantize(
            palette=pal, dither=Image.Dither.NONE)
        idx = np.asarray(p).copy()
        idx[a[..., 3] == 0] = 255
        f = Image.fromarray(idx, "P")
        f.putpalette(pal.getpalette()[:765] + [0, 0, 0])
        frames.append(f)
    frames[0].save(ROOT / "data/zunda_anim.gif", save_all=True, append_images=frames[1:],
                   duration=[d * 10 for *_, d in seq], loop=0, disposal=1, transparency=255, optimize=False, interlace=False)
    cat = Image.open(ROOT / "data/cat.png").convert("RGB")
    for n in (256, 16, 8):
        pal = cat.quantize(n, dither=Image.Dither.NONE)   # パレット（色の表）を決める
        tag = "" if n == 256 else str(n)
        pal.save(ROOT / f"data/cat{tag}_nodither.gif", interlace=False)
        cat.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).save(ROOT / f"data/cat{tag}_dither.gif", interlace=False)


if __name__ == "__main__":
    main()
