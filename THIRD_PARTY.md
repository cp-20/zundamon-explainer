# 第三者の素材とライセンス

このリポジトリの MIT ライセンス（[LICENSE](LICENSE)）は、コード・文書・設定・自作のデータだけに適用される。
以下の素材は作者のものなので、それぞれの規約に従うこと。再配布できないものはリポジトリに入れていない
（`.gitignore` 済み。用意の仕方は [docs/setup.md](docs/setup.md)、一覧は [config/assets.yaml](config/assets.yaml)）。

## リポジトリに入れていないもの

### BGM — 甘茶の音楽工房

- https://amachamusic.chagasi.com/ ／ 規約 https://amachamusic.chagasi.com/terms.html
- 動画での利用は可（収益化も可）。クレジットは任意。
- **YouTube の Content ID への登録は禁止**。曲だけの再配布は禁止。
- 使った曲：昼下がりのハバネラ（main）、小さな足跡（main_alt）、Happy time（outro）、深海魚の遊泳（thinking）

### 効果音 — 効果音ラボ

- https://soundeffect-lab.info/ ／ 規約 https://soundeffect-lab.info/agreement/
- 動画での利用は可。クレジットは任意。素材としての再配布はしない。

### 立ち絵 — 坂本アヒル 様（ずんだもん・四国めたん）

- 配布元の利用規約に従うこと。PSD、書き出した部品（`assets/characters/`）、立ち絵から作った画像
  （PNG 編の `data/zundamon.png`、JPEG 編の `data/zunda_*`、GIF 編の `data/zunda_anim.gif` など）は再配布しない。

### 音声 — VOICEVOX

- VOICEVOX:ずんだもん、VOICEVOX:四国めたん。動画では「VOICEVOX:キャラクター名」のクレジットが必要。
  各キャラクターの利用規約（東北ずん子・ずんだもんプロジェクト、四国めたん）にも従うこと。
- 合成した音声はリポジトリに入れていない（`cache/`・`build/` は無視している）。

### フォント

- Zen Maru Gothic、M PLUS Rounded 1c、JetBrains Mono：SIL Open Font License 1.1。`tools/fetch_assets.py` で取得する。

## リポジトリに入れているもの

| ファイル | 出典とライセンス |
|---|---|
| `videos/jpeg/data/cat.png`、`videos/gif/data/cat.png`、およびそこから作った `cat_*.jpg`・`cat*.gif` | 「Chelsea the cat」Stefan van der Walt、CC0（scikit-image のサンプル画像 `skimage.data.chelsea`） |
| `videos/png/data/gradient.png`・`photoish.png`・`noise.png` | 自作の合成画像（MIT） |

## 公開した動画（GitHub Releases）

動画ファイルには上の素材が含まれる。視聴・紹介のために置いているもので、MIT ライセンスの対象ではない。
動画から素材（曲・効果音・立ち絵）を取り出して使わないこと。
