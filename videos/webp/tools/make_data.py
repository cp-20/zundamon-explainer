"""data/ の素材を作る。Pillow (中の libwebp・libjpeg) で保存する。

    uv run python videos/webp/tools/make_data.py

- cat.png：猫の写真 (scikit-image の chelsea、CC0)。リポジトリに入っている。
- cat_q{5,80}.jpg：JPEG 編と同じ品質 5・80 の JPEG。cat_q{..}.webp：品質を変えた非可逆の WebP。cat_lossless.webp：可逆の WebP。
- zunda.png / zunda_lossless.webp / zunda_q80.webp：透明な背景のずんだもん (541×797)。
  zunda_anim.webp：GIF 編の動くスタンプを、可逆の動く WebP にしたもの。立ち絵から作るのでリポジトリには入れていない。
"""
import sys
from pathlib import Path

from PIL import Image

VDIR = Path(__file__).resolve().parent.parent
D = VDIR / "data"
sys.path.insert(0, str(VDIR.parents[1]))

WEBP_Q = (5, 10, 20, 30, 50, 80, 90)


def main():
    cat = Image.open(D / "cat.png").convert("RGB")
    for q in (5, 80):
        cat.save(D / f"cat_q{q}.jpg", quality=q, subsampling=2, optimize=False, progressive=False)
    for q in WEBP_Q:
        cat.save(D / f"cat_q{q}.webp", quality=q)
    cat.save(D / "cat_lossless.webp", lossless=True)
    try:
        from zunda import character
        from zunda.compose import BASE
        z = character.render("zundamon", dict(BASE["Z"]))
    except Exception as e:   # 立ち絵がない
        print("立ち絵がないので zunda* は作らない：", e)
        return
    z = z.resize((z.width // 2, z.height // 2), Image.LANCZOS)   # 立ち絵のキャンバス全体を半分に (縦横比はそのまま)
    z.save(D / "zunda.png", optimize=True)
    z.save(D / "zunda_lossless.webp", lossless=True)
    z.save(D / "zunda_q80.webp", quality=80)
    gif = VDIR.parent / "gif" / "data" / "zunda_anim.gif"
    if gif.exists():
        g = Image.open(gif)
        durs = []
        for k in range(g.n_frames):
            g.seek(k)
            durs.append(g.info["duration"])
        g.seek(0)
        g.save(D / "zunda_anim.webp", save_all=True, lossless=True, duration=durs, loop=0)
    else:
        print("GIF 編の zunda_anim.gif がないので zunda_anim.webp は作らない (videos/gif/tools/make_data.py)")


if __name__ == "__main__":
    main()
