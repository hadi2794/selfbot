"""
دستور .تنظیمات - پنل تنظیمات یکپارچه
"""
import json
import logging

from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import settings_repo

logger = logging.getLogger("selfbot.handlers.settings_center")

# کلیدهای تنظیمات
SETTINGS_KEYS = {
    "assistant_mode": "🤖 منشی",
    "ai_mode": "🧠 AI",
    "scheduler_enabled": "⏰ Scheduler",
    "autopost_enabled": "🔁 Autopost",
    "font_enabled": "🎨 Font",
    "guard_enabled": "🛡 محافظ",
    "stats_enabled": "📊 آمار",
    "notifications_enabled": "🔔 اعلان‌ها",
}


@client.on(events.NewMessage(outgoing=True, pattern=pat(["تنظیمات", "settings"])))
async def settings_handler(event):
    """نمایش پنل تنظیمات."""
    args = (event.pattern_match.group(1) or "").strip().split()
    sub = args[0].lower() if args else ""

    if sub in ("ذخیره", "save"):
        return await _save_settings(event, args[1:] if len(args) > 1 else [])
    if sub in ("تنظیم", "set"):
        return await _set_setting(event, args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "")

    # نمایش پنل اصلی
    all_settings = await settings_repo.get_all_settings()
    lines = [
        "⚙️ **تنظیمات یکپارچه**",
        "⚠️ این کلیدها فقط یه یادداشتِ متنی/key-value هستن؛ فعلاً به سوییچِ واقعیِ "
        "خودِ اون بخش‌ها (مثلاً `.منشی`, `.قلم`, `.زمان‌بند`) وصل نیستن - عوض‌کردنِ "
        "یه مقدار اینجا خودِ اون قابلیت رو روشن/خاموش نمی‌کنه.",
        "",
    ]

    for key, display in SETTINGS_KEYS.items():
        value = all_settings.get(key, "غیرفعال")
        status = "✅ فعال" if value == "true" else "❌ غیرفعال" if value == "false" else value
        lines.append(f"• {display}: {status}")

    lines.append("")
    lines.append(f"برای تغییر: `{PREFIX}تنظیمات تنظیم <key> <value>`")
    lines.append(f"مثال: `{PREFIX}تنظیمات تنظیم assistant_mode true`")
    lines.append("")
    lines.append("📋 کلیدهای موجود:")
    for key, display in SETTINGS_KEYS.items():
        lines.append(f"  `{key}` ← {display}")

    await event.edit("\n".join(lines))


async def _set_setting(event, key: str, value: str):
    """تغییر یک تنظیم."""
    if not key or not value:
        return await event.edit(f"❌ استفاده: `{PREFIX}تنظیمات تنظیم <key> <value>`")

    if key not in SETTINGS_KEYS:
        return await event.edit(f"❌ کلید نامعتبر. کلیدهای موجود: {', '.join(SETTINGS_KEYS.keys())}")

    await settings_repo.set_setting(key, value)
    await event.edit(f"✅ تنظیم `{key}` به `{value}` تغییر کرد.")


async def _save_settings(event, args):
    """ذخیره همه تنظیمات فعلی."""
    all_settings = await settings_repo.get_all_settings()
    backup = json.dumps(all_settings, ensure_ascii=False, indent=2)
    await event.edit(f"📋 تنظیمات فعلی:\n```json\n{backup}\n```")