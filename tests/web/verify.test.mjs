// The browser verifier (html/verify.js) against statements signed the way
// the backend signs them (backend/app/core/attestation.py). Node's WebCrypto.
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, sign as nodeSign } from "node:crypto";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

globalThis.window = globalThis;
vm.runInThisContext(readFileSync(new URL("../../html/evidence-crypto.js", import.meta.url), "utf8"));
vm.runInThisContext(readFileSync(new URL("../../html/verify.js", import.meta.url), "utf8"));
const C = globalThis.EvidenceCrypto;
const V = globalThis.ExportVerifier;

// An Ed25519 key pair; the "server" signs exactly what attestation.py signs.
const { publicKey, privateKey } = generateKeyPairSync("ed25519");
const rawPublic = publicKey.export({ type: "spki", format: "der" }).subarray(-32);
const key = { key_id: createHash("sha256").update(rawPublic).digest("hex").slice(0, 8), public_key: rawPublic.toString("base64"), algorithm: "Ed25519", message_format: "solusvires-attest-v1|<kind>|<item id>|<sha256 hex of ciphertext>|<attested_at ISO 8601>" };

function attest(kind, id, ciphertext, when, reason = "saved", supersedes = null) {
  const sha = kind === "attachment" ? createHash("sha256").update(Buffer.from(ciphertext, "base64")).digest("hex") : createHash("sha256").update(ciphertext, "ascii").digest("hex");
  const pyIso = when.toISOString().replace("Z", "+00:00"); // Python isoformat()
  const message = `solusvires-attest-v1|${kind}|${id}|${sha}|${pyIso}`;
  return { id: crypto.randomUUID(), ciphertext_sha256: sha, attested_at: when.toISOString(), key_id: key.key_id, signature: nodeSign(null, Buffer.from(message), privateKey).toString("base64"), reason, supersedes };
}

const salt = C.generateSaltBase64();
const PIN = "kettle-harbor-violet";
const pinKey = await C.deriveKey(PIN, salt);
const note = { entry_date: "2026-10-01", text: "He broke the door." };
const noteBlob = await C.encryptJSON(pinKey, note);
const entryId = crypto.randomUUID();
const photoBytes = new Uint8Array([255, 216, 255, 224, 1, 2, 3, 4]);
const photoBlob = await C.encryptBytes(pinKey, photoBytes);
const photoId = crypto.randomUUID();

const t0 = new Date("2026-10-01T10:00:00.123456Z");
const t1 = new Date("2026-10-02T10:00:00.000Z");
const first = attest("entry", entryId, "b2xkLWNpcGhlcg", t0);
const edited = attest("entry", entryId, noteBlob.ciphertext, t1, "edited", first.id);

function file(overrides = {}) {
  return {
    format: "solusvires-verification-v1",
    key,
    salt,
    items: [
      { kind: "entry", id: entryId, ciphertext: noteBlob.ciphertext, iv: noteBlob.iv, plaintext: note, attestations: [first, edited] },
      { kind: "attachment", id: photoId, ciphertext: photoBlob.ciphertext, iv: photoBlob.iv, plaintext: { name: "IMG.jpg" }, attestations: [attest("attachment", photoId, photoBlob.ciphertext, t1)] },
    ],
    ...overrides,
  };
}

test("statement text matches the backend's format, including the +00:00 time", () => {
  assert.equal(V.signedTime("2026-10-01T10:00:00.123456Z"), "2026-10-01T10:00:00.123456+00:00");
  assert.equal(V.statement("entry", "abc", "ff", "2026-10-01T10:00:00Z"), "solusvires-attest-v1|entry|abc|ff|2026-10-01T10:00:00+00:00");
});

test("a genuine file passes, with and without the PIN", async () => {
  const noPin = await V.verifyFile(file(), "");
  assert.equal(noPin.allOk, true);
  assert.equal(noPin.pinUsed, false);
  assert.ok(noPin.results[0].checks.some((c) => c.ok === null && /no PIN/.test(c.text)));
  const withPin = await V.verifyFile(file(), PIN);
  assert.equal(withPin.allOk, true);
  assert.ok(withPin.results[0].checks.some((c) => c.ok && /matches the export/.test(c.text)));
  assert.ok(withPin.results[1].checks.some((c) => c.ok && /decrypts with the PIN/.test(c.text)));
  assert.deepEqual(withPin.results[0].chain.map((c) => c.reason), ["saved", "edited"]);
});

test("an edited plaintext is caught with the PIN", async () => {
  const f = file();
  f.items[0].plaintext = { ...note, text: "Nothing happened." };
  const out = await V.verifyFile(f, PIN);
  assert.equal(out.allOk, false);
  assert.ok(out.results[0].checks.some((c) => c.ok === false && /does NOT match the text/.test(c.text)));
});

test("tampered ciphertext, a forged signature and a broken chain are each caught", async () => {
  const swapped = file();
  swapped.items[0].ciphertext = (await C.encryptJSON(pinKey, { ...note, text: "x" })).ciphertext;
  assert.ok((await V.verifyFile(swapped, "")).results[0].checks.some((c) => c.ok === false && /does NOT match the signed fingerprint/.test(c.text)));

  const forged = file();
  forged.items[0].attestations[1] = { ...edited, attested_at: "2026-09-01T00:00:00Z" };
  assert.ok((await V.verifyFile(forged, "")).results[0].checks.some((c) => c.ok === false && /invalid/.test(c.text)));

  const broken = file();
  broken.items[0].attestations[1] = { ...edited, supersedes: crypto.randomUUID() };
  assert.ok((await V.verifyFile(broken, "")).results[0].checks.some((c) => c.ok === false && /does not point at/.test(c.text)));
});

test("a wrong PIN is reported, not treated as tampering", async () => {
  const out = await V.verifyFile(file(), "wrong-pin-entirely");
  assert.ok(out.results[0].checks.some((c) => c.ok === false && /does not decrypt/.test(c.text)));
  // Signatures and fingerprints still pass: the data is intact, the PIN is wrong.
  assert.ok(out.results[0].checks.some((c) => c.ok && /signatures valid/.test(c.text)));
});

test("files that are not verification files are refused plainly", async () => {
  await assert.rejects(V.verifyFile({ format: "something-else" }, ""), /not a Solus Vires verification file/);
  await assert.rejects(V.verifyFile({ format: "solusvires-verification-v1", key: null, items: [] }, ""), /attestation off/);
});
