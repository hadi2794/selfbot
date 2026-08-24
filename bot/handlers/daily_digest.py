"""۱۷) خلاصه‌ی روزانه: `.خلاصه‌روز`

هر شب سرِ یه ساعتِ مشخص (پیش‌فرض ۲۳:۰۰ به‌وقتِ محلی)، خلاصه‌ای از پیام‌های
همون روز رو به Saved Messages (خودت) می‌فرسته - ترکیبی از سه بخشِ موجودِ
پروژه:
  - scheduler.py   → همون الگوی تسکِ پس‌زمینه‌ای که هر چند ثانیه چک می‌کنه
  - ai.py          → همون هسته‌ی خلاصه‌سازی که `.خلاصه` هم استفاده می‌کنه
  - notification_engine.py → همون مقصدِ نهاییِ اعلان‌ها (Saved Messages)

دو حالت داره:
  - حالتِ کلی (mode=all): همه‌ی چت‌های خصوصی/گروه/کانالِ اکانت رو بررسی
    می‌کنه (تا سقفِ DAILY_DIGEST_MAX_CHATS چت، برای جلوگیری از هزینه/
    تایم‌اوتِ AI روی اکانت‌های خیلی شلوغ).
  - حالتِ سفارشی (mode=custom): فقط چت‌هایی که با `.خلاصه‌روز افزودن <آیدی>`
    اضافه شدن.

اگه AI_API_KEY تنظیم نشده باشه، به‌جای خلاصه‌ی هوشمند یه گزارشِ ساده (تعدادِ
پیام + چندخط آخر) برای هر چت فرستاده می‌شه - قابلیت کاملاً غیرفعال نمی‌شه.
"""
import asyncio
import datetime as dt
import logging
import re

from telethon import events

from .. import ai, config
from ..config import PREFIX, TIMEZONE_OFFSET
from ..runtime import client
from .. import runtime
from ..storage.daily_digest_store import (
    daily_digest_state,
    save_daily_digest,
    add_digest_chat,
    remove_digest_chat,
    clear_digest_chats,
)
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.daily_digest")

_TELEGRAM_MAX = 4096
_CLOCK_RE_HH_MM = re.compile(r"^(\d{1,2}):(\d{2})$")

_DIGEST_SYSTEM = (
    "شما دستیاری هستید که فعالیتِ روزانه‌ی چت‌های تلگرام رو خلاصه می‌کنه. "
    "برای هر چت، فقط موضوعاتِ اصلی/تصمیم‌ها/پیام‌های مهم رو به‌صورتِ چند خطِ "
    "کوتاه (bullet) بنویس - بدون مقدمه‌چینی، بدون تکرارِ کلِ گفتگو. اگه چت "
    "فعالیتِ خاصی نداشته (چت‌احوالپرسی/کم‌پیام)، فقط یه خطِ خیلی کوتاه بنویس."
)


def _local_now() -> dt.datetime:
    return dt.datetime.utcnow() + dt.timedelta(hours=TIMEZONE_OFFSET)


def _today_str() -> str:
    return _local_now().strftime("%Y-%m-%d")


