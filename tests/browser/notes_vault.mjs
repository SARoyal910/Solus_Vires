// Notes export and search (P2-E3), the encrypted safety plan (P2-E8), and
// photo evidence (P2-E7) in headless Chrome against a local preview.
//   PREVIEW_URL=http://127.0.0.1:8120 node tests/browser/notes_vault.mjs
// One throwaway account on the local preview; never point it at production.
import puppeteer from "puppeteer-core";
import crypto from "node:crypto";
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import vm from "node:vm";
import { containsGps, withExif } from "../web/exif-fixture.mjs";

const BASE = process.env.PREVIEW_URL || "http://127.0.0.1:8099";
const PASSWORD = "pw-" + crypto.randomBytes(8).toString("hex");
const PIN = "pin-" + crypto.randomBytes(8).toString("hex");
const results = [];
const check = (name, ok, extra = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  (" + extra + ")" : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The page's own metadata scanner, run here on bytes pulled out of the browser.
const sandbox = { window: {} };
vm.runInNewContext(readFileSync(new URL("../../html/image-clean.js", import.meta.url), "utf8"), sandbox);
const { findMetadata, readExifDate } = sandbox.window.ImageClean;

const work = mkdtempSync(join(tmpdir(), "sv-vault-"));
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: process.env.CI ? ["--no-sandbox"] : [],
});
const ctx = await browser.createBrowserContext();
const page = await ctx.newPage();
await page.setViewport({ width: 1100, height: 900 });
page.on("pageerror", (e) => check("no page errors", false, e.message));
await page.evaluateOnNewDocument(() => { window.print = () => { window.__printed = (window.__printed || 0) + 1; }; });
const cdp = await browser.target().createCDPSession();
await cdp.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: work, browserContextId: ctx.id });

async function waitFor(fn, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await sleep(150); }
  return false;
}
const text = (sel) => page.$eval(sel, (el) => el.textContent);
const visible = (id) => page.$eval(`#${id}`, (el) => !el.hidden && el.getBoundingClientRect().height > 0);

// Account + PIN.
await page.goto(`${BASE}/account.html`, { waitUntil: "load" });
const user = "vault_" + crypto.randomBytes(4).toString("hex");
const reg = await page.evaluate(async (u, p) => {
  const opts = (b) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
  return [(await fetch("/api/auth/register", opts({ username: u, password: p }))).status, (await fetch("/api/auth/login", opts({ username: u, password: p }))).status];
}, user, PASSWORD);
if (reg[0] !== 200 || reg[1] !== 200) throw new Error("account setup failed " + reg);
await page.goto(`${BASE}/log.html`, { waitUntil: "load" });
await waitFor(() => visible("pin-setup-view"));
await page.evaluate((pin) => { const f = document.getElementById("pin-setup-form"); f.pin.value = pin; f.pin_confirm.value = pin; f.requestSubmit(); }, PIN);
await waitFor(() => visible("unlocked-view"));
await page.evaluate(() => document.getElementById("first-save-ack").click());

// --- P2-E8 safety plan ---
await page.evaluate(() => {
  document.getElementById("plan-details").open = true;
  const f = document.getElementById("plan-form");
  f.elements["field:code_word"].value = "blue kettle";
  f.elements["field:people"].value = "Sam 555-0100";
  f.elements["check:id"].checked = true;
  f.elements["check:meds"].checked = true;
  f.requestSubmit();
});
check("plan saves", await waitFor(async () => (await text("#plan-status")) === "Plan saved."));
const storedPlan = await page.evaluate(async () => (await (await fetch("/api/evidence/safety-plan")).json()));
check("plan reaches the server only as ciphertext", !!storedPlan && !JSON.stringify(storedPlan).includes("kettle") && !atob(storedPlan.ciphertext).includes("kettle"));

// --- entries + search ---
async function addEntry(date, body, files = []) {
  if (files.length) await (await page.$("#entry-form input[name=photos]")).uploadFile(...files);
  await page.evaluate((d, t) => { const f = document.getElementById("entry-form"); f.entry_date.value = d; f.text.value = t; f.requestSubmit(); }, date, body);
  await waitFor(async () => /^Added|Entry added|Nothing was saved|Unable/.test(await text("#entry-status")), 40000);
  return text("#entry-status");
}
await addEntry("2026-09-20", "They took the car keys again.");
await addEntry("2026-09-01", "Shouting about money at night.");

