"""۱۰) بکاپ‌گیری: پیام‌ها (متن/JSON)، رسانه‌ها، لیست چت‌ها، و کل تنظیمات بات"""
import json
import logging
from datetime import datetime, timezone
from io import BytesIO

from telethon import events

from .. import config
from ..config import PREFIX
from ..runtime import client
from ..clock import clock_state, CLOCK_STYLES, persist_clock_state
from ..storage.notes_store import load_notes, save_note
from ..storage.autopost_store import (
    autopost_state,
    save_autopost,
    add_autopost_chat,
    clear_autopost_chats,
)
from ..storage.assistant_store import assistant_state, save_assistant
from ..storage.font_store import font_state, save_font_state
from ..storage.group_guard_store import (
    group_guard_state,
    set_link_filter as _set_link_filter,
    set_welcome_enabled as _set_welcome_enabled,
    set_welcome_text as _set_welcome_text,
)
from ..storage.stats_store import STATS, record_error as _record_error
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.backup")

BACKUP_MAX_MESSAGES = config.BACKUP_MAX_MESSAGES
BACKUP_MAX_MEDIA = config.BACKUP_MAX_MEDIA

async def _gather_config_snapshot():
    """
    همه‌ی تنظیمات/وضعیتِ ذخیره‌شدنیِ بات (که حالا منبع اصلی‌شون PostgreSQL
    است) رو توی یک دیکشنری واحد جمع می‌کنه - این JSON فقط برای Export/Backup/
    Import دستیِ کاربره؛ PostgreSQL منبع اصلیِ داده باقی می‌مونه.
    """
    return {
        "_kind": "selfbot_config_backup",
        "_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": await load_notes(),
        "autopost": dict(autopost_state),
        "assistant": {
            "mode": assistant_state["mode"],
            "text": assistant_state["text"],
            "delay": assistant_state["delay"],
            "include": list(assistant_state["include"]),
            "exclude": list(assistant_state["exclude"]),
            "auto_detect": assistant_state["auto_detect"],
            "manual_enabled": assistant_state["enabled"] if not assistant_state["auto_detect"] else False,
            "ai_mode": assistant_state["ai_mode"],
        },
        "font": dict(font_state),
        "clock": {
            "enabled": clock_state["enabled"],
            "style": clock_state["style"],
            "base_name": clock_state["base_name"],
        },
        "group_guard": {
            "link_filter_chats": list(group_guard_state["link_filter_chats"]),
            "welcome": {
                str(cid): entry for cid, entry in group_guard_state["welcome"].items()
            },
        },
        "stats": dict(STATS),
    }


