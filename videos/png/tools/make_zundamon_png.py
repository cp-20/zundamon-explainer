"""data/zundamon.png（題材にする「ずんだもんの画像」）を立ち絵の部品から作る。

    uv run python videos/png/tools/make_zundamon_png.py

公開版で使った画像は立ち絵素材から作ったもので、再配布できないためリポジトリに入れていない。
これで作る画像は公開版とは別物になる（キャンバス全体・既定の表情で書き出す）。大きさ・フィルタの数などの
数字が変わるので、scenes の assert と PLAN.md の台詞の数字を、新しい画像に合わせて直すこと。
"""
import sys
from pathlib import Path

VDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VDIR.parents[1]))
from zunda import character  # noqa: E402
from zunda.compose import BASE  # noqa: E402


def main():
    im = character.render("zundamon", dict(BASE["Z"]))
    out = VDIR / "data" / "zundamon.png"
    im.save(out, optimize=True)
    print(out, im.size, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
