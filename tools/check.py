"""画面の機械的な検査。build/log/<S>.json（Manim が残した各状態の外接矩形）と台詞の時刻表を見る。

    uv run python tools/check.py S05 [S06 ...]

検出するもの
- はみ出し：画面の外 / 立ち絵・字幕の領域への侵入
- 重なり：文字どうし、文字と枠線、閉じた枠線どうしの交差
- 一瞬だけ出る文字：表示時間が読むのに足りない文字
- ずれ：キューに間に合わなかったアニメーション、台詞中に長く止まった画面、長さの不一致
"""
import json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zunda.paths import BUILD, ROOT  # noqa: E402
from zunda.layout import CHAR, H, MARGIN, SUB_BOX, W  # noqa: E402

CLOSED = {"Rectangle", "Square", "RoundedRectangle", "Circle", "Ellipse", "Polygon", "RegularPolygon",
          "Triangle", "SurroundingRectangle", "BackgroundRectangle"}


def forbidden_mask():
    p = BUILD / "check" / "mask.npy"
    if p.exists():
        return np.load(p)
    from zunda.compose import EXPR, sprite
    m = np.zeros((H, W), bool)
    for sp in "ZM":
        c = CHAR[sp]
        for ex in EXPR[sp]:
            for mo in ("closed", "half", "open"):
                a, ox, oy = sprite(sp, ex, mo, False)
                al = a[..., 3] > 0.1
                x, y = c["x"] + ox, c["y"] + oy - 10  # 話し始めの跳ねの分
                h, w = al.shape
                ys, xs = slice(max(y, 0), min(y + h, H)), slice(max(x, 0), min(x + w, W))
                m[ys, xs] |= al[ys.start - y:ys.stop - y, xs.start - x:xs.stop - x]
    from scipy.ndimage import binary_dilation
    m = binary_dilation(m, iterations=14)
    x0, y0, x1, y1 = SUB_BOX
    m[y0:y1, x0:x1] = True
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, m)
    return m


def inter(a, b, pad=0):
    x0, y0 = max(a[0], b[0]) + pad, max(a[1], b[1]) + pad
    x1, y1 = min(a[2], b[2]) - pad, min(a[3], b[3]) - pad
    return max(0, x1 - x0) * max(0, y1 - y0)


def area(a):
    return max(0, a[2] - a[0]) * max(0, a[3] - a[1])


def contains(a, b, tol=3):
    return a[0] - tol <= b[0] and a[1] - tol <= b[1] and a[2] + tol >= b[2] and a[3] + tol >= b[3]


def jumps(video):
    """前後はほとんど動いていないのに、1 フレームだけ画面が大きく変わる所（消し方の不具合でのちらつき）"""
    import subprocess
    if not video.exists():
        return []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "scale=96:54,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(float)
    d = np.abs(np.diff(a, axis=0)).mean((1, 2))
    out = []
    for i, v in enumerate(d):
        around = max(d[max(0, i - 2):i].max(initial=0), d[i + 1:i + 3].max(initial=0))
        if v > 6 and v > 4 * around:
            out.append((round((i + 1) / 30, 2), float(v)))
    return out