async def _apply_config_snapshot(data):
    """
    یه اسنپ‌شات (خروجیِ _gather_config_snapshot) رو روی وضعیت زنده‌ی بات اعمال
    می‌کنه و PostgreSQL رو هم به‌روز می‌کنه (نه فایل JSON - JSON فقط قالبِ
    Import/Export هست). کلیدهایی که توی فایل بکاپ نباشن دست‌نخورده می‌مونن
    (merge، نه جایگزینیِ کامل).
    """
    applied = []

    if isinstance(data.get("notes"), dict):
        for key, text in data["notes"].items():
            await save_note(key, text)
        applied.append("یادداشت‌ها")

    if isinstance(data.get("autopost"), dict):
        a = data["autopost"]
        autopost_state["enabled"] = a.get("enabled", autopost_state["enabled"])
        autopost_state["interval_minutes"] = a.get("interval_minutes", autopost_state["interval_minutes"])
        autopost_state["text"] = a.get("text", autopost_state["text"])
        await save_autopost()
        chats = a.get("chats")
        if isinstance(chats, dict):
            await clear_autopost_chats()
            for cid_str, title in chats.items():
                await add_autopost_chat(int(cid_str), title)
        applied.append("ارسال‌خودکار")

    if isinstance(data.get("assistant"), dict):
        a = data["assistant"]
        assistant_state["mode"] = a.get("mode", assistant_state["mode"])
        assistant_state["text"] = a.get("text", assistant_state["text"])
        assistant_state["delay"] = a.get("delay", assistant_state["delay"])
        assistant_state["include"] = set(a.get("include", []))
        assistant_state["exclude"] = set(a.get("exclude", []))
        assistant_state["auto_detect"] = a.get("auto_detect", assistant_state["auto_detect"])
        assistant_state["ai_mode"] = a.get("ai_mode", assistant_state["ai_mode"])
        if not assistant_state["auto_detect"]:
            assistant_state["enabled"] = a.get("manual_enabled", False)
        await save_assistant()
        applied.append("منشی")

    if isinstance(data.get("font"), dict):
        font_state.update(data["font"])
        await save_font_state()
        applied.append("فونت")

    if isinstance(data.get("clock"), dict):
        if "enabled" in data["clock"]:
            clock_state["enabled"] = bool(data["clock"]["enabled"])
        if data["clock"].get("style") in CLOCK_STYLES:
            clock_state["style"] = data["clock"]["style"]
        if data["clock"].get("base_name"):
            clock_state["base_name"] = data["clock"]["base_name"]
        await persist_clock_state()
        applied.append("ساعت")

    if isinstance(data.get("group_guard"), dict):
        g = data["group_guard"]
        for cid in g.get("link_filter_chats", []):
            try:
                await _set_link_filter(int(cid), True)
            except (TypeError, ValueError):
                continue
        welcome = g.get("welcome")
        if isinstance(welcome, dict):
            for cid_str, entry in welcome.items():
                try:
                    cid = int(cid_str)
                except (TypeError, ValueError):
                    continue
                if not isinstance(entry, dict):
                    continue
                if entry.get("text"):
                    await _set_welcome_text(cid, entry["text"])
                await _set_welcome_enabled(cid, bool(entry.get("enabled")))
        applied.append("مدیریت گروه پیشرفته")

    return applied


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پشتیبان", "backup"])))
async def backup_handler(event):
    args = (event.pattern_match.group(1) or "").strip()
    parts = args.split(None, 1)
    sub = parts[0].lower() if parts else ""

    # ---- .پشتیبان تنظیمات : بکاپ کامل تنظیمات/وضعیتِ بات (برای بازگردانی بعد از ری‌دیپلوی) ----
    if sub in ("تنظیمات", "settings", "config"):
        await event.edit("⏳ در حال آماده‌سازی بکاپ تنظیمات...")
        snapshot = await _gather_config_snapshot()
        content = json.dumps(snapshot, ensure_ascii=False, indent=2)
        bio = BytesIO(content.encode("utf-8"))
        bio.name = f"selfbot_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        await client.send_file(
            "me", bio,
            caption="⚙️ بکاپ تنظیمات سلف‌بات (یادداشت‌ها، منشی، ارسال‌خودکار، فونت، ساعت، آمار)\n"
                    f"برای بازیابی: روی همین فایل ریپلای کن و بنویس `{PREFIX}بازیابی`",
        )
        return await event.edit("✅ بکاپ تنظیمات به Saved Messages ارسال شد")

    # ---- .پشتیبان چت‌ها : بکاپ لیست همه‌ی چت‌ها/دیالوگ‌های اکانت ----
    if sub in ("چت‌ها", "چتها", "chats", "dialogs"):
        await event.edit("⏳ در حال جمع‌آوری لیست چت‌ها...")
        lines = []
        async for d in client.iter_dialogs():
            kind = "کانال" if (d.is_channel and not d.is_group) else ("گروه" if d.is_group else "خصوصی")
            extra = f" — {d.unread_count} خوانده‌نشده" if d.unread_count else ""
            lines.append(f"[{kind}] {d.name} — id={d.id}{extra}")
        content = "\n".join(lines) or "(چتی پیدا نشد)"
        bio = BytesIO(content.encode("utf-8"))
        bio.name = "chats_backup.txt"
        await client.send_file("me", bio, caption=f"📇 بکاپ لیست {len(lines)} چت")
        return await event.edit("✅ بکاپ لیست چت‌ها به Saved Messages ارسال شد")

    # ---- .پشتیبان رسانه <عدد> : دانلود و فوروارد رسانه‌های N پیام آخر به Saved Messages ----
    if sub in ("رسانه", "media"):
        n_str = parts[1].strip() if len(parts) > 1 else ""
        n = int(n_str) if n_str.isdigit() else 200
        n = min(n, BACKUP_MAX_MESSAGES)
        await event.edit(f"⏳ در حال بررسی {n} پیام آخر برای رسانه...")
        sent = 0
        hit_cap = False
        async for m in client.iter_messages(event.chat_id, limit=n):
            if not m.media:
                continue
            if sent >= BACKUP_MAX_MEDIA:
                hit_cap = True
                break
            try:
                date = m.date.strftime("%Y-%m-%d %H:%M")
                await client.send_file("me", m.media, caption=f"🗂 از چت {event.chat_id} — {date}")
                sent += 1
            except Exception:
                _record_error()
                logger.exception("خطا در بکاپ رسانه")
        note = f" (به سقف {BACKUP_MAX_MEDIA} فایل رسیدیم، بقیه ارسال نشدن)" if hit_cap else ""
        return await event.edit(f"✅ {sent} فایل رسانه به Saved Messages ارسال شد{note}")

    # ---- .پشتیبان json <عدد> : بکاپ ساختاریافته‌ی پیام‌ها (برای پردازش برنامه‌ای) ----
    as_json = sub in ("json", "جیسون")
    n_str = (parts[1].strip() if len(parts) > 1 else "") if as_json else args
    n = int(n_str) if n_str and n_str.isdigit() else 100
    n = min(n, BACKUP_MAX_MESSAGES)
    await event.edit(f"⏳ در حال گرفتن بکاپ {n} پیام آخر...")

    if as_json:
        items = []
        async for m in client.iter_messages(event.chat_id, limit=n):
            sender = await m.get_sender()
            name = getattr(sender, "first_name", None) if sender else None
            items.append({
                "id": m.id,
                "date": m.date.isoformat(),
                "sender_id": m.sender_id,
                "sender_name": name,
                "text": m.raw_text or None,
                "media_type": type(m.media).__name__ if m.media else None,
            })
        items.reverse()
        content = json.dumps(items, ensure_ascii=False, indent=2)
        bio = BytesIO(content.encode("utf-8"))
        bio.name = "backup.json"
    else:
        lines = []
        async for m in client.iter_messages(event.chat_id, limit=n):
            sender = await m.get_sender()
            name = getattr(sender, "first_name", "؟") if sender else "؟"
            date = m.date.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{date}] {name}: {m.raw_text or '(media)'}")
        lines.reverse()
        content = "\n".join(lines) or "(چتی برای بکاپ پیدا نشد)"
        bio = BytesIO(content.encode("utf-8"))
        bio.name = "backup.txt"

    await client.send_file("me", bio, caption=f"📦 بکاپ {n} پیام از چت {event.chat_id}")
    await event.edit("✅ بکاپ به Saved Messages ارسال شد")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["بازیابی", "restore"], arg=False)))
