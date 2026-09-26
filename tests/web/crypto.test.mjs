// Runs the browser's evidence-crypto.js under Node's WebCrypto.
//   node --test tests/web/
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

globalThis.window = globalThis;
vm.runInThisContext(readFileSync(new URL("../../html/evidence-crypto.js", import.meta.url), "utf8"));
const C = globalThis.EvidenceCrypto;

const salt = C.generateSaltBase64();
const rightKey = await C.deriveKey("kettle-harbor-violet", salt);
const wrongKey = await C.deriveKey("kettle-harbor-violeT", salt);

test("notes round-trip under the right PIN", async () => {
  const note = { entry_date: "2026-09-26", text: "He took my phone again." };
  const blob = await C.encryptJSON(rightKey, note);
  assert.deepEqual(await C.decryptJSON(rightKey, blob.ciphertext, blob.iv), note);
});

test("a wrong PIN cannot decrypt notes", async () => {
  const blob = await C.encryptJSON(rightKey, { text: "private" });
  await assert.rejects(C.decryptJSON(wrongKey, blob.ciphertext, blob.iv));
});

test("ciphertext never contains the plaintext", async () => {
  const blob = await C.encryptJSON(rightKey, { text: "private words" });
  assert.ok(!Buffer.from(blob.ciphertext, "base64").toString("latin1").includes("private words"));
});

test("key-check accepts the right PIN and rejects a wrong one (H3)", async () => {
  const check = await C.makeKeyCheck(rightKey);
  assert.equal(await C.keyMatchesCheck(rightKey, check), true);
  assert.equal(await C.keyMatchesCheck(wrongKey, check), false);
});

test("key-check under the same PIN but a different salt is rejected", async () => {
  const otherSaltKey = await C.deriveKey("kettle-harbor-violet", C.generateSaltBase64());
  assert.equal(await C.keyMatchesCheck(otherSaltKey, await C.makeKeyCheck(rightKey)), false);
});

test("a tampered key-check is rejected, not accepted", async () => {
  const check = await C.makeKeyCheck(rightKey);
  const bytes = Buffer.from(check.ciphertext, "base64");
  bytes[0] ^= 1;
  assert.equal(await C.keyMatchesCheck(rightKey, { ...check, ciphertext: bytes.toString("base64") }), false);
});
