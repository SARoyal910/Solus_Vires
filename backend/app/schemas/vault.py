import base64
import binascii
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .evidence import EncryptedBlob as EncryptedBlobIn
from .evidence import KeyCheck as KeyCheckBlob

# The browser re-encodes images to at most 5 MiB before encrypting; AES-GCM
# adds a 16-byte tag. Base64 grows that by a third.
MAX_ATTACHMENT_PLAINTEXT_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_CIPHERTEXT_BYTES = MAX_ATTACHMENT_PLAINTEXT_BYTES + 16
_MAX_ATTACHMENT_BASE64_CHARS = 4 * ((MAX_ATTACHMENT_CIPHERTEXT_BYTES + 2) // 3)


class AttachmentCreate(BaseModel):
    """An encrypted image plus its encrypted description. Opaque to the server."""

    entry_id: uuid.UUID
    ciphertext: str = Field(min_length=1, max_length=_MAX_ATTACHMENT_BASE64_CHARS)
    iv: str = Field(min_length=1, max_length=64)
    meta_ciphertext: str = Field(min_length=1, max_length=4000)
    meta_iv: str = Field(min_length=1, max_length=64)

    @field_validator("ciphertext")
    @classmethod
    def must_be_base64(cls, value: str) -> str:
        try:
            raw = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("ciphertext must be base64") from exc
        if len(raw) > MAX_ATTACHMENT_CIPHERTEXT_BYTES:
            raise ValueError("attachment is larger than 5 MB")
        return value


class AttachmentInfo(BaseModel):
    """Everything about an attachment except the image itself."""

    id: uuid.UUID
    entry_id: uuid.UUID
    iv: str
    meta_ciphertext: str
    meta_iv: str
    size_bytes: int
    created_at: datetime


class AttachmentData(BaseModel):
    id: uuid.UUID
    ciphertext: str
    iv: str


class SafetyPlanResponse(BaseModel):
    ciphertext: str
    iv: str
    updated_at: datetime


class RekeyAttachmentStage(BaseModel):
    """One photo re-encrypted under the new key, staged ahead of the swap (P3-J2)."""

    rekey_id: uuid.UUID
    ciphertext: str = Field(min_length=1, max_length=_MAX_ATTACHMENT_BASE64_CHARS)
    iv: str = Field(min_length=1, max_length=64)

    @field_validator("ciphertext")
    @classmethod
    def must_be_base64(cls, value: str) -> str:
        return AttachmentCreate.must_be_base64(value)


class RekeyEntry(BaseModel):
    id: uuid.UUID
    ciphertext: str = Field(min_length=1, max_length=200_000)
    iv: str = Field(min_length=1, max_length=64)


class RekeyAttachmentMeta(BaseModel):
    id: uuid.UUID
    meta_ciphertext: str = Field(min_length=1, max_length=4000)
    meta_iv: str = Field(min_length=1, max_length=64)


class RekeyRequest(BaseModel):
    """Everything in the vault, re-encrypted under the new PIN, swapped in at once.

    The server cannot read any of it. It only checks that the set of ids
    matches what the account holds right now, so a note added from another
    device mid-change cannot be silently left under the old key.
    """

    rekey_id: uuid.UUID
    salt: str = Field(min_length=1, max_length=512)
    key_check: KeyCheckBlob
    profile: EncryptedBlobIn | None = None
    plan: EncryptedBlobIn | None = None
    entries: list[RekeyEntry] = Field(default_factory=list, max_length=5000)
    attachments: list[RekeyAttachmentMeta] = Field(default_factory=list, max_length=2000)


class RekeyResponse(BaseModel):
    ok: bool
    entries: int
    attachments: int
