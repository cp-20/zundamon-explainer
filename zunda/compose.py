"""Manim の映像に立ち絵（口パク・まばたき）と字幕を重ねる。

    uv run python -m zunda.compose S05 [--preview]
入力: build/render/<S>.mp4, build/voice/<S>.json  出力: build/comp/<S>.mp4（映像のみ）
"""
import json, random, subprocess, sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from . import character, subtitle
from .layout import CHAR, FPS, H, SUB_BOX, W
from .paths import BUILD, config


# 表情 → レイヤーの選択（config/characters.yaml）。キーは parts.json のグループパス
_SP = config("characters")["speakers"]
EXPR = {k: v["expressions"] for k, v in _SP.items()}
BASE = {k: v["base"] for k, v in _SP.items()}
MOUTH = {k: v["mouth"] for k, v in _SP.items()}
BLINK = {k: v["blink"] for k, v in _SP.items()}
NO_BLINK = {(k, e) for k, v in _SP.items() for e in v.get("no_blink", [])}


@lru_cache(None)
def sprite(sp, expr, mouth, blink):
    st = dict(BASE[sp]); st.update(EXPR[sp].get(expr, {}))
    st["!口"] = MOUTH[sp][mouth]
    if blink:
        st.update(BLINK[sp])
    c = CHAR[sp]
    im = character.render(c["name"], st)
    w, h = im.size
    im = im.resize((round(w * c["scale"]), round(h * c["scale"])), Image.LANCZOS)
    if c.get("flip"):
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    a = np.asarray(im).astype(np.float32)
    a[..., 3] /= 255
    bb = im.getbbox()  # 透明な余白は切って位置だけ覚える
    return a[bb[1]:bb[3], bb[0]:bb[2]], bb[0], bb[1]


def blend(frame, rgba, x, y):
    """frame: HxWx3 uint8, rgba: hxwx4 float（色は 0-255、α は 0-1）を (x,y) に置く（はみ出しは切る）"""
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4]
    region = frame[y0:y1, x0:x1].astype(np.float32)
    region *= 1 - a
    region += s[..., :3] * a
    frame[y0:y1, x0:x1] = region + 0.5


def mouth_track(tl, n):
    """各話者の各フレームの口の形"""
    res = {"Z": ["closed"] * n, "M": ["closed"] * n}
    for ln in tl["lines"]:
        tr = res[ln["speaker"]]
        for vowel, cs, vs, e in ln["moras"]:
            for f in range(int(cs * FPS), min(int(e * FPS) + 1, n)):
                t = (f + 0.5) / FPS
                if not (cs <= t < e):
                    continue
                if vowel in ("pau", "N", "cl"):
                    m = "closed"
                elif t < vs:
                    m = "half"
                else:
                    m = "open" if vowel in "aeoA" else "half"
                tr[f] = m
    # 1フレームだけの閉じ/開きはちらつくので埋める
    for tr in res.values():
        for f in range(1, n - 1):
            if tr[f - 1] == tr[f + 1] != tr[f]:
                tr[f] = tr[f - 1]
    return res


def expr_track(tl, n):
    """各話者の表情：自分の台詞の間はその表情、それ以外は直前の表情を少し保ってから通常に戻す"""
    res = {"Z": ["通常"] * n, "M": ["通常"] * n}
    for ln in tl["lines"]:
        f0, f1 = int(ln["start"] * FPS), min(int((ln["end"] + 1.2) * FPS), n)
        for f in range(f0, f1):
            res[ln["speaker"]][f] = ln["expr"]
    return res


def blink_track(scene_id, n):
    res = {}
    for sp in "ZM":
        rng = random.Random(f"{scene_id}{sp}")
        tr = [False] * n
        f = int(rng.uniform(1.0, 3.0) * FPS)
        while f < n:
            for k in range(3):
                if f + k < n:
                    tr[f + k] = True
            f += int(rng.uniform(2.5, 5.5) * FPS)
        res[sp] = tr
    return res


def bounce(tl, sp, f):
    """話し始めに少し跳ねる（px）"""
    t = f / FPS
    for ln in tl["lines"]:
        if ln["speaker"] == sp and 0 <= t - ln["start"] < 0.3:
            x = (t - ln["start"]) / 0.3
            return -10 * np.sin(np.pi * x)
    return 0.0


def sub_track(tl, n):
    """各フレームの (ページ文字列, 話者)。台詞間の短い隙間は前の字幕を保つ"""
    res = [None] * n
    lines = tl["lines"]
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else tl["duration"]
        end = nxt if nxt - ln["voice_end"] < 0.7 else ln["voice_end"] + 0.3
        pages = ln["pages"]
        for k, pg in enumerate(pages):
            t0 = pg["t"]
            t1 = pages[k + 1]["t"] if k + 1 < len(pages) else end
            for f in range(int(t0 * FPS), min(int(t1 * FPS), n)):
                res[f] = (pg["text"], ln["speaker"])
    return res


@lru_cache(None)
def sub_image(text, sp):
    a = np.asarray(subtitle.render(text, sp)).astype(np.float32)
    a[..., 3] /= 255
    return a


def compose(sid, src=None, dst=None, scale=1.0):
    tl = json.loads((BUILD / "voice" / f"{sid}.json").read_text())
    src = src or BUILD / "render" / f"{sid}.mp4"
    dst = dst or BUILD / "comp" / f"{sid}.mp4"
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    n = int(round(tl["duration"] * FPS))
    mouths, exprs, blinks, subs = mouth_track(tl, n), expr_track(tl, n), blink_track(sid, n), sub_track(tl, n)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-vf", f"scale={W}:{H}:flags=bicubic", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-vf", f"scale={ow}:{oh}:flags=lanczos", "-c:v", "libx264",
                            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(dst)], stdin=subprocess.PIPE)
    last = None
    for f in range(n):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            buf = last  # 映像が短ければ最後のフレームを伸ばす
        last = buf
        frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        for sp in "ZM":
            ex = exprs[sp][f]
            bl = blinks[sp][f] and (sp, ex) not in NO_BLINK
            spr, ox, oy = sprite(sp, ex, mouths[sp][f], bl)
            c = CHAR[sp]
            blend(frame, spr, c["x"] + ox, int(round(c["y"] + oy + bounce(tl, sp, f))))
        if subs[f]:
            img = sub_image(*subs[f])
            h, w = img.shape[:2]
            x = (SUB_BOX[0] + SUB_BOX[2] - w) // 2
            y = SUB_BOX[3] - h
            blend(frame, img, x, y)
        enc.stdin.write(frame.tobytes())
    enc.stdin.close(); enc.wait(); dec.kill()
    return dst


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for sid in args:
        print(compose(sid, scale=0.5 if "--preview" in sys.argv else 1.0))
