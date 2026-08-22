"""۲) ابزار: calc / qr / shorten / weather / tr / google / genpass / hash / base64 / count / currency / price"""
import base64
import hashlib
import random
import string
from io import BytesIO
from urllib.parse import quote as urlquote

import aiohttp

from telethon import events

from ..config import PREFIX
from ..runtime import client, get_http_session
from ..calc import safe_eval
from ..utils import pat

@client.on(events.NewMessage(outgoing=True, pattern=pat(["حساب", "calc"])))
async def calc_handler(event):
    expr = event.pattern_match.group(1)
    if not expr:
        return await event.edit(
            f"مثال: `{PREFIX}حساب 5*(3+2)` یا `{PREFIX}حساب sqrt(2)+sin(pi/2)`\n"
            "توابع: sqrt, abs, round, sin, cos, tan, asin, acos, atan, log, log10, log2, "
            "exp, floor, ceil, factorial, min, max, hypot, degrees, radians\n"
            "ثابت‌ها: pi, e, tau, inf"
        )
    try:
        result = safe_eval(expr)
        await event.edit(f"🧮 `{expr}` = **{result}**")
    except ZeroDivisionError:
        await event.edit("❌ تقسیم بر صفر ممکن نیست")
    except (SyntaxError, ValueError, TypeError):
        await event.edit("❌ عبارت ریاضی نامعتبره")
    except OverflowError:
        await event.edit("❌ عدد نتیجه خیلی بزرگه")
    except Exception:
        await event.edit("❌ خطا در محاسبه")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["کیوآر", "qr"])))
async def qr_handler(event):
    import qrcode
    text = event.pattern_match.group(1)
    if not text:
        return await event.edit(f"مثال: `{PREFIX}کیوآر https://example.com`")
    img = qrcode.make(text)
    bio = BytesIO()
    bio.name = "qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    await event.delete()
    await client.send_file(event.chat_id, bio, caption=f"🔳 QR برای: {text}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["کوتاه", "shorten"])))
async def shorten_handler(event):
    url = event.pattern_match.group(1)
    if not url:
        return await event.edit(f"مثال: `{PREFIX}کوتاه https://example.com/long-link`")
    try:
        session = await get_http_session()
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get("https://is.gd/create.php",
                                params={"format": "simple", "url": url},
                                timeout=timeout) as r:
            text = await r.text()
        await event.edit(f"🔗 لینک کوتاه‌شده:\n{text}")
    except Exception:
        await event.edit("❌ خطا در کوتاه کردن لینک")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["هوا", "weather"])))
async def weather_handler(event):
    city = event.pattern_match.group(1)
    if not city:
        return await event.edit(f"مثال: `{PREFIX}هوا Tehran`")
    try:
        session = await get_http_session()
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(f"https://wttr.in/{city}?format=%C+%t+%h+%w",
                                timeout=timeout) as r:
            text = await r.text()
        await event.edit(f"🌤 آب‌وهوای {city}:\n{text}")
    except Exception:
        await event.edit("❌ خطا در دریافت آب‌وهوا")


async def translate_text(lang: str, text: str) -> str:
    """
    هسته‌ی خالصِ ترجمه (بدون event) - هم توسطِ `.ترجمه` و هم توسطِ روترِ
    هوشمند (`.هوش`) استفاده می‌شه. روی خطا Exception می‌ندازه.
    """
    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=10)
    params = {"client": "gtx", "sl": "auto", "tl": lang, "dt": "t", "q": text}
    headers = {"User-Agent": "Mozilla/5.0"}
    async with session.get(
        "https://translate.googleapis.com/translate_a/single",
        params=params, headers=headers, timeout=timeout,
    ) as r:
        if r.status != 200:
            raise ValueError(f"HTTP {r.status}")
        data = await r.json(content_type=None)
    translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
    if not translated.strip():
        raise ValueError("پاسخِ خالی")
    return translated


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ترجمه", "tr"])))
async def translate_handler(event):
    args = event.pattern_match.group(1)
    lang, text = None, None
    if args and " " in args:
        lang, text = args.split(" ", 1)
    elif args and event.is_reply:
        lang = args.strip()
        reply = await event.get_reply_message()
        text = reply.raw_text
    if not lang or not text:
        return await event.edit(f"مثال: `{PREFIX}ترجمه en سلام دنیا` یا با ریپلای: `{PREFIX}ترجمه en`")
    try:
        translated = await translate_text(lang, text)
        await event.edit(f"🌐 ترجمه ({lang}):\n{translated}")
    except Exception:
        await event.edit("❌ خطا در ترجمه (زبانِ مقصد رو با کدِ دو-حرفی بده، مثلاً en/fa/ar)")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["جستجو", "google"])))
