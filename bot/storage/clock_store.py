"""
وضعیتِ ساعتِ زنده/پروفایل - PostgreSQL از طریق Repository Layer.

نکته: در نسخه‌ی قبلی (فقط JSON) این بخش اصلاً persist نمی‌شد (clock_state
فقط در حافظه بود و با هر ری‌استارت به مقادیر پیش‌فرض/env برمی‌گشت - همون
چیزی که کامنت بالای clock.py هم بهش اشاره می‌کنه). طبق درخواستِ migration
به PostgreSQL برای «Clock/Profile Settings»، این بخش حالا هم persist می‌شه؛
هیچ قابلیتی حذف نشده، فقط یک نقطه‌ضعفِ قبلی (از دست رفتنِ استایل/نام پایه‌ی
ساعت بعد از هر ری‌دیپلوی) برطرف شده.
"""
from ..repositories import clock_repo


async def load_clock_settings() -> dict:
    settings = await clock_repo.get_settings()
    return {"enabled": settings.enabled, "style": settings.style, "base_name": settings.base_name}


async def save_clock_settings(enabled: bool, style: str, base_name) -> None:
    await clock_repo.save_settings(enabled=enabled, style=style, base_name=base_name)
