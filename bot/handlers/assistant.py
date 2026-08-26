"""۸) منشی چت: پاسخِ خودکارِ هوشمند با تشخیصِ ترکیبیِ آنلاین/آفلاین

تشخیصِ «آفلاین‌بودن» (که تعیین می‌کنه منشی خودش کِی روشن/خاموش بشه) از دو
سیگنالِ کاملاً محلی (بدونِ هیچ تماسی با تلگرام) تشکیل شده - نگاهِ کاملِ
منطق پایینِ فایل، تابعِ _recompute_enabled_from_signals:

  ۱) زمان‌بندی: پنجره‌های ثابتِ ساعتی که خودت تعریف می‌کنی (مثلاً خواب:
     ۲۳:۰۰ تا ۰۸:۰۰). داخلِ این بازه‌ها، صرف‌نظر از فعالیتِ اخیرت، منشی
     همیشه روشنه - چون این یعنی «قطعاً در دسترس نیستم»، حتی اگه یه لحظه
     گوشیت رو چک کنی یا جواب بدی.
  ۲) فعالیت: اگه الان توی هیچ پنجره‌ی زمان‌بندی‌شده‌ای نباشیم، به همون روشِ
     قبلی برمی‌گردیم - آخرین باری که از هر دستگاهی یه پیامِ خروجیِ واقعی
     فرستادی. بعدِ ASSISTANT_ONLINE_THRESHOLD ثانیه سکوت، آفلاین حساب
     می‌شی و منشی روشن می‌شه.

یعنی زمان‌بندی یه لایه‌ی «حتماً روشن» روی همون تشخیصِ رفتاریِ قبلیه، نه یه
حالتِ جایگزین: اگه هیچ پنجره‌ای تعریف نکنی، رفتار دقیقاً همون قبلیه. جزئیاتِ
پنجره‌ها با `{PREFIX}منشی زمان‌بندی` مدیریت می‌شن.

قفلِ دستی (`.منشی روشن`/`.منشی خاموش`) هنوز کاملاً بالادستِ هر دو سیگنالِ
بالاست: وقتی auto_detect=False باشه، نه فعالیت نه زمان‌بندی هیچ‌کدوم دست به
enabled نمی‌زنن.
"""
import asyncio
import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone

from telethon import events

from .. import ai, config, runtime
from ..config import PREFIX
from ..runtime import client
from ..storage.assistant_store import (
    add_schedule_window,
    assistant_state,
    clear_schedule_windows,
    remove_schedule_window,
    save_assistant,
)
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from . import audio

logger = logging.getLogger("selfbot.handlers.assistant")

# آخرین باری که یه پیامِ خروجیِ واقعی (از هر دستگاهی، نه فقط همین اسکریپت -
# چون تلگرام پیام‌های خروجیِ خودت رو بینِ همه‌ی سشن‌های اکانت sync می‌کنه)
# دیده شده. این تنها منبعِ تشخیصِ آنلاین/آفلاینِ این فایله (نه سؤال‌کردن از
# تلگرام «سشن‌های دیگه‌م الان چی‌ان» - اون روش قبلاً امتحان شد و چون
# account.getAuthorizations برای پرسوجوی مکرر و همیشگی طراحی نشده، دیر یا
# زود با FloodWaitError ریت‌لیمیت می‌شد و enabled برای همیشه گیر می‌کرد؛
# نگاهِ کاملِ ماجرا توی داکیومنتِ assistant_status_watcher پایینِ فایل).
_last_self_activity = datetime.min.replace(tzinfo=timezone.utc)

# شمارنده‌ی «همین الان دارم توی این چت auto-reply می‌فرستم» (chat_id -> تعداد
# درحال‌ارسال). قبل از فرستادنِ پاسخ (نه بعدش) پر می‌شه - چرا این مهمه:
# آپدیتِ «پیامِ خروجیِ جدید» که assistant_self_activity_watcher رو صدا می‌زنه،
# توسطِ Telethon همون وسطِ خودِ فراخوانیِ event.reply() (قبل از این‌که
# await برگرده) به‌عنوانِ یه تسکِ جدا پردازش می‌شه؛ یعنی اگه فقط *بعد* از
# reply() یه‌جایی مارکش کنیم (مثلاً با آیدیِ پیام)، ممکنه اون تسکِ دیگه زودتر
# از این‌که برسیم به خطِ مارک‌کردن اجرا بشه - و چون هنوز مارک نشده، به‌غلط
# به‌عنوانِ «خودِ کاربر همین الان پیام فرستاد» حساب بشه و بلافاصله منشی رو
# خاموش کنه (دقیقاً همون باگی که باعث می‌شد منشی موقعِ آفلاین‌بودن، همون اول
# یه پاسخ بده و بعد خودش رو خاموش کنه). با شمارنده‌ی بر پایه‌ی chat_id (نه
# آیدیِ پیام) و افزایشِ *قبل* از await، این پنجره‌ی رقابتی کاملاً بسته می‌شه.
_auto_reply_in_flight: dict[int, int] = {}

