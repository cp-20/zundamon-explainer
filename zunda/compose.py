"""Manim の映像に立ち絵（口パク・まばたき）と字幕を重ねる。

    uv run python -m zunda.compose S05 [--preview]
入力: build/render/<S>.mp4, build/voice/<S>.json  出力: build/comp/<S>.mp4（映像のみ）
"""
import json, os, random, subprocess, sys
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


_SLOT = None


def nvenc_slot():
    """NVENC の同時に使える数には上限がある（家庭用の GPU は数本）。cache/nvenc/ のロックファイルで席を取り、
    取れたらそのプロセスが終わるまで持つ。取れなければ None（CPU で書き出す）。"""
    global _SLOT
    if _SLOT is not None:
        return _SLOT
    import fcntl
    from .paths import CACHE
    d = CACHE / "nvenc"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(int(config("render").get("nvenc_sessions", 3))):
        fh = open(d / f"slot{i}", "w")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _SLOT = fh
            return fh
        except OSError:
            fh.close()
    return None


def use_nvenc():
    """この処理で NVENC を使うか（config/render.yaml の encoder、GPU があるか、席が空いているか）"""
    enc = config("render").get("encoder", "auto")
    if enc == "x264":
        return False
    return _has_nvenc() and nvenc_slot() is not None


def encoder_args():
    """ffmpeg の書き出しの引数。NVENC が使えれば GPU、だめなら x264"""
    r = config("render")
    if use_nvenc():
        n = r["nvenc"]
        return ["-c:v", "h264_nvenc", "-preset", n["preset"], "-rc", "vbr", "-cq", str(n["cq"]), "-b:v", "0"]
    x = r["x264"]
    return ["-c:v", "libx264", "-preset", x["preset"], "-crf", str(x["crf"])]


@lru_cache(None)
def _has_nvenc():
    """h264_nvenc で 1 フレーム書けるか（ドライバや GPU がないと失敗する）。並行の子プロセスには ZX_NVENC で伝える"""
    import os
    if os.environ.get("ZX_NVENC") in ("0", "1"):
        return os.environ["ZX_NVENC"] == "1"
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1", "-c:v", "h264_nvenc",
                        "-f", "null", "-"], capture_output=True)
    return p.returncode == 0


@lru_cache(None)
def sprite(sp, expr, mouth, blink, scale=1.0):
    """立ち絵 1 枚（表情・口・まばたき・大きさ）。PSD の部品から作るのは重いので cache/sprites/ にも残す"""
    import hashlib
    from .paths import ASSETS, CACHE
    c = CHAR[sp]
    tree = ASSETS / "characters" / c["name"] / "parts.json"
    key = json.dumps([sp, expr, mouth, blink, scale, c, BASE[sp], EXPR[sp].get(expr), MOUTH[sp], BLINK[sp],
                      tree.stat().st_mtime], ensure_ascii=False, sort_keys=True, default=str)
    p = CACHE / "sprites" / (hashlib.sha1(key.encode()).hexdigest()[:20] + ".npz")
    if p.exists():
        z = np.load(p)
        return (z["col"], z["inv"]), int(z["ox"]), int(z["oy"])
    (col, inv), ox, oy = _sprite(sp, expr, mouth, blink, scale)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}.npz")
    np.savez(tmp, col=col, inv=inv, ox=ox, oy=oy)
    os.replace(tmp, p)
    return (col, inv), ox, oy


def _sprite(sp, expr, mouth, blink, scale):
    st = dict(BASE[sp]); st.update(EXPR[sp].get(expr, {}))
    st["!口"] = MOUTH[sp][mouth]
    if blink:
        st.update(BLINK[sp])
    c = CHAR[sp]
    im = character.render(c["name"], st)
    w, h = im.size
    im = im.resize((round(w * c["scale"] * scale), round(h * c["scale"] * scale)), Image.LANCZOS)
    if c.get("flip"):
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    bb = im.getbbox()  # 透明な余白は切って位置だけ覚える
    return premul(np.asarray(im)[bb[1]:bb[3], bb[0]:bb[2]]), bb[0], bb[1]


def premul(rgba):
    """RGBA(uint8) → (色×α, 255−α)。合成を整数の掛け算 1 回と足し算 1 回にするための前計算"""
    a = rgba[..., 3:4].astype(np.uint16)
    return (rgba[..., :3].astype(np.uint16) * a, (255 - a))


