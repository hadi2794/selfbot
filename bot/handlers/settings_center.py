"""
دستور .تنظیمات - پنل تنظیماتِ یکپارچه.

این پنل دیگه یه دفترچه‌ی جدا نیست: هر کلید مستقیماً به state واقعیِ همون
بخش وصله (دقیقاً همون چیزی که `.منشی`/`.ارسال‌خودکار`/`.قلم` خودشون
دست‌کاری می‌کنن)، پس عوض‌کردنِ یه مقدار اینجا خودِ اون قابلیت رو واقعاً
روشن/خاموش می‌کنه - نه یه کپیِ نمایشی که فقط نشون داده می‌شه.

`guard_enabled` عمداً اینجا نیست: محافظِ گروه (فیلترلینک/خوش‌آمد/فیلترپورن/
فیلتراسپم) سراسری نیست، هر گروه جدا تنظیم می‌شه (`.فیلترلینک`, `.خوش‌آمد`,
`.فیلترپورن`, `.فیلتراسپم` توی همون گروه).
"""
import json
import logging

from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..storage.assistant_store import assistant_state, save_assistant
from ..storage.autopost_store import autopost_state, save_autopost
from ..storage.daily_digest_store import daily_digest_state, save_daily_digest
from ..storage.font_store import font_state, save_font_state
from ..storage.settings_toggles import set_toggle, toggles
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.settings_center")

# کلیدهای تنظیمات
SETTINGS_KEYS = {
    "assistant_mode": "🤖 منشی",
    "ai_mode": "🧠 AI منشی",
    "assistant_schedule_enabled": "🗓 زمان‌بندیِ منشی",
    "scheduler_enabled": "⏰ زمان‌بند/یادآوری",
    "autopost_enabled": "🔁 ارسالِ خودکار",
    "daily_digest_enabled": "🌙 خلاصه‌ی روزانه",
    "font_enabled": "🎨 فونتِ خودکار",
    "stats_enabled": "📊 آمار",
    "notifications_enabled": "🔔 موتورِ اعلان",
}

_TRUE_WORDS = ("true", "on", "1", "روشن", "فعال")
_FALSE_WORDS = ("false", "off", "0", "خاموش", "غیرفعال")


def _live_status() -> dict:
    """وضعیتِ واقعیِ همین‌الانِ هر بخش (نه چیزی که قبلاً توی settings ذخیره شده)."""
    return {
        "assistant_mode": assistant_state["enabled"],
        "ai_mode": assistant_state["ai_mode"],
        "assistant_schedule_enabled": assistant_state["schedule_enabled"],
        "scheduler_enabled": toggles["scheduler_enabled"],
        "autopost_enabled": autopost_state["enabled"],
        "daily_digest_enabled": daily_digest_state["enabled"],
        "font_enabled": font_state["enabled"],
        "stats_enabled": toggles["stats_enabled"],
        "notifications_enabled": toggles["notifications_enabled"],
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

    # نمایش پنل اصلی - همیشه از رویِ state واقعی، نه یه کپیِ قدیمی
    status = _live_status()
    lines = ["⚙️ **تنظیمات یکپارچه**", ""]

    for key, display in SETTINGS_KEYS.items():
        enabled = status[key]
        lines.append(f"• {display}: {'✅ فعال' if enabled else '❌ غیرفعال'}")

    lines.append("")
    lines.append(f"برای تغییر: `{PREFIX}تنظیمات تنظیم <key> <true|false>`")
    lines.append(f"مثال: `{PREFIX}تنظیمات تنظیم assistant_mode true`")
    lines.append("")
    lines.append("📋 کلیدهای موجود:")
    for key, display in SETTINGS_KEYS.items():
        lines.append(f"  `{key}` ← {display}")
    lines.append("")
    lines.append(
        f"🛡 محافظِ گروه (فیلترلینک/خوش‌آمد/فیلترپورن/فیلتراسپم) سراسری نیست؛ هر گروه جدا با "
        f"`{PREFIX}فیلترلینک` / `{PREFIX}خوش‌آمد` / `{PREFIX}فیلترپورن` / `{PREFIX}فیلتراسپم` "
        "توی همون گروه تنظیم می‌شه."
    )

    await event.edit("\n".join(lines))


async def _set_setting(event, key: str, value: str):
    """تغییر یک تنظیم - مستقیماً روی stateِ واقعیِ همون بخش اعمال می‌شه."""
    if not key or not value:
        return await event.edit(f"❌ استفاده: `{PREFIX}تنظیمات تنظیم <key> <true|false>`")

    if key not in SETTINGS_KEYS:
        return await event.edit(f"❌ کلید نامعتبر. کلیدهای موجود: {', '.join(SETTINGS_KEYS.keys())}")

    normalized = value.strip().lower()
    if normalized in _TRUE_WORDS:
        enabled = True
    elif normalized in _FALSE_WORDS:
        enabled = False
    else:
        return await event.edit(f"❌ مقدار باید true/false (یا on/off, روشن/خاموش) باشه، نه `{value}`")

    if key == "assistant_mode":
        assistant_state["enabled"] = enabled
        assistant_state["auto_detect"] = False  # قفلِ دستی، دقیقاً هم‌رفتار با `.منشی روشن/خاموش`
        if enabled:
            assistant_state["replied"] = set()
        await save_assistant()
    elif key == "ai_mode":
        assistant_state["ai_mode"] = enabled
        await save_assistant()
    elif key == "assistant_schedule_enabled":
        # نکته: این فقط لایه‌ی زمان‌بندی رو روشن/خاموش می‌کنه، نه خودِ enabled -
        # اگه auto_detect روشن باشه، بازبینیِ بعدیِ assistant_status_watcher
        # (حداکثر تا ASSISTANT_CHECK_INTERVAL ثانیه‌ی دیگه) enabled رو با
        # مقدارِ تازه‌ی این کلید هماهنگ می‌کنه؛ برای اثرِ فوری از
        # `.منشی زمان‌بندی روشن/خاموش` استفاده کن.
        assistant_state["schedule_enabled"] = enabled
        await save_assistant()
    elif key == "autopost_enabled":
        autopost_state["enabled"] = enabled
        await save_autopost()
    elif key == "daily_digest_enabled":
        daily_digest_state["enabled"] = enabled
        await save_daily_digest()
    elif key == "font_enabled":
        font_state["enabled"] = enabled
        await save_font_state()
    elif key in ("scheduler_enabled", "stats_enabled", "notifications_enabled"):
        await set_toggle(key, enabled)

    await event.edit(f"✅ {SETTINGS_KEYS[key]} → {'فعال ✅' if enabled else 'غیرفعال ❌'}")


async def _save_settings(event, args):
    """خروجیِ JSON از وضعیتِ فعلیِ همه‌ی بخش‌ها (برای مشاهده/بکاپِ دستی)."""
    backup = json.dumps(_live_status(), ensure_ascii=False, indent=2)
    await event.edit(f"📋 تنظیمات فعلی:\n```json\n{backup}\n```")