async def google_handler(event):
    q = event.pattern_match.group(1)
    if not q:
        return await event.edit(f"مثال: `{PREFIX}جستجو چطور پایتون یاد بگیرم`")
    link = "https://www.google.com/search?q=" + urlquote(q)
    await event.edit(f"🔍 نتایج گوگل برای: {q}\n{link}")


def generate_password(length: int = 16) -> str:
    """هسته‌ی خالصِ تولیدِ رمز - هم توسطِ `.رمزعبور` و هم روترِ هوشمند استفاده می‌شه."""
    length = max(4, min(length, 128))
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(random.SystemRandom().choice(alphabet) for _ in range(length))


@client.on(events.NewMessage(outgoing=True, pattern=pat(["رمزعبور", "genpass"])))
async def genpass_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    length = 16
    if arg:
        try:
            length = int(arg)
        except ValueError:
            return await event.edit(f"مثال: `{PREFIX}رمزعبور 20`")
    pwd = generate_password(length)
    await event.edit(f"🔐 رمز عبور تصادفی ({len(pwd)} کاراکتر):\n`{pwd}`")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["هش", "hash"])))
async def hash_handler(event):
    args = event.pattern_match.group(1)
    text = None
    algo = "sha256"
    if args:
        parts = args.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() in ("md5", "sha1", "sha256", "sha512"):
            algo, text = parts[0].lower(), parts[1]
        else:
            text = args
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text
    if not text:
        return await event.edit(f"مثال: `{PREFIX}هش سلام` یا `{PREFIX}هش sha512 سلام`")
    digest = hashlib.new(algo, text.encode("utf-8")).hexdigest()
    await event.edit(f"🔒 {algo}:\n`{digest}`")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["بیس۶۴", "بیس64", "base64"])))
async def base64_handler(event):
    args = event.pattern_match.group(1)
    sub, text = None, None
    if args:
        parts = args.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() in ("انکد", "دیکد", "encode", "decode"):
            sub, text = parts[0].lower(), parts[1]
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text
        sub = sub or "encode"
    if not text:
        return await event.edit(f"مثال: `{PREFIX}بیس64 انکد سلام` یا `{PREFIX}بیس64 دیکد c2xhbQ==`")
    try:
        if sub in ("دیکد", "decode"):
            result = base64.b64decode(text.encode("utf-8")).decode("utf-8", errors="replace")
            await event.edit(f"🔓 دیکد شده:\n`{result}`")
        else:
            result = base64.b64encode(text.encode("utf-8")).decode("utf-8")
            await event.edit(f"🔐 انکد شده:\n`{result}`")
    except Exception:
        await event.edit("❌ خطا در تبدیل - ورودی معتبر نیست")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["نویسه‌شمار", "count"])))
async def count_handler(event):
    text = event.pattern_match.group(1)
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text
    if not text:
        return await event.edit(f"مثال: `{PREFIX}نویسه‌شمار یک متن اینجا` یا با ریپلای روی پیام")
    chars = len(text)
    chars_no_space = len(text.replace(" ", "").replace("\n", ""))
    words = len(text.split())
    lines = len(text.splitlines()) or 1
    await event.edit(
        "🔢 **آمار متن:**\n"
        f"حروف: {chars} (بدون فاصله: {chars_no_space})\n"
        f"کلمات: {words}\n"
        f"خط‌ها: {lines}"
    )


