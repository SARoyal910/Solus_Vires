(function () {
  "use strict";

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawData = atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || "";

  const states = {
    loading: document.getElementById("loading-state"),
    invalid: document.getElementById("invalid-state"),
    invite: document.getElementById("invite-state"),
    accepted: document.getElementById("accepted-state"),
    declined: document.getElementById("declined-state"),
    revoked: document.getElementById("revoked-state"),
  };

  function showState(name) {
    for (const key in states) states[key].hidden = key !== name;
  }

  function isIOS() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  }

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Request failed.");
    }
    return res.json();
  }

  async function loadInvite() {
    if (!token) {
      showState("invalid");
      return;
    }
    try {
      const info = await api(`/api/checkin/invite/${encodeURIComponent(token)}`);
      render(info);
    } catch (e) {
      showState("invalid");
    }
  }

  function render(info) {
    if (info.status === "pending") {
      document.getElementById("username-pending").textContent = info.survivor_username;
      showState("invite");
    } else if (info.status === "accepted") {
      document.getElementById("username-accepted").textContent = info.survivor_username;
      document.getElementById("already-subscribed-note").hidden = info.subscribed_devices === 0;
      document.getElementById("ios-note").hidden = !(isIOS() && !isStandalone());
      showState("accepted");
    } else if (info.status === "declined") {
      document.getElementById("username-declined").textContent = info.survivor_username;
      showState("declined");
    } else if (info.status === "revoked") {
      document.getElementById("username-revoked").textContent = info.survivor_username;
      showState("revoked");
    } else {
      showState("invalid");
    }
  }

  document.getElementById("accept-btn")?.addEventListener("click", async () => {
    const status = document.getElementById("respond-status");
    status.textContent = "Accepting...";
    try {
      await api(`/api/checkin/invite/${encodeURIComponent(token)}/accept`, { method: "POST" });
      await loadInvite();
    } catch (e) {
      status.textContent = "Something went wrong. Try again.";
    }
  });

  document.getElementById("decline-btn")?.addEventListener("click", async () => {
    const status = document.getElementById("respond-status");
    status.textContent = "Declining...";
    try {
      await api(`/api/checkin/invite/${encodeURIComponent(token)}/decline`, { method: "POST" });
      await loadInvite();
    } catch (e) {
      status.textContent = "Something went wrong. Try again.";
    }
  });

  document.getElementById("reaccept-btn")?.addEventListener("click", async () => {
    try {
      await api(`/api/checkin/invite/${encodeURIComponent(token)}/accept`, { method: "POST" });
      await loadInvite();
    } catch (e) {
      // stay on current view; nothing user-actionable to show here
    }
  });

  document.getElementById("stop-btn")?.addEventListener("click", async () => {
    try {
      await api(`/api/checkin/invite/${encodeURIComponent(token)}/stop`, { method: "POST" });
      await loadInvite();
    } catch (e) {
      // stay on current view
    }
  });

  document.getElementById("enable-push-btn")?.addEventListener("click", async () => {
    const status = document.getElementById("push-status");

    if (isIOS() && !isStandalone()) {
      status.textContent = "Add this page to your Home Screen first, then open it from there.";
      return;
    }

    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      status.textContent = "Push notifications aren't supported in this browser. Email alerts will still work.";
      return;
    }

    status.textContent = "Requesting permission...";
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        status.textContent = "Permission not granted. Email alerts will still work.";
        return;
      }

      const { public_key } = await api("/api/checkin/vapid-public-key");
      if (!public_key) {
        status.textContent = "Push isn't configured on this server yet. Email alerts will still work.";
        return;
      }

      const registration = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });

      await api(`/api/checkin/invite/${encodeURIComponent(token)}/subscribe`, {
        method: "POST",
        body: JSON.stringify({
          endpoint: subscription.endpoint,
          keys: {
            p256dh: arrayBufferToBase64Url(subscription.getKey("p256dh")),
            auth: arrayBufferToBase64Url(subscription.getKey("auth")),
          },
        }),
      });

      status.textContent = "Push notifications enabled on this device.";
    } catch (e) {
      status.textContent = "Couldn't enable push notifications right now. Email alerts will still work.";
    }
  });

  function arrayBufferToBase64Url(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  loadInvite();
})();
