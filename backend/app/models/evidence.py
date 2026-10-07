import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CaseProfile(Base):
    """A survivor's private, encrypted record about their situation. Always ciphertext.

    Scoped one-per-user by the unique constraint on user_id — never queryable across users,
    never a shared/global table. See Solus Vires plan: no public abuser registry.
    """

    __tablename__ = "case_profiles"

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


class EvidenceEntry(Base):
    """A single encrypted evidence log entry. The server never sees plaintext content."""

    __tablename__ = "evidence_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    iv: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EvidenceAttestation(Base):
    """One signed statement: "this ciphertext hash existed at this time" (P3-H1).

    A row per save. Editing a note or changing the PIN (which re-encrypts
    everything) adds a new row that points at the one it supersedes, so a
    verifier sees the whole chain back to the first save, with its reason.
    Holds a hash of ciphertext, never content.
    """

    __tablename__ = "evidence_attestations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # entry | attachment | profile | plan
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ciphertext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    attested_at: Mapped[datetime] = mapped_column(nullable=False)
    key_id: Mapped[str] = mapped_column(String(16), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)  # saved | edited | rekeyed
    supersedes: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
