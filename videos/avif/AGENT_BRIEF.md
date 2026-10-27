# シーン担当への指示 (AVIF 編)

AVIF の仕組みを、ずんだもん (Z・聞き手) と四国めたん (M・解説) の掛け合いで、普通の高校生に分かるように解説する動画。
PNG 編・JPEG 編・GIF 編・WebP 編・HEIC 編の続編。品質の目標は 3Blue1Brown。見ていて気持ちいい、意味のある動きだけの可視化にする。
依頼者からは「今までの動画の 2 倍のクオリティで」と頼まれている。HEIC 編で足りなかったのは、文字が小さい・画面の中央が空く・図が細い、の 3 つ。

## 最初に読むもの

1. 見本のシーン `scenes/s06_cfl.py` (依頼者が確認済み。分かりやすさ・動き・大きさの基準) と、その部品 `vlib/ui.py`・`vlib/photoview.py`
2. `PLAN.md` の担当の節 (`uv run python tools/plan_view.py avif` の `build/plan.html` でも読める)
3. リポジトリの docs：`docs/visual-design.md`、`docs/scene-code.md`、`docs/quality-checks.md`、`docs/script-writing.md`
4. HEIC 編で似たことをしているシーン (`videos/heic/scenes/`)：S01 のスマホとパソコンと棒グラフは `s01_hook.py`、
   先頭のバイト列と箱の帯は `s02_boxes.py`、ブロックの分割と寄る動きは `s03_blocks.py`、予測の扇の矢印は `s04_modes.py`、
   波の棒は `s06_transform.py`、算術符号の定規は `s07_cabac.py` (と `videos/webp/scenes/s06_arith.py`)、
   フィルタの前後は `s08_filters.py`、小さい画像の比べ方は `s10_compare.py`、まとめとクレジットは `s11_summary.py`。
   見た目をそろえたい所は写して直してよい (HEIC 編のファイル自体は変えない)。

## あなたの担当

- 担当のシーンを `scenes/sNN_<題名>.py` (クラス `SNN`) に書き、`bin/pipeline.sh avif SNN` で検査 0 件まで直す。シート `build/sheet/SNN.png` とフレームを目で見る。
- 台詞は依頼者が確認済み。どうしても変えるときは `script/SNN.md` に節を写して直す (PLAN.md は直さない)。変えたら `bin/voice.sh avif SNN`。
  間 (`(+秒)`) を足すだけのときも同じ。変えた台詞は `build/voice/SNN.json` の `kana` で読みを確かめる。
- 共通部品 (`zunda/`、`config/`、`tools/`、`bin/`)、`vlib/` の既存のファイル、`videos/avif/tools/` の既存のファイル、他のシーンは変更しない。
  足りない部品 (データの取り出し・その場面だけの図) はシーンのファイルの中に書く。不具合は報告に書く。1080p では描かない。git にコミットしない。
- 指示を過剰に読み取らない。計画どおり最小限に作り、図を見れば分かることを文字にしない。画面の案はたたき台なので、もっと分かりやすい見せ方があれば変えてよい。
- 画面は大きく使う：本文・数字 34〜48px、ラベル 26〜32px (最小 22px、マスの中の数字だけ 24px まで可)。上の帯だけに詰めず、2 人の間の領域 (x 440〜1480、y 905 まで) も使う。
  主役の図は画面の主役の大きさにする。前の動画では担当の全員が最初は小さく作った。

## 言葉づかい (依頼者の指摘で決まったこと)

画面の文字に、AI が作ったような造語・比喩を使わない。「色の板」「くらべ札」「包み」「でこぼこの形」「写す」「縮める」「道具」は使わない。
使う言葉：Y (明るさ)・Cb (青み)・Cr (赤み)、比較表、OBU、明暗のパターン、流用する、圧縮する、予測、記録する、分割、画素、ファイルサイズ、特許料、粒子。
シリーズで説明済みの言葉 (波、割って丸める、算術符号の定規、ループフィルタ、HEIF の箱) は使ってよい。説明のない専門用語 (量子化、周波数、エントロピー符号化、輝度、色差) は画面に出さない。

## この動画の部品とデータ (`vlib/`)

画面に出す数字は、すべてここ (自前の読み取り器・復号器) から取る (直書きしない)。台詞の数字と一致することを `assert` する。

