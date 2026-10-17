"""素材を assets/ に落とす（config/assets.yaml の一覧から）。

    uv run python tools/fetch_assets.py            # BGM・効果音・フォント
    uv run python tools/fetch_assets.py --check    # そろっているかだけ確かめる

立ち絵（assets/characters/<name>/parts.json + parts/）は自動では取らない。docs/setup.md を参照。
素材はどれも再配布できない、または再配布に条件があるので、リポジトリには入れていない（THIRD_PARTY.md）。
"""
import io
import sys
import time
import zipfile
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (X11; Linux x86_64) zundamon-explainer/fetch_assets"


def get(url, referer=None):
    h = {"User-Agent": UA}
    if referer:
        h["Referer"] = referer
    r = requests.get(url, headers=h, timeout=120)
    r.raise_for_status()
    return r.content


def main(check=False):
    man = yaml.safe_load((ROOT / "config" / "assets.yaml").read_text())
    missing = []
    zips = {}
    for kind in ("bgm", "se", "fonts"):
        sec = man[kind]
        for fn, meta in sec["files"].items():
            dst = ROOT / "assets" / kind / fn
            if dst.exists():
                continue
            if check:
                missing.append(str(dst.relative_to(ROOT)))
                continue
            url = meta["url"]
            if "member" in meta:
                if url not in zips:
                    zips[url] = zipfile.ZipFile(io.BytesIO(get(url)))
                data = zips[url].read(meta["member"])
            else:
                # 効果音ラボは、そのページから来たことを示さないと 403 になる
                data = get(url, referer=url.rsplit("/mp3/", 1)[0] + "/" if kind == "se" else None)
                time.sleep(0.5)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            print("got", dst.relative_to(ROOT))
    for name in man["characters"]["names"]:
        if not (ROOT / "assets" / "characters" / name / "parts.json").exists():
            missing.append(f"assets/characters/{name}/parts.json（立ち絵：docs/setup.md）")
    if missing:
        print("足りない素材:\n  " + "\n  ".join(missing))
        sys.exit(1)
    print("素材はそろっている")


if __name__ == "__main__":
    main("--check" in sys.argv)
