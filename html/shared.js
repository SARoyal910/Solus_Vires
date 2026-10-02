function quickExit() {
  window.location.replace("https://www.weather.com/");
}

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
  const wide = window.matchMedia("(min-width: 921px)");
  wide.addEventListener("change", (event) => {
    if (event.matches) {
      setMenuOpen(false);
    }
  });
}

// Scroll-reveal: progressive enhancement only. Without this script (or with
// JS disabled), .card/.section-head elements render fully visible via their
// normal CSS - the shared.css hidden/transition rules only apply once
// .reveal-ready is present on <body>, which only this script adds.
if ("IntersectionObserver" in window) {
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
