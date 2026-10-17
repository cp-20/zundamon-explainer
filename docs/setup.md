# 環境づくり

## 必要なもの

- Linux（WSL2 で動作を確認）、[uv](https://docs.astral.sh/uv/)、ffmpeg、Manim の依存（cairo・pango など）
- Python は必ず uv 経由で動かす（`uv run python ...`）。
- VOICEVOX エンジン（GPU 版を推奨）

```bash
uv sync
docker run -d --name voicevox --gpus all -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:nvidia-latest
curl 127.0.0.1:50021/version
```

PC を再起動すると VOICEVOX のコンテナが止まっていることがある。音声が作れないときは `docker start voicevox`。

## 素材

素材は再配布できないので、リポジトリに入っていない（[../THIRD_PARTY.md](../THIRD_PARTY.md)）。

```bash
uv run python tools/fetch_assets.py          # BGM・効果音・フォント → assets/
uv run python tools/fetch_assets.py --check  # そろったか確かめる
```

### 立ち絵

坂本アヒル 様の「ずんだもん」「四国めたん」の立ち絵素材（PSD、PSDTool 形式）を配布元から入手し、利用規約を確認してから書き出す。

```bash
uv run --extra psd python tools/export_psd_parts.py <ずんだもん.psd> assets/characters/zundamon
uv run --extra psd python tools/export_psd_parts.py <四国めたん.psd> assets/characters/metan
```

書き出すと `parts.json`（レイヤーの木構造）と `parts/*.png` ができる。表情・口・まばたきに使うレイヤーの名前は
`config/characters.yaml` に書いてある。PSD の版が違って名前が合わないときは、`parts.json` を見て YAML を直す。

## 動画ごとのデータ

各動画の `videos/<name>/README.md` を参照。立ち絵から作る画像（PNG 編の題材の画像、GIF 編の動くスタンプなど）は
リポジトリに入れていないので、その動画の `tools/` で作る。
