"""AV1 の仕様書 (markdown の原稿) から、定数と表をすべて抜き出して av1tables.py を作る。

    uv run python videos/avif/tools/gen_av1tables.py <av1-spec の場所>

抜き出すもの：
- 3 章の定数の表 (`NAME` | 値)
- 6・7 章の名前の表 (| 数 | NAME の行。KEY_FRAME、BLOCK_64X64、DCT_DCT など)
- 6〜10 章の ~~~~~ c の中の `Name[ ... ] = { ... }` (既定の CDF、走査の順、量子化の表など)
"""
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "av1tables.py"


def constants(spec):
    """3 章の表：`NAME` | 値"""
    out = {}
    for line in (spec / "03.symbols.md").read_text().splitlines():
        m = re.match(r"\|\s*`([A-Z0-9_]+)`\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2).replace("\\<", "<").replace("\\>", ">")
    return out


def enums(spec):
    """6・7 章の「| 数 | (数 |) NAME」の行。名前は最後の数の値"""
    out = {}
    for f in ("06.bitstream.syntax.md", "07.bitstream.semantics.md"):
        for line in (spec / f).read_text().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2 or not line.lstrip().startswith("|"):
                continue
            if sum(bool(re.fullmatch(r"[A-Z][A-Z0-9_]*_[A-Z0-9_]*", c)) for c in cells) != 1:
                continue   # 名前が 2 つ以上ある表 (cfl_alpha_signs など) は対応の表で、名前の定義ではない
            nums = []
            for c in cells:
                if re.fullmatch(r"-?\d+", c):
                    nums.append(int(c))
                elif re.fullmatch(r"[A-Z][A-Z0-9_]*", c) and nums and "_" in c:
                    if c in out and out[c] != nums[-1]:
                        raise ValueError(f"{c}: {out[c]} と {nums[-1]}")
                    out[c] = nums[-1]
                    break
                else:
                    break
    return out


def tables(spec):
    """~~~~~ c の中の Name[ dims ] = { ... }。[(名前, dims の文字列, 中身の文字列)]"""
    out = []
    files = sorted(spec.glob("0[6-9]*.md")) + [spec / "10.additional.tables.md"]
    for f in files:
        t = f.read_text()
        for blk in re.findall(r"~~~~~[^\n]*\n(.*?)~~~~~", t, re.S):
            for m in re.finditer(r"(?m)^\s*([A-Z][A-Za-z0-9_]*)\s*((?:\[[^\]=]*\]\s*)+)=\s*\{", blk):
                i, d = m.end(), 1
                while d:
                    d += (blk[i] == "{") - (blk[i] == "}")
                    i += 1
                body = blk[m.end() - 1:i]
                body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
                body = re.sub(r"//[^\n]*", "", body)
                dims = re.findall(r"\[([^\]]*)\]", m.group(2))
                out.append((m.group(1), dims, body))
    return out


def fmt(v, indent=0, width=118):
    """入れ子の list を、横に詰めて書く"""
    s = repr(v)
    if len(s) + indent <= width:
        return s
    if all(not isinstance(x, list) for x in v):
        lines, cur = [], ""
        for x in v:
            p = repr(x) + ", "
            if len(cur) + len(p) + indent + 1 > width:
                lines.append(cur.rstrip())
                cur = ""
            cur += p
        lines.append(cur.rstrip().rstrip(","))
        pad = " " * (indent + 1)
        return "[" + ("\n" + pad).join(lines) + "]"
    pad = " " * (indent + 1)
    return "[" + (",\n" + pad).join(fmt(x, indent + 1, width) for x in v) + "]"


def main(spec):
    spec = Path(spec)
    ns = {}
    lines = ['"""AV1 の定数と表。AV1 Bitstream & Decoding Process Specification (av1-spec の markdown の原稿) から',
             'gen_av1tables.py で自動で作ったもの。手で直さない。"""', "", "# ---- 3 章の定数"]
    for k, v in constants(spec).items():
        ns[k] = eval(v, {}, dict(ns))
        lines.append(f"{k} = {ns[k]}")
    lines.append("")
    lines.append("# ---- 6・7 章の名前 (表の値)")
    for k, v in enums(spec).items():
        if k in ns:
            assert ns[k] == v, k
            continue
        ns[k] = v
        lines.append(f"{k} = {v}")
    lines.append("")
    lines.append("# ---- 表")
    seen = {}
    for name, dims, body in tables(spec):
        py = body.replace("{", "[").replace("}", "]")
        py = re.sub(r"(\w)(\s*\n\s*)(\w)", r"\1,\2\3", py)   # 仕様書の Split_Tx_Size は行末の , が 1 つ抜けている
        try:
            val = eval(py, {}, dict(ns))
        except NameError as e:   # インター (動き) の表で、名前が仕様書の表にないもの
            print("とばす:", name, e)
            continue
        # 大きさの確かめ
        shape = []
        x = val
        while isinstance(x, list):
            shape.append(len(x))
            x = x[0] if x else None
        want = [eval(d.strip(), {}, dict(ns)) if d.strip() else None for d in dims]
        if want != [None] and len(want) == len(shape):
            for a, b in zip(want, shape):
                assert a is None or a == b, (name, want, shape)
        if name in seen:
            assert seen[name] == val, name
            continue
        seen[name] = val
        lines.append(f"{name} = {fmt(val, len(name) + 3)}")
    OUT.write_text("\n".join(lines) + "\n")
    print(OUT, len(seen), "個の表")


if __name__ == "__main__":
    main(sys.argv[1])
