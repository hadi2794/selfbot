"""schema جدید: scheduled_jobs (برای .زمان‌بند و .یادآوری)

Revision ID: 0002_scheduled_jobs
Revises: 0001_initial_schema
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_scheduled_jobs"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="schedule"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('schedule', 'reminder')", name="ck_scheduled_jobs_kind"),
    )
    op.create_index("ix_scheduled_jobs_run_at", "scheduled_jobs", ["run_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_jobs_run_at", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
