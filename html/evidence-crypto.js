// Zero-knowledge helpers for the private notes/evidence log.
// The Evidence PIN never leaves this browser. Only ciphertext + iv are ever sent to the server.

const PBKDF2_ITERATIONS = 600000;

function bufToBase64(buf) {
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

function base64ToBuf(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function generateSaltBase64() {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return bufToBase64(salt);
}

async function deriveKey(pin, saltBase64) {
  const enc = new TextEncoder();
  const baseKey = await crypto.subtle.importKey(
    "raw",
    enc.encode(pin),
    "PBKDF2",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: base64ToBuf(saltBase64),
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256",
    },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

async function encryptJSON(key, value) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = new TextEncoder();
  const plaintext = enc.encode(JSON.stringify(value));
  const ciphertextBuf = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext);
  return { ciphertext: bufToBase64(ciphertextBuf), iv: bufToBase64(iv) };
}

async function decryptJSON(key, ciphertextBase64, ivBase64) {
  const ciphertextBuf = base64ToBuf(ciphertextBase64);
  const iv = new Uint8Array(base64ToBuf(ivBase64));
  const plaintextBuf = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ciphertextBuf);
  const dec = new TextDecoder();
  return JSON.parse(dec.decode(plaintextBuf));
}

// A fixed value encrypted under the PIN at setup. Decrypting it is how the
// browser proves a PIN is right before anything is written with it; AES-GCM
// refuses to decrypt under any other key.
const KEY_CHECK_VALUE = "solusvires-key-check-v1";

function makeKeyCheck(key) {
  return encryptJSON(key, KEY_CHECK_VALUE);
}

async function keyMatchesCheck(key, keyCheck) {
  try {
    return (await decryptJSON(key, keyCheck.ciphertext, keyCheck.iv)) === KEY_CHECK_VALUE;
  } catch (e) {
    return false;
  }
}

window.EvidenceCrypto = {
  generateSaltBase64,
  deriveKey,
  encryptJSON,
  decryptJSON,
  makeKeyCheck,
  keyMatchesCheck,
};
