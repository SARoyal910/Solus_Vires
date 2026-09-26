"""push endpoint unique per contact, not globally

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26

A browser has one push endpoint per site. With endpoint globally unique, a
person who is the trusted contact for two survivors had their device silently
moved to whichever invite they subscribed under last, and the first
survivor's alerts stopped reaching them (engineering review H4). The same
endpoint may now belong to several contacts.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_push_subscriptions_endpoint", "push_subscriptions", type_="unique")
    op.create_unique_constraint(
        "uq_push_subscriptions_contact_endpoint", "push_subscriptions", ["trusted_contact_id", "endpoint"]
    )
    op.create_index("ix_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"])


def downgrade() -> None:
    # Keeps the most recent row per endpoint, which is what the old rule did.
    op.execute(
        """
        DELETE FROM push_subscriptions a USING push_subscriptions b
        WHERE a.endpoint = b.endpoint AND a.last_seen_at < b.last_seen_at
        """
    )
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_constraint("uq_push_subscriptions_contact_endpoint", "push_subscriptions", type_="unique")
    op.create_unique_constraint("uq_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"])
