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
