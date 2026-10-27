"""保存 (縮める) にかかる時間を測って data/encode_time.json に書く (実験と弱点のシーン)。

    uv run python videos/avif/tools/measure_time.py [回数]

cat.png を、JPEG 品質 80・WebP 品質 80 (Pillow)・HEIC 品質 45 (pillow-heif、HEIC 編と同じ設定)・AVIF 品質 60 (Pillow、本編と同じ設定) でメモリに保存する。
それぞれ最初に 1 回空回ししてから、指定の回数 (既定 15) をくり返し、かかった時間 (壁時計) の中央値を取る。
"""
import io
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import PIL
import pillow_heif
from PIL import Image

D = Path(__file__).resolve().parent.parent / "data"


def save_jpeg(im):
    im.save(io.BytesIO(), "JPEG", quality=80, subsampling=2, optimize=False, progressive=False)


def save_webp(im):
    im.save(io.BytesIO(), "WEBP", quality=80)


def save_heic(im):
    pillow_heif.from_pillow(im).save(io.BytesIO(), quality=45)


def save_avif(im):
    im.save(io.BytesIO(), "AVIF", quality=60)


def measure(fn, im, n):
    fn(im)
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn(im)
        ts.append(time.perf_counter() - t0)
    return ts


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    im = Image.open(D / "cat.png").convert("RGB")
    im.load()
    res = {}
    # 順番の偏りを避けるため、4 つを交互に何周かする
    runs = {"jpeg": [], "webp": [], "heic": [], "avif": []}
    fns = {"jpeg": save_jpeg, "webp": save_webp, "heic": save_heic, "avif": save_avif}
    for _ in range(3):
        for k, fn in fns.items():
            runs[k] += measure(fn, im, n)
    for k, ts in runs.items():
        res[k] = dict(median_s=statistics.median(ts), min_s=min(ts), runs=len(ts))
    out = dict(
        settings=dict(jpeg="Pillow quality=80", webp="Pillow quality=80", heic="pillow-heif quality=45", avif="Pillow quality=60"),
        image=f"cat.png {im.width}x{im.height}",
        machine=platform.processor() or platform.machine(),
        pillow_heif=pillow_heif.__version__,
        pillow=PIL.__version__,
        **res,
        heic_over_jpeg=res["heic"]["median_s"] / res["jpeg"]["median_s"],
        webp_over_jpeg=res["webp"]["median_s"] / res["jpeg"]["median_s"],
        avif_over_jpeg=res["avif"]["median_s"] / res["jpeg"]["median_s"],
        avif_over_heic=res["avif"]["median_s"] / res["heic"]["median_s"],
    )
    (D / "encode_time.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    for k in ("jpeg", "webp", "heic", "avif"):
        print(f"{k}: {res[k]['median_s'] * 1000:.2f} ms (min {res[k]['min_s'] * 1000:.2f})")
    print(f"HEIC / JPEG = {out['heic_over_jpeg']:.0f}  AVIF / JPEG = {out['avif_over_jpeg']:.0f}  "
          f"AVIF / HEIC = {out['avif_over_heic']:.1f}")


if __name__ == "__main__":
    main()
