"""افزودنِ جدول‌های خلاصه‌ی روزانه (`.خلاصه‌روز`): daily_digest_settings + daily_digest_chats

Revision ID: 0008_daily_digest
Revises: 0007_group_filters
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_daily_digest"
down_revision: Union[str, None] = "0007_group_filters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_digest_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mode", sa.String(16), nullable=False, server_default="all"),
        sa.Column("hour", sa.SmallInteger(), nullable=False, server_default="23"),
        sa.Column("minute", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("last_run_date", sa.String(10), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_daily_digest_settings_singleton"),
    )

    op.create_table(
        "daily_digest_chats",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("chat_id"),
    )


def downgrade() -> None:
    op.drop_table("daily_digest_chats")
    op.drop_table("daily_digest_settings")
