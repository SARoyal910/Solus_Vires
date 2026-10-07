"""Encryption at rest for the few things the server must be able to read (P3-I2).

Almost everything a survivor writes is encrypted in the browser and never
readable here. The exception is the note a survivor leaves for their trusted
contacts: it has to go into an alert email at alert time, so the server must
decrypt it then. This module keeps it AES-GCM encrypted in the database under
CONTACT_NOTE_KEY, so a copy of the database alone does not reveal it. It is a
smaller promise than the notes vault's and the privacy page says so.

With no key configured the feature is off: nothing is stored, nothing fails.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import get_settings

_PREFIX = "v1:"


def enabled() -> bool:
    return bool(get_settings().contact_note_key)


def _key() -> bytes:
    raw = get_settings().contact_note_key
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise RuntimeError("CONTACT_NOTE_KEY is not base64") from exc
    if len(key) != 32:
        raise RuntimeError(
            "CONTACT_NOTE_KEY must decode to 32 bytes; generate one with "
            "python -c 'import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'"
        )
    return key


def encrypt_text(plaintext: str, *, associated: str) -> str:
    """Returns "v1:<nonce>:<ciphertext>", both base64. `associated` binds the row (e.g. the user id)."""
    nonce = os.urandom(12)
    sealed = AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), associated.encode("utf-8"))
    return _PREFIX + base64.b64encode(nonce).decode() + ":" + base64.b64encode(sealed).decode()


def decrypt_text(stored: str, *, associated: str) -> str:
    if not stored.startswith(_PREFIX):
        raise ValueError("unknown at-rest format")
    nonce_b64, sealed_b64 = stored[len(_PREFIX):].split(":", 1)
    plain = AESGCM(_key()).decrypt(
        base64.b64decode(nonce_b64), base64.b64decode(sealed_b64), associated.encode("utf-8")
    )
    return plain.decode("utf-8")
