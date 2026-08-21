"""۳) یادداشت‌ها: note / notes / getnote / delnote"""
from telethon import events

from ..config import PREFIX
from ..runtime import client
from ..storage.notes_store import delete_note, load_notes, save_note
from ..utils import pat

@client.on(events.NewMessage(outgoing=True, pattern=pat(["یادداشت", "note"])))
async def note_handler(event):
    args = event.pattern_match.group(1)
    if not args or " " not in args:
        return await event.edit(f"مثال: `{PREFIX}یادداشت keyname متن یادداشت`")
    key, text = args.split(" ", 1)
    await save_note(key, text)
    await event.edit(f"📝 یادداشت `{key}` ذخیره شد")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["یادداشت‌ها", "notes"], arg=False)))
async def notes_list_handler(event):
    notes = await load_notes()
    if not notes:
        return await event.edit("هیچ یادداشتی وجود نداره")
    text = "📒 لیست یادداشت‌ها:\n" + "\n".join(f"• `{k}`" for k in notes)
    await event.edit(text)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["نمایش‌یادداشت", "getnote"])))
async def getnote_handler(event):
    key = event.pattern_match.group(1)
    notes = await load_notes()
    if not key or key not in notes:
        return await event.edit("همچین یادداشتی پیدا نشد")
    await event.edit(f"📝 `{key}`:\n{notes[key]}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["حذف‌یادداشت", "delnote"])))
async def delnote_handler(event):
    key = event.pattern_match.group(1)
    notes = await load_notes()
    if not key or key not in notes:
        return await event.edit("همچین یادداشتی پیدا نشد")
    await delete_note(key)
    await event.edit(f"🗑 یادداشت `{key}` حذف شد")