def _status_text() -> str:
    st = daily_digest_state
    status = "روشن ✅" if st["enabled"] else "خاموش ❌"
    mode_fa = "کلی (همه‌ی چت‌ها/گروه‌ها/کانال‌ها)" if st["mode"] == "all" else "سفارشی"
    chats = st["chats"]
    if st["mode"] == "custom":
        if chats:
            chat_lines = "\n".join(f"   – {title} (`{cid}`)" for cid, title in chats.items())
            dest_line = f"{len(chats)} چت\n{chat_lines}"
        else:
            dest_line = f"هیچ‌کدام (اول با `{PREFIX}خلاصه‌روز افزودن` اضافه کن)"
    else:
        dest_line = f"خودکار (تا سقفِ {config.DAILY_DIGEST_MAX_CHATS} چتِ اخیر)"
    return (
        "🌙 **خلاصه‌ی روزانه**\n\n"
        f"• وضعیت: {status}\n"
        f"• ساعتِ ارسال: {st['hour']:02d}:{st['minute']:02d} (وقتِ محلی)\n"
        f"• حالت: {mode_fa}\n"
        f"• چت‌های مقصدِ بررسی: {dest_line}\n"
        f"• آخرین ارسال: {st['last_run_date'] or '(هنوز ارسال نشده)'}\n\n"
        f"راهنما:\n"
        f"`{PREFIX}خلاصه‌روز روشن/خاموش`\n"
        f"`{PREFIX}خلاصه‌روز حالت کلی` یا `{PREFIX}خلاصه‌روز حالت سفارشی`\n"
        f"`{PREFIX}خلاصه‌روز زمان 23:00`\n"
        f"`{PREFIX}خلاصه‌روز افزودن [آیدیِ چت]` (بدون آیدی = همین چت)\n"
        f"`{PREFIX}خلاصه‌روز حذف [آیدیِ چت]`\n"
        f"`{PREFIX}خلاصه‌روز لیست` / `{PREFIX}خلاصه‌روز پاک`\n"
        f"`{PREFIX}خلاصه‌روز الان` (اجرای فوری برای تست)"
    )


