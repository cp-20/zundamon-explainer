"""Export every leaf layer of a PSDTool-style PSD (坂本アヒル式立ち絵など) as PNG parts.

usage: uv run python tools/export_psd_parts.py <file.psd> <out_dir>

Writes <out_dir>/parts/*.png and <out_dir>/parts.json describing the layer tree
(bottom-to-top order, offsets, default visibility, PSDTool flags '*' radio / '!' forced).
zunda.character.PsdCharacter composes images from this at render time.
"""
import json
import sys
from pathlib import Path

from psd_tools import PSDImage


def main(src, out):
    psd = PSDImage.open(src)
    out = Path(out)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    counter = [0]

    def node(layer, path):
        name = layer.name
        d = {
            "name": name,
            "path": path,
            "visible": bool(layer.visible),
            "opacity": layer.opacity / 255,
            "blend": str(layer.blend_mode).split(".")[-1].lower(),
        }
        if layer.is_group():
            d["children"] = [node(c, f"{path}/{c.name}") for c in layer]
        else:
            counter[0] += 1
            fn = f"{counter[0]:04d}.png"
            if layer.bbox != (0, 0, 0, 0):
                # topil() gives raw pixels; layer opacity/blend handled by composer
                im = layer.topil()
                if im is not None:
                    im.convert("RGBA").save(out / "parts" / fn)
                    d["file"] = fn
                    d["offset"] = [layer.left, layer.top]
        return d

    tree = {"size": list(psd.size), "source": Path(src).name, "children": [node(l, l.name) for l in psd]}
    (out / "parts.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1))
    print("exported", counter[0], "layers ->", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
