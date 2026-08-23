"""Repository لایه‌ی «مدیریت گروه پیشرفته» (فیلترلینک + خوش‌آمدگویی)، به‌ازای هر گروه."""
from sqlalchemy import select

from ..db.engine import session_scope
from ..db.models import GroupGuardSettings


async def _get_or_create(session, chat_id: int) -> GroupGuardSettings:
    obj = await session.get(GroupGuardSettings, chat_id)
    if obj is None:
        obj = GroupGuardSettings(chat_id=chat_id)
        session.add(obj)
        await session.flush()
    return obj


async def list_all() -> list[GroupGuardSettings]:
    async with session_scope() as session:
        rows = (await session.execute(select(GroupGuardSettings))).scalars().all()
        return [
            GroupGuardSettings(
                chat_id=r.chat_id,
                link_filter_enabled=r.link_filter_enabled,
                welcome_enabled=r.welcome_enabled,
                welcome_text=r.welcome_text,
                porn_filter_enabled=r.porn_filter_enabled,
                spam_filter_enabled=r.spam_filter_enabled,
            )
            for r in rows
        ]


async def set_link_filter(chat_id: int, enabled: bool) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session, chat_id)
        obj.link_filter_enabled = enabled


async def set_porn_filter(chat_id: int, enabled: bool) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session, chat_id)
        obj.porn_filter_enabled = enabled


async def set_spam_filter(chat_id: int, enabled: bool) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session, chat_id)
        obj.spam_filter_enabled = enabled


async def set_welcome(
    chat_id: int, *, enabled: bool | None = None, text: str | None = None
) -> None:
    """
    enabled=None یعنی «روشن/خاموش‌بودن رو دست نزن»، فقط اگه text داده شده باشه
    آپدیتش کن (و برعکس) - چون `.خوش‌آمد متن ...` و `.خوش‌آمد روشن/خاموش`
    دو دستورِ جدا هستن و نباید همدیگه رو overwrite کنن.
    """
    async with session_scope() as session:
        obj = await _get_or_create(session, chat_id)
        if enabled is not None:
            obj.welcome_enabled = enabled
        if text is not None:
            obj.welcome_text = text
