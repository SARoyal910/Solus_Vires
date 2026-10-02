// Quick Exit v2, the Esc hint, neutral titles, and plain view (P2-E1, P2-E2,
// P2-E4) in headless Chrome against a local preview. No accounts are made.
//   SV_BASE_URL=http://127.0.0.1:8120 node tests/browser/site_ui.mjs
// With SV_NGINX_URL (the nginx stack, see csp_clickthrough.mjs) it also checks
// the no-JavaScript /plain/ pages nginx serves.
// Never touches the outside world: requests to the neutral sites Quick Exit
// opens are answered locally by the test.
import puppeteer from "puppeteer-core";

const BASE = process.env.SV_BASE_URL || "http://127.0.0.1:8099";
const NGINX = process.env.SV_NGINX_URL || "";
const results = [];
const check = (name, ok, extra = "") => { results.push(ok); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  (" + extra + ")" : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  acceptInsecureCerts: true,
  args: ["--ignore-certificate-errors"],
});

// A page whose window.open is recorded (or made to throw, like a popup
// blocker), and whose requests to anything but the site are answered locally.
async function exitPage({ openThrows = false } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  const opened = [];
  const outside = [];
  await page.exposeFunction("__recordOpen", (args) => opened.push(args));
  await page.evaluateOnNewDocument((throws) => {
    window.open = (...args) => {
      window.__recordOpen(args);
      if (throws) throw new Error("blocked");
      return null;
    };
  }, openThrows);
  await page.setRequestInterception(true);
  page.on("request", (req) => {
    if (req.url().startsWith(BASE) || !/^https?:/.test(req.url())) return req.continue();
    outside.push({ url: req.url(), referer: req.headers().referer || req.headers().Referer || "" });
    req.respond({ status: 200, contentType: "text/html", body: "<title>neutral</title>neutral" });
  });
  return { ctx, page, opened, outside };
}

// --- P2-E1 Quick Exit ---
{
  const { ctx, page, opened, outside } = await exitPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto(`${BASE}/safety.html`, { waitUntil: "load" });
  const historyBefore = await page.evaluate(() => history.length);
  await Promise.all([page.waitForNavigation({ waitUntil: "load" }), page.evaluate(() => document.getElementById("quick-exit-btn").click())]);
  check("button: opens a neutral site in a new tab", opened.length === 1 && opened[0][0] === "https://www.weather.com/" && opened[0][1] === "_blank");
  check("button: the new tab gets no opener or referrer", opened.length === 1 && /noopener/.test(opened[0][2]) && /noreferrer/.test(opened[0][2]));
  check("button: this tab is replaced by a neutral site", page.url() === "https://www.google.com/");
  check("button: replaced, not pushed (Back doesn't return here)", (await page.evaluate(() => history.length)) === historyBefore);
  check("button: the neutral site isn't told where the visitor came from", outside.length > 0 && outside.every((r) => r.referer === ""), JSON.stringify(outside.map((r) => r.referer)));
  await ctx.close();
}
{
  const { ctx, page, opened } = await exitPage({ openThrows: true });
  await page.goto(`${BASE}/index.html`, { waitUntil: "load" });
  await Promise.all([page.waitForNavigation({ waitUntil: "load" }), page.evaluate(() => document.getElementById("quick-exit-btn").click())]);
  check("popup blocked: the page is still replaced", opened.length === 1 && page.url() === "https://www.google.com/");
  await ctx.close();
}
{
  const { ctx, page } = await exitPage();
  await page.goto(`${BASE}/resources.html`, { waitUntil: "load" });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "load" }),
    (async () => { await page.keyboard.press("Escape"); await sleep(100); await page.keyboard.press("Escape"); })(),
  ]);
  check("Esc pressed twice leaves the site", page.url() === "https://www.google.com/");
  await ctx.close();
}
{
  const { ctx, page } = await exitPage();
  await page.goto(`${BASE}/resources.html`, { waitUntil: "load" });
  await page.keyboard.press("Escape");
  await sleep(900);
  await page.keyboard.press("Escape");
  await sleep(500);
  check("two slow, separate Esc presses do not leave", page.url() === `${BASE}/resources.html`);
  await ctx.close();
}

