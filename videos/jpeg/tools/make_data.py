"""data/ の素材を作る。

    uv run python videos/jpeg/tools/make_data.py

- cat_q{5,10,30,50,80,95}.jpg：猫の写真（data/cat.png、CC0）を Pillow（libjpeg）で品質を変えて保存。リポジトリにも入っている。
- zunda_white.png / zunda_q80.jpg：白背景のずんだもん（イラストとの比較用）。立ち絵から作るのでリポジトリには入れていない。
  元にする data/zundamon.png は videos/png/tools/make_zundamon_png.py で作れる（公開版とは別の画像になる）。
"""
from pathlib import Path

from PIL import Image

D = Path(__file__).resolve().parent.parent / "data"


def main():
    cat = Image.open(D / "cat.png").convert("RGB")
    for q in (5, 10, 30, 50, 80, 95):
        cat.save(D / f"cat_q{q}.jpg", quality=q, subsampling=2, optimize=False, progressive=False)
    src = D / "zundamon.png"
    if not src.exists():
        src = D.parent.parent / "png" / "data" / "zundamon.png"
    if src.exists():
        z = Image.open(src)
        bg = Image.new("RGB", z.size, (255, 255, 255))
        bg.paste(z, mask=z.split()[3])
        bg = bg.resize((541, 797), Image.LANCZOS)
        bg.save(D / "zunda_white.png", optimize=True)
        bg.save(D / "zunda_q80.jpg", quality=80, subsampling=2)
    else:
        print("zundamon.png がないので zunda_white / zunda_q80 は作らない（videos/png/tools/make_zundamon_png.py）")


if __name__ == "__main__":
    main()
