import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EncryptedBlob(BaseModel):
    """Opaque client-encrypted payload. The server never inspects this content."""

    ciphertext: str = Field(min_length=1, max_length=200_000)
    iv: str = Field(min_length=1, max_length=64)


class KeyCheck(BaseModel):
    ciphertext: str = Field(min_length=1, max_length=512)
    iv: str = Field(min_length=1, max_length=64)


class SaltResponse(BaseModel):
    salt: str | None
    key_check: KeyCheck | None = None


class SetSaltRequest(BaseModel):
    salt: str = Field(min_length=1, max_length=512)
    # Optional only so a browser still running the old page can finish setup;
    # the current page always sends it.
    key_check: KeyCheck | None = None


class CaseProfileResponse(BaseModel):
    ciphertext: str
    iv: str
    updated_at: datetime


class EvidenceEntryResponse(BaseModel):
    id: uuid.UUID
    ciphertext: str
    iv: str
    created_at: datetime
    updated_at: datetime


class AttestationResponse(BaseModel):
    """A signed "this ciphertext existed at this time" statement (P3-H1)."""

    id: uuid.UUID
    kind: str
    item_id: uuid.UUID
    ciphertext_sha256: str
    attested_at: datetime
    key_id: str
    signature: str
    reason: str
    supersedes: uuid.UUID | None


class AttestationKeyResponse(BaseModel):
    enabled: bool
    key_id: str | None = None
    public_key: str | None = None
    algorithm: str = "Ed25519"
    message_format: str = "solusvires-attest-v1|<kind>|<item id>|<sha256 hex of ciphertext>|<attested_at ISO 8601>"
