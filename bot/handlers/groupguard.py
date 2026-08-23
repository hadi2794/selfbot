"""
۱۵) مدیریت گروه پیشرفته: فیلترلینک / خوش‌آمدگویی / برچسب‌همه / فیلترِ پورن / فیلترِ اسپم

  - `.فیلترلینک روشن/خاموش/وضعیت`  → حذف خودکار پیام‌های حاویِ لینک از
    اعضای غیرادمینِ همین گروه (چک ادمین‌بودن با client.get_permissions، پس
    خودِ ادمین‌ها و owner همیشه مستثنی‌ان).
  - `.خوش‌آمد روشن/خاموش/وضعیت/متن <متن>`  → پیامِ خوش‌آمدگویی خودکار برای
    عضو جدیدِ همین گروه. توی متن می‌شه از `{نام}` (اسمِ کاربر) یا `{منشن}`
    (تگِ واقعیِ کاربر) استفاده کرد.
  - `.برچسب‌همه <متن اختیاری>`  → با یه دستور همه‌ی اعضای گروه رو تگ می‌زنه؛
    برای کاهشِ ریسکِ اسپم/فلاد، در batchهای چندتایی با فاصله ارسال می‌شه و
    سقفِ تعداد عضو داره - این ویژگی رو با احتیاط و کم استفاده کن.
  - `.فیلترپورن روشن/خاموش/وضعیت`  → هر عکسِ معمولیِ ارسالی از طرفِ اعضای
    غیرادمین با AI (نیازمندِ AI_API_KEY + مدلِ Vision-دار مثلِ gpt-4o-mini)
    بررسی و در صورتِ تشخیصِ محتوای نامناسب حذف می‌شه. اگه AI در دسترس نباشه
    یا خطا بده، fail-open می‌کنه (کاری با عکس نداره؛ ترجیح بر ریسک‌نکردنِ
    حذفِ اشتباهیِ عکسِ سالمه). فعلاً فقط عکسِ فشرده رو پوشش می‌ده، نه
    ویدیو/GIF/استیکر/فایل.
  - `.فیلتراسپم روشن/خاموش/وضعیت`  → کاملاً محلی (بدونِ نیاز به AI): اگه یه
    عضوِ غیرادمین توی یه بازه‌ی زمانیِ کوتاه بیش از حد پیام بفرسته (فلاد) یا
    عینِ یه متن رو چندبار پشتِ‌سرِهم تکرار کنه، اون پیام‌ها خودکار حذف می‌شن
    و یه هشدارِ کوتاه (با فاصله‌ی زمانی، برای جلوگیری از اسپم‌شدنِ خودِ هشدار)
    توی گروه فرستاده می‌شه.

هر پنج تنظیم (فیلترلینک/خوش‌آمد/فیلترپورن/فیلتراسپم) به‌ازای هر گروه (chat_id)
در PostgreSQL ذخیره می‌شن، پس با ری‌استارت/ری‌دیپلوی از دست نمی‌رن.
"""
import asyncio
import base64
import logging
import re
import time
from collections import deque

from telethon import events

from .. import ai, config, runtime
from ..config import PREFIX
from ..runtime import client
from ..storage.group_guard_store import (
    get_welcome_text,
    group_guard_state,
    is_link_filter_enabled,
    is_porn_filter_enabled,
    is_spam_filter_enabled,
    is_welcome_enabled,
    set_link_filter,
    set_porn_filter,
    set_spam_filter,
    set_welcome_enabled,
    set_welcome_text,
)
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.groupguard")

# لینک/دعوتِ تلگرام یا هر URL دیگه (http/https/www./t.me/telegram.me) - عمداً
# @username رو چک نمی‌کنیم چون ریپلای/منشنِ عادیِ اعضا هم همین الگو رو داره
# و false-positive زیاد می‌شد.
_LINK_RE = re.compile(
    r"(https?://|www\.[a-z0-9-]+\.[a-z]{2,}|t(?:elegram)?\.me/)", re.IGNORECASE
)

