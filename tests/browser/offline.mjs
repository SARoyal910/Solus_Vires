// Drives the installable-app / offline-copy behaviour (P2-E9) in headless
// Chrome against a local preview. Never point it at production.
//   scripts/preview.sh && node tests/browser/offline.mjs
//   PREVIEW_URL=http://127.0.0.1:8130 node tests/browser/offline.mjs
// Needs puppeteer-core (see notes_pin.mjs) and Chrome.
import puppeteer from "puppeteer-core";

const BASE = process.env.PREVIEW_URL || "http://127.0.0.1:8099";
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const EXPECTED = [
  "/emergency.html", "/resources.html", "/es/emergencia.html", "/es/recursos.html",
  "/shared.css", "/shared.js", "/offline.js", "/local-help.js", "/manifest.json", "/icon-192.png", "/icon-512.png",
];
const results = [];
const check = (name, ok, extra = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  (" + extra + ")" : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, ms = 15000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await sleep(150); }
  return false;
}

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true });

const cacheKeys = (page) => page.evaluate(async () => {
  const out = [];
  for (const name of await caches.keys()) {
    for (const req of await (await caches.open(name)).keys()) out.push(new URL(req.url).pathname);
  }
  return out.sort();
});
const registered = (page) => page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration("/")));
const statusText = (page) => page.$eval("#offline-status", (el) => el.textContent.trim());
const visible = (page, id) => page.$eval(`#${id}`, (el) => !el.hidden);

// 1. Manifest and icons are same-origin and well-formed.
{
  const page = await (await browser.createBrowserContext()).newPage();
  await page.goto(`${BASE}/index.html`, { waitUntil: "load" });
  const m = await page.evaluate(async () => {
    const link = document.querySelector('link[rel="manifest"]');
    const res = await fetch(link.href);
    const json = await res.json();
    const icons = await Promise.all(json.icons.map(async (i) => (await fetch(i.src)).status));
    const touch = (await fetch(document.querySelector('link[rel="apple-touch-icon"]').href)).status;
    return { href: link.getAttribute("href"), json, icons, touch };
  });
  check("manifest is same-origin and parses", m.href === "/manifest.json" && m.json.start_url === "/" && m.json.display === "standalone");
  check("manifest uses the plain site name", m.json.name === "Solus Vires" && m.json.short_name === "Solus Vires");
  check("every icon loads", m.icons.every((s) => s === 200) && m.touch === 200, m.icons.join(","));
}

// 2. Reading the crisis pages stores nothing and registers nothing.
const ctx = await browser.createBrowserContext();
const page = await ctx.newPage();
const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(String(e)));
for (const p of ["/emergency.html", "/resources.html", "/es/emergencia.html", "/es/recursos.html"]) {
  await page.goto(BASE + p, { waitUntil: "load" });
}
await page.goto(`${BASE}/emergency.html`, { waitUntil: "load" });
check("panel shown, save offered", (await visible(page, "offline-panel")) && (await visible(page, "offline-save")) && !(await visible(page, "offline-remove")));
check("visiting registers no service worker", !(await registered(page)));
check("visiting stores nothing", (await cacheKeys(page)).length === 0);

// 3. Save: exactly the listed public files, nothing private.
await page.evaluate(() => document.getElementById("offline-save-btn").click());
await waitFor(async () => (await statusText(page)).startsWith("Saved on this device"));
check("save reports success", (await statusText(page)).startsWith("Saved on this device"), await statusText(page));
let keys = await cacheKeys(page);
check("cache holds exactly the crisis pages and their files", JSON.stringify(keys) === JSON.stringify([...EXPECTED].sort()), keys.join(" "));
check("remove is now offered", (await visible(page, "offline-remove")) && !(await visible(page, "offline-save")));

