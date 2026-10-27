import re
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.ui import CARD_ROWS, compare_card  # noqa: E402
from zunda.fx import pop  # noqa: E402
from zunda.paths import config as yaml_config, video_config  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

CARD_C = (960, 340)
EQ_Y = 735
ROW_DIM = 0.55
# 台詞のキュー → 光る行 (比較表の行の番号)
LIGHT = [("t2", 0.0, 0), ("t3", 0.0, 1), ("t3b", 0.0, 2), ("t4", 0.0, 3), ("t5", 0.0, 4), ("t6", 0.0, 5),
         ("t7", 0.0, 6)]


def credit_lines():
    """config/assets.yaml の credits ＋ video.yaml の extra_credits を、画面用に
    (URL と括弧のライセンス名を外し、「、」と「 / 」で行を分ける。HEIC 編のクレジットと同じ形)"""
    out = []
    for cat, vals in [tuple(c) for c in yaml_config("assets")["credits"]] + [tuple(c) for c in video_config()["extra_credits"]]:
        lines = []
        for v in vals:
            v = re.sub(r"\s*https?://\S+", "", v)
            v = re.sub(r"（[^）]*）", "", v)
            lines += [s.strip() for s in re.split(r"、| / ", v) if s.strip()]
        out.append((cat, lines))
    return out


class S12(PScene):
    def construct(self):
        assert len(CARD_ROWS) == 7 and sorted(k for _, _, k in LIGHT) == list(range(7))
        credits = credit_lines()
        assert credits[0] == ("音声", ["VOICEVOX:ずんだもん", "VOICEVOX:四国めたん"])
        assert ("音楽", ["甘茶の音楽工房"]) in credits
        assert ("フォント", ["Zen Maru Gothic", "M PLUS Rounded 1c", "JetBrains Mono"]) in credits
        assert credits[-1][0] == "写真" and len(credits[-1][1]) == 2

        # ================= 比較表 7 行 =================
        card = compare_card(7, center=CARD_C)
        for r in card.rows:
            r[1].set_opacity(ROW_DIM)
        self.at("s12_01", -0.1)
        self.play(FadeIn(card, shift=UP * u(30)), run_time=1.0)

        # ---- HEIF の箱 ＋ AV1 ＝ AVIF ----
        e1, e2, e3, e4, e5 = (mix("HEIFの箱", 52, BLUE), mix("＋", 52, DIM), mix("AV1", 52, CYAN),
                              mix("＝", 52, DIM), mix("AVIF", 56, YELLOW))
        eq = VGroup(e1, e2, e3, e4, e5).arrange(RIGHT, buff=u(26)).move_to(px(960, EQ_Y))
        self.at("t1", -0.1)
        self.play(LaggedStart(*[FadeIn(e, shift=RIGHT * u(12)) for e in eq], lag_ratio=0.3), run_time=1.6)

        # ---- 台詞に合わせて AVIF の列が上から光る ----
        for cue, off, k in LIGHT:
            self.at(cue, off - 0.1)
            r = card.rows[k][1]
            r.generate_target()
            r.target.set_opacity(1)
            r.target[2].set_color(YELLOW)
            self.play(MoveToTarget(r), run_time=0.5)
            self.play(pop(r[2], 1.12, 0.6), run_time=0.6)

        # ---- 別の工夫で、同じくらい小さく ----
        self.at("s12_06", -0.1)
        col = VGroup(card.head[1], *[r[1][2] for r in card.rows])
        self.play(pop(col, 1.06, 0.8), run_time=0.8)
        self.at("s12_06", 2.4)
        self.play(pop(eq[4], 1.15, 0.7), run_time=0.7)

        # ---- 図が消えて、クレジット ----
        self.at("S12_07.end", 0.3)
        self.play(FadeOut(VGroup(card, eq)), run_time=1.4)
        title = jp("クレジット", 44, INK).move_to(px(960, 70))
        cred = VGroup(title)
        y = 150
        for cat_, vals in credits:
            cred.add(jp(cat_, 34, DIM).move_to(px(470, y), aligned_edge=LEFT))
            for v_ in vals:
                cred.add(mix(v_, 34, INK).move_to(px(710, y), aligned_edge=LEFT))
                y += 52
            y += 16
        assert y < 880
        self.at("S12_07.end", 1.9)
        self.play(FadeIn(cred, shift=UP * u(10)), run_time=1.0)

        # ---- 「ありがとう」「またね」のあと、ゆっくり消える ----
        self.at("S12_09.end", 0.8)
        self.play(FadeOut(cred), run_time=self.until(self.tl["duration"], -0.3))
        self.finish()
