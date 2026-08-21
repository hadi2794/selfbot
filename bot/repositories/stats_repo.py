"""
Repository لایه‌ی آمار.

به‌خاطر حجمِ بالای پیام‌ها (stats_collector روی *هر* پیام اجرا می‌شه)، شمارنده‌ها
در حافظه (bot/storage/stats_store.py -> STATS) نگه داشته می‌شن تا هیچ query
اضافه‌ای روی هر پیام به دیتابیس زده نشه؛ فقط save_snapshot() (که هر
STATS_SAVE_INTERVAL ثانیه، یا با دستور `.آمار`/`.آمار بازنشانی` صدا زده می‌شه)
با دیتابیس صحبت می‌کنه - و این کار همیشه داخل یک تراکنشِ واحد (atomic) انجام
می‌شه: یا کل اسنپ‌شات ذخیره می‌شه، یا (در صورت خطا) هیچی، و آمار هیچ‌وقت
نصفه‌ونیمه روی دیسک نمی‌مونه.
"""
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db.engine import session_scope
from ..db.models import StatsChatCount, StatsCommandCount, StatsSummary


async def _get_or_create_summary(session) -> StatsSummary:
    obj = await session.get(StatsSummary, 1)
    if obj is None:
        obj = StatsSummary(id=1)
        session.add(obj)
        await session.flush()
    return obj


async def get_snapshot() -> dict:
    async with session_scope() as session:
        summary = await _get_or_create_summary(session)
        commands = (await session.execute(select(StatsCommandCount))).scalars().all()
        chats = (await session.execute(select(StatsChatCount))).scalars().all()
        return {
            "commands_total": summary.commands_total,
            "messages_total": summary.messages_total,
            "autopost_ok": summary.autopost_ok,
            "autopost_fail": summary.autopost_fail,
            "errors": summary.errors,
            "commands_by_name": {c.command_name: c.count for c in commands},
            "per_chat": {
                str(c.chat_id): {"messages": c.messages, "commands": c.commands, "title": c.title}
                for c in chats
            },
        }


async def save_snapshot(stats: dict) -> None:
    """اسنپ‌شات کاملِ STATS رو در یک تراکنشِ واحد (atomic) ذخیره می‌کنه."""
    async with session_scope() as session:
        summary = await _get_or_create_summary(session)
        summary.commands_total = stats["commands_total"]
        summary.messages_total = stats["messages_total"]
        summary.autopost_ok = stats["autopost_ok"]
        summary.autopost_fail = stats["autopost_fail"]
        summary.errors = stats["errors"]

        for name, count in stats["commands_by_name"].items():
            stmt = pg_insert(StatsCommandCount).values(command_name=name, count=count)
            stmt = stmt.on_conflict_do_update(
                index_elements=[StatsCommandCount.command_name], set_={"count": count}
            )
            await session.execute(stmt)

        for chat_id_str, info in stats["per_chat"].items():
            stmt = pg_insert(StatsChatCount).values(
                chat_id=int(chat_id_str),
                messages=info.get("messages", 0),
                commands=info.get("commands", 0),
                title=info.get("title"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[StatsChatCount.chat_id],
                set_={
                    "messages": info.get("messages", 0),
                    "commands": info.get("commands", 0),
                    "title": info.get("title"),
                },
            )
            await session.execute(stmt)


async def reset() -> None:
    async with session_scope() as session:
        summary = await _get_or_create_summary(session)
        summary.commands_total = 0
        summary.messages_total = 0
        summary.autopost_ok = 0
        summary.autopost_fail = 0
        summary.errors = 0
        await session.execute(delete(StatsCommandCount))
        await session.execute(delete(StatsChatCount))
