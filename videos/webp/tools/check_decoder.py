"""自前の復号器と libwebp (dwebp・Pillow) の結果を突き合わせる。

- 非可逆：Y・U・V の全画素を dwebp -yuv (ループフィルタあり) と dwebp -yuv -nofilter の両方と比べる
- 可逆：RGBA の全画素を Pillow と比べる

    uv run python videos/webp/tools/check_decoder.py videos/webp/data/*.webp
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import webpanalyze as W  # noqa: E402


def dwebp_yuv(path, w, h, nofilter):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "o.yuv"
        subprocess.run(["dwebp", str(path), "-yuv", "-o", str(out)] + (["-nofilter"] if nofilter else []),
                       check=True, capture_output=True)
        raw = np.frombuffer(out.read_bytes(), np.uint8)
    cw, ch = (w + 1) // 2, (h + 1) // 2
    y = raw[:w * h].reshape(h, w)
    u = raw[w * h:w * h + cw * ch].reshape(ch, cw)
    v = raw[w * h + cw * ch:w * h + 2 * cw * ch].reshape(ch, cw)
    return y, u, v


def check(path):
    path = Path(path)
    inf = W.analyze(path)
    if "vp8" in inf:
        v = inf["vp8"]
        w, h = v["width"], v["height"]
        cw, ch = (w + 1) // 2, (h + 1) // 2
        for nf, tag in ((True, "_nofilter"), (False, "")):
            ry, ru, rv = dwebp_yuv(path, w, h, nf)
            my = np.array(v["Y" + tag], np.uint8)[:h, :w]
            mu = np.array(v["U" + tag], np.uint8)[:ch, :cw]
            mv = np.array(v["V" + tag], np.uint8)[:ch, :cw]
            bad = [int((a != b).sum()) for a, b in ((my, ry), (mu, ru), (mv, rv))]
            print(f"{path.name} VP8{' nofilter' if nf else ''}: 違う画素 Y/U/V = {bad}")
            assert bad == [0, 0, 0]
    if "vp8l" in inf:
        ref = np.asarray(Image.open(path).convert("RGBA"))
        mine = inf["vp8l"]["rgba"]
        bad = int((ref != mine).any(-1).sum())
        print(f"{path.name} VP8L: 違う画素 {bad} / {ref.shape[0] * ref.shape[1]}")
        assert bad == 0
    if "alph" in inf:
        ref = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
        bad = int((ref != inf["alph"]["alpha"]).sum())
        print(f"{path.name} ALPH: 違う画素 {bad}")
        assert bad == 0
    if "frames" in inf:
        im = Image.open(path)
        for k, fr in enumerate(inf["frames"]):
            if "vp8l" in fr:
                im.seek(k)
                print(f"{path.name} frame {k}: {fr['width']}x{fr['height']} at ({fr['x']},{fr['y']}) "
                      f"{fr['duration']}ms blend={fr['blend']} dispose={fr['dispose']}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        check(p)
