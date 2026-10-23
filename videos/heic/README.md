# HEIC 編

**謎の拡張子HEIC、実はWebPより2割小さかった【ずんだもん解説】** — https://youtu.be/-Aqzhf8QRy0
(約 10 分、11 シーン。動画ファイルは Release `heic-v1`)

猫の写真 (HEIC 品質 45 で 13,368 バイト。元とのずれが JPEG 品質 80 の 23,693 バイト・WebP 品質 80 の 16,974 バイトとほぼ同じ) で、
箱の中身 → ブロックの大きさを選ぶ → 35 通りの予想 → 向きも予想する → 波の大きさともう 1 つの波 → CABAC → デブロッキングと SAO → 箱の力 → 実験と弱点、の順に解説する。

## ファイル

| 場所 | 中身 |
|---|---|
| `scenes/` | S01〜S11。見本は `s03_blocks.py` |
| `vlib/data.py` | 箱の読み取り・復号の結果 (CU・TU・予想・係数・SAO・CABAC の判定の記録)、大きさ、面積の割合 |
| `vlib/photoview.py` | 写真を窓で映し、寄る・引くの動きと、ブロックの境目の線を重ねる部品 (S03〜S06) |
| `tools/heif.py` | 自前の HEIF の箱の読み取り。HEVC の本体を ffmpeg で読める形 (Annex B) で取り出す |
| `tools/hevc.py` | 自前の HEVC の復号器 (イントラ・8 ビット・4:2:0。CABAC・WPP・符号の隠し・cu_qp_delta・デブロッキング・SAO)。ffmpeg と Y・U・V の全画素が一致 |
| `tools/hevctables.py` | HEVC の定数表 |
| `tools/make_data.py` | 猫の写真の HEIC・JPEG・WebP と、透明とサムネイルつきのずんだもんの HEIC を作る |
| `tools/thumbnail.py` | サムネの案 (公開は V3) |
| `tools/measure_time.py` | JPEG・WebP・HEIC の保存にかかる時間を測る (`data/encode_time.json`) |

## データの用意

`data/cat*` は猫の写真 (CC0) から作ったもので、リポジトリに入っている。
`data/zunda.heic` は立ち絵から作るので入っていない。

```bash
uv run python videos/heic/tools/make_data.py                              # 立ち絵 (assets/characters) が必要
uv run python videos/heic/tools/hevc.py videos/heic/data/cat_q45.heic     # 自前の復号器と ffmpeg の突き合わせ
```

## この動画で決めたこと

- 本編の品質は 45。元とのずれ (RGB の平均) 2.65 が JPEG (2.61) と WebP (2.72) の間になる品質。
- 四分木の見本：64×64 の (横 2, 縦 2)。左目の下のふち。この写真には 64×64 のまま使ったブロックはなく、面積の半分が 32×32。
- 32×32 の多くは毛の模様で、0 でない係数が多い。「大きいブロックは数が少ない」とは言わず、背景の 1 ブロック (0 でないのは 6 個) を例にする。
- SAO の効き目は小さい (明るさのずれ 1.958 → 1.934)。そのまま「少し減る」と言う。
- CABAC の「覚える」効き目は、確率を使う問いのビット数を答えと確率から計算して比べる (75,349 / 65,210 / 59,759)。