def check(sid):
    log = json.loads((BUILD / "log" / f"{sid}.json").read_text())
    tl = json.loads((BUILD / "voice" / f"{sid}.json").read_text())
    mask = forbidden_mask()
    issues = []
    seen = set()

    def add(kind, t, msg):
        key = (kind, msg)
        if key not in seen:
            seen.add(key)
            issues.append((t, kind, msg))

    def name(it):
        return f"「{it['text']}」" if it.get("text") else f"{it['kind']}:{it.get('cls', '')}"

    for st in log["states"]:
        if st["t1"] - st["t0"] < 0.05 and st["kind"] == "wait":
            continue
        t = st["t1"]
        items = [it for it in st["items"] if it["bbox"]]
        for it in items:
            b = it["bbox"]
            if b[0] < MARGIN - 4 or b[1] < MARGIN - 4 or b[2] > W - MARGIN + 4 or b[3] > H - MARGIN + 4:
                add("はみ出し", t, f"{name(it)} が画面の端 {[round(v) for v in b]}")
            x0, y0, x1, y1 = [int(round(v)) for v in b]
            sub = mask[max(y0, 0):max(min(y1, H), 0), max(x0, 0):max(min(x1, W), 0)]
            if sub.size and sub.mean() > 0.002:
                add("領域侵入", t, f"{name(it)} が立ち絵/字幕の領域に入る {[round(v) for v in b]}")
        texts = [it for it in items if it["kind"] == "text"]
        for tx in texts:
            h = tx["bbox"][3] - tx["bbox"][1]
            # 22px 未満の文字。字形の高さは 漢字かな≈0.85em、数字・大文字≈0.7em、小文字≈0.5em
            txt = tx.get("text") or ""
            if any(ord(ch) > 0x3000 for ch in txt):
                need = 0.75 * 22  # かなは漢字より背が低い
            elif any(ch.isdigit() or ch.isupper() for ch in txt):
                need = 0.68 * 22
            elif any(ch.isalpha() for ch in txt):
                need = 0.48 * 22
            else:
                need = 0
            if h < need - 0.5:
                add("小さい文字", t, f"{name(tx)} の高さ {h:.0f}px（22px 以上の大きさにする）")
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                a, b = texts[i]["bbox"], texts[j]["bbox"]
                ov = inter(a, b, 2)
                if ov > 0.08 * min(area(a), area(b)):
                    add("文字の重なり", t, f"{name(texts[i])} と {name(texts[j])}")
        strokes = [it for it in items if it["kind"] == "shape" and it.get("stroke", 0) > 0]
        for tx in texts:
            for sh in strokes:
                if inter(tx["bbox"], sh["bbox"], 2) > 0 and not contains(sh["bbox"], tx["bbox"]) \
                        and sh.get("cls") in CLOSED:
                    add("文字と枠線", t, f"{name(tx)} が {sh.get('cls')} の線にかかる")
        for tx in texts:
            for im in items:
                if im["kind"] in ("image", "group") and inter(tx["bbox"], im["bbox"], 2) > 0:
                    add("文字と図", t, f"{name(tx)} が {im['kind']} {[round(v) for v in im['bbox']]} に重なる")
        closed = [s for s in strokes if s.get("cls") in CLOSED]
        for i in range(len(closed)):
            for j in range(i + 1, len(closed)):
                a, b = closed[i]["bbox"], closed[j]["bbox"]
                if inter(a, b, 2) > 0 and not contains(a, b) and not contains(b, a):
                    add("枠線の交差", t, f"{closed[i]['cls']} {[round(v) for v in a]} と {closed[j]['cls']} {[round(v) for v in b]}")

    # 一瞬だけ出る文字
    life = defaultdict(float)
    first = {}
    for st in log["states"]:
        for it in st["items"]:
            if it["kind"] == "text":
                k = (it["id"], it["text"])
                life[k] += st["t1"] - st["t0"]
                first.setdefault(k, st["t0"])
    for (i, txt), d in life.items():
        need = max(1.0, 0.12 * len(txt or ""))
        if d < need:
            add("一瞬の文字", first[(i, txt)], f"「{txt}」が {d:.2f}s しか出ない（{need:.1f}s 必要）")

    # 同期
    for lt in log["late"]:
        add("遅れ", lt["t"], f"キュー {lt['cue']} に {lt['by']:.2f}s 遅れた")
    moves = [p for p in log["plays"] if p["anims"] != ["Wait"]]
    for ln in tl["lines"]:
        a, b = ln["start"], ln["voice_end"]
        ts = sorted([a] + [p["t0"] for p in moves if a <= p["t0"] <= b] + [p["t1"] for p in moves if a <= p["t1"] <= b] + [b])
        gap = max(y - x for x, y in zip(ts, ts[1:]))
        if gap > 6.0:
            add("止まった画面", a, f"{ln['id']} の台詞中 {gap:.1f}s 画面が動かない")
    if abs(log.get("end", 0) - tl["duration"]) > 0.1:
        add("長さ", 0, f"映像 {log.get('end')}s と音声 {tl['duration']}s が合わない")
    for t, v in jumps(BUILD / "render" / f"{sid}.mp4"):
        add("ちらつき", t, f"1 フレームで画面が急に変わる（差 {v:.0f}）。消える・出るが一瞬で起きていないか")

    issues.sort()
    out = BUILD / "check"
    out.mkdir(parents=True, exist_ok=True)
    txt = "\n".join(f"{t:7.2f}s [{k}] {m}" for t, k, m in issues)
    (out / f"{sid}.txt").write_text(txt + "\n")
    print(f"== {sid}: {len(issues)} 件")
    print(txt)
    return issues


if __name__ == "__main__":
    for s in sys.argv[1:]:
        check(s)
