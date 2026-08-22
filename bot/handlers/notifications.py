"""
دستورات مرکز اعلان‌ها: .اعلان
"""
import logging
import json
from typing import List, Dict, Any

from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import notification_repo

logger = logging.getLogger("selfbot.handlers.notifications")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["اعلان", "notif"])))
async def notification_handler(event):
    """مدیریت قوانین اعلان."""
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
    """نمایش لیست قوانین."""
    rules = await notification_repo.get_rules(enabled_only=False)

    if not rules:
        return await event.edit(
            f"🔔 **مرکز اعلان‌ها**\n\n"
            f"🕳️ هیچ قانونی تعریف نشده.\n\n"
            f"• ایجاد قانون: `{PREFIX}اعلان جدید <نام> <نوع> <مقدار> <عملیات>`\n"
            f"• مثال: `{PREFIX}اعلان جدید vip keyword VPN notify`\n\n"
            f"⚠️ توجه: فعلاً این قوانین فقط ذخیره می‌شن؛ موتورِ اجرایی‌شون هنوز وصل نیست "
            f"(برای یه نسخه‌ی کاملاً کارکننده از همین ایده، فعلاً از `{PREFIX}اتوماسیون` "
            f"با event=message و action=notify استفاده کن)."
        )

    lines = ["🔔 **مرکز اعلان‌ها**", "⚠️ فعلاً فقط ذخیره می‌شن؛ موتورِ اجرایی‌شون وصل نیست (پایین رو ببین)", ""]

    for rule in rules:
        status = "✅" if rule.enabled else "❌"
        lines.append(f"{status} `#{rule.id}` **{rule.name}**")
        lines.append(f"   ▸ نوع: {rule.trigger_type} | مقدار: {rule.trigger_value[:40]}...")
        lines.append(f"   ▸ عملیات: {rule.action_type} {rule.action_value or ''}")
        lines.append("")

    lines.append("")
    lines.append(f"• جزئیات: `{PREFIX}اعلان اطلاعات <id>`")
    lines.append(f"• فعال/غیرفعال: `{PREFIX}اعلان فعال <id>` / `{PREFIX}اعلان غیرفعال <id>`")
    lines.append(f"• حذف: `{PREFIX}اعلان حذف <id>`")

    await event.edit("\n".join(lines))


async def _create_rule(event, args):
    """ایجاد قانون جدید."""
    if len(args) < 4:
        return await event.edit(
            f"❌ استفاده: `{PREFIX}اعلان جدید <نام> <نوع> <مقدار> <عملیات>`\n"
            f"انواع: message, keyword, user, time\n"
            f"عملیات: notify, save, forward, reply"
        )

    name = args[0]
    trigger_type = args[1]
    trigger_value = " ".join(args[2:-1])
    action_type = args[-1]

    valid_triggers = ["message", "keyword", "user", "time"]
    valid_actions = ["notify", "save", "forward", "reply"]

    if trigger_type not in valid_triggers:
        return await event.edit(f"❌ نوع نامعتبر. انواع: {', '.join(valid_triggers)}")
    if action_type not in valid_actions:
        return await event.edit(f"❌ عملیات نامعتبر. عملیات: {', '.join(valid_actions)}")

    try:
        rule = await notification_repo.create_rule(
            name=name,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            action_type=action_type,
        )
        await event.edit(
            f"✅ قانون `{rule.name}` ایجاد شد (شناسه `{rule.id}`)\n"
            f"📌 نوع: {rule.trigger_type} → {rule.action_type}"
        )
    except Exception as e:
        await event.edit(f"❌ خطا: {e}")


async def _delete_rule(event, args):
    """حذف قانون."""
    if not args or not args[0].isdigit():
        return await event.edit(f"❌ استفاده: `{PREFIX}اعلان حذف <id>`")

    rule_id = int(args[0])
    success = await notification_repo.delete_rule(rule_id)
    if success:
        await event.edit(f"✅ قا��ون {rule_id} حذف شد.")
    else:
        await event.edit(f"❌ قانون {rule_id} یافت نشد.")


async def _toggle_rule(event, args, enabled: bool):
    """فعال/غیرفعال کردن قانون."""
    if not args or not args[0].isdigit():
        return await event.edit(f"❌ استفاده: `{PREFIX}اعلان {'فعال' if enabled else 'غیرفعال'} <id>`")

    rule_id = int(args[0])
    success = await notification_repo.toggle_rule(rule_id, enabled)
    if success:
        status = "فعال" if enabled else "غیرفعال"
        await event.edit(f"✅ قانون {rule_id} {status} شد.")
    else:
        await event.edit(f"❌ قانون {rule_id} یافت نشد.")


async def _rule_info(event, args):
    """نمایش اطلاعات یک قانون."""
    if not args or not args[0].isdigit():
        return await event.edit(f"❌ استفاده: `{PREFIX}اعلان اطلاعات <id>`")

    rule_id = int(args[0])
    rule = await notification_repo.get_rule(rule_id)

    if not rule:
        return await event.edit(f"❌ قانون {rule_id} یافت نشد.")

    lines = [
        f"🔔 **قانون `{rule.name}`** (ID: {rule.id})",
        "",
        f"📌 وضعیت: {'✅ فعال' if rule.enabled else '❌ غیرفعال'}",
        f"📌 نوع رویداد: {rule.trigger_type}",
        f"📌 مقدار: {rule.trigger_value}",
        f"📌 عملیات: {rule.action_type}",
        f"📌 مقدار عملیات: {rule.action_value or 'ندارد'}",
        f"📌 ایجاد: {rule.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]

    await event.edit("\n".join(lines))