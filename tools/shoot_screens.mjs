// つもり貯金の紹介用スクショ（390x844・3倍＝1170x2532）を撮る。
// 使い捨てプロファイルの headless Chrome を DevTools プロトコルで操作するので、普段の Chrome には触れない。
// 見本の記録はこのファイルの中にある（実在の記録は使わない）。
//
// 使い方（プロジェクト直下で）:
//   python -m http.server 8769 --bind 127.0.0.1      … 編集用の index.html をそのまま配信（別のターミナルで）
//   node tools/shoot_screens.mjs promo/x             … 指定したフォルダに 1-home-bin.png などを書き出す
// README 用の画像（docs/images/）は、これを半分の大きさに縮めたもの。
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:8769/";
const OUT = process.argv[2];
const PORT = 9333;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const profile = mkdtempSync(join(tmpdir(), "tsumori-shot-"));
const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "about:blank",
], { stdio: "ignore" });

async function target() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const t = list.find(x => x.type === "page");
      if (t) return t.webSocketDebuggerUrl;
    } catch {}
    await sleep(200);
  }
  throw new Error("chrome did not start");
}

const ws = new WebSocket(await target());
await new Promise(r => ws.addEventListener("open", r, { once: true }));
let seq = 0;
const pending = new Map();
ws.addEventListener("message", e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = ++seq;
  pending.set(id, m => m.error ? rej(new Error(method + ": " + m.error.message)) : res(m.result));
  ws.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expr => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.value;

await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
await send("Emulation.setTouchEmulationEnabled", { enabled: true });

// ---------- 見本の記録 ----------
const D = (m, d) => `2026-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
let n = 0;
const E = (name, amount, category, date, pot = "main") => ({ id: "s" + (++n), name, amount, category, date, createdAt: n, memo: "", pot });
const baseEntries = [
  E("春ツアー 仙台公演", 10500, "live", D(4, 12)),
  E("ランダム缶バッジ 10個", 5000, "goods", D(4, 28)),
  E("福岡遠征 飛行機とホテル", 32000, "trip", D(5, 18)),
  E("FC先行 追加公演", 11000, "live", D(6, 9)),
  E("トレカ 1BOX", 6600, "goods", D(7, 3)),
  E("夏ツアー 横浜公演", 11000, "live", D(8, 2)),
  E("アクスタ全種", 7200, "goods", D(8, 24)),
  E("大阪遠征 新幹線", 14500, "trip", D(9, 14)),
  E("コンビニスイーツ", 480, "other", D(9, 21)),
  E("ファンミ 東京公演", 9800, "live", D(9, 28)),
];
const one = { version: 4, entries: baseEntries, achieved: [],
  pots: [{ id: "main", name: "つぎの遠征", amount: 150000, deadline: "", base: 0, view: "jar", shelf: { n: 0, amount: 0 } }],
  cur: "main", split: false };

n = 100;
const gachaEntries = [
  E("春ツアー 仙台公演", 10500, "live", D(4, 12), "ensei"),
  E("福岡遠征 飛行機", 18000, "trip", D(5, 18), "ensei"),
  E("FC先行 追加公演", 11000, "live", D(6, 9), "ensei"),
  E("夏ツアー 横浜公演", 11000, "live", D(8, 2), "ensei"),
  E("大阪遠征 新幹線", 14500, "trip", D(9, 14), "ensei"),
  E("コンビニスイーツ", 480, "other", D(9, 21), "ensei"),
  E("ファンミ 東京公演", 9800, "live", D(9, 28), "ensei"),
  E("ランダム缶バッジ", 5000, "goods", D(4, 28), "goods"),
  E("アクスタ全種", 7200, "goods", D(8, 24), "goods"),
];
const two = { version: 4, entries: gachaEntries, achieved: [],
  pots: [
    { id: "ensei", name: "遠征用", amount: 100000, deadline: "", base: 0, view: "gacha", shelf: { n: 0, amount: 0 } },
    { id: "goods", name: "グッズ用", amount: 30000, deadline: "", base: 0, view: "jar", shelf: { n: 0, amount: 0 } },
  ], cur: "ensei", split: true };

const shots = [
  { file: "1-home-bin.png", data: one, theme: "light", oshi: null, hash: "#home", scroll: 0 },
  { file: "2-home-gacha.png", data: two, theme: "dark", oshi: "#A374E8", hash: "#home", scroll: 0 },
  { file: "3-stats.png", data: one, theme: "light", oshi: "#5CC8F0", hash: "#stats", scroll: 0 },
  { file: "4-history.png", data: one, theme: "light", oshi: null, hash: "#history", scroll: 0 },
];

await send("Page.navigate", { url: BASE });
await sleep(1500);
for (const s of shots) {
  await evaluate(`(() => {
    localStorage.clear();
    localStorage.setItem("tsumori-chokin-v1", ${JSON.stringify(JSON.stringify(s.data))});
    localStorage.setItem("tsumori-chokin-theme", ${JSON.stringify(s.theme)});
    ${s.oshi ? `localStorage.setItem("tsumori-chokin-oshi", ${JSON.stringify(s.oshi)});` : ""}
    return true; })()`);
  await send("Page.navigate", { url: BASE + "?shot=" + encodeURIComponent(s.file) + s.hash });   // ? を変えて毎回読み込み直す
  await sleep(2500);
  await evaluate(`document.fonts.ready.then(() => { window.scrollTo(0, ${s.scroll}); return true; })`);
  await sleep(1200);
  const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(join(OUT, s.file), Buffer.from(data, "base64"));
  console.log("shot", s.file);
}

ws.close();
chrome.kill();
await sleep(500);
try { rmSync(profile, { recursive: true, force: true }); } catch {}
