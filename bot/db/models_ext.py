"""
مدل‌های جدید برای قابلیت‌های افزوده‌شده:
- Inbox (صندوق ورودی هوشمند)
- Notification Rules (قوانین اعلان)
- User Profiles (پروفایل کاربران با برچسب‌ها)
- AI Memory (حافظه‌ی هوش مصنوعی)
- Automation Rules (موتور اتوماسیون)
- Settings (تنظیمات یکپارچه)
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


# ------------------------------------------------------------- Inbox ---
class InboxItem(Base):
    """هر پیام ذخیره‌شده در صندوق ورودی."""

    __tablename__ = "inbox_items"
    __table_args__ = (
        Index("ix_inbox_items_chat_id", "chat_id"),
        Index("ix_inbox_items_read", "read"),
        Index("ix_inbox_items_importance", "importance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    sender_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=normal, 1=important, 2=high
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # منحصربه‌فرد بودن (chat_id, message_id) برای جلوگیری از دوتا شدن
    __table_args__ = __table_args__ + (
        UniqueConstraint("chat_id", "message_id", name="uq_inbox_chat_message"),
    )


# ----------------------------------------------------- Notification Rules ---
class NotificationRule(Base):
    """قانون اعلان: شرط + عمل."""

    __tablename__ = "notification_rules"
    __table_args__ = (
        CheckConstraint("trigger_type IN ('message', 'keyword', 'user', 'time')", name="ck_notif_trigger_type"),
        CheckConstraint("action_type IN ('notify', 'save', 'forward', 'reply')", name="ck_notif_action_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON یا متن شرط
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # پارامترهای عمل
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- User Profile ---
class UserProfile(Base):
    """اطلاعات تکمیلی کاربران (برچسب‌ها، یادداشت‌ها، VIP بودن)."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        Index("ix_user_profiles_user_id", "user_id"),
        Index("ix_user_profiles_tags", "tags"),  # for search
    )

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated: VIP, مشتری قدیمی, ...
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_vip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    added_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------------------------------------------------------- AI Memory ---
class AIMemory(Base):
    """حافظه‌ی هوش مصنوعی با دسته‌بندی."""

    __tablename__ = "ai_memory"
    __table_args__ = (
        Index("ix_ai_memory_category", "category"),
        Index("ix_ai_memory_key", "key"),
        UniqueConstraint("category", "key", name="uq_ai_memory_cat_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # کاربران, گفتگوها, پروژه‌ها, یادداشت‌ها, تنظیمات
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- Automation Rules ---
class AutomationRule(Base):
    """قوانین اتوماسیون: Event + Condition + Action."""

    __tablename__ = "automation_rules"
    __table_args__ = (
        CheckConstraint("event_type IN ('message', 'schedule', 'command', 'user_join', 'user_leave')", name="ck_auto_event"),
        CheckConstraint("action_type IN ('reply', 'ai', 'note', 'schedule', 'notify', 'guard', 'backup', 'autopost')", name="ck_auto_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # پارامترهای رویداد (JSON)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)  # شرط (مثلاً "keyword in message")
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action_value: Mapped[str] = mapped_column(Text, nullable=False)  # پارامترهای عمل (JSON)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ------------------------------------------------------- Unified Settings (Key-Value) ---
class Setting(Base):
    """تنظیمات یکپارچه (key-value) برای هر چیزی که جدول خاص ندارد."""

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_settings_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

# ------------------------------------------------------------ Hafez Poems ---
class HafezPoem(Base):
    """
    دیوانِ حافظ (برای `.فال`) - یک‌بار با `scripts/seed_hafez.py` پر می‌شه و
    بعدش هندلر فقط از همین جدول یه ردیفِ رندوم می‌خونه؛ در زمانِ اجرایِ ربات
    هیچ پکیج/شبکه‌ی اضافه‌ای لازم نیست (برخلافِ نسخه‌ی قبلی که با پکیجِ
    `hafez` در همون لحظه import می‌شد).
    """

    __tablename__ = "hafez_poems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # همون poem_id گنجور/hafez
    poem: Mapped[str] = mapped_column(Text, nullable=False)  # ابیات، هر مصرع در یک خط
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
