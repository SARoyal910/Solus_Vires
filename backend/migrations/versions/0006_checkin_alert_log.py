"""check-in reliability: alert history, numbered repeats, push health

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-02

P2-E5. checkin_alert_log is the survivor's own record of every alert and
stand-down sent for them (who was reached, by which channel), shown on
checkin.html and clearable there. checkin_schedules.alerts_sent_count numbers
repeat alerts and tells a check-in whether contacts need a stand-down.
push_subscriptions.last_push_ok_at is when the push service last accepted an
alert for that device; trusted_contacts.push_lost_at is set when a contact's
device was pruned as expired, so the survivor can see it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checkin_alert_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("alert_number", sa.Integer(), nullable=True),
        sa.Column("contacts_notified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushes_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushes_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checkin_alert_log_user_id", "checkin_alert_log", ["user_id"])
    op.add_column(
        "checkin_schedules",
        sa.Column("alerts_sent_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("push_subscriptions", sa.Column("last_push_ok_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trusted_contacts", sa.Column("push_lost_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("trusted_contacts", "push_lost_at")
    op.drop_column("push_subscriptions", "last_push_ok_at")
    op.drop_column("checkin_schedules", "alerts_sent_count")
    op.drop_index("ix_checkin_alert_log_user_id", table_name="checkin_alert_log")
    op.drop_table("checkin_alert_log")
