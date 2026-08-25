"""افزودنِ لایه‌ی زمان‌بندیِ منشیِ خودکار: ستونِ schedule_enabled + جدولِ assistant_schedule_windows

Revision ID: 0009_assistant_schedule
Revises: 0008_daily_digest
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_assistant_schedule"
down_revision: Union[str, None] = "0008_daily_digest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistant_settings",
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "assistant_schedule_windows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(64), nullable=False, server_default=""),
        sa.Column("start_minute", sa.SmallInteger(), nullable=False),
        sa.Column("end_minute", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("start_minute >= 0 AND start_minute < 1440", name="ck_assistant_window_start_range"),
        sa.CheckConstraint("end_minute >= 0 AND end_minute < 1440", name="ck_assistant_window_end_range"),
    )


def downgrade() -> None:
    op.drop_table("assistant_schedule_windows")
    op.drop_column("assistant_settings", "schedule_enabled")
