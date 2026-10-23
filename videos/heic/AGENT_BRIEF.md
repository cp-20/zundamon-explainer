# シーン担当への指示 (HEIC 編)

HEIC の仕組みを、ずんだもん (Z・聞き手) と四国めたん (M・解説) の掛け合いで、普通の高校生に分かるように解説する動画。
PNG 編・JPEG 編・GIF 編・WebP 編の続編。品質の目標は 3Blue1Brown。見ていて気持ちいい、意味のある動きだけの可視化にする。
依頼者からは「アニメーションの気持ちよさ・解説の分かりやすさ・動画全体の質を、前の動画より大きく上げる」と頼まれている。

## 最初に読むもの

1. 見本のシーン `scenes/s03_blocks.py` (依頼者が確認済み。分かりやすさ・動き・大きさの基準) と、その部品 `vlib/photoview.py`
2. `PLAN.md` の担当の節 (`uv run python tools/plan_view.py heic` の `build/plan.html` でも読める)
3. リポジトリの docs：`docs/visual-design.md`、`docs/scene-code.md`、`docs/quality-checks.md`、`docs/script-writing.md`
4. 前の動画で似たことをしているシーン (ファイルの先頭のバイト列は `videos/webp/scenes/s02_header.py`、算術符号の定規は `videos/webp/scenes/s06_arith.py`、
   ループフィルタは `videos/webp/scenes/s07_filter.py`、小さい画像の比べ方は `videos/webp/scenes/s10_compare.py`、クレジットは `videos/webp/scenes/s11_summary.py`)

## あなたの担当

- 担当のシーンを `scenes/sNN_<題名>.py` (クラス `SNN`) に書き、`bin/pipeline.sh heic SNN` で検査 0 件まで直す。シート `build/sheet/SNN.png` とフレームを目で見る。
- 台詞は依頼者が確認済み。どうしても変えるときは `script/SNN.md` に節を写して直す (PLAN.md は直さない)。変えたら `bin/voice.sh heic SNN`。
  間 (`(+秒)`) を足すだけのときも同じ。
- 共通部品 (`zunda/`、`config/`、`tools/`、`bin/`)、`vlib/` の既存の関数、`videos/heic/tools/` の既存のファイル、他のシーンは変更しない。
  足りない部品はシーンのファイルの中に書く (新しい道具が要るなら `videos/heic/tools/` に新しいファイルとして)。不具合は報告に書く。1080p では描かない。
- 指示を過剰に読み取らない。計画どおり最小限に作り、図を見れば分かることを文字にしない。画面の案はたたき台なので、もっと分かりやすい見せ方があれば変えてよい。
- 画面は大きく使う：本文・数字 34〜48px、ラベル 26〜32px (最小 22px)。上の帯だけに詰めず、2 人の間の領域 (x 440〜1480、y 905 まで) も使う。
  WebP 編では 6 人中 6 人が最初は小さく作った。主役の図は画面の主役の大きさにする。

## この動画の部品とデータ (`vlib/`)

画面に出す数字は、すべてここ (自前の読み取り器・復号器) から取る (直書きしない)。台詞の数字と一致することを `assert` する。

- `vlib/data.py`
  - 名前は `data/` のファイル名。拡張子を省くと heic → png → webp → jpg の順に探す (`"cat_q45"` は HEIC、`"cat_q80.jpg"` は JPEG)。
  - `size(name)`、`file_bytes(name)`、`fmt(n)` (3 桁区切り)、`pixels(name)` (絵として出す RGB(A)。HEIC は自前の復号)、`mean_abs_err(name)` (元との RGB の平均のずれ)。
  - 箱：`boxes(name)` (tools/heif.py の結果：`tree` 箱の木、`items` 項目 (`type`・`extents`・`props`)、`primary`、`mdat`、`brand` …)。
  - HEVC：`dec(name)` (tools/hevc.py の `Decoder`。下を参照)、`picture_size()` (451, 300)、`rgb_decoded(name, stage)` (stage は final / deblocked / recon / pred)、
    `ctb_size()` 64、`ctb_grid()` (8, 5)、`splits()`、`ctb_splits(rx, ry)`、`cus()`、`area_shares()`、`MAIN = "cat_q45"`、`MAIN_CTB = (2, 2)`、`SIZE_COLOR`。
  - CABAC：`cabac_log()`、`ctx_trace(文脈の名前, 番号)` ([(読む前の「1」の確率, 答え)])、`cabac_costs()` (n 75,349 / fixed 65,210 / adapt 59,759)、`p_lps(状態)`。
