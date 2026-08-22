"""۱۴) زمان‌بندی و یادآوری: schedule / remind

هر دو دستور از یه موتور مشترک استفاده می‌کنن (جدول scheduled_jobs):
  - `.زمان‌بند <زمان> <متن>`  → متن رو سرِ وقتِ مشخص توی همین چت می‌فرسته
  - `.یادآوری <زمان> <متن>`  → متن رو سرِ وقتِ مشخص به Saved Messages (خودت) می‌فرسته

فرمت‌های «زمان» که پشتیبانی می‌شن:
  - نسبی: عدد + واحد → `10m` `2h` `1d` `45s` یا فارسی `10دقیقه` `2ساعت` `1روز` `45ثانیه`
  - ساعتِ امروز/فردا: `14:30` (اگه گذشته باشه، خودکار می‌ره برای فردا)
  - تاریخ و ساعت کامل: `2026-08-25 14:30`
"""
import asyncio
import datetime as dt
import logging
import re

from telethon import errors, events

from .. import runtime
from ..config import PREFIX, TIMEZONE_OFFSET
from ..runtime import client
from ..storage.scheduler_store import create_job, delete_job, get_job, list_due_jobs, list_jobs
from ..storage.settings_toggles import toggles
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.scheduler")

_REL_UNITS = {
    "s": 1, "sec": 1, "ثانیه": 1,
    "m": 60, "min": 60, "دقیقه": 60,
    "h": 3600, "hour": 3600, "ساعت": 3600,
    "d": 86400, "day": 86400, "روز": 86400,
}
_REL_RE = re.compile(r"^(\d+)\s*(" + "|".join(re.escape(u) for u in _REL_UNITS) + r")$")
_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_FULL_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})$")


def _local_now() -> dt.datetime:
    """همون الگوی clock.py: زمانِ محلی به‌صورت naive datetime."""
    return dt.datetime.utcnow() + dt.timedelta(hours=TIMEZONE_OFFSET)


def _to_utc_aware(local_dt: dt.datetime) -> dt.datetime:
    utc_naive = local_dt - dt.timedelta(hours=TIMEZONE_OFFSET)
    return utc_naive.replace(tzinfo=dt.timezone.utc)


def parse_time(raw: str) -> tuple[dt.datetime, str] | None:
    """
    ورودیِ کاربر رو parse می‌کنه و (run_at_utc, نمایشِ زمانِ محلی) برمی‌گردونه.
    اگه فرمت نامعتبر بود یا زمان توی گذشته بود، None برمی‌گردونه.
    """
    raw = raw.strip()
    now_local = _local_now()

    m = _REL_RE.match(raw)
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        target_local = now_local + dt.timedelta(seconds=amount * _REL_UNITS[unit])
        return _to_utc_aware(target_local), target_local.strftime("%Y-%m-%d %H:%M")

    m = _FULL_RE.match(raw)
    if m:
        date_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
        try:
            target_local = dt.datetime.strptime(date_part, "%Y-%m-%d").replace(hour=hh, minute=mm)
        except ValueError:
            return None
        if target_local <= now_local:
            return None
        return _to_utc_aware(target_local), target_local.strftime("%Y-%m-%d %H:%M")

    m = _CLOCK_RE.match(raw)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        target_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target_local <= now_local:
            target_local += dt.timedelta(days=1)
        return _to_utc_aware(target_local), target_local.strftime("%Y-%m-%d %H:%M")

    return None


_TIME_HELP = (
    "فرمت‌های مجاز:\n"
    "• نسبی: `10m` `2h` `1d` `45s` یا `10 دقیقه` `2 ساعت` `1 روز` (با فاصله یا چسبیده، هر دو کار می‌کنه)\n"
    "• ساعتِ امروز/فردا: `14:30`\n"
    "• تاریخ کامل: `2026-08-25 14:30`"
)

_UNIT_TOKENS = set(_REL_UNITS.keys())


def _extract_time_and_text(arg: str) -> tuple[str, str]:
    """
    زمان و متن رو از آرگومان جدا می‌کنه. علاوه بر فرمتِ چسبیده (`10دقیقه`)،
    فرمتِ با فاصله هم پشتیبانی می‌شه (`10 دقیقه`) چون برای فارسی‌زبون‌ها
    نوشتنش با فاصله طبیعی‌تره؛ قبلاً فقط حالتِ چسبیده کار می‌کرد و باعث
    می‌شد `.زمان‌بند 10 دقیقه سلام` با خطای «زمانِ نامعتبر» رد بشه.
    """
    tokens = arg.split()
    if len(tokens) >= 2 and tokens[0].isdigit() and tokens[1] in _UNIT_TOKENS:
        time_raw = tokens[0] + tokens[1]
        text = " ".join(tokens[2:])
        return time_raw, text
    parts = arg.split(maxsplit=1)
    time_raw = parts[0] if parts else ""
    text = parts[1] if len(parts) > 1 else ""
    return time_raw, text


async def _add_job(event, kind: str, arg: str, dest_chat_id: int, label: str):
    time_raw, text = _extract_time_and_text((arg or "").strip())
    if not time_raw or (not text and not event.is_reply):
        return await event.edit(f"مثال: `{PREFIX}{label} 10m متن پیام`\n\n{_TIME_HELP}")

    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text or ""
    if not text:
        return await event.edit(f"مثال: `{PREFIX}{label} 10m متن پیام` (یا ریپلای روی یه پیام)")

    parsed = parse_time(time_raw)
    if parsed is None:
        return await event.edit(f"⏰ زمانِ نامعتبر یا گذشته.\n\n{_TIME_HELP}")
    run_at_utc, local_display = parsed

    job = await create_job(dest_chat_id, text, run_at_utc, kind)
    await event.edit(f"✅ ثبت شد (شناسه `{job.id}`) — سرِ **{local_display}** ارسال می‌شه")