- `vlib/data.py`
  - 名前は `data/` のファイル名。拡張子を省くと avif → png → heic → webp → jpg の順に探す (`"cat_q60"` は AVIF、`"cat_q45.heic"`)。
  - `size(name)`、`file_bytes(name)`、`fmt(n)` (3 桁区切り)、`pixels(name)` (絵として出す RGB。AVIF は自前の復号)、`mean_abs_err(name, src="cat.png")`。
  - 箱：`boxes(name)` (tools/heif.py の結果：`tree`・`items`・`props`・`mdat` …)、`obus(name)` (本体の OBU：type・name・pos・header・size・data)。
  - AV1：`dec(name)` (tools/av1.py の `Decoder`。復号は数秒かかり、結果は `cache/avif/` に残る)、`picture_size()` (451, 300)、
    `planes(name, stage)` (写真の大きさに切った Y・U・V。stage は final / lr / cdef / deblocked / recon / pred)、`rgb_decoded(name, stage)`、
    `source_yuv("cat.png")` (元の写真の Y・Cb・Cr。「元」と比べるときに使う)、`blocks()`、`partitions()`、`txbs(name, plane)`、
    `MODE_NAMES`・`PARTITION_NAMES`・`TX_TYPE_NAMES`。
  - CfL：`cfl_example()`、`cfl_stats()` (S06 で使用済み)。
- `Decoder` の記録 (詳しくは `tools/av1.py` の先頭の説明)：`seq`・`frame`・`fields` (頭の値とビット位置)、`partitions`、`blocks`、`txbs`、
  面ごとの途中の画像 `pred`・`recon`・`deblocked`・`cdef`・`lr`・`final` と `crop()`、`intra_pred(txb, keep={})` (予測を作り直し、端の画素や角度を keep に入れる)、
  `cdef_log` (8×8 ごとの向き dir 0〜7 と var、64×64 ごとの強さ)、`deblock_log`、`symbols` (読んだ記号すべて：名前・CDF の名前・読む前の CDF・値・ビット位置)、
  `initial_cdf(key)`・`av1.symbol_prob(cdf, value)`、`film_grain` (粒子の値・作った粒子の画像 `luma_grain`・`scaling`・`noise`)。
  モード番号：0 DC、1〜8 が V・H・D45・D135・D113・D157・D203・D67、9 SMOOTH、10 SMOOTH_V、11 SMOOTH_H、12 PAETH、13 CfL (色だけ)。
  変換の種類の名前は「縦_横」：ADST_DCT は縦が ADST・横が DCT (仕様の 7.13.3)。
- `vlib/ui.py`：`cb_color(v)`・`cr_color(v)`・`chroma_image(plane, "cb"/"cr")` (Cb・Cr の塗り分け)、`gray(v)`、`CellGrid` (数のマス。
  場面には `.cells` と `.nums` を別々に入れる。Indicate などでマスのまとまりを場面に入れたら、あとで外して `bring_to_front(nums)`)、
  `text_color_on(色)`、`compare_card(n_rows, center, new)` (比較表。`CARD_ROWS` の最初の n_rows 行。new 行目を明るく)、`HEIC_COL`。
- `vlib/photoview.py`：HEIC 編と同じ `PhotoView`・`PLine`・`PRect`・`Grow`・`ViewAnim`・`move_view`・`TrackFade`・`cross_lines`。
  使い方は HEIC 編の AGENT_BRIEF (`videos/heic/AGENT_BRIEF.md`) と `videos/heic/scenes/s03_blocks.py`。写真は `view.check_ignore = True`。

## 色の約束

予測はシアン `CYAN`、元 − 予測 の差は紫 `PURPLE`、注目は黄 `YELLOW`、失われる・ずれは珊瑚 `CORAL`、まだ作っていない所は暗く沈める。
HEIC は灰青 `HEIC_COL`、AVIF は黄。Cb・Cr は `cb_color`・`cr_color` (128 は灰、Cb は少ないと黄・多いと青、Cr は少ないと青緑・多いと赤)。
ブロックの大きさの線の色は HEIC 編と同じ：64 白 `#eef0f4`、32 青 `#5aa7ea`、16 緑 `#7fd18b`、8 砂 `#e8c36a`、4 橙 `#f08a5d`。横長・縦長のブロックはピンク `#ff6fb5`。
算術符号の定規：選ばれた区間は黄、ほかの区間は区間ごとに少しずつ違う落ち着いた色。2 択のときは HEIC 編と同じ「はい」青・「いいえ」珊瑚。