async def restore_handler(event):
    """با ریپلای روی فایلِ خروجیِ `.پشتیبان تنظیمات`، تنظیمات بات رو (در PostgreSQL) برمی‌گردونه."""
    if not event.is_reply:
        return await event.edit(f"روی فایل بکاپِ تنظیمات (خروجیِ `{PREFIX}پشتیبان تنظیمات`) ریپلای کن")
    reply = await event.get_reply_message()
    if not reply.file:
        return await event.edit("پیام ریپلای‌شده فایل نداره")
    await event.edit("⏳ در حال بازیابی تنظیمات...")
    try:
        raw = await client.download_media(reply, file=bytes)
        data = json.loads(raw.decode("utf-8"))
        if data.get("_kind") != "selfbot_config_backup":
            return await event.edit("❌ این فایل، بکاپ تنظیماتِ سلف‌بات نیست")
        applied = await _apply_config_snapshot(data)
        if not applied:
            return await event.edit("چیزی برای بازیابی توی این فایل پیدا نشد")
        await event.edit("✅ بازیابی شد: " + "، ".join(applied))
    except json.JSONDecodeError:
        await event.edit("❌ فایل معتبر (JSON) نیست")
    except Exception as e:
        _record_error()
        await event.edit(f"❌ خطا در بازیابی: {e}")
