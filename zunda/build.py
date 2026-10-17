"""書き出し（描画 → 立ち絵と字幕の合成 → 音 → 検査）を速く回す。

    ZX_VIDEO=gif uv run python -m zunda.build scene S05               # 1 シーン（540p の試写）
    ZX_VIDEO=gif uv run python -m zunda.build scene S05 --res 1080    # 1 シーン（本番の大きさ）
    ZX_VIDEO=gif uv run python -m zunda.build scene S05 --line S05_18  # その台詞のあたりだけ
    ZX_VIDEO=gif uv run python -m zunda.build scene S05 --from 100 --to 130   # 時刻の範囲だけ
    ZX_VIDEO=gif uv run python -m zunda.build all                     # 通し（1080p）

速くする仕組み（docs/speed.md）
- 1 シーンを数秒ずつの「かけら」に分け、別々のプロセスで同時に描く。かけらの前の部分は描かずに
  状態だけ進める（Manim の skip）。Manim の描画は 1 プロセス 1 コアなので、コアの数だけ並べられる。
- 描き終わったかけらから、立ち絵と字幕を重ねる（これも並行）。書き出しは GPU（NVENC）があれば使う。
- かけらをつないで 1 本にする（つなぎ目は再エンコードしない）。音・検査・シートも並行に作る。
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .paths import BUILD, ROOT, VIDEO, config, video_config

FPS = 30


def _jobs(n=None):
    j = n or config("render").get("jobs") or 0
    if not j:
        cores = os.cpu_count() or 4
        j = max(1, min(cores - 2, 12))
    return j


def _scene_file(sid):
    vdir = VIDEO.resolve()
    hits = sorted((vdir / "scenes").glob(f"{sid.lower()}_*.py"))
    if not hits:
        raise FileNotFoundError(f"scenes/{sid.lower()}_*.py がない")
    return hits[0]


def _timeline(sid):
    return json.loads((BUILD / "voice" / f"{sid}.json").read_text())


def _chunk_bounds(sid, start, end, jobs):
    """[start, end) をかけらに分ける境目。シーン全体なら最後は inf（最後のかけらが終わりまで描いて記録を書く）"""
    sec = config("render")["chunk_seconds"]
    n = max(1, min(jobs, math.ceil((end - start) / sec)))
    step = (end - start) / n
    return [start + step * k for k in range(n)] + [end]


def _render_chunk(sid, k, t_from, t_to, res, clip, last):
    """1 つのかけら：Manim で描いて、そのまま立ち絵と字幕を重ねる。返り値は (k, 合成済みの mp4, 描いた mp4, 開始, 終了)"""
    vdir = VIDEO.resolve()
    tag = f".c{k:02d}"
    media = BUILD / "media" / f"{sid}{tag}.{res}"
    if media.exists():
        shutil.rmtree(media)
    env = dict(os.environ, PV_RES=str(res), PV_FROM=str(t_from), PV_TO="inf" if last else str(t_to),
               PV_TAG=tag, PV_CLIP="1" if clip else "", PYTHONWARNINGS="ignore",
               PYTHONPATH=f"{ROOT}:{vdir}" + (":" + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""))
    log = BUILD / "media" / f"{sid}{tag}.{res}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as fh:
        p = subprocess.run([str(Path(sys.executable).parent / "manim"), "render", "-q", "h", "--media_dir", str(media), "--disable_caching",
                            str(_scene_file(sid)), sid], env=env, stdout=fh, stderr=subprocess.STDOUT, cwd=ROOT)
    if p.returncode != 0:
        raise RuntimeError(f"{sid}{tag} の描画に失敗：{log}\n" + "".join(open(log).readlines()[-25:]))
    win = json.loads((BUILD / "render" / f"{sid}{tag}.window.json").read_text())
    found = list(media.glob(f"videos/**/{res}p30/{sid}.mp4"))
    if not found or win["end"] - win["start"] < 0.5 / FPS:
        return k, None, None, win["start"], win["end"]          # 描くものがなかった（長い待ちの途中など）
    rendered = BUILD / "render" / f"{sid}{tag}.mp4"
    shutil.copy(found[0], rendered)
    return k, rendered, win["start"], win["end"]


def _compose_chunk(sid, k, rendered, f0, f1, res):
    """かけら 1 つに立ち絵と字幕を重ねる。フレームの範囲 [f0, f1) はちょうどその枚数にそろえる（足りなければのばす）"""
    from .compose import compose
    return k, compose(sid, src=rendered, dst=BUILD / "comp" / f"{sid}.c{k:02d}.mp4", scale=res / 1080,
                      f0=f0, f1=f1)


def _frame_ranges(results, n_end):
    """描いたかけら [(k, 映像, 開始, 終了)] → 隙間も重なりもないフレームの範囲。
    Manim は描くときは時刻をフレーム単位で、描かないとき（skip）は秒のまま進めるので、かけらの境目の時刻が
    少しずれる。境目は次のかけらの開始時刻で決め、最後はシーン（または範囲）の終わりまでにする。"""
    rs = [r for r in sorted(results) if r[1]]
    starts = [int(round(r[2] * FPS)) for r in rs]
    ends = starts[1:] + [n_end]
    return [(r[0], r[1], a, max(a + 1, b)) for r, a, b in zip(rs, starts, ends)]


def _concat(parts, dst):
    lst = Path(str(dst) + ".txt")
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(dst)], check=True)
    lst.unlink()
    return dst


def _tasks(sid, res, t_from, t_to, clip, jobs):
    tl = _timeline(sid)
    end = tl["duration"] if t_to is None else min(t_to, tl["duration"])
    whole = t_from <= 0 and t_to is None
    b = _chunk_bounds(sid, t_from, end, jobs)
    n = len(b) - 1
    return [(sid, k, b[k], b[k + 1], res, clip and k == 0, whole and k == n - 1) for k in range(n)]


def _finish_scene(sid, comps, rends, start, end, window, wav):
    """かけらをつなぎ、音を付け、（シーン全体なら）検査とシートを作る"""
    suffix = "" if window is None else f"@{window[0]:g}-{window[1]:g}"
    comp = _concat(comps, BUILD / "comp" / f"{sid}{suffix}.mp4")
    if window is None:
        _concat(rends, BUILD / "render" / f"{sid}.mp4")
    for p in comps + rends:
        Path(p).unlink(missing_ok=True)
    if wav is None:          # 通し：音はあとでまとめて作る
        return comp
    out = BUILD / "out" / f"{sid}{suffix}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(comp), "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
                    "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(out)], check=True)
    if window is None:
        procs = [subprocess.Popen([sys.executable, str(ROOT / "tools" / t), sid], stdout=subprocess.DEVNULL if t == "sheet.py" else None)
                 for t in ("check.py", "sheet.py")]
        for p in procs:
            if p.wait():
                raise RuntimeError(f"{sid} の検査かシートに失敗")
    return out


def _audio(sid):
    from .master import scene_audio
    return scene_audio(sid)


def build_scenes(sids, res, t_from=0.0, t_to=None, clip=False, jobs=None, audio=True):
    """描画（かけらごとに並行）→ 合成（かけらごとに並行）→ シーンごとにつなぐ。音は最初から並行で作る"""
    jobs = _jobs(jobs)
    from .compose import _has_nvenc
    os.environ["ZX_NVENC"] = "1" if _has_nvenc() else "0"
    tasks = {sid: _tasks(sid, res, t_from, t_to, clip, jobs) for sid in sids}
    window = None if (t_from <= 0 and t_to is None) else (t_from, t_to if t_to is not None else _timeline(sids[0])["duration"])
    rendered = {sid: [] for sid in sids}
    composed = {sid: [] for sid in sids}
    ranges = {}
    outs = {}
    t = time.time()
    with ProcessPoolExecutor(jobs) as ex:
        audio_f = {sid: ex.submit(_audio, sid) for sid in sids} if audio else {}
        pending = {ex.submit(_render_chunk, *a): ("r", a[0]) for ts in tasks.values() for a in ts}
        while pending:
            for f in as_completed(list(pending)):
                kind, sid = pending.pop(f)
                if kind == "r":
                    rendered[sid].append(f.result())
                    if len(rendered[sid]) == len(tasks[sid]):
                        n = int(round(_timeline(sid)["duration"] * FPS))
                        n_end = n if window is None else min(n, int(round(window[1] * FPS)))
                        ranges[sid] = _frame_ranges(rendered[sid], n_end)
                        print(f"  {sid} 描画 {time.time() - t:.0f}s（{len(tasks[sid])} かけら）", flush=True)
                        for k, src, f0, f1 in ranges[sid]:
                            pending[ex.submit(_compose_chunk, sid, k, src, f0, f1, res)] = ("c", sid)
                else:
                    composed[sid].append(f.result())
                    if len(composed[sid]) == len(ranges[sid]):
                        comps = [c for _, c in sorted(composed[sid])]
                        rends = [r[1] for r in ranges[sid]]
                        start, end = ranges[sid][0][2] / FPS, ranges[sid][-1][3] / FPS
                        wav = audio_f[sid].result() if audio else None
                        outs[sid] = _finish_scene(sid, comps, rends, start, end, window, wav)
                        print(f"{outs[sid]}  ({time.time() - t:.0f}s)", flush=True)
                break
    return outs


def _line_window(sid, line_id, pad=0.6):
    for ln in _timeline(sid)["lines"]:
        if ln["id"] == line_id:
            return max(0.0, ln["start"] - pad), ln["end"] + pad
    raise KeyError(line_id)


def main():
    ap = argparse.ArgumentParser(prog="zunda.build")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scene", help="シーンを書き出す（既定は 540p の試写）")
    s.add_argument("scenes", nargs="+")
    s.add_argument("--res", type=int, default=None)
    s.add_argument("--from", dest="t_from", type=float, default=None)
    s.add_argument("--to", dest="t_to", type=float, default=None)
    s.add_argument("--line", default=None, help="この台詞のあたりだけ（例：S05_18）")
    s.add_argument("--jobs", type=int, default=None)
    a = sub.add_parser("all", help="通し（1080p）")
    a.add_argument("--jobs", type=int, default=None)
    args = ap.parse_args()

    if args.cmd == "scene":
        res = args.res or config("render")["preview_res"]
        if args.line:
            t_from, t_to = _line_window(args.scenes[0], args.line)
        else:
            t_from, t_to = args.t_from or 0.0, args.t_to
        partial = t_from > 0 or t_to is not None
        build_scenes(args.scenes, res, t_from, t_to, clip=partial, jobs=args.jobs)
    else:
        from .script import load
        from . import voice, master
        sids = list(load())
        voice.main()
        build_scenes(sids, 1080, jobs=args.jobs, audio=False)
        for sid in sids:
            subprocess.run([sys.executable, str(ROOT / "tools" / "check.py"), sid], check=True, stdout=subprocess.DEVNULL)
        slug = video_config()["slug"]
        master.build(sids, f"{slug}_video")
        subprocess.run([sys.executable, str(ROOT / "tools" / "description.py")], check=True, stdout=subprocess.DEVNULL)
        o = BUILD / "out"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(o / f"{slug}_video.mp4"), "-vf", "scale=854:480",
                        "-c:v", "libx264", "-crf", "24", "-c:a", "aac", "-b:a", "128k", str(o / f"{slug}_video_480p.mp4")],
                       check=True)
        for sid in sids:
            n = sum(1 for l in (BUILD / "check" / f"{sid}.txt").read_text().splitlines() if l.strip())
            print(f"{sid}: {n} 件")


if __name__ == "__main__":
    main()
