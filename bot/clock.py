"""ساعت زنده در نام پروفایل: استایل‌ها، وضعیت، و تسک پس‌زمینه."""
import asyncio
import logging
import re
from datetime import datetime, timedelta

from telethon import errors, functions

from . import config
from .runtime import client
from .storage.clock_store import load_clock_settings, save_clock_settings
from .storage.stats_store import record_error

logger = logging.getLogger("selfbot.clock")


def _to_persian_digits(s):
    return s.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _to_fullwidth(s):
    # بلاک Fullwidth Forms: با افزودن 0xFEE0 به کاراکترهای ASCII قابل‌چاپ به‌دست میاد
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else c for c in s)


def _to_monospace_digits(s):
    # Mathematical Monospace Digits: U+1D7F6 تا U+1D7FF
    return "".join(chr(0x1D7F6 + int(c)) if c.isdigit() else c for c in s)


def _to_doublestruck_digits(s):
    # Mathematical Double-Struck Digits: U+1D7D8 تا U+1D7E1
    return "".join(chr(0x1D7D8 + int(c)) if c.isdigit() else c for c in s)


def _to_circled_digits(s):
    def circ(d):
        d = int(d)
        return chr(0x24EA) if d == 0 else chr(0x2460 + d - 1)  # ⓪①②③...
    return "".join(circ(c) if c.isdigit() else c for c in s)


def _to_bold_digits(s):
    # Mathematical Bold Digits: U+1D7CE تا U+1D7D7
    return "".join(chr(0x1D7CE + int(c)) if c.isdigit() else c for c in s)


def _to_subscript_digits(s):
    # Subscript Digits: U+2080 تا U+2089
    return "".join(chr(0x2080 + int(c)) if c.isdigit() else c for c in s)


