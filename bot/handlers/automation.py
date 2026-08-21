"""
دستورات مدیریت قوانین اتوماسیون.
"""

import json
import logging
from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..storage.automation_store import (
    get_active_rules,
    get_rule,
    invalidate_cache,
    reload_rule,
)
from ..repositories import automation_repo
from ..utils import pat
from ..storage.stats_store import record_error as _record_error

logger = logging.getLogger("selfbot.handlers.automation")

TRIGGER_TYPES = ["message", "command", "event", "schedule", "mention", "join"]
ACTION_TYPES = ["reply", "message", "note", "reminder", "assistant", "autopost", "backup", "stats", "ai", "webhook"]

def _format_rule(rule) -> str:
    """قالب‌بندی یک قانون برای نمایش."""
    status_emoji = {
        "active": "✅",
        "paused": "⏸️",
        "archived": "📦",
    }.get(rule.status, "❓")
    
    trigger_desc = {
        "message": "پیام جدید",
        "command": "دستور",
        "event": "رویداد",
        "schedule": "زمان‌بندی",
        "mention": "منشن",
        "join": "عضویت",
    }.get(rule.trigger_type, rule.trigger_type)
    
    action_desc = {
        "reply": "پاسخ",
        "message": "ارسال پیام",
        "note": "یادداشت",
        "reminder": "یادآوری",
        "assistant": "منشی",
        "autopost": "ارسال خودکار",
        "backup": "بکاپ",
        "stats": "آمار",
        "ai": "هوش مصنوعی",
        "webhook": "وب‌هوک",
    }.get(rule.action_type, rule.action_type)
    
    lines = [
        f"{status_emoji} **#{rule.id}** {rule.name}",
        f"  📌 شرط: {trigger_desc}",
        f"  ⚡ عمل: {action_desc}",
    ]
    if rule.description:
        lines.append(f"  📝 {rule.description}")
    if rule.schedule_cron:
        lines.append(f"  🕐 زمان‌بندی: {rule.schedule_cron}")
    if rule.cooldown_seconds:
        lines.append(f"  ⏱️ فاصله: {rule.cooldown_seconds}s")
    if rule.max_executions:
        lines.append(f"  🔢 حداکثر: {rule.max_executions} (اجرا: {rule.executions_count})")
    if rule.last_executed_at:
        lines.append(f"  🕒 آخرین اجرا: {rule.last_executed_at.strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["اتوماسیون", "automation"])))
async def automation_handler(event):
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if not sub or sub in ("لیست", "list", "status"):
        # نمایش همه قوانین
        rules = await get_active_rules()
        if not rules:
            return await event.edit(
                f"🤖 **موتور اتوماسیون**\n\n"
                f"هیچ قانون فعالی وجود ندارد.\n"
                f"برای ساخت قانون جدید:\n"
                f"`{PREFIX}اتوماسیون جدید`"
            )
        lines = ["🤖 **قوانین اتوماسیون فعال**\n"]
        for rule in rules:
            lines.append(_format_rule(rule))
            lines.append("")
        await event.edit("\n".join(lines))
        return

    if sub in ("جدید", "new", "add"):
        # راهنمای ساخت قانون جدید
        return await event.edit(
            f"🧠 **ساخت قانون جدید اتوماسیون**\n\n"
            f"فرمت: `{PREFIX}اتوماسیون جدید <نام> | شرط | عمل`\n\n"
            f"**شرط‌ها:**\n"
            f"• `message` - هر پیام جدید\n"
            f"• `command` - دستور خاص\n"
            f"• `schedule` - زمان‌بندی\n"
            f"• `mention` - منشن شدن\n"
            f"• `join` - عضویت جدید\n\n"
            f"**عمل‌ها:**\n"
            f"• `reply:<متن>` - پاسخ دادن\n"
            f"• `message:<متن>` - ارسال پیام\n"
            f"• `note:<کلید>:<متن>` - ذخیره یادداشت\n"
            f"• `reminder:<زمان>:<متن>` - ثبت یادآوری\n"
            f"• `assistant:<حالت>` - تغییر منشی\n"
            f"• `autopost:<عملیات>` - کنترل ارسال خودکار\n"
            f"• `stats` - نمایش آمار\n"
            f"• `ai:<سوال>` - پرسش از هوش مصنوعی\n\n"
            f"**مثال‌ها:**\n"
            f"`{PREFIX}اتوماسیون جدید خوش‌آمدگویی | join | reply:سلام به گروه خوش آمدید!`\n"
            f"`{PREFIX}اتوماسیون جدید یادآوری روزانه | schedule:0 9 * * * | reminder:1h:گزارش روزانه را بفرست`"
        )

    if sub in ("فعال", "enable"):
        if not arg.isdigit():
            return await event.edit(f"مثال: `{PREFIX}اتوماسیون فعال 3`")
        rule_id = int(arg)
        rule = await automation_repo.update_rule(rule_id, status="active")
        if not rule:
            return await event.edit("قانونی با این شناسه یافت نشد")
        await reload_rule(rule_id)
        return await event.edit(f"✅ قانون #{rule_id} فعال شد")

    if sub in ("غیرفعال", "disable", "pause"):
        if not arg.isdigit():
            return await event.edit(f"مثال: `{PREFIX}اتوماسیون غیرفعال 3`")
        rule_id = int(arg)
        rule = await automation_repo.update_rule(rule_id, status="paused")
        if not rule:
            return await event.edit("قانونی با این شناسه یافت نشد")
        await reload_rule(rule_id)
        return await event.edit(f"⏸️ قانون #{rule_id} غیرفعال شد")

    if sub in ("حذف", "delete", "remove"):
        if not arg.isdigit():
            return await event.edit(f"مثال: `{PREFIX}اتوماسیون حذف 3`")
        rule_id = int(arg)
        deleted = await automation_repo.delete_rule(rule_id)
        if not deleted:
            return await event.edit("قانونی با این شناسه یافت نشد")
        await invalidate_cache()
        return await event.edit(f"🗑️ قانون #{rule_id} حذف شد")

    if sub in ("اطلاعات", "info", "show"):
        if not arg.isdigit():
            return await event.edit(f"مثال: `{PREFIX}اتوماسیون اطلاعات 3`")
        rule_id = int(arg)
        rule = await get_rule(rule_id)
        if not rule:
            return await event.edit("قانونی با این شناسه یافت نشد")
        return await event.edit(_format_rule(rule))

    if sub in ("بازنشانی", "reset"):
        if not arg.isdigit():
            return await event.edit(f"مثال: `{PREFIX}اتوماسیون بازنشانی 3`")
        rule_id = int(arg)
        await automation_repo.reset_executions(rule_id)
        await reload_rule(rule_id)
        return await event.edit(f"🔄 شمارندهٔ قانون #{rule_id} بازنشانی شد")

    await event.edit(f"دستور نامعتبر. برای راهنما: `{PREFIX}اتوماسیون جدید`")