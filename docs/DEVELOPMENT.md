# 開発メモ（作る側向け）

使う人向けの説明は [README](../README.md)。ここはソースを直す・公開するときの手順と注意点。

## ファイル構成

| パス | 役割 |
|---|---|
| `index.html` | 編集用のソース（ここを直す）。HTML・CSS・JS がすべて入った 1 ファイル |
| `tools/build.py` | 公開用ファイルを `dist/` に書き出す |
| `tools/make_icons.py` | ホーム画面用アイコンを `icons/` に描く |
| `tools/make_og.py` | SNS でシェアしたときの紹介カード `og.png`（1200×630）を描く。公開版に同梱するが、オフライン用の保存対象には入れない |
| `tools/shoot_screens.mjs` | 紹介用のスクショ（見本の記録入り）を撮る。README 用は半分に縮めて `docs/images/`（X 投稿用の原寸は `promo/`。git には入れない） |
| `tools/sw.js` | オフライン用 Service Worker（版は `version.json` で管理） |
| `CHANGES.json` | 利用者に見せる更新内容の一覧 |
| `fonts/src/` | フォントの元データ（SIL OFL 1.1）。`fonts/*.woff2` はビルドが絞り込んで作る |
| `dist/web/` | **スマホ向けの公開版**（Web に置く。オフライン対応・ホーム画面に追加できる）。git には入れない |
| `dist/つもり貯金.html` | PC 向けの単体版（フォント込みの 1 ファイル。ダブルクリックで開く）。git には入れない |

## 直したら

```
python tools/build.py
```

`index.html` を編集したら必ずビルドし直す。公開版にはスクリプトとスタイルのハッシュを使った CSP が入るため、ビルドし直さないと公開版のスクリプトが動かなくなる。
ビルドは決定的で、中身が同じなら同じ版番号（`version.json` の `version`）になる。改行は `.gitattributes` で LF に固定している。

- HTML に `style="…"` を直書きしない（CSP でブロックされる。ビルドが検査して止まる）。JS から `el.style` で入れるのは可
- 外部 URL や通信用 API（`fetch` など）の記述があると、ビルドが止まる

## 更新内容を書く

公開する前に `CHANGES.json` の先頭に 1 件足す（`rev` は 1 ずつ増やす。`items` は利用者向けの短い文、1 件 100 文字・20 行まで）。
ビルドが `version.json` に載せ、利用者が「更新を確認する」を押したときに、今の版より新しい分だけ表示される。

## セキュリティの実装

- **通信しない**：外部のフォント・スクリプト・解析タグは使わない。CSP の `default-src 'none'` で、外部への通信と外部ファイルの読み込みをブラウザ側で禁止している（ページからの `fetch` も通らない）
- **記録は端末の中だけ**：localStorage（`tsumori-chokin-v1`）に保存し、どこにも送らない
- **入力値は HTML として扱わない**：画面にはすべて `textContent` で入れる
- **バックアップの読み込み**：他の人から受け取ったファイルも想定し、5MB・2万件・カテゴリ40個の上限と、項目ごとの型・長さ・色コードの検査を行う
- **CSV 書き出し**：`=` `+` `-` `@` で始まる値の前に `'` を付け、表計算ソフトで数式として実行されないようにする

## オフライン用の仕組み（`tools/sw.js`）

- 初回だけ、アプリ一式（約3MB。`version.json` の `assets`）を Cache Storage に保存する。以後はすべて保存したものを返す
- **アプリの更新は自動では行わない**。ページの「更新を確認する」を押したときだけ `version.json` を見に行き、「更新する」を押したときだけダウンロードする（message `check` / `apply`）
- 「更新する」の直前に、ページが記録の控え（localStorage の `tsumori-chokin-snapshot`）を取る。sw.js は 1 つ前の版も残し、「前の版に戻す」（message `rollback`）で版を入れ替え、ページが記録を控えに戻す。戻したあとは「更新する」で、取り直さずに新しい版へ戻れる
- オンラインで開くたびに、ブラウザが `sw.js` に変更がないかを確かめる（登録は `updateViaCache: "none"`、`_headers` で no-cache）。`sw.js` の不具合を直したとき、次に開いた時点で届く。アプリ本体はこれでは変わらない
- **非常口**：`<公開URL>/?reset` を開くと、アプリの保存分を最新版で取り直してから普通に開き直す（記録は消えない）。電波がないときは案内の画面を出し、保存分は消さない
- `tools/sw.js` はむやみに変えないこと。中身が変わると、利用者のブラウザが次に開いたときに自動で入れ替える（保存済みのアプリ本体はそのまま）。変えたら、古い版から上がる流れを必ず手元で試す

## 検索エンジンと SNS のカード

- 検索エンジンには載せない（`<meta name="robots" content="noindex, nofollow">`、`robots.txt` で拒否）
- ただし `robots.txt` で X のロボット（Twitterbot）だけは許可し、URL をシェアしたときに紹介カード（`og.png`）が出るようにしている。OGP のメタタグは `index.html` の head にある

## 公開（Cloudflare Pages）

公開先は Cloudflare Pages の Direct Upload（Git 連携・CLI は使わない）。無料プランで転送量・アクセス数の上限がない。

1. Cloudflare にログイン →「Workers & Pages」→ 作成 →「Pages」→「アセットをアップロード（Upload assets）」（**Git に接続は選ばない**。あとから切り替えられない）
2. `dist/web` フォルダを**フォルダごと**ドラッグ → デプロイ

直したとき：`python tools/build.py` → Pages のプロジェクトの「新しいデプロイを作成」から `dist/web` を再度ドラッグ。URL は変わらない。

- 公開のたびに `<英数字>.<プロジェクト名>.pages.dev` という URL も増えるが、別のサイト扱い（記録も別になる）なので、人に教えるのは `<プロジェクト名>.pages.dev` だけにする
- デプロイが増えすぎるとプロジェクトの削除が面倒になるので、まとめて出す
- 空のファイル（0 バイト）や `.` で始まるファイルがあると、アップロードが失敗することがある
- **Cloudflare Pages は `/index.html` を `/` へ 308 転送する**。`sw.js` は転送つきの応答を作り直して保存する（転送つきのままだとページ表示に使えず、2回目以降に開けなくなる）

公開後の確認（`index.html` は `/` で比べる）：

```bash
cd dist/web && U=https://oshi-tsumori.pages.dev
[ "$(curl -s $U/ | sha256sum | cut -c1-12)" = "$(sha256sum index.html | cut -c1-12)" ] && echo "一致 /"
for f in sw.js version.json LICENSE.txt fonts/MochiyPopOne.woff2 icons/icon-192.png; do [ "$(curl -s $U/$f | sha256sum | cut -c1-12)" = "$(sha256sum $f | cut -c1-12)" ] && echo "一致 $f" || echo "不一致 $f"; done
curl -sI $U/sw.js | grep -i cache-control
```

## 手元での確認

```bash
cd dist/web && python -m http.server 8766 --bind 127.0.0.1
```

localhost ならオフライン用の仕組みも動く。確認で localStorage や Service Worker を触ったら、終わったら消す。
