"""افزودنِ ai_mode به assistant_settings (اتصالِ اختیاریِ .منشی به هوش‌مصنوعی)

Revision ID: 0004_assistant_ai_mode
Revises: 0003_group_guard
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_assistant_ai_mode"
down_revision: Union[str, None] = "0003_group_guard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistant_settings",
        sa.Column("ai_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("assistant_settings", "ai_mode")
