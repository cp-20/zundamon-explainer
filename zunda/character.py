"""坂本アヒル式 PSD 書き出し（parts.json + PNG）から立ち絵を合成する。

state は {"グループパス": "選ぶ子の名前"} の辞書。'*' で始まる子はラジオ式（1つだけ表示）。
指定のないグループは PSD 既定の表示状態を使う。extra は追加で表示する非ラジオ層のパス集合。
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from .paths import ASSETS

CHAR_DIR = ASSETS / "characters"


@lru_cache(None)
def _tree(name):
    return json.loads((CHAR_DIR / name / "parts.json").read_text())


@lru_cache(None)
def _layer(name, file):
    return Image.open(CHAR_DIR / name / "parts" / file).convert("RGBA")


def _multiply(base, layer, off):
    x, y = off
    w, h = layer.size
    b = np.asarray(base.crop((x, y, x + w, y + h))).astype(np.float32) / 255
    l = np.asarray(layer).astype(np.float32) / 255
    a = l[..., 3:4]
    rgb = b[..., :3] * (1 - a) + b[..., :3] * l[..., :3] * a
    out = np.concatenate([rgb, b[..., 3:4]], -1)
    base.paste(Image.fromarray((out * 255).astype(np.uint8)), (x, y))


def render(name, state=None, extra=(), hide=()):
    state = state or {}
    t = _tree(name)
    canvas = Image.new("RGBA", tuple(t["size"]), (0, 0, 0, 0))

    def visible(node, parent_path):
        n = node["name"]
        if node["path"] in hide:
            return False
        if node["path"] in extra:
            return True
        if n.startswith("*") and parent_path in state:
            return n[1:] == state[parent_path]
        if n.startswith("!"):
            return True
        return node["visible"]

    def draw(node, parent_path=""):
        for ch in node.get("children", []):  # 下の層から順に並んでいる
            if not visible(ch, parent_path):
                continue
            if "file" in ch:
                im = _layer(name, ch["file"])
                if ch.get("blend") == "multiply":
                    _multiply(canvas, im, ch["offset"])
                else:
                    canvas.alpha_composite(im, tuple(ch["offset"]))
            if ch.get("children"):
                draw(ch, ch["path"])

    draw(t)
    return canvas