## 比較表 (各シーンの {card})

S03〜S09 の最後の `{card}` で、`compare_card(k, center=(960, 420), new=k-1)` を出す (S03 は k=1 … S09 は k=7)。
出し方は見本 (s06_cfl.py の最後) と同じ：写真を少し暗くし、表を下から出して、新しい行を Indicate。シーンの終わりの 1.3 秒前に表を消して写真を戻す。
S01 の `{tools}` は `compare_card(0)` (頭の行だけ)。S12 は 7 行すべて。

## 見本で決まったこと・踏んだ落とし穴

- 手順は 1 歩ずつ。実データの小さな例で実際にやってみせ、結果は少し止める。手順の決まり (①②…) は出したままにして、いまの手順を光らせる。
- 同じものは同じオブジェクトのまま変形させる (S06 の 8×8 のマスは、明るさ → 平均 → 明暗のパターン → × −0.25 → 予測 と同じマスが変わる)。
- 数のマス (`CellGrid`) を Indicate すると、マスのまとまりが場面に入り直して数字の上に重なる。Indicate のあと `self.remove(まとまり)`・`self.add(cells)`・`self.bring_to_front(nums)`。
- 写真の上の四角 (`PRect`) が写真の端で立ち絵の領域に入るときは、写真の一部として `check_ignore = True`。
- キューに間に合わないときは、動きを 1 つの `play` にまとめる。検査の「遅れ」で確かめる。
- 画像を消すときは `img.animate.set_opacity(0)` (Group の FadeOut はちらつく)。
- 負の数はマイナス記号 `−`。

## シーンのつなぎ目

PHOTO = `PhotoView(rgb_decoded(), (960, 386), 1040, 692)` (写真だけ、線なし、暗くしない)。

| シーン | 担当 | 最初の画面 | 最後の画面 |
|---|---|---|---|
| S01 | A | 空 | タイトル `jp("AVIFの中身をのぞく", 72)` を `px(960, 300)` |
| S02 | A | S01 と同じタイトル (最初の台詞で消す) | PHOTO |
| S03 | B | PHOTO | PHOTO |
| S04 | B | PHOTO | PHOTO |
| S05 | C | PHOTO | PHOTO |
| S06 | (見本、完成済み) | PHOTO | PHOTO |
| S07 | D | PHOTO | PHOTO |
| S08 | D | PHOTO | PHOTO |
| S09 | E | PHOTO | PHOTO |
| S10 | E | PHOTO | 空 |
| S11 | F | 空 | 空 |
| S12 | F | 空 | 空 (クレジットのあと) |

## 調べてある実データ (台詞の数字はこれ。assert で確かめる)

- S01：JPEG 品質 80 23,693 / WebP 品質 80 16,974 / HEIC 品質 45 13,368 (`cat_q45.heic`) / AVIF 13,179 バイト。元とのずれ 2.61 / 2.72 / 2.65 / 2.69。差 189。
  ブラウザの対応：Chrome 85 (2020 年 8 月)・Firefox 93 (2021 年 10 月)・Safari 16 (2022 年 9 月)。AOMedia の設立 2015 年。
- S02：箱 ftyp 32・meta 235・mdat 12,912 (HEIC は 24・385・12,959)。av1C 12、hvcC 122、HEIC だけの clap 40 (meta の差 150)。
  OBU：区切り 2 バイト・設定 12 バイト (頭 2 ＋ 中身 10)・フレーム 12,890 バイト (頭 3 ＋ 12,887)。設定の 10 バイトの中身は `dec().fields` (幅 −1 = 450 を 9 ビット、高さ −1 = 299、still_picture = 1、
  enable_filter_intra 1・enable_intra_edge_filter 1・enable_superres 0・enable_cdef 1・enable_restoration 0・film_grain_params_present 0 など)。