// The hint, and that it never costs header space on phones.
{
  const page = await browser.newPage();
  for (const [lang, path, word] of [["en", "/index.html", "Esc twice"], ["es", "/es/", "Esc dos veces"]]) {
    await page.setViewport({ width: 1280, height: 800 });
    await page.goto(BASE + path, { waitUntil: "load" });
    const wide = await page.evaluate(() => {
      const h = document.getElementById("exit-hint");
      return { shown: !!h && h.getBoundingClientRect().width > 0, text: h ? h.textContent : "", header: document.querySelector("body > header").getBoundingClientRect().height };
    });
    check(`${lang} 1280px: "Press Esc twice" hint visible beside Quick Exit`, wide.shown && wide.text.includes(word), wide.text);
    check(`${lang} 1280px: header stays one row`, wide.header < 70, `${wide.header}px`);
    for (const w of [360, 390]) {
      await page.setViewport({ width: w, height: 800 });
      await page.goto(BASE + path, { waitUntil: "load" });
      const closed = await page.evaluate(() => ({
        header: document.querySelector("body > header").getBoundingClientRect().height,
        hintShown: document.getElementById("exit-hint").getBoundingClientRect().width > 0,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
      }));
      await page.evaluate(() => document.getElementById("nav-toggle").click());
      await sleep(100);
      const open = await page.evaluate(() => {
        const note = document.querySelector("header nav .menu-note");
        const toggle = document.getElementById("theme-toggle");
        return {
          header: document.querySelector("body > header").getBoundingClientRect().height,
          note: note && note.getBoundingClientRect().height > 0 ? note.textContent : "",
          toggle: !!toggle && toggle.getBoundingClientRect().height > 0,
        };
      });
      check(`${lang} ${w}px: header one row, no sideways scroll, hint not in the header`, closed.header < 70 && !closed.overflow && !closed.hintShown, `${closed.header}px`);
      check(`${lang} ${w}px: menu open keeps the header one row and shows the Esc note and plain-view switch`, open.header < 70 && open.note.includes("Esc") && open.toggle);
    }
  }
  await page.close();
}

// --- P2-E2 neutral titles ---
{
  const page = await browser.newPage();
  for (const [path, title] of [["/log.html", "Notes"], ["/checkin.html", "Reminders"], ["/account.html", "Account"]]) {
    await page.goto(BASE + path, { waitUntil: "load" });
    check(`${path} tab title is "${title}"`, (await page.title()) === title, await page.title());
  }
  await page.close();
}

