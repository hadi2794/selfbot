"""
دستور .سلامت - نمایش وضعیت سرویس‌ها و uptime
"""
import logging

from telethon import events

from .. import health
from ..config import PREFIX
from ..runtime import client
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.health")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["سلامت", "health"])))
async def health_handler(event):
    """نمایش وضعیت سلامت تمام سرویس‌ها."""
    await event.edit("🔄 در حال بررسی وضعیت سرویس‌ها...")

    try:
        report = await health.get_health_report()
        formatted = health.format_health_report(report)
        await event.edit(formatted)
    except Exception as e:
        logger.exception("خطا در بررسی سلامت")
        await event.edit(f"❌ خطا در بررسی سلامت: {e}")