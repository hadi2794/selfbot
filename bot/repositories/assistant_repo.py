"""Repository لایه‌ی منشیِ چت (تنظیمات کلی + قوانین چت‌به‌چت + پنجره‌های زمان‌بندی)."""
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db.engine import session_scope
from ..db.models import AssistantChatRule, AssistantScheduleWindow, AssistantSettings


async def _get_or_create(session) -> AssistantSettings:
    obj = await session.get(AssistantSettings, 1)
    if obj is None:
        obj = AssistantSettings(id=1)
        session.add(obj)
        await session.flush()
    return obj


async def get_settings() -> AssistantSettings:
    async with session_scope() as session:
        return await _get_or_create(session)


async def save_settings(
    *,
    mode: str,
    text: str,
    delay_seconds: int,
    auto_detect: bool,
    manual_enabled: bool,
    ai_mode: bool = False,
    schedule_enabled: bool = True,
) -> None:
    async with session_scope() as session:
        obj = await _get_or_create(session)
        obj.mode = mode
        obj.text = text
        obj.delay_seconds = delay_seconds
        obj.auto_detect = auto_detect
        obj.manual_enabled = manual_enabled
        obj.ai_mode = ai_mode
        obj.schedule_enabled = schedule_enabled


async def list_chat_rules() -> dict:
    """chat_id (int) -> 'include' | 'exclude'"""
    async with session_scope() as session:
        rows = (await session.execute(select(AssistantChatRule))).scalars().all()
        return {row.chat_id: row.rule for row in rows}


async def replace_chat_rules(*, include: set, exclude: set) -> None:
    """
    کل جدولِ قوانینِ چت رو با include/exclude فعلی جایگزین می‌کنه - همه در یک
    تراکنش (atomic): یا کامل اعمال می‌شه یا هیچی، هیچ‌وقت نصفه‌ونیمه نمی‌مونه.
    """
    async with session_scope() as session:
        await session.execute(delete(AssistantChatRule))
        rows = [{"chat_id": cid, "rule": "include"} for cid in include] + [
            {"chat_id": cid, "rule": "exclude"} for cid in exclude
        ]
        if rows:
            await session.execute(pg_insert(AssistantChatRule), rows)


async def list_schedule_windows() -> list[dict]:
    """همه‌ی پنجره‌های زمانیِ تعریف‌شده، مرتب بر اساسِ ساعتِ شروع."""
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(AssistantScheduleWindow).order_by(AssistantScheduleWindow.start_minute)
            )
        ).scalars().all()
        return [
            {"id": r.id, "label": r.label, "start_minute": r.start_minute, "end_minute": r.end_minute}
            for r in rows
        ]


async def add_schedule_window(label: str, start_minute: int, end_minute: int) -> int:
    """یه پنجره‌ی جدید اضافه می‌کنه و id تازه‌ساخته‌شده رو برمی‌گردونه."""
    async with session_scope() as session:
        obj = AssistantScheduleWindow(label=label, start_minute=start_minute, end_minute=end_minute)
        session.add(obj)
        await session.flush()
        return obj.id


async def delete_schedule_window(window_id: int) -> bool:
    """یه پنجره رو با id حذف می‌کنه؛ True اگه واقعاً چیزی حذف شد."""
    async with session_scope() as session:
        result = await session.execute(
            delete(AssistantScheduleWindow).where(AssistantScheduleWindow.id == window_id)
        )
        return result.rowcount > 0


async def clear_schedule_windows() -> int:
    """همه‌ی پنجره‌ها رو پاک می‌کنه؛ تعدادِ ردیف‌های حذف‌شده رو برمی‌گردونه."""
    async with session_scope() as session:
        result = await session.execute(delete(AssistantScheduleWindow))
        return result.rowcount
