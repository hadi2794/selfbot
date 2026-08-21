"""۱۶) هوش مصنوعی: `.پرسش` (سوال/خلاصه‌سازیِ یه پیام)، `.خلاصه` (خلاصه‌ی N
پیامِ آخرِ چت)، و `.ترجمه‌هوشمند` (ترجمه با مدلِ زبانی به‌جای سرویسِ ترجمه‌ی ساده)

همه‌ی این‌ها از هسته‌ی مشترکِ bot/ai.py (ask_ai) استفاده می‌کنن که یه wrapper
روی APIِ چت‌تکمیلیِ سازگار با OpenAI ه. برای فعال‌سازی باید متغیرِ محیطیِ
`AI_API_KEY` رو ست کنی (اختیاری: `AI_MODEL`/`AI_API_BASE` برای سرویس‌های
دیگه) - وگرنه این دستورات فقط یه پیامِ راهنما می‌دن و بقیه‌ی سلف‌بات عادی
کار می‌کنه.

نکته: `.منشی هوش‌مصنوعی روشن/خاموش` (توی bot/handlers/assistant.py تعریف
شده) باعث می‌شه پاسخِ خودکارِ منشی هم به‌جای متنِ ثابت، از همین هسته تولید
بشه - یعنی این قابلیت هم می‌تونه جدا (`.پرسش`/`.خلاصه`) استفاده بشه، هم به
منشی وصل بشه.

`.ترجمه‌هوشمند` جدا از `.ترجمه`ی معمولی (توی bot/handlers/tools.py، بدونِ
نیاز به AI_API_KEY) عمل می‌کنه: کندتره ولی چون از یه مدلِ زبانی استفاده
می‌کنه، جمله‌های پیچیده/محاوره‌ای/طولانی رو خیلی طبیعی‌تر و دقیق‌تر ترجمه
می‌کنه.
"""
from telethon import events

from .. import ai, config
from ..config import PREFIX
from ..runtime import client
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from . import audio

_SYSTEM_PROMPT = (
    "شما دستیاری هستید که پیام‌های فارسی/انگلیسیِ تلگرام رو خلاصه یا تحلیل "
    "می‌کنه و به سوالات پاسخ می‌ده. کوتاه، دقیق و بدون مقدمه‌چینیِ اضافه پاسخ بده."
)


async def _ask_and_reply(event, messages, *, thinking_text="🤔 در حال فکر کردن..."):
    await event.edit(thinking_text)
    try:
        answer = await ai.ask_ai(messages)
    except ai.AIDisabledError:
        return await event.edit(
            "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
            "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن "
            "(اختیاری: `AI_MODEL`/`AI_API_BASE` برای سرویس‌های دیگه)."
        )
    except ai.AIRequestError as e:
        _record_error()
        return await event.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")
    if not answer:
        return await event.edit("⚠️ مدل پاسخِ خالی برگردوند")
    await event.edit(f"🤖 {answer}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پرسش", "ask"])))
async def ask_handler(event):
    question = (event.pattern_match.group(1) or "").strip()
    context_text = None

    if event.is_reply:
        reply = await event.get_reply_message()
        context_text = reply.raw_text or ""
        if not context_text and audio.is_audio_message(reply):
            # ریپلای‌شده صوتیه و متنِ مستقیم نداره؛ خودکار رونویسی می‌کنیم
            # تا `.پرسش`/`.پرسش <سوال>` روی پیامِ صوتی هم کار کنه.
            await event.edit("⏳ در حال رونویسیِ پیامِ صوتی...")
            try:
                context_text = await audio.transcribe_message(reply)
            except ai.AIDisabledError:
                return await event.edit(
                    "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
                    "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن."
                )
            except ai.AIRequestError as e:
                _record_error()
                return await event.edit(f"❌ خطا در رونویسیِ پیامِ صوتی: {e}")

    if not question and not context_text:
        return await event.edit(
            f"مثال: `{PREFIX}پرسش پایتخت فرانسه کجاست؟`\n"
            f"با ریپلای روی یه پیام (متنی یا صوتی): `{PREFIX}پرسش` برای خلاصه/تحلیلِ همون پیام، "
            f"یا `{PREFIX}پرسش این پیام چی میگه؟` برای سوال درباره‌ش."
        )

    if context_text and question:
        user_content = f"متنِ زیر رو در نظر بگیر:\n\n{context_text}\n\nسوال: {question}"
    elif context_text:
        user_content = f"متنِ زیر رو خلاصه/تحلیل کن:\n\n{context_text}"
    else:
        user_content = question

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    await _ask_and_reply(event, messages)


_SUMMARY_DEFAULT_MESSAGES = 50


