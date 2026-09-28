"""SNS でシェアしたときのカード画像（1200x630）を og.png に書き出す。

使い方: python tools/make_og.py
ビンの絵は make_icons.py と同じ描き方。文字は同梱フォント（fonts/src、SIL OFL 1.1）で描く。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import make_icons

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "og.png"
FONT = ROOT / "fonts" / "src"

W, H = 1200, 630
SS = 2                     # 2 倍で描いてから縮小してなめらかにする
BG = "#FFF4F8"
DOT = "#FFD9E7"
CARD = "#FFFFFF"
INK = "#4B2A48"
SOFT = "#8C6A86"
PINK = "#FF6FA5"
LEMON = "#FFE27A"
LEMON_SOFT = "#FFF7D1"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT / name), size * SS)


def s(*v: float) -> tuple:
    return tuple(int(x * SS) for x in v)


def draw() -> Image.Image:
    img = Image.new("RGB", s(W, H), BG)
    d = ImageDraw.Draw(img)
    # 水玉
    for y in range(0, H + 22, 22):
        for x in range(0, W + 22, 22):
            d.ellipse(s(x - 2.2, y - 2.2, x + 2.2, y + 2.2), fill=DOT)

    # カード（アプリのパネルと同じく、ずらした影つき）
    card = (48, 44, W - 56, H - 52)
    d.rounded_rectangle(s(card[0] + 10, card[1] + 10, card[2] + 10, card[3] + 10), radius=40 * SS, fill=PINK)
    d.rounded_rectangle(s(*card), radius=40 * SS, fill=CARD, outline=INK, width=5 * SS)

    # ビン（アイコンと同じ絵。背景色だけカードに合わせて切り抜く）
    make_icons.BG = CARD
    jar = make_icons.draw_icon().resize(s(400, 400), Image.LANCZOS)
    # ビンのまわりだけを切り出して貼る
    full = Image.new("L", jar.size, 0)
    ImageDraw.Draw(full).rounded_rectangle(s(55, 30, 345, 350), radius=30 * SS, fill=255)
    img.paste(jar, s(78, 120), full)

    d = ImageDraw.Draw(img)
    x = 470
    # タイトル（アプリのロゴと同じく、レモン色の影）
    title = font("MochiyPopOne-Regular.ttf", 92)
    d.text(s(x + 6, 116), "つもり貯金", font=title, fill=LEMON)
    d.text(s(x, 110), "つもり貯金", font=title, fill=PINK)
    # タグライン
    d.text(s(x, 250), "ガマンした分だけ、", font=font("ZenMaruGothic-Bold.ttf", 44), fill=INK)
    d.text(s(x, 306), "未来の推し活へ。", font=font("ZenMaruGothic-Bold.ttf", 44), fill=INK)
    # 説明
    body = font("ZenMaruGothic-Medium.ttf", 25)
    d.text(s(x, 380), "ライブの落選、遠征やめた、グッズ我慢…", font=body, fill=SOFT)
    d.text(s(x, 416), "使うはずだったお金を「貯まったつもり」で記録", font=body, fill=SOFT)

    # 特徴のバッジ
    chip = font("ZenMaruGothic-Bold.ttf", 22)
    cx = x
    for label in ["記録は端末の中だけ", "無料・広告なし", "オフラインOK"]:
        w = d.textlength(label, font=chip) / SS
        d.rounded_rectangle(s(cx, 478, cx + w + 36, 522), radius=22 * SS, fill=LEMON_SOFT, outline=INK, width=3 * SS)
        d.text(s(cx + 18, 486), label, font=chip, fill=INK)
        cx += w + 36 + 12

    # URL
    d.text(s(92, 520), "oshi-tsumori.pages.dev", font=font("ZenMaruGothic-Bold.ttf", 22), fill=SOFT)
    return img.resize((W, H), Image.LANCZOS)


def main() -> None:
    draw().save(OUT, optimize=True)
    print("wrote", OUT, f"{OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
