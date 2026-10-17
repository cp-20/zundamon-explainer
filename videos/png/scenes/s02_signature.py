import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[3]), str(Path(__file__).resolve().parents[1])]  # リポジトリと動画のフォルダ

from vlib.data import file_bytes, fmt  # noqa: E402
from zunda.fx import Shake, pop, retext, underline  # noqa: E402
from zunda.scene import *  # noqa: E402,F403

# ---- S02 と S03 で共有するダンプの配置（S02 の最後の画面 = S03 の最初の画面）----
RAW = file_bytes("zundamon")[:64]
SIG = b"\x89PNG\r\n\x1a\n"
assert RAW[:8] == SIG
DSIZE = 40


def bx(i):
    return 960 + (i % 16 - 7.5) * 64


def by(i):
    return 75 + 62 * (i // 16)


def hx(v):
    return f"{v:02X}"


def byte_mob(txt, x, y, size=DSIZE, color=INK):
    return mono(txt, size, color).move_to(px(x, y))


def dump_final():
    """ダンプの最終形：先頭8バイト（シグネチャ）だけ明るい"""
    return [byte_mob(hx(RAW[i]), bx(i), by(i), DSIZE, INK if i < 8 else DIM) for i in range(64)]


def morph(old, new):
    """同じオブジェクトのまま new の形・位置・色へ（検査用の text も更新）"""
    old.text = getattr(new, "text", None)
    return Transform(old, new)


LIFT_Y = 600


def LX(i):
    return 960 + (i - 3.5) * 110


class S02(PScene):
    def construct(self):
        # ---- S01 の最後の画面：タイトルだけ ----
        title = jp("PNGの中身をのぞく", 72).move_to(px(960, 300))
        title.check_ignore = True  # S01 から引き継ぐ画面（S01 側では十分長く出ている）
        self.add(title)

        # ---- S02_01：タイトルが消え、バイト列が流れ込む ----
        self.at("s02_01", 0.0)
        self.play(FadeOut(title, shift=UP * u(70)), run_time=0.9)
        B = [byte_mob(hx(RAW[i]), bx(i), by(i)) for i in range(64)]
        self.at("bytes", -0.4)
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT * u(150)) for b in B], lag_ratio=0.02), run_time=1.8)

        # Z「暗号みたい」：ダンプ全体がびくっと揺れる
        self.at("S02_02", 0.3)
        self.play(Shake(VGroup(*B), 5, run_time=0.6))

        # ---- S02_02：1バイト = 0〜255、16進数は2桁 ----
        self.at("s02_02", 0.1)
        note = mix("1バイト ＝ 0〜255", 56).move_to(px(960, 470))
        self.play(FadeIn(note, shift=DOWN * u(10)), run_time=0.6)
        self.at("hex")
        self.play(retext(note, mix("16進数：2桁で 00〜FF", 56, YELLOW)), run_time=0.8)

        # ---- S02_03：A〜F が混ざっているバイトを黄色に ----
        self.at("alpha")
        letters = [i for i in range(64) if any(c in "ABCDEF" for c in hx(RAW[i]))]
        self.play(LaggedStart(*[B[i].animate.set_color(YELLOW) for i in letters], lag_ratio=0.03), run_time=1.3)

        # ---- S02_04：A〜F = 10〜15 ----
        self.at("s02_04", 0.1)
        table = jp("A=10  B=11  C=12  D=13  E=14  F=15", 48, INK, t2c={c: YELLOW for c in "ABCDEF"})
        self.play(retext(note, table), run_time=0.9)

        # ---- S02_05：4E = 4×16 + 14 = 78 ----
        self.at("s02_05", 0.0)
        i4e = RAW.index(0x4E)
        assert i4e == 2 and 4 * 16 + 14 == 0x4E == 78
        first = jp("4E", 72, YELLOW)
        rest = [jp("=", 72), jp("4×16", 72), jp("+", 72), jp("14", 72, YELLOW), jp("=", 72), jp("78", 72)]
        eq = VGroup(first, *rest).arrange(RIGHT, buff=u(28)).move_to(px(960, 690))
        self.at("ex", -0.5)
        self.play(pop(B[i4e], 1.5), run_time=0.5)
        cp = B[i4e].copy()
        self.add(cp)
        self.play(cp.animate(path_arc=-PI / 4).become(first), run_time=0.8)
        self.play(FadeIn(VGroup(rest[0], rest[1]), shift=LEFT * u(10)), run_time=0.6)
        self.play(FadeIn(VGroup(rest[2], rest[3]), shift=LEFT * u(10)), run_time=0.6)
        self.play(FadeIn(VGroup(rest[4], rest[5]), shift=LEFT * u(10)), run_time=0.5)
        self.play(pop(rest[5], 1.35), run_time=0.5)
        # Z「16のまとまりが4つと、14」：4×16 → 14 の順に拡大
        self.at("S02_07", 0.4)
        self.play(pop(rest[1], 1.25), run_time=0.7)
        self.at("S02_07", 2.2)
        self.play(pop(rest[3], 1.25), run_time=0.7)

        # ---- S02_06：先頭8バイト = シグネチャ ----
        self.at("s02_06", 0.2)
        self.play(FadeOut(VGroup(note, eq, cp)), run_time=0.6)
        self.at("sig")
        self.play(*[Transform(B[i], byte_mob(hx(RAW[i]), LX(i), LIFT_Y, 72, INK)) for i in range(8)],
                  *[B[i].animate.set_color(DIM) for i in range(8, 64)], run_time=1.1)
        self.at("signame")
        sig_lbl = mix("PNG シグネチャ", 56, YELLOW).move_to(px(960, 490))
        self.play(FadeIn(sig_lbl, shift=DOWN * u(10)), run_time=0.6)

        # Z「何のためにあるのだ？」：持ち上がった8バイトが拡大
        self.at("S02_09", 0.3)
        self.play(*[pop(B[i], 1.2) for i in range(8)], run_time=0.7)

        # ---- S02_07：50 4E 47 → P N G ----
        self.at("png")
        letters_png = "PNG"
        assert bytes(RAW[1:4]) == b"PNG"
        self.play(*[morph(B[i + 1], byte_mob(ch, LX(i + 1), LIFT_Y, 88, INK)) for i, ch in enumerate(letters_png)],
                  run_time=0.9)
        self.at("s02_08", 0.1)
        self.play(*[pop(B[i], 1.3) for i in (1, 2, 3)], run_time=0.7)

        # ---- S02_09：残りの5バイト ----
        # Z「残りの5つは何なのだ？」：その5バイトが拡大
        self.at("S02_12", 0.9)
        self.play(*[pop(B[i], 1.3) for i in (0, 4, 5, 6, 7)], run_time=0.7)
        self.at("trap")
        rest5 = (0, 4, 5, 6, 7)
        self.play(*[B[i].animate.set_color(YELLOW) for i in rest5], *[B[i].animate.set_color(DIM) for i in (1, 2, 3)],
                  run_time=0.6)

        # ---- S02_10：0D 0A は Windows、0A は Mac の改行 ----
        self.at("crlf")
        ul_y = LIFT_Y + 62
        ul1 = Line(px(LX(4) - 46, ul_y), px(LX(5) + 46, ul_y), color=BLUE, stroke_width=5)
        lb1 = mix("Windows の改行", 34, BLUE).move_to(px((LX(4) + LX(5)) / 2, ul_y + 52))
        self.play(Create(ul1), FadeIn(lb1, shift=DOWN * u(8)), run_time=0.7)
        self.at("lf")
        ul2 = Line(px(LX(7) - 46, ul_y), px(LX(7) + 46, ul_y), color=PURPLE, stroke_width=5)
        lb2 = mix("Mac などの改行", 34, PURPLE).move_to(px(LX(7) - 60, ul_y + 112))
        conn = Line(px(LX(7), ul_y + 6), px(LX(7), ul_y + 88), color=PURPLE, stroke_width=3)
        self.play(Create(ul2), Create(conn), FadeIn(lb2, shift=DOWN * u(8)), run_time=0.7)

        # Z「改行？」：0D 0A と注記が拡大
        self.at("S02_15", 0.2)
        self.play(pop(VGroup(B[4], B[5]), 1.2), pop(lb1, 1.12), run_time=0.7)

        # ---- S02_11：改行変換で 0D が抜ける ----
        self.at("s02_11", 0.0)
        ghost = VGroup(*[byte_mob(hx(SIG[i]), LX(i), 745, 44, DIM) for i in range(8)])
        ghost_lbl = jp("本来のシグネチャ", 30, DIM).move_to(px(960, 810))
        self.play(FadeOut(VGroup(ul1, lb1, ul2, lb2, conn)), run_time=0.5)
        self.play(FadeIn(ghost, shift=UP * u(10)), FadeIn(ghost_lbl), run_time=0.6)
        self.at("broken")
        self.play(B[4].animate.set_color(CORAL).shift(UP * u(50)).set_opacity(0),
                  *[B[i].animate.set_color(CORAL).shift(LEFT * u(110)) for i in (5, 6, 7)], run_time=0.7)
        self.play(Shake(VGroup(B[5], B[6], B[7]), 12), run_time=0.7)

        # Z「1バイト抜けただけで、ずれる」：ずれたバイトがもう一度揺れる
        self.at("S02_17", 0.7)
        self.play(Shake(VGroup(B[5], B[6], B[7]), 10), run_time=0.6)

        # ---- S02_12：Z「ずれて合わなくなる」→ S02_13：元に戻る ----
        self.at("s02_13", -0.6)
        self.play(B[4].animate.set_color(YELLOW).shift(DOWN * u(50)).set_opacity(1),
                  *[B[i].animate.set_color(YELLOW).shift(RIGHT * u(110)) for i in (5, 6, 7)],
                  FadeOut(ghost), FadeOut(ghost_lbl), run_time=0.7)
        self.at("high")
        assert SIG[0] == 0x89 and 0x89 == 137 and 0x89 & 0x7F == 0x09
        l137 = jp("137 ≥ 128", 38, YELLOW).move_to(px(LX(0), LIFT_Y + 100))
        self.play(pop(B[0], 1.3), FadeIn(l137, shift=UP * u(8)), run_time=0.7)
        self.at("t89")
        l09 = jp("一番上のビットが落ちる", 30, CORAL).move_to(px(LX(0) + 50, LIFT_Y + 160))
        self.play(morph(B[0], byte_mob("09", LX(0), LIFT_Y, 72, CORAL)), FadeIn(l09, shift=UP * u(8)), run_time=0.5)
        self.play(Shake(B[0], 12), run_time=0.6)
        # Z「1Aは何なのだ？」：89 は元に戻り、1A が拡大
        self.at("S02_20", 0.1)
        self.play(morph(B[0], byte_mob("89", LX(0), LIFT_Y, 72, YELLOW)), FadeOut(VGroup(l137, l09)),
                  pop(B[6], 1.4), run_time=0.8)
        self.at("t1a")
        l1a = jp("ここで終わり", 38, YELLOW).move_to(px(LX(6), LIFT_Y + 100))
        self.play(FadeIn(l1a, shift=UP * u(8)), run_time=0.6)

        # ---- S02_14：ダンプに戻る（S03 の最初の画面）----
        self.at("ok")
        final = dump_final()
        self.play(*[Transform(B[i], final[i]) for i in range(64)], FadeOut(VGroup(sig_lbl, l1a)), run_time=1.2)
        self.finish()
