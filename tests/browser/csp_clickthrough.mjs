// Clicks through every page under the real nginx Content-Security-Policy and
// fails on any CSP violation, uncaught page error, or a page served without
// the policy (P2-A4). Needs the nginx + api + db stack (see the CI "headers"
// job), not the uvicorn preview, because only nginx sends the header.
//   SV_NGINX_URL=https://127.0.0.1:8443 node tests/browser/csp_clickthrough.mjs
// Optional: SV_API_CONTAINER=<api container name> lets it mint a check-in
// invite token (docker exec) so the invite page's accept/decline flows run too.
// Throwaway accounts only; never point it at production.
import puppeteer from "puppeteer-core";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";

const BASE = process.env.SV_NGINX_URL || "https://127.0.0.1:8443";
const API_CONTAINER = process.env.SV_API_CONTAINER || "";
const HTML_DIR = new URL("../../html/", import.meta.url);
const PASSWORD = "pw-" + crypto.randomBytes(8).toString("hex");
const PIN = "pin-" + crypto.randomBytes(8).toString("hex");

const pages = [
  ...readdirSync(HTML_DIR).filter((f) => f.endsWith(".html")).map((f) => "/" + f),
  "/es/",
  ...readdirSync(new URL("es/", HTML_DIR)).filter((f) => f.endsWith(".html")).map((f) => "/es/" + f),
  ...(process.env.SV_EXTRA_PATHS || "").split(/\s+/).filter(Boolean),
];

const problems = [];
let visits = 0;
let inCanary = false;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  acceptInsecureCerts: true,
  args: ["--ignore-certificate-errors", ...(process.env.CI ? ["--no-sandbox"] : [])],
});

