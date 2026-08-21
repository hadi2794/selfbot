"""Repository لایه‌ی ارسالِ خودکار (تنظیمات کلی + لیست چت‌های مقصد)."""
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db.engine import session_scope
from ..db.models import AutopostChat, AutopostSettings


async def _get_or_create(session) -> AutopostSettings:
    obj = await session.get(AutopostSettings, 1)
    if obj is None:
        obj = AutopostSettings(id=1)
        session.add(obj)
        await session.flush()
    return obj


async def get_settings() -> AutopostSettings:
    async with session_scope() as session:
        return await _get_or_create(session)


async def save_settings(*, enabled: bool, interval_minutes: int, text: str) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session)
        obj.enabled = enabled
        obj.interval_minutes = interval_minutes
        obj.text = text


async def list_chats() -> dict:
    """chat_id (رشته) -> title ، دقیقاً هم‌شکل با ساختار قبلیِ JSON."""
    async with session_scope() as session:
        rows = (await session.execute(select(AutopostChat))).scalars().all()
        return {str(row.chat_id): row.title for row in rows}


async def upsert_chat(chat_id: int, title: str) -> None:
    async with session_scope() as session:
        stmt = pg_insert(AutopostChat).values(chat_id=chat_id, title=title)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AutopostChat.chat_id], set_={"title": title}
        )
        await session.execute(stmt)


async def remove_chat(chat_id: int) -> None:
    async with session_scope() as session:
        await session.execute(delete(AutopostChat).where(AutopostChat.chat_id == chat_id))


async def clear_chats() -> None:
    async with session_scope() as session:
        await session.execute(delete(AutopostChat))
