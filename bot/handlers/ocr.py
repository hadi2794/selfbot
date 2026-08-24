"""🔤 استخراج متن از عکس (OCR)

پیش‌فرض از Tesseract (رایگان، محلی، بدونِ نیاز به AI_API_KEY - دقیقاً همون
فلسفه‌ی bot/local_speech.py برای رونویسیِ صوت) استفاده می‌کنه. برای متن‌های
دست‌نویس/زاویه‌دار/باکیفیتِ پایین که Tesseract روشون ضعیفه، آرگومانِ اختیاریِ
`ai` می‌تونی بدی تا به‌جاش از همون سرویسِ AI Vision که `.فیلترپورن` هم استفاده
می‌کنه (bot/ai.py، نیازمندِ AI_API_KEY با مدلِ Vision‌دار) استفاده بشه.

نصبِ Tesseract روی سیستم (نه فقط پکیجِ پایتون pytesseract) لازمه؛ توی
Dockerfile با tesseract-ocr + tesseract-ocr-fas + tesseract-ocr-eng اضافه
شده. اگه نصب نباشه، دستور یه پیامِ راهنما می‌ده (و اگه AI_API_KEY ست باشه،
پیشنهاد می‌ده به‌جاش از `ai` استفاده کنی).
"""
import asyncio
import base64
from io import BytesIO

from telethon import events

from .. import ai, config
from ..config import PREFIX
from ..runtime import client
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

_TELEGRAM_MAX = 4096

# نام‌های زبانِ Tesseract (بسته‌ی زبانِ نصب‌شده باید همین اسم‌ها رو داشته باشه)
_LANG_MAP = {
    "fa": "fas",
    "fas": "fas",
    "فارسی": "fas",
    "en": "eng",
    "eng": "eng",
    "انگلیسی": "eng",
}
_DEFAULT_LANG = "fas+eng"

_VISION_SYSTEM = (
    "شما یه ابزارِ OCR هستید. تمامِ متنِ قابلِ‌خوندنِ داخلِ عکس (فارسی یا "
    "انگلیسی یا هر زبانِ دیگه) رو دقیقاً همون‌طور که نوشته شده، خط‌به‌خط "
    "استخراج کن. فقط خودِ متن رو برگردون - بدون مقدمه، بدون توضیح، بدون "
    "علامت‌گذاریِ اضافه. اگه هیچ متنی توی عکس نیست، دقیقاً بنویس: NO_TEXT"
)


def _is_image_message(msg) -> bool:
    if msg.photo:
        return True
    if msg.document and (msg.document.mime_type or "").startswith("image/"):
        return True
    return False


def _run_tesseract(raw: bytes, lang: str) -> str:
    """بلاک‌کننده - باید توی thread جدا (asyncio.to_thread) صدا زده بشه."""
    import pytesseract
    from PIL import Image

    img = Image.open(BytesIO(raw))
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    return pytesseract.image_to_string(img, lang=lang)


async def _extract_local(raw: bytes, lang: str) -> str:
    return await asyncio.to_thread(_run_tesseract, raw, lang)


async def _extract_ai(raw: bytes) -> str:
    b64 = base64.b64encode(raw).decode("ascii")
    messages = [
        {"role": "system", "content": _VISION_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "متنِ داخلِ این عکس رو استخراج کن."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        },
    ]
    text = await ai.ask_ai(messages, max_tokens=1500)
    return "" if text.strip() == "NO_TEXT" else text


async def _send_result(event, reply, text: str, *, engine_label: str):
    text = (text or "").strip()
    if not text:
        return await event.edit(f"⚠️ هیچ متنی توی عکس پیدا نشد ({engine_label})")

    header = f"🔤 **متنِ استخراج‌شده** ({engine_label}):\n\n"
    chunk = header + text
    if len(chunk) <= _TELEGRAM_MAX:
        await event.edit(chunk)
        return

    # طولانی‌تر از سقفِ تلگرام - مثلِ راهنما، چندتکه می‌فرستیم
    await event.edit(header.strip())
    remaining = text
    while remaining:
        piece, remaining = remaining[:_TELEGRAM_MAX], remaining[_TELEGRAM_MAX:]
        await event.respond(piece)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["استخراج‌متن", "استخراج متن", "ocr", "متن‌عکس"])))
async def ocr_handler(event):
    if not event.is_reply:
        return await event.edit(
            f"روی یه عکس ریپلای کن.\n"
            f"مثال: `{PREFIX}استخراج‌متن` (پیش‌فرض: فارسی+انگلیسی، محلی/رایگان)\n"
            f"`{PREFIX}استخراج‌متن en` — فقط انگلیسی\n"
            f"`{PREFIX}استخراج‌متن ai` — با هوشِ مصنوعی (بهتر برای دست‌نویس/کیفیتِ پایین، نیازمندِ AI_API_KEY)"
        )
    reply = await event.get_reply_message()
    if not _is_image_message(reply):
        return await event.edit("❌ پیام ریپلای‌شده عکس نیست")

    arg = (event.pattern_match.group(1) or "").strip().lower()
    use_ai = arg in ("ai", "هوش", "هوش مصنوعی", "هوشمند")
    lang = _LANG_MAP.get(arg, _DEFAULT_LANG) if not use_ai else _DEFAULT_LANG

    msg = await event.edit("⏳ در حال استخراجِ متن از عکس...")
    try:
        raw = await client.download_media(reply, file=bytes)
    except Exception as e:
        _record_error()
        return await msg.edit(f"❌ خطا در دانلودِ عکس: {e}")

    if use_ai:
        try:
            text = await _extract_ai(raw)
        except ai.AIDisabledError:
            return await msg.edit(
                "⚠️ **قابلیتِ هوش مصنوعی غیرفعاله**\n"
                "برای فعال‌سازی، متغیرِ محیطیِ `AI_API_KEY` رو ست کن "
                f"(اختیاری: `AI_MODEL`/`AI_API_BASE`)، یا بدونِ آرگومان از استخراجِ محلی استفاده کن (`{PREFIX}استخراج‌متن`)."
            )
        except ai.AIRequestError as e:
            _record_error()
            return await msg.edit(f"❌ خطا در ارتباط با سرویسِ هوش مصنوعی: {e}")
        return await _send_result(event, reply, text, engine_label="AI Vision")

    try:
        text = await _extract_local(raw, lang)
    except ImportError:
        return await msg.edit(
            "❌ پکیجِ `pytesseract` نصب نیست. `pytesseract` رو به `requirements.txt` اضافه کن و دوباره دیپلوی کن."
        )
    except Exception as e:
        _record_error()
        msg_low = str(e).lower()
        if "tesseract is not installed" in msg_low or "not in your path" in msg_low:
            hint = (
                f"\nراهنمایی: چون `AI_API_KEY` ست شده، می‌تونی به‌جاش `{PREFIX}استخراج‌متن ai` رو امتحان کنی."
                if config.AI_API_KEY
                else ""
            )
            return await msg.edit(
                "❌ Tesseract روی سیستم نصب نیست (این جدا از پکیجِ پایتونیه - باینریِ خودِ tesseract-ocr لازمه)."
                + hint
            )
        return await msg.edit(f"❌ خطا در OCR: {e}")

    await _send_result(event, reply, text, engine_label=f"محلی/{lang}")