async function newPage(ctx) {
  const page = await ctx.newPage();
  await page.evaluateOnNewDocument(() => {
    window.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      window.__csp.push(`${e.violatedDirective} blocked ${e.blockedURI || "inline"} (${e.sourceFile}:${e.lineNumber})`);
    });
    // Quick Exit must not actually leave during the test.
    window.__opened = [];
    window.open = (...args) => { window.__opened.push(args); return null; };
    window.print = () => { window.__printed = (window.__printed || 0) + 1; };
  });
  page.on("console", (msg) => {
    if (!inCanary && /Content.Security.Policy/i.test(msg.text())) problems.push(`${page.url()} console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => problems.push(`${page.url()} page error: ${err.message}`));
  return page;
}

async function collect(page, label) {
  const found = await page.evaluate(() => window.__csp.splice(0)).catch(() => []);
  for (const v of found) problems.push(`${label}: ${v}`);
}

async function go(page, path, label) {
  const res = await page.goto(BASE + path, { waitUntil: "load" });
  visits++;
  const csp = res && res.headers()["content-security-policy"];
  if (!csp) problems.push(`${label} ${path}: served without Content-Security-Policy`);
  await sleep(300);
}

const click = (page, sel) => page.evaluate((s) => { const el = document.querySelector(s); if (el) el.click(); return !!el; }, sel);

async function exercise(page, path) {
  // Scroll the whole page so every scroll-reveal transition runs.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 30)); }
  });
  if (path === "/recovery.html") {
    for (const id of ["#breath-start", "#breath-stop", "#grounding-start", "#grounding-next", "#grounding-next", "#affirmation-next", "#progress-reset"]) {
      await click(page, id);
      await sleep(150);
    }
    await page.evaluate(() => { const box = document.querySelector("input[data-progress]"); if (box) box.click(); });
  }
  if (path === "/is-this-abuse.html" || path === "/es/es-abuso.html") {
    await page.evaluate(() => {
      const form = document.getElementById("reflect-form");
      if (!form) return;
      form.querySelectorAll("input[type=checkbox]").forEach((b, i) => { if (i % 2 === 0) b.click(); });
    });
  }
  await page.evaluate(() => {
    document.querySelectorAll("[data-state-finder] select").forEach((s) => {
      if (s.options.length > 1) { s.selectedIndex = 1; s.dispatchEvent(new Event("change", { bubbles: true })); }
    });
  });
  // Offline copy panel (Emergency/Resources, if present): save, then remove.
  if (await click(page, "#offline-save-btn")) {
    await sleep(2500);
    await click(page, "#offline-remove-btn");
    await sleep(800);
  }
  // Contact form (if the page shows it): fill and send.
  await page.evaluate(() => {
    const form = document.getElementById("contact-form");
    if (!form || form.closest("[hidden]")) return;
    form.querySelectorAll("input[type=text], input[type=email], input:not([type]), textarea").forEach((el) => {
      el.value = el.type === "email" ? "test@example.com" : "click-through test";
    });
    form.requestSubmit();
  });
  await sleep(600);
  // Quick Exit (window.open and print are stubbed above; replace is not, so
  // only check the button is wired, without pressing it).
  await sleep(200);
}

async function mobileMenu(page, path, label) {
  await page.setViewport({ width: 390, height: 844 });
  await go(page, path, label);
  await click(page, "#nav-toggle");
  await sleep(200);
  await click(page, "#theme-toggle");
  await sleep(200);
  await click(page, "#theme-toggle");
  await click(page, "#nav-toggle");
  await collect(page, `${label} ${path} (390px, menu)`);
  await page.setViewport({ width: 1280, height: 900 });
}

async function walkAll(page, label) {
  for (const path of pages) {
    await go(page, path, label);
    try {
      await exercise(page, path);
    } catch (e) {
      problems.push(`${label} ${path}: ${e.message} (url now ${page.url()})`);
    }
    await collect(page, `${label} ${path}`);
    await mobileMenu(page, path, label);
  }
}

// 0. Canary: an inline script and a style attribute must be reported, or a
// green run would mean nothing.
{
  const ctx = await browser.createBrowserContext();
  const page = await newPage(ctx);
  inCanary = true;
  await go(page, "/", "canary");
  await page.evaluate(() => {
    const s = document.createElement("script");
    s.textContent = "window.__ran = true";
    document.head.appendChild(s);
    document.body.setAttribute("style", "color: red");
  });
  await sleep(300);
  const caught = await page.evaluate(() => window.__csp.splice(0));
  const ran = await page.evaluate(() => window.__ran === true);
  if (caught.length < 2 || ran) problems.push(`canary: policy did not block injected inline script/style (${caught.length} reported, ran=${ran})`);
  else console.log(`canary ok: ${caught.length} injected violations blocked and reported`);
  await ctx.close();
  inCanary = false;
}

// 1. Logged out.
{
  const ctx = await browser.createBrowserContext();
  const page = await newPage(ctx);
  await page.setViewport({ width: 1280, height: 900 });
  await walkAll(page, "logged out");
  await ctx.close();
}

// 2. Logged in, with notes unlocked, check-ins set up, and an invite answered.
{
  const ctx = await browser.createBrowserContext();
  const page = await newPage(ctx);
  await page.setViewport({ width: 1280, height: 900 });
  await go(page, "/account.html", "setup");
  const user = "csp_" + crypto.randomBytes(4).toString("hex");
  // Through the real forms, so account.js runs under the policy. Sign in is
  // the default view; the create-account form is behind a link.
  await click(page, "#show-register-link");
  await page.waitForFunction(() => !document.getElementById("register-card").hidden);
  await page.evaluate((u, p) => {
    const f = document.getElementById("register-form");
    f.username.value = u; f.password.value = p; f.requestSubmit();
  }, user, PASSWORD);
  await page.waitForFunction(() => !document.getElementById("recovery-codes-card").hidden, { timeout: 15000 });
  await click(page, "#codes-saved-check");
  await click(page, "#codes-continue-btn");
  await page.evaluate((u, p) => {
    const f = document.getElementById("login-form");
    f.username.value = u; f.password.value = p; f.requestSubmit();
  }, user, PASSWORD);
  await page.waitForFunction(() => !document.getElementById("logged-in-view").hidden, { timeout: 15000 });
  await collect(page, "account register/login");

  await walkAll(page, "logged in");

  // Notes: set a PIN, write, search, export, lock, unlock.
  await go(page, "/log.html", "notes");
  await page.waitForFunction(() => !document.getElementById("pin-setup-view").hidden, { timeout: 15000 });
  await page.evaluate((pin) => {
    const f = document.getElementById("pin-setup-form");
    f.pin.value = pin; f.pin_confirm.value = pin;
    f.pin.dispatchEvent(new Event("input", { bubbles: true }));
    f.requestSubmit();
  }, PIN);
  await page.waitForFunction(() => !document.getElementById("unlocked-view").hidden, { timeout: 30000 });
  await page.evaluate(() => {
    const ack = document.getElementById("first-save-ack");
    if (ack && !ack.checked) ack.click();
    const f = document.getElementById("entry-form");
    f.entry_date.value = "2026-09-30"; f.text.value = "csp click-through entry"; f.requestSubmit();
  });
  await page.waitForFunction(() => document.getElementById("entries-list").textContent.includes("csp click-through entry"), { timeout: 15000 });
  await page.evaluate(() => {
    const s = document.getElementById("entry-search");
    if (s) { s.value = "click"; s.dispatchEvent(new Event("input", { bubbles: true })); }
  });
  await click(page, "#export-open-btn");
  await page.waitForFunction(() => !document.getElementById("export-view").hidden, { timeout: 15000 });
  for (const id of ["#export-print-btn", "#export-text-btn", "#export-close-btn"]) { await click(page, id); await sleep(400); }
  await page.evaluate(() => {
    const f = document.getElementById("plan-form");
    if (!f) return;
    document.getElementById("plan-details").open = true;
    const field = f.querySelector("textarea, input[type=text]");
    if (field) field.value = "csp plan";
    f.requestSubmit();
  });
  await sleep(800);
  await click(page, "#lock-now-btn");
  await page.evaluate((pin) => {
    const f = document.getElementById("pin-unlock-form"); f.pin.value = pin; f.requestSubmit();
  }, PIN);
  await page.waitForFunction(() => !document.getElementById("unlocked-view").hidden, { timeout: 30000 });
  await sleep(500);
  await collect(page, "notes flow");

  // Check-ins: schedule, check in, add a contact.
  await go(page, "/checkin.html", "checkin");
  await page.waitForFunction(() => !document.getElementById("signed-in-view").hidden, { timeout: 15000 });
  await page.evaluate(() => {
    const f = document.getElementById("add-contact-form");
    f.querySelector("[name=nickname]").value = "Jo";
    f.querySelector("[name=contact_email]").value = "jo@example.com";
    f.requestSubmit();
  });
  await sleep(1000);
  await page.evaluate(() => {
    const f = document.getElementById("schedule-form");
    const active = document.getElementById("schedule-active");
    if (!active.checked) active.click();
    f.requestSubmit();
  });
  await sleep(1000);
  await click(page, "#checkin-now-btn");
  await sleep(800);
  await collect(page, "checkin flow");

  if (API_CONTAINER) {
    const contactId = await page.evaluate(async () => (await (await fetch("/api/checkin/contacts")).json())[0].id);
    const token = execFileSync("docker", ["exec", "-i", API_CONTAINER, "python", "-c",
      "import sys, uuid; from app.services.checkin import make_contact_token; print(make_contact_token(uuid.UUID(sys.argv[1])))", contactId],
    ).toString().trim();
    const invitePage = await newPage(await browser.createBrowserContext());
    const path = `/checkin-invite.html?token=${encodeURIComponent(token)}`;
    await go(invitePage, path, "invite");
    await invitePage.waitForFunction(() => !document.getElementById("invite-state").hidden, { timeout: 15000 });
    await click(invitePage, "#accept-btn");
    await invitePage.waitForFunction(() => !document.getElementById("accepted-state").hidden, { timeout: 15000 });
    await click(invitePage, "#enable-push-btn");
    await sleep(800);
    await click(invitePage, "#stop-btn");
    await sleep(800);
    await collect(invitePage, "invite flow");
  } else {
    console.log("note: SV_API_CONTAINER not set, invite accept/decline flow skipped");
  }

  await click(page, "#nav-toggle");
  await go(page, "/account.html", "logout");
  await page.waitForFunction(() => !document.getElementById("logged-in-view").hidden, { timeout: 15000 });
  await click(page, "#logout-btn");
  await sleep(800);
  await collect(page, "logout");
  await ctx.close();
}

// 3. JavaScript disabled: pages still render and nothing is blocked.
{
  const ctx = await browser.createBrowserContext();
  const page = await newPage(ctx);
  await page.setJavaScriptEnabled(false);
  for (const path of pages) {
    const res = await page.goto(BASE + path, { waitUntil: "load" });
    visits++;
    if (!res.headers()["content-security-policy"]) problems.push(`no-js ${path}: served without Content-Security-Policy`);
  }
  await ctx.close();
}

await browser.close();
for (const p of problems) console.log("FAIL  " + p);
console.log(`\n${visits} page loads across ${pages.length} pages, ${problems.length} problem(s)`);
process.exit(problems.length ? 1 : 0);
