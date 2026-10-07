"""evidence_attestations: signed "this ciphertext existed at this time" rows

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-07

P3-H1. One row per save of a note, photo, profile or safety plan: the
SHA-256 of the ciphertext, the time, the key id and an Ed25519 signature,
plus the reason (saved, edited, rekeyed) and the row it supersedes. Hashes
only; never content. Deleted with the account.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence_attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("key_id", sa.String(length=16), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("supersedes", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_evidence_attestations_user_id", "evidence_attestations", ["user_id"])
    op.create_index("ix_evidence_attestations_item_id", "evidence_attestations", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_attestations_item_id", table_name="evidence_attestations")
    op.drop_index("ix_evidence_attestations_user_id", table_name="evidence_attestations")
    op.drop_table("evidence_attestations")
