# PNG 編

**6.9MBの画像が333KBに！？1バイトも消えないPNG圧縮の仕組み【ずんだもん解説】** — https://youtu.be/BhYgIYsvkBo
（約 18 分、10 シーン。動画ファイルは Release `png-v1`）

ずんだもんの立ち絵の PNG（約 690 万バイトの画素が 333,074 バイト）を 1 バイトずつのぞき、
シグネチャ → チャンク → フィルタ → LZ77 → ハフマン符号 → DEFLATE → 4 枚の画像での実験、の順に解説する。

## ファイル

| 場所 | 中身 |
|---|---|
| `PLAN.md` | 台詞と画面の計画 |
| `AGENT_BRIEF.md` | シーン担当に渡した指示（記録） |
| `scenes/` | S01〜S10。見本は `s05_filter.py` |
| `vlib/data.py` | 画素・チャンク・フィルタ後のデータ、解析結果の読み出し |
| `vlib/pmap.py` | 工程の地図（画素 → フィルタ → LZ77 → ハフマン → zlib → IDAT） |
| `vlib/style.py` | フィルタ 5 種の色と名前 |
| `tools/pnganalyze.py` | 自前の PNG 読み取り（inflate を自前で実装。LZ77 のトークン・ハフマン表まで取り出す） |
| `tools/make_meta_png.py` | tEXt・tIME チャンクを足した画像を作る |
| `tools/make_zundamon_png.py` | 題材の画像を立ち絵から作る |
| `tools/thumbnail.py` | サムネの案（公開は B） |

## データの用意

`data/gradient.png`・`photoish.png`・`noise.png` は自作の合成画像（リポジトリに入っている）。
題材の `data/zundamon.png` は立ち絵から作った画像なので入っていない。

```bash
uv run python videos/png/tools/make_zundamon_png.py     # 立ち絵（assets/characters）が必要
uv run python videos/png/tools/make_meta_png.py
cd videos/png && uv run python tools/pnganalyze.py data/*.png   # → build/analysis/*.json
```

作り直した画像は公開版とは別物になる（大きさ・フィルタの数などの数字が変わる）。シーンの `assert` と台詞の数字を合わせて直すこと。

## この動画で決めたこと

- 声の間の長さは公開当時のもの（`video.yaml` の `voice:`）。
- 色の約束：フィルタ 5 種 None 灰 / Sub 青 / Up 黄 / Average 紫 / Paeth 珊瑚。データの「元」は白、「コピー」はシアン。
