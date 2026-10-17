# シーン担当エージェントへの指示（JPEG 編）

> この動画を作ったときに、シーン担当のエージェントに渡した指示（記録）。新しい動画では docs/templates/AGENT_BRIEF.md から作る。

JPEG の仕組みを、ずんだもん（Z・初学者）と四国めたん（M・解説）の掛け合いで、普通の高校生に分かるように丁寧に解説する動画（1920×1080 / 30fps / Manim）。前回の PNG 編の続編。
**品質の目標は 3Blue1Brown。YouTube で10万回再生されるもの。** 見ていて気持ちいい、意味のある動きだけの可視化にする。

見本は S05（波に分ける）：`scenes/s05_dct.py`。**まずこれを全部読むこと。** ユーザーが確認済み。書き方・粒度・動きの付け方をそろえる。

## あなたの担当

担当シーンのコード `scenes/sNN_<名前>.py`（クラス名は `SNN`、`PScene` を継承）を作り、`bin/pipeline.sh jpeg SNN` が通り、検査が0件になるまで仕上げる。

- 台詞と画面の計画は `PLAN.md` の自分のシーンの節。**画面の案はたたき台**なので、もっと良い見せ方があれば変えてよい。台詞はユーザー確認済みなので、基本は変えない。
- どうしても台詞を変えるときは `PLAN.md` を編集しない（他と衝突する）。自分の節を `script/SNN.md` に丸ごと写して（`## SNN タイトル` の見出しから）直す。あれば `PLAN.md` より優先される。
- `zunda/`・`config/`・`tools/`・`bin/`・他のシーンは**変更しない**。部品が欲しければ自分のシーンファイルの中に書く。共通部品の不具合は報告に書く。
- 1080p の描画はしない（最後にまとめてやる）。

## 作業の流れ

1. `bin/voice.sh jpeg SNN` で音声と時刻表 `build/voice/SNN.json` を作る（台詞を変えたときだけ。今はもう作ってある）。各台詞の `kana`（読み）を確認し、誤読があれば報告する。
2. シーンのコードを書く。キューの時刻は `build/voice/SNN.json` の `lines[].cues`。
3. `bin/pipeline.sh jpeg SNN`（描画→立ち絵と字幕の合成→音声→検査→シート）。2〜4分。出力：
   - `build/out/SNN.mp4`：プレビュー動画
   - `build/check/SNN.txt`：検査結果
   - `build/sheet/SNN.png`：画面の状態ごとのフレームと、その時の台詞を並べたシート
4. 検査を0件にする。一時的な写し（飛ばしているコピー等）や、数えている途中の数字で誤検出されるものは、そのオブジェクトに `m.check_ignore = True`。
5. **シートを Read で見て、目で確認する**。検査は完全ではない。遷移の途中も `ffmpeg -ss <秒> -i build/out/SNN.mp4 -frames:v 1 -vf scale=960:540 x.png` で数枚切り出して、ガタつき・変な重なり・読めない小ささ・消し忘れがないか見る。直して繰り返す。
6. 待つときは、自分で起動したコマンドの終了を待つ（`pgrep -f pipeline.sh` のような自分自身にも一致する待ち方はしない）。

## Manim の落とし穴（見本で踏んだもの）

- `LaggedStart(*[Transform(c, b) for c in group])` のように**グループの中身を個別にアニメーション**すると、中身が個別に場面へ入る。あとで `self.remove(group)` しても中身が残る。`self.remove(group, *group)` で外す。
- 8×8 などの小さい配列の `ImageMobject` はそのままだと端がずれる。`vlib.jparts.gray_img()` を使う（大きく引き伸ばしてから置く）。
- 負の数は `str(v).replace("-", "−")`（ハイフンではなくマイナス記号）。

## 同期（最重要）

- 台詞中の `{cue}` の時刻（その位置の音が出る時刻）に画面を合わせる。`self.at("cue")` でその時刻まで待ってから `self.play(...)`。`self.at("cue", -0.1)` のように前後にずらせる。台詞の頭のキュー（`{s06_01}` など）も使える。
- **アニメーションの方を台詞に合わせる。** 次のキューまでに終わる長さにする（`self.until("next")` で残り秒数）。遅れると検査に出る。
- 最後は必ず `self.finish()`。

