"""
دستورات حافظه هوش مصنوعی: .حافظه
"""
import logging
from typing import Dict, List

from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import ai_memory_repo

logger = logging.getLogger("selfbot.handlers.ai_memory")

CATEGORY_ICONS = {
    "کاربران": "👤",
    "گفتگوها": "💬",
    "پروژه‌ها": "📌",
    "یادداشت‌ها": "📝",
    "تنظیمات": "⚙️",
}


@client.on(events.NewMessage(outgoing=True, pattern=pat(["حافظه", "memory"])))
async def memory_handler(event):
    """مدیریت حافظه هوش مصنوعی."""
    args = (event.pattern_match.group(1) or "").strip().split()
    sub = args[0].lower() if args else ""

    if not sub:
        return await _show_memory_stats(event)

    if sub in ("افزودن", "add"):
        return await _add_memory(event, args[1:] if len(args) > 1 else [])
    if sub in ("جستجو", "search"):
        return await _search_memory(event, args[1:] if len(args) > 1 else [])
    if sub in ("حذف", "delete", "remove"):
        return await _delete_memory(event, args[1:] if len(args) > 1 else [])
    if sub in ("لیست", "list"):
        return await _list_memory(event, args[1:] if len(args) > 1 else [])
    if sub in ("پاک", "clear"):
        return await _clear_category(event, args[1:] if len(args) > 1 else [])

    return await _show_memory_stats(event)


async def _show_memory_stats(event):
    """نمایش آمار حافظه."""
    stats = await ai_memory_repo.get_stats()
    total = sum(stats.values())

    if total == 0:
        return await event.edit(
            f"🧠 **حافظه هوش مصنوعی**\n\n"
            f"🕳️ هنوز هیچ حافظه‌ای ذخیره نشده.\n\n"
            f"• افزودن: `{PREFIX}حافظه افزودن <دسته> <کلید> <مقدار>`\n"
            f"• مثال: `{PREFIX}حافظه افزودن کاربران هادی کاربر VIP`"
        )

    lines = ["🧠 **حافظه هوش مصنوعی**", ""]
    for cat in ai_memory_repo.CATEGORIES:
        icon = CATEGORY_ICONS.get(cat, "📁")
        count = stats.get(cat, 0)
        lines.append(f"{icon} {cat}: {count} آیتم")

    lines.append("")
    lines.append(f"📊 مجموع: {total} آیتم")
    lines.append("")
    lines.append(f"• جستجو: `{PREFIX}حافظه جستجو <عبارت>`")
    lines.append(f"• لیست: `{PREFIX}حافظه لیست <دسته>`")
    lines.append(f"• حذف: `{PREFIX}حافظه حذف <دسته> <کلید>`")
    lines.append(f"• پاک کردن دسته: `{PREFIX}حافظه پاک <دسته>`")

    await event.edit("\n".join(lines))


async def _add_memory(event, args):
    """افزودن حافظه جدید."""
    if len(args) < 3:
        return await event.edit(
            f"❌ استفاده: `{PREFIX}حافظه افزودن <دسته> <کلید> <مقدار>`\n"
            f"دسته‌ها: {', '.join(ai_memory_repo.CATEGORIES)}"
        )

    category = args[0]
    if category not in ai_memory_repo.CATEGORIES:
        return await event.edit(
            f"❌ دسته نامعتبر. دسته‌ها: {', '.join(ai_memory_repo.CATEGORIES)}"
        )

    key = args[1]
    value = " ".join(args[2:])

    try:
        memory = await ai_memory_repo.save_memory(category, key, value)
        await event.edit(
            f"✅ حافظه ذخیره شد.\n"
            f"📁 دسته: {memory.category}\n"
            f"🔑 کلید: {memory.key}\n"
            f"📝 مقدار: {memory.value[:100]}..."
        )
    except Exception as e:
        await event.edit(f"❌ خطا: {e}")


async def _search_memory(event, args):
    """جستجو در حافظه."""
    if not args:
        return await event.edit(f"❌ استفاده: `{PREFIX}حافظه جستجو <عبارت>`")

    query = " ".join(args)
    results = await ai_memory_repo.search_memories(query)

    if not results:
        return await event.edit(f"🔍 نتیجه‌ای برای `{query}` یافت نشد.")

    lines = [f"🔍 **نتایج جستجو: `{query}`**", ""]
    for category, items in results.items():
        icon = CATEGORY_ICONS.get(category, "📁")
        lines.append(f"{icon} **{category}** ({len(items)})")
        for item in items[:5]:
            value_preview = item.value[:60] + ("..." if len(item.value) > 60 else "")
            lines.append(f"  `{item.key}`: {value_preview}")
        if len(items) > 5:
            lines.append(f"  ... و {len(items) - 5} مورد دیگر")
        lines.append("")

    await event.edit("\n".join(lines))


async def _delete_memory(event, args):
    """حذف یک حافظه."""
    if len(args) < 2:
        return await event.edit(f"❌ استفاده: `{PREFIX}حافظه حذف <دسته> <کلید>`")

    category = args[0]
    key = args[1]

    if category not in ai_memory_repo.CATEGORIES:
        return await event.edit(f"❌ دسته نامعتبر. دسته‌ها: {', '.join(ai_memory_repo.CATEGORIES)}")

    success = await ai_memory_repo.delete_memory(category, key)
    if success:
        await event.edit(f"✅ حافظه `{key}` از دسته `{category}` حذف شد.")
    else:
        await event.edit(f"❌ حافظه `{key}` در دسته `{category}` یافت نشد.")


async def _list_memory(event, args):
    """لیست حافظه‌های یک دسته."""
    if not args:
        return await event.edit(f"❌ استفاده: `{PREFIX}حافظه لیست <دسته>`")

    category = args[0]
    if category not in ai_memory_repo.CATEGORIES:
        return await event.edit(f"❌ دسته نامعتبر. دسته‌ها: {', '.join(ai_memory_repo.CATEGORIES)}")

    items = await ai_memory_repo.get_memories_by_category(category)

    if not items:
        return await event.edit(f"🕳️ دسته `{category}` خالی است.")

    icon = CATEGORY_ICONS.get(category, "📁")
    lines = [f"{icon} **{category}** ({len(items)})", ""]

    for item in items[:20]:
        value_preview = item.value[:60] + ("..." if len(item.value) > 60 else "")
        lines.append(f"`{item.key}`: {value_preview}")

    if len(items) > 20:
        lines.append(f"... و {len(items) - 20} مورد دیگر")

    await event.edit("\n".join(lines))


async def _clear_category(event, args):
    """پاک کردن همه حافظه‌های یک دسته."""
    if not args:
        return await event.edit(f"❌ استفاده: `{PREFIX}حافظه پاک <دسته>`")

    category = args[0]
    if category not in ai_memory_repo.CATEGORIES:
        return await event.edit(f"❌ دسته نامعتبر. دسته‌ها: {', '.join(ai_memory_repo.CATEGORIES)}")

    count = await ai_memory_repo.delete_category(category)
    await event.edit(f"✅ {count} آیتم از دسته `{category}` پاک شد.")