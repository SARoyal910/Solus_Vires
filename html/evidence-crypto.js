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

// A rough, honest strength hint for the notes PIN (P2-A10). Not a promise:
// it only catches the common weak shapes (too short, one repeated character,
// digits only, keyboard runs, a few very common words) and rewards length and
// several unrelated words, which is what actually slows down guessing.
const PIN_MIN_LENGTH = 12;
const COMMON_PIN_PARTS = ["password", "passw0rd", "qwerty", "asdfgh", "letmein", "iloveyou", "123456", "abcdef", "abc123", "welcome", "monkey", "dragon"];

function pinStrength(pin) {
  const value = String(pin || "");
  const length = [...value].length;
  if (length < PIN_MIN_LENGTH) {
    const more = PIN_MIN_LENGTH - length;
    return { level: "short", message: `Too short: ${more} more character${more === 1 ? "" : "s"} needed.` };
  }
  const lower = value.toLowerCase();
  const distinct = new Set(lower).size;
  const words = lower.split(/[^\p{L}]+/u).filter((w) => w.length >= 3);
  const isRun = (s) => {
    for (let i = 2; i < s.length; i++) {
      const a = s.charCodeAt(i - 2), b = s.charCodeAt(i - 1), c = s.charCodeAt(i);
      if (!(b - a === c - b && Math.abs(c - b) === 1)) return false;
    }
    return true;
  };
  if (distinct <= 3 || /^\d+$/.test(value) || isRun(lower) || COMMON_PIN_PARTS.some((p) => lower.includes(p))) {
    return { level: "weak", message: "Easy to guess. Try a few unrelated words, like kettle-harbor-violet." };
  }
  if (length >= 20 || (words.length >= 3 && length >= 16)) {
    return { level: "strong", message: "Strong. Write it down somewhere safe." };
  }
  return { level: "ok", message: "OK. Longer is stronger: a few unrelated words work well." };
}

window.EvidenceCrypto = {
  generateSaltBase64,
  deriveKey,
  encryptJSON,
  decryptJSON,
  makeKeyCheck,
  keyMatchesCheck,
  pinStrength,
  PIN_MIN_LENGTH,
};
