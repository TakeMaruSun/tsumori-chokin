"""つもり貯金の公開用ファイルを dist/ に書き出す。

使い方:  python tools/build.py

出力
  dist/web/            … スマホ向け（Web に置く版）。オフライン対応・ホーム画面に追加できる
  dist/つもり貯金.html  … PC 向けの単体版。フォントも中に入った 1 ファイルで、ダブルクリックで開ける
  fonts/*.woff2        … 編集用 index.html がそのまま動くための絞り込み済みフォント

やっていること
  1. フォントを必要な文字だけに絞る（見出し用は画面の文字だけ、本文用は第1水準漢字＋かな）
  2. CSP（Content-Security-Policy）を付ける。外部への通信・外部スクリプトの読み込みをすべて禁止し、
     このファイルに書かれたスクリプトとスタイルだけを、中身のハッシュで許可する
     → index.html を編集したら、必ずこのビルドをやり直すこと（ハッシュが変わるため）
  3. オフライン用の Service Worker（tools/sw.js をそのままコピー）と、版番号・ファイル一覧の version.json を置く
     更新は利用者が「せってい → 更新を確認する」を押したときだけ行う
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "index.html"
FONT_SRC = ROOT / "fonts" / "src"
FONT_OUT = ROOT / "fonts"
DIST = ROOT / "dist"
WEB = DIST / "web"
STANDALONE = DIST / "つもり貯金.html"
CHANGES = ROOT / "CHANGES.json"

FONTS = {
    # 出力名: (元ファイル, 絞り込み方)
    "MochiyPopOne.woff2": ("MochiyPopOne-Regular.ttf", "ui"),
    "ZenMaruGothic-Medium.woff2": ("ZenMaruGothic-Medium.ttf", "text"),
    "ZenMaruGothic-Bold.woff2": ("ZenMaruGothic-Bold.ttf", "text"),
}


# ---------------------------------------------------------------------------
# フォント
# ---------------------------------------------------------------------------
def jis_level1() -> set[str]:
    """JIS X 0208 の記号・英数・かな（1〜8区）と第1水準漢字（16〜47区）。"""
    chars = set()
    for row in list(range(1, 9)) + list(range(16, 48)):
        for col in range(1, 95):
            try:
                chars.add(bytes([row + 0xA0, col + 0xA0]).decode("euc_jp"))
            except UnicodeDecodeError:
                pass
    return chars


def charset(html: str, kind: str) -> str:
    base = set(chr(c) for c in range(0x20, 0x7F)) | set(html) | set("０１２３４５６７８９円万年月日")
    if kind == "text":
        base |= jis_level1()
        base |= set(chr(c) for c in range(0xFF01, 0xFF5F))  # 全角英数記号
        base |= set(chr(c) for c in range(0xFF61, 0xFFA0))  # 半角カナ
        base |= set("♡♥☆★♪〜～・…‥「」『』【】！？")
    return "".join(sorted(c for c in base if c.isprintable()))


def build_fonts(html: str) -> dict[str, bytes]:
    out = {}
    for name, (src, kind) in FONTS.items():
        opt = subset.Options()
        opt.flavor = "woff2"
        opt.layout_features = ["kern", "palt", "liga"]
        opt.name_IDs = ["*"]          # 著作権・ライセンス情報をフォントの中に残す（OFL の条件）
        opt.name_languages = ["*"]
        opt.notdef_outline = True
        opt.hinting = False
        # 作成日時を書き換えない（中身が同じなら同じファイルになり、版番号も変わらない）
        font = TTFont(FONT_SRC / src, recalcTimestamp=False)
        s = subset.Subsetter(opt)
        s.populate(text=charset(html, kind))
        s.subset(font)
        buf = io.BytesIO()
        font.save(buf)
        out[name] = buf.getvalue()
        print(f"  font {name}: {len(out[name]) / 1024:.0f} KB")
    return out


# ---------------------------------------------------------------------------
# CSP
# ---------------------------------------------------------------------------
def sha256(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


def inline_hashes(html: str, tag: str) -> list[str]:
    return [sha256(m) for m in re.findall(rf"<{tag}>(.*?)</{tag}>", html, flags=re.S)]


def add_csp(html: str, extra: dict[str, str]) -> str:
    directives = {
        "default-src": "'none'",
        "script-src": " ".join(inline_hashes(html, "script")),
        "style-src": " ".join(inline_hashes(html, "style")),
        "base-uri": "'none'",
        "form-action": "'none'",
        "object-src": "'none'",
        **extra,
    }
    csp = "; ".join(f"{k} {v}" for k, v in directives.items())
    meta = f'<meta http-equiv="Content-Security-Policy" content="{csp}">'
    return html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + meta, 1)


def check_no_inline_style_attr(html: str) -> None:
    """CSP（style-src はハッシュ指定）では、HTML に直書きした style="…" はブロックされる。"""
    body = re.sub(r"<!--.*?-->|<script>.*?</script>", "", html, flags=re.S)
    bad = re.findall(r"<[^>]*\sstyle\s*=", body)
    if bad:
        sys.exit(f"HTML に style 属性が直書きされています（公開版で効かなくなる）: {bad[:3]}")


def check_no_external(html: str, label: str) -> None:
    """外部 URL を読み込む記述が残っていないか確かめる（コメントとライセンス表記の URL は対象外）。"""
    body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    bad = re.findall(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", body) + re.findall(r"url\(\s*[\"']?\s*(?:https?:)?//", body)
    bad += re.findall(r"\bimport\s*\(|\bfetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|EventSource", body)
    if bad:
        sys.exit(f"[{label}] 外部に通信しうる記述があります: {bad}")


def load_changes() -> tuple[int, list[dict]]:
    """CHANGES.json（更新内容の一覧）を読む。「更新を確認する」を押したときに、今の版より新しい分だけ画面に出す。"""
    notes = []
    for n in json.loads(CHANGES.read_text(encoding="utf-8")):
        rev, date, lines = n.get("rev"), n.get("date"), n.get("items")
        if not (isinstance(rev, int) and rev > 0 and isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
                and isinstance(lines, list) and 0 < len(lines) <= 20 and all(isinstance(x, str) and 0 < len(x) <= 100 for x in lines)):
            sys.exit(f"CHANGES.json の書き方が正しくありません: {n}")
        notes.append({"rev": rev, "date": date, "items": lines})
    if len({n["rev"] for n in notes}) != len(notes):
        sys.exit("CHANGES.json に同じ rev が重複しています")
    notes.sort(key=lambda n: n["rev"], reverse=True)
    return (notes[0]["rev"] if notes else 0), notes[:10]


def assert_single(html: str, pattern: str, label: str) -> None:
    n = len(re.findall(pattern, html))
    if n != 1:
        sys.exit(f"ビルドの前提が崩れています（{label} が {n} 個）。tools/build.py を見直してください")


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------
def main() -> None:
    html = SRC.read_text(encoding="utf-8")
    assert_single(html, r"const OFFLINE = false;", "OFFLINE の定義")
    assert_single(html, r'<meta charset="utf-8">', "charset")
    check_no_external(html, "index.html")
    check_no_inline_style_attr(html)

    print("フォントを絞り込み中…")
    fonts = build_fonts(html)
    for name, data in fonts.items():
        (FONT_OUT / name).write_bytes(data)

    # dist/ はフォルダごと消さずに中身だけ消す（エクスプローラー等で開いていても失敗しないように）
    if DIST.exists():
        for p in DIST.iterdir():
            if p == WEB:
                for q in WEB.iterdir():
                    shutil.rmtree(q) if q.is_dir() else q.unlink()
            else:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    (WEB / "fonts").mkdir(parents=True, exist_ok=True)
    (WEB / "icons").mkdir(exist_ok=True)

    # ---------- スマホ向け（Web に置く版） ----------
    web = html.replace("const OFFLINE = false;", "const OFFLINE = true;")
    web = add_csp(web, {
        "font-src": "'self'",
        "img-src": "'self' data:",
        "manifest-src": "'self'",
        "worker-src": "'self'",
    })
    (WEB / "index.html").write_text(web, encoding="utf-8", newline="\n")
    for name, data in fonts.items():
        (WEB / "fonts" / name).write_bytes(data)
    for lic in FONT_OUT.glob("OFL-*.txt"):
        shutil.copy(lic, WEB / "fonts" / lic.name)
    shutil.copy(ROOT / "LICENSE", WEB / "LICENSE.txt")
    for icon in (ROOT / "icons").glob("*.png"):
        shutil.copy(icon, WEB / "icons" / icon.name)
    shutil.copy(ROOT / "manifest.webmanifest", WEB / "manifest.webmanifest")
    # 検索エンジンに載せない（家族など URL を知っている人だけで使う想定）
    (WEB / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")

    assets = ["./", "index.html", "manifest.webmanifest"]
    assets += [f"fonts/{n}" for n in sorted(fonts)]
    assets += [f"icons/{p.name}" for p in sorted((WEB / "icons").glob("*.png"))]
    h = hashlib.sha256()
    for a in assets[1:]:
        h.update((WEB / a).read_bytes())
    version = h.hexdigest()[:12]
    # sw.js は版に関係なく同じ中身にする（変わるとブラウザが自動で更新を始めるため）。
    # 版とファイル一覧は version.json に書き、更新はアプリの「更新を確認する」ボタンからだけ行う
    shutil.copy(ROOT / "tools" / "sw.js", WEB / "sw.js")
    rev, notes = load_changes()
    (WEB / "version.json").write_text(json.dumps({"version": version, "rev": rev, "notes": notes, "assets": assets}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    # ヘッダーを設定できる公開先（Cloudflare Pages・Netlify）向け：sw.js は毎回「変更がないか」を確かめる
    # （直した sw.js が、次に開いたときに届くように）。中身が同じなら「変更なし」の返事だけ
    (WEB / "_headers").write_text(
        "/sw.js\n  Cache-Control: no-cache\n/version.json\n  Cache-Control: no-store\n",
        encoding="utf-8", newline="\n")
    check_no_external(web, "web")

    # ---------- PC 向けの単体版（1 ファイル） ----------
    one = html
    for name, data in fonts.items():
        uri = "data:font/woff2;base64," + base64.b64encode(data).decode()
        one = one.replace(f'url("fonts/{name}")', f'url("{uri}")')
    # 単体版ではホーム画面・オフライン用のファイルは使わない
    one = re.sub(r'\s*<link rel="(?:manifest|apple-touch-icon)"[^>]*>', "", one)
    one = one.replace("<!--\n  外部には一切つながりません。", "<!--\n  フォント: Mochiy Pop One (c) 2020 The Mochiypop Project Authors / Zen Maru Gothic (c) 2021 The Zen Maru Gothic Project Authors\n  いずれも SIL Open Font License 1.1。\n  外部には一切つながりません。", 1)
    # 1 ファイルだけを渡されても条件を満たすよう、ライセンスの全文を末尾のコメントに入れる
    # （アプリは MIT、同梱フォントは SIL OFL 1.1。どちらも配布時に著作権表示とライセンス文を付けることが条件）
    texts = [(ROOT / "LICENSE").read_text(encoding="utf-8")] + [p.read_text(encoding="utf-8") for p in sorted(FONT_OUT.glob("OFL-*.txt"))]
    licenses = "\n\n".join(t.replace("--", "- -").strip() for t in texts)   # コメントの中に -- は書けない
    one = one.replace("</html>", f"<!--\n{licenses}\n-->\n</html>", 1)
    one = add_csp(one, {"font-src": "data:", "img-src": "data:"})
    if 'url("fonts/' in one:
        sys.exit("単体版にフォントの外部参照が残っています")
    check_no_external(one, "standalone")
    STANDALONE.write_text(one, encoding="utf-8", newline="\n")

    size = sum(p.stat().st_size for p in WEB.rglob("*") if p.is_file())
    print(f"dist/web          : {size / 1024 / 1024:.1f} MB（版 {version}）")
    print(f"dist/つもり貯金.html: {STANDALONE.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