// --- P2-E4 plain view ---
{
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto(`${BASE}/safety.html`, { waitUntil: "load" });
  const before = await page.evaluate(() => ({ plain: document.documentElement.classList.contains("theme-plain"), title: document.title }));
  check("plain view is off by default", !before.plain);
  await page.evaluate(() => document.querySelector("footer a.theme-link").click());
  const on = await page.evaluate(() => ({
    plain: document.documentElement.classList.contains("theme-plain"),
    title: document.title,
    stored: localStorage.getItem("sv-theme"),
    bg: getComputedStyle(document.body).backgroundColor,
    url: location.pathname,
    link: document.querySelector("footer a.theme-link").textContent,
  }));
  check("footer switch turns plain view on in place", on.plain && on.url === "/safety.html" && on.link === "Normal view");
  check("plain view: light background", on.bg === "rgb(246, 246, 244)", on.bg);
  check("plain view: neutral tab title", on.title === "Notes", on.title);
  check("plain view: remembered in localStorage only", on.stored === "plain" && (await page.cookies()).length === 0);
  for (const path of ["/safety.html", "/index.html", "/es/"]) {
    await page.goto(BASE + path, { waitUntil: "load" });
    const s = await page.evaluate(() => ({
      plain: document.documentElement.classList.contains("theme-plain"),
      title: document.title,
      anims: [...document.querySelectorAll("*")].filter((el) => getComputedStyle(el).animationName !== "none" || getComputedStyle(el, "::after").animationName !== "none").length,
      glow: getComputedStyle(document.querySelector(".quick-exit")).boxShadow,
      reveal: document.body.classList.contains("reveal-ready"),
    }));
    check(`plain view survives navigation to ${path}, with no animation, glow, or scroll reveal`, s.plain && s.anims === 0 && s.glow === "none" && !s.reveal, JSON.stringify(s));
  }
  check("Spanish pages get a Spanish neutral title", (await page.title()) === "Notas");
  await page.setViewport({ width: 390, height: 800 });
  await page.goto(`${BASE}/index.html`, { waitUntil: "load" });
  await page.evaluate(() => { document.getElementById("nav-toggle").click(); document.getElementById("theme-toggle").click(); });
  const off = await page.evaluate(() => ({ plain: document.documentElement.classList.contains("theme-plain"), title: document.title, stored: localStorage.getItem("sv-theme"), pressed: document.getElementById("theme-toggle").getAttribute("aria-pressed") }));
  check("menu switch turns it back off, restoring the real title", !off.plain && off.title === "Solus Vires" && off.stored === "default" && off.pressed === "false", JSON.stringify(off));
  await ctx.close();
}
{
  // Blocked storage (some private modes throw): pages still work, switch works for the page.
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(window, "localStorage", { get() { throw new Error("SecurityError"); } });
  });
  await page.goto(`${BASE}/safety.html`, { waitUntil: "load" });
  await page.evaluate(() => document.querySelector("footer a.theme-link").click());
  check("storage blocked: no errors, and the switch still works on this page", errors.length === 0 && (await page.evaluate(() => document.documentElement.classList.contains("theme-plain"))), errors.join("; "));
  await ctx.close();
}
{
  // Reduced motion: no scroll reveal even in the normal colours.
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
  await page.goto(`${BASE}/safety.html`, { waitUntil: "load" });
  const r = await page.evaluate(() => ({ reveal: document.body.classList.contains("reveal-ready"), plain: document.documentElement.classList.contains("theme-plain") }));
  check("prefers-reduced-motion: no scroll reveal, and the colours stay the visitor's choice", !r.reveal && !r.plain);
  await ctx.close();
}

// --- No JavaScript: nginx's /plain/ copy ---
if (NGINX) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setJavaScriptEnabled(false);
  await page.goto(`${NGINX}/safety.html`, { waitUntil: "load" });
  const link = await page.evaluate(() => { const a = document.querySelector("footer a.theme-link"); return a ? [a.textContent, a.getAttribute("href")] : null; });
  check("no JS: every page's footer links to its plain copy", !!link && link[0] === "Plain view" && link[1] === "/plain/safety.html", JSON.stringify(link));
  await page.goto(`${NGINX}/plain/safety.html`, { waitUntil: "load" });
  const p = await page.evaluate(() => ({
    plain: document.documentElement.classList.contains("theme-plain"),
    title: document.title,
    bg: getComputedStyle(document.body).backgroundColor,
    offsite: [...document.querySelectorAll("a[href^='/']")].filter((a) => !a.getAttribute("href").startsWith("/plain/") && !a.classList.contains("theme-link")).length,
    back: document.querySelector("footer a.theme-link").getAttribute("href"),
  }));
  check("no JS: /plain/ page is plain, light, and titled Notes", p.plain && p.title === "Notes" && p.bg === "rgb(246, 246, 244)", JSON.stringify(p));
  check("no JS: every site link stays inside /plain/", p.offsite === 0);
  check("no JS: the footer link goes back to the normal page", p.back === "/safety.html");
  await page.goto(`${NGINX}/plain/es/`, { waitUntil: "load" });
  check("no JS: Spanish plain page is titled Notas", (await page.title()) === "Notas");
  const res = await page.goto(`${NGINX}/plain/log.html`, { waitUntil: "load" });
  check("no JS: /plain/ is never cached (it includes the private pages)", res.headers()["cache-control"] === "no-store");
  await ctx.close();
} else {
  console.log("note: SV_NGINX_URL not set, no-JS /plain/ checks skipped");
}

await browser.close();
console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
process.exit(results.every(Boolean) ? 0 : 1);
