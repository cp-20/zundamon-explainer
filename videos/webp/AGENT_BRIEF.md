# シーン担当への指示 (WebP 編)

WebP の仕組みを、ずんだもん (Z・聞き手) と四国めたん (M・解説) の掛け合いで、普通の高校生に分かるように解説する動画。
PNG 編・JPEG 編・GIF 編の続編。品質の目標は 3Blue1Brown。見ていて気持ちいい、意味のある動きだけの可視化にする。

## 最初に読むもの

1. 見本のシーン `scenes/s04_predict.py` (依頼者が確認済み。分かりやすさ・動き・大きさの基準) と、その部品 `vlib/catview.py`
2. `PLAN.md` の担当の節 (`uv run python tools/plan_view.py webp` の `build/plan.html` でも読める)
3. リポジトリの docs：`docs/visual-design.md`、`docs/scene-code.md`、`docs/quality-checks.md`、`docs/script-writing.md`
4. 前の動画で似たことをしているシーン (例：ファイルの先頭のバイト列は `videos/gif/scenes/s02_header.py`、クレジットは `videos/gif/scenes/s09_summary.py`、ブロックの数字は `videos/jpeg/vlib/jparts.py`)

## あなたの担当

- 担当のシーンを `scenes/sNN_<題名>.py` (クラス `SNN`) に書き、`bin/pipeline.sh webp SNN` で検査 0 件まで直す。シート `build/sheet/SNN.png` とフレームを目で見る。
- 台詞は依頼者が確認済み。どうしても変えるときは `script/SNN.md` に節を写して直す (PLAN.md は直さない)。変えたら `bin/voice.sh webp SNN`。
- 共通部品 (`zunda/`、`config/`、`tools/`、`bin/`)、`vlib/` の既存の関数、他のシーンは変更しない。足りない部品はシーンのファイルの中に書く。不具合は報告に書く。1080p では描かない。
- 指示を過剰に読み取らない。計画どおり最小限に作り、図を見れば分かることを文字にしない。画面の案はたたき台なので、もっと分かりやすい見せ方があれば変えてよい。
- 画面は大きく使う：本文・数字 34〜48px、ラベル 26〜32px (最小 22px)。上の帯だけに詰めず、2 人の間の領域 (x 440〜1480、y 905 まで) も使う。

## この動画の部品とデータ (`vlib/`)

画面に出す数字は、すべてここから取る (直書きしない)。台詞の数字と一致することを `assert` する。

- `vlib/data.py`
  - 名前は `data/` のファイル名。拡張子を省くと webp → png → jpg の順に探す (`"cat_q80"` は WebP、`"cat_q80.jpg"` は JPEG)。
  - `size(name)` ファイルの大きさ、`file_bytes(name)`、`pixels(name)` (Pillow で読んだ RGB(A)。絵として出す用)、`fmt(n)` (3 桁区切り)、`gif_stamp_size()`、`GIF_STAMP` (GIF 編のスタンプのパス)。
  - `mean_abs_err(name)`：元の写真との 1 点あたりの平均のずれ (JPEG 2.61 / WebP 2.72)。
  - 非可逆：`webp(name)` (自前の復号の結果すべて)、`vp8_info(name)` (`width height mbw mbh q quant filter segments partitions first_size probs mbs …`)、
    `y_orig()` 元の明るさ、`y_decoded(name, filt)` 復号の明るさ、`y_pred(name)` 予想だけ、`y_planes(name)` 復号の Y・U・V、
    `mb(mx, my)` (`ymode bmodes uvmode segment levels deq pred4 mode_log tok_log has_coeffs filter`)、`sub_block(mx, my, b)`、
    `MAIN_MB = (10, 7)`、`MAIN_SB = 13` (主役の 4×4)、`fdct4(差)`、`quant_steps(segment)`、`quantize(係数, 割る数)`、`basis4()` (16 種類の模様)、
    `all_levels()` (書いた数すべて)、`decisions()` (判定の数, 係数の区画のビット数)、`bits_of(判定の記録)`。
    判定の記録は `(確率 p, 読んだビット, 読む前の幅, 0 の側の幅)` の列で、ビットが 0 になる確率が p/256。係数の最初の判定でビット 0 は「ここで終わり (残りは全部 0)」。
  - 可逆・透明・動き：`vp8l_info(name)` (変換・読み取りの記録)、`distance_map()`、`alpha_info()`、`anim_frames()`、`anim_canvas()` (各コマを重ねた画面)。
