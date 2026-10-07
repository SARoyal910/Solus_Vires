"""Tamper-evident attestation of ciphertext (P3-H1, decision D11).

When a note, photo, profile or safety plan is saved, the server records the
SHA-256 of the ciphertext it received, the time, and an Ed25519 signature
over both. The server learns nothing it did not already hold: it stores that
ciphertext anyway. What the signature adds is a statement a third party can
check later, offline, against the public key published on /trust.html:

    "Solus Vires held exactly this ciphertext at this time."

With the survivor's PIN, the verifier can also decrypt the ciphertext and
confirm it matches the plaintext in the export. Without it, only the first
statement can be checked. Neither is a legal finding; the wording rule in
PHASE3_PLAN.md D11 is "tamper-evident", never "admissible".

Off, and silently so, without ATTESTATION_PRIVATE_KEY: items save as before,
with no attestation row.
"""

import base64
import hashlib
import logging
from datetime import datetime, timezone
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import get_settings

logger = logging.getLogger("solusvires.attestation")


def enabled() -> bool:
    return bool(get_settings().attestation_private_key)


@lru_cache
def _private_key() -> Ed25519PrivateKey:
    raw = get_settings().attestation_private_key
    seed = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if len(seed) != 32:
        raise RuntimeError(
            "ATTESTATION_PRIVATE_KEY must decode to 32 bytes; generate one with "
            "python -c 'import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'"
        )
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_b64() -> str:
    """The raw 32-byte Ed25519 public key, base64, as published on /trust.html."""
    raw = _private_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(raw).decode()


def key_id() -> str:
    """Short identifier for the published key: first 8 hex of SHA-256(public key)."""
    return hashlib.sha256(base64.b64decode(public_key_b64())).hexdigest()[:8]


def ciphertext_sha256(ciphertext: str | bytes) -> str:
    data = ciphertext if isinstance(ciphertext, bytes) else ciphertext.encode("ascii")
    return hashlib.sha256(data).hexdigest()


def message(kind: str, item_id: str, sha256_hex: str, attested_at: datetime) -> bytes:
    """The exact bytes that are signed. Documented on /for-advocates.html and used by verify.html."""
    return f"solusvires-attest-v1|{kind}|{item_id}|{sha256_hex}|{attested_at.isoformat()}".encode("utf-8")


def sign(kind: str, item_id: str, sha256_hex: str, attested_at: datetime) -> str:
    return base64.b64encode(_private_key().sign(message(kind, item_id, sha256_hex, attested_at))).decode()


def verify(
    public_key_b64_value: str, kind: str, item_id: str, sha256_hex: str, attested_at: datetime, signature_b64: str
) -> bool:
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64_value))
        key.verify(base64.b64decode(signature_b64), message(kind, item_id, sha256_hex, attested_at))
        return True
    except Exception:
        return False


def now() -> datetime:
    """Full precision: the signed string is attested_at.isoformat(), which the API
    returns with a trailing Z; a verifier swaps that Z for +00:00 to rebuild it."""
    return datetime.now(timezone.utc)
