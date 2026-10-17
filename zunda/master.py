"""音声の仕上げと最終の書き出し。

    uv run python -m zunda.master S05            # 1シーンの試し（build/out/S05.mp4）
    uv run python -m zunda.master all            # 通し（build/out/<slug>_video.mp4）

声・効果音・BGM を混ぜる。BGM は台詞の間だけ下げ（ダッキング）、全体を -14 LUFS に揃える。
"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln

from .paths import ASSETS, BUILD, config, video_config

_A = config("audio")
SR = _A["sample_rate"]
BGM_GAIN_DB, DUCK_DB, SE_GAIN_DB = _A["bgm_gain_db"], _A["duck"]["depth_db"], _A["se_gain_db"]
TARGET_LUFS = _A["target_lufs"]


def bgm_plan():
    """シーン → 曲（video.yaml の bgm。書いていないシーンは default）"""
    b = video_config().get("bgm") or {}
    return b.get("scenes", {}), b.get("default", "main")


def load(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32).reshape(-1, 2).copy()


def db(x):
    return 10 ** (x / 20)


def mix(scenes):
    tls = [json.loads((BUILD / "voice" / f"{s}.json").read_text()) for s in scenes]
    offs = np.cumsum([0] + [t["duration"] for t in tls])
    n = int(offs[-1] * SR) + SR
    voice = np.zeros((n, 2), np.float32)
    se = np.zeros((n, 2), np.float32)
    speech = np.zeros(n, bool)
    for s, tl, off in zip(scenes, tls, offs):
        v = load(BUILD / "voice" / f"{s}.wav")
        i = int(off * SR)
        voice[i:i + len(v)] += v[: n - i]
        for ln in tl["lines"]:
            speech[int((off + ln["start"]) * SR):int((off + ln["voice_end"]) * SR)] = True
        logp = BUILD / "log" / f"{s}.json"
        if logp.exists():
            for e in json.loads(logp.read_text())["se"]:
                a = load(ASSETS / "se" / f"{e['name']}.mp3") * db(SE_GAIN_DB + e.get("gain", 0))
                j = int((off + e["t"]) * SR)
                se[j:j + len(a)] += a[: n - j]
    # BGM：シーンの曲ごとに区間をつなぎ、切り替わりは 1.5 秒でクロスフェード
    bgm = np.zeros((n, 2), np.float32)
    plan, default = bgm_plan()
    segs = []
    for s, off, tl in zip(scenes, offs, tls):
        name = plan.get(s, default)
        if segs and segs[-1][0] == name:
            segs[-1][2] = off + tl["duration"]
        else:
            segs.append([name, off, off + tl["duration"]])
    xf = int(_A["bgm_crossfade"] * SR)
    for k, (name, t0, t1) in enumerate(segs):
        track = load(ASSETS / "bgm" / f"{name}.mp3")
        i0, i1 = int(t0 * SR), min(int(t1 * SR) + (xf if k + 1 < len(segs) else SR), n)
        L = i1 - i0
        reps = int(np.ceil(L / len(track)))
        seg = np.tile(track, (reps, 1))[:L].copy()
        fade = np.ones(L, np.float32)
        if k > 0:
            fade[:xf] = np.linspace(0, 1, xf)
        if k + 1 < len(segs):
            fade[-xf:] = np.minimum(fade[-xf:], np.linspace(1, 0, xf))
        else:
            fl = int(_A["bgm_fade_out"] * SR)
            fade[-fl:] = np.minimum(fade[-fl:], np.linspace(1, 0, fl))
        bgm[i0:i1] += seg * fade[:, None]
    # ダッキング：会話が続いている間（すき間 GAP_HOLD 秒未満）は下げたまま。
    # 長い間に入ったときだけ RELEASE 秒かけてゆっくり戻し、次の台詞の ATTACK 秒前から下げる。
    GAP_HOLD, ATTACK, RELEASE = _A["duck"]["hold_gap"], _A["duck"]["attack"], _A["duck"]["release"]
    hold = speech.copy()
    on = np.flatnonzero(np.diff(np.r_[0, speech.astype(np.int8), 0]) == 1)
    off = np.flatnonzero(np.diff(np.r_[0, speech.astype(np.int8), 0]) == -1)
    for a, b in zip(off[:-1], on[1:]):          # 台詞の終わり a → 次の台詞の始まり b
        if (b - a) / SR < GAP_HOLD:
            hold[a:b] = True
    for b in on:                                 # 先読み：台詞の前から下げ始める
        hold[max(b - int(ATTACK * SR), 0):b] = True
    target = np.where(hold, DUCK_DB, 0.0).astype(np.float32)
    env = np.zeros(n, np.float32)
    cur, blk = 0.0, 480
    dn, up = DUCK_DB / (ATTACK * SR / blk), -DUCK_DB / (RELEASE * SR / blk)   # ブロックごとの変化量（直線）
    for b in range(0, n, blk):
        tgt = target[b:b + blk].min()
        cur = max(tgt, cur + dn) if tgt < cur else min(tgt, cur + up)
        env[b:b + blk] = cur
    bgm *= db(BGM_GAIN_DB + env)[:, None]
    out = voice + se + bgm
    meter = pyln.Meter(SR)
    loud = meter.integrated_loudness(out)
    out *= db(TARGET_LUFS - loud)
    return out, offs


def write_wav(path, a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "-",
                    "-af", "alimiter=limit=0.89:level=false", "-c:a", "pcm_s16le", str(path)],
                   input=a.astype(np.float32).tobytes(), check=True)


def render_audio(scenes, name):
    """声・効果音・BGM を混ぜて −14 LUFS にした wav を build/out/<name>.wav に書く"""
    out = BUILD / "out"
    out.mkdir(parents=True, exist_ok=True)
    audio, offs = mix(scenes)
    wav = out / f"{name}.wav"
    write_wav(wav, audio)
    # リミッターで少し下がる分を測って補正し、もう一度書く
    got = pyln.Meter(SR).integrated_loudness(load(wav))
    if abs(got - TARGET_LUFS) > 0.05:
        write_wav(wav, audio * db(TARGET_LUFS - got))
    return wav, offs


def scene_audio(sid):
    """1 シーン分の音（試写用）"""
    return render_audio([sid], sid)[0]


def build(scenes, name):
    out = BUILD / "out"
    wav, offs = render_audio(scenes, name)
    lst = out / f"{name}.txt"
    lst.write_text("".join(f"file '{BUILD / 'comp' / (s + '.mp4')}'\n" for s in scenes))
    mp4 = out / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(mp4)], check=True)
    meter = pyln.Meter(SR)
    a = load(wav)
    print(mp4, f"{len(a) / SR:.1f}s", f"{meter.integrated_loudness(a):.2f} LUFS")
    return mp4, offs


if __name__ == "__main__":
    from .script import load as load_script
    arg = sys.argv[1:]
    if arg == ["all"]:
        build(sorted(load_script()), video_config()["slug"] + "_video")
    else:
        build(arg, "_".join(arg))