def blend(frame, pm, x, y, W=W, H=H):
    """frame: HxWx3 uint8 に、premul() 済みの画像を (x, y) に置く（はみ出しは切る）"""
    col, inv = pm
    h, w = col.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    sl = (slice(y0 - y, y1 - y), slice(x0 - x, x1 - x))
    region = frame[y0:y1, x0:x1]
    out = region.astype(np.uint16)
    out *= inv[sl]
    out += col[sl]
    out += 127
    out //= 255
    region[...] = out


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
def sub_image(text, sp, scale=1.0):
    im = subtitle.render(text, sp)
    if scale != 1.0:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    return premul(np.asarray(im))


class Overlay:
    """1 シーンぶんの立ち絵（口パク・まばたき・表情・跳ね）と字幕を、フレームの番号から重ねる。
    """

    def __init__(self, sid, scale=1.0):
        self.tl = tl = json.loads((BUILD / "voice" / f"{sid}.json").read_text())
        self.n = n = int(round(tl["duration"] * FPS))
        self.scale = scale
        self.mouths, self.exprs = mouth_track(tl, n), expr_track(tl, n)
        self.blinks, self.subs = blink_track(sid, n), sub_track(tl, n)

    def apply(self, frame, f):
        """frame：(高さ, 幅, 3 または 4) の uint8。f 番目のフレームの重ねものをその場で描く"""
        f = min(max(f, 0), self.n - 1)
        oh, ow = frame.shape[:2]
        rgb = frame[..., :3]
        s = self.scale
        for sp in "ZM":
            ex = self.exprs[sp][f]
            bl = self.blinks[sp][f] and (sp, ex) not in NO_BLINK
            spr, ox, oy = sprite(sp, ex, self.mouths[sp][f], bl, s)
            c = CHAR[sp]
            blend(rgb, spr, round(c["x"] * s) + ox, int(round((c["y"] + bounce(self.tl, sp, f)) * s)) + oy, ow, oh)
        if self.subs[f]:
            img = sub_image(*self.subs[f], s)
            h, w = img[0].shape[:2]
            blend(rgb, img, round((SUB_BOX[0] + SUB_BOX[2]) * s / 2) - w // 2, round(SUB_BOX[3] * s) - h, ow, oh)
        return frame


def compose(sid, src=None, dst=None, scale=1.0, f0=0, f1=None):
    """Manim の映像 src（f0 番目のフレームから始まる）に立ち絵と字幕を重ねて dst に書く。
    f1 まで（既定はシーンの終わり）ちょうどの枚数にする（映像が短ければ最後のフレームをのばす）。
    scale は出力の大きさ（0.5 なら 960×540）。src の大きさは出力に合わせて拡大・縮小する。"""
    src = src or BUILD / "render" / f"{sid}.mp4"
    dst = dst or BUILD / "comp" / f"{sid}.mp4"
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    ov = Overlay(sid, scale)
    f1 = ov.n if f1 is None else min(f1, ov.n)
    ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-vf", f"scale={ow}:{oh}:flags=bicubic",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    args = encoder_args()
    nv = "h264_nvenc" in args
    # NVENC には RGB をそのまま渡し、色の変換は GPU にまかせる。x264 は ffmpeg が YUV に変換する
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb0" if nv else "rgb24",
                            "-s", f"{ow}x{oh}", "-r", str(FPS), "-i", "-", *args,
                            *([] if nv else ["-pix_fmt", "yuv420p"]), str(dst)], stdin=subprocess.PIPE)
    fs = ow * oh * 3
    last = None
    out = np.empty((oh, ow, 4), np.uint8) if nv else None
    for f in range(f0, f1):
        buf = dec.stdout.read(fs)
        if len(buf) < fs:
            buf = last  # 映像が短ければ最後のフレームを伸ばす
        last = buf
        if nv:
            out[..., :3] = np.frombuffer(buf, np.uint8).reshape(oh, ow, 3)
            enc.stdin.write(ov.apply(out, f).data)
        else:
            frame = np.frombuffer(buf, np.uint8).reshape(oh, ow, 3).copy()
            enc.stdin.write(ov.apply(frame, f).data)
    enc.stdin.close(); enc.wait(); dec.kill()
    return dst


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for sid in args:
        print(compose(sid, scale=0.5 if "--preview" in sys.argv else 1.0))
