"""
موتورِ اعلان - ارزیابیِ قوانینِ `.اعلان` روی پیام‌های ورودی و اجرای عملیاتشون.

برخلافِ automation_engine (که برای هر قانون یه عملیاتِ دلخواه روی هر
رویدادی اجرا می‌کنه و می‌تونه توی خودِ چت جواب بده)، این موتور محدود و
متمرکز روی «اطلاع‌رسانی به خودِ صاحبِ اکانته»: notify/save/forward همیشه
فقط برای خودِ صاحبِ اکانت اجرا می‌شن (پیام به Saved Messages یا صندوقِ
ورودیِ داخلیِ ربات) - هیچ‌وقت به شخصِ سومی چیزی فرستاده نمی‌شه. تنها
استثنا عملیاتِ reply هست که توی همون چتی که پیام اومده جواب می‌ده (دقیقاً
هم‌رفتار با automation_engine._handle_reply که از قبل توی همین پروژه
پذیرفته‌شده بود).

⚠️ trigger_type="time" فعلاً پشتیبانی نمی‌شه: این موتور فقط رویِ پیام‌های
*ورودی* اجرا می‌شه، و قانون‌های زمانی نیاز به یه زمان‌بندِ جداگونه دارن که
هنوز ساخته نشده - این‌جور قانون‌ها ذخیره می‌شن ولی هیچ‌وقت trigger نمی‌شن.
"""
import logging
from typing import Any, Dict

from . import runtime
from .repositories import notification_repo
from .repositories.inbox_repo import save_item
from .runtime import client

logger = logging.getLogger("selfbot.notification_engine")


def _matches(rule, context: Dict[str, Any]) -> bool:
    ttype = rule.trigger_type
    if ttype == "message":
        return True
    if ttype == "keyword":
        text = context.get("text") or ""
        keyword = (rule.trigger_value or "").strip().lower()
        return bool(keyword) and keyword in text.lower()
    if ttype == "user":
        sender_id = context.get("sender_id")
        target = (rule.trigger_value or "").strip().lstrip("@")
        return sender_id is not None and target.isdigit() and str(sender_id) == target
    # "time": نیازمندِ زمان‌بندِ جداگونه‌ست، فعلاً هیچ‌وقت match نمی‌شه
    return False


async def _handle_notify(rule, context):
    self_id = runtime.SELF_ID
    if not self_id:
        return
    text = context.get("text") or "(بدون متن)"
    try:
        await client.send_message(
            self_id,
            f"🔔 **اعلان: {rule.name}**\n\n{text}\n\n"
            f"از طرف: `{context.get('sender_id')}` — چت: `{context.get('chat_id')}`",
        )
    except Exception:
        logger.exception("خطا در ارسال اعلان (notify)")


async def _handle_save(rule, context):
    try:
        await save_item(
            chat_id=context["chat_id"],
            message_id=context["message_id"],
            text=context.get("text") or "",
            sender_id=context.get("sender_id"),
        )
    except Exception:
        logger.exception("خطا در ذخیره‌ی پیام (save)")


async def _handle_forward(rule, context):
    self_id = runtime.SELF_ID
    if not self_id:
        return
    try:
        await client.forward_messages(self_id, context["message_id"], context["chat_id"])
    except Exception:
        logger.exception("خطا در فوروارد پیام")


async def _handle_reply(rule, context):
    chat_id = context.get("chat_id")
    message_id = context.get("message_id")
    if not chat_id:
        return
    try:
        await client.send_message(
            chat_id,
            rule.action_value or f"🔔 {rule.name}",
            reply_to=message_id,
        )
    except Exception:
        logger.exception("خطا در پاسخِ خودکارِ اعلان")


_ACTION_HANDLERS = {
    "notify": _handle_notify,
    "save": _handle_save,
    "forward": _handle_forward,
    "reply": _handle_reply,
}


async def trigger_notifications(context: Dict[str, Any]) -> None:
    """برای هر پیامِ ورودی صدا زده می‌شه (از bot/handlers/notifications.py)."""
    rules = await notification_repo.get_rules(enabled_only=True)
    if not rules:
        return
    for rule in rules:
        try:
            if not _matches(rule, context):
                continue
            handler = _ACTION_HANDLERS.get(rule.action_type)
            if handler:
                await handler(rule, context)
        except Exception:
            logger.exception("خطا در اجرای قانونِ اعلانِ %s", rule.id)
