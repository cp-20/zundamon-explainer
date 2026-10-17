#!/usr/bin/env bash
# シーンを書き出して確かめる（作業中の試写）。描画と合成は時間で分けて並行に行う（zunda/build.py）。
#   bin/pipeline.sh <video> S05                    # 540p でシーン全体 → 検査・シートも作る
#   bin/pipeline.sh <video> S05 --res 1080         # 本番の大きさ
#   bin/pipeline.sh <video> S05 --line S05_18      # その台詞のあたりだけ（直した所を素早く見る）
#   bin/pipeline.sh <video> S05 --from 100 --to 130
# 出力：videos/<video>/build/out/S05.mp4（部分なら S05@100-130.mp4）、build/check/S05.txt、build/sheet/S05.png
set -e
source "$(dirname "$0")/env.sh"
uv run python -m zunda.build scene "$@"
