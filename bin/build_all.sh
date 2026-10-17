#!/usr/bin/env bash
# 通しビルド（1080p）。音声 → 全シーンの描画と合成（かけらに分けて並行）→ 検査 → 音の仕上げ → 概要欄 → 480p の試写版。
#   bin/build_all.sh <video> [--jobs N]
# 出力：videos/<video>/build/out/<slug>_video.mp4、<slug>_video_480p.mp4、description.txt
set -e
source "$(dirname "$0")/env.sh"
uv run python -m zunda.build all "$@"
