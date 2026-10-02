// Drives the Notes PIN flows in headless Chrome against scripts/preview.sh.
//   (cd tests/browser && npm install puppeteer-core@23) && node tests/browser/notes_pin.mjs
// SV_BASE_URL points it at another local preview (default http://127.0.0.1:8099).
// Uses throwaway accounts on the local preview only; never point it at production.
import puppeteer from "puppeteer-core";
import crypto from "node:crypto";

const BASE = process.env.SV_BASE_URL || "http://127.0.0.1:8099";
const rnd = () => crypto.randomBytes(4).toString("hex");
const PASSWORD = "pw-" + crypto.randomBytes(8).toString("hex");
const PIN = "pin-" + crypto.randomBytes(8).toString("hex");
const WRONG = PIN + "x";
const results = [];
const check = (name, ok, extra = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  (" + extra + ")" : ""}`); };

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});

async function freshUser() {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/account.html`);
  const user = "chk_" + rnd();
  const r = await page.evaluate(async (u, p) => {
    const reg = await fetch("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p }) });
    const log = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p }) });
    return [reg.status, log.status];
  }, user, PASSWORD);
  if (r[0] !== 200 || r[1] !== 200) throw new Error("account setup failed " + r);
  return page;
}

const visible = (page, id) => page.$eval(`#${id}`, (el) => !el.hidden);
const statusText = (page, id) => page.$eval(`#${id}`, (el) => el.textContent.trim());
async function waitFor(page, fn, ms = 15000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await new Promise((r) => setTimeout(r, 150)); }
  return false;
}
async function unlock(page, pin) {
  await page.$eval("#pin-unlock-form input[name=pin]", (el, v) => { el.value = v; }, pin);
  await page.$eval("#pin-unlock-form", (f) => f.requestSubmit());
  await waitFor(page, async () => (await visible(page, "unlocked-view")) || !["", "Unlocking..."].includes(await statusText(page, "pin-unlock-status")));
  return (await visible(page, "unlocked-view")) ? "UNLOCKED" : await statusText(page, "pin-unlock-status");
}
const keyCheck = (page) => page.evaluate(async () => (await (await fetch("/api/evidence/salt")).json()).key_check);

// 1. New account: set PIN, then a wrong PIN on the EMPTY vault must be rejected (H3).
{
  const page = await freshUser();
  await page.goto(`${BASE}/log.html`);
  await waitFor(page, () => visible(page, "pin-setup-view"));
  check("new account sees PIN setup", await visible(page, "pin-setup-view"));

  await page.$eval("#pin-setup-form input[name=pin]", (el) => { el.value = "short-pin"; });
  await page.$eval("#pin-setup-form input[name=pin_confirm]", (el) => { el.value = "short-pin"; });
  await page.$eval("#pin-setup-form", (f) => { f.noValidate = true; f.requestSubmit(); f.noValidate = false; });
  await waitFor(page, async () => (await statusText(page, "pin-setup-status")) !== "");
  check("PIN under 12 characters is refused", (await statusText(page, "pin-setup-status")) === "PIN is too short." && !(await visible(page, "unlocked-view")));

  await page.$eval("#pin-setup-form input[name=pin]", (el, v) => { el.value = v; }, PIN);
  await page.$eval("#pin-setup-form input[name=pin_confirm]", (el, v) => { el.value = v; }, PIN);
  await page.$eval("#pin-setup-form", (f) => f.requestSubmit());
  check("setup unlocks the notes", await waitFor(page, () => visible(page, "unlocked-view")));
  check("key-check stored at setup", !!(await keyCheck(page)));

  await page.click("#lock-now-btn");
  check("wrong PIN on empty vault is rejected", (await unlock(page, WRONG)) === "Incorrect PIN.");
  check("right PIN unlocks", (await unlock(page, PIN)) === "UNLOCKED");
}

// 2. Older account, PIN set before key-checks existed, nothing saved: PIN must be entered twice.
{
  const page = await freshUser();
  await page.evaluate(() => fetch("/api/evidence/salt", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ salt: "c2FsdHNhbHRzYWx0c2FsdA==" }) }));
  await page.goto(`${BASE}/log.html`);
  await waitFor(page, () => visible(page, "pin-unlock-view"));
  check("legacy: first entry asks to confirm", (await unlock(page, PIN)).startsWith("Enter the same PIN once more"));
  check("legacy: different second entry is rejected", (await unlock(page, WRONG)).startsWith("Those didn't match"));
  await unlock(page, PIN);
  check("legacy: same PIN twice unlocks", (await unlock(page, PIN)) === "UNLOCKED");
  check("legacy: key-check written", !!(await keyCheck(page)));
  await page.click("#lock-now-btn");
  check("legacy: afterwards a wrong PIN is rejected first time", (await unlock(page, WRONG)) === "Incorrect PIN.");
}

// 3. Older account with a saved note: verified against the note, then key-check backfilled.
{
  const page = await freshUser();
  await page.goto(`${BASE}/log.html`);
  await page.evaluate(async (pin) => {
    const salt = EvidenceCrypto.generateSaltBase64();
    await fetch("/api/evidence/salt", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ salt }) });
    const key = await EvidenceCrypto.deriveKey(pin, salt);
    const blob = await EvidenceCrypto.encryptJSON(key, { entry_date: "2026-09-01", text: "saved before the upgrade" });
    await fetch("/api/evidence/entries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(blob) });
  }, PIN);
  await page.goto(`${BASE}/log.html`);
  await waitFor(page, () => visible(page, "pin-unlock-view"));
  check("legacy+data: wrong PIN rejected", (await unlock(page, WRONG)) === "Incorrect PIN.");
  check("legacy+data: key-check not written by a wrong PIN", !(await keyCheck(page)));
  check("legacy+data: right PIN unlocks", (await unlock(page, PIN)) === "UNLOCKED");
  await waitFor(page, async () => (await page.$eval("#entries-list", (el) => el.textContent)).includes("saved before the upgrade"));
  check("legacy+data: old note still readable", (await page.$eval("#entries-list", (el) => el.textContent)).includes("saved before the upgrade"));
  check("legacy+data: key-check backfilled", !!(await keyCheck(page)));
}

await browser.close();
console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
process.exit(results.every(Boolean) ? 0 : 1);
