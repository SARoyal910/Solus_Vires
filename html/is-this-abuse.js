// Private self-check on /is-this-abuse.html. Deliberately stores nothing:
// no localStorage, no network. Ticks vanish when the page is left.
(function () {
  const form = document.getElementById("reflect-form");
  const result = document.getElementById("reflect-result");
  if (!form || !result) return;

  function update() {
    const checked = form.querySelectorAll("input:checked").length;
    if (checked === 0) {
      result.textContent = "";
    } else if (checked === 1) {
      result.textContent =
        "Even one of these, happening again and again, is worth talking about. A Hotline advocate can help you think it through: 1-800-799-7233, or text START to 88788.";
    } else {
      result.textContent =
        "You ticked " + checked + " of these. That is a pattern, and patterns like this are what abuse looks like. You deserve support. A Hotline advocate is there 24/7: 1-800-799-7233, or text START to 88788.";
    }
  }

  form.addEventListener("change", update);
  // Clear on the way out, including when the page is restored from the back/forward cache.
  window.addEventListener("pageshow", () => {
    form.reset();
    update();
  });
})();
