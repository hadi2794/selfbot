"""
دستور .جستجو - جستجوی جهانی در تمام داده‌ها
"""
import logging
from typing import List, Dict, Any

from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import (
    notes_repo,
    ai_memory_repo,
    user_profile_repo,
    inbox_repo,
    settings_repo,
    scheduler_repo,
)

logger = logging.getLogger("selfbot.handlers.global_search")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["جستجو", "search"])))
async def global_search_handler(event):
    """جستجو در تمام داده‌ها."""
    args = (event.pattern_match.group(1) or "").strip().split()
    if not args:
        return await event.edit(
            f"🔍 **جستجوی جهانی**\n\n"
            f"استفاده: `{PREFIX}جستجو <عبارت>`\n\n"
            f"جستجو در:\n"
            f"• یادداشت‌ها\n"
            f"• حافظه AI\n"
            f"• پروفایل کاربران\n"
            f"• صندوق ورودی\n"
            f"• تنظیمات\n"
            f"• کارهای زمان‌بندی‌شده"
        )

    query = " ".join(args)
    await event.edit(f"🔍 در حال جستجوی `{query}`...")

    results = {}

    try:
        # جستجو در یادداشت‌ها
        notes = await notes_repo.search_notes(query)
        if notes:
            results["یادداشت‌ها"] = [f"`{n.key}`: {n.text[:80]}..." for n in notes[:5]]

        # جستجو در حافظه AI
        memories = await ai_memory_repo.search_memories(query)
        if memories:
            items = []
            for cat, mems in memories.items():
                for m in mems[:3]:
                    items.append(f"[{cat}] `{m.key}`: {m.value[:80]}...")
            if items:
                results["حافظه AI"] = items[:10]

        # جستجو در پروفایل کاربران
        profiles = await user_profile_repo.search_profiles(query)
        if profiles:
            results["کاربران"] = [
                f"@{p.username or p.first_name or str(p.user_id)}: {p.tags or 'بدون برچسب'}"
                for p in profiles[:5]
            ]

        # جستجو در صندوق ورودی
        inbox_items = await inbox_repo.search_items(query)
        if inbox_items:
            results["صندوق ورودی"] = [
                f"{i.sender_name or 'ناشناس'}: {i.text[:60]}..." for i in inbox_items[:5]
            ]

        # جستجو در کارهای زمان‌بندی‌شده
        jobs = await scheduler_repo.search_jobs(query)
        if jobs:
            results["زمان‌بندی"] = [
                f"#{j.id} {j.text[:40]}... ({j.run_at.strftime('%Y-%m-%d %H:%M')})"
                for j in jobs[:5]
            ]

        # جستجو در تنظیمات
        settings = await settings_repo.get_all_settings()
        matched_settings = {k: v for k, v in settings.items() if query.lower() in k.lower() or query.lower() in v.lower()}
        if matched_settings:
            results["تنظیمات"] = [f"`{k}`: {v[:40]}..." for k, v in list(matched_settings.items())[:5]]

    except Exception as e:
        logger.exception("خطا در جستجوی جهانی")
        return await event.edit(f"❌ خطا در جستجو: {e}")

    if not results:
        return await event.edit(f"🔍 نتیجه‌ای برای `{query}` یافت نشد.")

    lines = [f"🔍 **نتایج جستجو: `{query}`**", ""]

    total = 0
    for section, items in results.items():
        lines.append(f"📁 **{section}** ({len(items)})")
        for item in items[:5]:
            lines.append(f"  • {item}")
        if len(items) > 5:
            lines.append(f"  ... و {len(items) - 5} مورد دیگر")
        lines.append("")
        total += len(items)

    lines.append(f"📊 مجموع: {total} نتیجه")

    await event.edit("\n".join(lines))