"""Repository لایه‌ی یادداشت‌ها."""
from sqlalchemy import select

from ..db.engine import session_scope
from ..db.models import Note


async def get_all() -> dict:
    async with session_scope() as session:
        rows = (await session.execute(select(Note))).scalars().all()
        return {row.key: row.text for row in rows}


async def get_one(key: str) -> str | None:
    async with session_scope() as session:
        obj = await session.get(Note, key)
        return obj.text if obj else None


async def upsert(key: str, text: str) -> None:
    async with session_scope() as session:
        obj = await session.get(Note, key)
        if obj is not None:
            obj.text = text
        else:
            session.add(Note(key=key, text=text))


async def delete_note(key: str) -> bool:
    async with session_scope() as session:
        obj = await session.get(Note, key)
        if obj is None:
            return False
        await session.delete(obj)
        return True
