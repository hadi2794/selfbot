"""۶) فونت پیام: انگلیسی (یونیکد ریاضی) / فارسی (تزئینی) / ترکیبی"""
import logging

from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..fonts import (
    ENGLISH_FONTS as _ENGLISH_FONTS,
    PERSIAN_FONTS as _PERSIAN_FONTS,
    COMBINED_FONTS as _COMBINED_FONTS,
    FONT_STYLES,
)
from ..storage.font_store import font_state, save_font_state
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.font")

@client.on(events.NewMessage(outgoing=True, pattern=pat(["قلم", "font"])))
async def font_handler(event):
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not sub or sub in ("فهرست", "list"):
        sample = "Text متن"
        lines = ["🔤 **فونت‌های موجود** (نمونه با «Text متن»):\n", "**انگلیسی:**"]
        for name in _ENGLISH_FONTS:
            lines.append(f"▫️ `{name}` → {FONT_STYLES[name](sample)}")
        lines.append("\n**فارسی:**")
        for name in _PERSIAN_FONTS:
            lines.append(f"▫️ `{name}` → {FONT_STYLES[name](sample)}")
        lines.append("\n**ترکیبی:**")
        for name in _COMBINED_FONTS:
            lines.append(f"▫️ `{name}` → {FONT_STYLES[name](sample)}")
        lines.append(
            f"\nاستفاده‌ی یه‌بار: `{PREFIX}قلم <نام> <متن>` یا ریپلای + `{PREFIX}قلم <نام>`\n"
            f"اعمال خودکار روی همه‌ی پیام‌ها: `{PREFIX}قلم تنظیم <نام>` بعد `{PREFIX}قلم روشن`"
        )
        return await event.edit("\n".join(lines))

    if sub in ("وضعیت", "status"):
        state_fa = "روشن ✅" if font_state["enabled"] else "خاموش ❌"
        return await event.edit(
            f"🔤 **فونت خودکار پیام‌ها**\n\n"
            f"• وضعیت: {state_fa}\n"
            f"• فونت انتخابی: `{font_state['style']}`\n\n"
            f"روشن/خاموش: `{PREFIX}قلم روشن` / `{PREFIX}قلم خاموش`\n"
            f"تغییر فونت: `{PREFIX}قلم تنظیم <نام>`"
        )

    if sub in ("تنظیم", "set"):
        name = rest.strip().lower()
        if name not in FONT_STYLES:
            return await event.edit(f"فونت نامعتبره. برای فهرست: `{PREFIX}قلم فهرست`")
        font_state["style"] = name
        await save_font_state()
        return await event.edit(f"✅ فونت پیش‌فرض روی `{name}` تنظیم شد")

    if sub in ("روشن", "on"):
        font_state["enabled"] = True
        await save_font_state()
        return await event.edit(
            f"✅ فونت خودکار روشن شد (فونت: `{font_state['style']}`)\n"
            "از الان، هر پیام عادی‌ای که بفرستی (نه دستورها) خودکار با این فونت "
            "ارسال می‌شه. توجه: چون پیام اول واقعی فرستاده می‌شه و بعد ادیت می‌شه، "
            "یه لحظه‌ی خیلی کوتاه متن اصلی قابل‌دیدنه."
        )

    if sub in ("خاموش", "off"):
        font_state["enabled"] = False
        await save_font_state()
        return await event.edit("✅ فونت خودکار خاموش شد")

    if sub not in FONT_STYLES:
        return await event.edit(f"فونت نامعتبره. برای فهرست: `{PREFIX}قلم فهرست`")

    text = rest
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text or ""
    if not text:
        return await event.edit(f"مثال: `{PREFIX}قلم {sub} متن شما`")

    await event.edit(FONT_STYLES[sub](text))


@client.on(events.NewMessage(outgoing=True))
async def font_autoapply(event):
    """
    وقتی فونت خودکار روشنه، این هندلر روی *هر* پیام معمولی‌ای که می‌فرستی
    (نه دستورهای ربات که با پیشوند شروع می‌شن) فونت انتخابی رو اعمال می‌کنه.
    """
    if not font_state["enabled"]:
        return
    text = event.raw_text
    if not text or text.startswith(PREFIX):
        return  # دستورهای خودِ ربات رو دست نمی‌زنیم
    style = font_state["style"]
    if style not in FONT_STYLES:
        return
    try:
        await event.edit(FONT_STYLES[style](text))
    except Exception:
        _record_error()
        logger.exception("خطا در اعمال خودکار فونت")
