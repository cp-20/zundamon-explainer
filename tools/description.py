"""概要欄（説明・チャプター・クレジット）を作る。チャプターの時刻は各シーンの音声の長さから計算する。

    ZX_VIDEO=gif uv run python tools/description.py  → videos/gif/build/out/description.txt

説明とチャプター名は videos/<name>/video.yaml（description / chapters / extra_credits）、
共通のクレジットは config/assets.yaml の credits。
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zunda.paths import BUILD, config, video_config  # noqa: E402
from zunda.script import load  # noqa: E402


def ts(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


def credit_lines():
    """[(項目, [名前...])]：共通のクレジット＋動画ごとの追加"""
    return [tuple(c) for c in config("assets")["credits"]] + [tuple(c) for c in video_config().get("extra_credits", [])]


def main():
    v = video_config()
    t = 0.0
    chapters = []
    for sid in load():
        chapters.append(f"{ts(t)} {v['chapters'][sid]}")
        t += json.loads((BUILD / "voice" / f"{sid}.json").read_text())["duration"]
    credits = "\n".join(f"{k}：{'、'.join(names)}" for k, names in credit_lines())
    text = f"""{v['description'].strip()}

■ チャプター
{chr(10).join(chapters)}

■ クレジット
{credits}
"""
    out = BUILD / "out" / "description.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
