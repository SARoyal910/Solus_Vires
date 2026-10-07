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
  // True until anything (profile, entry, plan) has been saved. While it is,
  // the no-recovery warning shows again and the first save waits for a tick
  // (P2-A10, user review Marisol #5).
  let vaultEmpty = true;

  const firstSaveWarning = document.getElementById("first-save-warning");
  const firstSaveAck = document.getElementById("first-save-ack");

  function showView(name) {
    for (const key in views) views[key].hidden = key !== name;
  }

  function scheduleAutoLock() {
    if (autoLockTimer) clearTimeout(autoLockTimer);
    autoLockTimer = setTimeout(lockNow, AUTO_LOCK_MS);
  }

  // Everything decrypted lives here while unlocked, and only here and in
  // the DOM; lockNow() empties both.
  const state = {
    profile: null,
    plan: null,
    entries: [], // { id, created_at, entry_date, text, unreadable }
    photos: new Map(), // id -> { id, entry_id, created_at, size, meta, bytes, url }
  };

  // Locking forgets the key and wipes every decrypted thing from the page,
  // so nothing readable is left in the DOM behind the PIN screen.
  function lockNow() {
    flushPendingDeletes(true);
    cryptoKey = null;
    pendingConfirmPin = null;
    if (autoLockTimer) clearTimeout(autoLockTimer);
    for (const photo of state.photos.values()) if (photo.url) URL.revokeObjectURL(photo.url);
    state.profile = null;
    state.plan = null;
    state.entries = [];
    state.photos = new Map();
    closeExport();
    document.getElementById("entries-list").textContent = "";
    document.getElementById("profile-form").reset();
    document.getElementById("plan-form").reset();
    document.getElementById("entry-form").reset();
    document.getElementById("plan-details").open = false;
    document.getElementById("entry-search").value = "";
    document.getElementById("search-status").textContent = "";
    document.getElementById("short-pin-notice").hidden = true;
    firstSaveWarning.hidden = true;
    for (const id of ["profile-status", "entry-status", "plan-status", "export-status"]) {
      document.getElementById(id).textContent = "";
    }
    showView("pinUnlock");
  }

  function setVaultEmpty(empty) {
    vaultEmpty = empty;
    firstSaveWarning.hidden = !empty;
    if (!empty) firstSaveAck.checked = false;
  }

  // Returns false (and says why) when this would be the first save and the
  // PIN warning hasn't been acknowledged yet.
  function readyForFirstSave(status) {
    if (!vaultEmpty || firstSaveAck.checked) return true;
    status.textContent = "Before saving, tick the box above to confirm you've written your PIN down.";
    firstSaveWarning.scrollIntoView({ block: "center" });
    firstSaveAck.focus();
    return false;
  }

  ["click", "keydown", "input"].forEach((evt) =>
    document.addEventListener(evt, () => {
      if (cryptoKey) scheduleAutoLock();
    })
  );

  // On Android, choosing a photo opens the gallery app and hides this tab.
  // While a picker is open, leave locking to the idle timer instead.
  let pickingFilesUntil = 0;
  document.addEventListener("click", (event) => {
    if (event.target.closest && event.target.closest("input[type=file], label.file-pick")) {
      pickingFilesUntil = Date.now() + 2 * 60 * 1000;
    }
  }, true);
  document.addEventListener("change", (event) => {
    if (event.target.type === "file") pickingFilesUntil = 0;
  }, true);

  let rekeyInProgress = false;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && cryptoKey && Date.now() > pickingFilesUntil && !rekeyInProgress) lockNow();
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

  // ---------- Loading and showing decrypted data ----------

  async function tryDecrypt(blob) {
    try {
      return await EvidenceCrypto.decryptJSON(cryptoKey, blob.ciphertext, blob.iv);
    } catch (e) {
      return null;
    }
  }

  async function loadProfile() {
    const profile = await (await api("/api/evidence/case-profile")).json();
    if (!profile) return;
    setVaultEmpty(false);
    const data = await tryDecrypt(profile);
    if (!data) return; // can't happen past the key-check; leave fields blank
    state.profile = data;
    const form = document.getElementById("profile-form");
    form.name.value = data.name || "";
    form.relationship.value = data.relationship || "";
    form.notes.value = data.notes || "";
  }

  // ---------- Safety plan (P2-E8) ----------

  function buildPlanForm() {
    const box = document.getElementById("plan-fields");
    if (box.childElementCount) return;
    for (const section of NotesExport.PLAN) {
      const fieldset = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = section.title;
      fieldset.append(legend);
      for (const item of section.checklist || []) {
        const label = document.createElement("label");
        label.className = "progress-check";
        const box2 = document.createElement("input");
        box2.type = "checkbox";
        box2.name = `check:${item.key}`;
        label.append(box2, " ", item.label);
        fieldset.append(label);
      }
      for (const field of section.fields || []) {
        const label = document.createElement("label");
        label.append(field.label);
        const input = document.createElement(field.short ? "input" : "textarea");
        if (field.short) input.type = "text";
        else input.rows = 3;
        input.name = `field:${field.key}`;
        input.autocomplete = "off";
        label.append(input);
        fieldset.append(label);
      }
      box.append(fieldset);
    }
  }

  function readPlanForm() {
    const plan = { version: 1, fields: {}, checklist: {} };
    for (const el of document.getElementById("plan-form").elements) {
      if (!el.name) continue;
      const [kind, key] = el.name.split(":");
      if (kind === "field") plan.fields[key] = el.value;
      if (kind === "check") plan.checklist[key] = el.checked;
    }
    return plan;
  }

  function fillPlanForm(plan) {
    for (const el of document.getElementById("plan-form").elements) {
      if (!el.name) continue;
      const [kind, key] = el.name.split(":");
      if (kind === "field") el.value = (plan.fields || {})[key] || "";
      if (kind === "check") el.checked = !!(plan.checklist || {})[key];
    }
  }

  async function loadPlan() {
    const res = await api("/api/evidence/safety-plan");
    const plan = res.ok ? await res.json() : null;
    if (!plan) return;
    setVaultEmpty(false);
    const data = await tryDecrypt(plan);
    if (!data) return;
    state.plan = data;
    fillPlanForm(data);
  }

  // ---------- Photos (P2-E7) ----------

  function photoError(e, name) {
    const code = e && e.code;
    if (code === "not-image") return `"${name}" isn't a photo or screenshot this page can read.`;
    if (code === "too-large") return `"${name}" is too large: over 40 MB, or it can't be made smaller than 5 MB.`;
    if (code === "metadata-remains") return `"${name}" still had hidden details after cleaning, so it wasn't saved.`;
    return `"${name}" couldn't be opened here. If it's an iPhone HEIC photo, try a screenshot of it, or share it as a JPEG.`;
  }

  // Cleans every file first, so a bad one stops the save before anything is written.
  async function cleanAll(files, status) {
    const cleaned = [];
    for (let i = 0; i < files.length; i++) {
      status.textContent = `Removing hidden details from photo ${i + 1} of ${files.length}…`;
      try {
        cleaned.push({ file: files[i], ...(await ImageClean.cleanImage(files[i])) });
      } catch (e) {
        throw new Error(photoError(e, files[i].name));
      }
    }
    return cleaned;
  }

  // Encrypts and uploads cleaned photos for one entry. Returns how many failed.
  async function uploadPhotos(entryId, cleaned, status) {
    let failed = 0;
    for (let i = 0; i < cleaned.length; i++) {
      const c = cleaned[i];
      status.textContent = `Encrypting and saving photo ${i + 1} of ${cleaned.length}…`;
      try {
        const meta = { name: c.file.name || "photo", type: c.type, width: c.width, height: c.height, taken: c.taken, size: c.bytes.length };
        const body = await EvidenceCrypto.encryptBytes(cryptoKey, c.bytes);
        const encMeta = await EvidenceCrypto.encryptJSON(cryptoKey, meta);
        const res = await api("/api/evidence/attachments", {
          method: "POST",
          body: JSON.stringify({ entry_id: entryId, ciphertext: body.ciphertext, iv: body.iv, meta_ciphertext: encMeta.ciphertext, meta_iv: encMeta.iv }),
        });
        if (!res.ok) throw new Error("not saved");
      } catch (e) {
        failed++;
      }
    }
    return failed;
  }

  async function loadPhotoList() {
    const res = await api("/api/evidence/attachments");
    if (!res.ok) return;
    for (const info of await res.json()) {
      const meta = await tryDecrypt({ ciphertext: info.meta_ciphertext, iv: info.meta_iv });
      state.photos.set(info.id, {
        id: info.id,
        entry_id: info.entry_id,
        iv: info.iv,
        created_at: info.created_at,
        size: info.size_bytes,
        meta: meta || { name: "Unreadable photo" },
        unreadable: !meta,
        bytes: null,
        url: "",
      });
    }
  }

  // Downloads and decrypts one photo's image (once).
  async function loadPhoto(photo) {
    if (photo.url || photo.unreadable) return photo;
    const data = await (await api(`/api/evidence/attachments/${photo.id}`)).json();
    photo.bytes = await EvidenceCrypto.decryptBytes(cryptoKey, data.ciphertext, data.iv);
    photo.url = URL.createObjectURL(new Blob([photo.bytes], { type: photo.meta.type || "image/jpeg" }));
    return photo;
  }

  function saveFile(name, blob) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  // ---------- Entries ----------

  async function loadEntries() {
    const raw = await (await api("/api/evidence/entries")).json();
    if (raw.length) setVaultEmpty(false);
    const entries = [];
    for (const entry of raw) {
      const data = await tryDecrypt(entry);
      entries.push({ id: entry.id, created_at: entry.created_at, entry_date: data ? data.entry_date : "", text: data ? data.text : "", unreadable: !data });
    }
    state.entries = entries;
    renderEntries();
  }

  function photosFor(entryId) {
    return [...state.photos.values()].filter((p) => p.entry_id === entryId);
  }

  function renderPhoto(photo, card) {
    const row = document.createElement("div");
    row.className = "photo-row";
    const label = document.createElement("p");
    label.className = "photo-label";
    const m = photo.meta;
    label.textContent = [m.name, m.taken ? `taken ${m.taken.replace("T", " ").slice(0, 16)}` : "", NotesExport.formatSize(photo.size)].filter(Boolean).join(" · ");
    row.append(label);
    const buttons = document.createElement("div");
    buttons.className = "photo-actions";
    const show = document.createElement("button");
    show.type = "button";
    show.className = "btn small";
    show.textContent = "Show";
    show.disabled = photo.unreadable;
    show.addEventListener("click", async () => {
      show.disabled = true;
      show.textContent = "Opening…";
      try {
        await loadPhoto(photo);
        const img = document.createElement("img");
        img.className = "photo-preview";
        img.src = photo.url;
        img.alt = m.name;
        row.append(img);
        show.remove();
        const save = document.createElement("button");
        save.type = "button";
        save.className = "btn small";
        save.textContent = "Save a copy";
        save.addEventListener("click", () => saveFile(m.name || "photo.jpg", new Blob([photo.bytes], { type: m.type })));
        buttons.prepend(save);
      } catch (e) {
        show.textContent = "Couldn't open";
      }
    });
    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn small";
    del.textContent = "Delete photo";
    del.addEventListener("click", async () => {
      const res = await api(`/api/evidence/attachments/${photo.id}`, { method: "DELETE" });
      if (!res.ok) return;
      if (photo.url) URL.revokeObjectURL(photo.url);
      state.photos.delete(photo.id);
      renderEntries();
    });
    buttons.append(show, del);
    row.append(buttons);
    card.append(row);
  }

  function renderEntries() {
    const list = document.getElementById("entries-list");
    list.textContent = "";
    for (const entry of state.entries) {
      const card = document.createElement("article");
      card.className = "card entry-card";
      card.dataset.id = entry.id;
      const title = document.createElement("h3");
      title.textContent = entry.unreadable ? "Unable to decrypt" : entry.entry_date ? NotesExport.longDate(entry.entry_date) : "Undated";
      const body = document.createElement("p");
      body.className = "entry-text";
      body.textContent = entry.unreadable ? "This entry could not be read with the current PIN." : entry.text;
      card.append(title, body);
      for (const photo of photosFor(entry.id)) renderPhoto(photo, card);

      const actions = document.createElement("div");
      actions.className = "photo-actions";
      if (!entry.unreadable) {
        const pick = document.createElement("label");
        pick.className = "btn small file-pick";
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.multiple = true;
        input.className = "visually-hidden";
        pick.append("Add photos", input);
        input.addEventListener("change", async () => {
          const status = card.querySelector(".status") || card.appendChild(Object.assign(document.createElement("p"), { className: "status" }));
          const files = [...input.files];
          input.value = "";
          if (!files.length) return;
          try {
            const cleaned = await cleanAll(files, status);
            const failed = await uploadPhotos(entry.id, cleaned, status);
            await reloadPhotos();
            const fresh = document.querySelector(`.entry-card[data-id="${entry.id}"]`);
            if (fresh) {
              const note = document.createElement("p");
              note.className = "status";
              note.textContent = failed ? `${failed} photo(s) couldn't be saved. Try again.` : "Photos added.";
              fresh.append(note);
            }
          } catch (e) {
            status.textContent = e.message;
          }
        });
        actions.append(pick);
      }
      const del = document.createElement("button");
      del.type = "button";
      del.className = "btn danger small";
      del.textContent = "Delete";
      del.addEventListener("click", () => queueDelete(entry, card));
      actions.append(del);
      card.append(actions);
      list.append(card);
    }
    applySearch();
  }

  // ---------- Delete with undo (P3-J3) ----------
  // The entry disappears at once but the request waits 30 seconds, held only
  // in this page's memory. Undo puts it back; locking, leaving the page or the
  // timer running out sends the delete. The server never hears about an undo.

  const UNDO_SECONDS = 30;
  const pendingDeletes = new Map();

  function updateUndoBar() {
    const bar = document.getElementById("undo-bar");
    if (pendingDeletes.size === 0) {
      bar.hidden = true;
      return;
    }
    const soonest = Math.min(...[...pendingDeletes.values()].map((p) => p.deadline));
    const left = Math.max(0, Math.ceil((soonest - Date.now()) / 1000));
    const n = pendingDeletes.size;
    document.getElementById("undo-text").textContent = `${n === 1 ? "Entry" : n + " entries"} deleted. Undo within ${left}s.`;
    bar.hidden = false;
  }

  async function sendDelete(id, keepalive = false) {
    const pending = pendingDeletes.get(id);
    if (!pending) return;
    pendingDeletes.delete(id);
    clearTimeout(pending.timer);
    try {
      await fetch(`/api/evidence/entries/${id}`, { method: "DELETE", credentials: "include", keepalive });
    } catch (e) {
      // Offline: the entry stays on the server and comes back at next unlock.
    }
    for (const p of photosFor(id)) {
      if (p.url) URL.revokeObjectURL(p.url);
      state.photos.delete(p.id);
    }
    state.entries = state.entries.filter((e) => e.id !== id);
    pending.card.remove();
    updateUndoBar();
  }

  function queueDelete(entry, card) {
    card.hidden = true;
    const deadline = Date.now() + UNDO_SECONDS * 1000;
    const timer = setTimeout(() => sendDelete(entry.id), UNDO_SECONDS * 1000);
    pendingDeletes.set(entry.id, { card, deadline, timer });
    updateUndoBar();
  }

  function undoDeletes() {
    for (const [id, pending] of pendingDeletes) {
      clearTimeout(pending.timer);
      pending.card.hidden = false;
      pendingDeletes.delete(id);
    }
    updateUndoBar();
    applySearch();
  }

  function flushPendingDeletes(keepalive = false) {
    for (const id of [...pendingDeletes.keys()]) sendDelete(id, keepalive);
  }

  document.getElementById("undo-btn").addEventListener("click", undoDeletes);
  setInterval(() => { if (pendingDeletes.size) updateUndoBar(); }, 1000);
  window.addEventListener("pagehide", () => flushPendingDeletes(true));

  async function reloadPhotos() {
    const keep = state.photos;
    state.photos = new Map();
    await loadPhotoList();
    for (const [id, p] of state.photos) {
      const old = keep.get(id);
      if (old && old.url) Object.assign(p, { bytes: old.bytes, url: old.url });
    }
    for (const [id, old] of keep) if (!state.photos.has(id) && old.url) URL.revokeObjectURL(old.url);
    renderEntries();
  }

  // ---------- Search (client-side, over decrypted entries only) ----------

  function applySearch() {
    const query = document.getElementById("entry-search").value.trim().toLowerCase();
    const status = document.getElementById("search-status");
    let shown = 0;
    for (const card of document.querySelectorAll("#entries-list .entry-card")) {
      const entry = state.entries.find((e) => e.id === card.dataset.id);
      const haystack = entry
        ? [entry.text, entry.entry_date, NotesExport.longDate(entry.entry_date), ...photosFor(entry.id).map((p) => p.meta.name)].join(" ").toLowerCase()
        : "";
      const match = !query || haystack.includes(query);
      card.hidden = !match;
      if (match) shown++;
    }
    status.textContent = query ? `Showing ${shown} of ${state.entries.length} entries.` : "";
  }

  async function enterUnlocked(pinLength) {
    setVaultEmpty(true);
    buildPlanForm();
    document.getElementById("short-pin-notice").hidden = pinLength >= EvidenceCrypto.PIN_MIN_LENGTH;
    showView("unlocked");
    scheduleAutoLock();
    await loadProfile();
    await loadPlan();
    await loadPhotoList();
    await loadEntries();
  }

  // ---------- Export: print / PDF / text (P2-E3) ----------
  // Photos are downloaded (still encrypted) and decrypted first. After that,
  // building, printing, and saving the copy make no network requests at all.

  let exportModel = null;
  let exportAttestations = [];

  function closeExport() {
    document.getElementById("export-view").hidden = true;
    document.getElementById("vault-main").hidden = false;
    document.body.classList.remove("export-open");
    document.getElementById("export-doc").textContent = "";
    exportModel = null;
  }

  async function openExport() {
    const status = document.getElementById("export-status");
    const opener = document.getElementById("export-open-btn");
    opener.disabled = true;
    try {
      const photos = [...state.photos.values()].filter((p) => !p.url && !p.unreadable);
      for (let i = 0; i < photos.length; i++) {
        opener.textContent = `Preparing photos (${i + 1} of ${photos.length})…`;
        await loadPhoto(photos[i]).catch(() => {});
      }
      // Attestations and the key (P3-H1); both are harmless if the feature is off.
      let attestations = [];
      let attestationKey = null;
      try {
        attestations = await (await api("/api/evidence/attestations")).json();
        attestationKey = await (await api("/api/evidence/attestation-key")).json();
      } catch (e) {
        attestations = [];
      }
      exportAttestations = attestations;
      exportModel = NotesExport.buildModel({
        profile: state.profile,
        plan: state.plan,
        entries: state.entries.map((e) => ({
          ...e,
          photos: photosFor(e.id).map((p) => ({ ...p.meta, id: p.id, created_at: p.created_at, size: p.size, url: p.url })),
        })),
        exportedAt: new Date(),
        attestations,
        attestationKey,
      });
      const verifiable = !!exportModel.attestationKey && attestations.length > 0;
      document.getElementById("export-verify-btn").hidden = !verifiable;
      document.getElementById("export-verify-hint").hidden = !verifiable;
      NotesExport.renderInto(document.getElementById("export-doc"), exportModel);
      document.getElementById("vault-main").hidden = true;
      document.getElementById("export-view").hidden = false;
      document.body.classList.add("export-open");
      status.textContent = "";
      document.getElementById("export-title").scrollIntoView({ block: "start" });
    } finally {
      opener.disabled = false;
      opener.textContent = "Print or save a copy";
    }
  }

  // Deriving the key takes 600,000 PBKDF2 rounds: a second or more on older
  // phones. Show that something is happening so it doesn't look frozen.
  function setBusy(form, busy, label) {
    const button = form.querySelector("button[type=submit]");
    if (busy) {
      button.dataset.label = button.dataset.label || button.textContent;
      button.textContent = label;
    } else if (button.dataset.label) {
      button.textContent = button.dataset.label;
    }
    button.disabled = busy;
    form.setAttribute("aria-busy", String(busy));
  }

  // ---------- Change PIN (P3-J2) ----------
  // Everything is decrypted with the current key and re-encrypted with the new
  // one here, in the browser. Photos are staged one request at a time under a
  // change id; the final request carries the rest and the server swaps all of
  // it in one transaction, or refuses and leaves the old key in place.

  const changePinStrength = document.getElementById("change-pin-strength");
  document.querySelector("#change-pin-form input[name=new_pin]").addEventListener("input", (event) => {
    const value = event.target.value;
    if (!value) {
      changePinStrength.textContent = "";
      delete changePinStrength.dataset.level;
      return;
    }
    const result = EvidenceCrypto.pinStrength(value);
    changePinStrength.textContent = result.message;
    changePinStrength.dataset.level = result.level;
  });

  document.getElementById("change-pin-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const status = document.getElementById("change-pin-status");
    const current = form.current_pin.value;
    const next = form.new_pin.value;
    if (next !== form.new_pin_confirm.value) {
      status.textContent = "The new PINs don't match.";
      return;
    }
    if (next.length < EvidenceCrypto.PIN_MIN_LENGTH) {
      status.textContent = `The new PIN needs at least ${EvidenceCrypto.PIN_MIN_LENGTH} characters.`;
      return;
    }
    if (EvidenceCrypto.pinStrength(next).level === "weak") {
      status.textContent = "That new PIN is easy to guess. Try a few unrelated words.";
      return;
    }
    if (next === current) {
      status.textContent = "That's the same PIN.";
      return;
    }
    setBusy(form, true, "Checking…");
    rekeyInProgress = true;
    try {
      const saltData = await (await api("/api/evidence/salt")).json();
      const oldKey = await EvidenceCrypto.deriveKey(current, saltData.salt);
      if (!saltData.key_check || !(await EvidenceCrypto.keyMatchesCheck(oldKey, saltData.key_check))) {
        status.textContent = "That isn't your current PIN.";
        return;
      }
      const newSalt = EvidenceCrypto.generateSaltBase64();
      const newKey = await EvidenceCrypto.deriveKey(next, newSalt);
      const rekeyId = crypto.randomUUID();

      // Read everything fresh from the server, so nothing saved from another
      // device since this page loaded is left behind under the old key.
      status.textContent = "Reading your notes…";
      const [profile, plan, entries, photos] = await Promise.all([
        (await api("/api/evidence/case-profile")).json(),
        (await api("/api/evidence/safety-plan")).json(),
        (await api("/api/evidence/entries")).json(),
        (await api("/api/evidence/attachments")).json(),
      ]);

      // Every item must decrypt under the current key before anything is
      // sent; one unreadable item means stop, not "skip it".
      const body = { rekey_id: rekeyId, salt: newSalt, entries: [], attachments: [] };
      body.key_check = await EvidenceCrypto.makeKeyCheck(newKey);
      body.profile = profile ? await EvidenceCrypto.reencryptJSON(oldKey, newKey, profile) : null;
      body.plan = plan ? await EvidenceCrypto.reencryptJSON(oldKey, newKey, plan) : null;
      for (let i = 0; i < entries.length; i++) {
        setBusy(form, true, `Re-encrypting notes (${i + 1} of ${entries.length})…`);
        const blob = await EvidenceCrypto.reencryptJSON(oldKey, newKey, entries[i]);
        body.entries.push({ id: entries[i].id, ...blob });
      }
      for (let i = 0; i < photos.length; i++) {
        setBusy(form, true, `Re-encrypting photos (${i + 1} of ${photos.length})…`);
        const meta = await EvidenceCrypto.reencryptJSON(oldKey, newKey, { ciphertext: photos[i].meta_ciphertext, iv: photos[i].meta_iv });
        const data = await (await api(`/api/evidence/attachments/${photos[i].id}`)).json();
        const image = await EvidenceCrypto.reencryptBytes(oldKey, newKey, data);
        const staged = await api(`/api/evidence/attachments/${photos[i].id}/rekey`, {
          method: "POST",
          body: JSON.stringify({ rekey_id: rekeyId, ...image }),
        });
        if (!staged.ok) throw new Error("staging failed");
        body.attachments.push({ id: photos[i].id, meta_ciphertext: meta.ciphertext, meta_iv: meta.iv });
      }

      setBusy(form, true, "Saving…");
      const res = await api("/api/evidence/rekey", { method: "POST", body: JSON.stringify(body) });
      if (res.status === 409) {
        status.textContent = "Something changed while this ran, so nothing was changed. Try again.";
        return;
      }
      if (!res.ok) throw new Error("rekey failed");
      cryptoKey = newKey;
      form.reset();
      changePinStrength.textContent = "";
      document.getElementById("short-pin-notice").hidden = true;
      const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
      status.textContent = `Done. Your PIN is changed and everything (${plural(entries.length, "note")}, ${plural(photos.length, "photo")}) is saved under it. Write the new PIN down.`;
      scheduleAutoLock();
    } catch (e) {
      if (e && e.message === "not authenticated") return;
      status.textContent = e && e.name === "OperationError"
        ? "One of your notes couldn't be read with the current PIN, so nothing was changed."
        : "Couldn't change the PIN right now. Nothing was changed.";
    } finally {
      rekeyInProgress = false;
      setBusy(form, false);
    }
  });

  const pinStrengthHint = document.getElementById("pin-strength");
  document.querySelector("#pin-setup-form input[name=pin]").addEventListener("input", (event) => {
    const value = event.target.value;
    if (!value) {
      pinStrengthHint.textContent = "";
      delete pinStrengthHint.dataset.level;
      return;
    }
    const result = EvidenceCrypto.pinStrength(value);
    pinStrengthHint.textContent = result.message;
    pinStrengthHint.dataset.level = result.level;
  });

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
    status.textContent = "Setting up… this can take a few seconds.";
    setBusy(form, true, "Setting up…");
    const pinLength = form.pin.value.length;
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
      pinStrengthHint.textContent = "";
      status.textContent = "";
      await enterUnlocked(pinLength);
    } catch (e) {
      status.textContent = "Unable to set up your PIN right now.";
    } finally {
      setBusy(form, false);
    }
  });

  document.getElementById("pin-unlock-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("pin-unlock-status");
    const form = event.target;
    status.textContent = "Unlocking…";
    setBusy(form, true, "Unlocking…");
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
      await enterUnlocked(pin.length);
    } catch (e) {
      cryptoKey = null;
      status.textContent = "Unable to unlock right now.";
    } finally {
      setBusy(form, false);
    }
  });

  document.getElementById("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("profile-status");
    const form = event.target;
    if (!readyForFirstSave(status)) return;
    const profile = { name: form.name.value, relationship: form.relationship.value, notes: form.notes.value };
    const blob = await EvidenceCrypto.encryptJSON(cryptoKey, profile);
    try {
      const res = await api("/api/evidence/case-profile", { method: "PUT", body: JSON.stringify(blob) });
      if (!res.ok) throw new Error("not saved");
      state.profile = profile;
      setVaultEmpty(false);
      status.textContent = "Saved.";
    } catch (e) {
      status.textContent = "Unable to save right now.";
    }
  });

  document.getElementById("plan-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("plan-status");
    if (!readyForFirstSave(status)) return;
    const plan = readPlanForm();
    const blob = await EvidenceCrypto.encryptJSON(cryptoKey, plan);
    try {
      const res = await api("/api/evidence/safety-plan", { method: "PUT", body: JSON.stringify(blob) });
      if (!res.ok) throw new Error("not saved");
      state.plan = plan;
      setVaultEmpty(false);
      status.textContent = "Plan saved.";
    } catch (e) {
      status.textContent = "Unable to save your plan right now.";
    }
  });

  document.getElementById("entry-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("entry-status");
    const form = event.target;
    if (!readyForFirstSave(status)) return;
    const submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    try {
      let cleaned = [];
      try {
        cleaned = await cleanAll([...form.photos.files], status);
      } catch (e) {
        status.textContent = e.message + " Nothing was saved.";
        return;
      }
      status.textContent = "Saving…";
      const blob = await EvidenceCrypto.encryptJSON(cryptoKey, { entry_date: form.entry_date.value, text: form.text.value });
      let entryId;
      try {
        const res = await api("/api/evidence/entries", { method: "POST", body: JSON.stringify(blob) });
        if (!res.ok) throw new Error("not saved");
        entryId = (await res.json()).id;
      } catch (e) {
        status.textContent = "Unable to add this entry right now.";
        return;
      }
      setVaultEmpty(false);
      const failed = cleaned.length ? await uploadPhotos(entryId, cleaned, status) : 0;
      form.reset();
      await reloadPhotos();
      await loadEntries();
      status.textContent = failed
        ? `Entry added, but ${failed} photo${failed === 1 ? "" : "s"} couldn't be saved. You can add ${failed === 1 ? "it" : "them"} to the entry below.`
        : cleaned.length ? `Added, with ${cleaned.length} photo${cleaned.length === 1 ? "" : "s"}.` : "Added.";
    } finally {
      submit.disabled = false;
    }
  });

  document.getElementById("entry-search").addEventListener("input", applySearch);
  document.getElementById("lock-now-btn").addEventListener("click", lockNow);
  document.getElementById("export-open-btn").addEventListener("click", openExport);
  document.getElementById("export-close-btn").addEventListener("click", closeExport);
  document.getElementById("export-print-btn").addEventListener("click", () => window.print());
  document.getElementById("export-verify-btn").addEventListener("click", async () => {
    if (!exportModel || !exportModel.attestationKey) return;
    const status = document.getElementById("export-status");
    status.textContent = "Preparing the verification file…";
    try {
      // Ciphertext is re-read from the server so the file carries exactly
      // what was attested; the plaintext comes from this export.
      const [saltData, rawEntries, rawPhotos, rawProfile, rawPlan] = await Promise.all([
        (await api("/api/evidence/salt")).json(),
        (await api("/api/evidence/entries")).json(),
        (await api("/api/evidence/attachments")).json(),
        (await api("/api/evidence/case-profile")).json(),
        (await api("/api/evidence/safety-plan")).json(),
      ]);
      const rowsFor = (kind, id) => exportAttestations.filter((r) => r.kind === kind && r.item_id === id);
      const items = [];
      for (const e of rawEntries) {
        const shown = state.entries.find((x) => x.id === e.id);
        items.push({ kind: "entry", id: e.id, ciphertext: e.ciphertext, iv: e.iv,
          plaintext: shown && !shown.unreadable ? { entry_date: shown.entry_date, text: shown.text } : null,
          attestations: rowsFor("entry", e.id) });
      }
      for (const p of rawPhotos) {
        const data = await (await api(`/api/evidence/attachments/${p.id}`)).json();
        const known = state.photos.get(p.id);
        items.push({ kind: "attachment", id: p.id, ciphertext: data.ciphertext, iv: data.iv,
          plaintext: known && known.meta && !known.unreadable ? { name: known.meta.name, taken: known.meta.taken || null, width: known.meta.width, height: known.meta.height } : null,
          attestations: rowsFor("attachment", p.id) });
      }
      if (rawProfile) {
        const rows = exportAttestations.filter((r) => r.kind === "profile");
        items.push({ kind: "profile", id: rows.length ? rows[0].item_id : null, ciphertext: rawProfile.ciphertext, iv: rawProfile.iv, plaintext: state.profile, attestations: rows });
      }
      if (rawPlan) {
        const rows = exportAttestations.filter((r) => r.kind === "plan");
        items.push({ kind: "plan", id: rows.length ? rows[0].item_id : null, ciphertext: rawPlan.ciphertext, iv: rawPlan.iv, plaintext: state.plan, attestations: rows });
      }
      const file = NotesExport.buildVerificationFile({ exportedAt: exportModel.exportedAt, attestationKey: exportModel.attestationKey, salt: saltData.salt, items });
      const day = new Date().toISOString().slice(0, 10);
      saveFile(`notes-verification-${day}.json`, new Blob([JSON.stringify(file, null, 1)], { type: "application/json" }));
      status.textContent = "Verification file saved to your downloads. It contains your encrypted notes and the text of this export; treat it like the PDF.";
    } catch (e) {
      status.textContent = "Couldn't prepare the verification file right now.";
    }
  });

  document.getElementById("export-text-btn").addEventListener("click", () => {
    if (!exportModel) return;
    const day = new Date().toISOString().slice(0, 10);
    saveFile(`notes-${day}.txt`, new Blob([NotesExport.toText(exportModel)], { type: "text/plain;charset=utf-8" }));
    document.getElementById("export-status").textContent = "Text file saved to your downloads. It is not encrypted.";
  });

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
