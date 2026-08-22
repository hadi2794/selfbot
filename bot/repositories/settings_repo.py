"""
Repository برای تنظیمات یکپارچه (Settings Key-Value).
"""

from sqlalchemy import select, update, delete
from typing import Optional, Dict, Any
import json

from ..db.engine import session_scope
from ..db.models_ext import Setting


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """دریافت یک تنظیم."""
    async with session_scope() as session:
        stmt = select(Setting).where(Setting.key == key)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            return setting.value
        return default


async def get_setting_json(key: str, default: Optional[Any] = None) -> Any:
    """دریافت یک تنظیم به‌صورت JSON."""
    value = await get_setting(key)
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


async def set_setting(key: str, value: str) -> Setting:
    """تنظیم یک مقدار (رشته)."""
    async with session_scope() as session:
        stmt = select(Setting).where(Setting.key == key)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            session.add(setting)
        await session.commit()
        await session.refresh(setting)
        return setting


async def set_setting_json(key: str, value: Any) -> Setting:
    """تنظیم یک مقدار (JSON)."""
    return await set_setting(key, json.dumps(value, ensure_ascii=False))


async def delete_setting(key: str) -> bool:
    """حذف یک تنظیم."""
    async with session_scope() as session:
        stmt = delete(Setting).where(Setting.key == key)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def get_all_settings() -> Dict[str, str]:
    """دریافت همه‌ی تنظیمات."""
    async with session_scope() as session:
        stmt = select(Setting)
        result = await session.execute(stmt)
        settings = result.scalars().all()
        return {s.key: s.value for s in settings}


async def get_settings_by_prefix(prefix: str) -> Dict[str, str]:
    """دریافت تنظیماتی که کلیدشان با پیشوند مشخص شروع می‌شود."""
    async with session_scope() as session:
        stmt = select(Setting).where(Setting.key.startswith(prefix))
        result = await session.execute(stmt)
        settings = result.scalars().all()
        return {s.key: s.value for s in settings}