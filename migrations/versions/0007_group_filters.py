"""افزودنِ فیلترِ پورن و فیلترِ اسپم به group_guard_settings (برای .فیلترپورن و .فیلتراسپم)

Revision ID: 0007_group_filters
Revises: 0006_hafez_poems
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_group_filters"
down_revision: Union[str, None] = "0006_hafez_poems"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "group_guard_settings",
        sa.Column("porn_filter_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "group_guard_settings",
        sa.Column("spam_filter_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("group_guard_settings", "spam_filter_enabled")
    op.drop_column("group_guard_settings", "porn_filter_enabled")
