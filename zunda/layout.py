"""画面の領域（px, 左上原点, 1920×1080）。立ち絵・字幕・図の取り合いはここだけで決める。"""
W, H = 1920, 1080
FPS = 30

from .paths import config

# 立ち絵：canvas をこの倍率・左上位置で置く（config/characters.yaml）
_SP = config("characters")["speakers"]
CHAR = {k: dict(name=v["name"], **v["placement"]) for k, v in _SP.items()}
COLOR = {k: tuple(v["color"]) for k, v in _SP.items()}

# 字幕の帯
SUB_BOX = (430, 925, 1490, 1068)  # x0, y0, x1, y1
SUB_FONT = "assets/fonts/MPLUSRounded1c-ExtraBold.ttf"   # リポジトリからの相対パス
SUB_SIZE = 50
SUB_MAX_W = SUB_BOX[2] - SUB_BOX[0] - 40

# 図を置いてよい領域（この外に出たら check.py が指摘する）。立ち絵の頭の上は全幅、間は字幕の上まで。
MARGIN = 28
SAFE_TOP = (MARGIN, MARGIN, W - MARGIN, 455)
SAFE_MID = (440, MARGIN, 1480, 905)
