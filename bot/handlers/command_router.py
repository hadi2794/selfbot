"""۱۷) روترِ دستوریِ هوشمند: `.هوش <جمله‌ی آزاد>`

به‌جای اینکه کاربر مجبور باشه فرمتِ دقیقِ دستورها رو حفظ کنه (مثلاً
`.یادآوری 14:30 ...`)، این دستور یه جمله‌ی آزاد/محاوره‌ای می‌گیره، با
هسته‌ی مشترکِ bot/ai.py (همون ask_ai که .پرسش/.خلاصه هم ازش استفاده می‌کنن)
سعی می‌کنه intent + پارامترها رو استخراج کنه، و **قبل از اجرا** خلاصه‌ی
تشخیص‌داده‌شده رو نشون می‌ده و منتظرِ تاییدِ صریحِ کاربر (`.هوش تایید`) می‌مونه.
یعنی مدل هیچ‌وقت مستقیماً کاری رو انجام نمی‌ده - فقط پیشنهاد می‌ده و اجرای
واقعی (ثبت توی همون موتورِ scheduler.py که `.یادآوری` هم ازش استفاده می‌کنه)
فقط بعدِ تاییدِ دستیِ کاربر روی اکانتِ خودش انجام می‌شه.

فعلاً فقط intent=«یادآوری» پشتیبانی می‌شه (یعنی محدود به همون کاری که
`.یادآوری` هم می‌کنه: یه پیامِ یادآوری سرِ وقتِ مشخص به Saved Messages
می‌فرسته). برای هر intentِ دیگه یا وقتی مدل مطمئن نیست، فقط یه پیامِ راهنما
می‌ده و پیشنهاد می‌کنه از دستورِ مستقیم استفاده کنه - چیزی خودکار ثبت نمی‌شه.

نیازمندِ همون AI_API_KEY یِ بخشِ هوش مصنوعیه؛ بدونش فقط پیامِ راهنما می‌ده و
بقیه‌ی سلف‌بات مثلِ همیشه عادی کار می‌کنه.
"""
import datetime as dt
import json
import logging
import time

from telethon import events

from .. import ai, runtime
from ..config import PREFIX
from ..runtime import client
from ..storage.scheduler_store import create_job
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from .scheduler import _FULL_RE, _local_now, _to_utc_aware

logger = logging.getLogger("selfbot.handlers.command_router")

# chat_id -> {"text", "run_at_utc", "local_display", "created_at"} — پیشنهادِ
# در انتظارِ تاییدِ همون چت (فقط یکی در آن واحد، دقیقاً مثلِ GUESS_GAMES توی fun.py)
PENDING = {}
_PENDING_TTL_SECONDS = 5 * 60

_ROUTER_SYSTEM_PROMPT = """تو یه روترِ دستوریِ سلف‌بات تلگرام هستی. کاربر یه جمله‌ی
آزاد و محاوره‌ای (فارسی یا انگلیسی) می‌نویسه؛ کارِ تو فقط تشخیصه، نه اجرا.
باید **فقط و فقط** یه شیِ JSON خام برگردونی (بدون توضیح، بدون Markdown،
بدون بک‌تیک، بدون هیچ متنِ اضافه) دقیقاً با این ساختار:

{{"intent": "reminder" یا "unknown", "time": "YYYY-MM-DD HH:MM" یا null, "text": "..." یا null}}

قوانین:
- زمانِ محلیِ الانِ کاربر: {now}
- اگه جمله معنیِ «یه‌چیزی رو یادم بنداز / یادآوری کن / فراموش نکنم / سرِ فلان ساعت» داشت -> "intent":"reminder"
- "time" همیشه باید یه تاریخ+ساعتِ کاملِ **آینده** به‌فرمتِ دقیقِ "YYYY-MM-DD HH:MM" باشه
  (بر اساسِ همون زمانِ الانِ بالا حساب کن؛ اگه فقط ساعت گفته شده و امروز گذشته، یعنی فردا)
- "text" خلاصه‌ی کوتاهِ همون چیزی‌که باید یادش بیفته، به زبانِ خودِ کاربر
- اگه intent نامشخص بود، یا زمان/متن به‌اندازه‌ی کافی روشن نبود -> دقیقاً
  {{"intent": "unknown", "time": null, "text": null}} برگردون
- تو **هیچ‌وقت** واقعاً پیام به کسِ دیگه‌ای نمی‌فرستی و وانمود نمی‌کنی کاری انجام دادی -
  فقط تشخیص می‌دی؛ اجرای واقعی با خودِ سیستمه، بعدِ تاییدِ کاربر."""


