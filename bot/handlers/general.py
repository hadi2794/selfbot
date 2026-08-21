"""۱) عمومی: ping / alive / id / info"""
import time
from datetime import timedelta

from telethon import events

from .. import config
from ..runtime import client, START_TIME
from ..clock import clock_state
from ..utils import pat


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پینگ", "ping"], arg=False)))
async def ping_handler(event):
    start = time.time()
    msg = await event.edit("🏓 Pinging...")
    delta = (time.time() - start) * 1000
    await msg.edit(f"🏓 Pong!\n⏱ {delta:.0f} ms")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["فعال", "alive"], arg=False)))
async def alive_handler(event):
    uptime = str(timedelta(seconds=int(time.time() - START_TIME)))
    text = (
        "🤖 **سلف‌بات فعال است**\n"
        f"⏳ Uptime: `{uptime}`\n"
        f"🔡 Prefix: `{config.PREFIX}`\n"
        f"🕐 ساعت زنده: {'روشن' if clock_state['enabled'] else 'خاموش'}"
    )
    await event.edit(text)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["آیدی", "id"], arg=False)))
async def id_handler(event):
    text = f"🆔 Chat ID: `{event.chat_id}`\n"
    if event.is_reply:
        reply = await event.get_reply_message()
        text += f"👤 User ID: `{reply.sender_id}`\n"
        text += f"✉️ Message ID: `{reply.id}`"
    await event.edit(text)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["اطلاعات", "info"], arg=False)))
async def info_handler(event):
    if event.is_reply:
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
    else:
        user = await client.get_me()
    text = (
        f"👤 **نام:** {user.first_name or ''} {user.last_name or ''}\n"
        f"🆔 **آیدی:** `{user.id}`\n"
        f"🔗 **یوزرنیم:** @{user.username if user.username else '---'}"
    )
    await event.edit(text)
