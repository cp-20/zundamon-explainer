# シーンのコード

各シーンは `videos/<name>/scenes/sNN_<題名>.py` に、`PScene` を継承したクラス `SNN` として書く。

```python
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]

from vlib.data import pixels, fmt          # その動画のデータ (videos/<name>/vlib/)  # noqa: E402
from zunda.fx import pop, underline        # 共通の強調                             # noqa: E402
from zunda.scene import *                  # PScene, px, u, jp, mix, mono, 色など     # noqa: E402,F403


class S05(PScene):
    def construct(self):
        self.at("row", -0.1)               # キュー "row" の 0.1 秒前まで待つ
        self.play(FadeIn(...), run_time=self.until("next"))
        self.finish()                      # 最後に必ず。シーンの長さまで待ち、記録を書く
```

## 部品 (`zunda/`)

| 名前 | 役目 |
|---|---|
| `PScene` | 基底クラス。`at(cue, offset)` キューの時刻まで待つ/`until(cue)` そこまでの残り秒数/`se(name)` 効果音 (1 シーン 3 回まで、意味のある瞬間だけ) /`finish()` |
| `px(x, y)`・`u(px)` | 画面の px (左上原点) → Manim の座標・長さ |
| `jp(s, size, color)`・`mix()` | 説明の文字 (和文フォント。size は px) |
| `mono(s, size, color)` | バイト列・16 進・ビット列 |
| `png_mob(arr, height, nearest=True)` | 画像。透明は市松模様 |
| 色 | `INK DIM BG CYAN YELLOW CORAL PURPLE BLUE ZCOL MCOL` |
| `zunda/fx.py` | `pop(m, scale, run_time)`、`underline(m, color)`、`Shake(m, amp)`、`retext(old, new)` (数字の書き換え。検査用の文字も更新) |

動画ごとの部品 (工程の地図、ブロックの表示など) は `videos/<name>/vlib/` に置く。

## キューと時刻

- キューの時刻は `bin/voice.sh` が作る `build/voice/SNN.json` の `lines[].cues`。
- 秒数を直接書かない (`self.at(12.3)`)。音声のタイミングを変えるとずれる。必要なら PLAN.md の台詞にキューを足す。
- 台詞の途中の位置は、台詞のキューからの相対 (`self.at("b5", 1.2)`) にするか、キューを足す。

## 検査への対応

- 一時的な写し (飛んでいくコピー)、数えている途中の数字、図の下敷きの画像など、検査に引っかかるが意図したものは `m.check_ignore = True`。
- 検査が 0 件でもシートとフレームを目で見る ([quality-checks.md](quality-checks.md))。

## Manim の落とし穴

| 症状 | 原因と対処 |
|---|---|
| グループを消したのに中身が残る | `LaggedStart(*[Transform(c, ...) for c in group])` のように中身を個別にアニメーションすると、中身が個別に場面に入る。`self.remove(group, *group)` で外す |
| 出したはずの文字が、出た直後に消える | 同じオブジェクトに `FadeIn` と `.animate` (`pop` も中身は `.animate`) を同じ `play` で重ねると、後のほうが上書きする。出してから次の `play` で強調する |
| 変形先のオブジェクトが動かない・色が変わらない | `TransformFromCopy(a, b)` は `b` そのものを場面に入れない。あとで `b` を動かすなら `ReplacementTransform(a.copy(), b)` |
| 画像が 1 フレームだけ消えて、ちらつく | 画像を含む `Group` の `FadeOut` で起きることがある。画像は `img.animate.set_opacity(0)` で消す (検査の「ちらつき」が見つける) |
| 小さい配列の画像の端がずれる・ぼやける | 小さい配列はドットを並べた大きな配列にしてから置く (`png_mob(..., nearest=True)`) |
| `ValueTracker` を使うと検査が落ちる | 検査は場面の全オブジェクトを調べる。更新関数で画像の中身を書き換える小さな `Animation` を書くほうが安全 |

## 動画ごとのデータ (`vlib/data.py`)

- 画像の画素、ファイルのバイト、解析器の結果を返す関数をまとめる。画面に出す数字はここからしか取らない。
- 解析器 (`videos/<name>/tools/*analyze.py`) は、形式を自前で読む。既存の実装と結果が一致することを確かめてから使う。
