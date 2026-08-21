"""۷) پروفایل: setbio / setname / setpic / clock / clockstyle"""
from datetime import datetime, timedelta

from telethon import events, functions

from .. import config
from ..config import PREFIX
from ..runtime import client
from ..clock import (
    clock_state,
    CLOCK_STYLES,
    CLOCK_STYLE_ORDER,
    apply_clock_now as _apply_clock_now,
    persist_clock_state,
)
from ..utils import pat

@client.on(events.NewMessage(outgoing=True, pattern=pat(["بیو", "setbio"])))
async def setbio_handler(event):
    bio = event.pattern_match.group(1)
    if not bio:
        return await event.edit(f"مثال: `{PREFIX}بیو بیو جدید`")
    await client(functions.account.UpdateProfileRequest(about=bio))
    await event.edit("✅ بیو بروزرسانی شد")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["نام", "setname"])))
async def setname_handler(event):
    name = event.pattern_match.group(1)
    if not name:
        return await event.edit(f"مثال: `{PREFIX}نام نام جدید`")
    clock_state["base_name"] = name
    if clock_state["enabled"]:
        await _apply_clock_now()
    else:
        await client(functions.account.UpdateProfileRequest(first_name=name))
    await persist_clock_state()
    await event.edit("✅ نام پایه بروزرسانی شد")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["عکس", "setpic"], arg=False)))
async def setpic_handler(event):
    if not event.is_reply:
        return await event.edit("روی یک عکس ریپلای کن")
    reply = await event.get_reply_message()
    if not reply.photo:
        return await event.edit("پیام ریپلای‌شده عکس نیست")
    file_bytes = await client.download_media(reply, file=bytes)
    uploaded = await client.upload_file(file_bytes, file_name="pic.jpg")
    await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
    await event.edit("✅ عکس پروفایل تغییر کرد")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ساعت", "clock"])))
async def clock_toggle_handler(event):
    arg = (event.pattern_match.group(1) or "").strip().lower()
    if arg in ("خاموش", "off"):
        clock_state["enabled"] = False
        await persist_clock_state()
        await event.edit("🕐 ساعت زنده خاموش شد")
    elif arg in ("روشن", "on"):
        clock_state["enabled"] = True
        await persist_clock_state()
        await event.edit("🕐 ساعت زنده روشن شد (طی چند ثانیه اعمال می‌شه)")
    else:
        await event.edit(f"استفاده: `{PREFIX}ساعت روشن` یا `{PREFIX}ساعت خاموش`")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["مدل‌ساعت", "شکل‌ساعت", "clockstyle"])))
async def clockstyle_handler(event):
    arg = (event.pattern_match.group(1) or "").strip().lower()
    if not arg or arg in ("فهرست", "list"):
        now = datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)
        lines = ["🎨 **مدل‌های ساعت زنده:**\n"]
        for name in CLOCK_STYLE_ORDER:
            preview = CLOCK_STYLES[name](now.hour, now.minute)
            marker = "✅" if name == clock_state["style"] else "▫️"
            lines.append(f"{marker} `{name}` → {preview}")
        lines.append(f"\nبرای تغییر: `{PREFIX}مدل‌ساعت <نام>` یا `{PREFIX}مدل‌ساعت بعدی`")
        return await event.edit("\n".join(lines))

    if arg in ("بعدی", "next"):
        idx = CLOCK_STYLE_ORDER.index(clock_state["style"])
        new_style = CLOCK_STYLE_ORDER[(idx + 1) % len(CLOCK_STYLE_ORDER)]
    elif arg in CLOCK_STYLES:
        new_style = arg
    else:
        return await event.edit(f"استایل نامعتبره. برای دیدن فهرست: `{PREFIX}مدل‌ساعت فهرست`")

    clock_state["style"] = new_style
    preview = CLOCK_STYLES[new_style](*(datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)).timetuple()[3:5])
    await persist_clock_state()
    await event.edit(f"✅ استایل ساعت روی `{new_style}` تنظیم شد\nنمونه: {preview}")
    await _apply_clock_now()