_TAG_BATCH_SIZE = 5
_TAG_BATCH_DELAY = 3  # ثانیه بین هر batch - برای کاهش ریسک اسپم/فلاد
_TAG_MAX_MEMBERS = 200  # سقف امن؛ گروه‌های بزرگ‌تر ریسک محدودیت اکانت رو بالا می‌برن

# کشِ کوتاه‌مدتِ نتیجه‌ی ادمین‌بودن - چون فیلترِ اسپم رویِ *هر* پیامِ گروه چک
# می‌کنه، بدونِ این کش هر پیام یه درخواستِ شبکه‌ایِ جدید به تلگرام می‌زد.
_ADMIN_CACHE_TTL = 300  # ثانیه
_admin_cache: dict[tuple[int, int], tuple[bool, float]] = {}


async def _is_admin_or_creator(chat_id: int, user_id: int) -> bool:
    """
    نکته: قبلاً وقتی get_permissions fail می‌شد، تابع False ("ادمین نیست")
    برمی‌گردوند - که یعنی پیام حذف می‌شد؛ درحالی‌که کامنتِ خودِ کد می‌گفت هدف
    اینه که با عدمِ اطمینان، پیام حذف *نشه*. این‌جا درستش کردیم: روی خطا True
    ("برای احتیاط، ادمین فرض کن") برمی‌گردونه تا پیامِ یه ادمینِ واقعی به‌خاطرِ
    یه خطای موقتِ شبکه اشتباهی حذف نشه.
    """
    key = (chat_id, user_id)
    now = time.monotonic()
    cached = _admin_cache.get(key)
    if cached is not None and now - cached[1] < _ADMIN_CACHE_TTL:
        return cached[0]
    try:
        perms = await client.get_permissions(chat_id, user_id)
        is_admin = bool(getattr(perms, "is_admin", False) or getattr(perms, "is_creator", False))
    except Exception:
        is_admin = True  # اگه نتونستیم چک کنیم، برای احتیاط پیام رو حذف نمی‌کنیم
    _admin_cache[key] = (is_admin, now)
    return is_admin


# ---------------------------------------------------------------- فیلترلینک ---
@client.on(events.NewMessage(outgoing=True, pattern=pat(["فیلترلینک", "linkfilter"])))
async def linkfilter_cmd_handler(event):
    if not event.is_group:
        return await event.edit("این دستور فقط توی گروه‌ها کار می‌کنه")

    sub = (event.pattern_match.group(1) or "").strip().lower()

    if sub in ("روشن", "on"):
        await set_link_filter(event.chat_id, True)
        return await event.edit(
            "✅ فیلترلینک روشن شد.\n"
            "از این به بعد پیام‌های حاویِ لینک از طرفِ اعضای غیرادمینِ این گروه خودکار حذف می‌شن."
        )

    if sub in ("خاموش", "off"):
        await set_link_filter(event.chat_id, False)
        return await event.edit("❌ فیلترلینک این گروه خاموش شد")

    status = "روشن ✅" if is_link_filter_enabled(event.chat_id) else "خاموش ❌"
    await event.edit(
        "🔗 **فیلترلینک**\n"
        f"وضعیتِ این گروه: {status}\n\n"
        f"`{PREFIX}فیلترلینک روشن` / `{PREFIX}فیلترلینک خاموش`\n"
        "⚠️ فقط پیام‌های اعضای غیرادمین حذف می‌شن؛ خودتون و بقیه‌ی ادمین‌ها مستثنی‌اید."
    )


@client.on(events.NewMessage(incoming=True))
async def linkfilter_watcher(event):
    if not event.is_group:
        return
    if not is_link_filter_enabled(event.chat_id):
        return
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return
    text = event.raw_text or ""
    if not _LINK_RE.search(text):
        return
    if await _is_admin_or_creator(event.chat_id, sender_id):
        return
    try:
        await event.delete()
    except Exception:
        _record_error()
        logger.exception("خطا در حذف پیامِ لینک‌دار")


