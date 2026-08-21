"""
آمار سلف‌بات - PostgreSQL از طریق Repository Layer.

به‌خاطر اینکه record_message/record_command روی *هر* پیام اجرا می‌شن، این
توابع سینک و فقط روی دیکشنریِ درون‌حافظه‌یِ STATS کار می‌کنن (دقیقاً مثل قبل)
تا هیچ query اضافه‌ای به دیتابیس زده نشه. فقط init_stats()/save_stats()/
reset_stats() با PostgreSQL صحبت می‌کنن.
"""
import logging

from ..repositories import stats_repo
from ..utils import ALL_COMMAND_NAMES

logger = logging.getLogger("selfbot.storage.stats_store")

_DEFAULT = {
    "commands_total": 0,
    "commands_by_name": {},  # نام فارسی دستور -> تعداد اجرا
    "messages_total": 0,  # همه‌ی پیام‌های دیده‌شده (ورودی+خروجی)
    "autopost_ok": 0,
    "autopost_fail": 0,
    "errors": 0,  # فقط خطاهای سیستمی/پس‌زمینه، نه خطاهای ورودی کاربر
    "per_chat": {},  # chat_id (رشته) -> {"messages": n, "commands": n, "title": ...}
}

STATS = dict(_DEFAULT)
STATS["commands_by_name"] = {}
STATS["per_chat"] = {}


async def init_stats() -> None:
    """موقع استارتاپ، آخرین اسنپ‌شاتِ ذخیره‌شده در PostgreSQL رو در STATS بارگذاری می‌کنه."""
    snapshot = await stats_repo.get_snapshot()
    STATS.update(snapshot)


async def save_stats() -> None:
    """اسنپ‌شاتِ فعلیِ STATS رو یک‌جا و اتمیک (یک تراکنش) در PostgreSQL ذخیره می‌کنه."""
    try:
        await stats_repo.save_snapshot(STATS)
    except Exception:
        logger.exception("خطا در ذخیره‌ی آمار")


async def reset_stats() -> None:
    STATS.update(
        {
            "commands_total": 0,
            "commands_by_name": {},
            "messages_total": 0,
            "autopost_ok": 0,
            "autopost_fail": 0,
            "errors": 0,
            "per_chat": {},
        }
    )
    await stats_repo.reset()


def chat_stats(chat_id):
    key = str(chat_id)
    return STATS["per_chat"].setdefault(key, {"messages": 0, "commands": 0, "title": None})


def record_error():
    STATS["errors"] += 1


def record_message(event):
    STATS["messages_total"] += 1
    chat_stats(event.chat_id)["messages"] += 1


def record_command(event, raw_name):
    canonical = ALL_COMMAND_NAMES.get(raw_name)
    if not canonical:
        return  # پیامی که با پیشوند شروع می‌شه ولی دستور واقعی نیست (تایپ اشتباه)
    STATS["commands_total"] += 1
    STATS["commands_by_name"][canonical] = STATS["commands_by_name"].get(canonical, 0) + 1
    chat_stats(event.chat_id)["commands"] += 1