await page.evaluate(() => { const s = document.getElementById("entry-search"); s.value = "car keys"; s.dispatchEvent(new Event("input")); });
const shown = await page.$$eval("#entries-list .entry-card", (cards) => cards.filter((c) => !c.hidden).map((c) => c.textContent));
check("search finds matching entries only", shown.length === 1 && shown[0].includes("car keys"), await text("#search-status"));
await page.evaluate(() => { const s = document.getElementById("entry-search"); s.value = "september 1"; s.dispatchEvent(new Event("input")); });
check("search matches the written date too", (await page.$$eval("#entries-list .entry-card", (c) => c.filter((x) => !x.hidden).length)) === 1);
await page.evaluate(() => { const s = document.getElementById("entry-search"); s.value = ""; s.dispatchEvent(new Event("input")); });

// --- P2-E7 photos: a GPS-tagged JPEG must lose its EXIF before encryption ---
const plainJpeg = Buffer.from(await page.evaluate(async () => {
  const c = document.createElement("canvas");
  c.width = 320; c.height = 200;
  const g = c.getContext("2d");
  g.fillStyle = "#3a6"; g.fillRect(0, 0, 320, 200); g.fillStyle = "#fff"; g.fillRect(40, 40, 120, 60);
  const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
  return [...new Uint8Array(await blob.arrayBuffer())];
}));
const gpsJpeg = withExif(new Uint8Array(plainJpeg));
check("fixture: the test photo really carries EXIF with GPS", findMetadata(gpsJpeg).includes("EXIF") && containsGps(gpsJpeg));
const gpsPath = join(work, "IMG_0001.jpg");
writeFileSync(gpsPath, gpsJpeg);
const notImage = join(work, "notes.txt");
writeFileSync(notImage, "not a photo");

// Record exactly what the cleaner hands to the encryption step.
await page.evaluate(() => {
  const original = ImageClean.cleanImage;
  window.__cleaned = [];
  ImageClean.cleanImage = async (file) => { const out = await original(file); window.__cleaned.push([...out.bytes]); return out; };
});

const before = await page.evaluate(async () => (await (await fetch("/api/evidence/entries")).json()).length);
const refused = await addEntry("2026-09-25", "should not save", [notImage]);
const after = await page.evaluate(async () => (await (await fetch("/api/evidence/entries")).json()).length);
check("a non-image file stops the save and nothing is written", /Nothing was saved/.test(refused) && after === before, refused);

const added = await addEntry("2026-09-21", "Photo of the message he sent.", [gpsPath]);
check("entry with a photo saves", /with 1 photo/.test(added), added);
const cleanedBytes = new Uint8Array((await page.evaluate(() => window.__cleaned))[0] || []);
check("before encryption: the cleaned photo has no EXIF or other metadata", cleanedBytes.length > 0 && findMetadata(cleanedBytes).length === 0, JSON.stringify(findMetadata(cleanedBytes)));
check("before encryption: no GPS bytes survive", cleanedBytes.length > 0 && !containsGps(cleanedBytes));

const stored = await page.evaluate(async (pin) => {
  const list = await (await fetch("/api/evidence/attachments")).json();
  const data = await (await fetch(`/api/evidence/attachments/${list[0].id}`)).json();
  const salt = (await (await fetch("/api/evidence/salt")).json()).salt;
  const key = await EvidenceCrypto.deriveKey(pin, salt);
  const bytes = await EvidenceCrypto.decryptBytes(key, data.ciphertext, data.iv);
  const meta = await EvidenceCrypto.decryptJSON(key, list[0].meta_ciphertext, list[0].meta_iv);
  return { count: list.length, raw: atob(data.ciphertext).slice(0, 4000), bytes: [...bytes], meta };
}, PIN);
const storedBytes = new Uint8Array(stored.bytes);
check("server holds one photo, as ciphertext (no JPEG or EXIF markers)", stored.count === 1 && !stored.raw.includes("Exif") && !stored.raw.includes("JFIF"));
check("decrypted stored photo has no metadata and no GPS", findMetadata(storedBytes).length === 0 && !containsGps(storedBytes));
check("capture date kept inside the encrypted description; no location field", stored.meta.taken === "2026-09-01T21:14:05" && !JSON.stringify(stored.meta).match(/gps|lat|lon/i), JSON.stringify(stored.meta));
check("decrypted photo is a real image of the same size", readExifDate(storedBytes) === null && stored.meta.width === 320 && stored.meta.height === 200);

await page.evaluate(() => [...document.querySelectorAll("#entries-list button")].find((b) => b.textContent === "Show").click());
check("photo shows in the entry after decrypting", await waitFor(() => page.evaluate(() => { const img = document.querySelector(".photo-preview"); return !!img && img.naturalWidth === 320; })));

