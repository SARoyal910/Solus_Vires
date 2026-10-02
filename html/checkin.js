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

  let alertsSent = 0;

  async function loadSchedule() {
    const schedule = await api("/api/checkin/schedule");
    const form = document.getElementById("schedule-form");
    form.interval_hours.value = String(schedule.interval_hours);
    form.grace_hours.value = String(schedule.grace_hours);
    form.active.checked = schedule.active;

    alertsSent = schedule.alerts_sent || 0;
    const card = document.getElementById("checkin-now-card");
    const deadlineText = document.getElementById("deadline-text");
    if (schedule.active) {
      card.hidden = false;
      if (alertsSent > 0) {
        deadlineText.textContent =
          alertsSent === 1
            ? "Your trusted contacts have been sent an alert. Check in to stop the alerts; they'll be told you checked in."
            : `Your trusted contacts have been sent ${alertsSent} alerts. Check in to stop the alerts; they'll be told you checked in.`;
      } else if (schedule.overdue) {
        deadlineText.textContent = "You're overdue. If you don't check in, your trusted contacts will be alerted soon.";
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

    const devices = contact.subscribed_devices === 1 ? "1 device" : `${contact.subscribed_devices} devices`;
    const statusLabels = {
      pending: "Invited — waiting on them",
      accepted: `Accepted · email, plus push on ${devices}`,
      declined: "Declined",
      revoked: "They stopped these alerts. You can invite them again; nothing reaches them unless they accept.",
    };
    const statusP = document.createElement("p");
    statusP.className = "status";
    statusP.textContent = statusLabels[contact.status] || contact.status;
    card.appendChild(statusP);

    if (contact.status === "accepted" && contact.subscribed_devices > 0) {
      const pushP = document.createElement("p");
      pushP.textContent = contact.push_last_confirmed_at
        ? `Push last accepted for delivery: ${fmtDate(contact.push_last_confirmed_at)}. (Accepted by the push service, which isn't proof they saw it.)`
        : "No push has been sent to them yet.";
      card.appendChild(pushP);
    }

    if (contact.push_lost_at) {
      const warn = document.createElement("p");
      warn.className = "notice";
      warn.textContent =
        `Push notifications stopped working on their device (noticed ${fmtDate(contact.push_lost_at)}). ` +
        "They'll still get alerts by email. To get push back, they can open their invite link again on that device and turn notifications on.";
      card.appendChild(warn);
    }

    const actions = document.createElement("div");
    actions.className = "actions";

    const actionStatus = document.createElement("p");
    actionStatus.className = "status";
    actionStatus.setAttribute("aria-live", "polite");

    if (["pending", "declined", "revoked"].includes(contact.status)) {
      const resendBtn = document.createElement("button");
      resendBtn.type = "button";
      resendBtn.className = "btn";
      resendBtn.textContent = contact.status === "revoked" ? "Invite again" : "Resend invite";
      resendBtn.addEventListener("click", async () => {
        resendBtn.disabled = true;
        actionStatus.textContent = "Sending invite...";
        try {
          await api(`/api/checkin/contacts/${contact.id}/resend`, { method: "POST" });
          await loadContacts();
        } catch (e) {
          resendBtn.disabled = false;
          actionStatus.textContent = e.message || "Unable to send the invite right now.";
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
    card.appendChild(actionStatus);
    return card;
  }

  async function loadContacts() {
    const contacts = await api("/api/checkin/contacts");
    const list = document.getElementById("contacts-list");
    list.textContent = "";
    if (contacts.length === 0) {
      const empty = document.createElement("p");
      empty.className = "status";
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
      await loadHistory();
    } catch (e) {
      status.textContent = "Unable to save right now.";
    }
  });

  document.getElementById("checkin-now-btn").addEventListener("click", async () => {
    const status = document.getElementById("checkin-status");
    status.textContent = "Checking in...";
    try {
      const hadAlerts = alertsSent > 0;
      await api("/api/checkin/schedule/checkin", { method: "POST" });
      status.textContent = hadAlerts
        ? "Checked in. The contacts who were alerted are being told the alerts have stopped."
        : "Checked in.";
      await loadSchedule();
      await loadHistory();
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

  function historyLine(entry) {
    const when = fmtDate(entry.created_at);
    const people = entry.contacts_notified === 1 ? "1 contact" : `${entry.contacts_notified} contacts`;
    const channels = `${entry.emails_sent} email${entry.emails_sent === 1 ? "" : "s"}, ${entry.pushes_sent} push${entry.pushes_sent === 1 ? "" : "es"} sent` +
      (entry.pushes_failed ? `, ${entry.pushes_failed} push${entry.pushes_failed === 1 ? "" : "es"} failed` : "");
    if (entry.kind === "alert") {
      const label = entry.alert_number > 1 ? `Alert ${entry.alert_number}` : "Alert";
      return `${when}: ${label} sent to ${people} (${channels}).`;
    }
    if (entry.kind === "turned_off") {
      return `${when}: You turned check-ins off; ${people} told the alerts stopped (${channels}).`;
    }
    return `${when}: You checked in; ${people} told the alerts stopped (${channels}).`;
  }

  async function loadHistory() {
    const entries = await api("/api/checkin/alerts");
    const list = document.getElementById("alert-history");
    list.textContent = "";
    entries.forEach((entry) => {
      const li = document.createElement("li");
      li.textContent = historyLine(entry);
      list.appendChild(li);
    });
    document.getElementById("alert-history-empty").hidden = entries.length > 0;
    document.getElementById("alert-history-actions").hidden = entries.length === 0;
  }

  document.getElementById("clear-history-btn").addEventListener("click", async () => {
    const status = document.getElementById("alert-history-status");
    try {
      await api("/api/checkin/alerts", { method: "DELETE" });
      status.textContent = "History cleared.";
      await loadHistory();
    } catch (e) {
      status.textContent = "Unable to clear history right now.";
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
    await loadHistory();
  }

  init();
})();
