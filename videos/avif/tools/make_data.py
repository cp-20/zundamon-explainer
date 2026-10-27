"""data/ の素材を作る。AVIF は Pillow (中の libavif と libaom)、JPEG・WebP は Pillow、HEIC は pillow-heif で保存する。

    uv run python videos/avif/tools/make_data.py

- cat.png：猫の写真 (scikit-image の chelsea、CC0)。前の 5 本と同じ。
- cat_q60.avif：本編。元とのずれが HEIC 編の HEIC 品質 45 (と JPEG・WebP の品質 80) と同じくらいになる品質。
- cat_q30.avif：うんと小さくしたもの (4 千バイトくらい。HEIC 編の実験と同じ大きさ)。
- cat_q*.jpg・webp・heic：前の動画と同じ設定。
- cat_grain.png：猫の明るさに、暗い所で撮ったような粒 (正規分布、標準偏差 9) を足したもの。フィルムグレインの実験用。
- cat_grain_fg.avif：粒を取り除いてから縮め、粒の作り方だけを書く (libaom の denoise-noise-level)。
  粒の取り除きは同じ設定でも毎回少し違うファイルになるので、すでにあれば作り直さない (作り直すときは消してから)。
- cat_grain_q60.avif：粒をそのまま、本編と同じ品質 60 で縮めたもの (粒があると大きくなる)。
- cat_grain_q*.avif (q60 以外)：粒をそのまま縮めたもの。cat_grain_fg.avif といちばん近い大きさになる品質を探す。
"""
import io
import sys
from pathlib import Path

import numpy as np
import pillow_heif
from PIL import Image

VDIR = Path(__file__).resolve().parent.parent
D = VDIR / "data"
sys.path.insert(0, str(VDIR.parents[1]))

AVIF_Q = (30, 60)
GRAIN_SIGMA, GRAIN_SEED = 9, 1
FG_Q, FG_DENOISE = 50, 25


def avif_bytes(im, q, **kw):
    b = io.BytesIO()
    im.save(b, "AVIF", quality=q, **kw)
    return b.getvalue()


def main():
    cat = Image.open(D / "cat.png").convert("RGB")
    for q in AVIF_Q:
        cat.save(D / f"cat_q{q}.avif", quality=q)   # speed 6・4:2:0・8 ビット (Pillow の既定)
    for q in (5, 80):
        cat.save(D / f"cat_q{q}.jpg", quality=q, subsampling=2, optimize=False, progressive=False)
    for q in (10, 80):
        cat.save(D / f"cat_q{q}.webp", quality=q)
    for q in (25, 45):
        pillow_heif.from_pillow(cat).save(D / f"cat_q{q}.heic", quality=q)
    # フィルムグレイン
    a = np.asarray(cat).astype(float)
    noise = np.random.default_rng(GRAIN_SEED).normal(0, GRAIN_SIGMA, a.shape[:2])[..., None]
    grain = Image.fromarray(np.clip(a + noise, 0, 255).round().astype(np.uint8))
    grain.save(D / "cat_grain.png")
    if not (D / "cat_grain_fg.avif").exists():
        (D / "cat_grain_fg.avif").write_bytes(avif_bytes(grain, FG_Q, advanced=[("denoise-noise-level", str(FG_DENOISE))]))
    fg = (D / "cat_grain_fg.avif").read_bytes()
    q = min(range(20, FG_Q + 1), key=lambda q: abs(len(avif_bytes(grain, q)) - len(fg)))
    for old in D.glob("cat_grain_q*.avif"):
        old.unlink()
    for q in sorted({q, 60}):
        (D / f"cat_grain_q{q}.avif").write_bytes(avif_bytes(grain, q))


if __name__ == "__main__":
    main()
