// Offline verifier for a notes export's verification file (P3-H2).
//
// Everything happens in this page: parse the file, rebuild each signed
// statement, check Ed25519 signatures with the key in the file, hash the
// ciphertext, and, with the PIN, decrypt and compare. No request is made
// unless the person presses the one button that fetches the site's current
// key for comparison. tests/web/verify.test.mjs runs this under Node.
(function () {
  "use strict";

  const enc = new TextEncoder();
  const dec = new TextDecoder();

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function hex(buf) {
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // The API returns times with a trailing Z; the server signed Python's
  // isoformat(), which writes +00:00. Same instant, same digits.
  function signedTime(iso) {
    return String(iso).replace(/Z$/, "+00:00");
  }

  function statement(kind, itemId, sha256, attestedAt) {
    return `solusvires-attest-v1|${kind}|${itemId}|${sha256}|${signedTime(attestedAt)}`;
  }

  async function importKey(publicKeyB64) {
    return crypto.subtle.importKey("raw", b64ToBytes(publicKeyB64), { name: "Ed25519" }, false, ["verify"]);
  }

  async function verifySignature(key, kind, itemId, row) {
    try {
      return await crypto.subtle.verify({ name: "Ed25519" }, key, b64ToBytes(row.signature), enc.encode(statement(kind, itemId, row.ciphertext_sha256, row.attested_at)));
    } catch (e) {
      return false;
    }
  }

  async function sha256Hex(bytes) {
    return hex(await crypto.subtle.digest("SHA-256", bytes));
  }

  // Notes hash the base64 text as stored; photos hash the decoded bytes.
  async function ciphertextHash(kind, ciphertext) {
    return kind === "attachment" ? sha256Hex(b64ToBytes(ciphertext)) : sha256Hex(enc.encode(ciphertext));
  }

  function chainProblems(rows) {
    const sorted = [...rows].sort((a, b) => String(a.attested_at).localeCompare(String(b.attested_at)));
    const problems = [];
    if (sorted.length && sorted[0].supersedes) problems.push("the first statement claims to supersede another that is not in the file");
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i].supersedes !== sorted[i - 1].id) problems.push(`statement ${i + 1} does not point at statement ${i}`);
    }
    return { sorted, problems };
  }

  async function verifyItem(item, key, pinKey) {
    const result = { kind: item.kind, id: item.id, checks: [], ok: true, chain: [] };
    const note = (ok, text) => { result.checks.push({ ok, text }); if (!ok) result.ok = false; };
    const rows = item.attestations || [];
    if (!rows.length) {
      note(false, "no signed statement for this item");
      return result;
    }
    const { sorted, problems } = chainProblems(rows);
    result.chain = sorted.map((r) => ({ at: r.attested_at, reason: r.reason, hash: r.ciphertext_sha256 }));
    for (const p of problems) note(false, p);
    let sigOk = 0;
    for (const r of sorted) if (await verifySignature(key, item.kind, item.id, r)) sigOk++;
    note(sigOk === sorted.length, sigOk === sorted.length ? `${sorted.length} signature${sorted.length === 1 ? "" : "s"} valid` : `${sorted.length - sigOk} of ${sorted.length} signatures invalid`);
    const latest = sorted[sorted.length - 1];
    const actual = await ciphertextHash(item.kind, item.ciphertext);
    note(actual === latest.ciphertext_sha256, actual === latest.ciphertext_sha256 ? "encrypted data matches the newest signed fingerprint" : "encrypted data does NOT match the signed fingerprint");
    if (pinKey) {
      try {
        if (item.kind === "attachment") {
          await EvidenceCrypto.decryptBytes(pinKey, item.ciphertext, item.iv);
          note(true, "decrypts with the PIN (image bytes; compare the photo by eye in the export)");
        } else {
          const plain = await EvidenceCrypto.decryptJSON(pinKey, item.ciphertext, item.iv);
          const same = JSON.stringify(plain) === JSON.stringify(item.plaintext);
          note(same, same ? "decrypted text matches the export" : "decrypted text does NOT match the text in the file");
        }
      } catch (e) {
        note(false, "does not decrypt with this PIN");
      }
    } else {
      result.checks.push({ ok: null, text: "text not compared (no PIN given)" });
    }
    return result;
  }

  async function verifyFile(file, pin) {
    if (!file || file.format !== "solusvires-verification-v1") throw new Error("This is not a Solus Vires verification file.");
    if (!file.key || !file.key.public_key) throw new Error("The file has no signing key; the export was made with attestation off.");
    const key = await importKey(file.key.public_key);
    const pinKey = pin && file.salt ? await EvidenceCrypto.deriveKey(pin, file.salt) : null;
    const results = [];
    for (const item of file.items || []) results.push(await verifyItem(item, key, pinKey));
    return { key: file.key, results, allOk: results.every((r) => r.ok), pinUsed: !!pinKey };
  }

  window.ExportVerifier = { verifyFile, statement, signedTime, ciphertextHash, chainProblems };

  if (typeof document === "undefined" || !document.getElementById("verify-form")) return;

  const status = document.getElementById("verify-status");
  let loaded = null;

  function render(outcome) {
    document.getElementById("key-card").hidden = false;
    document.getElementById("key-id").textContent = outcome.key.key_id || "";
    document.getElementById("key-public").textContent = outcome.key.public_key || "";
    const card = document.getElementById("results-card");
    card.hidden = false;
    const kinds = { entry: "Note", attachment: "Photo", profile: "Private profile", plan: "Safety plan" };
    document.getElementById("results-summary").textContent = outcome.allOk
      ? `All ${outcome.results.length} items check out${outcome.pinUsed ? ", including the text" : " (signatures and fingerprints; no PIN given, so the text was not compared)"}.`
      : `${outcome.results.filter((r) => !r.ok).length} of ${outcome.results.length} items have a problem. Read each one below.`;
    const box = document.getElementById("results");
    box.textContent = "";
    for (const r of outcome.results) {
      const art = document.createElement("article");
      art.className = "card verify-item " + (r.ok ? "verify-ok" : "verify-bad");
      const h = document.createElement("h3");
      h.textContent = `${kinds[r.kind] || r.kind} ${r.id ? r.id.slice(0, 8) : ""} · ${r.ok ? "OK" : "PROBLEM"}`;
      art.append(h);
      const ul = document.createElement("ul");
      for (const c of r.checks) {
        const li = document.createElement("li");
        li.textContent = `${c.ok === null ? "–" : c.ok ? "✓" : "✗"} ${c.text}`;
        ul.append(li);
      }
      art.append(ul);
      if (r.chain.length) {
        const p = document.createElement("p");
        p.className = "hint";
        p.textContent = "Signed: " + r.chain.map((c) => `${c.reason} ${new Date(c.at).toLocaleString()}`).join(" → ");
        art.append(p);
      }
      box.append(art);
    }
  }

  document.getElementById("verify-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const f = form.file.files[0];
    if (!f) return;
    status.textContent = "Checking…";
    try {
      loaded = JSON.parse(await f.text());
      const outcome = await verifyFile(loaded, form.pin.value);
      render(outcome);
      status.textContent = "";
    } catch (e) {
      status.textContent = e.message || "Couldn't read that file.";
    }
  });

  document.getElementById("key-live-btn").addEventListener("click", async () => {
    const out = document.getElementById("key-live");
    try {
      const live = await (await fetch("/api/evidence/attestation-key")).json();
      if (!live.enabled) { out.textContent = "The site is not publishing a key right now."; return; }
      const same = loaded && loaded.key && live.public_key === loaded.key.public_key;
      out.textContent = `${live.key_id} ${same ? "· matches the file" : "· DOES NOT match the file"}`;
    } catch (e) {
      out.textContent = "Couldn't reach the site (offline?). Compare the key id with the one on /for-advocates.html another way.";
    }
  });
})();
