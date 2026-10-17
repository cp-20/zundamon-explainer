#!/usr/bin/env bash
# 台詞の音声と時刻表を作る（VOICEVOX が必要）。  bin/voice.sh <video> [S05 ...]（省略で全シーン）
set -e
source "$(dirname "$0")/env.sh"
uv run python -m zunda.voice "$@"
