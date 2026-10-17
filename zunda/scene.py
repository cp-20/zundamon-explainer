"""Manim の基底クラス。台詞の時刻表に合わせて画面を進め、検査用のログを残す。

    class S05(PScene):
        def construct(self):
            self.at("row")              # キュー "row" の時刻まで待つ
            self.play(..., run_time=1)  # そこから動かす
            self.finish()               # シーンの最後まで待つ
"""
import json
from pathlib import Path

import numpy as np
from manim import *  # noqa

from .layout import FPS, H, W

from .paths import BUILD

import os

# PV_RES=540 で 960×540 の試し描画（時刻は同じ）
_res = int(os.environ.get("PV_RES", H))
# 時間の一部だけを描く（zunda/build.py が使う）。PV_FROM 以上 PV_TO 未満に「始まる」アニメーションだけを描き、
# それより前は描かずに状態だけ進め（Manim の skip）、PV_TO に達したら打ち切る。
# PV_CLIP=1 のときは「範囲に少しでもかかる」アニメーションを描く（部分の試写用）。
_FROM = float(os.environ.get("PV_FROM", "0") or 0)
_TO = float(os.environ.get("PV_TO", "inf") or "inf")
_CLIP = os.environ.get("PV_CLIP") == "1"
_WINDOW = _FROM > 0 or _TO != float("inf")
config.pixel_width, config.pixel_height, config.frame_rate = W * _res // H, _res, FPS

# 速さ：Manim の描画の重い所を差し替える（SVG のパスの共有、画像の部分だけの合成。zunda/fastcam.py）
from . import fastcam  # noqa: E402,F401

# 速さ：Manim の書き出し（あとで立ち絵と字幕を重ねて書き直す中間ファイル）は、GPU（NVENC）があればそれで書く
def _manim_encoder():
    import av
    from .compose import use_nvenc
    if "h264_nvenc" in av.codecs_available and use_nvenc():
        config.video_codec = "h264_nvenc"
        config.video_encoder_options = {"preset": "p1", "rc": "vbr", "cq": "16", "b": "0"}
    else:   # 中間のファイルなので速さ優先
        config.video_codec = "libx264"
        config.video_encoder_options = {"preset": "ultrafast", "crf": "14"}


from .paths import config as config_yaml  # noqa: E402
_manim_encoder()
config.background_color = "#14161c"


BG = "#14161c"
INK = "#eef0f4"
DIM = "#7d8494"
ZCOL, MCOL = "#7cc35a", "#e3609a"
CYAN, YELLOW, CORAL, PURPLE, BLUE = "#4fd1e8", "#f2c14e", "#ef6f5e", "#a58bf0", "#5aa7ea"
JP = "Zen Maru Gothic"
MONO = "JetBrains Mono"

UNIT = W / config.frame_width  # px per manim unit


def px(x, y):
    """画面 px（左上原点）→ manim 座標"""
    return np.array([x / UNIT - config.frame_width / 2, config.frame_height / 2 - y / UNIT, 0])


def u(p):
    """px の長さ → manim 単位"""
    return p / UNIT


EM = 1.875  # font_size 1 あたりの em（px）。実測：font_size=48 で em≈90px


def jp(s, size=40, color=INK, weight="BOLD", **kw):
    """日本語テキスト。size は em の px"""
    return Text(s, font=JP, font_size=size / EM, color=color, weight=weight, **kw)


def mono(s, size=40, color=INK, weight="BOLD", **kw):
    return Text(s, font=MONO, font_size=size / EM, color=color, weight=weight, **kw)


TEXT_TYPES = (Text, MarkupText, MathTex, Tex, DecimalNumber, Integer)


