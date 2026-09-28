// つもり貯金 — オフライン用 Service Worker
//
// ・初回だけ、アプリ一式（version.json に載っているファイル）を端末に保存する
// ・以後はすべて端末に保存したものを返す。記録はページ側の localStorage にあり、ここでは扱わない
// ・新しい版の確認とダウンロードは、ページの「更新を確認する」「更新する」を押したときだけ行う
// ・1 つ前の版も捨てずに残し、「前の版に戻す」で切り替えられる
//
// ⚠️ このファイルはむやみに変えないこと。中身が変わると、ブラウザが自動で新しい sw.js を入れる
//    （保存済みのアプリ本体はそのまま）。アプリの版は version.json で管理している（tools/build.py が生成）。
"use strict";

const META = "tsumori-meta";           // いま使っている保存先（active）と、1 つ前の保存先（prev）の名前を覚えておく場所
let activeName = null;

async function getMeta(key) {
  const r = await (await caches.open(META)).match(key);
  return r ? await r.text() : null;
}
async function setMeta(key, value) {
  const c = await caches.open(META);
  if (value) await c.put(key, new Response(value)); else await c.delete(key);
}
async function getActive() {
  if (!activeName) activeName = await getMeta("active");
  return activeName;
}
async function setActive(name) {
  await setMeta("active", name);
  activeName = name;
}

// 更新内容の一覧（なくても動く。形がおかしければ捨てる）
function okNotes(m) {
  const notes = Array.isArray(m.notes) ? m.notes.slice(0, 20).filter(n => n && Number.isInteger(n.rev) && typeof n.date === "string" && n.date.length <= 10 &&
    Array.isArray(n.items) && n.items.length <= 20 && n.items.every(x => typeof x === "string" && x.length <= 100)) : [];
  return { rev: Number.isInteger(m.rev) ? m.rev : 0, notes };
}

// 公開先の version.json を読む（呼ばれたときだけ通信する）
async function fetchManifest() {
  const r = await fetch("version.json", { cache: "no-store" });
  if (!r.ok) throw new Error("http " + r.status);
  const m = await r.json();
  const okPath = a => typeof a === "string" && a.length < 200 && !/^[a-z][a-z0-9+.-]*:|^\/\/|\.\./i.test(a);
  if (!m || typeof m.version !== "string" || !/^[0-9a-f]{6,64}$/.test(m.version) || !Array.isArray(m.assets) || !m.assets.every(okPath)) {
    throw new Error("bad manifest");
  }
  return { version: m.version, assets: m.assets, ...okNotes(m) };
}
// 公開先が /index.html を / へ転送する（Cloudflare Pages など）と、転送を経た応答が保存される。
// ブラウザはそれをページ表示に使うことを認めないので、転送の印を外した応答に作り直す
async function clean(r) {
  if (!r || !r.redirected) return r;
  return new Response(await r.blob(), { status: r.status, statusText: r.statusText, headers: r.headers });
}
// 初回はページ表示で読み込んだものをブラウザのキャッシュから使い回す（二重にダウンロードしない）。
// 更新のときは公開先に問い合わせ直す
async function download(m, fresh) {
  const name = "tsumori-" + m.version;
  const cache = await caches.open(name);
  const got = await Promise.all(m.assets.map(async a => {
    const r = await fetch(new Request(a, { cache: fresh ? "no-cache" : "default" }));
    if (!r.ok) throw new Error("http " + r.status + " " + a);
    return [a, await clean(r)];
  }));
  for (const [a, r] of got) await cache.put(a, r);
  await cache.put("version.json", new Response(JSON.stringify(m), { headers: { "Content-Type": "application/json" } }));
  return name;
}
// 保存先に入っている版の情報（version.json を最後に書くので、これがあれば一式そろっている）
async function infoOf(name) {
  if (!name || !(await caches.has(name))) return null;
  const r = await (await caches.open(name)).match("version.json");
  if (!r) return null;
  const m = await r.json();
  return { version: m.version, ...okNotes(m) };
}
async function cleanup() {
  const keep = new Set([META, await getActive(), await getMeta("prev")]);
  for (const k of await caches.keys()) if (k.startsWith("tsumori-") && !keep.has(k)) await caches.delete(k);
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    // すでに保存済みなら何もしない（このファイル自体が変わったときも、保存済みのアプリをそのまま使う）
    if (!(await getActive())) await setActive(await download(await fetchManifest(), false));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => { await cleanup(); await self.clients.claim(); })());
});

