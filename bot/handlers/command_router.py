"""۱۷) روترِ دستوریِ هوشمند: `.هوش <جمله‌ی آزاد>`

به‌جای اینکه کاربر مجبور باشه فرمتِ دقیقِ دستورها رو حفظ کنه، این دستور یه
جمله‌ی آزاد/محاوره‌ای می‌گیره، با هسته‌ی مشترکِ bot/ai.py (همون ask_ai که
`.پرسش`/`.خلاصه` هم ازش استفاده می‌کنن) سعی می‌کنه intent + پارامترها رو
استخراج کنه، و **قبل از اجرا** خلاصه‌ی تشخیص‌داده‌شده رو نشون می‌ده و منتظرِ
تاییدِ صریحِ کاربر (`.هوش تایید`) می‌مونه. یعنی مدل هیچ‌وقت مستقیماً کاری رو
انجام نمی‌ده - فقط پیشنهاد می‌ده، و اجرای واقعی همیشه از همون کدِ handlerِ
اصلیِ همون بخش (یا هسته‌ی مشترکی که ازش استخراج شده) استفاده می‌کنه.

برخلافِ نسخه‌ی قبلی که فقط «یادآوری» رو پشتیبانی می‌کرد، این نسخه یه
رجیستریِ قابل‌توسعه از intentهاست (`ACTIONS`) که چند بخشِ مختلفِ ربات رو
پوشش می‌ده:

  • زمان‌بندی   → reminder, schedule_message
  • یادداشت‌ها  → note_add, note_get, note_delete, note_list
  • ابزار       → calc, translate, currency, genpass
  • پروفایل     → setbio, setname
  • فونت        → font_apply
  • سرگرمی      → coin_flip, random_number, choose, magic8ball
  • منشی        → assistant_toggle (روشن/خاموش/خودکار)
  • خلاصه‌ی روزانه → daily_digest_toggle (روشن/خاموش/اجرای فوری)
  • آمار        → stats_view (فقط خواندنی)

عمداً چیزهایی مثلِ مدیریتِ گروه (بن/کیک/ارتقا)، عملیاتِ فایلی (عکسِ پروفایل،
QR، صوت)، و اتوماسیون‌های ماندگار (autopost/groupguard) توی این رجیستری
نیستن: یا روی افرادِ دیگه اثر می‌ذارن (و پارس‌کردنِ اشتباهِ یه جمله می‌تونه
عواقبِ جبران‌ناپذیر داشته باشه)، یا ورودی‌شون فایله نه متن. اونا همیشه از
طریقِ دستورِ مستقیمِ خودشون در دسترسن.

برای اضافه‌کردنِ یه intentِ جدید کافیه یه ورودیِ دیگه به دیکشنریِ ACTIONS
پایینِ همین فایل اضافه کنی: یه build() که پارامترهای مدل رو validate/normalize
می‌کنه و متنِ پیش‌نمایش می‌سازه، و یه execute() که کارِ واقعی رو (با استفاده
از همون storage/هسته‌ای که handlerِ اصلیِ اون بخش استفاده می‌کنه) انجام می‌ده.
"""
import datetime as dt
import json
import logging
import random
import time

from telethon import events, functions

from .. import ai, runtime
from ..calc import safe_eval
from ..clock import apply_clock_now as _apply_clock_now, clock_state, persist_clock_state
from ..config import PREFIX
from ..fonts import FONT_STYLES
from ..runtime import client
from ..storage.assistant_store import assistant_state, save_assistant
from ..storage.daily_digest_store import daily_digest_state, save_daily_digest
from ..storage.notes_store import delete_note, load_notes, save_note
from ..storage.scheduler_store import create_job
from ..storage.stats_store import STATS, record_error as _record_error
from ..utils import pat
from .fun import _MAGIC8BALL_ANSWERS
from .scheduler import _FULL_RE, _local_now, _to_utc_aware
from .tools import convert_currency, generate_password, translate_text

logger = logging.getLogger("selfbot.handlers.command_router")

