"""alert history records how many emails the fallback provider carried

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-07

SCALE.md Stage 1 item 2: a second email provider (Postmark) takes over when
Brevo fails or is out of quota. checkin_alert_log.emails_via_fallback counts
how many of emails_sent went through it, so a delivery problem can be traced
to a provider from the history alone. Counts only, never addresses.

Additive (expand/contract): old code ignores the column, the default is 0.
The column drop pencilled as 0008 in PHASE2_PLAN.md moves to 0009.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "checkin_alert_log",
        sa.Column("emails_via_fallback", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("checkin_alert_log", "emails_via_fallback")
