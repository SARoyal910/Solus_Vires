import base64
import binascii
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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
