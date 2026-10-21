"""PLAN.md を、対話形式のブログ記事のような HTML にする (台詞の確認用)。

    uv run python tools/plan_view.py webp        # → videos/webp/build/plan.html

- 台詞は話し手の顔 (表情どおり) と吹き出し。[表記|よみ] はふりがな、{cue} は小さな印、(+秒) は間の印。
- `→` の画面の案は吹き出しの下のカード。build/voice/SNN.json があれば、台詞の時刻と VOICEVOX の読み (kana) も出す。
- 顔は立ち絵から作るので、HTML は build/ に置く (コミットしない)。立ち絵がなければ頭文字の丸で代わりにする。
"""
import base64
import html
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zunda.script import CUE_RE, HEAD_RE, LINE_RE, RUBY_RE, SPACE_RE  # noqa: E402

ICON_BOX = {"Z": (340, 190, 780, 630), "M": (291, 60, 761, 530)}   # 立ち絵の中の顔の範囲 (px)
EXPRS = ["通常", "笑", "驚", "困", "考", "得意"]


def faces():
    """{(話し手, 表情): data URI}。立ち絵がなければ空"""
    try:
        from PIL import ImageOps

        from zunda import character
        from zunda.compose import BASE, EXPR
        from zunda.paths import config
        sp = config("characters")["speakers"]
    except Exception:
        return {}
    out = {}
    for k in ("Z", "M"):
        for e in EXPRS:
            try:
                st = dict(BASE[k])
                st.update(EXPR[k][e])
                im = character.render(sp[k]["name"], st).crop(ICON_BOX[k]).resize((144, 144))
            except Exception:
                return {}
            if sp[k].get("placement", {}).get("flip"):
                im = ImageOps.mirror(im)
            b = io.BytesIO()
            im.save(b, "PNG", optimize=True)
            out[(k, e)] = "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()
    return out


def inline(s, cue_cls="cue"):
    """本文の装飾：ふりがな、キュー、太字、コード"""
    s = SPACE_RE.sub("", s) if cue_cls == "cue" else s
    parts = []
    pos = 0
    pat = re.compile(r"\[([^|\]]+)\|([^\]]+)\]|\{(\w+)\}|\*\*(.+?)\*\*|`([^`]+)`")
    for m in pat.finditer(s):
        parts.append(html.escape(s[pos:m.start()]))
        if m.group(1):
            parts.append(f"<ruby>{html.escape(m.group(1))}<rt>{html.escape(m.group(2))}</rt></ruby>")
        elif m.group(3):
            parts.append(f'<span class="{cue_cls}" data-cue="{m.group(3)}">{m.group(3)}</span>')
        elif m.group(4):
            parts.append(f"<strong>{inline(m.group(4), cue_cls)}</strong>")
        else:
            parts.append(f"<code>{html.escape(m.group(5))}</code>")
        pos = m.end()
    parts.append(html.escape(s[pos:]))
    return "".join(parts)


