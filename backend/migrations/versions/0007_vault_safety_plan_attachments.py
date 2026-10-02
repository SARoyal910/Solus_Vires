"""encrypted safety plan and photo attachments

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-02

safety_plans (P2-E8): one encrypted blob per account, the fillable version
of the Safety Planning checklist. evidence_attachments (P2-E7): encrypted
photos/screenshots tied to a note, metadata stripped in the browser before
encryption. Ciphertext only in both; the server can't read either. The
ledger in docs/PHASE2_PLAN.md pencilled 0007 for attachments alone; the
safety plan rides in the same revision.

Chained after 0006 (Lane A's checkin_alert_log), which lands in the same
merge. It can't be applied on a branch without 0005 and 0006.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "safety_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("iv", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "evidence_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("iv", sa.Text(), nullable=False),
        sa.Column("meta_ciphertext", sa.Text(), nullable=False),
        sa.Column("meta_iv", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_attachments_user_id", "evidence_attachments", ["user_id"])
    op.create_index("ix_evidence_attachments_entry_id", "evidence_attachments", ["entry_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_attachments_entry_id", table_name="evidence_attachments")
    op.drop_index("ix_evidence_attachments_user_id", table_name="evidence_attachments")
    op.drop_table("evidence_attachments")
    op.drop_table("safety_plans")
