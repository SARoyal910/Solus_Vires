// Quick Exit (P2-E1). Opens a neutral site in a new tab AND replaces this
// page, so the back button doesn't lead straight here. The replace never
// depends on the new tab: popup blockers can stop window.open (double-Esc
// doesn't count as a click, so browsers usually block it then), and the
// current page must leave either way. Neither site is told where the visitor
// came from. It can't erase history; the footer says so.
const QUICK_EXIT_NEW_TAB = "https://www.weather.com/";
const QUICK_EXIT_REPLACE = "https://www.google.com/";

function quickExit() {
  document.documentElement.classList.add("exiting"); // hide the page at once
  try {
    const noReferrer = document.createElement("meta");
    noReferrer.name = "referrer";
    noReferrer.content = "no-referrer";
    document.head.appendChild(noReferrer);
  } catch (e) {
    // still leave
  }
  try {
    window.open(QUICK_EXIT_NEW_TAB, "_blank", "noopener,noreferrer");
  } catch (e) {
    // blocked or unavailable: the replace below still happens
  }
  window.location.replace(QUICK_EXIT_REPLACE);
}

// Coming back with the Back button restores the page from cache; show it.
window.addEventListener("pageshow", () => document.documentElement.classList.remove("exiting"));

const quickExitButton = document.getElementById("quick-exit-btn");
if (quickExitButton) {
  quickExitButton.addEventListener("click", quickExit);
}

let lastEsc = 0;
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") {
    return;
  }

  const now = Date.now();
  if (now - lastEsc < 650) {
    quickExit();
  }
  lastEsc = now;
});

// Mobile menu: progressive enhancement. On small screens shared.css collapses
// the page links behind a menu button that only exists once this runs; with
// JS disabled the links stay visible as a single swipeable row instead.
const siteHeader = document.querySelector("body > header");
const primaryNav = siteHeader && siteHeader.querySelector("nav");
if (siteHeader && primaryNav) {
  const spanish = (document.documentElement.lang || "").toLowerCase().startsWith("es");
  const labels = spanish ? { open: "Abrir menú", close: "Cerrar menú" } : { open: "Open menu", close: "Close menu" };
  primaryNav.id = primaryNav.id || "primary-nav";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "nav-toggle";
  toggle.id = "nav-toggle";
  toggle.setAttribute("aria-controls", primaryNav.id);
  toggle.innerHTML =
    '<svg class="icon-menu" width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>' +
    '<svg class="icon-close" width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
  siteHeader.insertBefore(toggle, primaryNav);

  const setMenuOpen = (open) => {
    siteHeader.classList.toggle("menu-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? labels.close : labels.open);
  };
  setMenuOpen(false);
  document.body.classList.add("js-nav");

  toggle.addEventListener("click", () => {
    setMenuOpen(!siteHeader.classList.contains("menu-open"));
  });
  primaryNav.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      setMenuOpen(false);
    }
  });
  // pointerdown, not click: iOS Safari does not send click for taps on plain text.
  document.addEventListener("pointerdown", (event) => {
    if (siteHeader.classList.contains("menu-open") && !siteHeader.contains(event.target)) {
      setMenuOpen(false);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && siteHeader.classList.contains("menu-open")) {
      setMenuOpen(false);
      toggle.focus();
    }
  });
  const wide = window.matchMedia("(min-width: 1025px)");
  wide.addEventListener("change", (event) => {
    if (event.matches) {
      setMenuOpen(false);
    }
  });
}

// Esc hint and plain view (P2-E1, P2-E4). Neither adds a row to the header.
// On wide screens the hint sits beside Quick Exit and the plain-view switch is
// in the footer; on phones both are in the menu panel (and the footer).
const pageIsSpanish = (document.documentElement.lang || "").toLowerCase().startsWith("es");
const uiWords = pageIsSpanish
  ? { hint: "O pulsa <kbd>Esc</kbd> dos veces", menuNote: "Salida rápida (el botón rojo) sale de este sitio al instante. Con teclado: pulsa Esc dos veces.", plain: "Vista sencilla", normal: "Vista normal", title: "Notas" }
  : { hint: "Or press <kbd>Esc</kbd> twice", menuNote: "Quick Exit (the red button) leaves this site at once. On a keyboard, press Esc twice.", plain: "Plain view", normal: "Normal view", title: "Notes" };