def md_block(lines):
    """前置き (最初のシーンより前) の簡単な Markdown"""
    out, in_list = [], False
    for ln in lines:
        if ln.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(ln[2:], 'cue-n')}</li>")
            continue
        if ln.startswith("  ") and in_list and out:
            out[-1] = out[-1][:-5] + " " + inline(ln.strip(), "cue-n") + "</li>"
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if not ln.strip() or ln.strip() == "---":
            continue
        if ln.startswith("# "):
            continue
        if ln.startswith("## "):
            out.append(f"<h3>{inline(ln[3:], 'cue-n')}</h3>")
        else:
            out.append(f"<p>{inline(ln, 'cue-n')}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def fmt_t(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def build(video):
    vdir = ROOT / "videos" / video
    text = (vdir / "PLAN.md").read_text()
    rows = text.splitlines()
    title = next((r[2:].strip() for r in rows if r.startswith("# ")), video)
    first = next((i for i, r in enumerate(rows) if HEAD_RE.match(r)), len(rows))
    pre = md_block(rows[:first])
    voice = {}
    for p in (vdir / "build" / "voice").glob("S*.json"):
        d = json.loads(p.read_text())
        voice[p.stem] = d
    face = faces()
    from zunda.paths import config
    sp = config("characters")["speakers"]
    names = {k: v.get("display", k) for k, v in sp.items()}

    body, toc = [], []
    scene, idx, total = None, 0, 0.0
    pending_note = []

    def flush_notes():
        if pending_note:
            body.append('<div class="note"><span class="note-tag">画面</span>' + "<br>".join(pending_note) + "</div>")
            pending_note.clear()
    for r in rows[first:]:
        if m := HEAD_RE.match(r):
            flush_notes()
            if scene:
                body.append("</section>")
            scene, idx = m.group(1), 0
            dur = voice.get(scene, {}).get("duration")
            total += dur or 0
            dtxt = f'<span class="dur">{fmt_t(dur)}</span>' if dur else ""
            body.append(f'<section class="scene" id="{scene}"><h2><span class="sid">{scene}</span>'
                        f'{inline(m.group(2), "cue-n")}{dtxt}</h2>')
            toc.append(f'<a href="#{scene}"><span class="sid">{scene}</span>{html.escape(m.group(2))}'
                       f'{"<span class=dur>" + fmt_t(dur) + "</span>" if dur else ""}</a>')
            continue
        if not scene:
            continue
        if m := LINE_RE.match(r):
            flush_notes()
            k, expr, raw, pause = m.groups()
            expr = expr or "通常"
            idx += 1
            lid = f"{scene}_{idx:02d}"
            vl = next((x for x in voice.get(scene, {}).get("lines", []) if x["id"] == lid), None)
            meta = f'<span class="who">{names[k]}</span><span class="expr">{expr}</span><span class="lid">{lid}</span>'
            if vl:
                meta += f'<span class="time">{fmt_t(vl["start"])}</span>'
            av = (f'<span class="face f{k}{EXPRS.index(expr)}" title="{names[k]}（{expr}）"></span>' if (k, expr) in face
                  else f'<span class="ph">{names[k][0]}</span>')
            ptxt = f'<span class="pause">間 {pause}s</span>' if pause else ""
            kana = f'<div class="kana">{html.escape(vl["kana"])}</div>' if vl and vl.get("kana") else ""
            body.append(f'<div class="line {k}"><div class="av">{av}</div><div class="col"><div class="meta">{meta}</div>'
                        f'<div class="bubble">{inline(raw)}{ptxt}</div>{kana}</div></div>')
            continue
        if r.startswith("→"):
            pending_note.append(inline(r[1:].strip(), "cue-n"))
        elif r.startswith("  ") and pending_note:
            pending_note[-1] += " " + inline(r.strip(), "cue-n")
        elif r.strip():
            flush_notes()
            body.append(f'<p class="aside">{inline(r.strip(), "cue-n")}</p>')
    flush_notes()
    if scene:
        body.append("</section>")
    tot = f"（音声 {fmt_t(total)}）" if total else ""
    fcss = "\n".join(f'.f{k}{EXPRS.index(e)} {{ background-image:url({u}); }}' for (k, e), u in face.items())
    page = TEMPLATE.format(title=html.escape(title), tot=tot, pre=pre, toc="\n".join(toc), body="\n".join(body),
                           faces=fcss)
    out = vdir / "build" / "plan.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(out, "顔あり" if face else "顔なし (立ち絵がない)")


TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@500;700&display=swap" rel="stylesheet">
<style>
:root {{ --bg:#f6f4ef; --paper:#fffdf9; --ink:#2a2d34; --dim:#7b8090; --line:#e4e0d6;
  --z:#7cc35a; --zb:#eef8e6; --m:#e3609a; --mb:#fdebf3; --note:#f1f3f8; --cue:#8a74d8; --yel:#c9930f; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#14161c; --paper:#1c1f27; --ink:#eef0f4;
  --dim:#8a90a0; --line:#2e3240; --zb:#22301c; --mb:#36202b; --note:#232733; --cue:#a58bf0; --yel:#f2c14e; }} }}
:root[data-theme="dark"] {{ --bg:#14161c; --paper:#1c1f27; --ink:#eef0f4; --dim:#8a90a0; --line:#2e3240;
  --zb:#22301c; --mb:#36202b; --note:#232733; --cue:#a58bf0; --yel:#f2c14e; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Zen Maru Gothic",sans-serif; line-height:1.75; }}
header {{ max-width:860px; margin:0 auto; padding:40px 16px 8px; }}
h1 {{ font-size:28px; margin:0 0 4px; }}
.sub {{ color:var(--dim); font-size:14px; }}
.bar {{ position:sticky; top:0; z-index:5; background:color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter:blur(6px);
  border-bottom:1px solid var(--line); }}
.bar .in {{ max-width:860px; margin:0 auto; padding:8px 16px; display:flex; gap:16px; flex-wrap:wrap; font-size:14px; color:var(--dim); }}
.bar label {{ cursor:pointer; user-select:none; }}
main {{ max-width:860px; margin:0 auto; padding:0 16px 80px; }}
details.pre {{ background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:6px 18px; margin:16px 0; font-size:15px; }}
details.pre summary {{ cursor:pointer; font-weight:700; padding:6px 0; }}
nav.toc {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:6px; margin:16px 0 8px; }}
nav.toc a {{ background:var(--paper); border:1px solid var(--line); border-radius:10px; padding:6px 10px; color:var(--ink);
  text-decoration:none; font-size:14px; display:flex; gap:8px; align-items:center; }}
nav.toc a:hover {{ border-color:var(--dim); }}
.sid {{ font-family:ui-monospace,monospace; font-size:12px; color:var(--dim); }}
.dur {{ margin-left:auto; font-family:ui-monospace,monospace; font-size:12px; color:var(--dim); }}
.scene {{ margin-top:48px; }}
.scene h2 {{ display:flex; align-items:baseline; gap:10px; font-size:22px; border-bottom:2px solid var(--line); padding-bottom:6px; }}
.line {{ display:flex; gap:12px; margin:18px 0; align-items:flex-start; }}
.line.M {{ flex-direction:row-reverse; }}
.av {{ flex:0 0 64px; width:64px; height:64px; border-radius:50%; overflow:hidden; border:3px solid var(--z); background:var(--paper); }}
.line.M .av {{ border-color:var(--m); }}
.av .face {{ display:block; width:100%; height:100%; background-size:cover; }}
{faces}
.av .ph {{ display:flex; width:100%; height:100%; align-items:center; justify-content:center; font-weight:700; font-size:24px; }}
.col {{ max-width:min(620px, calc(100% - 76px)); display:flex; flex-direction:column; }}
.line.M .col {{ align-items:flex-end; }}
.meta {{ display:flex; gap:8px; font-size:12px; color:var(--dim); margin:0 6px 2px; align-items:baseline; }}
.who {{ font-weight:700; color:var(--z); }}
.line.M .who {{ color:var(--m); }}
.expr {{ border:1px solid var(--line); border-radius:6px; padding:0 6px; }}
.lid, .time {{ font-family:ui-monospace,monospace; }}
.bubble {{ position:relative; background:var(--zb); border-radius:4px 18px 18px 18px; padding:10px 16px; font-size:18px; font-weight:500; }}
.line.M .bubble {{ background:var(--mb); border-radius:18px 4px 18px 18px; }}
ruby rt {{ font-size:10px; color:var(--dim); }}
.cue {{ display:inline-block; font-family:ui-monospace,monospace; font-size:10px; line-height:1; color:var(--cue);
  border:1px solid currentColor; border-radius:4px; padding:2px 4px; margin:0 2px; vertical-align:2px; opacity:.85; }}
.cue-n {{ font-family:ui-monospace,monospace; font-size:11px; color:var(--cue); border:1px solid currentColor; border-radius:4px; padding:0 4px; }}
.cue.hl, .cue-n.hl {{ background:var(--cue); color:var(--paper); }}
.pause {{ display:inline-block; margin-left:8px; font-size:11px; color:var(--dim); border:1px dashed var(--dim); border-radius:10px; padding:0 8px; vertical-align:2px; }}
.kana {{ font-family:ui-monospace,monospace; font-size:11px; color:var(--dim); margin:4px 8px 0; word-break:break-all; }}
.note {{ margin:6px 86px 18px; background:var(--note); border-left:3px solid var(--dim); border-radius:6px; padding:8px 14px;
  font-size:14px; color:var(--ink); }}
.note-tag {{ display:inline-block; font-size:11px; font-weight:700; color:var(--dim); margin-right:8px; }}
.note strong {{ color:var(--yel); }}
code {{ font-family:ui-monospace,monospace; font-size:.9em; background:var(--line); border-radius:4px; padding:0 4px; }}
p.aside {{ color:var(--dim); font-size:14px; }}
body.no-cue .cue {{ display:none; }}
body.no-note .note {{ display:none; }}
body.no-kana .kana {{ display:none; }}
@media (max-width:600px) {{ .note {{ margin:6px 0 18px; }} .bubble {{ font-size:16px; }} .av {{ flex-basis:48px; width:48px; height:48px; }} }}
</style></head>
<body class="no-kana">
<header><h1>{title}</h1><div class="sub">PLAN.md から作った読みやすい版 {tot}</div></header>
<div class="bar"><div class="in">
<label><input type="checkbox" id="t-cue" checked> キュー</label>
<label><input type="checkbox" id="t-note" checked> 画面の案</label>
<label><input type="checkbox" id="t-kana"> 読み (VOICEVOX)</label>
</div></div>
<main>
<details class="pre"><summary>前提・素材・画面の約束</summary>{pre}</details>
<nav class="toc">{toc}</nav>
{body}
</main>
<script>
const tg = (id, cls, inv) => document.getElementById(id).addEventListener('change', e => {{
  document.body.classList.toggle(cls, inv ? e.target.checked : !e.target.checked); }});
tg('t-cue', 'no-cue'); tg('t-note', 'no-note'); tg('t-kana', 'no-kana');
document.querySelectorAll('[data-cue]').forEach(el => {{
  const sc = el.closest('section'); const name = el.dataset.cue;
  const set = on => sc && sc.querySelectorAll(`[data-cue="${{name}}"]`).forEach(x => x.classList.toggle('hl', on));
  el.addEventListener('mouseenter', () => set(true)); el.addEventListener('mouseleave', () => set(false));
}});
</script>
</body></html>
"""


if __name__ == "__main__":
    build(sys.argv[1])
