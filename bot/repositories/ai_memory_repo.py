"""
Repository برای حافظه‌ی هوش مصنوعی (AI Memory).
"""

from sqlalchemy import select, delete, func
from typing import List, Optional, Dict

from ..db.engine import session_scope
from ..db.models_ext import AIMemory


CATEGORIES = ["کاربران", "گفتگوها", "پروژه‌ها", "یادداشت‌ها", "تنظیمات"]


async def save_memory(category: str, key: str, value: str) -> AIMemory:
    """ذخیره یا بروزرسانی یک حافظه."""
    if category not in CATEGORIES:
        raise ValueError(f"دسته‌بندی نامعتبر: {category}")

    async with session_scope() as session:
        stmt = select(AIMemory).where(AIMemory.category == category, AIMemory.key == key)
        result = await session.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory:
            memory.value = value
            await session.commit()
            await session.refresh(memory)
            return memory
        memory = AIMemory(category=category, key=key, value=value)
        session.add(memory)
        await session.commit()
        await session.refresh(memory)
        return memory


async def get_memory(category: str, key: str) -> Optional[AIMemory]:
    """دریافت یک حافظه."""
    async with session_scope() as session:
        stmt = select(AIMemory).where(AIMemory.category == category, AIMemory.key == key)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_memories_by_category(category: str) -> List[AIMemory]:
    """دریافت همه‌ی حافظه‌های یک دسته."""
    async with session_scope() as session:
        stmt = select(AIMemory).where(AIMemory.category == category).order_by(AIMemory.key)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def search_memories(query: str) -> Dict[str, List[AIMemory]]:
    """جستجو در حافظه‌ها (بر اساس کلید یا مقدار)."""
    async with session_scope() as session:
        stmt = select(AIMemory).where(
            (AIMemory.key.ilike(f"%{query}%")) |
            (AIMemory.value.ilike(f"%{query}%"))
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())
        # گروه‌بندی بر اساس دسته
        grouped = {}
        for item in items:
            grouped.setdefault(item.category, []).append(item)
        return grouped


async def delete_memory(category: str, key: str) -> bool:
    """حذف یک حافظه."""
    async with session_scope() as session:
        stmt = delete(AIMemory).where(AIMemory.category == category, AIMemory.key == key)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def delete_category(category: str) -> int:
    """حذف همه‌ی حافظه‌های یک دسته."""
    async with session_scope() as session:
        stmt = delete(AIMemory).where(AIMemory.category == category)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount


async def get_stats() -> Dict[str, int]:
    """آمار حافظه‌ها به تفکیک دسته."""
    async with session_scope() as session:
        stats = {}
        for cat in CATEGORIES:
            stmt = select(func.count(AIMemory.id)).where(AIMemory.category == cat)
            count = await session.scalar(stmt) or 0
            stats[cat] = count
        return stats