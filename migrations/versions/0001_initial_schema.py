"""schema اولیه: notes, assistant, autopost, font, clock, stats

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --------------------------------------------------------------- notes
    op.create_table(
        "notes",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --------------------------------------------------------- assistant ---
    op.create_table(
        "assistant_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="mention"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("delay_seconds", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("auto_detect", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("manual_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_assistant_settings_singleton"),
    )

    op.create_table(
        "assistant_chat_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("rule", sa.String(length=8), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("chat_id", name="uq_assistant_chat_rules_chat_id"),
        sa.CheckConstraint("rule IN ('include', 'exclude')", name="ck_assistant_chat_rules_rule"),
    )
    op.create_index(
        "ix_assistant_chat_rules_chat_id", "assistant_chat_rules", ["chat_id"], unique=False
    )

    # ---------------------------------------------------------- autopost ---
    op.create_table(
        "autopost_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_autopost_settings_singleton"),
    )

    op.create_table(
        "autopost_chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # -------------------------------------------------------------- font ---
    op.create_table(
        "font_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("style", sa.String(length=32), nullable=False, server_default="bold"),
        sa.CheckConstraint("id = 1", name="ck_font_settings_singleton"),
    )

    # ----------------------------------------------------- clock/profile ---
    op.create_table(
        "clock_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("style", sa.String(length=32), nullable=False, server_default="default"),
        sa.Column("base_name", sa.Text(), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_clock_settings_singleton"),
    )

    # -------------------------------------------------------------- stats ---
    op.create_table(
        "stats_summary",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("commands_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("messages_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("autopost_ok", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("autopost_fail", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("errors", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_stats_summary_singleton"),
    )

    op.create_table(
        "stats_command_counts",
        sa.Column("command_name", sa.String(length=64), primary_key=True),
        sa.Column("count", sa.BigInteger(), nullable=False, server_default="0"),
    )

    op.create_table(
        "stats_chat_counts",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("messages", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("commands", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("title", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("stats_chat_counts")
    op.drop_table("stats_command_counts")
    op.drop_table("stats_summary")
    op.drop_table("clock_settings")
    op.drop_table("font_settings")
    op.drop_table("autopost_chats")
    op.drop_table("autopost_settings")
    op.drop_index("ix_assistant_chat_rules_chat_id", table_name="assistant_chat_rules")
    op.drop_table("assistant_chat_rules")
    op.drop_table("assistant_settings")
    op.drop_table("notes")