def _format_list(jobs, empty_msg: str, title: str) -> str:
    if not jobs:
        return empty_msg
    lines = [title, ""]
    for j in jobs:
        # درایور معمولاً aware (UTC) برمی‌گردونه؛ اگه به هر دلیلی naive بود هم
        # چون خودمون همیشه UTC ذخیره می‌کنیم، مستقیم به‌عنوان UTC درنظرش می‌گیریم.
        run_at_utc = j.run_at if j.run_at.tzinfo else j.run_at.replace(tzinfo=dt.timezone.utc)
        local_dt = run_at_utc.astimezone(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(
            hours=TIMEZONE_OFFSET
        )
        preview = j.text if len(j.text) <= 40 else j.text[:40] + "…"
        lines.append(f"• `{j.id}` — {local_dt.strftime('%Y-%m-%d %H:%M')} — {preview}")
    return "\n".join(lines)


# --------------------------------------------------------- زمان‌بند ---
@client.on(events.NewMessage(outgoing=True, pattern=pat(["زمان‌بند", "schedule"])))
async def schedule_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    sub = arg.split(maxsplit=1)[0].lower() if arg else ""

    if sub in ("لیست", "list"):
        jobs = [j for j in await list_jobs("schedule") if j.chat_id == event.chat_id]
        return await event.edit(
            _format_list(jobs, "توی این چت هیچ پیامِ زمان‌بندی‌شده‌ای نیست", "⏰ **پیام‌های زمان‌بندی‌شده (این چت)**")
        )

    if sub in ("لغو", "cancel"):
        rest = arg.split(maxsplit=1)
        job_id = rest[1].strip() if len(rest) > 1 else ""
        if not job_id.isdigit():
            return await event.edit(f"مثال: `{PREFIX}زمان‌بند لغو 3`")
        job = await get_job_checked(int(job_id), "schedule")
        if job is None or job.chat_id != event.chat_id:
            return await event.edit("همچین شناسه‌ای توی این چت پیدا نشد")
        await delete_job(job.id)
        return await event.edit(f"🗑 زمان‌بندیِ `{job.id}` لغو شد")

    await _add_job(event, "schedule", arg, event.chat_id, "زمان‌بند")


# ----------------------------------------------------------- یادآوری ---
@client.on(events.NewMessage(outgoing=True, pattern=pat(["یادآوری", "remind"])))
async def reminder_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    sub = arg.split(maxsplit=1)[0].lower() if arg else ""
    self_id = runtime.SELF_ID or event.chat_id  # احتیاطی، معمولاً موقع اجرا SELF_ID پر شده

    if sub in ("لیست", "list"):
        jobs = await list_jobs("reminder")
        return await event.edit(
            _format_list(jobs, "هیچ یادآوریِ فعالی نیست", "🔔 **یادآوری‌های فعال**")
        )

    if sub in ("لغو", "cancel"):
        rest = arg.split(maxsplit=1)
        job_id = rest[1].strip() if len(rest) > 1 else ""
        if not job_id.isdigit():
            return await event.edit(f"مثال: `{PREFIX}یادآوری لغو 3`")
        job = await get_job_checked(int(job_id), "reminder")
        if job is None:
            return await event.edit("همچین یادآوری‌ای پیدا نشد")
        await delete_job(job.id)
        return await event.edit(f"🗑 یادآوریِ `{job.id}` لغو شد")

    await _add_job(event, "reminder", arg, self_id, "یادآوری")


async def get_job_checked(job_id: int, kind: str):
    job = await get_job(job_id)
    if job is None or job.kind != kind:
        return None
    return job


# ------------------------------------------------------ تسکِ پس‌زمینه ---
async def scheduler_worker():
    """هر ۱۵ ثانیه چک می‌کنه ببینه کاری سر رسیده یا نه؛ اگه رسیده بفرسته و حذفش کنه."""
    from .. import health
    while True:
        await asyncio.sleep(15)
        health.update_worker_status("scheduler", "ok")
        if not toggles["scheduler_enabled"]:
            continue
        now_utc = dt.datetime.now(dt.timezone.utc)
        try:
            due = await list_due_jobs(now_utc)
        except Exception as e:
            logger.exception("خطا در خوندنِ کارهای زمان‌بندی‌شده")
            _record_error()
            health.update_worker_status("scheduler", "error", str(e))
            continue

        for job in due:
            text = job.text if job.kind == "schedule" else f"🔔 **یادآوری**\n\n{job.text}"
            try:
                await client.send_message(job.chat_id, text)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                continue  # این دور رد می‌شه، دورِ بعدی دوباره تلاش می‌شه (چون هنوز حذف نشده)
            except Exception:
                logger.exception("خطا در ارسال کارِ زمان‌بندی‌شده‌ی %s", job.id)
                _record_error()
            # چه موفق چه ناموفق (به‌جز FloodWait) حذف می‌شه تا لوپِ بی‌نهایت روی
            # خطاهای دائمی (مثل چت پاک‌شده) پیش نیاد.
            try:
                await delete_job(job.id)
            except Exception:
                logger.exception("خطا در حذفِ کارِ زمان‌بندی‌شده‌ی %s", job.id)
                _record_error()