# حافظه‌ی مکالمه‌ایِ منشی (فقط برای حالتِ هوش‌مصنوعی): به ازای هر
# (chat_id, sender_id) یه deque از پیام‌های اخیر (کاربر+منشی) نگه می‌داریم
# و موقعِ ساختنِ پرامپت، قبل از پیامِ جدید به AI می‌دیمش - تا مدل بتونه به
# چیزی که قبلاً توی همون مکالمه گفته شده ارجاع بده. drop-in-place: فقط
# در حافظه‌ی پروسه‌ست (نه دیتابیس)، با ری‌استارت پاک می‌شه، و با
# ASSISTANT_HISTORY_LIMIT محدود می‌شه که خودش رشدِ بی‌نهایتِ حافظه/تعدادِ
# توکنِ ارسالی به AI رو کنترل می‌کنه.
_conv_history: dict[tuple[int, int], deque] = {}


def _history_key(chat_id: int, sender_id: int) -> tuple[int, int]:
    return (chat_id, sender_id)


def _get_history_messages(key: tuple[int, int]) -> list[dict]:
    if config.ASSISTANT_HISTORY_LIMIT <= 0:
        return []
    return list(_conv_history.get(key, ()))


def _remember_exchange(key: tuple[int, int], user_text: str, assistant_text: str) -> None:
    limit = config.ASSISTANT_HISTORY_LIMIT
    if limit <= 0:
        return
    dq = _conv_history.get(key)
    if dq is None:
        dq = deque(maxlen=limit)
        _conv_history[key] = dq
    elif dq.maxlen != limit:
        # اگه ASSISTANT_HISTORY_LIMIT توی ران‌تایم عوض بشه (کمتر رایج، ولی
        # برای سازگاری) یه deque جدید با maxlenِ به‌روز می‌سازیم.
        dq = deque(dq, maxlen=limit)
        _conv_history[key] = dq
    dq.append({"role": "user", "content": user_text})
    dq.append({"role": "assistant", "content": assistant_text})


def _clear_all_history() -> int:
    count = len(_conv_history)
    _conv_history.clear()
    return count


_ASSISTANT_MODE_FA = {
    "auto": "خودکار (همه‌جا)",
    "mention": "فقط با منشن/ریپلای",
    "pm": "فقط پیوی",
    "groups": "فقط گروه‌ها",
}

# ورودیِ کاربر برای «حالت پاسخ» -> کلید داخلیِ همیشگی (auto/mention/pm/groups).
# هم نسخه‌ی فارسی و هم انگلیسیِ قدیمی رو قبول می‌کنه.
_ASSISTANT_MODE_ALIASES = {
    "خودکار": "auto", "auto": "auto",
    "منشن": "mention", "mention": "mention",
    "پیوی": "pm", "pm": "pm",
    "گروه‌ها": "groups", "گروهها": "groups", "groups": "groups",
}


# ---------------------------------------------------------- زمان‌بندی ---
# پنجره‌ها با دقیقه‌ی «از نیمه‌شب» (۰ تا ۱۴۳۹) ذخیره/محاسبه می‌شن، نه
# datetime.time یا timezone واقعی - چون تنها چیزی که لازم داریم مقایسه‌ی
# «الان کجای شبانه‌روزم» با یه بازه‌ست، و این کار با عددهای ساده هم دقیق‌تره
# هم از دردسرِ DST/timezone-aware در امان می‌مونه. زمانِ محلی هم دقیقاً با
# همون الگویی که scheduler.py/daily_digest.py استفاده می‌کنن حساب می‌شه
# (config.TIMEZONE_OFFSET، پیش‌فرض تهران) - نه چیزِ جدیدی، فقط همون قرارداد.
_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _local_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)


