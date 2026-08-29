import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SaltResponse(BaseModel):
    salt: str | None


class SetSaltRequest(BaseModel):
    salt: str = Field(min_length=1, max_length=512)


class EncryptedBlob(BaseModel):
    """Opaque client-encrypted payload. The server never inspects this content."""

    ciphertext: str = Field(min_length=1, max_length=200_000)
    iv: str = Field(min_length=1, max_length=64)


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