def _extract_json(raw: str):
    """
    خروجیِ مدل رو parse می‌کنه. اگه مدل دورِ JSON متنِ اضافه گذاشت (با وجودِ
    system prompt، بعضی مدل‌ها بازم گاهی این کارو می‌کنن)، اولین `{...}`ی که
    توی متن پیدا می‌شه رو جدا می‌کنیم و همونو parse می‌کنیم.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _parse_router_time(raw_time):
    """
    برخلافِ scheduler.parse_time (که چندین فرمتِ ورودیِ کاربر رو قبول می‌کنه)،
    اینجا فقط همون فرمتِ کاملی که توی system prompt از مدل خواستیم
    ("YYYY-MM-DD HH:MM") رو قبول می‌کنیم - چون تفسیرِ زمانِ نسبی/محاوره‌ای
    قبلاً توسطِ خودِ مدل (که «الان» رو داره) انجام شده.
    """
    if not isinstance(raw_time, str) or not raw_time.strip():
        return None
    m = _FULL_RE.match(raw_time.strip())
    if not m:
        return None
    date_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
    try:
        target_local = dt.datetime.strptime(date_part, "%Y-%m-%d").replace(hour=hh, minute=mm)
    except ValueError:
        return None
    if target_local <= _local_now():
        return None
    return _to_utc_aware(target_local), target_local.strftime("%Y-%m-%d %H:%M")


async def _confirm(event, chat_id):
    pending = PENDING.get(chat_id)
    if pending is None:
        return await event.edit(
            f"چیزی برای تایید در انتظار نیست. اول یه‌بار `{PREFIX}هوش <جمله>` رو بفرست."
        )
    if time.monotonic() - pending["created_at"] > _PENDING_TTL_SECONDS:
        PENDING.pop(chat_id, None)
        return await event.edit("⌛ این پیشنهاد منقضی شده - دوباره امتحان کن")

    self_id = runtime.SELF_ID or chat_id
    try:
        job = await create_job(self_id, pending["text"], pending["run_at_utc"], "reminder")
    except Exception as e:
        _record_error()
        return await event.edit(f"❌ خطا در ثبتِ یادآوری: {e}")

    PENDING.pop(chat_id, None)
    await event.edit(
        f"✅ ثبت شد (شناسه `{job.id}`) — سرِ **{pending['local_display']}** یادآوری می‌شه\n"
        f"(برای لغو: `{PREFIX}یادآوری لغو {job.id}`)"
    )


@client.on(events.NewMessage(outgoing=True, pattern=pat(["هوش", "ai_router"])))
async def command_router_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    chat_id = event.chat_id
    sub = arg.split(maxsplit=1)[0].lower() if arg else ""

    if sub in ("تایید", "confirm", "ok"):
        return await _confirm(event, chat_id)

    if sub in ("لغو", "cancel"):
        if PENDING.pop(chat_id, None) is not None:
            return await event.edit("🚫 پیشنهاد لغو شد")
        return await event.edit("چیزی برای لغو در انتظار نیست")

    if not arg:
        return await event.edit(
            f"مثال: `{PREFIX}هوش فردا ساعت ۹ یادم بنداز به علی زنگ بزنم`\n\n"
            "جمله رو تحلیل می‌کنم و قبل از ثبت، خلاصه‌ش رو نشون می‌دم:\n"
            f"• تایید: `{PREFIX}هوش تایید`\n"
            f"• لغو: `{PREFIX}هوش لغو`\n\n"
            "فعلاً فقط تشخیصِ «یادآوری» پشتیبانی می‌شه؛ برای بقیه‌ی قابلیت‌ها مستقیم "
            f"از دستورِ خودشون (مثلاً `{PREFIX}زمان‌بند`) استفاده کن."
        )

    await event.edit("🧠 در حال تشخیصِ دستور...")
    messages = [
        {
            "role": "system",
            "content": _ROUTER_SYSTEM_PROMPT.format(now=_local_now().strftime("%Y-%m-%d %H:%M")),
        },
        {"role": "user", "content": arg},
    ]
    try:
        answer = await ai.ask_ai(messages, max_tokens=200)
    except ai.AIDisabledError:
        return await event.edit(
            "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
            "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن."
        )
    except ai.AIRequestError as e:
        _record_error()
        return await event.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")

    data = _extract_json(answer)
    intent = data.get("intent") if isinstance(data, dict) else None

    if intent != "reminder":
        return await event.edit(
            "🤷 نتونستم این جمله رو با اطمینان به یه دستورِ پشتیبانی‌شده تبدیل کنم.\n"
            f"فعلاً فقط «یادآوری» پشتیبانی می‌شه - می‌تونی مستقیم از `{PREFIX}یادآوری <زمان> <متن>` استفاده کنی."
        )

    parsed = _parse_router_time(data.get("time"))
    text = data.get("text").strip() if isinstance(data.get("text"), str) else ""
    if parsed is None or not text:
        return await event.edit(
            "🤷 زمان یا متنِ یادآوری رو مطمئن تشخیص ندادم - لطفاً واضح‌تر بنویس (مثلاً با ذکرِ "
            f"ساعتِ دقیق)، یا مستقیم از `{PREFIX}یادآوری <زمان> <متن>` استفاده کن."
        )
    run_at_utc, local_display = parsed

    PENDING[chat_id] = {
        "text": text,
        "run_at_utc": run_at_utc,
        "local_display": local_display,
        "created_at": time.monotonic(),
    }
    await event.edit(
        "⏰ **می‌خوای این یادآوری ثبت بشه؟**\n\n"
        f"🕒 زمان: `{local_display}`\n"
        f"📝 متن: {text}\n\n"
        f"تایید: `{PREFIX}هوش تایید`  •  لغو: `{PREFIX}هوش لغو`"
    )