# ---------------------------------------------------------------- فیلترِ پورن ---
_PORN_FILTER_SYSTEM = (
    "شما یه فیلترِ محتوای بزرگسالان هستید. فقط بر اساسِ تصویرِ داده‌شده، دقیقاً "
    "با یکی از این دو کلمه جواب بده و هیچ چیزِ دیگه‌ای ننویس: "
    "NSFW اگه تصویر شاملِ نمایشِ صریحِ برهنگی/محتوای جنسی/پورنوگرافی باشه، "
    "یا SAFE در غیرِ این صورت."
)


async def _is_nsfw_image(raw: bytes) -> bool:
    """
    تصویر رو با همون سرویسِ AI که `.پرسش`/`.منشی` هم ازش استفاده می‌کنن تحلیل
    می‌کنه (پس AI_MODEL باید Vision داشته باشه - پیش‌فرضِ پروژه gpt-4o-mini
    این قابلیت رو داره). هر خطایی (AI غیرفعاله، مدل تصویر رو پشتیبانی
    نمی‌کنه، تایم‌اوت، ...) fail-open می‌شه: False برمی‌گردونه - ترجیح می‌دیم
    یه پورن رد بشه تا این‌که عکسِ سالمِ یه کاربر رو اشتباهی پاک کنیم.
    """
    b64 = base64.b64encode(raw).decode("ascii")
    messages = [
        {"role": "system", "content": _PORN_FILTER_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "این عکس رو بررسی کن."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        },
    ]
    try:
        answer = await ai.ask_ai(messages, max_tokens=5)
    except (ai.AIDisabledError, ai.AIRequestError):
        logger.debug("فیلترِ پورن: سرویسِ AI در دسترس نیست/خطا داد - fail-open")
        return False
    return "NSFW" in answer.upper()


@client.on(events.NewMessage(outgoing=True, pattern=pat(["فیلترپورن", "pornfilter"])))
async def pornfilter_cmd_handler(event):
    if not event.is_group:
        return await event.edit("این دستور فقط توی گروه‌ها کار می‌کنه")

    sub = (event.pattern_match.group(1) or "").strip().lower()

    if sub in ("روشن", "on"):
        if not config.AI_API_KEY:
            return await event.edit(
                "⚠️ فیلترِ پورن به AI_API_KEY نیاز داره (با یه مدلِ Vision-دار "
                "مثلِ gpt-4o یا gpt-4o-mini) - این متغیر رو تنظیم کن و دوباره امتحان کن. "
                "بدونِ این، این فیلتر عملاً هیچ عکسی رو چک نمی‌کنه."
            )
        await set_porn_filter(event.chat_id, True)
        return await event.edit(
            "✅ فیلترِ پورن روشن شد.\n"
            "از این به بعد عکسِ ارسالی از طرفِ اعضای غیرادمینِ این گروه با AI بررسی "
            "و در صورتِ تشخیصِ محتوای نامناسب حذف می‌شه.\n"
            "⚠️ فعلاً فقط عکسِ معمولی پوشش داده می‌شه؛ ویدیو/GIF/استیکر/فایل نه."
        )

    if sub in ("خاموش", "off"):
        await set_porn_filter(event.chat_id, False)
        return await event.edit("❌ فیلترِ پورنِ این گروه خاموش شد")

    status = "روشن ✅" if is_porn_filter_enabled(event.chat_id) else "خاموش ❌"
    ai_status = "آماده ✅" if config.AI_API_KEY else "AI_API_KEY تنظیم نشده ⚠️"
    await event.edit(
        "🔞 **فیلترِ پورن**\n"
        f"وضعیتِ این گروه: {status}\n"
        f"سرویسِ AI: {ai_status}\n\n"
        f"`{PREFIX}فیلترپورن روشن` / `{PREFIX}فیلترپورن خاموش`\n"
        "⚠️ فقط عکس‌های معمولی چک می‌شن (نه ویدیو/GIF/استیکر/فایل)؛ فقط پیام‌های اعضای غیرادمین حذف می‌شن.\n"
        "هر عکس یعنی یک درخواستِ AI - توی گروه‌های خیلی شلوغ ممکنه هزینه/تعدادِ درخواست بالا بره."
    )


