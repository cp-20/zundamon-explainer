#!/usr/bin/env bash
# Manim で 1 シーンを描く（映像のみ）。  bin/render.sh <video> S05 [解像度=1080]  → videos/<video>/build/render/S05.mp4
set -e
source "$(dirname "$0")/env.sh"
S=$1; RES=${2:-1080}
F=$(ls "$VDIR"/scenes/$(echo "$S" | tr A-Z a-z)_*.py)
B="$VDIR/build"
mkdir -p "$B/media" "$B/render"
PV_RES=$RES uv run manim render -q h --media_dir "$B/media/$RES" --disable_caching "$F" "$S" >"$B/media/$S.$RES.log" 2>&1 \
  || { tail -30 "$B/media/$S.$RES.log"; exit 1; }
cp "$(find "$B/media/$RES/videos" -path "*/${RES}p30/$S.mp4" | head -1)" "$B/render/$S.mp4"
echo "$B/render/$S.mp4"