@client.on(events.NewMessage(outgoing=True, pattern=pat(["خلاصه", "summarize"])))
async def summarize_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    count = _SUMMARY_DEFAULT_MESSAGES
    if arg:
        if not arg.isdigit():
            return await event.edit(
                f"مثال: `{PREFIX}خلاصه 50` (تعدادِ پیام‌های آخرِ همین چت برای خلاصه‌سازی)"
            )
        count = max(1, min(int(arg), config.AI_SUMMARY_MAX_MESSAGES))

    await event.edit(f"📥 در حالِ جمع‌آوریِ {count} پیامِ آخر...")
    try:
        msgs = await client.get_messages(event.chat_id, limit=count)
    except Exception as e:
        _record_error()
        return await event.edit(f"❌ خطا در دریافتِ پیام‌ها: {e}")

    lines = []
    for m in reversed(msgs):
        if not m.raw_text:
            continue
        sender = m.sender
        name = (
            getattr(sender, "first_name", None)
            or getattr(sender, "title", None)
            or getattr(sender, "username", None)
            or "؟"
        )
        lines.append(f"{name}: {m.raw_text}")

    if not lines:
        return await event.edit("پیامِ متنیِ قابل‌خلاصه‌سازی‌ای پیدا نشد")

    transcript = "\n".join(lines)
    # سقفِ تقریبیِ کاراکتر برای جلوگیری از ارسالِ حجمِ خیلی زیاد به مدل (هزینه/تایم‌اوت)
    if len(transcript) > 12000:
        transcript = transcript[-12000:]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "این‌ها آخرین پیام‌های یه گروه/چتِ تلگرام هستن (فرمتِ هر خط: "
                "`فرستنده: متن`). یه خلاصه‌ی کوتاه و مرتب از موضوعاتِ اصلیِ بحث بده:\n\n"
                + transcript
            ),
        },
    ]
    await _ask_and_reply(
        event, messages, thinking_text=f"🤔 در حالِ خلاصه‌سازیِ {len(lines)} پیام..."
    )


_TRANSLATE_SYSTEM = (
    "شما یه مترجمِ حرفه‌ای هستید. متنِ کاربر رو دقیق، طبیعی و روان به زبانِ "
    "مقصدی که کاربر مشخص کرده ترجمه کن. فقط و فقط خودِ ترجمه رو برگردون - "
    "بدون توضیح، بدون گیومه، بدون مقدمه‌چینی، بدون ذکرِ زبانِ مبدأ/مقصد."
)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["ترجمه‌هوشمند", "aitr"])))
async def ai_translate_handler(event):
    """
    ترجمه با مدلِ زبانی (جدا از `.ترجمه`ی معمولی در tools.py). کندتره و
    نیازمندِ AI_API_KEY هست، ولی برای متن‌های محاوره‌ای/پیچیده/طولانی
    کیفیتِ خیلی بهتری می‌ده.
    """
    args = (event.pattern_match.group(1) or "").strip()
    lang, text = None, None
    if args and " " in args:
        lang, text = args.split(" ", 1)
    elif args and event.is_reply:
        lang = args.strip()
        reply = await event.get_reply_message()
        text = reply.raw_text or ""
        if not text and audio.is_audio_message(reply):
            await event.edit("⏳ در حال رونویسیِ پیامِ صوتی...")
            try:
                text = await audio.transcribe_message(reply)
            except ai.AIDisabledError:
                return await event.edit(
                    "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
                    "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن."
                )
            except ai.AIRequestError as e:
                _record_error()
                return await event.edit(f"❌ خطا در رونویسیِ پیامِ صوتی: {e}")

    if not lang or not text:
        return await event.edit(
            f"مثال: `{PREFIX}ترجمه‌هوشمند en سلام دنیا` یا با ریپلای (متنی یا صوتی): `{PREFIX}ترجمه‌هوشمند en`"
        )

    messages = [
        {"role": "system", "content": _TRANSLATE_SYSTEM},
        {"role": "user", "content": f"به زبانِ «{lang}» ترجمه کن:\n\n{text}"},
    ]

    await event.edit(f"🤔 در حال ترجمه به {lang}...")
    try:
        answer = await ai.ask_ai(messages)
    except ai.AIDisabledError:
        return await event.edit(
            "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
            "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن "
            "(اختیاری: `AI_MODEL`/`AI_API_BASE` برای سرویس‌های دیگه).\n"
            f"برای ترجمه‌ی معمولی (بدون نیاز به AI) از `{PREFIX}ترجمه` استفاده کن."
        )
    except ai.AIRequestError as e:
        _record_error()
        return await event.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")
    if not answer:
        return await event.edit("⚠️ مدل پاسخِ خالی برگردوند")
    await event.edit(f"🌐🤖 ترجمه‌ی هوشمند ({lang}):\n{answer}")
