"""
دستورات صندوق ورودی هوشمند: .اینباکس، .ذخیره
"""
import logging
from datetime import datetime, timezone

from telethon import events
from telethon.tl.types import Message

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import inbox_repo

logger = logging.getLogger("selfbot.handlers.inbox")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["اینباکس", "inbox"])))
async def inbox_handler(event):
    """نمایش محتویات صندوق ورودی."""
    args = (event.pattern_match.group(1) or "").strip().split()
    sub = args[0].lower() if args else ""

    if sub in ("مهم", "important"):
        items = await inbox_repo.get_items(importance=1, limit=20)
        title = "📥 **صندوق ورودی - مهم**"
    elif sub in ("خوانده", "read"):
        items = await inbox_repo.get_items(read=True, limit=20)
        title = "📥 **صندوق ورودی - خوانده‌شده**"
    elif sub in ("نخوانده", "unread"):
        items = await inbox_repo.get_items(read=False, limit=20)
        title = "📥 **صندوق ورودی - خوانده‌نشده**"
    elif sub in ("پاک", "clear", "delete"):
        if len(args) > 1 and args[1].isdigit():
            item_id = int(args[1])
            success = await inbox_repo.delete_item(item_id)
            return await event.edit(f"✅ آیتم {item_id} {'حذف شد' if success else 'یافت نشد'}")
        return await event.edit(f"❌ برای حذف: `{PREFIX}اینباکس پاک <id>`")
    else:
        items = await inbox_repo.get_items(limit=20)
        title = "📥 **صندوق ورودی**"

    if not items:
        return await event.edit(f"{title}\n\n🕳️ خالی است.")

    stats = await inbox_repo.get_stats()
    lines = [
        title,
        f"📊 مجموع: {stats['total']}  |  🔴 مهم: {stats['important']}  |  📖 خوانده‌نشده: {stats['unread']}",
        "",
    ]

    for item in items[:15]:
        status = "🔴" if item.importance >= 2 else "🟡" if item.importance >= 1 else "🟢"
        read_mark = "📖" if item.read else "📩"
        sender = item.sender_name or f"ID:{item.sender_id}" if item.sender_id else "ناشناس"
        text_preview = item.text[:60] + ("..." if len(item.text) > 60 else "")
        lines.append(f"`#{item.id}` {status} {read_mark} **{sender}**: {text_preview}")
        lines.append(f"   🕐 {item.date.strftime('%Y-%m-%d %H:%M')} | چت: {item.chat_id}")
        lines.append("")

    if len(items) > 15:
        lines.append(f"... و {len(items) - 15} آیتم دیگر")

    lines.append("")
    lines.append(f"• ذخیره پیام: ریپلای کنید و `{PREFIX}ذخیره`")
    lines.append(f"• نشان‌گذاری خوانده: `{PREFIX}اینباکس خوانده`")
    lines.append(f"• حذف آیتم: `{PREFIX}اینباکس پاک <id>`")

    await event.edit("\n".join(lines))


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ذخیره", "save"])))
async def save_handler(event):
    """ذخیره پیام ریپلای‌شده در صندوق ورودی."""
    if not event.is_reply:
        return await event.edit(f"❌ باید به یک پیام ریپلای کنید: `{PREFIX}ذخیره`")

    reply: Message = await event.get_reply_message()
    if not reply:
        return await event.edit("❌ پیام مورد نظر یافت نشد.")

    # تشخیص اهمیت از آرگومان‌ها
    args = (event.pattern_match.group(1) or "").strip().split()
    importance = 0
    if "مهم" in args:
        importance = 1
    if "بسیارمهم" in args or "فوری" in args:
        importance = 2

    sender_id = reply.sender_id
    sender_name = None
    if sender_id:
        try:
            sender = await event.client.get_entity(sender_id)
            sender_name = sender.first_name or sender.username or str(sender_id)
        except Exception:
            sender_name = str(sender_id)

    text = reply.text or "[پیام بدون متن]"
    chat_id = reply.chat_id
    message_id = reply.id
    date = reply.date or datetime.now(timezone.utc)

    try:
        item = await inbox_repo.save_item(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            sender_id=sender_id,
            sender_name=sender_name,
            date=date.replace(tzinfo=timezone.utc),
            importance=importance,
        )
        await event.edit(
            f"✅ پیام ذخیره شد (شناسه `{item.id}`)\n"
            f"📌 اهمیت: {'🔴 فوری' if importance == 2 else '🟡 مهم' if importance == 1 else '🟢 معمولی'}\n"
            f"📥 برای مشاهده: `{PREFIX}اینباکس`"
        )
    except Exception as e:
        logger.exception("خطا در ذخیره پیام")
        await event.edit(f"❌ خطا: {e}")