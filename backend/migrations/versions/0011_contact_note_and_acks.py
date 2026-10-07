"""survivor's note to contacts (at rest) and contact acknowledgments

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-07

P3-I2: checkin_schedules.contact_note holds the survivor's optional message to
their trusted contacts, AES-GCM encrypted under CONTACT_NOTE_KEY, decrypted
only at alert time for the email and the alert landing page. P3-I3:
ack_count and first_ack_at record that a contact pressed "I've got this"
during the current alert episode, so other contacts see "someone is on it".
Counts only; reset when the survivor checks in. Additive.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("checkin_schedules", sa.Column("ack_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("checkin_schedules", sa.Column("first_ack_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("checkin_schedules", sa.Column("contact_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("checkin_schedules", "contact_note")
    op.drop_column("checkin_schedules", "first_ack_at")
    op.drop_column("checkin_schedules", "ack_count")