@client.on(events.NewMessage(outgoing=True, pattern=pat(["خلاصه‌روز", "خلاصه روز", "dailydigest", "digest"])))
async def daily_digest_handler(event):
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not sub:
        return await event.edit(_status_text())

    if sub in ("روشن", "on"):
        if daily_digest_state["mode"] == "custom" and not daily_digest_state["chats"]:
            return await event.edit(
                f"❌ حالتِ سفارشیه ولی هیچ چتی اضافه نشده. اول با `{PREFIX}خلاصه‌روز افزودن` اضافه کن "
                f"یا با `{PREFIX}خلاصه‌روز حالت کلی` به حالتِ کلی برگرد."
            )
        daily_digest_state["enabled"] = True
        await save_daily_digest()
        return await event.edit(_status_text())

    if sub in ("خاموش", "off"):
        daily_digest_state["enabled"] = False
        await save_daily_digest()
        return await event.edit(_status_text())

    if sub in ("حالت", "mode"):
        val = rest.strip().lower()
        if val in ("کلی", "all", "همه", "عمومی"):
            daily_digest_state["mode"] = "all"
        elif val in ("سفارشی", "custom"):
            daily_digest_state["mode"] = "custom"
        else:
            return await event.edit(f"مثال: `{PREFIX}خلاصه‌روز حالت کلی` یا `{PREFIX}خلاصه‌روز حالت سفارشی`")
        await save_daily_digest()
        return await event.edit(_status_text())

    if sub in ("زمان", "time"):
        m = _CLOCK_RE_HH_MM.match(rest.strip())
        if not m:
            return await event.edit(f"مثال: `{PREFIX}خلاصه‌روز زمان 23:00`")
        hh, mm = int(m.group(1)), int(m.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return await event.edit("⏰ ساعتِ نامعتبر - باید بینِ 00:00 و 23:59 باشه")
        daily_digest_state["hour"] = hh
        daily_digest_state["minute"] = mm
        await save_daily_digest()
        return await event.edit(f"✅ ساعتِ ارسالِ خلاصه‌ی روزانه روی {hh:02d}:{mm:02d} تنظیم شد")

    if sub in ("افزودن", "add"):
        chat_id = int(rest.strip()) if rest.strip().lstrip("-").isdigit() else event.chat_id
        try:
            chat = await client.get_entity(chat_id)
        except Exception as e:
            _record_error()
            return await event.edit(f"❌ خطا در پیداکردنِ چت: {e}")
        title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(chat_id)
        await add_digest_chat(chat_id, title)
        return await event.edit(f"✅ «{title}» به لیستِ خلاصه‌ی سفارشی اضافه شد")

    if sub in ("حذف", "remove"):
        chat_id = int(rest.strip()) if rest.strip().lstrip("-").isdigit() else event.chat_id
        removed = await remove_digest_chat(chat_id)
        if removed:
            return await event.edit(f"🗑 «{removed}» از لیستِ خلاصه‌ی سفارشی حذف شد")
        return await event.edit("این چت توی لیستِ سفارشی نبود")

    if sub in ("لیست", "list"):
        chats = daily_digest_state["chats"]
        if not chats:
            return await event.edit("لیستِ سفارشی خالیه")
        lines = ["📋 **لیستِ خلاصه‌ی سفارشی**", ""]
        for cid, title in chats.items():
            lines.append(f"• {title} (`{cid}`)")
        return await event.edit("\n".join(lines))

    if sub in ("پاک", "clear"):
        await clear_digest_chats()
        return await event.edit("🗑 لیستِ سفارشی پاک شد")

    if sub in ("الان", "فوری", "now"):
        await event.edit("⏳ در حالِ تولیدِ خلاصه‌ی روزانه... (به Saved Messages فرستاده می‌شه)")
        try:
            sent = await _run_daily_digest()
        except Exception as e:
            _record_error()
            logger.exception("خطا در اجرای فوریِ خلاصه‌ی روزانه")
            return await event.edit(f"❌ خطا در تولیدِ خلاصه: {e}")
        return await event.edit(f"✅ خلاصه‌ی {sent} چت به Saved Messages ارسال شد")

    await event.edit(f"دستور نامعتبره. برای وضعیت کامل: `{PREFIX}خلاصه‌روز`")


async def _target_chats() -> list[tuple[int, str]]:
    """لیستِ (chat_id, title) که باید برای خلاصه بررسی بشن."""
    if daily_digest_state["mode"] == "custom":
        return [(int(cid), title) for cid, title in daily_digest_state["chats"].items()]

    result = []
    async for d in client.iter_dialogs(limit=config.DAILY_DIGEST_MAX_CHATS):
        if d.id == (runtime.SELF_ID or 0):
            continue  # خودِ Saved Messages رو خلاصه نکن (مقصدِ خودِ گزارشه)
        result.append((d.id, d.name or str(d.id)))
    return result


def _media_label(m) -> str:
    """
    برچسبِ کوتاهِ فارسی برای پیام‌های رسانه‌ای - چون کانال‌های خبری اغلب
    پست‌هاشون عکس/ویدیو (با کپشنِ کوتاه یا حتی بدونِ کپشن) هستن، اگه فقط
    دنبالِ raw_text باشیم، تقریباً کلِ پستِ روزانه‌ی این کانال‌ها نادیده گرفته
    می‌شه. اینجا نوعِ رسانه رو تشخیص می‌دیم تا حتی بدونِ کپشن هم توی خلاصه لحاظ بشه.
    """
    if m.photo:
        return "[عکس]"
    if m.video or m.gif:
        return "[ویدیو]"
    if m.voice:
        return "[پیامِ صوتی]"
    if m.audio:
        return "[فایلِ صوتی]"
    if m.sticker:
        return "[استیکر]"
    if m.poll:
        return "[نظرسنجی]"
    if m.document:
        return "[فایل]"
    if m.web_preview:
        return "[لینک]"
    return "[رسانه]"


async def _collect_today_lines(chat_id: int, fallback_name: str) -> list[str]:
    """پیام‌های «امروز» (وقتِ محلی) همین چت - متنی یا رسانه‌ای (با برچسب+کپشن)."""
    today_local = _local_now().date()
    lines = []
    try:
        async for m in client.iter_messages(chat_id, limit=config.DAILY_DIGEST_MAX_MESSAGES_PER_CHAT):
            msg_local = (m.date + dt.timedelta(hours=TIMEZONE_OFFSET)) if m.date else None
            if msg_local is None:
                continue
            if msg_local.date() != today_local:
                if msg_local.date() < today_local:
                    break  # پیام‌ها نزولی‌ان؛ رسیدیم به دیروز، دیگه نیازی به ادامه نیست
                continue

            if m.raw_text:
                content = m.raw_text
            elif m.media:
                # پیامِ رسانه‌ایِ بدونِ کپشن (خیلی رایج توی کانال‌های خبری) -
                # به‌جای نادیده‌گرفتنِ کامل، حداقل نوعش رو توی خلاصه لحاظ کن.
                content = _media_label(m)
            else:
                continue  # پیامِ سرویسی (مثلِ «عکسِ گروه عوض شد») - قابلِ خلاصه‌کردن نیست

            sender = m.sender
            # برای پست‌های برادکستِ کانال‌ها معمولاً sender نداریم (Telegram
            # فرستنده‌ی تک‌به‌تک نمی‌فرسته مگر امضای پست فعال باشه)؛ توی این
            # حالت به‌جای «؟»ی بی‌معنی، اسمِ خودِ چت/کانال منطقی‌تره.
            name = (
                getattr(sender, "first_name", None)
                or getattr(sender, "title", None)
                or getattr(sender, "username", None)
                or fallback_name
            )
            lines.append(f"{name}: {content}")
    except Exception:
        logger.exception("خطا در خوندنِ پیام‌های چت %s برای خلاصه‌ی روزانه", chat_id)
        _record_error()
    return list(reversed(lines))


async def _summarize_chat(title: str, lines: list[str]) -> str:
    transcript = "\n".join(lines)
    if len(transcript) > 8000:
        transcript = transcript[-8000:]
    try:
        answer = await ai.ask_ai(
            [
                {"role": "system", "content": _DIGEST_SYSTEM},
                {
                    "role": "user",
                    "content": f"چتِ «{title}» - پیام‌های امروز:\n\n{transcript}",
                },
            ],
            max_tokens=250,
        )
        return answer.strip() or "(بدون خلاصه)"
    except (ai.AIDisabledError, ai.AIRequestError):
        # fallback بدونِ AI: فقط تعداد + چندخطِ آخر
        preview = "\n".join(f"  · {ln}" for ln in lines[-3:])
        return f"({len(lines)} پیام امروز)\n{preview}"


async def _run_daily_digest() -> int:
    """خلاصه‌ی امروز رو می‌سازه و به Saved Messages می‌فرسته. تعدادِ چتِ خلاصه‌شده رو برمی‌گردونه."""
    targets = await _target_chats()
    sections = []
    for chat_id, title in targets:
        lines = await _collect_today_lines(chat_id, title)
        if not lines:
            continue
        summary = await _summarize_chat(title, lines)
        sections.append(f"**{title}**\n{summary}")

    today = _today_str()
    if not sections:
        report = f"🌙 **خلاصه‌ی روزانه** — {today}\n\nامروز پیامِ قابل‌ذکری توی چت‌های بررسی‌شده ثبت نشد."
    else:
        header = f"🌙 **خلاصه‌ی روزانه** — {today} ({len(sections)} چتِ فعال)\n\n"
        report = header + "\n\n".join(sections)

    await _send_chunked(report)
    daily_digest_state["last_run_date"] = today
    await save_daily_digest()
    return len(sections)


async def _send_chunked(text: str) -> None:
    """چون خلاصه‌ی همه‌ی چت‌ها ممکنه از سقفِ ۴۰۹۶ کاراکترِ تلگرام بیشتر بشه، مثلِ ocr.py چندتکه می‌فرستیم."""
    if len(text) <= _TELEGRAM_MAX:
        await client.send_message("me", text)
        return
    remaining = text
    while remaining:
        piece, remaining = remaining[:_TELEGRAM_MAX], remaining[_TELEGRAM_MAX:]
        await client.send_message("me", piece)


async def daily_digest_worker():
    """
    مثلِ clock_updater دقیقاً سرِ شروعِ هر دقیقه بیدار می‌شه؛ اگه ساعت/دقیقه‌ی
    فعلی با تنظیماتِ کاربر یکی بود و امروز هنوز ارسال نشده، خلاصه رو می‌سازه.
    """
    from .. import health
    while True:
        now = _local_now()
        health.update_worker_status("daily_digest", "ok")
        if (
            daily_digest_state["enabled"]
            and now.hour == daily_digest_state["hour"]
            and now.minute == daily_digest_state["minute"]
            and daily_digest_state["last_run_date"] != _today_str()
        ):
            try:
                await _run_daily_digest()
            except Exception as e:
                logger.exception("خطا در اجرای خودکارِ خلاصه‌ی روزانه")
                _record_error()
                health.update_worker_status("daily_digest", "error", str(e))
        now2 = _local_now()
        await asyncio.sleep(max(60 - now2.second, 1))