- `dec(name)` (`Decoder`) の中身 (座標は明るさの画素。復号は 456×304 で、写真は 451×300 に切る)
  - `cus`：dict(x, y, size, depth, nxn, pus, qp, chroma_mode_idx, chroma_mode)。`pus` は dict(x, y, size, cand (候補 3 つ), mpm (候補に当たったか), mpm_idx か rem, mode)。
  - `tus`：dict(x, y, size, mode, cbf, qp, levels {色の番号: 係数の配列 (割って丸めたあとの数)})。
  - `pred[c]` 予想だけ、`resid[c]` 差だけ、`recon` ループフィルタの前、`deblocked`、`final` (SAO のあと)。c は 0 明るさ・1 Cb・2 Cr。`cropped(planes)` で写真の大きさに切る。
  - `intra_pred(c, x, y, n, mode, keep={})`：予想を作り直す (keep に使った上と左の点 `top` `left` が入る。`left[0]` は左上、`left[1 + y]`、`top[1 + x]`)。
  - `sao[(横, 縦)]`：64×64 ごとの SAO (`{0: dict(type, offsets, eo_class か band), 1: …, 2: …, "merge": …}`)。type 0 なし・1 帯・2 端。`sao_class[c]` 点ごとの分類。
  - `deblock_log`：明るさの境目 4 点ごとの判定 (vertical, e, s, beta, tc, d, mode：0 ならさない・1 弱く・2 強く)。
  - `splits`：「4 つに割る？」の答え (x, y, size, split, coded)。`ctb_bits[(横, 縦)]`：その 64×64 の読み始めと読み終わりのビット位置。
- `vlib/photoview.py`：`PhotoView` (写真を窓で映す。`set_box` ではなく `move_view(view, win, box)` で寄る・引く)、`PLine` (写真の座標の線。窓で切る)、
  `PRect`、`Grow` (線を真ん中から伸ばす)、`ViewAnim`、`cross_lines`、`grid64_lines`、`partition_lines` (S03 の最後の割れ方すべて)、`LW` (線の太さ)。
- 自前の読み取り器・復号器は `tools/heif.py` `tools/hevc.py`。ffmpeg と Y・U・V の全画素が一致 (`uv run python videos/heic/tools/hevc.py <file>`)。

## 色の約束

予想はシアン `CYAN`、元 − 予想 の差は紫 `PURPLE`、注目は黄 `YELLOW`、失われる・ずれは珊瑚 `CORAL`、まだ作っていない所は暗く沈める。
ブロックの大きさ (線の色) は `SIZE_COLOR`：64 白、32 青、16 緑、8 砂、4 橙。「割る？」の答えの 1 は黄、0 は暗い灰。
CABAC の「はい」は青 `BLUE`、「いいえ」は珊瑚 (WebP 編の定規と同じ)。ずんだもん `ZCOL`、めたん `MCOL`。

## 見本で決まったこと・踏んだ落とし穴

- 手順は 1 歩ずつ。実データの小さな例で実際にやってみせ、結果は少し止める。最初の数歩はゆっくり、あとは速く流してよい。
- 動きは「伸びる・飛ぶ・寄る」で見せる：線は真ん中から伸ばす (`Grow`)、ビットや数は写しを `path_arc` で飛ばす、写真は `move_view` で窓と箱を一緒に動かして寄る。
  寄るときは、注目していない所を `view.lit` で暗く沈める。
- 写真の上の線 (`PLine`) は窓で切るときに不透明度を持ち直すので、`FadeIn/FadeOut` ではなく、`Grow` か `ln._op` を変えて `ln.sync()` で出し入れする
  (s03 の `LineOp`)。
- 写真は下敷きとして `view.check_ignore = True` (検査の「文字と図」を避ける)。
- キューに間に合わないときは、1 つの `play` に `Succession` でまとめると速くなる。台詞の時刻を検査の「遅れ」で確かめる。
- 負の数はマイナス記号 `−` (`str(v).replace("-", "−")`)。

## 通しの試写で決まったこと (WebP 編から)

- **画面の文字は、出したらしばらく出しておく。** どの文字も 2.5 秒以上 (長い文は 1 文字 0.15 秒以上)。
  数字が変わっていく途中も、1 つの状態を 1.5 秒以上止めて読めるようにする。止める時間が足りないときは、途中の状態を飛ばすか、間を足す。

## シーンのつなぎ目

| シーン | 最初の画面 | 最後の画面 |
|---|---|---|
| S01 | 空 | タイトル `jp("HEICの中身をのぞく", 72)` を `px(960, 300)` |
| S02 | S01 と同じタイトル (最初の台詞で消す) | 写真だけ：`PhotoView(rgb_decoded(), (960, 386), 1040, 692)` (S03 の最初) |
| S03 | (見本、完成済み) | 写真 + `partition_lines(...)` のすべての線 (`SIZE_COLOR`、frac=1) |
| S04 | S03 の最後と同じ | S05 と同じ担当が決める |
| S05 | S04 の最後 | 空 |
| S06〜S10 | 空 | 空 |
| S11 | 空 | 動画の終わり。クレジットの上で「ありがとう」「またね」、最後にゆっくり消える |

## 報告に書くこと

- 作ったもの (流れを数行で) と尺。台詞を変えた所と理由。
- 検査の結果と、目で見て直した所。
- 自信のない所・確かめていない所・共通部品への要望。