// 非常口：?reset を付けて開くと、アプリの保存分を公開先の最新版で取り直してから普通に開き直す。
// 記録（localStorage）には触れない。アプリ本体が壊れて「更新する」ボタンが押せないときに使う
async function resetApp() {
  const m = await fetchManifest();
  const name = "tsumori-" + m.version;
  await caches.delete(name);                         // 取り直す版の保存分は、いったん空にしてから入れ直す
  const old = await getActive();
  await setActive(await download(m, true));
  if (old === name) await setMeta("prev", null);
  await cleanup();
}
const RESET_FAILED = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<title>つもり貯金</title><p style="font:16px/1.7 sans-serif;padding:24px">入れ直しに失敗しました。電波のあるところで、もう一度このリンクを開いてください。<br>記録はそのまま残っています。<br><a href="./">いまの版のまま開く</a></p>';

self.addEventListener("fetch", event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (req.mode === "navigate" && url.searchParams.has("reset")) {
    event.respondWith(resetApp().then(
      () => Response.redirect(new URL("./", self.location.href).href, 303),
      () => new Response(RESET_FAILED, { headers: { "Content-Type": "text/html; charset=utf-8" } })));
    return;
  }
  event.respondWith((async () => {
    const name = await getActive();
    const cache = name ? await caches.open(name) : null;
    const hit = cache && (req.mode === "navigate"
      ? (await cache.match("index.html")) || (await cache.match("./"))   // #タブ や ?付き でも保存済みのページを返す
      : await cache.match(req, { ignoreSearch: true }));
    if (hit && hit.redirected) {
      // 以前の版が転送つきのまま保存したもの。作り直して保存し直す（これで次からは直ったまま）
      const fixed = await clean(hit);
      await cache.put(req.mode === "navigate" ? "index.html" : req, fixed.clone());
      return fixed;
    }
    return hit || fetch(req);
  })());
});

// ページからの依頼（ボタンを押したときだけ届く）
self.addEventListener("message", event => {
  const port = event.ports && event.ports[0];
  const type = event.data && event.data.type;
  if (!port) return;
  const reply = p => p.then(v => port.postMessage({ ok: true, ...v }), e => port.postMessage({ ok: false, error: String(e && e.message || e) }));
  const versions = async () => {
    const [cur, prev] = await Promise.all([infoOf(await getActive()), infoOf(await getMeta("prev"))]);
    return { cur, prev };
  };
  if (type === "version") {
    // 残している版が今より新しい（前の版に戻したあと）なら、「前の版」としては返さない（「更新する」で戻れる）
    event.waitUntil(reply(versions().then(({ cur, prev }) => ({
      current: cur && cur.version,
      prev: prev && !(cur && prev.rev > cur.rev) ? prev.version : null,
    }))));
  } else if (type === "check") {
    event.waitUntil(reply((async () => {
      const [{ cur }, m] = await Promise.all([versions(), fetchManifest()]);
      const rev = cur ? cur.rev : 0;
      // 今の版より新しい更新内容だけを返す
      return { current: cur && cur.version, latest: m.version, notes: m.version === (cur && cur.version) ? [] : m.notes.filter(n => n.rev > rev) };
    })()));
  } else if (type === "apply") {
    event.waitUntil(reply((async () => {
      const [m, { cur }] = await Promise.all([fetchManifest(), versions()]);
      if (cur && m.version === cur.version) return { current: m.version, updated: false };
      const name = (await infoOf("tsumori-" + m.version)) ? "tsumori-" + m.version   // 前に戻した版をもう一度使うときは取り直さない
        : await download(m, true);                                                 // すべて保存できてから切り替える
      const old = await getActive();
      await setMeta("prev", old !== name ? old : null);
      await setActive(name);
      await cleanup();
      return { current: m.version, prev: cur && cur.version, updated: true };
    })()));
  } else if (type === "rollback") {
    event.waitUntil(reply((async () => {
      const prevName = await getMeta("prev"), prev = await infoOf(prevName);
      if (!prev) throw new Error("no previous version");
      const old = await getActive();
      await setActive(prevName);                       // 入れ替える（戻したあと「更新する」で、また新しい版にできる）
      await setMeta("prev", old);
      return { current: prev.version, rolledBack: true };
    })()));
  }
});