- `vlib/catview.py`：`CatView` (猫の明るさを拡大の窓・明るさの塗り分け・格子つきで映す)、`ViewAnim`、`zoom`、`window_around`、`gray_img`。
- 自前の復号器は `tools/vp8.py` `tools/vp8l.py` `tools/webpanalyze.py`。dwebp・Pillow と全画素一致を確認済み。

## 色の約束

予想はシアン `CYAN`、元 − 予想 の差は紫 `PURPLE`、注目は黄 `YELLOW`、失われる・ずれは珊瑚 `CORAL`、まだ作っていない所は暗く沈める。
算術符号の帯は「全部 0 / 終わり」の側が青 `BLUE`、もう一方が珊瑚。ずんだもん `ZCOL`、めたん `MCOL`。

## 見本で決まったこと・踏んだ落とし穴

- 手順は 1 歩ずつ。実データの小さな例 (主役の 4×4) で実際にやってみせ、結果は少し止める。
- 画像の上に数字や印を重ねるときは、画像を下敷きとして `img.check_ignore = True` にする (検査の「文字と図」を避ける)。
- `CatView.refresh()` は不透明度を保つ。`set_opacity(0)` のあとに状態を変えて `refresh()` しても見えない。
- 同じ画像に `ViewAnim` と `.animate` を同じ `play` で重ねない (片方が上書きする)。順に分ける。
- 予想に使う点は、ループフィルタの前の復号の値 (`y_decoded(filt=False)`)。元の写真と比べるときは `y_orig()`。
- 負の数はマイナス記号 `−` (`str(v).replace("-", "−")`)。

## 通しの試写で決まったこと

- **画面の文字は、出したらしばらく出しておく。** どの文字も 2.5 秒以上 (長い文は 1 文字 0.15 秒以上)。
  数字が変わっていく途中 (割った値 → 丸めた値、GIF の文 → WebP の文 など) も、1 つの状態を 1.5 秒以上止めて読めるようにする。
  止める時間が足りないときは、途中の状態を飛ばす (最初と最後だけ見せる) か、間を足す。
- 間を足すときは `script/SNN.md` に節を写し、台詞の行末の ` (+秒)` だけを直して `bin/voice.sh webp SNN` (台詞の文は変えない)。PLAN.md への反映は依頼者側でする。
- 読点を減らしたので、どのシーンも台詞の時刻が少し早くなった。キューに合わせた動きが遅れていないか、検査で確かめる。

## シーンのつなぎ目

| シーン | 最初の画面 | 最後の画面 |
|---|---|---|
| S01 | 空 | タイトル `jp("WebPの中身をのぞく", 72)` を `px(960, 300)` |
| S02 | S01 と同じタイトル (最初の台詞で消す) | S03 と同じ担当が決める |
| S03 | S02 の最後 | `CatView(y_orig(), (960, 340), 902, 600)`、`grid_mb = 1`、全体が明るい (S04 の最初と同じ) |
| S04 | (見本、完成済み) | 空 |
| S05 | 空 | S06 と同じ担当が決める |
| S06 | S05 の最後 | 空 |
| S07〜S10 | 空 | 空 |
| S11 | 空 | 動画の終わり。クレジットの上で「ありがとう」「またね」、最後にゆっくり消える |

## 報告に書くこと

- 作ったもの (流れを数行で) と尺。台詞を変えた所と理由。
- 検査の結果と、目で見て直した所。
- 自信のない所・確かめていない所・共通部品への要望。