if (siteHeader && quickExitButton) {
  const hint = document.createElement("p");
  hint.className = "exit-hint";
  hint.id = "exit-hint";
  hint.innerHTML = uiWords.hint;
  siteHeader.insertBefore(hint, quickExitButton);
  quickExitButton.setAttribute("aria-describedby", "exit-hint");
  quickExitButton.setAttribute("aria-keyshortcuts", "Escape");
  quickExitButton.title = hint.textContent;
}

// Plain view: light, grey, no glow or motion, and a neutral tab title. Off
// unless chosen; remembered on this device only (localStorage, never sent
// anywhere); undone with the same button. /theme.js applies it in <head> to
// avoid a flash of the normal colours. Without JavaScript, nginx serves the
// same pages under /plain/ with the class already set (nginx/snippets).
const THEME_KEY = "sv-theme";
const rootEl = document.documentElement;
const onPlainPath = window.location.pathname.startsWith("/plain/");
const titleTemplate = document.querySelector("head > template.sv-title");
const originalTitle = titleTemplate ? titleTemplate.innerHTML.trim() : document.title;

function readThemeChoice() {
  try {
    return window.localStorage.getItem(THEME_KEY);
  } catch (e) {
    return null;
  }
}

function storeThemeChoice(value) {
  try {
    window.localStorage.setItem(THEME_KEY, value);
  } catch (e) {
    // private mode etc.: the choice lasts for this page only
  }
}

const themeToggles = [];
function applyPlain(plain) {
  rootEl.classList.toggle("theme-plain", plain);
  document.title = plain ? uiWords.title : originalTitle;
  themeToggles.forEach((el) => el.setAttribute("aria-pressed", String(plain)));
  document.querySelectorAll("a.theme-link").forEach((link) => {
    link.textContent = plain ? uiWords.normal : uiWords.plain;
  });
}

function setPlain(plain) {
  storeThemeChoice(plain ? "plain" : "default");
  if (!plain && onPlainPath) {
    // The no-JS /plain/ copy has the class baked in; go to the normal page.
    window.location.href = window.location.pathname.replace(/^\/plain/, "") + window.location.search + window.location.hash;
    return;
  }
  applyPlain(plain);
}

if (onPlainPath) storeThemeChoice("plain");
applyPlain(onPlainPath || readThemeChoice() === "plain");

if (primaryNav) {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.id = "theme-toggle";
  toggle.className = "theme-toggle";
  toggle.textContent = uiWords.plain;
  toggle.setAttribute("aria-pressed", String(rootEl.classList.contains("theme-plain")));
  toggle.addEventListener("click", () => setPlain(!rootEl.classList.contains("theme-plain")));
  themeToggles.push(toggle);
  primaryNav.appendChild(toggle);

  const note = document.createElement("p");
  note.className = "menu-note";
  note.textContent = uiWords.menuNote;
  primaryNav.appendChild(note);
}

// The footer link nginx adds for no-JS visitors; with JS it switches in
// place. Where nginx isn't in front (local preview), add the same link here.
const footerLinks = document.querySelector("footer .footer-links");
if (footerLinks && !footerLinks.querySelector("a.theme-link")) {
  const link = document.createElement("a");
  link.className = "theme-link";
  link.href = "/plain" + window.location.pathname;
  footerLinks.prepend(link, " · ");
}
applyPlain(rootEl.classList.contains("theme-plain"));
document.querySelectorAll("a.theme-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    setPlain(!rootEl.classList.contains("theme-plain"));
  });
});

// Scroll-reveal: progressive enhancement only. Without this script (or with
// JS disabled), .card/.section-head elements render fully visible via their
// normal CSS - the shared.css hidden/transition rules only apply once
// .reveal-ready is present on <body>, which only this script adds.
// Skipped for plain view and for anyone whose device asks for reduced motion.
const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if ("IntersectionObserver" in window && !reduceMotion && !rootEl.classList.contains("theme-plain")) {
  document.body.classList.add("reveal-ready");

  const revealTargets = document.querySelectorAll(".card, .section-head");
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
  );

  revealTargets.forEach((el, index) => {
    el.style.transitionDelay = `${Math.min(index % 6, 5) * 60}ms`;
    observer.observe(el);
  });
}

// ---------- Installable app (P2-E9) ----------
// The site can be added to a home screen (manifest.json) and can keep an
// offline copy of the crisis pages, but only when someone chooses to. Chrome
// on Android otherwise pops up its own "Add to Home screen" banner by itself,
// which on a shared phone draws attention and could be tapped by mistake.
// This suppresses that banner; installing stays available from the browser's
// own menu. We never show an install prompt of our own. The service worker is
// registered only from checkin-invite.js (push) or offline.js (Save button),
// never here.
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
});
