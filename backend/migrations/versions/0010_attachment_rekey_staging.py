"""staging columns for re-encrypted attachments during a PIN change

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07

P3-J2. Changing the Notes PIN means re-encrypting every note, photo and the
safety plan under a new key, in the browser. Photos are too large to send
in one request, so each re-encrypted image is staged in these columns,
tagged with the change's id; the final request checks every photo has a
staged copy for that id and swaps them all in one transaction. Nothing live
changes until then.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("evidence_attachments", sa.Column("pending_ciphertext", sa.LargeBinary(), nullable=True))
    op.add_column("evidence_attachments", sa.Column("pending_iv", sa.Text(), nullable=True))
    op.add_column(
        "evidence_attachments", sa.Column("pending_rekey_id", postgresql.UUID(as_uuid=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("evidence_attachments", "pending_rekey_id")
    op.drop_column("evidence_attachments", "pending_iv")
    op.drop_column("evidence_attachments", "pending_ciphertext")