# chat_id -> {"action", "params", "preview", "created_at"} — پیشنهادِ در
# انتظارِ تاییدِ همون چت (فقط یکی در آن‌واحد، هم‌الگو با GUESS_GAMES توی fun.py)
PENDING = {}
_PENDING_TTL_SECONDS = 5 * 60


def _parse_router_time(raw_time):
    """
    فقط فرمتِ کاملی که توی system prompt از مدل خواستیم ("YYYY-MM-DD HH:MM")
    رو قبول می‌کنه - تفسیرِ زمانِ نسبی/محاوره‌ای قبلاً توسطِ خودِ مدل (که
    «الان» رو داره) انجام شده. برخلافِ scheduler.parse_time که چند فرمتِ
    ورودیِ کاربر رو قبول می‌کنه.
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


def _str_param(params, name):
    v = params.get(name) if isinstance(params, dict) else None
    return v.strip() if isinstance(v, str) else ""


# ============================================================ اکشن‌ها ===
# هر اکشن: prompt_spec (برای system prompt) + build() + execute()
#   build(params, event)   -> (ok: bool, preview_or_error: str, normalized: dict | None)
#   execute(event, norm)   -> str (متنِ نتیجه‌ی نهایی؛ می‌تونه Exception بندازه)
ACTIONS = {}


def _register(name, prompt_spec):
    def deco(cls):
        ACTIONS[name] = {"prompt_spec": prompt_spec, "build": cls.build, "execute": cls.execute}
        return cls
    return deco


# --------------------------------------------------------- زمان‌بندی ---
@_register(
    "reminder",
    'params: {"time": "YYYY-MM-DD HH:MM", "text": "..."} — یادآوری به خودِ کاربر (Saved Messages)',
)
class _Reminder:
    @staticmethod
    async def build(params, event):
        parsed = _parse_router_time(params.get("time"))
        text = _str_param(params, "text")
        if parsed is None or not text:
            return False, "⏰ زمان یا متنِ یادآوری واضح نبود.", None
        run_at_utc, local_display = parsed
        preview = f"🔔 یادآوری سرِ `{local_display}` (به Saved Messages):\n📝 {text}"
        return True, preview, {"run_at_utc": run_at_utc, "local_display": local_display, "text": text}

    @staticmethod
    async def execute(event, norm):
        self_id = runtime.SELF_ID or event.chat_id
        job = await create_job(self_id, norm["text"], norm["run_at_utc"], "reminder")
        return f"✅ یادآوری ثبت شد (شناسه `{job.id}`) — سرِ **{norm['local_display']}**"


@_register(
    "schedule_message",
    'params: {"time": "YYYY-MM-DD HH:MM", "text": "..."} — ارسالِ خودکارِ یه پیام توی همین چت در آینده',
)
class _ScheduleMessage:
    @staticmethod
    async def build(params, event):
        parsed = _parse_router_time(params.get("time"))
        text = _str_param(params, "text")
        if parsed is None or not text:
            return False, "⏰ زمان یا متنِ پیام واضح نبود.", None
        run_at_utc, local_display = parsed
        preview = f"⏰ سرِ `{local_display}` توی همین چت فرستاده بشه:\n📝 {text}"
        return True, preview, {"run_at_utc": run_at_utc, "local_display": local_display, "text": text}

    @staticmethod
    async def execute(event, norm):
        job = await create_job(event.chat_id, norm["text"], norm["run_at_utc"], "schedule")
        return f"✅ زمان‌بندی ثبت شد (شناسه `{job.id}`) — سرِ **{norm['local_display']}** فرستاده می‌شه"


# ---------------------------------------------------------- یادداشت‌ها ---
@_register(
    "note_add",
    'params: {"key": "...", "text": "..."} — ذخیره‌ی یه یادداشتِ جدید (اگه کلید تکراری باشه، جایگزین می‌شه)',
)
class _NoteAdd:
    @staticmethod
    async def build(params, event):
        key, text = _str_param(params, "key"), _str_param(params, "text")
        if not key or not text:
            return False, "📝 کلید یا متنِ یادداشت واضح نبود.", None
        return True, f"📝 یادداشتِ `{key}` ذخیره بشه؟\n{text}", {"key": key, "text": text}

    @staticmethod
    async def execute(event, norm):
        await save_note(norm["key"], norm["text"])
        return f"✅ یادداشت `{norm['key']}` ذخیره شد"


@_register("note_get", 'params: {"key": "..."} — نمایشِ یه یادداشتِ ذخیره‌شده')
class _NoteGet:
    @staticmethod
    async def build(params, event):
        key = _str_param(params, "key")
        if not key:
            return False, "📝 کلیدِ یادداشت واضح نبود.", None
        return True, f"📝 یادداشتِ `{key}` نشون داده بشه؟", {"key": key}

    @staticmethod
    async def execute(event, norm):
        notes = await load_notes()
        if norm["key"] not in notes:
            return f"❌ یادداشتی با کلید `{norm['key']}` پیدا نشد"
        return f"📝 `{norm['key']}`:\n{notes[norm['key']]}"


@_register("note_delete", 'params: {"key": "..."} — حذفِ یه یادداشتِ ذخیره‌شده')
class _NoteDelete:
    @staticmethod
    async def build(params, event):
        key = _str_param(params, "key")
        if not key:
            return False, "📝 کلیدِ یادداشت واضح نبود.", None
        return True, f"🗑 یادداشتِ `{key}` حذف بشه؟", {"key": key}

    @staticmethod
    async def execute(event, norm):
        notes = await load_notes()
        if norm["key"] not in notes:
            return f"❌ یادداشتی با کلید `{norm['key']}` پیدا نشد"
        await delete_note(norm["key"])
        return f"🗑 یادداشت `{norm['key']}` حذف شد"


# --------------------------------------------------------------- ابزار ---
@_register("calc", 'params: {"expr": "..."} — محاسبه‌ی یه عبارتِ ریاضی (فقط عملیات ریاضیِ ساده)')
class _Calc:
    @staticmethod
    async def build(params, event):
        expr = _str_param(params, "expr")
        if not expr:
            return False, "🧮 عبارتِ ریاضی واضح نبود.", None
        return True, f"🧮 محاسبه بشه: `{expr}` ؟", {"expr": expr}

    @staticmethod
    async def execute(event, norm):
        try:
            result = safe_eval(norm["expr"])
        except ZeroDivisionError:
            return "❌ تقسیم بر صفر ممکن نیست"
        except (SyntaxError, ValueError, TypeError):
            return "❌ عبارت ریاضی نامعتبره"
        except OverflowError:
            return "❌ عدد نتیجه خیلی بزرگه"
        return f"🧮 `{norm['expr']}` = **{result}**"


@_register(
    "translate",
    'params: {"lang": "کدِ دوحرفیِ زبانِ مقصد مثلِ en/fa/ar", "text": "..."} — ترجمه‌ی یه متن',
)
class _Translate:
    @staticmethod
    async def build(params, event):
        lang, text = _str_param(params, "lang"), _str_param(params, "text")
        if not lang or not text:
            return False, "🌐 زبانِ مقصد یا متن واضح نبود.", None
        return True, f"🌐 این متن به `{lang}` ترجمه بشه؟\n{text}", {"lang": lang, "text": text}

    @staticmethod
    async def execute(event, norm):
        try:
            translated = await translate_text(norm["lang"], norm["text"])
        except Exception:
            return "❌ خطا در ترجمه (زبانِ مقصد رو با کدِ دو-حرفی بده، مثلاً en/fa/ar)"
        return f"🌐 ترجمه ({norm['lang']}):\n{translated}"


@_register(
    "currency",
    'params: {"amount": عدد, "src": "کدِ ارزِ مبدا مثلِ USD", "dst": "کدِ ارزِ مقصد مثلِ IRR"} — تبدیلِ ارز',
)
class _Currency:
    @staticmethod
    async def build(params, event):
        amount_raw = params.get("amount") if isinstance(params, dict) else None
        src, dst = _str_param(params, "src").upper(), _str_param(params, "dst").upper()
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = None
        if amount is None or not src or not dst:
            return False, "💱 مقدار یا کدِ ارز واضح نبود.", None
        return (
            True,
            f"💱 تبدیلِ `{amount:g} {src}` به `{dst}` انجام بشه؟",
            {"amount": amount, "src": src, "dst": dst},
        )

    @staticmethod
    async def execute(event, norm):
        try:
            converted, rate = await convert_currency(norm["amount"], norm["src"], norm["dst"])
        except ValueError as e:
            return f"❌ {e}"
        except Exception:
            return "❌ خطا در دریافت نرخ ارز"
        return (
            f"💱 {norm['amount']:g} {norm['src']} = **{converted:,.4f} {norm['dst']}**\n"
            f"(نرخ: 1 {norm['src']} = {rate:g} {norm['dst']})"
        )


@_register("genpass", 'params: {"length": عددِ اختیاری، پیش‌فرض ۱۶} — تولیدِ رمزِ عبورِ تصادفی')
class _GenPass:
    @staticmethod
    async def build(params, event):
        length_raw = params.get("length") if isinstance(params, dict) else None
        try:
            length = int(length_raw) if length_raw not in (None, "") else 16
        except (TypeError, ValueError):
            length = 16
        length = max(4, min(length, 128))
        return True, f"🔐 یه رمزِ عبورِ تصادفیِ {length}-کاراکتری ساخته بشه؟", {"length": length}

    @staticmethod
    async def execute(event, norm):
        pwd = generate_password(norm["length"])
        return f"🔐 رمز عبور تصادفی ({len(pwd)} کاراکتر):\n`{pwd}`"


# ------------------------------------------------------------ پروفایل ---
@_register("setbio", 'params: {"text": "..."} — ⚠️ تغییرِ بیوی حساب (روی پروفایلِ عمومی اثر می‌ذاره)')
class _SetBio:
    @staticmethod
    async def build(params, event):
        text = _str_param(params, "text")
        if not text:
            return False, "📄 متنِ بیو واضح نبود.", None
        return True, f"⚠️ بیوی حساب به این تغییر کنه؟ (روی پروفایلِ عمومی اثر می‌ذاره)\n{text}", {"text": text}

    @staticmethod
    async def execute(event, norm):
        await client(functions.account.UpdateProfileRequest(about=norm["text"]))
        return "✅ بیو بروزرسانی شد"


@_register("setname", 'params: {"text": "..."} — ⚠️ تغییرِ نامِ حساب (روی پروفایلِ عمومی اثر می‌ذاره)')
class _SetName:
    @staticmethod
    async def build(params, event):
        text = _str_param(params, "text")
        if not text:
            return False, "📄 نامِ جدید واضح نبود.", None
        return True, f"⚠️ نامِ حساب به `{text}` تغییر کنه؟ (روی پروفایلِ عمومی اثر می‌ذاره)", {"text": text}

    @staticmethod
    async def execute(event, norm):
        clock_state["base_name"] = norm["text"]
        if clock_state["enabled"]:
            await _apply_clock_now()
        else:
            await client(functions.account.UpdateProfileRequest(first_name=norm["text"]))
        await persist_clock_state()
        return "✅ نام پایه بروزرسانی شد"


# ---------------------------------------------------------------- فونت ---
@_register(
    "font_apply",
    'params: {"style": "یکی از کلیدهای مجاز — انگلیسی: bold/italic/... — فارسی/ترکیبی بر اساسِ زبانِ متن", '
    '"text": "..."} — نمایشِ یه‌بارِ یه متن با یه فونتِ خاص (تغییرِ دائمی نیست)',
)
class _FontApply:
    @staticmethod
    async def build(params, event):
        style = _str_param(params, "style").lower()
        text = _str_param(params, "text")
        if style not in FONT_STYLES or not text:
            return False, f"🔤 فونت یا متن واضح نبود (فونت‌های مجاز: {', '.join(FONT_STYLES)})", None
        preview = FONT_STYLES[style](text)
        return True, f"🔤 این متن با فونتِ `{style}` نمایش داده بشه؟\n{preview}", {"style": style, "text": text}

    @staticmethod
    async def execute(event, norm):
        return FONT_STYLES[norm["style"]](norm["text"])


# --------------------------------------------------------------- سرگرمی ---
@_register("coin_flip", "params: {} — پرتابِ سکه (شیر یا خط)")
class _CoinFlip:
    @staticmethod
    async def build(params, event):
        return True, "🪙 یه سکه پرتاب بشه؟", {}

    @staticmethod
    async def execute(event, norm):
        return f"🪙 {random.choice(['🦁 شیر', '✍️ خط'])}"


@_register("random_number", 'params: {"min": عدد, "max": عدد} — تولیدِ یه عددِ تصادفی توی یه بازه')
class _RandomNumber:
    @staticmethod
    async def build(params, event):
        try:
            lo = int(params.get("min"))
            hi = int(params.get("max"))
        except (TypeError, ValueError):
            return False, "🎯 بازه‌ی عددی واضح نبود.", None
        if lo > hi:
            lo, hi = hi, lo
        return True, f"🎯 یه عددِ تصادفی بینِ `{lo}` و `{hi}` بدم؟", {"lo": lo, "hi": hi}

    @staticmethod
    async def execute(event, norm):
        return f"🎯 عدد تصادفی: **{random.randint(norm['lo'], norm['hi'])}**"


@_register(
    "choose",
    'params: {"options": ["گزینه۱", "گزینه۲", ...]} — انتخابِ تصادفیِ یکی از چند گزینه (حداقل ۲ تا)',
)
class _Choose:
    @staticmethod
    async def build(params, event):
        options = params.get("options") if isinstance(params, dict) else None
        if not isinstance(options, list):
            return False, "🎲 گزینه‌ها واضح نبودن.", None
        options = [str(o).strip() for o in options if str(o).strip()]
        if len(options) < 2:
            return False, "🎲 حداقل ۲ گزینه لازمه.", None
        return True, "🎲 از بینِ این گزینه‌ها یکی انتخاب بشه؟\n" + "، ".join(options), {"options": options}

    @staticmethod
    async def execute(event, norm):
        return f"🎲 انتخاب شد: **{random.choice(norm['options'])}**"


@_register("magic8ball", 'params: {"question": "..."} — پاسخِ توپِ جادویی به یه سوالِ بله/خیر')
class _Magic8Ball:
    @staticmethod
    async def build(params, event):
        q = _str_param(params, "question")
        if not q:
            return False, "🔮 سوال واضح نبود.", None
        return True, f"🔮 از توپِ جادویی بپرسم: «{q}»؟", {"question": q}

    @staticmethod
    async def execute(event, norm):
        answer = random.choice(_MAGIC8BALL_ANSWERS)
        return f"🔮 سوال: {norm['question']}\nپاسخ جادوگر: **{answer}**"


# ---------------------------------------------------------- یادداشت‌ها (ادامه) ---
@_register("note_list", "params: {} — نمایشِ لیستِ کلیدِ همه‌ی یادداشت‌های ذخیره‌شده")
class _NoteList:
    @staticmethod
    async def build(params, event):
        return True, "📋 لیستِ همه‌ی یادداشت‌ها نشون داده بشه؟", {}

    @staticmethod
    async def execute(event, norm):
        notes = await load_notes()
        if not notes:
            return "📋 هنوز هیچ یادداشتی ذخیره نشده"
        return "📋 **یادداشت‌ها:**\n" + "\n".join(f"• `{k}`" for k in notes)


# ------------------------------------------------------------- منشی ---
@_register(
    "assistant_toggle",
    'params: {"state": "on یا off یا auto"} — روشن/خاموش/خودکارکردنِ منشیِ خودکارِ چت',
)
class _AssistantToggle:
    @staticmethod
    async def build(params, event):
        state = _str_param(params, "state").lower()
        if state not in ("on", "off", "auto"):
            return False, "🤖 مشخص نبود منشی روشن/خاموش/خودکار بشه.", None
        label = {"on": "روشن (دستی)", "off": "خاموش (دستی)", "auto": "خودکار (بر اساسِ آنلاین/آفلاین‌بودنت)"}[state]
        return True, f"🤖 منشیِ چت روی «{label}» تنظیم بشه؟", {"state": state}

    @staticmethod
    async def execute(event, norm):
        state = norm["state"]
        if state == "on":
            assistant_state["enabled"] = True
            assistant_state["auto_detect"] = False
            assistant_state["replied"] = set()
        elif state == "off":
            assistant_state["enabled"] = False
            assistant_state["auto_detect"] = False
        else:
            assistant_state["auto_detect"] = True
        await save_assistant()
        label = {"on": "روشن ✅", "off": "خاموش ❌", "auto": "خودکار 🔄"}[state]
        return f"🤖 منشیِ چت: {label}"


# --------------------------------------------------------- خلاصه‌ی روزانه ---
@_register(
    "daily_digest_toggle",
    'params: {"action": "on یا off یا now"} — روشن/خاموش‌کردنِ ارسالِ خودکارِ خلاصه‌ی روزانه، یا اجرای فوریِ همین الانش',
)
class _DailyDigestToggle:
    @staticmethod
    async def build(params, event):
        action = _str_param(params, "action").lower()
        if action not in ("on", "off", "now"):
            return False, "🌙 مشخص نبود خلاصه‌ی روزانه روشن/خاموش بشه یا همین الان اجرا بشه.", None
        label = {"on": "روشن", "off": "خاموش", "now": "اجرای فوری (همین الان)"}[action]
        return True, f"🌙 خلاصه‌ی روزانه: «{label}»؟", {"action": action}

    @staticmethod
    async def execute(event, norm):
        action = norm["action"]
        if action == "on":
            daily_digest_state["enabled"] = True
            await save_daily_digest()
            return "🌙 ارسالِ خودکارِ خلاصه‌ی روزانه روشن شد"
        if action == "off":
            daily_digest_state["enabled"] = False
            await save_daily_digest()
            return "🌙 ارسالِ خودکارِ خلاصه‌ی روزانه خاموش شد"
        # action == "now"
        from .daily_digest import _run_daily_digest
        n = await _run_daily_digest()
        return f"🌙 خلاصه‌ی {n} چت به Saved Messages ارسال شد"


# ----------------------------------------------------------------- آمار ---
@_register("stats_view", "params: {} — نمایشِ خلاصه‌ی آمارِ استفاده از سلف‌بات (فقط خواندنی)")
class _StatsView:
    @staticmethod
    async def build(params, event):
        return True, "📊 آمارِ استفاده از سلف‌بات نشون داده بشه؟", {}

    @staticmethod
    async def execute(event, norm):
        return (
            "📊 **آمار سلف‌بات**\n\n"
            f"• کل دستورهای اجراشده: {STATS['commands_total']}\n"
            f"• کل پیام‌های دیده‌شده: {STATS['messages_total']}\n"
            f"• ارسالِ خودکارِ موفق: {STATS['autopost_ok']}\n"
            f"• ارسالِ خودکارِ ناموفق: {STATS['autopost_fail']}\n"
            f"• خطاهای سیستمی: {STATS['errors']}"
        )


# ===================================================== ساختِ system prompt ===
def _build_system_prompt(now_local: str) -> str:
    lines = [
        "تو یه روترِ دستوریِ سلف‌بات تلگرام هستی. کاربر یه جمله‌ی آزاد و محاوره‌ای",
        "(فارسی یا انگلیسی) می‌نویسه؛ کارِ تو فقط تشخیصه، نه اجرا.",
        "باید **فقط و فقط** یه شیِ JSON خام برگردونی (بدون توضیح، بدون Markdown،",
        'بدون بک‌تیک) دقیقاً با این ساختار: {"intent": "<یکی از کلیدهای زیر یا unknown>", "params": {...}}',
        "",
        f"زمانِ محلیِ الانِ کاربر: {now_local}",
        "",
        "intentهای مجاز و پارامترهاشون:",
    ]
    for name, spec in ACTIONS.items():
        lines.append(f'- "{name}": {spec["prompt_spec"]}')
    lines += [
        "",
        "قوانین:",
        "- هر جا زمان لازمه، همیشه به‌فرمتِ کاملِ آینده‌یِ \"YYYY-MM-DD HH:MM\" بده (بر اساسِ زمانِ بالا حساب کن؛"
        " اگه فقط ساعت گفته شده و امروز گذشته، یعنی فردا)",
        "- اگه جمله به هیچ‌کدوم از intentهای بالا نمی‌خورد، یا پارامترهای لازم به‌اندازه‌ی کافی روشن نبودن ->"
        ' دقیقاً {"intent": "unknown", "params": {}} برگردون',
        "- تو **هیچ‌وقت** واقعاً کاری انجام نمی‌دی (نه پیام می‌فرستی، نه چیزی تغییر می‌دی) - فقط تشخیص می‌دی؛",
        "  اجرای واقعی با خودِ سیستمه، بعدِ تاییدِ صریحِ کاربر.",
    ]
    return "\n".join(lines)


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


_ACTIONS_HELP_LIST = " / ".join(f"`{name}`" for name in ACTIONS)


async def _confirm(event, chat_id):
    pending = PENDING.get(chat_id)
    if pending is None:
        return await event.edit(
            f"چیزی برای تایید در انتظار نیست. اول یه‌بار `{PREFIX}هوش <جمله>` رو بفرست."
        )
    if time.monotonic() - pending["created_at"] > _PENDING_TTL_SECONDS:
        PENDING.pop(chat_id, None)
        return await event.edit("⌛ این پیشنهاد منقضی شده - دوباره امتحان کن")

    action = ACTIONS[pending["action"]]
    try:
        result_text = await action["execute"](event, pending["params"])
    except Exception as e:
        _record_error()
        logger.exception("خطا در اجرای اکشنِ روترِ هوشمند: %s", pending["action"])
        return await event.edit(f"❌ خطا در اجرا: {e}")

    PENDING.pop(chat_id, None)
    await event.edit(result_text)


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
            "جمله رو تحلیل می‌کنم و قبل از اجرا، خلاصه‌ش رو نشون می‌دم:\n"
            f"• تایید: `{PREFIX}هوش تایید`\n"
            f"• لغو: `{PREFIX}هوش لغو`\n\n"
            f"بخش‌های پشتیبانی‌شده: {_ACTIONS_HELP_LIST}\n"
            "برای هر چیزِ دیگه‌ای (مدیریتِ گروه، عکس/صوت، اتوماسیون‌ها) مستقیم از دستورِ خودشون استفاده کن."
        )

    await event.edit("🧠 در حال تشخیصِ دستور...")
    messages = [
        {"role": "system", "content": _build_system_prompt(_local_now().strftime("%Y-%m-%d %H:%M"))},
        {"role": "user", "content": arg},
    ]
    try:
        answer = await ai.ask_ai(messages, max_tokens=300)
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
    params = data.get("params") if isinstance(data, dict) else None
    if not isinstance(params, dict):
        params = {}

    action = ACTIONS.get(intent)
    if action is None:
        return await event.edit(
            "🤷 نتونستم این جمله رو با اطمینان به یه دستورِ پشتیبانی‌شده تبدیل کنم.\n"
            f"بخش‌های پشتیبانی‌شده: {_ACTIONS_HELP_LIST}\n"
            "برای هر چیزِ دیگه مستقیم از دستورِ خودش استفاده کن."
        )

    try:
        ok, preview_or_error, normalized = await action["build"](params, event)
    except Exception:
        _record_error()
        logger.exception("خطا در build اکشنِ روترِ هوشمند: %s", intent)
        return await event.edit("❌ خطا در پردازشِ پارامترها")

    if not ok:
        return await event.edit(
            f"🤷 {preview_or_error}\nمی‌تونی واضح‌تر بنویسی، یا مستقیم از دستورِ خودِ اون بخش استفاده کنی."
        )

    PENDING[chat_id] = {
        "action": intent,
        "params": normalized,
        "created_at": time.monotonic(),
    }
    await event.edit(
        f"{preview_or_error}\n\nتایید: `{PREFIX}هوش تایید`  •  لغو: `{PREFIX}هوش لغو`"
    )