// --- P2-E3 export: preparing may download (encrypted) photos; after that, nothing ---
await page.evaluate(() => document.getElementById("export-open-btn").click());
check("export view opens", await waitFor(() => visible("export-view")));
const requests = [];
const onRequest = (req) => { if (/^https?:/.test(req.url())) requests.push(`${req.method()} ${req.url()}`); };
page.on("request", onRequest);
await page.evaluate(() => document.getElementById("export-print-btn").click());
await page.evaluate(() => document.getElementById("export-text-btn").click());
await sleep(1500);
page.off("request", onRequest);
check("print and text download make zero network requests", requests.length === 0, requests.join(", "));
check("print was called", (await page.evaluate(() => window.__printed)) === 1);

const doc = await text("#export-doc");
const order = ["Shouting about money", "car keys", "Photo of the message"].map((t) => doc.indexOf(t));
check("export lists entries oldest first", order.every((i) => i >= 0) && order[0] < order[1] && order[1] < order[2]);
check("export has dates in words and saved times", /September 1, 2026/.test(doc) && /Saved: \d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(doc));
check("export includes the safety plan", /Safety plan/.test(doc) && /blue kettle/.test(doc) && /ID or driver's license/.test(doc));
check("export includes the photo, with its taken date", await page.evaluate(() => { const img = document.querySelector("#export-doc img"); return !!img && img.naturalWidth === 320 && /taken 2026-09-01 21:14/.test(document.getElementById("export-doc").textContent); }));
check("export says plainly that the copy is not encrypted", /not encrypted/.test(await text("#export-view")));

const files = readdirSync(work).filter((f) => f.startsWith("notes-") && f.endsWith(".txt"));
const txt = files.length ? readFileSync(join(work, files[0]), "utf8") : "";
check("text file downloads, with entries, plan, and photo listed", /car keys/.test(txt) && /blue kettle/.test(txt) && /IMG_0001\.jpg, taken 2026-09-01 21:14/.test(txt), files.join(","));

// Print stylesheet: only the export copy prints.
await page.emulateMediaType("print");
const printed = await page.evaluate(() => ({
  header: getComputedStyle(document.querySelector("body > header")).display,
  controls: getComputedStyle(document.querySelector(".export-controls")).display,
  doc: getComputedStyle(document.getElementById("export-doc")).display,
  bg: getComputedStyle(document.getElementById("export-doc")).backgroundColor,
}));
await page.emulateMediaType("screen");
check("print shows only the export copy, on white", printed.header === "none" && printed.controls === "none" && printed.doc !== "none" && printed.bg === "rgb(255, 255, 255)", JSON.stringify(printed));

// --- locking wipes it all; unlocking brings it back ---
await page.evaluate(() => document.getElementById("lock-now-btn").click());
const wiped = await page.evaluate(() => ({
  doc: document.getElementById("export-doc").textContent,
  list: document.getElementById("entries-list").textContent,
  plan: document.getElementById("plan-form").elements["field:code_word"].value,
  imgs: document.querySelectorAll("img[src^='blob:']").length,
}));
check("lock wipes the export copy, entries, plan, and photos from the page", !wiped.doc && !wiped.list && !wiped.plan && wiped.imgs === 0, JSON.stringify(wiped));
await page.evaluate((pin) => { const f = document.getElementById("pin-unlock-form"); f.pin.value = pin; f.requestSubmit(); }, PIN);
await waitFor(() => visible("unlocked-view"));
await waitFor(async () => (await page.$$("#entries-list .entry-card")).length === 3);
check("after unlock the plan comes back", (await page.evaluate(() => document.getElementById("plan-form").elements["field:code_word"].value)) === "blue kettle"
  && (await page.evaluate(() => document.getElementById("plan-form").elements["check:id"].checked)));
check("after unlock the photo is listed on its entry", /IMG_0001\.jpg/.test(await text("#entries-list")));

// Deleting the entry deletes its photo on the server.
await page.evaluate(() => {
  const card = [...document.querySelectorAll(".entry-card")].find((c) => c.textContent.includes("Photo of the message"));
  [...card.querySelectorAll("button")].find((b) => b.textContent === "Delete").click();
});
await waitFor(async () => (await page.$$("#entries-list .entry-card")).length === 2);
check("deleting an entry deletes its photos", (await page.evaluate(async () => (await (await fetch("/api/evidence/attachments")).json()).length)) === 0);

await browser.close();
console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
process.exit(results.every(Boolean) ? 0 : 1);