// 4. While controlled, private pages and the API are never written to the cache.
for (const p of ["/account.html", "/log.html", "/checkin.html", "/about.html"]) await page.goto(BASE + p, { waitUntil: "load" });
await page.evaluate(() => fetch("/api/health").then((r) => r.text()));
await page.evaluate(() => fetch("/api/auth/me").then((r) => r.text()));
keys = await cacheKeys(page);
check("private pages and /api/ never cached", !keys.some((k) => /account|log\.html|checkin|about|\/api\//.test(k)), keys.join(" "));

// 5. Network first: an online visit refreshes the saved copy.
const savedDate = () => page.evaluate(async () => (await (await caches.open("offline-v1")).match("/emergency.html")).headers.get("date"));
const before = await savedDate();
await sleep(1500);
await page.goto(`${BASE}/emergency.html`, { waitUntil: "load" });
await waitFor(async () => (await savedDate()) !== before, 5000);
check("online visit fetched the page and refreshed the saved copy", (await savedDate()) !== before, `${before} -> ${await savedDate()}`);

// 6. Offline: the saved copy is served; other pages fall back to it.
const swTarget = await browser.waitForTarget((t) => t.type() === "service_worker" && t.url().endsWith("/sw.js") && t.browserContext() === ctx);
const swSession = await swTarget.createCDPSession();
await swSession.send("Network.enable");
await swSession.send("Network.emulateNetworkConditions", { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
await page.setOfflineMode(true);
await page.goto(`${BASE}/resources.html`, { waitUntil: "load" });
check("offline: Resources opens from the saved copy", (await page.$eval("h1", (el) => el.textContent)).length > 0 && (await page.title()).includes("Resources"));
await page.goto(`${BASE}/emergency.html`, { waitUntil: "load" });
await waitFor(() => visible(page, "offline-note"), 5000);
check("offline: Emergency says it's a saved copy", (await visible(page, "offline-note")) && (await page.$eval("#offline-note", (el) => el.textContent)).startsWith("You're offline"));
// A page this browser never fetched (a visited one may still sit in the HTTP
// cache, which is the browser's doing, not the worker's).
await page.goto(`${BASE}/legal.html`, { waitUntil: "load" });
check("offline: another page falls back to Emergency", (await page.title()).startsWith("Emergency"), await page.title());
await page.goto(`${BASE}/es/`, { waitUntil: "load" });
check("offline: /es/ falls back to the Spanish emergency page", (await page.evaluate(() => document.documentElement.lang)) === "es");
await page.setOfflineMode(false);
await swSession.send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });

// 7. Remove deletes the copy and unregisters the worker (no push here).
await page.goto(`${BASE}/emergency.html`, { waitUntil: "load" });
await waitFor(() => visible(page, "offline-remove"));
await page.evaluate(() => document.getElementById("offline-remove-btn").click());
await waitFor(async () => (await statusText(page)).startsWith("The saved copy has been removed"));
check("remove deletes the saved copy", (await cacheKeys(page)).length === 0);
check("remove unregisters the worker", await waitFor(async () => !(await registered(page)), 5000));
check("no script errors on these pages", consoleErrors.length === 0, consoleErrors.join(" | "));

// 8. A trusted contact's push-only worker never caches anything.
{
  const ctx2 = await browser.createBrowserContext();
  await ctx2.overridePermissions(BASE, ["notifications"]);
  const p2 = await ctx2.newPage();
  await p2.goto(`${BASE}/checkin-invite.html`, { waitUntil: "load" });
  await p2.evaluate(async () => { await navigator.serviceWorker.register("/sw.js"); await navigator.serviceWorker.ready; });
  for (const p of ["/es/recursos.html", "/resources.html", "/emergency.html"]) await p2.goto(BASE + p, { waitUntil: "load" });
  check("push-only worker: crisis pages still not cached", (await cacheKeys(p2)).length === 0);
  await sleep(500);
  check("push-only worker: page shows 'not saved'", (await statusText(p2)).startsWith("Not saved"), await statusText(p2));
  // Push still works through the same worker (trusted contacts' alerts).
  const t = await browser.waitForTarget((x) => x.type() === "service_worker" && x.browserContext() === ctx2);
  const cdp = await p2.createCDPSession();
  const origin = new URL(BASE).origin;
  const regId = await p2.evaluate(async () => (await navigator.serviceWorker.getRegistration("/")).scope);
  await cdp.send("ServiceWorker.enable");
  const regs = await new Promise((resolve) => { cdp.on("ServiceWorker.workerRegistrationUpdated", (e) => resolve(e.registrations)); });
  const reg = regs.find((r) => r.scopeURL === regId);
  await cdp.send("ServiceWorker.deliverPushMessage", { origin, registrationId: reg.registrationId, data: JSON.stringify({ title: "Test alert", body: "test-user missed a scheduled check-in.", url: "/if-you-get-an-alert.html" }) });
  const shown = await waitFor(async () => (await p2.evaluate(async () => (await (await navigator.serviceWorker.getRegistration("/")).getNotifications()).map((n) => n.title))).includes("Test alert"), 5000);
  check("push: an alert still shows a notification", shown, t.url());
}

await browser.close();
const failed = results.filter((r) => !r).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
