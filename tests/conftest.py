"""
راه‌اندازیِ مشترکِ تست‌ها.

دو نوع تست داریم:
  ۱) تست‌های ساده (بدون نیاز به دیتابیس واقعی) - همیشه اجرا می‌شن.
  ۲) تست‌های Database/Repository/Migration/Backup - نیاز به یک PostgreSQL
     واقعیِ *تست* دارن (نه دیتابیس اصلیِ سلف‌بات!). این‌ها با مارکر
     `requires_db` علامت خوردن و فقط وقتی SELFBOT_TEST_DATABASE_URL ست شده
     باشه اجرا می‌شن؛ در غیر این‌صورت skip می‌شن (نه fail).

برای اجرای کامل:
    export SELFBOT_TEST_DATABASE_URL=postgresql://user:pass@localhost/selfbot_test
    alembic upgrade head   # (روی همون دیتابیسِ تست)
    pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# مقادیر بی‌خطر برای import شدنِ bot.config بدون داشتن اکانتِ واقعیِ تلگرام
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "test_hash")
os.environ.setdefault("PREFIX", ".")

_TEST_DB_URL = os.getenv("SELFBOT_TEST_DATABASE_URL")
if _TEST_DB_URL:
    # روی یک دیتابیسِ تستِ واقعی اجرا می‌شه
    os.environ["DATABASE_URL"] = _TEST_DB_URL
else:
    # فقط برای اینکه import ماژول‌های bot.db/bot.repositories خطا نده؛ این
    # آدرس هیچ‌وقت واقعاً connect نمی‌شه چون تست‌های requires_db skip می‌شن.
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://placeholder:placeholder@localhost/placeholder"
    )

import pytest  # noqa: E402

requires_db = pytest.mark.skipif(
    not _TEST_DB_URL,
    reason=(
        "برای اجرای تست‌های دیتابیس، متغیر محیطی SELFBOT_TEST_DATABASE_URL رو "
        "روی یک دیتابیس PostgreSQL تستِ واقعی (نه دیتابیس اصلی!) ست کن و "
        "`alembic upgrade head` رو روش اجرا کن."
    ),
)


@pytest.fixture(autouse=True)
async def _clean_tables():
    """قبل و بعد از هر تستِ DB، جدول‌های استفاده‌شده رو خالی می‌کنه تا تست‌ها مستقل باشن."""
    if not _TEST_DB_URL:
        yield
        return

    from bot.db import models
    from bot.db.engine import session_scope

    async def _truncate():
        async with session_scope() as session:
            for model in (
                models.Note,
                models.AssistantChatRule,
                models.AutopostChat,
                models.StatsCommandCount,
                models.StatsChatCount,
                models.ScheduledJob,
                models.GroupGuardSettings,
            ):
                await session.execute(model.__table__.delete())
            for model in (
                models.AssistantSettings,
                models.AutopostSettings,
                models.FontSettings,
                models.ClockSettings,
                models.StatsSummary,
            ):
                await session.execute(model.__table__.delete())

    await _truncate()
    yield
    await _truncate()
