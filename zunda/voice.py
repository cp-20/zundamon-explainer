"""VOICEVOX で台詞を合成し、キュー・字幕ページ・口パクの時刻表を作る。

キュー時刻：キュー直前までの文を audio_query して mora 数 k を数え、
全文の mora 時刻表で k 番目の mora が始まる時刻を使う。
"""
import hashlib, io, json, wave
from pathlib import Path

import numpy as np
import requests

from .paths import BUILD, CACHE as CACHE_ROOT, config, merged, video_config
from .script import load

_V = merged("voice")
URL = _V["url"]
VOICE = _V["speakers"]  # PLAN.md の Z / M → speaker id, speedScale, intonationScale
SR = 24000
CACHE = CACHE_ROOT / "voicevox"


def user_dict():
    """表記, 読み, アクセント核。config/readings.yaml の共通分に、video.yaml の user_dict を足したもの"""
    try:
        extra = video_config().get("user_dict") or []
    except RuntimeError:
        extra = []
    return [tuple(x) for x in config("readings")["user_dict"]] + [tuple(x) for x in extra]


def _post(path, **kw):
    r = requests.post(URL + path, timeout=120, **kw)
    r.raise_for_status()
    return r


def setup_dict():
    have = {v["surface"]: k for k, v in requests.get(URL + "/user_dict", timeout=30).json().items()}
    for surface, pron, acc in user_dict():
        # VOICEVOX は表記を全角にして保存する
        full = surface.translate({c: c + 0xFEE0 for c in range(0x21, 0x7F)})
        params = dict(surface=surface, pronunciation=pron, accent_type=acc, word_type="PROPER_NOUN")
        if full in have or surface in have:
            requests.put(URL + f"/user_dict_word/{have.get(full) or have[surface]}", params=params, timeout=30).raise_for_status()
        else:
            _post("/user_dict_word", params=params)


