"""ホーム画面用アイコン（貯金ビン）を icons/ に書き出す。

使い方: python tools/make_icons.py
外部の画像やフォントは使わず、Pillow の図形だけで描く。
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "icons"

BG = "#FFE3EE"
INK = "#4B2A48"
GLASS = "#FFFFFF"
MILK = "#FF7FAF"
LEMON = "#FFE27A"

S = 1024          # 大きく描いてから縮小してなめらかにする
LINE = 34


def draw_icon() -> Image.Image:
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)

    # ビンの首と胴
    neck = (380, 300, 644, 420)
    body = (282, 380, 742, 872)
    d.rounded_rectangle(body, radius=120, fill=GLASS, outline=INK, width=LINE)

    # 中身（胴の形で切り抜く）
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (body[0] + LINE // 2, body[1] + LINE // 2, body[2] - LINE // 2, body[3] - LINE // 2),
        radius=120 - LINE // 2, fill=255)
    liquid = Image.new("RGB", (S, S), GLASS)
    ld = ImageDraw.Draw(liquid)
    ld.rectangle((0, 610, S, S), fill=MILK)
    # 液面のゆるい波
    for i, x in enumerate(range(body[0] - 40, body[2] + 40, 110)):
        ld.ellipse((x, 575 + (i % 2) * 18, x + 130, 650), fill=MILK)
    img.paste(liquid, (0, 0), mask)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle(body, radius=120, outline=INK, width=LINE)
    # 首を胴の上に重ね、内側に入り込んだ線（首の底と胴の上辺）を消す
    d.rectangle(neck, fill=GLASS, outline=INK, width=LINE)
    d.rectangle((neck[0] + LINE, body[1] - LINE, neck[2] - LINE, neck[3] + LINE), fill=GLASS)

    # つや
    d.arc((320, 440, 500, 700), start=185, end=250, fill="#FFD0E2", width=28)

    # ハート
    hx, hy, r = 512, 735, 34
    d.ellipse((hx - 2 * r, hy - r, hx, hy + r), fill=GLASS)
    d.ellipse((hx, hy - r, hx + 2 * r, hy + r), fill=GLASS)
    d.polygon([(hx - 2 * r + 4, hy + 10), (hx + 2 * r - 4, hy + 10), (hx, hy + 2.3 * r)], fill=GLASS)

    # ふた
    d.rounded_rectangle((340, 190, 684, 318), radius=40, fill=LEMON, outline=INK, width=LINE)
    d.rounded_rectangle((452, 238, 572, 268), radius=15, fill=INK)
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    big = draw_icon()
    for name, size in [("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180)]:
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
