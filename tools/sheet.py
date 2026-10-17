"""画面の状態ごとのフレームと、その時の台詞を並べたシートを作る。

    uv run python tools/sheet.py S05   → build/sheet/S05.png
状態 = 各アニメーションが終わって落ち着いた瞬間（build/log の play の終わり）。
"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zunda.paths import BUILD, ROOT  # noqa: E402
TW, TH = 576, 324
FONT = ImageFont.truetype(str(ROOT / "assets/fonts/MPLUSRounded1c-Bold.ttf"), 17)


def frame_at(video, t):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={TW}:{TH}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    return Image.frombytes("RGB", (TW, TH), p.stdout)


def speaking(tl, t):
    for ln in tl["lines"]:
        if ln["start"] - 0.05 <= t <= ln["end"] + 0.4:
            return ln
    return None


def main(sid, video=None):
    video = video or BUILD / "comp" / f"{sid}.mp4"
    log = json.loads((BUILD / "log" / f"{sid}.json").read_text())
    tl = json.loads((BUILD / "voice" / f"{sid}.json").read_text())
    # play の終わりのうち、次の play まで 0.25 秒以上止まるもの（＝見える状態）
    plays = [p for p in log["plays"] if p["anims"] != ["Wait"]]
    times = []
    for i, p in enumerate(plays):
        nxt = plays[i + 1]["t0"] if i + 1 < len(plays) else log["end"]
        if nxt - p["t1"] >= 0.25:
            times.append(min(p["t1"] + 0.1, nxt - 0.02))
    cols = 4
    rows = (len(times) + cols - 1) // cols
    cap_h = 64
    sheet = Image.new("RGB", (cols * TW, rows * (TH + cap_h)), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    for k, t in enumerate(times):
        x, y = (k % cols) * TW, (k // cols) * (TH + cap_h)
        sheet.paste(frame_at(video, t), (x, y))
        ln = speaking(tl, t)
        txt = f"{t:6.2f}s  " + (f"{ln['id'][-2:]} {ln['speaker']}: {ln['text']}" if ln else "（無音）")
        # 長い台詞は折り返す
        lines, cur = [], ""
        for ch in txt:
            if FONT.getlength(cur + ch) > TW - 12:
                lines.append(cur); cur = ""
            cur += ch
        lines.append(cur)
        for j, l in enumerate(lines[:3]):
            d.text((x + 6, y + TH + 3 + j * 20), l, fill=(20, 20, 20), font=FONT)
    out = BUILD / "sheet"
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / f"{sid}.png")
    print(out / f"{sid}.png", len(times), "states")


if __name__ == "__main__":
    for s in sys.argv[1:]:
        main(s, BUILD / "out" / f"{s}.mp4" if (BUILD / "out" / f"{s}.mp4").exists() else None)
