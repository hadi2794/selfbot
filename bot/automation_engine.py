"""
موتور اتوماسیون - اجرای قوانین بر اساس رویدادها
"""
import logging
import json
from typing import Dict, Any, Optional, List

from .repositories import automation_repo
from .storage.scheduler_store import create_job
from .storage.notes_store import save_note
from .repositories.inbox_repo import save_item
from . import runtime
from .runtime import client

logger = logging.getLogger("selfbot.automation_engine")

# نگاشت عملیات به توابع
_action_handlers = {}


def register_action(action_type: str):
    """دکوریتور برای ثبت هندلر عملیات."""
    def decorator(func):
        _action_handlers[action_type] = func
        return func
    return decorator


@register_action("reply")
async def _handle_reply(rule, context: Dict[str, Any]):
    """ارسال پاسخ."""
    chat_id = context.get("chat_id")
    message_id = context.get("message_id")
    if not chat_id:
        return

    try:
        await client.send_message(
            chat_id,
            rule.action_value,
            reply_to=message_id,
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پاسخ: {e}")


@register_action("ai")
async def _handle_ai(rule, context: Dict[str, Any]):
    """پاسخ با AI."""
    from . import ai
    chat_id = context.get("chat_id")
    message_id = context.get("message_id")
    if not chat_id:
        return

    try:
        response = await ai.ask_ai([
            {"role": "user", "content": rule.action_value}
        ], max_tokens=300)
        if response:
            await client.send_message(
                chat_id,
                response,
                reply_to=message_id,
            )
    except Exception as e:
        logger.error(f"خطا در پاسخ AI: {e}")


@register_action("note")
async def _handle_note(rule, context: Dict[str, Any]):
    """ذخیره یادداشت."""
    key = context.get("key", "auto")
    try:
        await save_note(key, rule.action_value)
    except Exception as e:
        logger.error(f"خطا در ذخیره یادداشت: {e}")


@register_action("schedule")
async def _handle_schedule(rule, context: Dict[str, Any]):
    """زمان‌بندی کار."""
    # action_value format: "time|text"
    parts = rule.action_value.split("|", 1)
    if len(parts) != 2:
        return
    time_str, text = parts
    from .handlers.scheduler import parse_time
    parsed = parse_time(time_str.strip())
    if parsed:
        run_at, _local_display = parsed
        try:
            await create_job(runtime.SELF_ID or context.get("chat_id"), text.strip(), run_at, "schedule")
        except Exception as e:
            logger.error(f"خطا در زمان‌بندی: {e}")


@register_action("notify")
async def _handle_notify(rule, context: Dict[str, Any]):
    """ارسال اعلان."""
    chat_id = context.get("chat_id")
    if not chat_id:
        return

    try:
        await client.send_message(
            chat_id,
            f"🔔 **اعلان اتوماسیون**\n\n{rule.action_value}",
        )
    except Exception as e:
        logger.error(f"خطا در ارسال اعلان: {e}")


@register_action("save")
async def _handle_save(rule, context: Dict[str, Any]):
    """ذخیره در صندوق ورودی."""
    chat_id = context.get("chat_id")
    message_id = context.get("message_id")
    text = context.get("text", rule.action_value)
    if not chat_id or not message_id:
        return

    try:
        await save_item(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            sender_id=context.get("sender_id"),
        )
    except Exception as e:
        logger.error(f"خطا در ذخیره: {e}")


async def trigger_event(event_type: str, context: Dict[str, Any]):
    """
    اجرای قوانین منطبق با یک رویداد.
    """
    rules = await automation_repo.get_rules_for_event(event_type, context)

    if not rules:
        return

    logger.info(f"اجرای {len(rules)} قانون برای رویداد {event_type}")

    for rule in rules:
        try:
            # بررسی شرط (اگر وجود داشته باشد)
            if rule.condition:
                condition_met = await _evaluate_condition(rule.condition, context)
                if not condition_met:
                    continue

            # اجرای عملیات
            handler = _action_handlers.get(rule.action_type)
            if handler:
                await handler(rule, context)
            else:
                logger.warning(f"هندلر برای {rule.action_type} یافت نشد")

        except Exception as e:
            logger.exception(f"خطا در اجرای قانون {rule.id}: {e}")


async def _evaluate_condition(condition: str, context: Dict[str, Any]) -> bool:
    """
    ارزیابی شرط به صورت ساده.
    فرمت‌های پشتیبانی‌شده:
    - "keyword in message" → بررسی وجود کلمه در پیام
    - "sender_id == 123" → بررسی فرستنده
    - "chat_id == 456" → بررسی چت
    """
    condition = condition.strip()

    # بررسی شرط کلیدواژه
    if "in message" in condition:
        keyword = condition.replace("in message", "").strip().strip('"\'')
        message = context.get("text", "")
        return keyword.lower() in message.lower()

    # بررسی شرط برابری
    if "==" in condition:
        parts = condition.split("==", 1)
        left = parts[0].strip()
        right = parts[1].strip().strip('"\'')
        context_value = context.get(left)
        if context_value is not None:
            return str(context_value) == right

    return True  # شرط نامشخص → قبول