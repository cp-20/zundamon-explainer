"""PLAN.md から台詞を読み出す。

`## S05 フィルタ` の見出しでシーンを区切り、`> Z: 本文` / `> M(笑): 本文` を台詞とする。
本文中の {cue} はキュー、[表記|よみ] は字幕と読みの使い分け、末尾の (+1.2) は台詞後の追加の間。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import ROOT, VIDEO, config

SPEAKERS = {k: v["name"] for k, v in config("characters")["speakers"].items()}

LINE_RE = re.compile(r"^>\s*([ZM])(?:\(([^)]*)\))?:\s*(.*?)\s*(?:\(\+([\d.]+)\))?\s*$")
HEAD_RE = re.compile(r"^##\s+(S\d\d)\s+(.*)$")
CUE_RE = re.compile(r"\{(\w+)\}")
RUBY_RE = re.compile(r"\[([^|\]]+)\|([^\]]+)\]")
# 英数字の前後のスペースは削る
SPACE_RE = re.compile(r"(?<=[0-9A-Za-z])[ 　]+(?![0-9A-Za-z])|(?<![0-9A-Za-z])[ 　]+(?=[0-9A-Za-z])")  # 和文と英数字の間の空白だけ消す（「255 255」は残す）


# 読み上げだけに効く読み替え（VOICEVOX が誤読する語）。字幕はそのまま。
# config/readings.yaml の reading_fix に、video.yaml の reading_fix を足したもの
def _reading_fix():
    from .paths import video_config
    try:
        extra = video_config().get("reading_fix") or []
    except RuntimeError:
        extra = []
    return [tuple(x) for x in config("readings")["reading_fix"]] + [tuple(x) for x in extra]


def fix_reading(s):
    for a, b in _reading_fix():
        s = re.sub(a, b, s)
    return s


@dataclass
class Line:
    scene: str
    index: int
    speaker: str  # "Z" / "M"
    expr: str
    raw: str  # キューと[表記|よみ]を含む元の文
    pause: float = 0.0

    @property
    def id(self):
        return f"{self.scene}_{self.index:02d}"

    def _strip(self, s):
        return SPACE_RE.sub("", s)

    @property
    def subtitle(self):
        return self._strip(RUBY_RE.sub(r"\1", CUE_RE.sub("", self.raw)))

    @property
    def speech(self):
        return fix_reading(self._strip(RUBY_RE.sub(r"\2", CUE_RE.sub("", self.raw))))

    def segments(self):
        """[(cue名 or None, 字幕上の前置き, 読み上げの前置き)] — 各キュー直前までの文"""
        out = []
        for m in CUE_RE.finditer(self.raw):
            pre = self.raw[: m.start()]
            out.append((m.group(1), self._strip(RUBY_RE.sub(r"\1", CUE_RE.sub("", pre))),
                        fix_reading(self._strip(RUBY_RE.sub(r"\2", CUE_RE.sub("", pre))))))
        return out


@dataclass
class Scene:
    id: str
    title: str
    lines: list = field(default_factory=list)


def load(path=None):
    """PLAN.md を読み、script/SNN.md があればそのシーンだけ差し替える（作業中のシーンの台詞はこちらで直す）"""
    vdir = VIDEO.resolve()
    res = _parse(Path(path or vdir / "PLAN.md").read_text())
    for p in sorted((vdir / "script").glob("S*.md")):
        res.update(_parse(p.read_text()))
    return dict(sorted(res.items()))


def _parse(text):
    scenes, cur = [], None
    for row in text.splitlines():
        if m := HEAD_RE.match(row):
            cur = Scene(m.group(1), m.group(2).split("（")[0].strip())
            scenes.append(cur)
        elif (m := LINE_RE.match(row)) and cur:
            sp, expr, body, pause = m.groups()
            cur.lines.append(Line(cur.id, len(cur.lines) + 1, sp, expr or "通常", body, float(pause or 0)))
    return {s.id: s for s in scenes}
