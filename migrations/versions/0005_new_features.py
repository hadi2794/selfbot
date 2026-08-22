"""اضافه کردن جداول جدید برای قابلیت‌های نسخه 9.3 تا 10.0

Revision ID: 0005
Revises: 0004_assistant_ai_mode
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_new_features'
down_revision: Union[str, None] = '0004_assistant_ai_mode'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Inbox
    op.create_table(
        'inbox_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), nullable=True),
        sa.Column('sender_name', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('importance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id', 'message_id', name='uq_inbox_chat_message'),
    )
    op.create_index('ix_inbox_items_chat_id', 'inbox_items', ['chat_id'])
    op.create_index('ix_inbox_items_read', 'inbox_items', ['read'])
    op.create_index('ix_inbox_items_importance', 'inbox_items', ['importance'])

    # Notification Rules
    op.create_table(
        'notification_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('trigger_type', sa.String(16), nullable=False),
        sa.Column('trigger_value', sa.Text(), nullable=False),
        sa.Column('action_type', sa.String(16), nullable=False),
        sa.Column('action_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("trigger_type IN ('message', 'keyword', 'user', 'time')", name='ck_notif_trigger_type'),
        sa.CheckConstraint("action_type IN ('notify', 'save', 'forward', 'reply')", name='ck_notif_action_type'),
    )

    # User Profiles
    op.create_table(
        'user_profiles',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(64), nullable=True),
        sa.Column('first_name', sa.Text(), nullable=True),
        sa.Column('last_name', sa.Text(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_vip', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
    )
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'])
    op.create_index('ix_user_profiles_tags', 'user_profiles', ['tags'])

    # AI Memory
    op.create_table(
        'ai_memory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.String(32), nullable=False),
        sa.Column('key', sa.String(128), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', 'key', name='uq_ai_memory_cat_key'),
    )
    op.create_index('ix_ai_memory_category', 'ai_memory', ['category'])
    op.create_index('ix_ai_memory_key', 'ai_memory', ['key'])

    # Automation Rules
    op.create_table(
        'automation_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('event_type', sa.String(16), nullable=False),
        sa.Column('event_value', sa.Text(), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('action_type', sa.String(16), nullable=False),
        sa.Column('action_value', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("event_type IN ('message', 'schedule', 'command', 'user_join', 'user_leave')", name='ck_auto_event'),
        sa.CheckConstraint("action_type IN ('reply', 'ai', 'note', 'schedule', 'notify', 'guard', 'backup', 'autopost')", name='ck_auto_action'),
    )

    # Settings (Key-Value)
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(64), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_settings_key'),
    )


def downgrade() -> None:
    op.drop_table('settings')
    op.drop_table('automation_rules')
    op.drop_table('ai_memory')
    op.drop_table('user_profiles')
    op.drop_table('notification_rules')
    op.drop_table('inbox_items')