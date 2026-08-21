"""Repository لایه‌ی ساعتِ زنده/پروفایل."""
from ..db.engine import session_scope
from ..db.models import ClockSettings


async def _get_or_create(session) -> ClockSettings:
    obj = await session.get(ClockSettings, 1)
    if obj is None:
        obj = ClockSettings(id=1)
        session.add(obj)
        await session.flush()
    return obj


async def get_settings() -> ClockSettings:
    async with session_scope() as session:
        return await _get_or_create(session)


async def save_settings(*, enabled: bool, style: str, base_name: str | None) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session)
        obj.enabled = enabled
        obj.style = style
        obj.base_name = base_name
