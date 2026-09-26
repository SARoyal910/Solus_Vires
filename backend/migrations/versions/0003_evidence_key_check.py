"""evidence PIN key-check blob

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26

Stores a constant encrypted under the survivor's Notes PIN so the browser can
prove a PIN is correct before letting anyone write notes with it. Without it,
a wrong PIN on an empty vault was accepted and silently forked the notes
(engineering review H3). Ciphertext only; the server can't read it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("evidence_key_check_ciphertext", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("evidence_key_check_iv", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "evidence_key_check_iv")
    op.drop_column("users", "evidence_key_check_ciphertext")