def _cached(kind, key, fn):
    h = hashlib.sha1(json.dumps(key, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    p = CACHE / kind / h
    if p.exists():
        return p.read_bytes()
    data = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return data


DICT_VER = hashlib.sha1(json.dumps(user_dict(), ensure_ascii=False).encode()).hexdigest()[:8]


def query(text, sp):
    v = VOICE[sp]
    key = dict(t=text, s=v["speaker"], d=DICT_VER)
    q = json.loads(_cached("query", key, lambda: _post("/audio_query", params=dict(text=text, speaker=v["speaker"])).content))
    q["speedScale"] = v["speedScale"]
    q["intonationScale"] = v["intonationScale"]
    q["prePhonemeLength"] = _V["pre_phoneme"]
    q["postPhonemeLength"] = _V["post_phoneme"]
    revoice(q)
    sentence_pauses(q, text)
    return q


SENT_PAUSE = _V.get("sentence_pause")   # 台詞の途中の「。！？」のあとの間（読点より長く）。None なら何もしない


def sentence_pauses(q, text):
    """VOICEVOX は句点も読点もほぼ同じ長さで休む。文の切れ目（。！？）のあとだけ少し長くする"""
    if not SENT_PAUSE:
        return
    import re as _re
    puncts = _re.findall(r"[、。！？!?…]+", text)
    pm = [ap for ap in q["accent_phrases"] if ap.get("pause_mora")]
    if len(puncts) < len(pm):
        return
    for ap, p in zip(pm, puncts):
        if _re.search(r"[。！？!?]", p):
            ap["pause_mora"]["vowel_length"] = max(ap["pause_mora"]["vowel_length"], SENT_PAUSE)


REVOICE = set(_V.get("revoice") or [])  # 無声化すると別の音に聞こえる拍（「圧縮」の「シュ」がアッスクに聞こえる）


def revoice(q):
    """無声化された母音（大文字の U / I）を、REVOICE の拍だけ有声に戻す。高さは前の拍に合わせる"""
    prev = None
    for ap in q["accent_phrases"]:
        for m in ap["moras"]:
            if m["text"] in REVOICE and m["vowel"] in ("U", "I"):
                m["vowel"] = m["vowel"].lower()
                m["vowel_length"] = max(m["vowel_length"], 0.06)
                m["pitch"] = prev["pitch"] if prev and prev["pitch"] > 0 else 5.6
            prev = m


def synth(q, sp):
    v = VOICE[sp]
    return _cached("wav", dict(q=q, d=DICT_VER), lambda: _post(
        "/synthesis", params=dict(speaker=v["speaker"]), json=q).content)


def moras(q):
    """[(kana, vowel, consonant_start, vowel_start, end)] 秒。pause は vowel='pau'"""
    s = q["speedScale"]
    t = q["prePhonemeLength"] / s
    out = []
    for ap in q["accent_phrases"]:
        for m in ap["moras"]:
            c = (m.get("consonant_length") or 0) / s
            v = m["vowel_length"] / s
            out.append((m["text"], m["vowel"], t, t + c, t + c + v))
            t += c + v
        if ap.get("pause_mora"):
            pm = ap["pause_mora"]
            out.append(("、", "pau", t, t, t + pm["vowel_length"] / s))
            t += pm["vowel_length"] / s
    return out, t + q["postPhonemeLength"] / s


def kana(q):
    return "/".join("".join(m["text"] for m in ap["moras"]) + ("、" if ap.get("pause_mora") else "")
                    for ap in q["accent_phrases"])


def n_moras(text, sp):
    if not text.strip():
        return 0
    return sum(len(ap["moras"]) for ap in query(text, sp)["accent_phrases"])


def wav_array(data):
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == SR
        return np.frombuffer(w.readframes(w.getnframes()), np.int16)


_G = _V["gaps"]
GAP_SAME, GAP_SWITCH, GAP_ANSWER, HEAD, TAIL = _G["same"], _G["switch"], _G["answer"], _G["head"], _G["tail"]


def build_scene(scene):
    """シーンの音声と時刻表を作り build/voice/<id>.{wav,json} に保存"""
    from .subtitle import pages_for  # 循環を避ける
    out = BUILD / "voice"
    out.mkdir(parents=True, exist_ok=True)
    t = HEAD
    audio = [np.zeros(int(HEAD * SR), np.int16)]
    lines = []
    prev = None
    for ln in scene.lines:
        if prev is not None:
            if prev.speaker == ln.speaker:
                gap = GAP_SAME
            else:
                gap = GAP_ANSWER if prev.subtitle.rstrip("…").endswith(("？", "?")) else GAP_SWITCH
            gap += prev.pause
            audio.append(np.zeros(int(round(gap * SR)), np.int16)); t += gap
        q = query(ln.speech, ln.speaker)
        mo, dur = moras(q)
        data = wav_array(synth(q, ln.speaker))
        real = [m for m in mo if m[1] != "pau"]

        def at_prefix(speech_prefix):
            k = n_moras(speech_prefix, ln.speaker)
            if k >= len(real):
                return t + real[-1][4]
            return t + real[k][2]

        cues = {name: round(at_prefix(sp_pre), 3) for name, _, sp_pre in ln.segments()}
        pages = [dict(text=txt, t=round(at_prefix(sp_pre) if sp_pre else t, 3))
                 for txt, sp_pre in pages_for(ln)]
        start, end = t, t + len(data) / SR
        lines.append(dict(id=ln.id, speaker=ln.speaker, expr=ln.expr, text=ln.subtitle, kana=kana(q),
                          start=round(start, 3), end=round(end, 3), voice_end=round(t + real[-1][4], 3),
                          cues=cues, pages=pages,
                          moras=[(m[1], round(t + m[2], 3), round(t + m[3], 3), round(t + m[4], 3)) for m in mo]))
        audio.append(data); t = end
        prev = ln
        lines[-1]["calc_dur_err"] = round(dur - len(data) / SR, 3)
    tail = TAIL + (prev.pause if prev else 0)  # 最後の台詞の間も尺に入れる
    audio.append(np.zeros(int(tail * SR), np.int16)); t += tail
    pcm = np.concatenate(audio)
    with wave.open(str(out / f"{scene.id}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    tl = dict(scene=scene.id, title=scene.title, duration=round(len(pcm) / SR, 3), lines=lines)
    (out / f"{scene.id}.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    return tl


def main(sids=None):
    setup_dict()
    sc = load()
    for sid in (sids or sc):
        tl = build_scene(sc[sid])
        print(sid, tl["duration"], "s", max(abs(l["calc_dur_err"]) for l in tl["lines"]))


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