@client.on(events.NewMessage(incoming=True))
async def pornfilter_watcher(event):
    if not event.is_group:
        return
    if not is_porn_filter_enabled(event.chat_id):
        return
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return
    if not event.photo:
        return  # فعلاً فقط عکسِ فشرده‌شده چک می‌شه (نه ویدیو/GIF/استیکر/فایل)
    if await _is_admin_or_creator(event.chat_id, sender_id):
        return

    file_size = getattr(event.message.file, "size", None) or 0
    if file_size and file_size > config.GROUP_PORN_FILTER_MAX_BYTES:
        return  # عکسِ خیلی بزرگ - برای جلوگیری از دانلودِ سنگین/کند رد می‌شیم

    try:
        raw = await client.download_media(event.message, bytes)
    except Exception:
        _record_error()
        logger.exception("خطا در دانلودِ عکس برای فیلترِ پورن")
        return
    if not raw:
        return

    if not await _is_nsfw_image(raw):
        return

    try:
        await event.delete()
    except Exception:
        _record_error()
        logger.exception("خطا در حذفِ عکسِ فیلترشده")


# --------------------------------------------------------------- خوش‌آمد ---
@client.on(events.NewMessage(outgoing=True, pattern=pat(["خوش‌آمد", "welcome"])))
async def welcome_cmd_handler(event):
    if not event.is_group:
        return await event.edit("این دستور فقط توی گروه‌ها کار می‌کنه")

    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if sub in ("روشن", "on"):
        await set_welcome_enabled(event.chat_id, True)
        return await event.edit("✅ خوش‌آمدگویی خودکار برای عضو جدیدِ این گروه روشن شد")

    if sub in ("خاموش", "off"):
        await set_welcome_enabled(event.chat_id, False)
        return await event.edit("❌ خوش‌آمدگویی خودکار این گروه خاموش شد")

    if sub in ("متن", "text"):
        text = rest
        if not text and event.is_reply:
            reply = await event.get_reply_message()
            text = reply.raw_text or ""
        if not text:
            return await event.edit(
                f"مثال: `{PREFIX}خوش‌آمد متن سلام {{نام}} خوش اومدی به گروه!`\n"
                "می‌تونی از `{نام}` (اسمِ کاربر) یا `{منشن}` (تگِ واقعی) داخلِ متن استفاده کنی."
            )
        await set_welcome_text(event.chat_id, text)
        return await event.edit("✅ متنِ خوش‌آمدگویی ذخیره شد")

    status = "روشن ✅" if is_welcome_enabled(event.chat_id) else "خاموش ❌"
    await event.edit(
        "👋 **خوش‌آمدگویی**\n"
        f"وضعیتِ این گروه: {status}\n"
        f"متنِ فعلی: {get_welcome_text(event.chat_id)}\n\n"
        f"`{PREFIX}خوش‌آمد روشن` / `{PREFIX}خوش‌آمد خاموش`\n"
        f"`{PREFIX}خوش‌آمد متن <متن>` — جای‌گذاری‌های مجاز: `{{نام}}`, `{{منشن}}`"
    )


@client.on(events.ChatAction)
async def welcome_watcher(event):
    if not (event.user_joined or event.user_added):
        return
    chat_id = event.chat_id
    if chat_id is None or not is_welcome_enabled(chat_id):
        return
    try:
        users = await event.get_users()
    except Exception:
        return
    if not users:
        return

    template = get_welcome_text(chat_id)
    for user in users:
        if getattr(user, "bot", False) or user.id == runtime.SELF_ID:
            continue
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (
            user.username or str(user.id)
        )
        mention = f"[{name}](tg://user?id={user.id})"
        text = template.replace("{نام}", name).replace("{name}", name)
        text = text.replace("{منشن}", mention).replace("{mention}", mention)
        try:
            await client.send_message(chat_id, text, parse_mode="markdown")
        except Exception:
            _record_error()
            logger.exception("خطا در ارسالِ پیامِ خوش‌آمدگویی")


