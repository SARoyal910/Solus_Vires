// Service worker for solusvires.com. Two jobs, both opt-in:
//
// 1. Push notifications for trusted contacts (registered from
//    checkin-invite.js when a contact turns notifications on).
// 2. An offline copy of the crisis pages (P2-E9), saved ONLY when someone
//    presses "Save on this device" on Emergency or Resources (offline.js).
//    Nothing is cached until then, and "Remove" deletes it.
//
// Rules for the offline copy:
// - Only the public pages and files in OFFLINE_FILES are ever stored. Never
//   the private pages (account, log, checkin, checkin-invite) and never
//   /api/: they're not on the list, so they're never written to the cache.
// - Network first. Online, every request goes to the server (pages are
//   served Cache-Control: no-cache), and the saved copy is refreshed from the
//   answer, so nobody sees an old phone number while they have a connection.
//   The saved copy is used only when the network fails.
// - Offline, any other page falls back to the saved Emergency page (or the
//   Spanish one under /es/), so an installed app never opens to an error.

const CACHE = "offline-v1";
const OFFLINE_FILES = [
  "/emergency.html",
  "/resources.html",
  "/es/emergencia.html",
  "/es/recursos.html",
  "/shared.css",
  "/shared.js",
  "/offline.js",
  "/local-help.js",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
];
const OFFLINE_SET = new Set(OFFLINE_FILES);

// ---------- 1. Push (trusted contacts) ----------

self.addEventListener("push", (event) => {
  let payload = { title: "Solus Vires check-in alert", body: "", url: "/" };
  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch (e) {
      payload.body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      data: { url: payload.url },
      requireInteraction: true,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url === targetUrl && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

// ---------- 2. Offline copy (opt-in) ----------

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  // Drop caches from older versions of this file; keep the current one.
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("offline-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function savedAt() {
  if (!(await caches.has(CACHE))) return null;
  const cache = await caches.open(CACHE);
  const res = await cache.match("/emergency.html");
  return res ? res.headers.get("date") || "" : null;
}

async function saveAll() {
  const cache = await caches.open(CACHE);
  try {
    await Promise.all(
      OFFLINE_FILES.map(async (path) => {
        const res = await fetch(path, { cache: "no-cache" });
        if (!res.ok) throw new Error(path + " " + res.status);
        await cache.put(path, res);
      })
    );
  } catch (e) {
    await caches.delete(CACHE); // all or nothing: never leave half a copy
    throw e;
  }
}

self.addEventListener("message", (event) => {
  const port = event.ports && event.ports[0];
  const reply = (msg) => port && port.postMessage(msg);
  const type = event.data && event.data.type;
  let work;
  if (type === "offline-status") {
    work = savedAt().then((at) => reply({ ok: true, saved: at !== null, at }));
  } else if (type === "offline-save") {
    work = saveAll().then(savedAt).then(
      (at) => reply({ ok: true, saved: true, at }),
      () => reply({ ok: false, saved: false })
    );
  } else if (type === "offline-remove") {
    work = caches.delete(CACHE).then(() => reply({ ok: true, saved: false }));
  } else {
    return;
  }
  event.waitUntil(work);
});

function offlineFallback(url) {
  const page = url.pathname.startsWith("/es/") ? "/es/emergencia.html" : "/emergency.html";
  return caches.match(page, { cacheName: CACHE }).then((res) => res || Response.error());
}

async function networkFirst(request, url) {
  const listed = OFFLINE_SET.has(url.pathname);
  try {
    // Listed pages always revalidate with the server (a cheap 304 when
    // unchanged), whatever the browser's HTTP cache thinks is fresh.
    const res = await (listed ? fetch(url.pathname + url.search, { cache: "no-cache", credentials: "same-origin" }) : fetch(request));
    // Refresh the saved copy, but only if the person chose to keep one.
    if (listed && res.ok && (await caches.has(CACHE))) {
      const cache = await caches.open(CACHE);
      await cache.put(url.pathname, res.clone());
    }
    return res;
  } catch (e) {
    if (listed) {
      const saved = await caches.match(url.pathname, { cacheName: CACHE });
      if (saved) return saved;
    }
    if (request.mode === "navigate") return offlineFallback(url);
    throw e;
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  // Everything else is left to the browser untouched: no respondWith at all.
  if (!OFFLINE_SET.has(url.pathname) && request.mode !== "navigate") return;
  event.respondWith(networkFirst(request, url));
});