## 画面に出す文字（ユーザーの指定）

- 画面に出すのは「今話していること」の短いラベルと数字だけ。**図を見れば分かることを文字で説明しない**（例：見本で「足した波 3 / 8」という数を出したら、ユーザーに「図を見たら分かる説明はいらない」と言われて消した）。
- 文字は最低 1 秒は出しておく。長い文は 0.12 秒/字。

## 画面の原則（ユーザーの指定）

- **繋がり**：前の画面から続く要素は、同じオブジェクトのまま滑らかに変形させる（`Transform`、`.animate`、`retext`）。消して出し直したり、少しだけずらしたりしない。
- **動き**：意味のある動きだけ。出し入れのたびに周囲がガタガタ動くのは不可。複数の要素は 1 つの ease でまとめて動かす（同じ `self.play` に入れる）。
- **強調**：拡大（`pop`）・下線（`underline`）・文字色・揺らす（`Shake`）を使い分ける。囲み枠に頼らない。枠線同士は交差させない。
- **間**：大きく画面が変わる所には台詞の行末に間（`(+1.0)`）がある。その間に変形・答えを見せる。画面が止まったままの長い無音は作らない。
- **レイアウト**：場面ごとに自然な配置を設計する。立ち絵と字幕の領域には入らない。
  - 使ってよい領域（px、左上原点）：上の帯 `x 28〜1892, y 28〜455`（全幅）と、2人の間 `x 440〜1480, y 28〜905`。立ち絵の実際の形で検査する。
  - 地図の帯（`StageMap("strip")`）は上端 y 30〜85 を使う。その下から使う。
  - 文字は小さくしすぎない：本文・数字 34〜48px、ラベル 26〜32px、最小 22px（ただし 8×8 のマスの中の数字は 24px まで可）。
- **フォント**：説明の文字は数字・英字が入っていても和文フォント `jp()`（`mix()` も同じ）で1つの文字列に組む。等幅 `mono()` は**バイト列・16進ダンプ・ビット列**だけ。和文と数字を別々の Text にして `arrange` で並べない。
- **数値**：画面に出す数値は、すべて実データから計算する（下の `vlib.data`）。数字をコードに直書きしない。台詞の数字と一致することを `assert` で確かめる。

## 台詞と役割

- 台詞はユーザー確認済み。進行はめたん、ずんだもんはリアクション役（驚く・分からないと言う・素朴な疑問）。
- 表情は台詞に付いている（`Z(驚)` など）。立ち絵と字幕は自動で合成されるので、シーンのコードは図だけ描く。

## 部品

