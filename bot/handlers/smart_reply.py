"""
دستور .جواب - پیشنهاد پاسخ هوشمند
"""
import logging
import time
from typing import List, Tuple

from telethon import events
from telethon.tl.types import Message

from .. import ai
from ..config import PREFIX
from ..runtime import client
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.smart_reply")

# حالت‌های پاسخ
MODES = {
    "رسمی": "پاسخ رسمی و محترمانه، با ادبیات کامل",
    "دوستانه": "پاسخ دوستانه و گرم، مثل یک رفیق صمیمی",
    "طنز": "پاسخ طنزآمیز و شوخ، با کمی شوخی",
    "کوتاه": "پاسخ بسیار کوتاه و مستقیم، حداکثر ۲ جمله",
}


@client.on(events.NewMessage(outgoing=True, pattern=pat(["جواب", "reply"])))
async def smart_reply_handler(event):
    """پیشنهاد پاسخ هوشمند برای یک پیام."""
    args = (event.pattern_match.group(1) or "").strip().split()
    mode = args[0] if args else "دوستانه"

    # بررسی حالت ارسال
    if mode in ("ارسال", "send"):
        return await _send_reply(event, args[1:] if len(args) > 1 else [])

    if not event.is_reply:
        return await event.edit(
            f"❌ باید به یک پیام ریپلای کنید.\n"
            f"مثال: `{PREFIX}جواب دوستانه`\n"
            f"حالت‌ها: {', '.join(MODES.keys())}\n"
            f"برای ارسال: `{PREFIX}جواب ارسال`"
        )

    if mode not in MODES and mode != "ارسال":
        return await event.edit(
            f"❌ حالت نامعتبر. حالت‌های موجود: {', '.join(MODES.keys())}\n"
            f"مثال: `{PREFIX}جواب رسمی`"
        )

    reply: Message = await event.get_reply_message()
    if not reply:
        return await event.edit("❌ پیام مورد نظر یافت نشد.")

    await event.edit("🤔 در حال تولید پاسخ هوشمند...")

    # بررسیِ در دسترس‌بودنِ هوش مصنوعی (این دستور مستقل از سوییچِ ai_modeِ منشیه)
    from .. import config
    if not config.AI_API_KEY:
        return await event.edit(
            "⚠️ **قابلیت هوش مصنوعی غیرفعال است**\n"
            "برای فعال‌سازی، متغیر `AI_API_KEY` را تنظیم کنید."
        )

    # ساخت پرامپت
    mode_desc = MODES.get(mode, MODES["دوستانه"])
    text = reply.text or "[پیام بدون متن]"
    sender = reply.sender_id or "کاربر ناشناس"

    messages = [
        {"role": "system", "content": f"""
تو یک دستیار هوشمند هستی که به پیام‌ها پاسخ می‌دهی.
سبک پاسخ: {mode_desc}
پیام اصلی از طرف کاربر {sender} آمده است.
پاسخ باید فارسی باشد و دقیقاً به محتوای پیام بپردازد.
""" },
        {"role": "user", "content": f"پیام: {text}\n\nلطفاً پاسخ بده."},
    ]

    try:
        response = await ai.ask_ai(messages, max_tokens=300)
    except ai.AIDisabledError:
        return await event.edit(
            "⚠️ **قابلیت هوش مصنوعی غیرفعال است**\n"
            "برای فعال‌سازی، متغیر `AI_API_KEY` را تنظیم کنید."
        )
    except ai.AIRequestError as e:
        return await event.edit(f"❌ خطا در ارتباط با سرویس AI: {e}")

    if not response:
        return await event.edit("❌ پاسخ تولید نشد. دوباره امتحان کنید.")

    # ذخیره پیشنهاد در حافظه موقت برای ارسال
    _pending_replies[event.chat_id] = {
        "text": response,
        "reply_to": reply.id,
        "created_at": time.time(),
    }

    await event.edit(
        f"💡 **پاسخ پیشنهادی** ({mode}):\n\n{response}\n\n"
        f"• ارسال: `{PREFIX}جواب ارسال`\n"
        f"• حالت‌های دیگر: `{PREFIX}جواب رسمی`، `{PREFIX}جواب طنز`، ..."
    )


# حافظه موقت برای پاسخ‌های در انتظار
_pending_replies = {}
_PENDING_TTL = 120  # ثانیه


async def _send_reply(event, args):
    """ارسال پاسخ پیشنهادی."""
    chat_id = event.chat_id
    pending = _pending_replies.get(chat_id)

    if not pending:
        return await event.edit(
            f"❌ هیچ پاسخ در انتظاری نیست. اول `{PREFIX}جواب` را اجرا کنید."
        )

    if time.time() - pending["created_at"] > _PENDING_TTL:
        _pending_replies.pop(chat_id, None)
        return await event.edit("⏳ پیشنهاد منقضی شد. دوباره امتحان کنید.")

    try:
        tagged_text, entities = ai.tag_ai_text(pending["text"])
        await event.client.send_message(
            chat_id,
            tagged_text,
            reply_to=pending["reply_to"],
            formatting_entities=entities,
        )
        _pending_replies.pop(chat_id, None)
        await event.edit("✅ پاسخ ارسال شد.")
    except Exception as e:
        await event.edit(f"❌ خطا در ارسال پاسخ: {e}")