# AGENTS.md

ずんだもん (聞き手) と四国めたん (解説役) の掛け合いで、技術の仕組みを高校生にも分かるように解説する動画を、
Manim と VOICEVOX で作るためのリポジトリ。このファイルはエージェント向けの入口。

## まず読むもの (この順に)

1. [docs/workflow.md](docs/workflow.md) — 1 本の動画を作る流れと、人に確認を取るタイミング
2. [docs/script-writing.md](docs/script-writing.md) — 台詞の書き方 (PLAN.md の書式、2 人の役割、構成、間)
3. [docs/visual-design.md](docs/visual-design.md) — 画面の作り方 (分かりやすさの基準、レイアウト、文字、動き)
4. [docs/scene-code.md](docs/scene-code.md) — シーンのコードの書き方と Manim の落とし穴
5. 必要になったら：[docs/audio-and-subtitles.md](docs/audio-and-subtitles.md)、[docs/quality-checks.md](docs/quality-checks.md)、
   [docs/agents.md](docs/agents.md) (シーンを並行で作らせるとき)、[docs/publishing.md](docs/publishing.md) (タイトル・サムネ・公開)、
   [docs/setup.md](docs/setup.md) (環境づくり)

## リポジトリの地図

| 場所 | 中身 |
|---|---|
| `zunda/` | 全動画で共通の Python パッケージ (台詞の読み込み、音声、字幕、立ち絵の合成、音の仕上げ、Manim の基底クラス) |
| `config/` | 共通の設定 (YAML)。立ち絵と表情、声、読み、音、素材の一覧とクレジット |
| `tools/` | 共通の道具。検査 `check.py`、シート `sheet.py`、概要欄 `description.py`、素材の取得 `fetch_assets.py`、立ち絵の書き出し `export_psd_parts.py` |
| `bin/` | コマンド。`voice.sh` `render.sh` `pipeline.sh` `build_all.sh` (第 1 引数は動画の名前) |
| `videos/<name>/` | 動画ごとのもの。`video.yaml` (タイトル・チャプター・BGM・読みの追加)、`PLAN.md` (台詞と画面の計画)、`AGENT_BRIEF.md`、`scenes/`、`vlib/` (その動画だけの部品とデータの読み出し)、`tools/` (解析器・サムネ・データ作り)、`data/` |
| `docs/` | 知見。上の「まず読むもの」 |
| `assets/` | 素材 (BGM・効果音・フォント・立ち絵)。再配布できないのでリポジトリには入れない。`tools/fetch_assets.py` と docs/setup.md |

共通にできるものは `zunda/` と `config/` に、動画ごとに違うものは `videos/<name>/` に置く。
新しい動画で共通部品を直したら、過去の動画が壊れないか確かめる (docs/quality-checks.md の「通しの確かめ」)。

## コマンド

```bash
uv sync                                   # 依存 (Python は必ず uv 経由で動かす)
uv run python tools/fetch_assets.py       # BGM・効果音・フォント (立ち絵は docs/setup.md)
bin/voice.sh gif                          # 台詞の音声と時刻表 (VOICEVOX が必要)
bin/pipeline.sh gif S05                   # 1 シーンの試し (540p)：描画→合成→音→検査→シート
bin/build_all.sh gif                      # 通し (1080p)
```

## いつも守ること (詳しくは各 docs)

- 画面に出す数字は、すべて実データから計算する。台詞の数字と一致することをコードで `assert` する。
- 画面は台詞に合わせて動かす (台詞のキューの時刻に合わせる)。
- 図を見れば分かることを文字で説明しない。画面の文字は「いま話していること」だけ。
- ユーザーの指摘は、指摘された所だけを直す。広げて一般化しない (指示を過剰に読み取らない)。
- 報告では、確かめたことと確かめていないこと (音を聞いていない、動きを通しで見ていない、など) を分けて書く。
- 素材 (BGM・効果音・立ち絵、立ち絵から作った画像) はコミットしない。BGM の Content ID 登録は禁止。

## 文章のルール (README・docs・報告・Release の本文など)

- スラッシュは半角 `/`、かっこは半角 `()` を使う (全角の `／` `（）` は使わない)。
- 読めば分かること・自明な補足は書かない (同じ内容を 2 度書かない、当たり前の注意書きを添えない)。
- 動画の中の字幕・画面の文字は対象外 (台詞の書き方は docs/script-writing.md)。
