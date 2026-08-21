"""۹) مدیریت گروه: kick / ban / unban / mute / unmute / promote / demote / adminlist / grouplink / lockgroup / unlockgroup (فقط جایی که ادمین هستید)"""
from datetime import datetime, timedelta, timezone

from telethon import events, functions
from telethon.tl.types import ChatBannedRights, ChannelParticipantsAdmins

from ..config import PREFIX
from ..runtime import client
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

@client.on(events.NewMessage(outgoing=True, pattern=pat(["اخراج", "kick"], arg=False)))
async def kick_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    reply = await event.get_reply_message()
    try:
        await client.kick_participant(event.chat_id, reply.sender_id)
        await event.edit("✅ کاربر کیک شد")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["مسدود", "ban"], arg=False)))
async def ban_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    reply = await event.get_reply_message()
    try:
        await client.edit_permissions(event.chat_id, reply.sender_id, view_messages=False)
        await event.edit("✅ کاربر بن شد")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ارتقا", "promote"])))
async def promote_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    title = (event.pattern_match.group(1) or "Admin")[:16]
    reply = await event.get_reply_message()
    try:
        await client.edit_admin(event.chat_id, reply.sender_id, is_admin=True, title=title)
        await event.edit(f"✅ کاربر ادمین شد ({title})")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["تنزل", "demote"], arg=False)))
async def demote_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    reply = await event.get_reply_message()
    try:
        await client.edit_admin(event.chat_id, reply.sender_id, is_admin=False)
        await event.edit("✅ ادمین کاربر حذف شد")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["رفع‌مسدود", "unban"], arg=False)))
async def unban_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    reply = await event.get_reply_message()
    try:
        await client.edit_permissions(event.chat_id, reply.sender_id)
        await event.edit("✅ کاربر آنبن شد")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["بی‌صدا", "mute"])))
async def mute_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    reply = await event.get_reply_message()
    minutes_arg = (event.pattern_match.group(1) or "").strip()
    until_date = None
    if minutes_arg:
        try:
            until_date = datetime.now(timezone.utc) + timedelta(minutes=int(minutes_arg))
        except ValueError:
            return await event.edit(f"مثال: `{PREFIX}بی‌صدا 30` (دقیقه) با ریپلای، یا بدون عدد برای همیشه")
    try:
        await client.edit_permissions(event.chat_id, reply.sender_id, until_date=until_date, send_messages=False)
        suffix = f" برای {minutes_arg} دقیقه" if minutes_arg else ""
        await event.edit(f"🔇 کاربر بی‌صدا شد{suffix}")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["رفع‌سکوت", "unmute"], arg=False)))
async def unmute_handler(event):
    if not event.is_reply:
        return await event.edit("روی پیام کاربر ریپلای کن")
    reply = await event.get_reply_message()
    try:
        await client.edit_permissions(event.chat_id, reply.sender_id, send_messages=True)
        await event.edit("🔊 صدای کاربر برگشت")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ادمین‌ها", "adminlist"], arg=False)))
async def adminlist_handler(event):
    try:
        admins = await client.get_participants(event.chat_id, filter=ChannelParticipantsAdmins)
        if not admins:
            return await event.edit("هیچ ادمینی پیدا نشد")
        lines = ["👮 **ادمین‌های گروه:**\n"]
        for a in admins:
            name = f"{a.first_name or ''} {a.last_name or ''}".strip() or (a.username or str(a.id))
            lines.append(f"• {name}" + (f" (@{a.username})" if a.username else ""))
        await event.edit("\n".join(lines))
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["لینک‌گروه", "grouplink"], arg=False)))
async def grouplink_handler(event):
    try:
        result = await client(functions.messages.ExportChatInviteRequest(peer=event.chat_id))
        await event.edit(f"🔗 لینک دعوت گروه:\n{result.link}")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["قفل‌گروه", "lockgroup"], arg=False)))
async def lockgroup_handler(event):
    try:
        rights = ChatBannedRights(until_date=None, send_messages=True)
        await client(functions.messages.EditChatDefaultBannedRightsRequest(peer=event.chat_id, banned_rights=rights))
        await event.edit("🔒 گروه قفل شد - فقط ادمین‌ها می‌تونن پیام بفرستن")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["بازکردن‌گروه", "unlockgroup"], arg=False)))
async def unlockgroup_handler(event):
    try:
        rights = ChatBannedRights(until_date=None, send_messages=False)
        await client(functions.messages.EditChatDefaultBannedRightsRequest(peer=event.chat_id, banned_rights=rights))
        await event.edit("🔓 گروه باز شد - همه می‌تونن پیام بفرستن")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا: {e}")