- `zunda/scene.py`：`PScene`、`px(x, y)`（px→座標）、`u(px)`（長さ）、`jp(文字, size, color, **Text の引数)`（size は px）、`mix()`（＝jp）、`mono()`、色 `INK DIM BG CYAN YELLOW CORAL PURPLE BLUE ZCOL MCOL`、`self.se("pop")`（効果音。使うなら 1 シーン 3 回まで。`assets/se/` の名前）。
- `zunda/fx.py`：`pop(m, scale, run_time)`、`underline(m, color)`、`Shake(m, amp)`、`retext(old, new)`（数字の書き換え）。
- `vlib/smap.py`：工程の地図 `StageMap(mode, active, done)`。`mode="full"`（画面上部に大きく）/ `"strip"`（上端の細い帯）。段のキー `color sub block dct quant code`。`active` は今いる段、`done` は済んだ段のタプル（full で点が付く）。捨てる段（`sub`・`quant`）は、済んだ／今いる時に下に珊瑚の「捨てる」（`m.lossy[key]`）。切り替えは `self.play(Transform(m, m.state("strip", active="quant", done=(...))))`。部品は `m.parts[key]`、`m.arrows`、`m.checks`。
- `vlib/jparts.py`：`gray_img(配列, 高さpx)`、`BlockGrid(明るさ8×8)`（主役のブロックの表示、`.cell(r,c)` `.num(r,c)`）、`BasisGrid()`（64 模様、`.at(u,v)` `.zigzag()` `.coef_labels(F)`）、`coef_state(F)`、`QGrid(Q)`（量子化後の 8×8）、定位置 `BLOCK_POS` `GRID_POS` `QGRID_POS`。
- `vlib/data.py`（実データ）：
  - `pixels(name)`（`cat`・`cat_q5`…`cat_q95`・`zunda_white`・`zunda_q80`。JPEG は libjpeg で開いた画素）、`file_bytes(name)`、`ycc(name)`（元画像の Y/Cb/Cr）
  - `jpeg(name)` → `(要約, 構造, 係数, 自前復号RGB)`。要約 `summary(name)`：`file_bytes, width, height, raw_bytes, comps（h, v, blocks）, qt, segments（name, offset, length, scan_offset…）, seg_sizes, scan_bytes, ac_zero, ac_total, stats`。係数は `coef[comp][by, bx, 64]`（ジグザグ順、量子化後）。
  - 主役のブロック：`BLOCK = (13, 20)`、`block_pixels()`（元の明るさ 8×8）、`block_dct()`（DCT 係数）、`block_coef()`（ファイルの中の量子化後の係数 8×8）、`qtable(name, comp)`（量子化表 8×8）。`idct2`・`dct2`・`ZIGZAG`・`BASIS`・`to_block`・`codes_of(counts, syms)`（ハフマン符号の表）。
  - 自前の復号器は `tools/jpeganalyze.py`（ハフマン表は `jpeg(name)[1]["ht"][(0 か 1, 表番号)] = (counts, syms)`）。
- 画像ファイル：`data/cat.png`（元の写真 451×300）、`cat_q{5,10,30,50,80,95}.jpg`、`zunda_white.png` / `zunda_q80.jpg`（541×797）。
- 色の約束：明るさ Y は白、Cb は青 `BLUE`、Cr は赤 `CORAL` 寄り、捨てる・失われる・ずれは珊瑚 `CORAL`、注目は黄 `YELLOW`。工程の色は `vlib.smap.STAGE_COL`。

## シーンのつなぎ目（最初と最後の画面）

前のシーンの最後のフレームと、次のシーンの最初のフレームを一致させる。

| シーン | 最初の画面 | 最後の画面 |
|---|---|---|
| S01 | 空 | タイトル `jp("JPEGは何を捨てている？", 72)` を `px(960, 300)` |
| S02 | S01 と同じタイトル（最初の台詞で消す） | `StageMap("full", done=("color",))` だけ |
| S03 | S02 の最後 | `StageMap("full", done=("color", "sub"))` だけ |
| S04 | S03 の最後 | `StageMap("strip", active="block", done=("color", "sub"))` と `BlockGrid(block_pixels()).move_to(BLOCK_POS)` |
| S05 | S04 の最後 | `StageMap("strip", active="dct", done=("color", "sub", "block"))` と `coef_state(block_dct())` |
| S06 | S05 の最後 | `StageMap("strip", active="quant", done=("color", "sub", "block", "dct"))` と `QGrid(block_coef())` |
| S07 | S06 の最後 | `StageMap("full", done=6段すべて)` だけ |
| S08 | S07 の最後 | 空 |
| S09 | 空 | 空 |
| S10 | 空 | 空 |
| S11 | 空 | 自由（動画の終わり。クレジットの上で「ありがとう」「またね」、最後にゆっくり消す） |

## 報告に書くこと

- 作ったもの（シーンの流れを数行で）と、尺。
- 台詞を変えた所（`script/SNN.md`）と、その理由。
- 検査の結果と、目で見て直した所。
- 自信のない所・確認できていない所・共通部品への要望。

## 追記：同じオブジェクトに2つのアニメーションを同時にかけない

`self.play(FadeIn(x), pop(x))` のように、同じオブジェクトに `FadeIn` と `.animate`（`pop` も中身は `.animate`）を同じ `play` で重ねると、後のほうが前のほうを上書きして、終わった瞬間に消える。出してから、次の `play` で強調する。
