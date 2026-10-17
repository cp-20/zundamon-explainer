# bin/*.sh 共通：動画の名前（videos/<name>）を受け取り、環境を整える
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V="$1"; shift || true
[ -n "$V" ] && [ -d "$ROOT/videos/$V" ] || { echo "usage: $(basename "$0") <video> ...   (videos/ の下: $(ls "$ROOT/videos" | tr '\n' ' '))" >&2; exit 2; }
export ZX_VIDEO="$V"
export VDIR="$ROOT/videos/$V"
export PYTHONPATH="$ROOT:$VDIR${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONWARNINGS=ignore
cd "$ROOT"