# ------------------------------------------------------------ برچسب‌همه ---
@client.on(events.NewMessage(outgoing=True, pattern=pat(["برچسب‌همه", "tagall"])))
async def tagall_handler(event):
    if not event.is_group:
        return await event.edit("این دستور فقط توی گروه‌ها کار می‌کنه")

    custom_text = (event.pattern_match.group(1) or "").strip()

    try:
        participants = await client.get_participants(event.chat_id)
    except Exception as e:
        _record_error()
        logger.exception("خطا در گرفتنِ لیستِ اعضا")
        return await event.edit(f"❌ خطا در گرفتنِ لیستِ اعضا: {e}")

    members = [
        p
        for p in participants
        if not getattr(p, "bot", False) and not getattr(p, "deleted", False) and p.id != runtime.SELF_ID
    ]
    if not members:
        return await event.edit("عضوی برای تگ‌کردن پیدا نشد")

    if len(members) > _TAG_MAX_MEMBERS:
        return await event.edit(
            f"⚠️ این گروه {len(members)} عضو داره - برای کاهشِ ریسکِ اسپم/محدودیتِ اکانت "
            f"سقفِ این دستور {_TAG_MAX_MEMBERS} نفره. لطفاً توی گروه‌های کوچیک‌تر استفاده‌ش کن."
        )

    await event.edit(
        f"📣 در حالِ تگ‌کردنِ {len(members)} عضو، طیِ چند پیام با فاصله (برای جلوگیری از اسپم)..."
    )

    batches = [members[i : i + _TAG_BATCH_SIZE] for i in range(0, len(members), _TAG_BATCH_SIZE)]
    for batch in batches:
        mentions = " ".join(
            f"[{(m.first_name or m.username or str(m.id))}](tg://user?id={m.id})" for m in batch
        )
        body = f"{custom_text}\n{mentions}" if custom_text else mentions
        try:
            await client.send_message(event.chat_id, body, parse_mode="markdown")
        except Exception:
            _record_error()
            logger.exception("خطا در ارسالِ برچسب‌همه")
        await asyncio.sleep(_TAG_BATCH_DELAY)


