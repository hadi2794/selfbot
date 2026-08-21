"""۴) مدیریت پیام: del / purge / pin / unpin"""
from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..utils import pat

@client.on(events.NewMessage(outgoing=True, pattern=pat(["حذف", "del"], arg=False)))
async def del_handler(event):
    if event.is_reply:
        reply = await event.get_reply_message()
        await reply.delete()
    await event.delete()


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پاکسازی", "purge"])))
async def purge_handler(event):
    count_str = event.pattern_match.group(1)
    if event.is_reply:
        reply = await event.get_reply_message()
        ids = []
        async for m in client.iter_messages(event.chat_id, min_id=reply.id - 1, max_id=event.id):
            ids.append(m.id)
        await client.delete_messages(event.chat_id, ids)
    elif count_str and count_str.isdigit():
        n = int(count_str)
        ids = []
        async for m in client.iter_messages(event.chat_id, limit=n + 1):
            ids.append(m.id)
        await client.delete_messages(event.chat_id, ids)
    else:
        await event.edit(f"مثال: `{PREFIX}پاکسازی 10` یا ریپلای روی پیام + `{PREFIX}پاکسازی`")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["سنجاق", "pin"], arg=False)))
async def pin_handler(event):
    if not event.is_reply:
        return await event.edit("روی یک پیام ریپلای کن")
    reply = await event.get_reply_message()
    await client.pin_message(event.chat_id, reply.id)
    await event.edit("📌 پین شد")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["برداشتن‌سنجاق", "unpin"], arg=False)))
async def unpin_handler(event):
    if not event.is_reply:
        return await event.edit("روی یک پیام ریپلای کن")
    reply = await event.get_reply_message()
    await client.unpin_message(event.chat_id, reply.id)
    await event.edit("📌 آنپین شد")
