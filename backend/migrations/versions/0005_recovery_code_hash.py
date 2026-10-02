"""recovery codes looked up by a peppered HMAC-SHA256

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02

Recovery codes are 80 random bits, so they don't need a memory-hard hash.
Checking up to ten Argon2 hashes per /api/auth/recover request made that
endpoint a cheap way to burn server CPU (engineering review M6). New codes
are stored as HMAC-SHA256(RECOVERY_CODE_PEPPER, user id + code) and found
by a single indexed lookup. Codes issued before this keep their Argon2 hash
in code_hash and are still accepted until used.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recovery_codes", sa.Column("code_sha256", sa.String(length=64), nullable=True))
    op.create_index("ix_recovery_codes_code_sha256", "recovery_codes", ["code_sha256"])
    op.alter_column("recovery_codes", "code_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Codes stored only as an HMAC can't be turned back into Argon2 hashes;
    # they stop working on downgrade. Accounts keep their password.
    op.execute("DELETE FROM recovery_codes WHERE code_hash IS NULL")
    op.alter_column("recovery_codes", "code_hash", existing_type=sa.Text(), nullable=False)
    op.drop_index("ix_recovery_codes_code_sha256", table_name="recovery_codes")
    op.drop_column("recovery_codes", "code_sha256")
