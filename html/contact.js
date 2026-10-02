(function () {
  "use strict";

  // The form only appears when the server says messages really reach an
  // inbox. Otherwise (or without JS) the page keeps its where-to-get-help
  // content and says plainly that a contact address is being set up.
  const off = document.getElementById("contact-off");
  const intro = document.getElementById("contact-intro");
  const card = document.getElementById("contact-form-card");
  const form = document.getElementById("contact-form");
  const statusEl = document.getElementById("contact-status");
  const sent = document.getElementById("contact-sent");
  const sentText = document.getElementById("contact-sent-text");

  function windowText(days) {
    return days === 1 ? "within a day" : `within ${days} days`;
  }

  function showForm(responseDays) {
    document.getElementById("response-window").textContent = windowText(responseDays);
    off.hidden = true;
    intro.hidden = false;
    card.hidden = false;
  }

  async function init() {
    try {
      const res = await fetch("/api/contact/status", { credentials: "same-origin" });
      if (!res.ok) return;
      const info = await res.json();
      if (info.enabled) showForm(info.response_days);
    } catch (e) {
      // Leave the static "being set up" text in place.
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = form.message.value.trim();
    if (!message) {
      statusEl.textContent = "Write a message first.";
      form.message.focus();
      return;
    }
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    statusEl.textContent = "Sending...";
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          safe_name: form.safe_name.value,
          safe_contact: form.safe_contact.value,
          message,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok && body.ok) {
        form.reset();
        document.getElementById("contact-form-wrap").hidden = true;
        sentText.textContent = body.message;
        sent.hidden = false;
        return;
      }
      statusEl.textContent =
        typeof body.detail === "string"
          ? body.detail
          : "Your message could not be sent. If you need support now, call 1-800-799-7233 or text START to 88788.";
    } catch (e) {
      statusEl.textContent =
        "Your message could not be sent. If you need support now, call 1-800-799-7233 or text START to 88788.";
    } finally {
      button.disabled = false;
    }
  });

  init();
})();
