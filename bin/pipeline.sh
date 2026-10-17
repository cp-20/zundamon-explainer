#!/usr/bin/env bash
# 1 シーンを 描画→立ち絵と字幕の合成→音→検査→シート まで通す（作業中の確認用）。
#   bin/pipeline.sh <video> S05 [解像度=540]
# 出力：videos/<video>/build/out/S05.mp4（プレビュー）、build/check/S05.txt（検査）、build/sheet/S05.png（シート）
set -e
source "$(dirname "$0")/env.sh"
S=$1; RES=${2:-540}
"$ROOT/bin/render.sh" "$ZX_VIDEO" "$S" "$RES"
PREV=""; [ "$RES" != "1080" ] && PREV="--preview"
uv run python -m zunda.compose "$S" $PREV
uv run python -m zunda.master "$S"
uv run python tools/check.py "$S"
uv run python tools/sheet.py "$S"
