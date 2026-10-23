"""data/ の素材を作る。HEIC は pillow-heif (中の libheif と x265)、JPEG・WebP は Pillow で保存する。

    uv run python videos/heic/tools/make_data.py

- cat.png：猫の写真 (scikit-image の chelsea、CC0)。前の 4 本と同じ。
- cat_q{15,25,45}.heic：品質を変えた HEIC。q45 が本編 (元とのずれが JPEG・WebP の品質 80 と同じくらい)。
- cat_q{5,80}.jpg、cat_q{10,80}.webp：JPEG 編・WebP 編と同じ設定。
- zunda.heic (透明つき、サムネつき)：立ち絵から作るのでリポジトリには入れない。
"""
import sys
from pathlib import Path

import pillow_heif
from PIL import Image

VDIR = Path(__file__).resolve().parent.parent
D = VDIR / "data"
sys.path.insert(0, str(VDIR.parents[1]))

HEIC_Q = (15, 25, 45)


def main():
    cat = Image.open(D / "cat.png").convert("RGB")
    for q in HEIC_Q:
        pillow_heif.from_pillow(cat).save(D / f"cat_q{q}.heic", quality=q)
    for q in (5, 80):
        cat.save(D / f"cat_q{q}.jpg", quality=q, subsampling=2, optimize=False, progressive=False)
    for q in (10, 80):
        cat.save(D / f"cat_q{q}.webp", quality=q)
    try:
        from zunda import character
        from zunda.compose import BASE
        z = character.render("zundamon", dict(BASE["Z"]))
    except Exception as e:   # 立ち絵がない
        print("立ち絵がないので zunda.heic は作らない：", e)
        return
    z = z.resize((z.width // 2, z.height // 2), Image.LANCZOS)   # 立ち絵のキャンバス全体を半分に (WebP 編と同じ)
    hf = pillow_heif.from_pillow(z)
    hf.save(D / "zunda.heic", quality=45, thumbnails=[128])


if __name__ == "__main__":
    main()
