"""
Schema PostgreSQL برای همه‌ی داده‌های دائمیِ سلف‌بات.

جدول‌های «تک‌ردیفی» (Settings) با الگوی id=1 + CheckConstraint("id = 1")
پیاده شدن: چون این بخش‌ها (منشی/ارسال‌خودکار/فونت/ساعت/خلاصه‌ی آمار) در طرح
JSON قبلی هم یک آبجکت واحد بودن، نه چندین رکورد. این کار باعث می‌شه واکشی و
آپدیت این تنظیمات همیشه با یک PRIMARY KEY lookup ساده (سریع‌ترین حالت ممکن)
انجام بشه.

جدول‌های چندردیفی (Notes، لیست چت‌های ارسال‌خودکار، قوانین چت‌به‌چتِ منشی،
شمارنده‌های آمار) روی کلید طبیعی‌شون (key / chat_id / command_name) Unique
Constraint یا Primary Key دارن تا از رکورد تکراری جلوگیری بشه.
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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- Notes ---
class Note(Base):
    """یادداشت‌ها: `.یادداشت key متن`"""

    __tablename__ = "notes"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ----------------------------------------------------------- Assistant ---
class AssistantSettings(Base):
    """تنظیماتِ کلیِ منشیِ چت (تک‌ردیفی، id ثابت = 1)."""

    __tablename__ = "assistant_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_assistant_settings_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="mention")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    auto_detect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    manual_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # لایه‌ی زمان‌بندی (پنجره‌های AssistantScheduleWindow پایین) کلاً فعال/غیرفعاله؛
    # False یعنی پنجره‌ها پاک نمی‌شن ولی موقتاً بی‌اثرن (بدونِ نیاز به دوباره تعریف‌کردنشون).
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AssistantChatRule(Base):
    """
    «Chat Settings» ی منشی: لیست چت‌های مستثنی/همیشه‌فعال (include/exclude).
    هر چت فقط می‌تونه یکی از این دو قانون رو داشته باشه (دقیقاً مثل رفتار
    قبلیِ کد که با discard از لیست مقابل این انحصار رو تضمین می‌کرد) - این
    الزام با UniqueConstraint روی chat_id تضمین می‌شه.
    """

    __tablename__ = "assistant_chat_rules"
    __table_args__ = (
        UniqueConstraint("chat_id", name="uq_assistant_chat_rules_chat_id"),
        CheckConstraint("rule IN ('include', 'exclude')", name="ck_assistant_chat_rules_rule"),
        Index("ix_assistant_chat_rules_chat_id", "chat_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rule: Mapped[str] = mapped_column(String(8), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AssistantScheduleWindow(Base):
    """
    پنجره‌های زمانیِ ثابتِ «حتماً آفلاین»ِ منشیِ خودکار (مثلاً ساعتِ خواب یا
    ساعتِ کاری): در این بازه‌ها، صرف‌نظر از فعالیتِ اخیرِ خودت، منشی روشن
    می‌مونه - در کنارِ تشخیصِ رفتاریِ قبلی، نه به‌جاش (نگاهِ کاملِ منطق توی
    bot/handlers/assistant.py، تابعِ _recompute_enabled_from_signals).

    با start_minute/end_minute (دقیقه از نیمه‌شب، ۰ تا ۱۴۳۹) ذخیره می‌شن، نه
    sa.Time، تا محاسبه‌ی «الان توی بازه‌ام؟» یه مقایسه‌ی عددیِ ساده بمونه و
    درگیرِ تبدیل‌های timezone/DST نشه (پروژه از همون الگوی TIMEZONE_OFFSET
    استفاده می‌کنه که scheduler.py/daily_digest.py هم استفاده می‌کنن). اگه end_minute از
    start_minute کمتر باشه یعنی بازه از نیمه‌شب رد می‌شه (مثلاً خواب: ۲۳:۰۰
    تا ۰۸:۰۰) - این حالت مجازه و توی کدِ تشخیص جداگانه handle می‌شه.
    """

    __tablename__ = "assistant_schedule_windows"
    __table_args__ = (
        CheckConstraint("start_minute >= 0 AND start_minute < 1440", name="ck_assistant_window_start_range"),
        CheckConstraint("end_minute >= 0 AND end_minute < 1440", name="ck_assistant_window_end_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    start_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    end_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)


# ------------------------------------------------------------ Autopost ---
class AutopostSettings(Base):
    """تنظیماتِ کلیِ ارسال‌خودکار (تک‌ردیفی، id ثابت = 1)."""

    __tablename__ = "autopost_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_autopost_settings_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AutopostChat(Base):
    """لیستِ چت‌های مقصدِ ارسال‌خودکار."""

    __tablename__ = "autopost_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)


# ---------------------------------------------------------------- Font ---
class FontSettings(Base):
    """وضعیتِ فونتِ خودکار (تک‌ردیفی، id ثابت = 1)."""

    __tablename__ = "font_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_font_settings_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    style: Mapped[str] = mapped_column(String(32), nullable=False, default="bold")


# --------------------------------------------------- Clock / Profile ---
class ClockSettings(Base):
    """ساعتِ زنده در نامِ پروفایل (تک‌ردیفی، id ثابت = 1)."""

    __tablename__ = "clock_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_clock_settings_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    style: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    base_name: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------- Statistics ---
class StatsSummary(Base):
    """شمارنده‌های کلیِ آمار (تک‌ردیفی، id ثابت = 1)."""

    __tablename__ = "stats_summary"
    __table_args__ = (CheckConstraint("id = 1", name="ck_stats_summary_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    commands_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    messages_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    autopost_ok: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    autopost_fail: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StatsCommandCount(Base):
    """تعداد اجرای هر دستور (نامِ فارسیِ کانونیکال -> تعداد)."""

    __tablename__ = "stats_command_counts"

    command_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class StatsChatCount(Base):
    """آمار به‌تفکیکِ هر چت."""

    __tablename__ = "stats_chat_counts"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    messages: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    commands: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)


# ----------------------------------------------------- Group Guard ---
class GroupGuardSettings(Base):
    """
    تنظیماتِ «مدیریت گروه پیشرفته» به‌ازای هر گروه: فیلترلینک (حذف خودکار
    پیام‌های حاویِ لینک از غیرادمین‌ها)، خوش‌آمدگویی (پیام خودکار برای عضو
    جدید)، فیلترِ پورن (تحلیلِ تصویر با AI) و فیلترِ اسپم (فلاد/تکرارِ پیام).
    همه‌شون روی یک ردیف/گروه (chat_id) نگه داشته می‌شن چون همه «تنظیماتِ
    همون گروه» هستن، نه رکوردهای مستقل.
    """

    __tablename__ = "group_guard_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    link_filter_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    welcome_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    porn_filter_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    spam_filter_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ----------------------------------------------------- Daily Digest ---
class DailyDigestSettings(Base):
    """
    تنظیماتِ کلیِ `.خلاصه‌روز` (تک‌ردیفی، id ثابت = 1). هر شب سرِ
    hour:minute (به‌وقتِ محلی) یه خلاصه از فعالیتِ همون روز به Saved
    Messages فرستاده می‌شه - یا از «تمامِ چت‌ها» (mode=all) یا فقط از
    چت‌های انتخابیِ کاربر (mode=custom، توی جدولِ DailyDigestChat).

    last_run_date به‌صورتِ رشته‌ی `YYYY-MM-DD` (بر پایه‌ی زمانِ محلی)
    ذخیره می‌شه تا اگه پروسه چندبار توی همون دقیقه/بعد از ری‌استارت چک
    کرد، خلاصه دوبار برای یه روز ارسال نشه.
    """

    __tablename__ = "daily_digest_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_daily_digest_settings_singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="all")  # all | custom
    hour: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=23)
    minute: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_run_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DailyDigestChat(Base):
    """لیستِ چت/گروه/کانال‌های انتخابی برای حالتِ سفارشیِ `.خلاصه‌روز`."""

    __tablename__ = "daily_digest_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)


# --------------------------------------------------------- Scheduler ---
class ScheduledJob(Base):
    """
    کارهای زمان‌بندی‌شده: هم `.زمان‌بند` (ارسال متن به یه چت در آینده) و هم
    `.یادآوری` (که فقط یه zمان‌بندِ مقصدش همیشه خودِ owner/Saved Messages ست)
    از همین یک جدول استفاده می‌کنن؛ ستونِ kind فقط برای نمایش/فیلترِ لیست به
    کار می‌ره، منطق اجرا برای هر دو یکیه.

    run_at با timezone (UTC) ذخیره می‌شه تا مستقل از TIMEZONE_OFFSET همیشه
    قابل مقایسه‌ی درست با now باشه؛ تبدیل به وقتِ محلی فقط موقع نمایش انجام
    می‌شه (دقیقاً مثل الگوی clock.py).
    """

    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('schedule', 'reminder')", name="ck_scheduled_jobs_kind"),
        Index("ix_scheduled_jobs_run_at", "run_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    run_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="schedule")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
