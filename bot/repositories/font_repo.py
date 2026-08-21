"""Repository لایه‌ی فونتِ خودکار."""
from ..db.engine import session_scope
from ..db.models import FontSettings


async def _get_or_create(session) -> FontSettings:
    obj = await session.get(FontSettings, 1)
    if obj is None:
        obj = FontSettings(id=1)
        session.add(obj)
        await session.flush()
    return obj


async def get_settings() -> FontSettings:
    async with session_scope() as session:
        return await _get_or_create(session)


async def save_settings(*, enabled: bool, style: str) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session)
        obj.enabled = enabled
        obj.style = style
