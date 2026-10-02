"""Encrypted vault additions: the safety plan (P2-E8) and photo/screenshot
attachments (P2-E7). Like the notes, every byte of content is ciphertext made
in the survivor's browser under their Notes PIN; the server cannot read it.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, LargeBinary, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class SafetyPlan(Base):
    """One encrypted safety plan per account (the fillable Safety Planning checklist)."""

    __tablename__ = "safety_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    iv: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EvidenceAttachment(Base):
    """An encrypted photo or screenshot attached to one of the owner's notes.

    The browser strips the image's metadata (EXIF, including GPS) by
    re-encoding it, then encrypts it. ``ciphertext`` is the encrypted image;
    ``meta_ciphertext`` is an encrypted JSON description (file name, type,
    dimensions). Neither is readable here. Deleting the note or the account
    deletes its attachments (ON DELETE CASCADE).
    """

    __tablename__ = "evidence_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    iv: Mapped[str] = mapped_column(Text, nullable=False)
    meta_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    meta_iv: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
