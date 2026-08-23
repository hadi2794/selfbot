"""افزودنِ جدولِ hafez_poems (برای `.فال` - جایگزینِ importِ زمانِ‌اجرای پکیجِ hafez)

Revision ID: 0006_hafez_poems
Revises: 0005_new_features
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_hafez_poems"
down_revision: Union[str, None] = "0005_new_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hafez_poems",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("poem", sa.Text(), nullable=False),
        sa.Column("interpretation", sa.Text(), nullable=True),
        sa.Column("alt_interpretation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("hafez_poems")
