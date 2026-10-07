"""sessions.device_label and the invite_emails table

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-07

P3-J1: sessions gain a coarse device label ("Safari on iPhone") so the
"where you're signed in" view is recognisable without storing IPs or full
user agents. P3-J4: invite_emails records when an invite email went out,
per account, for a daily cap that protects the email quota alerts rely on.

Additive. The column drop pencilled for 0009 in PHASE2_PLAN moves again, to
the next free revision after Phase 3's ledger (PHASE3_PLAN.md §3).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("device_label", sa.String(length=40), nullable=True))
    op.create_table(
        "invite_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invite_emails_user_id", "invite_emails", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_invite_emails_user_id", table_name="invite_emails")
    op.drop_table("invite_emails")
    op.drop_column("sessions", "device_label")
