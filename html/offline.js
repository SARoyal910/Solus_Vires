// "Save on this device": the opt-in offline copy of Emergency and Resources
// (P2-E9). Loaded only on those pages and their Spanish versions.
//
// Nothing is stored and no service worker is registered until the person
// presses Save, because a saved copy is one more trace of this site on a
// device someone else may check (docs/THREAT_MODEL.md, A1). Remove deletes
// it again. The worker itself is html/sw.js.
(function () {
  const panel = document.getElementById("offline-panel");
  if (!panel || !("serviceWorker" in navigator) || !("caches" in window)) return;

  const es = (document.documentElement.lang || "").toLowerCase().startsWith("es");
  const t = es
    ? {
        saving: "Guardando…",
        saved: (d) => "Guardado en este dispositivo" + (d ? " el " + d : "") + ".",
        notSaved: "No está guardado en este dispositivo.",
        failed: "No se pudo guardar. Revise su conexión e inténtelo de nuevo.",
        removed: "Se eliminó la copia guardada.",
        offline: (d) => "Sin conexión: esta es la copia guardada" + (d ? " el " + d : "") + ". Los números pueden haber cambiado desde entonces.",
      }
    : {
        saving: "Saving…",
        saved: (d) => "Saved on this device" + (d ? " on " + d : "") + ".",
        notSaved: "Not saved on this device.",
        failed: "Couldn't save. Check your connection and try again.",
        removed: "The saved copy has been removed.",
        offline: (d) => "You're offline: this is the copy saved" + (d ? " on " + d : "") + ". Numbers may have changed since then.",
      };

  const status = document.getElementById("offline-status");
  const offlineNote = document.getElementById("offline-note");
  const saveWrap = document.getElementById("offline-save");
  const removeWrap = document.getElementById("offline-remove");

  function day(httpDate) {
    const d = httpDate ? new Date(httpDate) : null;
    return d && !isNaN(d) ? d.toLocaleDateString(es ? "es" : "en", { year: "numeric", month: "long", day: "numeric" }) : "";
  }

  function ask(worker, type) {
    return new Promise((resolve) => {
      const channel = new MessageChannel();
      channel.port1.onmessage = (event) => resolve(event.data);
      worker.postMessage({ type }, [channel.port2]);
    });
  }

  function show(saved, at) {
    saveWrap.hidden = saved;
    removeWrap.hidden = !saved;
    status.textContent = saved ? t.saved(day(at)) : t.notSaved;
    if (offlineNote) {
      offlineNote.hidden = !(saved && !navigator.onLine);
      offlineNote.textContent = t.offline(day(at));
    }
  }

  async function activeWorker() {
    const reg = await navigator.serviceWorker.getRegistration("/");
    return reg && (reg.active || reg.waiting || reg.installing) ? reg : null;
  }

  panel.hidden = false;
  show(false, null);

  // Only asks an existing worker; never registers one on page load.
  activeWorker().then(async (reg) => {
    if (!reg) return;
    const ready = await navigator.serviceWorker.ready;
    const r = await ask(ready.active, "offline-status");
    show(r.saved, r.at);
  });

  document.getElementById("offline-save-btn").addEventListener("click", async () => {
    status.textContent = t.saving;
    try {
      await navigator.serviceWorker.register("/sw.js");
      const reg = await navigator.serviceWorker.ready;
      const r = await ask(reg.active, "offline-save");
      if (r.ok) show(true, r.at);
      else status.textContent = t.failed;
    } catch (e) {
      status.textContent = t.failed;
    }
  });

  document.getElementById("offline-remove-btn").addEventListener("click", async () => {
    const reg = await activeWorker();
    if (reg && reg.active) await ask(reg.active, "offline-remove");
    // Unregister too, unless this browser also gets check-in alerts through
    // the same worker (a trusted contact): removing it would stop those.
    if (reg) {
      const push = reg.pushManager ? await reg.pushManager.getSubscription().catch(() => null) : null;
      if (!push) await reg.unregister();
    }
    show(false, null);
    status.textContent = t.removed;
  });
})();