# آیکون ساعت آنالوگ چرخان بر اساس ساعتِ فعلی (۱۲ تا برای رأس ساعت + ۱۲ تا برای نیم‌ساعت)
_CLOCK_ON_HOUR = ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"]
_CLOCK_HALF_HOUR = ["🕧", "🕜", "🕝", "🕞", "🕟", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦"]


def _rotating_clock_icon(hour, minute):
    h12 = hour % 12
    return _CLOCK_HALF_HOUR[h12] if minute >= 30 else _CLOCK_ON_HOUR[h12]


# --- پاک‌سازی پسوند ساعت قدیمی از نام ---
# چون clock_state فقط توی حافظه‌ست، هر بار که سرویس ری‌استارت/ری‌دیپلوی بشه
# (مثلاً روی Railway) نام فعلیِ زنده‌ی پروفایل که از قبل شامل ساعتِ استایل قبلی
# بوده به‌اشتباه به‌عنوان «نام پایه»ی جدید خونده می‌شه. این تابع، مهم نیست خروجی
# کدوم‌یک از ۱۵ استایل باشه، پسوند ساعتی رو از انتهای نام (حتی اگه چندلایه و
# تکرارشده باشه) پاک می‌کنه تا نام پایه‌ی واقعی برگرده.
_DIGIT_CLASS = (
    r"[0-9\u06F0-\u06F9\uFF10-\uFF19\U0001D7D8-\U0001D7E1\U0001D7F6-\U0001D7FF"
    r"\u2460-\u2468\u24EA\U0001D7CE-\U0001D7D7\u2080-\u2089]"
)
_SEP_CLASS = r"[:\uFF1A]"
_ICON_CLASS = r"(?:[\U0001F550-\U0001F567]|\u23F1)\uFE0F?"

_CLOCK_SUFFIX_RE = re.compile(
    r"(?:\s*\|\s*)?(?:"
    rf"{_ICON_CLASS}\s*{_DIGIT_CLASS}{{2}}{_SEP_CLASS}{_DIGIT_CLASS}{{2}}"   # default / animated
    rf"|{_DIGIT_CLASS}{{2}}{_SEP_CLASS}{_DIGIT_CLASS}{{2}}"                  # persian/fullwidth/monospace/doublestruck/circled/minimal/bold/subscript
    r"|『[0-9]{2}:[0-9]{2}』"                                                 # brackets
    rf"|{_ICON_CLASS}\s*[0-9]{{2}}•[0-9]{{2}}"                               # dotstyle
    r"|\[[0-9]{2}:[0-9]{2}\]"                                                # square
    r"|[0-9]{2}-[0-9]{2}"                                                    # dash
    r"|✦\s*[0-9]{2}:[0-9]{2}\s*✦"                                           # star
    r")\s*$"
)


def strip_clock_suffix(name):
    prev = None
    while prev != name:
        prev = name
        name = _CLOCK_SUFFIX_RE.sub("", name).rstrip()
    return name


def _style_default(hour, minute):
    return f"🕐 {hour:02d}:{minute:02d}"


def _style_animated(hour, minute):
    return f"{_rotating_clock_icon(hour, minute)} {hour:02d}:{minute:02d}"


def _style_persian(hour, minute):
    return _to_persian_digits(f"{hour:02d}:{minute:02d}")


def _style_fullwidth(hour, minute):
    return _to_fullwidth(f"{hour:02d}:{minute:02d}")


def _style_monospace(hour, minute):
    return _to_monospace_digits(f"{hour:02d}:{minute:02d}")


def _style_doublestruck(hour, minute):
    return _to_doublestruck_digits(f"{hour:02d}:{minute:02d}")


def _style_circled(hour, minute):
    return _to_circled_digits(f"{hour:02d}:{minute:02d}")


def _style_brackets(hour, minute):
    return f"『{hour:02d}:{minute:02d}』"


def _style_dotstyle(hour, minute):
    return f"⏱ {hour:02d}•{minute:02d}"


def _style_minimal(hour, minute):
    return f"{hour:02d}:{minute:02d}"


def _style_bold(hour, minute):
    return _to_bold_digits(f"{hour:02d}:{minute:02d}")


def _style_subscript(hour, minute):
    return _to_subscript_digits(f"{hour:02d}:{minute:02d}")


def _style_square(hour, minute):
    return f"[{hour:02d}:{minute:02d}]"


def _style_dash(hour, minute):
    return f"{hour:02d}-{minute:02d}"


def _style_star(hour, minute):
    return f"✦ {hour:02d}:{minute:02d} ✦"


# ترتیب نمایش در لیست و چرخش با مدل‌ساعت next
CLOCK_STYLE_ORDER = [
    "default", "animated", "persian", "fullwidth",
    "monospace", "doublestruck", "circled", "brackets", "dotstyle", "minimal",
    "bold", "subscript", "square", "dash", "star",
]
CLOCK_STYLES = {
    "default": _style_default,
    "animated": _style_animated,
    "persian": _style_persian,
    "fullwidth": _style_fullwidth,
    "monospace": _style_monospace,
    "doublestruck": _style_doublestruck,
    "circled": _style_circled,
    "brackets": _style_brackets,
    "dotstyle": _style_dotstyle,
    "minimal": _style_minimal,
    "bold": _style_bold,
    "subscript": _style_subscript,
    "square": _style_square,
    "dash": _style_dash,
    "star": _style_star,
}

clock_state = {
    "enabled": True,
    "base_name": None,
    "style": config.CLOCK_STYLE_ENV if config.CLOCK_STYLE_ENV in CLOCK_STYLES else "default",
}


async def init_clock_state() -> None:
    """
    موقع استارتاپ صدا زده می‌شه: enabled/style رو از PostgreSQL می‌خونه.
    base_name عمداً از دیتابیس بازیابی نمی‌شه - همون‌طور که کامنتِ بالای این
    فایل توضیح می‌ده، base_name همیشه باید زنده از روی نام فعلیِ پروفایل در
    تلگرام (با پاک‌کردنِ پسوند ساعت) مشتق بشه، نه از یک مقدار ذخیره‌شده که
    ممکنه با نامی که کاربر بین این‌مدت عوض کرده باشه تداخل کنه.
    """
    loaded = await load_clock_settings()
    clock_state["enabled"] = loaded["enabled"]
    if loaded["style"] in CLOCK_STYLES:
        clock_state["style"] = loaded["style"]


async def persist_clock_state() -> None:
    await save_clock_settings(
        enabled=clock_state["enabled"],
        style=clock_state["style"],
        base_name=clock_state["base_name"],
    )


async def refresh_base_name():
    """
    نام فعلیِ زنده رو از تلگرام می‌خونه و پسوند ساعت رو ازش پاک می‌کنه. اگه
    کاربر مستقیم توی اپ تلگرام اسمش رو عوض کرده باشه، این تابع همون نام جدید
    رو به‌عنوان نام پایه می‌پذیره - در نتیجه ربات دیگه اسم قدیمی رو روی اسم
    تازه‌ی کاربر بازنویسی نمی‌کنه. فقط توی تسک پس‌زمینه استفاده می‌شه، نه توی
    دستورات فوری مثل setname (تا با نامی که تازه ست کردید تداخل نکنه).
    """
    me = await client.get_me()
    clock_state["base_name"] = strip_clock_suffix(me.first_name or "")
    return clock_state["base_name"]


async def apply_clock_now():
    """اعمال فوری استایل/نام روی پروفایل، بدون صبر تا تیک بعدی ساعت"""
    if not clock_state["enabled"]:
        return
    if clock_state["base_name"] is None:
        me = await client.get_me()
        clock_state["base_name"] = strip_clock_suffix(me.first_name or "")
    now = datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)
    base = clock_state["base_name"][:40]
    clock_part = CLOCK_STYLES[clock_state["style"]](now.hour, now.minute)
    try:
        await client(functions.account.UpdateProfileRequest(first_name=f"{base} | {clock_part}"))
    except Exception:
        record_error()
        logger.exception("خطا در اعمال فوری استایل ساعت")


