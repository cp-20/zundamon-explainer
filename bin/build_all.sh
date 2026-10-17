#!/usr/bin/env bash
# 通しビルド（1080p）。音声→各シーンの描画と合成（並列）→検査→音の仕上げ→概要欄→480p の試写版。
#   bin/build_all.sh <video> [並列数=4]
# 出力：videos/<video>/build/out/<slug>_video.mp4、<slug>_video_480p.mp4、description.txt
set -e
source "$(dirname "$0")/env.sh"
J=${1:-4}
SLUG=$(uv run python -c "from zunda.paths import video_config; print(video_config()['slug'])")
SCENES=$(uv run python -c "from zunda.script import load; print(' '.join(load()))")
uv run python -m zunda.voice
printf '%s\n' $SCENES | xargs -P "$J" -I{} sh -c "'$ROOT/bin/render.sh' '$ZX_VIDEO' {} 1080 >/dev/null && uv run python -m zunda.compose {} >/dev/null && uv run python tools/check.py {} >/dev/null"
uv run python -m zunda.master all
uv run python tools/description.py > /dev/null
O="$VDIR/build/out"
ffmpeg -v error -y -i "$O/${SLUG}_video.mp4" -vf scale=854:480 -c:v libx264 -crf 24 -c:a aac -b:a 128k "$O/${SLUG}_video_480p.mp4"
for f in "$VDIR"/build/check/S*.txt; do echo "$(basename "$f" .txt): $(grep -c . "$f") 件"; done
