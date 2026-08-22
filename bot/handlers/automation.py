"""
دستورات موتور اتوماسیون: .اتوماسیون
"""
import logging
import json
from typing import List, Dict, Any

from telethon import events

from .. import runtime
from ..automation_engine import trigger_event
from ..config import PREFIX
from ..runtime import client
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from ..repositories import automation_repo

logger = logging.getLogger("selfbot.handlers.automation")


@client.on(events.NewMessage(incoming=True))
async def automation_incoming_trigger(event):
    """
    هر پیامِ ورودی (از هر چتی) رو به موتورِ اتوماسیون پاس می‌ده تا اگه یه
    قانونِ فعال با event_type="message" روش match بشه، عملیاتش اجرا بشه.
    بدونِ این هندلر، `.اتوماسیون جدید` فقط قانون می‌سازه ولی هیچ‌وقت هیچی
    اجرا نمی‌شه (چون trigger_event جای دیگه‌ای صدا زده نمی‌شد).
    """
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return  # به پیام‌های خودمون (دستورها) واکنش نشون نمی‌دیم
    context = {
        "chat_id": event.chat_id,
        "message_id": event.id,
        "sender_id": sender_id,
        "text": event.raw_text or "",
    }
    try:
        await trigger_event("message", context)
    except Exception:
        _record_error()
        logger.exception("خطا در اجرای موتورِ اتوماسیون برای پیامِ ورودی")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["اتوماسیون", "auto"])))
async def automation_handler(event):
    """مدیریت قوانین اتوماسیون."""
    args = (event.pattern_match.group(1) or "").strip().split()
    sub = args[0].lower() if args else ""

    if not sub:
        return await _show_rules(event)

    if sub in ("جدید", "new"):
        return await _create_rule(event, args[1:] if len(args) > 1 else [])
    if sub in ("حذف", "delete", "rm"):
        return await _delete_rule(event, args[1:] if len(args) > 1 else [])
    if sub in ("فعال", "enable"):
        return await _toggle_rule(event, args[1:] if len(args) > 1 else [], True)
    if sub in ("غیرفعال", "disable"):
        return await _toggle_rule(event, args[1:] if len(args) > 1 else [], False)
    if sub in ("اطلاعات", "info"):
        return await _rule_info(event, args[1:] if len(args) > 1 else [])

    return await _show_rules(event)


async def _show_rules(event):
    """نمایش لیست قوانین اتوماسیون."""
    rules = await automation_repo.get_rules(enabled_only=False)

    if not rules:
        return await event.edit(
            f"⚡ **موتور اتوماسیون**\n\n"
            f"🕳️ هیچ قانونی تعریف نشده.\n\n"
            f"• ایجاد قانون: `{PREFIX}اتوماسیون جدید <نام> <رویداد> <عملیات> <مقدار>`\n"
            f"• مثال: `{PREFIX}اتوماسیون جدید سلام message reply سلام 👋`\n\n"
            f"رویدادها: message, schedule, command, user_join, user_leave\n"
            f"عملیات: reply, ai, note, schedule, notify, guard, backup, autopost"
        )

    lines = ["⚡ **موتور اتوماسیون**", ""]

    for rule in rules:
        status = "✅" if rule.enabled else "❌"
        lines.append(f"{status} `#{rule.id}` **{rule.name}**")
        lines.append(f"   ▸ رویداد: {rule.event_type} → عملیات: {rule.action_type}")
        if rule.condition:
            lines.append(f"   ▸ شرط: {rule.condition[:40]}...")
        lines.append("")

    lines.append("")
    lines.append(f"• جزئیات: `{PREFIX}اتوماسیون اطلاعات <id>`")
    lines.append(f"• فعال/غیرفعال: `{PREFIX}اتوماسیون فعال <id>` / `{PREFIX}اتوماسیون غیرفعال <id>`")
    lines.append(f"• حذف: `{PREFIX}اتوماسیون حذف <id>`")

    await event.edit("\n".join(lines))


async def _create_rule(event, args):
    """ایجاد قانون اتوماسیون جدید."""
    if len(args) < 4:
        return await event.edit(
            f"❌ استفاده: `{PREFIX}اتوماسیون جدید <نام> <رویداد> <عملیات> <مقدار>`\n"
            f"رویدادها: message, schedule, command, user_join, user_leave\n"
            f"عملیات: reply, ai, note, schedule, notify, guard, backup, autopost"
        )

    name = args[0]
    event_type = args[1]
    action_type = args[2]
    action_value = " ".join(args[3:])

    valid_events = ["message", "schedule", "command", "user_join", "user_leave"]
    valid_actions = ["reply", "ai", "note", "schedule", "notify", "guard", "backup", "autopost"]

    if event_type not in valid_events:
        return await event.edit(f"❌ رویداد نامعتبر. رویدادها: {', '.join(valid_events)}")
    if action_type not in valid_actions:
        return await event.edit(f"❌ عملیات نامعتبر. عملیات: {', '.join(valid_actions)}")

    try:
        rule = await automation_repo.create_rule(
            name=name,
            event_type=event_type,
            action_type=action_type,
            action_value=action_value,
        )
        await event.edit(
            f"✅ قانون `{rule.name}` ایجاد شد (شناسه `{rule.id}`)\n"
            f"📌 رویداد: {rule.event_type} → {rule.action_type}"
        )
    except Exception as e:
        await event.edit(f"❌ خطا: {e}")


async def _delete_rule(event, args):
    """حذف قانون."""
    if not args or not args[0].isdigit():
        return await event.edit(f"❌ استفاده: `{PREFIX}اتوماسیون حذف <id>`")

    rule_id = int(args[0])
    success = await automation_repo.delete_rule(rule_id)
    if success:
        await event.edit(f"✅ قانون {rule_id} حذف شد.")
    else:
        await event.edit(f"❌ قانون {rule_id} یافت نشد.")


async def _toggle_rule(event, args, enabled: bool):
    """فعال/غیرفعال کردن قانون."""
    if not args or not args[0].isdigit():
        return await event.edit(f"❌ استفاده: `{PREFIX}اتوماسیون {'فعال' if enabled else 'غیرفعال'} <id>`")

    rule_id = int(args[0])
    success = await automation_repo.toggle_rule(rule_id, enabled)
    if success:
        status = "فعال" if enabled else "غیرفعال"
        await event.edit(f"✅ قانون {rule_id} {status} شد.")
    else:
        await event.edit(f"❌ قانون {rule_id} یافت نشد.")


async def _rule_info(event, args):
    """نمایش اطلاعات یک قانون."""
    if not args or not args[0].isdigit():
        return await event.edit(f"❌ استفاده: `{PREFIX}اتوماسیون اطلاعات <id>`")

    rule_id = int(args[0])
    rule = await automation_repo.get_rule(rule_id)

    if not rule:
        return await event.edit(f"❌ قانون {rule_id} یافت نشد.")

    lines = [
        f"⚡ **قانون `{rule.name}`** (ID: {rule.id})",
        "",
        f"📌 وضعیت: {'✅ فعال' if rule.enabled else '❌ غیرفعال'}",
        f"📌 رویداد: {rule.event_type}",
        f"📌 مقدار رویداد: {rule.event_value or 'ندارد'}",
        f"📌 شرط: {rule.condition or 'ندارد'}",
        f"📌 عملیات: {rule.action_type}",
        f"📌 مقدار عملیات: {rule.action_value}",
        f"📌 اولویت: {rule.priority}",
        f"📌 ایجاد: {rule.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]

    await event.edit("\n".join(lines))