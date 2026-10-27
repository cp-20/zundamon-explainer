# AVIF 編

**HEICとほぼ同じ13,179バイト、なのに特許料0円。AVIFの中身をのぞいてみた【ずんだもん解説】** — https://youtu.be/UstNOfWVg9c
(約 15 分半、12 シーン。動画ファイルは Release `avif-v1`)

猫の写真 (AVIF 品質 60 で 13,179 バイト。元とのずれが HEIC 編の HEIC 品質 45 の 13,368 バイトとほぼ同じ) で、
ファイルサイズは HEIC と互角のまま特許料がかからない AV1 が、HEIC とは別のどんな工夫で圧縮しているかを、
箱と OBU → ブロックの分け方 → 56 方向の予測 → Paeth 予測とスムース予測 → 明るさから色を予測 → 波を縦と横で選ぶ → 一度に何択も選べる算術符号 → 模様の向きに沿ってならす → 粒子を作り直す → 実験と弱点、の順に解説する。

## ファイル

| 場所 | 中身 |
|---|---|
| `scenes/` | 見本は `s06_cfl.py` |
| `vlib/data.py` | 箱・OBU・復号の結果 (ブロック・予測・係数・CDEF・記号の記録)、CfL の見本のブロック |
| `vlib/ui.py` | Cb・Cr の塗り分け、数のマス (CellGrid)、比較表 |
| `vlib/photoview.py` | 写真を窓で映す部品 (HEIC 編と同じ) |
| `tools/heif.py` | 自前の HEIF の箱の読み取り (HEIC 編のものに av1C と OBU の切り分けを足したもの) |
| `tools/av1.py` | 自前の AV1 の復号器 (イントラ・静止画)。aomdec と Y・U・V の全画素が一致 |
| `tools/av1tables.py` | AV1 の定数表。`tools/gen_av1tables.py` が AV1 の仕様書 (av1-spec) の Markdown から作る |
| `tools/make_data.py` | 猫の写真の AVIF・HEIC・JPEG・WebP と、粒を足した猫の AVIF を作る |
| `tools/thumbnail.py` | サムネの案 (公開は B) |
| `tools/measure_time.py` | JPEG・WebP・HEIC・AVIF の保存にかかる時間を測る (`data/encode_time.json`) |

## データの用意

`data/` はすべて猫の写真 (CC0) から作ったもので、リポジトリに入っている。
`cat_grain_fg.avif` は libaom の粒の取り除きが毎回少し違うファイルを作るので、`make_data.py` はあれば作り直さない。

```bash
uv run python videos/avif/tools/make_data.py
uv run python videos/avif/tools/av1.py videos/avif/data/cat_q60.avif --stats   # 自前の復号器と aomdec の突き合わせ
```

## この動画で決めたこと

- 本編の品質は 60 (Pillow 12.3 の AVIF。libavif 1.4.2 と libaom 3.14.1、速さ 6)。元とのずれ 2.69 が HEIC (2.65)・WebP (2.72)・JPEG (2.61) と同じくらい。
  大きさは HEIC と 189 バイトしか違わないので、「HEIC より小さい」とは言わない。
- この写真で使われた区切りは 4 種 (割らない・横に 2 つ・縦に 2 つ・4 つ) だけ。T 字や 4 本は、遅い設定 (速さ 0〜2) で出る。
- この写真ではループの復元フィルタは使われていない (sequence header の enable_restoration が 0)。CDEF は 64×64 の 40 個のうち 9 個。
- Cb・Cr の画像は、128 を灰、少ないほうを黄 (青み)・青緑 (赤み)、多いほうを青・赤に塗る (`vlib/ui.py`)。青みと赤みで同じ決まり。
