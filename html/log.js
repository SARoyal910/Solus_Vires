// Private notes page. Everything here runs in the browser: the PIN, the key,
// and decrypted notes never leave it. Kept out of the HTML so the
// Content-Security-Policy can forbid inline script (P2-A4).
(() => {
  const AUTO_LOCK_MS = 4 * 60 * 1000;

  const views = {
    signedOut: document.getElementById("signed-out-view"),
    pinSetup: document.getElementById("pin-setup-view"),
    pinUnlock: document.getElementById("pin-unlock-view"),
    unlocked: document.getElementById("unlocked-view"),
  };

  let cryptoKey = null;
  let autoLockTimer = null;

  function showView(name) {
    for (const key in views) views[key].hidden = key !== name;
  }

  function scheduleAutoLock() {
    if (autoLockTimer) clearTimeout(autoLockTimer);
    autoLockTimer = setTimeout(lockNow, AUTO_LOCK_MS);
  }

  function lockNow() {
    cryptoKey = null;
    pendingConfirmPin = null;
    if (autoLockTimer) clearTimeout(autoLockTimer);
    showView("pinUnlock");
  }

  ["click", "keydown", "input"].forEach((evt) =>
    document.addEventListener(evt, () => {
      if (cryptoKey) scheduleAutoLock();
    })
  );

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && cryptoKey) lockNow();
  });

  async function api(path, options = {}) {
    const res = await fetch(path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (res.status === 401) {
      showView("signedOut");
      throw new Error("not authenticated");
    }
    return res;
  }

  async function loadEntries() {
    const res = await api("/api/evidence/entries");
    const entries = await res.json();
    const list = document.getElementById("entries-list");
    list.textContent = "";
    for (const entry of entries) {
      let data;
      try {
        data = await EvidenceCrypto.decryptJSON(cryptoKey, entry.ciphertext, entry.iv);
      } catch (e) {
        data = null;
      }
      const card = document.createElement("article");
      card.className = "card";
      const title = document.createElement("h3");
      title.textContent = data ? data.entry_date || "Undated" : "Unable to decrypt";
      const body = document.createElement("p");
      body.textContent = data ? data.text : "This entry could not be read with the current PIN.";
      const del = document.createElement("button");
      del.type = "button";
      del.className = "btn danger";
      del.textContent = "Delete";
      del.addEventListener("click", async () => {
        await api(`/api/evidence/entries/${entry.id}`, { method: "DELETE" });
        await loadEntries();
      });
      card.appendChild(title);
      card.appendChild(body);
      card.appendChild(del);
      list.appendChild(card);
    }
  }

  async function loadProfile() {
    const res = await api("/api/evidence/case-profile");
    const profile = await res.json();
    if (!profile) return;
    try {
      const data = await EvidenceCrypto.decryptJSON(cryptoKey, profile.ciphertext, profile.iv);
      const form = document.getElementById("profile-form");
      form.name.value = data.name || "";
      form.relationship.value = data.relationship || "";
      form.notes.value = data.notes || "";
    } catch (e) {
      // Wrong PIN relative to previously saved profile; leave fields blank.
    }
  }

  async function enterUnlocked() {
    showView("unlocked");
    scheduleAutoLock();
    await loadProfile();
    await loadEntries();
  }

  // Zero-knowledge encryption means the server can never confirm a PIN is
  // correct; the browser has to. Accounts set up with the current page have a
  // key-check (a constant encrypted under the PIN) and that alone decides.
  //
  // Older accounts don't. For those, try decrypting something already saved,
  // then store a key-check so it's never guessed again. If nothing is saved
  // there's nothing to test against, so ask for the PIN twice instead: letting
  // a single unverified PIN through is what split people's notes in two
  // (engineering review H3).
  let pendingConfirmPin = null;

  async function tryDecryptSavedData(key) {
    const profile = await (await api("/api/evidence/case-profile")).json();
    const entries = profile ? [] : await (await api("/api/evidence/entries")).json();
    const sample = profile || entries[0];
    if (!sample) return null;
    try {
      await EvidenceCrypto.decryptJSON(key, sample.ciphertext, sample.iv);
      return true;
    } catch (e) {
      return false;
    }
  }

  async function storeKeyCheck(key) {
    const blob = await EvidenceCrypto.makeKeyCheck(key);
    const res = await api("/api/evidence/key-check", { method: "PUT", body: JSON.stringify(blob) });
    if (res.ok) return true;
    if (res.status === 409) {
      // Another tab stored one first; it is now the authority.
      const data = await (await api("/api/evidence/salt")).json();
      return data.key_check ? EvidenceCrypto.keyMatchesCheck(key, data.key_check) : false;
    }
    throw new Error("could not store key check");
  }

  // Returns "ok", "wrong", "confirm" (legacy empty vault, ask again), or "mismatch".
  async function checkPin(pin, key, saltData) {
    if (saltData.key_check) {
      return (await EvidenceCrypto.keyMatchesCheck(key, saltData.key_check)) ? "ok" : "wrong";
    }

    const decrypted = await tryDecryptSavedData(key);
    if (decrypted === false) return "wrong";
    if (decrypted === true) {
      await storeKeyCheck(key).catch(() => {}); // verified already; backfill is best-effort
      return "ok";
    }

    if (pendingConfirmPin === null) {
      pendingConfirmPin = pin;
      return "confirm";
    }
    const matches = pendingConfirmPin === pin;
    pendingConfirmPin = null;
    if (!matches) return "mismatch";
    return (await storeKeyCheck(key)) ? "ok" : "wrong";
  }

  document.getElementById("pin-setup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("pin-setup-status");
    const form = event.target;
    if (form.pin.value !== form.pin_confirm.value) {
      status.textContent = "PINs do not match.";
      return;
    }
    if (form.pin.value.length < 12) {
      status.textContent = "PIN is too short.";
      return;
    }
    const salt = EvidenceCrypto.generateSaltBase64();
    status.textContent = "Setting up...";
    try {
      const key = await EvidenceCrypto.deriveKey(form.pin.value, salt);
      const key_check = await EvidenceCrypto.makeKeyCheck(key);
      const res = await api("/api/evidence/salt", {
        method: "PUT",
        body: JSON.stringify({ salt, key_check }),
      });
      if (res.status === 409) {
        // A PIN was already set (e.g. in another tab). Never write notes under
        // a salt the server didn't keep; send them to the unlock screen.
        form.reset();
        status.textContent = "";
        showView("pinUnlock");
        return;
      }
      if (!res.ok) throw new Error("salt not saved");
      cryptoKey = key;
      form.reset();
      status.textContent = "";
      await enterUnlocked();
    } catch (e) {
      status.textContent = "Unable to set up your PIN right now.";
    }
  });

  document.getElementById("pin-unlock-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("pin-unlock-status");
    const form = event.target;
    status.textContent = "Unlocking...";
    try {
      const res = await api("/api/evidence/salt");
      const data = await res.json();
      if (!data.salt) {
        status.textContent = "No PIN set up yet.";
        return;
      }
      const pin = form.pin.value;
      const key = await EvidenceCrypto.deriveKey(pin, data.salt);
      const result = await checkPin(pin, key, data);
      form.reset();
      if (result === "confirm") {
        status.textContent = "Enter the same PIN once more to confirm it.";
        return;
      }
      if (result === "mismatch") {
        status.textContent = "Those didn't match. Enter your PIN again.";
        return;
      }
      if (result !== "ok") {
        status.textContent = "Incorrect PIN.";
        return;
      }
      cryptoKey = key;
      status.textContent = "";
      await enterUnlocked();
    } catch (e) {
      cryptoKey = null;
      status.textContent = "Unable to unlock right now.";
    }
  });

  document.getElementById("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("profile-status");
    const form = event.target;
    const blob = await EvidenceCrypto.encryptJSON(cryptoKey, {
      name: form.name.value,
      relationship: form.relationship.value,
      notes: form.notes.value,
    });
    try {
      await api("/api/evidence/case-profile", { method: "PUT", body: JSON.stringify(blob) });
      status.textContent = "Saved.";
    } catch (e) {
      status.textContent = "Unable to save right now.";
    }
  });

  document.getElementById("entry-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("entry-status");
    const form = event.target;
    const blob = await EvidenceCrypto.encryptJSON(cryptoKey, {
      entry_date: form.entry_date.value,
      text: form.text.value,
    });
    try {
      await api("/api/evidence/entries", { method: "POST", body: JSON.stringify(blob) });
      form.reset();
      status.textContent = "Added.";
      await loadEntries();
    } catch (e) {
      status.textContent = "Unable to add this entry right now.";
    }
  });

  document.getElementById("lock-now-btn").addEventListener("click", lockNow);

  async function init() {
    try {
      await api("/api/auth/me");
    } catch (e) {
      return;
    }
    const res = await api("/api/evidence/salt");
    const data = await res.json();
    showView(data.salt ? "pinUnlock" : "pinSetup");
  }

  init();
})();
