// Account page: log in, register, recovery codes, password reset, log out,
// delete account. Kept out of the HTML so the Content-Security-Policy can
// forbid inline script (P2-A4).
(() => {
  const loggedOutView = document.getElementById("logged-out-view");
  const loggedInView = document.getElementById("logged-in-view");
  const recoveryCodesCard = document.getElementById("recovery-codes-card");

  function showLoggedOut() {
    recoveryCodesCard.hidden = true;
    loggedInView.hidden = true;
    loggedOutView.hidden = false;
  }

  function showLoggedIn(username) {
    recoveryCodesCard.hidden = true;
    loggedOutView.hidden = true;
    loggedInView.hidden = false;
    document.getElementById("me-username").textContent = username;
    loadSessions();
  }

  // Where you're signed in (P3-J1). The server sends device family and
  // times only; there is nothing here that could place a device.
  function describeWhen(iso) {
    const then = new Date(iso);
    const minutes = Math.round((Date.now() - then.getTime()) / 60000);
    if (minutes < 2) return "just now";
    if (minutes < 60) return minutes + " minutes ago";
    const hours = Math.round(minutes / 60);
    if (hours < 48) return hours + (hours === 1 ? " hour ago" : " hours ago");
    return Math.round(hours / 24) + " days ago";
  }

  async function loadSessions() {
    const list = document.getElementById("sessions-list");
    try {
      const res = await fetch("/api/auth/sessions", { credentials: "include" });
      if (!res.ok) return;
      const rows = await res.json();
      list.replaceChildren();
      for (const row of rows) {
        const li = document.createElement("li");
        const device = document.createElement("strong");
        device.textContent = row.device;
        li.appendChild(device);
        if (row.current) {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = "this device";
          li.appendChild(document.createTextNode(" "));
          li.appendChild(tag);
        }
        const when = document.createElement("span");
        when.className = "muted";
        when.textContent = " · last used " + describeWhen(row.last_seen_at) + ", signed in " + describeWhen(row.signed_in_at || row.created_at);
        li.appendChild(when);
        list.appendChild(li);
      }
      document.getElementById("logout-others-btn").disabled = rows.length < 2;
    } catch (e) {
      // Leave the list as it was; this card is informational.
    }
  }

  document.getElementById("logout-others-btn").addEventListener("click", async () => {
    const status = document.getElementById("sessions-status");
    status.textContent = "Signing out other devices...";
    const res = await fetch("/api/auth/logout-others", { method: "POST", credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      status.textContent = data.signed_out === 0
        ? "No other devices were signed in."
        : "Signed out " + data.signed_out + (data.signed_out === 1 ? " other device." : " other devices.") + " If you didn't recognise it, change your password too.";
      await loadSessions();
    } else {
      status.textContent = "Couldn't sign out other devices. Try again.";
    }
  });

  async function refreshSession() {
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        showLoggedIn(data.username);
        return;
      }
    } catch (e) {
      // fall through to logged-out view
    }
    showLoggedOut();
  }

  document.getElementById("show-recover-btn").addEventListener("click", () => {
    const card = document.getElementById("recover-card");
    card.hidden = !card.hidden;
  });

  // Sign in is the default; the create-account form is one link away.
  // Showing both at once read as two equal choices, when nearly everyone
  // arriving here already has an account.
  const loginCard = document.getElementById("login-card");
  const registerCard = document.getElementById("register-card");
  const showRegister = (on) => {
    registerCard.hidden = !on;
    loginCard.hidden = on;
    (on ? registerCard : loginCard).querySelector("input").focus();
  };
  document.getElementById("show-register-link").addEventListener("click", (event) => {
    event.preventDefault();
    showRegister(true);
  });
  document.getElementById("show-login-link").addEventListener("click", (event) => {
    event.preventDefault();
    showRegister(false);
  });
  if (location.hash === "#create-account") showRegister(true);

  document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("login-status");
    status.textContent = "Logging in...";
    const form = event.target;
    const body = JSON.stringify({
      username: form.username.value,
      password: form.password.value,
    });
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body,
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        form.reset();
        status.textContent = "";
        await refreshSession();
        return;
      }
      status.textContent = data.detail || "Unable to log in.";
    } catch (e) {
      status.textContent = "Unable to log in right now.";
    }
  });

  document.getElementById("register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("register-status");
    status.textContent = "Creating account...";
    const form = event.target;
    const body = JSON.stringify({
      username: form.username.value,
      password: form.password.value,
      invite_code: form.invite_code.value || null,
    });
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        form.reset();
        status.textContent = "";
        const list = document.getElementById("recovery-codes-list");
        list.textContent = "";
        for (const code of data.recovery_codes) {
          const div = document.createElement("div");
          div.textContent = code;
          list.appendChild(div);
        }
        loggedOutView.hidden = true;
        recoveryCodesCard.hidden = false;
        return;
      }
      status.textContent = data.detail || "Unable to create account.";
    } catch (e) {
      status.textContent = "Unable to create account right now.";
    }
  });

  document.getElementById("codes-saved-check").addEventListener("change", (event) => {
    document.getElementById("codes-continue-btn").disabled = !event.target.checked;
  });

  document.getElementById("codes-continue-btn").addEventListener("click", () => {
    showLoggedOut();
    // The new account signs in next, so land on the sign-in card.
    showRegister(false);
    document.getElementById("login-form").username.value = document.getElementById("register-form").username.value;
  });

  document.getElementById("recover-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("recover-status");
    status.textContent = "Resetting...";
    const form = event.target;
    const body = JSON.stringify({
      username: form.username.value,
      recovery_code: form.recovery_code.value,
      new_password: form.new_password.value,
    });
    try {
      const res = await fetch("/api/auth/recover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        form.reset();
        status.textContent = "Password reset. You can log in now.";
        return;
      }
      status.textContent = data.detail || "Unable to reset password.";
    } catch (e) {
      status.textContent = "Unable to reset password right now.";
    }
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    await refreshSession();
  });

  document.getElementById("logout-all-btn").addEventListener("click", async () => {
    await fetch("/api/auth/logout-all", { method: "POST", credentials: "include" });
    await refreshSession();
  });

  document.getElementById("show-delete-btn").addEventListener("click", (event) => {
    document.getElementById("delete-account-form").hidden = false;
    event.target.hidden = true;
  });

  document.getElementById("delete-account-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("delete-status");
    const form = event.target;
    status.textContent = "Deleting...";
    try {
      const res = await fetch("/api/auth/delete-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password: form.password.value }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        form.reset();
        await refreshSession();
        return;
      }
      status.textContent = data.detail || "Unable to delete your account.";
    } catch (e) {
      status.textContent = "Unable to delete your account right now.";
    }
  });

  refreshSession();
})();