class PScene(Scene):
    SCENE_ID = None

    def setup(self):
        sid = self.SCENE_ID or type(self).__name__
        self.tl = json.loads((BUILD / "voice" / f"{sid}.json").read_text())
        self.cues = {}
        for ln in self.tl["lines"]:
            self.cues[ln["id"]] = ln["start"]
            self.cues[ln["id"] + ".end"] = ln["voice_end"]
            for k, v in ln["cues"].items():
                assert k not in self.cues, f"キュー名が重複: {k}"
                self.cues[k] = v
        self.log = dict(scene=sid, duration=self.tl["duration"], plays=[], states=[], se=[], late=[], waits=[])
        if _WINDOW:
            # 描かないアニメーション（skip）の間は、画面の計算もしない（Manim は skip 中も 1 コマ描いてしまう）
            r = self.renderer
            orig_update, orig_static = r.update_frame, r.save_static_frame_data

            def update_frame(*a, **k):
                if not r.skip_animations:
                    return orig_update(*a, **k)

            def save_static(scene, mobs):
                if not r.skip_animations:
                    return orig_static(scene, mobs)
                r.static_image = None

            r.update_frame, r.save_static_frame_data = update_frame, save_static
        self._seg_start = 0.0

    # ---- 時刻 ----
    @property
    def now(self):
        return self.renderer.time

    def cue(self, name):
        if name not in self.cues:
            raise KeyError(f"キューがない: {name}（{sorted(self.cues)}）")
        return self.cues[name]

    def at(self, name, offset=0.0):
        """キュー（または秒数）の時刻まで待つ。過ぎていたら遅れとして記録"""
        t = (self.cue(name) if isinstance(name, str) else name) + offset
        d = t - self.now
        if d > 1 / FPS:
            super().wait(d)
            self._snapshot("wait")
        elif d < -0.12:
            self.log["late"].append(dict(cue=name, by=round(-d, 3), t=round(self.now, 3)))

    def until(self, name, offset=0.0):
        """今からキューまでの秒数（アニメーションの長さに使う）"""
        t = (self.cue(name) if isinstance(name, str) else name) + offset
        return max(t - self.now, 1 / FPS)

    def se(self, name, offset=0.0, gain=0.0):
        self.log["se"].append(dict(name=name, t=round(self.now + offset, 3), gain=gain))

    # ---- 再生と記録 ----
    def _run_time(self, args, kw):
        if "run_time" in kw:
            return kw["run_time"]
        rts = [getattr(a, "run_time", 1.0) for a in args if isinstance(a, Animation)]
        return max(rts) if rts else 1.0

    def play(self, *args, **kw):
        t0 = self.now
        if _WINDOW:
            t1 = t0 + self._run_time(args, kw)
            if t0 >= _TO - 1e-6:
                self._window_end()
            # 下の端：PV_CLIP なら範囲にかかるもの、そうでなければ範囲内で始まるもの（分けて並べたときに重ならない）
            draw = (t1 > _FROM + 1e-6 if _CLIP else t0 >= _FROM - 1e-6) and t0 < _TO - 1e-6
            self.renderer._original_skipping_status = not draw
            if draw and not hasattr(self, "_win_start"):
                self._win_start = t0
        super().play(*args, **kw)
        self.log["plays"].append(dict(t0=round(t0, 3), t1=round(self.now, 3),
                                      anims=[type(a).__name__ for a in args if isinstance(a, Animation)]))
        self._snapshot("play")

    def wait(self, duration=1.0, **kw):
        super().wait(duration, **kw)
        self._snapshot("wait")

    def _window_end(self):
        """部分の描画の終わり：実際に描いた範囲を書き残して打ち切る"""
        from manim.utils.exceptions import EndSceneEarlyException
        self._write_window(self.now)
        raise EndSceneEarlyException()

    def _write_window(self, end):
        out = BUILD / "render"
        out.mkdir(parents=True, exist_ok=True)
        tag = os.environ.get("PV_TAG", "")
        start = getattr(self, "_win_start", end)
        (out / f"{self.log['scene']}{tag}.window.json").write_text(json.dumps(dict(start=start, end=end)))

    def finish(self):
        self.at(self.tl["duration"] - 1 / FPS)
        if _WINDOW:
            self._write_window(self.now)
        self.log["end"] = round(self.now, 3)
        out = BUILD / "log"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{self.log['scene']}.json").write_text(json.dumps(self.log, ensure_ascii=False))

    def _bbox(self, m):
        pts = m.get_all_points() if isinstance(m, VMobject) else m.points
        if len(pts) == 0:
            return None
        lo, hi = pts.min(0), pts.max(0)
        x0, y0 = (lo[0] + config.frame_width / 2) * UNIT, (config.frame_height / 2 - hi[1]) * UNIT
        x1, y1 = (hi[0] + config.frame_width / 2) * UNIT, (config.frame_height / 2 - lo[1]) * UNIT
        return [round(float(v), 1) for v in (x0, y0, x1, y1)]

    def _visible(self, m):
        if isinstance(m, ImageMobject):
            return True
        for sm in m.family_members_with_points():
            if (sm.get_fill_opacity() > 0.05) or (sm.get_stroke_opacity() > 0.05 and sm.get_stroke_width() > 0):
                return True
        return False

    def _items(self):
        items = []

        def walk(m, depth):
            if getattr(m, "check_ignore", False) or not self._visible(m):
                return
            if isinstance(m, TEXT_TYPES):
                txt = getattr(m, "text", None) or getattr(m, "tex_string", None) or (
                    str(m.get_value()) if hasattr(m, "get_value") else "")
                bb = self._bbox(m)
                if bb:
                    items.append(dict(id=id(m), kind="text", text=txt, bbox=bb))
                return
            if isinstance(m, ImageMobject):
                items.append(dict(id=id(m), kind="image", bbox=self._bbox(m)))
                return
            subs = m.submobjects
            leaves = len(m.family_members_with_points())
            if getattr(m, "check_group", False) or (subs and leaves > 150):
                bb = self._bbox(m)
                if bb:
                    items.append(dict(id=id(m), kind="group", bbox=bb))
                return
            if not subs:
                bb = self._bbox(m)
                if bb:
                    items.append(dict(id=id(m), kind="shape", bbox=bb, cls=type(m).__name__,
                                      stroke=float(m.get_stroke_width()) if m.get_stroke_opacity() > 0.05 else 0.0,
                                      fill=float(m.get_fill_opacity())))
                return
            for s in subs:
                walk(s, depth + 1)

        for m in self.mobjects:
            walk(m, 0)
        return items

    def _snapshot(self, kind):
        t0, t1 = self._seg_start, self.now
        self._seg_start = t1
        self.log["states"].append(dict(t0=round(t0, 3), t1=round(t1, 3), kind=kind, items=self._items()))