async def convert_currency(amount: float, src: str, dst: str) -> tuple[float, float]:
    """
    هسته‌ی خالصِ تبدیلِ ارز (بدون event) - (converted, rate) رو برمی‌گردونه.
    هم توسطِ `.ارز` و هم توسطِ روترِ هوشمند (`.هوش`) استفاده می‌شه.
    روی خطا یا کدِ ارزِ نامعتبر ValueError می‌ندازه.
    """
    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=10)
    async with session.get(f"https://open.er-api.com/v6/latest/{src}", timeout=timeout) as r:
        data = await r.json(content_type=None)
    if data.get("result") != "success" or dst not in data.get("rates", {}):
        raise ValueError("کد ارز نامعتبره یا در دسترس نیست")
    rate = data["rates"][dst]
    return amount * rate, rate


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ارز", "currency"])))
async def currency_handler(event):
    args = event.pattern_match.group(1)
    if not args:
        return await event.edit(f"مثال: `{PREFIX}ارز 10 USD IRR`")
    parts = args.split()
    if len(parts) != 3:
        return await event.edit(f"مثال: `{PREFIX}ارز 10 USD IRR`")
    try:
        amount = float(parts[0])
    except ValueError:
        return await event.edit(f"مثال: `{PREFIX}ارز 10 USD IRR`")
    src, dst = parts[1].upper(), parts[2].upper()
    try:
        converted, rate = await convert_currency(amount, src, dst)
        await event.edit(f"💱 {amount:g} {src} = **{converted:,.4f} {dst}**\n(نرخ: 1 {src} = {rate:g} {dst})")
    except ValueError as e:
        await event.edit(f"❌ {e}")
    except Exception:
        await event.edit("❌ خطا در دریافت نرخ ارز")


# --- قیمت لحظه‌ای طلا/ارز/سکه (منبع: tgju.org) ---------------------------------
# TGJU یه فیدِ JSON عمومی (بدون نیاز به کلید/API) روی چند زیردامنه‌ی call1..call4
# منتشر می‌کنه که دقیقاً همون داده‌ی جدول اصلیِ سایت رو برمی‌گردونه. اینجا چند
# زیردامنه رو پشت سر هم امتحان می‌کنیم (برای مواقعی که یکیشون کند/در دسترس نباشه)
# و فقط کلیدهایی که واقعاً توی پاسخ باشن نمایش داده می‌شن - اگه TGJU ساختار یا
# اسمِ یکی از کلیدها رو عوض کنه، اون آیتم به‌سادگی از خروجی حذف می‌شه (بدون کرش).
TGJU_ENDPOINTS = [
    "https://call4.tgju.org/ajax.json",
    "https://call3.tgju.org/ajax.json",
    "https://call2.tgju.org/ajax.json",
    "https://call1.tgju.org/ajax.json",
]
TGJU_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.tgju.org/",
}

# (کلیدِ فید TGJU, برچسبِ فارسی, واحد)
PRICE_GROUPS = [
    ("ارز", "💵", [
        ("price_dollar_rl", "دلار آمریکا", "ریال"),
        ("price_eur", "یورو", "ریال"),
        ("price_gbp", "پوند انگلیس", "ریال"),
        ("price_try", "لیر ترکیه", "ریال"),
        ("price_aed", "درهم امارات", "ریال"),
        ("price_cad", "دلار کانادا", "ریال"),
        ("price_aud", "دلار استرالیا", "ریال"),
        ("price_cny", "یوان چین", "ریال"),
    ]),
    ("طلا", "🥇", [
        ("geram18", "طلای ۱۸ عیار (هر گرم)", "ریال"),
        ("mesghal", "مثقال طلا", "ریال"),
        ("ons", "انس جهانی طلا", "دلار"),
    ]),
    ("سکه", "🪙", [
        ("sekee", "سکه امامی", "ریال"),
        ("sekeb", "سکه بهار آزادی", "ریال"),
        ("nim", "نیم‌سکه", "ریال"),
        ("rob", "ربع‌سکه", "ریال"),
        ("gerami", "سکه گرمی", "ریال"),
    ]),
]