async def clock_updater():
    """
    این تسک همیشه دقیقاً سر شروع هر دقیقه (ثانیه صفر) بیدار می‌شه و پروفایل
    رو آپدیت می‌کنه. CLOCK_INTERVAL یعنی «هر چند دقیقه یک‌بار آپدیت بشه»
    (پیش‌فرض هر ۱ دقیقه). همچنین هر تیک، نام زنده رو با تلگرام هماهنگ
    می‌کنه تا اگه کاربر مستقیم توی اپ اسمش رو عوض کرده باشه، ربات روش
    بازنویسی نکنه.
    """
    interval_minutes = max(config.CLOCK_INTERVAL // 60, 1)
    last_sent = None  # tuple (style, base, hour, minute) برای تشخیص تغییر واقعی
    while True:
        now = datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)
        if clock_state["enabled"] and now.minute % interval_minutes == 0:
            try:
                base = (await refresh_base_name())[:40]
                key = (clock_state["style"], base, now.hour, now.minute)
                if key != last_sent:
                    clock_part = CLOCK_STYLES[clock_state["style"]](now.hour, now.minute)
                    new_name = f"{base} | {clock_part}"
                    await client(functions.account.UpdateProfileRequest(first_name=new_name))
                    last_sent = key
                    await persist_clock_state()
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception:
                record_error()
                logger.exception("خطا در بروزرسانی ساعت")
        # صبر تا دقیقاً لحظه‌ی شروع دقیقه‌ی بعدی (نه یک فاصله‌ی ثابت و بی‌ربط به ساعت واقعی)
        now2 = datetime.utcnow() + timedelta(hours=config.TIMEZONE_OFFSET)
        await asyncio.sleep(max(60 - now2.second, 1))
