"""字幕：BudouX で文節に分けて最大2行に組み、白文字＋話者色の縁取り画像を作る。"""
import re
from functools import lru_cache

import budoux
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import binary_fill_holes

from .layout import COLOR, SUB_FONT, SUB_MAX_W, SUB_SIZE
from .paths import ROOT
from .script import CUE_RE, RUBY_RE, fix_reading

_parser = budoux.load_default_japanese_parser()
STROKE = 7
LINE_GAP = 8


@lru_cache(None)
def font(size=SUB_SIZE):
    return ImageFont.truetype(str(ROOT / SUB_FONT), size)


def width(s):
    return font().getlength(s)


END, COMMA = "。！？!?", "、，,…"
BAD_HEAD = "すするれらりっんゃゅょぁぃぅぇぉー"   # 前の文節にくっついているはずの頭（「動か|す」のような切れ目を避ける）


def _cut_cost(left, right, page):
    """left と right の間で切るときの不自然さ（小さいほど自然）"""
    a = left.rstrip()
    if a[-1:] in END or a.endswith("」") and a[-2:-1] in END:
        c = 0.0
    elif a[-1:] in COMMA:
        c = 1.0 if not page else 2.5
    else:
        c = 4.0 if not page else 9.0
    if right[:1] in BAD_HEAD:
        c += 6.0
    # かぎかっこの中では切らない
    if a.count("「") > a.count("」"):
        c += 6.0
    return c


def _line_split(chunks):
    """1 ページ分の文節 → (コスト, 行のリスト)。1 行で入ればそのまま"""
    s = "".join(chunks)
    if width(s) <= SUB_MAX_W:
        return 0.0, [s]
    best = None
    for i in range(1, len(chunks)):
        a, b = "".join(chunks[:i]), "".join(chunks[i:])
        wa, wb = width(a), width(b)
        if max(wa, wb) > SUB_MAX_W:
            continue
        c = _cut_cost(a, b, page=False)
        c += 1.5 * abs(wa - wb) / SUB_MAX_W          # 2 行の長さが釣り合っているほど良い
        if min(wa, wb) < 0.3 * SUB_MAX_W:
            c += 3.0                                  # 片方だけ極端に短い行は避ける
        if best is None or c < best[0]:
            best = (c, [a, b])
    return best if best else (None, None)


def _layout(chunks):
    return _line_split(chunks)[1]


def _paginate(chunks):
    """ページの切り方を全体で最も自然に（ページ数は少なく、文の切れ目で）"""
    n = len(chunks)
    INF = float("inf")
    dp = [(INF, None)] * (n + 1)
    dp[0] = (0.0, None)
    for j in range(1, n + 1):
        for i in range(j):
            if dp[i][0] == INF:
                continue
            lc, lines = _line_split(chunks[i:j])
            if lines is None:
                continue
            c = dp[i][0] + lc + 3.0                  # 1 ページ増えるごとに 3
            if len(lines) == 1 and width(lines[0]) < 0.35 * SUB_MAX_W and (i > 0 or j < n):
                c += 5.0                             # 「あ、」だけのような短すぎるページは避ける
            if i > 0:
                c += _cut_cost("".join(chunks[:i]), "".join(chunks[i:]), page=True)
            if c < dp[j][0]:
                dp[j] = (c, i)
    if dp[n][0] == INF:
        raise ValueError("字幕に入らない: " + "".join(chunks))
    cuts, j = [], n
    while j > 0:
        i = dp[j][1]
        cuts.append((i, j))
        j = i
    return [chunks[i:j] for i, j in reversed(cuts)]


def _sub_to_speech_prefix(line, n):
    """字幕の先頭 n 文字ぶんに対応する読み上げの前置き"""
    out_sub, out_sp, i, raw = 0, [], 0, line.raw
    while out_sub < n and i < len(raw):
        if m := CUE_RE.match(raw, i):
            i = m.end(); continue
        if m := RUBY_RE.match(raw, i):
            out_sub += len(m.group(1)); out_sp.append(m.group(2)); i = m.end(); continue
        out_sub += 1; out_sp.append(raw[i]); i += 1
    return fix_reading(line._strip("".join(out_sp)))


def pages_for(line):
    """[(ページ文字列 '行1\\n行2', 読み上げの前置き)]"""
    chunks = _parser.parse(line.subtitle)
    res, n = [], 0
    for pg in _paginate(chunks):
        res.append(("\n".join(l.strip() for l in _layout(pg)), _sub_to_speech_prefix(line, n) if n else ""))
        n += sum(len(c) for c in pg)
    return res


def render(text, speaker):
    """字幕画像（RGBA）。中央揃え。"""
    f = font()
    lines = text.split("\n")
    asc, desc = f.getmetrics()
    lh = asc + desc
    pad = STROKE + 6
    wmax = int(max(width(l) for l in lines)) + 2 * pad
    h = lh * len(lines) + LINE_GAP * (len(lines) - 1) + 2 * pad
    col = COLOR[speaker]
    outline = Image.new("L", (wmax, h), 0)
    fill = Image.new("L", (wmax, h), 0)
    do, df = ImageDraw.Draw(outline), ImageDraw.Draw(fill)
    for k, l in enumerate(lines):
        x = (wmax - width(l)) / 2
        y = pad + k * (lh + LINE_GAP)
        do.text((x, y), l, font=f, fill=255, stroke_width=STROKE, stroke_fill=255)
        df.text((x, y), l, font=f, fill=255)
    o = np.asarray(outline) > 127
    o = binary_fill_holes(o)  # 閉じた隙間も縁取り色で塗る
    oa = np.asarray(Image.fromarray((o * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)))
    fa = np.asarray(fill).astype(np.float32) / 255
    rgb = np.empty((h, wmax, 3), np.float32)
    rgb[:] = col
    rgb = rgb * (1 - fa[..., None]) + 255 * fa[..., None]
    a = np.maximum(oa.astype(np.float32) / 255, fa)
    img = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA")
    # ごく薄い影で背景から浮かせる
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(Image.fromarray((a * 110).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)))
    base = Image.new("RGBA", (wmax + 8, h + 8), (0, 0, 0, 0))
    base.alpha_composite(sh, (4, 6))
    base.alpha_composite(img, (0, 0))
    return base