GROUP_ALIASES = {
    "ارز": ("ارزها", "currency", "fx", "دلار"),
    "طلا": ("gold",),
    "سکه": ("سکه‌ها", "coin", "coins"),
}


async def _fetch_tgju_current():
    """داده‌ی «current» فید TGJU رو برمی‌گردونه؛ چند زیردامنه رو پشت سر هم امتحان می‌کنه."""
    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=8)
    last_err = None
    for url in TGJU_ENDPOINTS:
        try:
            async with session.get(url, timeout=timeout, headers=TGJU_HEADERS) as r:
                if r.status != 200:
                    continue
                data = await r.json(content_type=None)
            current = data.get("current") if isinstance(data, dict) else None
            if current:
                return current
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("پاسخ معتبری از TGJU دریافت نشد")


def _price_line(current: dict, key: str, label: str, unit: str) -> str:
    item = current.get(key) or {}
    price = item.get("p")
    if not price:
        return None
    return f"› {label}: **{price}** {unit}"


@client.on(events.NewMessage(outgoing=True, pattern=pat(["قیمت", "price"])))
async def price_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()

    msg = await event.edit("⏳ در حال دریافت قیمت‌های لحظه‌ای از TGJU...")
    try:
        current = await _fetch_tgju_current()
    except Exception:
        await msg.edit(
            "❌ خطا در دریافت قیمت‌ها از TGJU.\n"
            "ممکنه سایت موقتاً در دسترس نباشه یا فیلترشکن/DNS سرور لازم باشه؛ چند لحظه دیگه دوباره امتحان کن."
        )
        return

    # اگه آرگومان دقیقاً اسم یکی از بخش‌ها (یا مترادف‌هاش) باشه -> فقط همون بخش
    matched_group = None
    for name, emoji, items in PRICE_GROUPS:
        if arg and (arg == name or arg.lower() in GROUP_ALIASES.get(name, ())):
            matched_group = (name, emoji, items)
            break

    # اگه آرگومان بود ولی اسم بخش نبود -> جستجوی آزاد بین برچسب‌های همه‌ی آیتم‌ها
    if arg and matched_group is None:
        matches = []
        for _, _, items in PRICE_GROUPS:
            for key, label, unit in items:
                if arg in label:
                    line = _price_line(current, key, label, unit)
                    if line:
                        matches.append(line)
        if not matches:
            return await msg.edit(
                "❌ آیتمی با این اسم توی لیستِ پوشش‌داده‌شده پیدا نشد.\n"
                f"مثال: `{PREFIX}قیمت` (همه) یا `{PREFIX}قیمت طلا` یا `{PREFIX}قیمت دلار`"
            )
        await msg.edit("💹 **نتیجه‌ی جستجو** (منبع: tgju.org)\n\n" + "\n".join(matches))
        return

    groups_to_show = [matched_group] if matched_group else PRICE_GROUPS
    sections = []
    for name, emoji, items in groups_to_show:
        lines = [_price_line(current, k, l, u) for k, l, u in items]
        lines = [ln for ln in lines if ln]
        if lines:
            sections.append(f"{emoji} **{name}**\n" + "\n".join(lines))

    if not sections:
        await msg.edit("❌ داده‌ای برای نمایش پیدا نشد (احتمالاً TGJU ساختار فید رو تغییر داده).")
        return

    header = "💹 **قیمت‌های لحظه‌ای بازار** (به ریال، منبع: tgju.org)\n" + ("─" * 24)
    footer = "\n\n🔎 برای یه بخش: `" + PREFIX + "قیمت طلا` یا `" + PREFIX + "قیمت سکه` — برای جستجو: `" + PREFIX + "قیمت دلار`"
    await msg.edit(header + "\n\n" + "\n\n".join(sections) + footer)

