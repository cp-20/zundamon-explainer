"""リポジトリと「いま作っている動画」の場所、設定ファイルの読み込み。

動画は videos/<name>/ に置き、環境変数 ZX_VIDEO で選ぶ（bin/*.sh が設定する）。
共通の設定は config/*.yaml、動画ごとの設定は videos/<name>/video.yaml。
"""
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
ASSETS = ROOT / "assets"
CACHE = ROOT / "cache"


def _video_dir():
    v = os.environ.get("ZX_VIDEO")
    if not v:
        raise RuntimeError("ZX_VIDEO が未設定（例: ZX_VIDEO=gif、bin/*.sh 経由で実行する）")
    p = Path(v)
    return p.resolve() if p.is_absolute() or p.exists() else (ROOT / "videos" / v).resolve()


class _Lazy:
    """VIDEO / BUILD を import 時ではなく使うときに決める（ZX_VIDEO なしでも import できるように）"""

    def __init__(self, f):
        self._f = f

    def __truediv__(self, other):
        return self._f() / other

    def __fspath__(self):
        return str(self._f())

    def __str__(self):
        return str(self._f())

    def resolve(self):
        return self._f()


VIDEO = _Lazy(_video_dir)
BUILD = _Lazy(lambda: _video_dir() / "build")


@lru_cache(None)
def config(name):
    """config/<name>.yaml"""
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text())


@lru_cache(None)
def video_config():
    """videos/<name>/video.yaml"""
    p = _video_dir() / "video.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def merged(name, key=None):
    """共通の設定に、動画ごとの上書き（video.yaml の同じ名前の節）を重ねたもの"""
    base = dict(config(name))
    over = video_config().get(key or name) or {}
    base.update(over)
    return base