CHECKER = ((40, 44, 54), (52, 57, 69))  # 透明を表す市松模様（暗め）


def checker_composite(rgba, cell):
    """RGBA 配列を市松模様の上に合成した RGB 配列（透明な所が見えるように）"""
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    k = ((yy // cell + xx // cell) % 2).astype(bool)
    bg = np.where(k[..., None], np.array(CHECKER[1]), np.array(CHECKER[0])).astype(np.float32)
    if rgba.shape[2] == 3:
        return rgba
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3] * a + bg * (1 - a)).astype(np.uint8)


def png_mob(arr, height_px, cell_px=14, nearest=False):
    """画像（numpy RGBA/RGB）を、透明部分は市松模様にして高さ height_px で置く"""
    scale = height_px / arr.shape[0]
    rgb = checker_composite(arr, max(1, round(cell_px / scale)))
    m = ImageMobject(rgb)
    if nearest:
        m.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
    m.height = u(height_px)
    return m


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mix(s, size=40, color=INK, weight="BOLD", **_):
    """和文と数字・英字が混ざった1行。説明の文字は数字も和文と同じフォントで1つの文字列に組む。
    （等幅 mono() はバイト列・16進ダンプなど「並び」を見せる所だけに使う）"""
    return jp(s, size, color, weight)