# ---------------------------------------------------------------- فیلترِ اسپم ---
def _normalize_for_spam(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# (chat_id, sender_id) -> deque[(monotonic_ts, message_id, normalized_text)] -
# فقط درون‌حافظه‌ست (نیازی به ماندگاریِ بینِ ری‌استارت نداره، چون فقط برای
# تشخیصِ فلادِ *لحظه‌ای* استفاده می‌شه، نه تاریخچه‌ی بلندمدت).
_spam_tracker: dict[tuple[int, int], deque] = {}
# برای این‌که خودِ پیامِ هشدار سرِ هر فلاد اسپم نشه، بینِ دو هشدارِ پیاپی برای
# همون (گروه، فرستنده) این‌قدر صبر می‌کنیم.
_spam_last_warned: dict[tuple[int, int], float] = {}


@client.on(events.NewMessage(outgoing=True, pattern=pat(["فیلتراسپم", "spamfilter"])))
async def spamfilter_cmd_handler(event):
    if not event.is_group:
        return await event.edit("این دستور فقط توی گروه‌ها کار می‌کنه")

    sub = (event.pattern_match.group(1) or "").strip().lower()

    if sub in ("روشن", "on"):
        await set_spam_filter(event.chat_id, True)
        return await event.edit(
            "✅ فیلترِ اسپم روشن شد.\n"
            f"از این به بعد اگه یه عضوِ غیرادمین توی {config.GROUP_SPAM_WINDOW_SECONDS} ثانیه "
            f"بیشتر از {config.GROUP_SPAM_MAX_MESSAGES} پیام بفرسته (فلاد)، یا عینِ یه متن رو "
            f"{config.GROUP_SPAM_DUPLICATE_THRESHOLD} بار پشتِ‌سرِهم تکرار کنه، اون پیام‌ها "
            "خودکار حذف می‌شن."
        )

    if sub in ("خاموش", "off"):
        await set_spam_filter(event.chat_id, False)
        return await event.edit("❌ فیلترِ اسپمِ این گروه خاموش شد")

    status = "روشن ✅" if is_spam_filter_enabled(event.chat_id) else "خاموش ❌"
    await event.edit(
        "🚯 **فیلترِ اسپم**\n"
        f"وضعیتِ این گروه: {status}\n\n"
        f"`{PREFIX}فیلتراسپم روشن` / `{PREFIX}فیلتراسپم خاموش`\n"
        f"معیار: بیش از {config.GROUP_SPAM_MAX_MESSAGES} پیام در {config.GROUP_SPAM_WINDOW_SECONDS} ثانیه "
        f"(فلاد)، یا تکرارِ عینِ یه متن {config.GROUP_SPAM_DUPLICATE_THRESHOLD} بار پشتِ‌سرِهم.\n"
        "⚠️ فقط پیام‌های اعضای غیرادمین چک می‌شن؛ بدونِ نیاز به AI کار می‌کنه."
    )


@client.on(events.NewMessage(incoming=True))
async def spamfilter_watcher(event):
    if not event.is_group:
        return
    if not is_spam_filter_enabled(event.chat_id):
        return
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return
    if await _is_admin_or_creator(event.chat_id, sender_id):
        return

    key = (event.chat_id, sender_id)
    now = time.monotonic()
    dq = _spam_tracker.setdefault(key, deque(maxlen=50))

    # پاک‌کردنِ رکوردهای قدیمی‌تر از بازه‌ی زمانیِ موردنظر
    while dq and now - dq[0][0] > config.GROUP_SPAM_WINDOW_SECONDS:
        dq.popleft()

    text = _normalize_for_spam(event.raw_text)
    dq.append((now, event.id, text))

    flood = len(dq) > config.GROUP_SPAM_MAX_MESSAGES
    duplicate = bool(text) and sum(1 for _, _, t in dq if t == text) >= config.GROUP_SPAM_DUPLICATE_THRESHOLD
    if not (flood or duplicate):
        return

    if flood:
        # فلاده - کلِ بازه‌ی اخیرِ همین فرستنده مشکوکه، همه رو پاک می‌کنیم.
        ids_to_delete = [mid for _, mid, _ in dq]
        dq.clear()
    else:
        # فقط تکرارِ همون متنِ خاص رو پاک می‌کنیم؛ پیام‌های دیگه‌ی همین فرستنده
        # که توی بازه بودن ولی متنِ متفاوتی داشتن دست‌نخورده می‌مونن.
        ids_to_delete = [mid for _, mid, t in dq if t == text]
        remaining = [entry for entry in dq if entry[1] not in ids_to_delete]
        dq.clear()
        dq.extend(remaining)

    try:
        await client.delete_messages(event.chat_id, ids_to_delete)
    except Exception:
        _record_error()
        logger.exception("خطا در حذفِ پیام‌های اسپم")

    last_warned = _spam_last_warned.get(key, 0.0)
    if now - last_warned >= config.GROUP_SPAM_WARN_COOLDOWN_SECONDS:
        _spam_last_warned[key] = now
        reason = "فلادِ پیام" if flood else "تکرارِ پیام"
        try:
            await client.send_message(
                event.chat_id,
                f"🚯 اسپم ({reason}) از طرفِ [یه عضو](tg://user?id={sender_id}) شناسایی و پاک شد.",
                parse_mode="markdown",
            )
        except Exception:
            _record_error()
            logger.exception("خطا در ارسالِ هشدارِ اسپم")
