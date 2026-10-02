// Applies the plain view before the page paints (P2-E4), so someone who chose
// it never sees a flash of the normal colours. Load in <head>. The toggle and
// everything else live in shared.js; this only reads the saved choice.
try {
  if (window.localStorage.getItem("sv-theme") === "plain" || window.location.pathname.startsWith("/plain/")) {
    document.documentElement.classList.add("theme-plain");
  }
} catch (e) {
  // storage blocked: normal view
}
