(function () {
  "use strict";

  const signedOutView = document.getElementById("signed-out-view");
  const signedInView = document.getElementById("signed-in-view");

  async function api(path, options = {}) {
    const res = await fetch(path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (res.status === 401) {
      signedOutView.hidden = false;
      signedInView.hidden = true;
      throw new Error("not authenticated");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Request failed.");
    }
    return res.json();
  }

  function fmtDate(iso) {
    if (!iso) return "unknown";
    return new Date(iso).toLocaleString();
  }

  async function loadSchedule() {
    const schedule = await api("/api/checkin/schedule");
    const form = document.getElementById("schedule-form");
    form.interval_hours.value = String(schedule.interval_hours);
    form.grace_hours.value = String(schedule.grace_hours);
    form.active.checked = schedule.active;

    const card = document.getElementById("checkin-now-card");
    const deadlineText = document.getElementById("deadline-text");
    if (schedule.active) {
      card.hidden = false;
      if (schedule.overdue) {
        deadlineText.textContent = "You're overdue — your trusted contacts may have already been alerted.";
      } else {
        deadlineText.textContent = `Next check-in due by ${fmtDate(schedule.next_deadline_at)}.`;
      }
    } else {
      card.hidden = true;
    }
  }

  function contactCard(contact) {
    const card = document.createElement("article");
    card.className = "card";

    const title = document.createElement("h3");
    title.textContent = contact.nickname;
    card.appendChild(title);

    const email = document.createElement("p");
    email.textContent = contact.contact_email;
    card.appendChild(email);

    const statusLabels = {
      pending: "Invited — waiting on them",
      accepted: `Accepted · ${contact.subscribed_devices} device(s) enabled for push`,
      declined: "Declined",
      revoked: "Stopped by contact",
    };
    const statusP = document.createElement("p");
    statusP.className = "status";
    statusP.textContent = statusLabels[contact.status] || contact.status;
    card.appendChild(statusP);

    const actions = document.createElement("div");
    actions.className = "actions";

    if (contact.status === "pending" || contact.status === "declined") {
      const resendBtn = document.createElement("button");
      resendBtn.type = "button";
      resendBtn.className = "btn";
      resendBtn.textContent = "Resend invite";
      resendBtn.addEventListener("click", async () => {
        resendBtn.disabled = true;
        try {
          await api(`/api/checkin/contacts/${contact.id}/resend`, { method: "POST" });
          await loadContacts();
        } catch (e) {
          resendBtn.disabled = false;
        }
      });
      actions.appendChild(resendBtn);
    }

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn danger";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", async () => {
      await api(`/api/checkin/contacts/${contact.id}`, { method: "DELETE" });
      await loadContacts();
    });
    actions.appendChild(removeBtn);

    card.appendChild(actions);
    return card;
  }

  async function loadContacts() {
    const contacts = await api("/api/checkin/contacts");
    const list = document.getElementById("contacts-list");
    list.textContent = "";
    if (contacts.length === 0) {
      const empty = document.createElement("p");
      empty.style.color = "var(--muted)";
      empty.textContent = "No trusted contacts yet.";
      list.appendChild(empty);
      return;
    }
    contacts.forEach((c) => list.appendChild(contactCard(c)));
  }

  document.getElementById("schedule-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("schedule-status");
    status.textContent = "Saving...";
    const form = event.target;
    try {
      await api("/api/checkin/schedule", {
        method: "PUT",
        body: JSON.stringify({
          active: form.active.checked,
          interval_hours: Number(form.interval_hours.value),
          grace_hours: Number(form.grace_hours.value),
        }),
      });
      status.textContent = "Saved.";
      await loadSchedule();
    } catch (e) {
      status.textContent = "Unable to save right now.";
    }
  });

  document.getElementById("checkin-now-btn").addEventListener("click", async () => {
    const status = document.getElementById("checkin-status");
    status.textContent = "Checking in...";
    try {
      await api("/api/checkin/schedule/checkin", { method: "POST" });
      status.textContent = "Checked in.";
      await loadSchedule();
    } catch (e) {
      status.textContent = "Unable to check in right now.";
    }
  });

  document.getElementById("add-contact-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("add-contact-status");
    status.textContent = "Sending invite...";
    const form = event.target;
    try {
      await api("/api/checkin/contacts", {
        method: "POST",
        body: JSON.stringify({
          nickname: form.nickname.value,
          contact_email: form.contact_email.value,
        }),
      });
      form.reset();
      status.textContent = "Invite sent.";
      await loadContacts();
    } catch (e) {
      status.textContent = e.message || "Unable to send invite right now.";
    }
  });

  async function init() {
    try {
      await api("/api/auth/me");
    } catch (e) {
      return;
    }
    signedOutView.hidden = true;
    signedInView.hidden = false;
    await loadSchedule();
    await loadContacts();
  }

  init();
})();