def _minute_of_day(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def _parse_clock(raw: str) -> int | None:
    """ورودیِ «HH:MM» رو به دقیقه‌ی از نیمه‌شب تبدیل می‌کنه؛ نامعتبر بود -> None."""
    m = _CLOCK_RE.match(raw.strip())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh * 60 + mm


def _format_clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _window_contains(start_minute: int, end_minute: int, minute: int) -> bool:
    """
    آیا `minute` (دقیقه‌ی از نیمه‌شب) داخلِ بازه‌ی [start_minute, end_minute]
    هست؟ هر دو سرِ بازه inclusive-ان. اگه end_minute از start_minute کمتر
    باشه یعنی بازه از نیمه‌شب رد می‌شه (مثلاً ۲۳:۰۰ تا ۰۸:۰۰ -> start=1380,
    end=480؛ یعنی از ۲۳:۰۰ شب تا ۰۸:۰۰ صبحِ روزِ بعد).
    """
    if start_minute <= end_minute:
        return start_minute <= minute <= end_minute
    return minute >= start_minute or minute <= end_minute


def _active_schedule_window(minute: int) -> dict | None:
    """اولین پنجره‌ای که الان توش هستیم (اگه لایه‌ی زمان‌بندی فعال باشه)، وگرنه None."""
    if not assistant_state["schedule_enabled"]:
        return None
    for window in assistant_state["schedule_windows"]:
        if _window_contains(window["start_minute"], window["end_minute"], minute):
            return window
    return None


def _current_signal_reason() -> tuple[str, dict | None]:
    """
    فقط برای تصمیم‌گیری/نمایش - خودش چیزی رو تغییر نمی‌ده. اگه الان داخلِ یه
    پنجره‌ی زمان‌بندی‌شده‌ایم ("schedule", window)، وگرنه ("activity", None)
    یعنی تصمیم بر اساسِ همون تایمرِ سکوت/فعالیتِ قبلیه.
    """
    window = _active_schedule_window(_minute_of_day(_local_now()))
    if window is not None:
        return "schedule", window
    return "activity", None


def _assistant_status_text():
    status = "روشن ✅" if assistant_state["enabled"] else "خاموش ❌"
    mode_fa = _ASSISTANT_MODE_FA.get(assistant_state["mode"], assistant_state["mode"])
    if assistant_state["auto_detect"]:
        kind, window = _current_signal_reason()
        if kind == "schedule":
            reason_text = (
                f"الان به‌خاطرِ بازه‌ی زمان‌بندیِ «{window['label'] or 'بدون‌برچسب'}» "
                f"({_format_clock(window['start_minute'])}–{_format_clock(window['end_minute'])}) روشنه"
            )
        else:
            reason_text = (
                f"بر اساسِ آخرین باری که از هر دستگاهی برات پیامِ واقعی فرستادی؛ "
                f"بعدِ {config.ASSISTANT_ONLINE_THRESHOLD} ثانیه سکوت، خودش روشن می‌شه"
            )
        control_line = f"خودکار ({reason_text})"
        footer = (
            f"با `{PREFIX}منشی روشن` یا `{PREFIX}منشی خاموش` می‌تونی دستی قفلش کنی "
            "(از اون به بعد حتی اگه آنلاین/آفلاین بشی یا داخلِ بازه‌ی زمان‌بندی باشی، تشخیص خودکار دیگه دست بهش نمی‌زنه)."
        )
    else:
        control_line = "دستی 🔒 (قفل‌شده - نه فعالیت نه زمان‌بندی روش تاثیری نداره)"
        footer = f"برای برگردوندن به تشخیص خودکار: `{PREFIX}منشی خودکار`"

    windows = assistant_state["schedule_windows"]
    if not windows:
        schedule_summary = "تعریف نشده"
    else:
        layer = "فعال ✅" if assistant_state["schedule_enabled"] else "غیرفعال ❌ (موقتاً خاموش)"
        schedule_summary = f"{len(windows)} بازه، {layer}"

    return (
        "🤖 **منشی چت**\n\n"
        f"• وضعیت: {status}\n"
        f"• کنترل: {control_line}\n"
        f"• حالت پاسخ: {mode_fa}\n"
        f"• تأخیر پاسخ: {assistant_state['delay']} ثانیه\n"
        f"• منبعِ پاسخ: {'هوش مصنوعی 🤖' if assistant_state['ai_mode'] else 'متنِ ثابت'}\n"
        f"• محدودیتِ پاسخ: "
        f"{'بدون محدودیت - به همه‌ی پیام‌ها جواب می‌ده' if assistant_state['ai_mode'] else 'فقط یک‌بار به هر نفر در هر نشست'}\n"
        f"• حافظه‌ی مکالمه: "
        f"{f'تا {config.ASSISTANT_HISTORY_LIMIT} پیامِ آخرِ هر مکالمه ({len(_conv_history)} مکالمه فعال)' if config.ASSISTANT_HISTORY_LIMIT > 0 else 'خاموش'}\n"
        f"• متن ثابت (fallback): {assistant_state['text'] or '(تنظیم نشده)'}\n"
        f"• زمان‌بندی: {schedule_summary} (جزئیات: `{PREFIX}منشی زمان‌بندی`)\n"
        f"• چت‌های مستثنی: {len(assistant_state['exclude'])}\n"
        f"• چت‌های همیشه‌فعال: {len(assistant_state['include'])}\n\n"
        f"{footer}"
    )


def _schedule_status_text() -> str:
    windows = assistant_state["schedule_windows"]
    header = "🗓 **زمان‌بندیِ منشیِ خودکار**\n\n"
    layer_state = (
        "فعال ✅" if assistant_state["schedule_enabled"]
        else "غیرفعال ❌ (بازه‌ها حذف نشدن، فقط موقتاً بی‌اثرن)"
    )
    state_line = f"وضعیتِ لایه: {layer_state}\n\n"

    if not windows:
        body = (
            "هیچ بازه‌ای تعریف نشده - یعنی منشیِ خودکار فقط بر اساسِ فعالیتِ اخیرت تصمیم می‌گیره.\n\n"
            f"افزودن: `{PREFIX}منشی زمان‌بندی افزودن 23:00 08:00 خواب`\n"
            "(یعنی از ۲۳:۰۰ تا ۰۸:۰۰، صرف‌نظر از فعالیتِ اخیرت، منشی روشن می‌مونه)"
        )
        return header + state_line + body

    now_minute = _minute_of_day(_local_now())
    lines = []
    for i, w in enumerate(windows, start=1):
        active = assistant_state["schedule_enabled"] and _window_contains(
            w["start_minute"], w["end_minute"], now_minute
        )
        mark = " ← الان فعال" if active else ""
        label = w["label"] or "بدون‌برچسب"
        lines.append(f"{i}. {label}: {_format_clock(w['start_minute'])}–{_format_clock(w['end_minute'])}{mark}")

    footer = (
        f"\n\nافزودنِ بازه‌ی دیگه: `{PREFIX}منشی زمان‌بندی افزودن HH:MM HH:MM [برچسب]`\n"
        f"حذفِ یکی: `{PREFIX}منشی زمان‌بندی حذف <شماره>`\n"
        f"پاک‌کردنِ همه: `{PREFIX}منشی زمان‌بندی پاک`\n"
        f"روشن/خاموشِ کلِ این لایه: `{PREFIX}منشی زمان‌بندی روشن` / `{PREFIX}منشی زمان‌بندی خاموش`"
    )
    return header + state_line + "\n".join(lines) + footer


def _assistant_should_respond(event):
    if event.is_channel and not event.is_group:
        return False  # کانال‌های برادکست رو نادیده بگیر
    chat_id = event.chat_id
    if chat_id in assistant_state["exclude"]:
        return False
    if chat_id in assistant_state["include"]:
        return True
    mode = assistant_state["mode"]
    if mode == "auto":
        return True
    if mode == "pm":
        return event.is_private
    if mode == "groups":
        return event.is_group
    if mode == "mention":
        if event.is_private:
            return True
        return bool(getattr(event.message, "mentioned", False))
    return False


@client.on(events.NewMessage(outgoing=True, pattern=pat(["منشی", "assistant"])))
async def assistant_handler(event):
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not sub or sub in ("وضعیت", "status"):
        return await event.edit(_assistant_status_text())

    if sub in ("روشن", "on"):
        assistant_state["enabled"] = True
        assistant_state["auto_detect"] = False  # قفل دستی - تشخیص خودکار دیگه دست بهش نمی‌زنه
        assistant_state["replied"] = set()
        await save_assistant()
        return await event.edit(_assistant_status_text())

    if sub in ("خاموش", "off"):
        assistant_state["enabled"] = False
        assistant_state["auto_detect"] = False  # قفل دستی - حتی اگه آفلاین بشی خاموش می‌مونه
        await save_assistant()
        return await event.edit(_assistant_status_text())

    if sub in ("خودکار", "auto"):
        assistant_state["auto_detect"] = True
        # به‌جای صبرکردن تا دورِ بعدیِ assistant_status_watcher (تا
        # ASSISTANT_CHECK_INTERVAL ثانیه)، همین الان یه‌بار enabled رو از
        # روی فعالیت/زمان‌بندی بازمحاسبه می‌کنیم (کاملاً محلیه، خطا نمی‌ده).
        _recompute_enabled_from_signals()
        await save_assistant()
        return await event.edit(
            "✅ تشخیص خودکار آنلاین/آفلاین دوباره فعال شد.\n"
            "از این به بعد روشن/خاموش‌بودن منشی خودش بر اساسِ آنلاین/آفلاین‌بودنت و بازه‌های زمان‌بندی‌شده مدیریت می‌شه.\n\n"
            + _assistant_status_text()
        )

    if sub in ("زمانبندی", "زمان‌بندی", "schedule"):
        args = rest.split(maxsplit=1)
        action = args[0].lower() if args else ""
        tail = args[1] if len(args) > 1 else ""

        if not action or action in ("وضعیت", "status", "لیست", "list"):
            return await event.edit(_schedule_status_text())

        if action in ("افزودن", "add"):
            parts2 = tail.split(maxsplit=2)
            if len(parts2) < 2:
                return await event.edit(f"مثال: `{PREFIX}منشی زمان‌بندی افزودن 23:00 08:00 خواب`")
            start = _parse_clock(parts2[0])
            end = _parse_clock(parts2[1])
            if start is None or end is None:
                return await event.edit("⛔ فرمتِ ساعت نامعتبره؛ باید HH:MM باشه (مثلاً 23:00).")
            if start == end:
                return await event.edit("⛔ ساعتِ شروع و پایان نمی‌تونن یکی باشن.")
            if len(assistant_state["schedule_windows"]) >= config.ASSISTANT_SCHEDULE_MAX_WINDOWS:
                return await event.edit(
                    f"⛔ سقفِ تعدادِ بازه‌ها ({config.ASSISTANT_SCHEDULE_MAX_WINDOWS} تا) پره؛ "
                    f"یکی رو حذف کن (`{PREFIX}منشی زمان‌بندی حذف <شماره>`) یا اول پاکشون کن."
                )
            label = parts2[2].strip() if len(parts2) > 2 else ""
            await add_schedule_window(label, start, end)
            if assistant_state["auto_detect"]:
                _recompute_enabled_from_signals()
            span = f"{_format_clock(start)}–{_format_clock(end)}"
            return await event.edit(
                f"✅ بازه‌ی «{label or 'بدون‌برچسب'}» ({span}) اضافه شد.\n\n" + _schedule_status_text()
            )

        if action in ("حذف", "remove", "delete"):
            if not tail.strip().isdigit():
                return await event.edit(
                    f"مثال: `{PREFIX}منشی زمان‌بندی حذف 1` (شماره رو از `{PREFIX}منشی زمان‌بندی` ببین)"
                )
            idx = int(tail.strip())
            windows = assistant_state["schedule_windows"]
            if not (1 <= idx <= len(windows)):
                return await event.edit("⛔ همچین شماره‌ای توی لیست نیست.")
            target = windows[idx - 1]
            await remove_schedule_window(target["id"])
            if assistant_state["auto_detect"]:
                _recompute_enabled_from_signals()
            return await event.edit(
                f"🗑 بازه‌ی «{target['label'] or 'بدون‌برچسب'}» حذف شد.\n\n" + _schedule_status_text()
            )

        if action in ("پاک", "clear"):
            n = await clear_schedule_windows()
            if assistant_state["auto_detect"]:
                _recompute_enabled_from_signals()
            return await event.edit(f"🗑 {n} بازه پاک شد." if n else "لیستِ بازه‌ها از قبل هم خالی بود.")

        if action in ("روشن", "on"):
            assistant_state["schedule_enabled"] = True
            if assistant_state["auto_detect"]:
                _recompute_enabled_from_signals()
            await save_assistant()
            return await event.edit("✅ لایه‌ی زمان‌بندی فعال شد.\n\n" + _schedule_status_text())

        if action in ("خاموش", "off"):
            assistant_state["schedule_enabled"] = False
            if assistant_state["auto_detect"]:
                _recompute_enabled_from_signals()
            await save_assistant()
            return await event.edit("❌ لایه‌ی زمان‌بندی غیرفعال شد (بازه‌ها حذف نشدن، فقط موقتاً بی‌اثرن).")

        return await event.edit(f"دستور نامعتبره. راهنما: `{PREFIX}منشی زمان‌بندی`")

    if sub in ("متن", "text"):
        text = rest
        if not text and event.is_reply:
            reply = await event.get_reply_message()
            text = reply.raw_text or ""
        if not text:
            return await event.edit(f"مثال: `{PREFIX}منشی متن سلام، فعلاً آنلاین نیستم`")
        assistant_state["text"] = text
        await save_assistant()
        return await event.edit("✅ متن پاسخ ذخیره شد")

    if sub in ("تأخیر", "تاخیر", "delay"):
        if not rest.strip().isdigit():
            return await event.edit(f"مثال: `{PREFIX}منشی تأخیر 3`")
        assistant_state["delay"] = max(int(rest.strip()), 0)
        await save_assistant()
        return await event.edit(f"✅ تأخیر روی {assistant_state['delay']} ثانیه تنظیم شد")

    if sub in ("حالت", "mode"):
        m_raw = rest.strip().lower()
        m = _ASSISTANT_MODE_ALIASES.get(m_raw)
        if not m:
            return await event.edit(f"مثال: `{PREFIX}منشی حالت خودکار` (خودکار/منشن/پیوی/گروه‌ها)")
        assistant_state["mode"] = m
        await save_assistant()
        warn = ""
        if m == "auto":
            warn = (
                "\n⚠️ توجه: توی این حالت به همه‌ی پیام‌های هر چتی (حتی بدون تگ/ریپلای) "
                "جواب می‌ده - توی گروه‌های شلوغ ممکنه شبیه اسپم به‌نظر برسه."
            )
        return await event.edit(f"✅ حالت روی `{_ASSISTANT_MODE_FA[m]}` تنظیم شد{warn}")

    if sub in ("هوش‌مصنوعی", "هوشمصنوعی", "ai"):
        opt = rest.strip().lower()
        if opt in ("روشن", "on"):
            assistant_state["ai_mode"] = True
            await save_assistant()
            return await event.edit(
                "✅ پاسخِ خودکارِ منشی از این به بعد به‌جای متنِ ثابت، با هوش مصنوعی تولید می‌شه.\n"
                "⚠️ توی این حالت به **همه‌ی** پیام‌ها جواب می‌ده (نه فقط یک‌بار به هر نفر) - "
                "توی چت‌های شلوغ ممکنه هزینه/تعدادِ درخواستِ زیادی به سرویسِ AI بزنه.\n"
                "⚠️ نیازمندِ `AI_API_KEY` ست‌شده‌ست؛ اگه ست نباشه یا خطا بده، خودکار به متنِ ثابتِ فعلی fallback می‌کنه.\n"
                f"🧠 هر مکالمه تا {config.ASSISTANT_HISTORY_LIMIT} پیامِ آخرش رو به‌عنوانِ حافظه به مدل می‌ده "
                "تا جواب‌ها پیوسته باشن (با `ASSISTANT_HISTORY_LIMIT` قابلِ تنظیمه؛ برای پاک‌کردنش: "
                f"`{PREFIX}منشی حافظه پاک`)."
            )
        if opt in ("خاموش", "off"):
            assistant_state["ai_mode"] = False
            await save_assistant()
            return await event.edit("❌ پاسخِ منشی دوباره فقط از متنِ ثابت استفاده می‌کنه (یک‌بار به هر نفر)")
        status = "روشن ✅" if assistant_state["ai_mode"] else "خاموش ❌"
        return await event.edit(
            f"🤖 وضعیتِ پاسخِ هوش‌مصنوعیِ منشی: {status}\n\n"
            f"`{PREFIX}منشی هوش‌مصنوعی روشن` / `{PREFIX}منشی هوش‌مصنوعی خاموش`\n"
            "توی این حالت به همه‌ی پیام‌ها جواب می‌ده (نه فقط یک‌بار به هر نفر).\n"
            "برای سوال/خلاصه‌سازیِ دستی (جدا از منشی) هم می‌تونی از "
            f"`{PREFIX}پرسش` و `{PREFIX}خلاصه` استفاده کنی."
        )

    if sub in ("مستثنی", "exclude"):
        assistant_state["exclude"].add(event.chat_id)
        assistant_state["include"].discard(event.chat_id)
        await save_assistant()
        return await event.edit("🚫 این چت مستثنی شد (منشی اینجا پاسخ نمی‌ده)")

    if sub in ("شامل", "include"):
        assistant_state["include"].add(event.chat_id)
        assistant_state["exclude"].discard(event.chat_id)
        await save_assistant()
        return await event.edit("✅ این چت به لیست همیشه‌فعال اضافه شد")

    if sub in ("پاک", "clear"):
        assistant_state["include"].clear()
        assistant_state["exclude"].clear()
        await save_assistant()
        return await event.edit("🗑 لیست مستثنی/شامل پاک شد")

    if sub in ("حافظه", "history"):
        if rest.strip().lower() in ("پاک", "clear"):
            n = _clear_all_history()
            return await event.edit(f"🗑 حافظه‌ی مکالمه‌ی {n} چت پاک شد")
        if config.ASSISTANT_HISTORY_LIMIT <= 0:
            return await event.edit(
                "🧠 حافظه‌ی مکالمه‌ی منشی خاموشه (`ASSISTANT_HISTORY_LIMIT=0`)."
            )
        return await event.edit(
            f"🧠 حافظه‌ی مکالمه: تا {config.ASSISTANT_HISTORY_LIMIT} پیامِ آخرِ هر مکالمه "
            f"({len(_conv_history)} مکالمه فعال)\n"
            f"برای پاک‌کردن: `{PREFIX}منشی حافظه پاک`"
        )

    await event.edit(f"دستور نامعتبره. برای وضعیت کامل: `{PREFIX}منشی`")


_ASSISTANT_AI_SYSTEM = (
    "شما دستیارِ شخصیِ صاحبِ این اکانتِ تلگرام هستید و دارید وقتی صاحبِ اکانت "
    "آفلاین/مشغوله به‌جاش به پیام‌ها پاسخِ کوتاه و مؤدبانه می‌دید. پاسخ رو خیلی "
    "کوتاه (حداکثر ۲-۳ جمله) و به همون زبانِ پیامِ ورودی بده، بدون مقدمه‌چینی."
)


@client.on(events.NewMessage(incoming=True))
async def assistant_autoreply(event):
    if not assistant_state["enabled"]:
        return
    if not assistant_state["ai_mode"] and not assistant_state["text"]:
        return
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return
    if not _assistant_should_respond(event):
        return

    key = (event.chat_id, sender_id)
    if not assistant_state["ai_mode"]:
        # حالتِ متنِ ثابت: فقط یک‌بار به هر نفر توی هر نشست، تا اسپم نشه.
        if key in assistant_state["replied"]:
            return
        assistant_state["replied"].add(key)
    # حالتِ هوش‌مصنوعی: هیچ محدودیتی نداره - به تک‌تکِ پیام‌ها جواب می‌ده،
    # چون هر جواب بر اساسِ همون پیامِ مشخص تولید می‌شه (نه یه متنِ تکراری).

    try:
        delay = assistant_state["delay"]
        if delay > 0:
            async with client.action(event.chat_id, "typing"):
                await asyncio.sleep(delay)

        reply_text = assistant_state["text"]
        used_ai = False
        if assistant_state["ai_mode"]:
            try:
                incoming_text = event.raw_text or ""
                if not incoming_text and audio.is_audio_message(event.message):
                    # پیامِ ورودی صوتیه؛ قبل از دادن به AI خودمون رونویسی می‌کنیم.
                    try:
                        incoming_text = await audio.transcribe_message(event.message)
                    except (ai.AIDisabledError, ai.AIRequestError):
                        incoming_text = ""
                incoming_text = incoming_text or "(بدون متن)"
                hist_key = _history_key(event.chat_id, sender_id)
                messages = [
                    {"role": "system", "content": _ASSISTANT_AI_SYSTEM},
                    *_get_history_messages(hist_key),
                    {"role": "user", "content": incoming_text},
                ]
                ai_answer = await ai.ask_ai(messages, max_tokens=300)
                if ai_answer:
                    reply_text = ai_answer
                    used_ai = True
                    _remember_exchange(hist_key, incoming_text, ai_answer)
            except (ai.AIDisabledError, ai.AIRequestError):
                _record_error()
                logger.exception("خطا در پاسخِ هوش‌مصنوعیِ منشی - fallback به متنِ ثابت")

        if not reply_text:
            return  # نه متنِ ثابتی هست، نه AI جواب داد

        # فقط وقتی پاسخ واقعاً از AI اومده باشه (نه متنِ ثابتِ خودِ owner)
        # برچسبِ مخفیِ «نوشته‌شده با AI» بهش اضافه می‌شه.
        entities = None
        if used_ai:
            reply_text, entities = ai.tag_ai_text(reply_text)

        # قبل از await (نه بعدش) مارک می‌کنیم - نگاهِ بالا به تعریفِ
        # _auto_reply_in_flight برای توضیحِ کاملِ چرایی.
        _auto_reply_in_flight[event.chat_id] = _auto_reply_in_flight.get(event.chat_id, 0) + 1
        try:
            await event.reply(reply_text, formatting_entities=entities)
        finally:
            remaining = _auto_reply_in_flight.get(event.chat_id, 1) - 1
            if remaining <= 0:
                _auto_reply_in_flight.pop(event.chat_id, None)
            else:
                _auto_reply_in_flight[event.chat_id] = remaining
    except Exception:
        _record_error()
        logger.exception("خطا در پاسخ خودکار منشی")


@client.on(events.NewMessage(outgoing=True))
async def assistant_self_activity_watcher(event):
    """
    هر پیامِ خروجیِ واقعی (چه از همین اسکریپت، چه از گوشی/دسکتاپت - چون
    تلگرام پیام‌های خروجیِ خودت رو بینِ همه‌ی سشن‌های اکانت sync می‌کنه و این
    هندلر هم دقیقاً همون آپدیت رو می‌بینه) رو به‌عنوانِ «الان پشتِ اکانتم» در
    نظر می‌گیره. این تنها منبعِ سیگنالِ فعالیتِ تشخیصِ آنلاین/آفلاینه - نگاهِ
    بالای فایل (کنارِ تعریفِ _last_self_activity) برای این‌که چرا این روش
    جایگزینِ روشِ قبلی (پرسیدنِ لیستِ سشن‌ها از تلگرام) شد.
    """
    global _last_self_activity

    if _auto_reply_in_flight.get(event.chat_id, 0) > 0:
        # این خودِ منشیه که داره توی همین چت auto-reply می‌ده، نه کاربر - نادیده بگیر.
        return

    raw = (event.raw_text or "").strip()
    if raw.startswith(PREFIX):
        # این یه دستورِ کنترلیِ خودِ سلف‌بات (مثلِ `.منشی خودکار` یا حتی صرفِ
        # چک‌کردنِ وضعیت با `.منشی`) - نه یه پیامِ واقعی به یه نفر. اگه این‌ها
        # رو هم «فعالیت» حساب می‌کردیم، هر بار که برای عوض‌کردنِ حالت یا چک‌کردنِ
        # وضعیت تایپ می‌کردید، تایمرِ سکوت (ASSISTANT_ONLINE_THRESHOLD)
        # ریست می‌شد - و دقیقاً همین باعث می‌شد بعدِ برگردوندن به حالتِ خودکار،
        # منشی تا ابد روشن نشه (چون هر چک‌کردنِ وضعیت، خودش دوباره تایمر رو
        # ریست می‌کرد). دستورهای کنترلی نباید نشونه‌ی «الان دارم چت می‌کنم» باشن.
        return

    _last_self_activity = datetime.now(timezone.utc)
    if assistant_state["auto_detect"]:
        # قبلاً اینجا مستقیم `assistant_state["enabled"] = False` می‌شد (چون
        # فرستادنِ یه پیامِ واقعی یعنی «آنلاینم»). ولی این فرض دیگه همیشه
        # درست نیست: اگه الان داخلِ یه بازه‌ی زمان‌بندی‌شده باشیم (مثلاً
        # ساعتِ ۲ نصفِ‌شب یه پیام بفرستی درحالی‌که بازه‌ی «خواب» تعریف کردی)،
        # منشی باید همچنان روشن بمونه. به‌جای یه شرطِ جداگانه، از همون تابعِ
        # مشترکِ تصمیم‌گیری (_recompute_enabled_from_signals) استفاده می‌کنیم
        # تا این استثنا فقط یه‌جا (نه اینجا و هم توی خودِ تابع) پیاده بشه.
        _recompute_enabled_from_signals()


def _recompute_enabled_from_signals() -> None:
    """
    فقط وقتی auto_detect=True صدا زده می‌شه (نه موقعِ قفلِ دستی). دو سیگنالِ
    کاملاً محلی رو ترکیب می‌کنه - نگاهِ کاملِ توضیح توی docstringِ بالای فایل:

      ۱) اگه الان داخلِ یه بازه‌ی زمان‌بندی‌شده باشیم -> همیشه روشن، صرف‌نظر
         از فعالیتِ اخیر.
      ۲) وگرنه -> بر اساسِ همون تایمرِ سکوت/فعالیتِ قبلی تصمیم می‌گیریم.

    هیچ درخواستی به تلگرام نمی‌زنه (نه برای زمان‌بندی، نه برای فعالیت)، پس
    هیچ‌وقت نمی‌تونه خطا یا FloodWait بده - همون ویژگیِ حیاتی‌ای که باعثِ
    جایگزینیِ روشِ قبلیِ «پرسیدنِ سشن‌ها از تلگرام» شده بود، اینجا هم حفظ می‌شه.
    """
    kind, _window = _current_signal_reason()
    if kind == "schedule":
        new_enabled = True
    else:
        seconds_since_self = (datetime.now(timezone.utc) - _last_self_activity).total_seconds()
        online = seconds_since_self < config.ASSISTANT_ONLINE_THRESHOLD
        new_enabled = not online

    if new_enabled != assistant_state["enabled"]:
        if new_enabled:
            assistant_state["replied"] = set()  # نشست تازه = دوباره به همه جواب بده
        assistant_state["enabled"] = new_enabled


async def assistant_status_watcher():
    """
    هر چند ثانیه یک‌بار (ASSISTANT_CHECK_INTERVAL) وضعیتِ enabled رو بر
    اساسِ زمان‌بندی + آخرین «فعالیتِ خودم» (که assistant_self_activity_watcher
    بالا، بدونِ تاخیر و برای هر دستگاهی ثبتش می‌کنه) بازبینی می‌کنه - نگاهِ
    _recompute_enabled_from_signals برای منطقِ کامل.

    نسخه‌ی قبلیِ این تابع هر بار با GetAuthorizationsRequest از تلگرام
    لیستِ سشن‌های فعال رو می‌گرفت - که مشکل داشت: این متد برای پرسوجوی
    مکرر (هر ۳۰ ثانیه، برای همیشه) طراحی نشده و دیر یا زود با FloodWaitError
    ریت‌لیمیت می‌شد؛ و چون اون خطا هر بار توسطِ همین حلقه catch و نادیده
    گرفته می‌شد، enabled دیگه هیچ‌وقت دوباره محاسبه نمی‌شد و منشی برای همیشه
    روی حالتِ خاموش گیر می‌کرد - دقیقاً همون باگی که این نسخه حلش می‌کنه.
    الان هیچ درخواستی به تلگرام زده نمی‌شه؛ تشخیص فقط بر اساسِ سیگنال‌های
    کاملاً محلیِ بالا انجام می‌شه، که نه ریت‌لیمیت می‌شن و نه اصلاً می‌تونن
    خطا بدن.

    اگه با `.منشی روشن` یا `.منشی خاموش` دستی قفلش کرده باشی (auto_detect
    خاموش)، این تابع اصلاً دست به enabled نمی‌زنه - حتی اگه آفلاین بشی یا
    داخلِ یه بازه‌ی زمان‌بندی‌شده باشی.
    """
    from .. import health
    while True:
        if assistant_state["auto_detect"]:
            _recompute_enabled_from_signals()
        health.update_worker_status("assistant", "ok")
        await asyncio.sleep(config.ASSISTANT_CHECK_INTERVAL)
