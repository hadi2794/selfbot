"""
مدل‌های مربوط به موتور اتوماسیون (قوانین شرطی).

هر قانون شامل:
- نام و توضیح
- شرط (نوع رویداد، فیلترها)
- عمل (نوع عمل، پارامترها)
- وضعیت (فعال/غیرفعال)
- زمان‌بندی (اختیاری)
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AutomationRule(Base):
    """قانون اتوماسیون - شرط و عمل."""

    __tablename__ = "automation_rules"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="ck_automation_rules_status"
        ),
        CheckConstraint(
            "trigger_type IN ('message', 'command', 'event', 'schedule', 'mention', 'join')",
            name="ck_automation_rules_trigger"
        ),
        CheckConstraint(
            "action_type IN ('reply', 'message', 'note', 'reminder', 'assistant', 'autopost', 'backup', 'stats', 'ai', 'webhook')",
            name="ck_automation_rules_action"
        ),
        Index("ix_automation_rules_status", "status"),
        Index("ix_automation_rules_trigger_type", "trigger_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    
    # شرط
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)  # message, command, event, schedule, mention, join
    trigger_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"pattern": "...", "chat_id": 123, "sender_id": 456}
    
    # عمل
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)  # reply, message, note, reminder, assistant, autopost, backup, stats, ai, webhook
    action_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"text": "...", "delay": 5, "target": "..."}
    
    # زمان‌بندی (برای trigger_type = schedule)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "0 9 * * *" یا "every 5 minutes"
    schedule_timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "Asia/Tehran"
    
    # محدودیت‌ها
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # حداقل فاصله بین اجراها
    max_executions: Mapped[int | None] = mapped_column(Integer, nullable=True)  # حداکثر تعداد اجرا (None = نامحدود)
    executions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # آخرین اجرا
    last_executed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AutomationRule id={self.id} name={self.name} status={self.status}>"