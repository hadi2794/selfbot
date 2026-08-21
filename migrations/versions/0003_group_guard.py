"""schema جدید: group_guard_settings (برای .فیلترلینک و .خوش‌آمد)

Revision ID: 0003_group_guard
Revises: 0002_scheduled_jobs
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_group_guard"
down_revision: Union[str, None] = "0002_scheduled_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_guard_settings",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "link_filter_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "welcome_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("welcome_text", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("group_guard_settings")
