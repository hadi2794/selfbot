"""Repository لایه‌ی خلاصه‌ی روزانه (`.خلاصه‌روز`): تنظیماتِ کلی + لیستِ چت‌های سفارشی."""
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db.engine import session_scope
from ..db.models import DailyDigestChat, DailyDigestSettings


async def _get_or_create(session) -> DailyDigestSettings:
    obj = await session.get(DailyDigestSettings, 1)
    if obj is None:
        obj = DailyDigestSettings(id=1)
        session.add(obj)
        await session.flush()
    return obj


async def get_settings() -> DailyDigestSettings:
    async with session_scope() as session:
        return await _get_or_create(session)


async def save_settings(
    *, enabled: bool, mode: str, hour: int, minute: int, last_run_date: str | None
) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session)
        obj.enabled = enabled
        obj.mode = mode
        obj.hour = hour
        obj.minute = minute
        obj.last_run_date = last_run_date


async def list_chats() -> dict:
    """chat_id (رشته) -> title"""
    async with session_scope() as session:
        rows = (await session.execute(select(DailyDigestChat))).scalars().all()
        return {str(row.chat_id): row.title for row in rows}


async def upsert_chat(chat_id: int, title: str) -> None:
    async with session_scope() as session:
        stmt = pg_insert(DailyDigestChat).values(chat_id=chat_id, title=title)
        stmt = stmt.on_conflict_do_update(
            index_elements=[DailyDigestChat.chat_id], set_={"title": title}
        )
        await session.execute(stmt)


async def remove_chat(chat_id: int) -> None:
    async with session_scope() as session:
        await session.execute(delete(DailyDigestChat).where(DailyDigestChat.chat_id == chat_id))


async def clear_chats() -> None:
    async with session_scope() as session:
        await session.execute(delete(DailyDigestChat))
