"""۱۱) ارسال خودکار متن به گروه (autopost)"""
import asyncio
import logging
import time

from telethon import errors, events

from .. import config
from ..config import PREFIX
from ..runtime import client
from ..storage.autopost_store import (
    autopost_state,
    save_autopost,
    add_autopost_chat,
    remove_autopost_chat,
    clear_autopost_chats,
    reset_autopost_timer as _reset_autopost_timer,
    get_next_run,
    get_force_now,
    set_force_now,
)
from ..storage.stats_store import STATS, record_error as _record_error, save_stats
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.autopost")


def _autopost_status_text():
    status = "روشن ✅" if autopost_state["enabled"] else "خاموش ❌"
    n = autopost_state["interval_minutes"]
    chats = autopost_state["chats"]
    if chats:
        chat_lines = "\n".join(f"   – {title} (`{cid}`)" for cid, title in chats.items())
        dest_line = f"{len(chats)} گروهِ مشخص\n{chat_lines}"
    else:
        dest_line = f"هیچ‌کدام (اول با `{PREFIX}ارسال‌خودکار افزودن` اضافه کن)"
    text_preview = autopost_state["text"] or "(تنظیم نشده)"
    return (
        "🔁 **ارسال خودکار متن**\n\n"
        f"• وضعیت: {status}\n"
        f"• فاصله: {n} دقیقه\n"
        f"• گروه‌های مقصد: {dest_line}\n"
        f"• متن: {text_preview}\n\n"
        f"راهنما: `{PREFIX}ارسال‌خودکار روشن/خاموش` ، `{PREFIX}ارسال‌خودکار فاصله <عدد>` ، "
        f"`{PREFIX}ارسال‌خودکار متن <متن>` ، `{PREFIX}ارسال‌خودکار افزودن/حذف` ، `{PREFIX}ارسال‌خودکار فوری`"
    )


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ارسال‌خودکار", "autopost"])))
async def autopost_handler(event):
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not sub:
        return await event.edit(_autopost_status_text())

    if sub in ("روشن", "on"):
        if not autopost_state["text"]:
            return await event.edit(f"❌ اول یه متن ست کن: `{PREFIX}ارسال‌خودکار متن <متن>`")
        if not autopost_state["chats"]:
            return await event.edit(f"❌ اول حداقل یه گروه اضافه کن: `{PREFIX}ارسال‌خودکار افزودن` (داخل خود گروه بفرست)")
        autopost_state["enabled"] = True
        _reset_autopost_timer()
        await save_autopost()
        return await event.edit(_autopost_status_text())

    if sub in ("خاموش", "off"):
        autopost_state["enabled"] = False
        await save_autopost()
        return await event.edit(_autopost_status_text())

    if sub in ("فاصله", "interval"):
        if not rest.strip().isdigit():
            return await event.edit(f"مثال: `{PREFIX}ارسال‌خودکار فاصله 5`")
        n = max(int(rest.strip()), config.AUTOPOST_MIN_INTERVAL_MINUTES)
        autopost_state["interval_minutes"] = n
        _reset_autopost_timer()
        await save_autopost()
        warn = "" if n >= 5 else "\n⚠️ فاصله‌ی کمتر از ۵ دقیقه ریسک محدودیت از طرف تلگرام رو بالا می‌بره."
        return await event.edit(f"✅ فاصله روی {n} دقیقه تنظیم شد{warn}")

    if sub in ("متن", "text"):
        text = rest
        if not text and event.is_reply:
            reply = await event.get_reply_message()
            text = reply.raw_text or ""
        if not text:
            return await event.edit(
                f"مثال: `{PREFIX}ارسال‌خودکار متن میو` یا ریپلای روی یه پیام + `{PREFIX}ارسال‌خودکار متن`"
            )
        autopost_state["text"] = text
        await save_autopost()
        return await event.edit("✅ متن ارسال خودکار ذخیره شد")

    if sub in ("افزودن", "add"):
        chat_id = int(rest.strip()) if rest.strip().lstrip("-").isdigit() else event.chat_id
        try:
            chat = await client.get_entity(chat_id)
        except Exception as e:
            _record_error()
            return await event.edit(f"❌ خطا در پیداکردن چت: {e}")
        title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(chat_id)
        await add_autopost_chat(chat_id, title)
        return await event.edit(f"✅ «{title}» به لیست مقصدها اضافه شد")

    if sub in ("حذف", "remove"):
        chat_id = int(rest.strip()) if rest.strip().lstrip("-").isdigit() else event.chat_id
        removed = await remove_autopost_chat(chat_id)
        if removed:
            return await event.edit(f"🗑 «{removed}» از لیست مقصدها حذف شد")
        return await event.edit("این چت توی لیست مقصدها نبود")

    if sub in ("پاک", "clear"):
        await clear_autopost_chats()
        return await event.edit("🗑 همه‌ی مقصدها پاک شدن")

    if sub in ("فوری", "now"):
        set_force_now(True)
        return await event.edit("⏩ ارسال فوری توی صف قرار گرفت (تا ۵ ثانیه دیگه)")

    await event.edit(f"دستور نامعتبره. برای وضعیت کامل: `{PREFIX}ارسال‌خودکار`")


async def autopost_worker():
    from .. import health
    while True:
        await asyncio.sleep(5)
        health.update_worker_status("autopost", "ok")
        if not autopost_state["enabled"] or not autopost_state["chats"] or not autopost_state["text"]:
            continue
        if get_force_now() or time.time() >= get_next_run():
            set_force_now(False)
            for chat_id_str in list(autopost_state["chats"].keys()):
                try:
                    await client.send_message(int(chat_id_str), autopost_state["text"])
                    STATS["autopost_ok"] += 1
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    logger.exception("خطا در ارسال خودکار به %s", chat_id_str)
                    STATS["autopost_fail"] += 1
                    _record_error()
            _reset_autopost_timer()
            await save_stats()