- S03：64×64 の (横 2, 縦 1) = 画素 (128, 64)。64 は 4 分割、左上 32 も 4 分割、その右下の 16×16 (144, 80) が「横に 2 分割」(まぶたの輪郭)。
  右下の 32×32 (160, 96) の中の 16×16 が「縦に 2 分割」。この画像の分割は NONE・HORZ・VERT・SPLIT の 4 種類だけ。横長・縦長のブロックは 44 個。
  画像の右端 (x 448〜) と下端は、はみ出す所で自動的に決まる分割 (coded が split_or_horz / split_or_vert / implied) がある。
- S04：明るさの 16×16 (208, 128) が V (90°) ＋ 3 段 = 99°。元 (`source_yuv()[0]`) とのずれ：真上のまま 14.07 → 実際 5.89 (`av1.intra_predict` に angle_delta=0 の引数を渡して作り直す)。
  8 方向 = 45・67・90・113・135・157・180・203 度、傾きは 3 度ずつ −3〜+3 段。この画像の明るさで使われた角度は 56 通りのうち 46 通り。傾きは 8×8 以上のブロックだけ。
- S05：Paeth の例 (208, 144) 16×16 (目尻)。スムースの例 (64, 96) 32×32 (ぼけた背景)。明るさの予測の種類の数：DC 261・SMOOTH 99・H 68・D203 37・V 27・D157 22・D67 19・D135 18・D45 15・PAETH 13・D113 4 (SMOOTH_V・SMOOTH_H は 0)。
- S07：左から予測 (H) の 8×8 は 25 個、元とのずれの列ごとの平均 3.8〜11.6 (右ほど大きい)、行ごとはほぼ平ら。上から予測 (V) の 8×8 は 12 個、行ごと 5.7〜12.9。
  明るさの係数のある変換：DCT_DCT 339・DCT_ADST (横だけ ADST) 167・ADST_DCT (縦だけ) 100・ADST_ADST 111・H_DCT 4。H で予測したブロックの 46 / 75 が DCT_ADST、V の 17 / 29 が ADST_DCT。
- S08：読んだ記号 95,319 回 (うち 1 ビットそのままの読み取り 24,391)。coeff_base (0・1・2・3 以上の 4 択) が 53,280 回。予測の種類 (intra_frame_y_mode) は 13 択、CDF は上と左のブロックの種類で 5×5 通り。
- S09：CDEF を使った 64×64 は 40 個中 9 個 (cdef_idx 1：強さ y_pri 5)。その中の明るさの元とのずれ 1.444 (デブロッキングのあと) → 1.371 (CDEF のあと)。
  CDEF の向き dir：0 は 45° (／)、2 は水平、4 は −45° (＼)、6 は垂直、奇数はその間 (仕様 7.15.2 の partial の足し方から読んだもの。毛やひげの上に線を引いて、向きが合うか自分で確かめる)。2,166 個の 8×8 の向きは `cdef_log["blocks"]`。
- S10：`cat_grain.png` (猫の明るさに標準偏差 9 の粒子を足したもの)。同じ品質 60 で 13,179 → 25,872 バイト (`cat_grain_q60.avif`)。
  粒子の作り直し `cat_grain_fg.avif` 9,531 バイト、そのまま圧縮 `cat_grain_q44.avif` 8,783 バイト。粒子を足した元とのずれ 7.6 / 9.3。粒子の値は約 140 バイト (1,115 ビット。`fields` のうち film grain の値)。
  明るさごとの強さ `point_y_value`・`point_y_scaling` (11 点)、となりとの似かたの係数 `ar_coeffs_y_plus_128` (24 個)。粒子の見本の画像 `film_grain["luma_grain"]` (73×82)。
- S11：4KB くらい：JPEG 品質 5 3,797 (ずれ 11.0)・WebP 品質 10 3,898 (5.6)・HEIC 品質 25 3,791 (4.9)・AVIF 品質 30 3,750 (4.9)。保存の時間は `data/encode_time.json` (AVIF / JPEG = 159 倍、AVIF は HEIC の 0.6 倍)。

## 報告に書くこと

- 作ったもの (流れを数行で) と尺。台詞を変えた所と理由。
- 検査の結果と、目で見て直した所 (シートを見て、文字の大きさ・中央の空き・重なりを直したか)。
- 自信のない所・確かめていない所・共通部品への要望。
