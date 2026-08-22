"""
Health Monitor - وضعیت سنجی تمام بخش‌های سلف‌بات.

نمایش وضعیت هر Worker و سرویس متصل (Telegram, PostgreSQL, AI, Scheduler, Autopost, Assistant, Statistics).
"""

import time
import logging
from typing import Dict, Any, Optional

from sqlalchemy import text

from . import runtime, config
from .db.engine import session_scope
from .db.models import StatsSummary, ScheduledJob

logger = logging.getLogger("selfbot.health")

# ذخیره آخرین وضعیت هر سرویس برای تشخیص تغییرات
_last_health: Dict[str, Any] = {}
_worker_status: Dict[str, Dict[str, Any]] = {}


def get_uptime() -> str:
    """زمان اجرای سلف‌بات از شروع."""
    elapsed = time.time() - runtime.START_TIME
    days = int(elapsed // 86400)
    hours = int((elapsed % 86400) // 3600)
    minutes = int((elapsed % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"


def format_status(status: bool) -> str:
    return "🟢 OK" if status else "🔴 FAIL"


async def check_telegram() -> bool:
    """بررسی اتصال به تلگرام با ارسال درخواست ساده."""
    try:
        me = await runtime.client.get_me()
        return me is not None
    except Exception:
        return False


async def check_postgresql() -> bool:
    """بررسی اتصال به PostgreSQL."""
    try:
        async with session_scope() as session:
            # یک کوئری ساده برای تست اتصال
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False


async def check_ai() -> bool:
    """بررسی در دسترس‌بودن سرویس AI (فقط اگه API Key تنظیم شده)."""
    if not config.AI_API_KEY:
        return True  # غیرفعال ولی مشکل نداره
    try:
        from . import ai
        # یک درخواست کوچک برای تست
        await ai.ask_ai(
            [{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return True
    except Exception:
        return False


async def check_scheduler() -> bool:
    """بررسی Worker زمان‌بند (با چک کردن آخرین اجرا)."""
    info = _worker_status.get("scheduler", {})
    last_run = info.get("last_run")
    if last_run is None:
        return False
    # اگر بیش از 5 دقیقه از آخرین اجرا گذشته، احتمالاً مشکل داره
    if time.time() - last_run > 300:
        return False
    return True


async def check_autopost() -> bool:
    """بررسی Worker ارسال‌خودکار."""
    info = _worker_status.get("autopost", {})
    last_run = info.get("last_run")
    if last_run is None:
        return False
    if time.time() - last_run > 300:
        return False
    return True


async def check_assistant() -> bool:
    """بررسی Worker منشی."""
    info = _worker_status.get("assistant", {})
    last_run = info.get("last_run")
    if last_run is None:
        return False
    if time.time() - last_run > 300:
        return False
    return True


async def check_stats() -> bool:
    """بررسی Worker آمار."""
    info = _worker_status.get("stats", {})
    last_run = info.get("last_run")
    if last_run is None:
        return False
    if time.time() - last_run > 300:
        return False
    return True


async def get_health_report() -> Dict[str, Any]:
    """گزارش کامل وضعیت سلامت."""
    results = {
        "telegram": await check_telegram(),
        "postgresql": await check_postgresql(),
        "ai": await check_ai(),
        "scheduler": await check_scheduler(),
        "autopost": await check_autopost(),
        "assistant": await check_assistant(),
        "stats": await check_stats(),
    }

    # محاسبه تعداد سرویس‌های سبز
    ok_count = sum(1 for v in results.values() if v)
    total = len(results)

    return {
        "status": results,
        "summary": f"{ok_count}/{total} OK",
        "uptime": get_uptime(),
        "timestamp": time.time(),
    }


def format_health_report(report: Dict[str, Any]) -> str:
    """تبدیل گزارش به متن زیبا برای نمایش در تلگرام."""
    lines = ["📊 **وضعیت سلامت**"]
    lines.append(f"⏱ **Uptime:** {report['uptime']}")
    lines.append(f"📈 **خلاصه:** {report['summary']}")
    lines.append("")

    status_map = {
        "telegram": "Telegram",
        "postgresql": "PostgreSQL",
        "ai": "AI",
        "scheduler": "Scheduler",
        "autopost": "Autopost",
        "assistant": "Assistant",
        "stats": "Statistics",
    }

    for key, display in status_map.items():
        ok = report["status"].get(key, False)
        icon = "🟢" if ok else "🔴"
        lines.append(f"{icon} **{display}**")

    # اضافه کردن اطلاعات دقیق‌تر برای Workerهای خراب
    if not report["status"].get("scheduler"):
        info = _worker_status.get("scheduler", {})
        if info.get("last_error"):
            lines.append(f"   └ آخرین خطا: {info['last_error'][:100]}")
        if info.get("last_run"):
            elapsed = time.time() - info["last_run"]
            lines.append(f"   └ آخرین اجرا: {int(elapsed)} ثانیه پیش")

    return "\n".join(lines)


def update_worker_status(worker_name: str, status: str, error: Optional[str] = None):
    """
    به‌روزرسانی وضعیت یک Worker.
    توسط خود Workerها صدا زده می‌شه.
    """
    now = time.time()
    if worker_name not in _worker_status:
        _worker_status[worker_name] = {}

    _worker_status[worker_name]["last_run"] = now
    _worker_status[worker_name]["status"] = status
    if error:
        _worker_status[worker_name]["last_error"] = error
        _worker_status[worker_name]["error_count"] = _worker_status[worker_name].get("error_count", 0) + 1
    else:
        _worker_status[worker_name]["error_count"] = 0