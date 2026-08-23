"""
Repository برای دیوانِ حافظ (`.فال`).

داده‌ها یک‌بار با `scripts/seed_hafez.py` توی PostgreSQL ریخته می‌شن؛ از اون به
بعد هندلر (`bot/handlers/fun.py`) فقط از `random_poem()` استفاده می‌کنه -
هیچ importِ زمانِ‌اجرای پکیجِ خارجی و هیچ نیازِ شبکه‌ای نداره.
"""
from sqlalchemy import func, select

from ..db.engine import session_scope
from ..db.models_ext import HafezPoem


async def count() -> int:
    async with session_scope() as session:
        result = await session.execute(select(func.count()).select_from(HafezPoem))
        return result.scalar_one()


async def random_poem() -> HafezPoem | None:
    """یه غزلِ تصادفی از جدول برمی‌گردونه (یا None اگه جدول هنوز seed نشده)."""
    async with session_scope() as session:
        stmt = select(HafezPoem).order_by(func.random()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def bulk_upsert(poems: list[dict]) -> int:
    """
    برای `scripts/seed_hafez.py`: لیستی از دیکشنری‌های
    ``{"id", "poem", "interpretation", "alt_interpretation"}`` رو upsert
    می‌کنه (idempotent - چندبار اجرا مشکلی نداره). تعدادِ ردیف‌های پردازش‌شده
    رو برمی‌گردونه.
    """
    if not poems:
        return 0
    async with session_scope() as session:
        for p in poems:
            obj = await session.get(HafezPoem, p["id"])
            if obj is None:
                obj = HafezPoem(id=p["id"])
                session.add(obj)
            obj.poem = p["poem"]
            obj.interpretation = p.get("interpretation")
            obj.alt_interpretation = p.get("alt_interpretation")
        return len(poems)
