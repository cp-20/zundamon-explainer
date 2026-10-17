# JPEG 編

**写真は「波」でできている！？JPEG圧縮の仕組みをやさしく解説【ずんだもん解説】** — https://youtu.be/dZP4YsrL6nw
（約 12.5 分、11 シーン。動画ファイルは Release `jpeg-v1`）

猫の写真（PNG 218,916 バイト → JPEG 23,693 バイト）で、JPEG が「何を捨てているか」を
明るさと色 → 色の間引き → 8×8 のブロック → DCT（波に分ける）→ 量子化 → ジグザグとハフマン符号 → ファイルの中身 → 品質の実験、の順に解説する。

## ファイル

| 場所 | 中身 |
|---|---|
| `scenes/` | S01〜S11。見本は `s05_dct.py` |
| `vlib/data.py` | 画素、Y/Cb/Cr、主役のブロック（猫の左目の瞳のふち）、量子化表、係数の読み出し |
| `vlib/jparts.py` | 8×8 のマス、64 の DCT の模様、量子化後の表 |
| `vlib/smap.py` | 工程の地図（色を分ける → 間引く → 8×8 → 波 → 割って丸める → 符号） |
| `tools/jpeganalyze.py` | 自前のベースライン JPEG 復号器（ハフマン復号・逆量子化・逆 DCT。libjpeg と輝度 ±1 で一致） |
| `tools/make_data.py` | 品質違いの JPEG と、白背景のずんだもん（イラストとの比較用）を作る |
| `tools/thumbnail.py` | サムネの案（公開は E） |

## データの用意

`data/cat.png` は scikit-image の「Chelsea the cat」（Stefan van der Walt, CC0）。`cat_q*.jpg` はそこから作ったもので、リポジトリに入っている。
S10 で使う `zunda_white.png`・`zunda_q80.jpg` は立ち絵から作るので入っていない（`tools/make_data.py`、PNG 編の題材の画像が必要）。

## この動画で決めたこと

- 声の間の長さは公開当時のもの（`video.yaml` の `voice:`）。
- 主役のブロック：輝度の (行 13, 列 20)。元の画素から計算した DCT を量子化すると、ファイルの中の係数と完全に一致する。
