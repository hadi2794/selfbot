"""🔊 صوت و متن: رونویسی (Speech-to-Text) و متن‌به‌صوت (Text-to-Speech)

رونویسی و متن‌به‌صوت از bot/local_speech.py استفاده می‌کنن (رایگان و
بدونِ نیاز به AI_API_KEY: رونویسی از موتورِ رایگانِ گوگل، متن‌به‌صوت از
edge-tts). فقط ترکیبِ اختیاریِ «رونویسی + پرسش از هوشِ مصنوعی» (پایین‌تر)
هنوز از bot/ai.py (همون AI_API_KEY یِ `.پرسش`/`.خلاصه`) استفاده می‌کنه.

ترکیب با AI:
  - `.رونویسی` تنها → فقط متنِ پیامِ صوتیِ ریپلای‌شده رو برمی‌گردونه (بدون AI).
  - `.رونویسی <سوال/درخواست>` → اول رونویسی می‌کنه (بدون AI)، بعد همون متن رو
    به‌عنوانِ context به هسته‌ی AI می‌ده (دقیقاً الگویِ `.پرسش` روی متن) -
    این بخش نیازمندِ AI_API_KEY هست.
  - `.پرسش` (در bot/handlers/ai.py) و پاسخِ خودکارِ منشی (assistant.py) هم
    وقتی ریپلای/پیامِ ورودی صوتیه و متنِ مستقیم نداره، خودشون این ماژول رو
    برای رونویسیِ خودکار صدا می‌کنن - نیازی نیست کاربر دستی `.رونویسی` بزنه.
"""
import os
import shutil
import subprocess
import tempfile
from io import BytesIO

from telethon import events

from .. import ai, local_speech
from ..config import PREFIX
from ..runtime import client
from ..storage.stats_store import record_error as _record_error
from ..utils import pat

_SYSTEM_PROMPT = (
    "شما دستیاری هستید که پیام‌های فارسی/انگلیسیِ تلگرام رو خلاصه یا تحلیل "
    "می‌کنه و به سوالات پاسخ می‌ده. کوتاه، دقیق و بدون مقدمه‌چینیِ اضافه پاسخ بده."
)

_AI_DISABLED_MSG = (
    "⚠️ **قابلیتِ پرسیدنِ سوال از AI دربارهِ رونویسی غیرفعاله**\n"
    "(خودِ رونویسی نیاز به این نداره) برای فعال‌سازیِ این بخش، متغیرِ "
    "محیطیِ `AI_API_KEY` رو ست کن."
)


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def is_audio_message(msg) -> bool:
    """پیامِ ویس/صوتی/فایلِ صوتیه؟ - از ai.py و assistant.py هم استفاده می‌شه."""
    if not msg:
        return False
    if msg.voice or msg.audio:
        return True
    if msg.document and (msg.document.mime_type or "").startswith("audio/"):
        return True
    return False


def _guess_ext(msg) -> str:
    if msg.document:
        for attr in msg.document.attributes:
            name = getattr(attr, "file_name", None)
            if name and "." in name:
                return name.rsplit(".", 1)[-1].lower()
        mime = msg.document.mime_type or ""
        if "/" in mime:
            return mime.split("/")[-1].split(";")[0].lower()
    return "ogg"


async def transcribe_message(msg) -> str:
    """دانلود + رونویسیِ یه پیامِ صوتی؛ از ai.py/assistant.py هم صدا زده می‌شه."""
    raw = await client.download_media(msg, file=bytes)
    return await local_speech.transcribe_local(raw, ext=_guess_ext(msg))


# ----------------------------------------------------------------- رونویسی
@client.on(events.NewMessage(outgoing=True, pattern=pat(["رونویسی", "transcribe"])))
async def transcribe_handler(event):
    if not event.is_reply:
        return await event.edit(
            f"روی یه پیامِ صوتی/ویس ریپلای کن.\n"
            f"مثال: `{PREFIX}رونویسی` (فقط متن) یا "
            f"`{PREFIX}رونویسی خلاصه‌ش کن` (رونویسی + پرسش از AI)"
        )
    reply = await event.get_reply_message()
    if not is_audio_message(reply):
        return await event.edit("❌ پیامِ ریپلای‌شده صوتی نیست")

    followup = (event.pattern_match.group(1) or "").strip()

    msg = await event.edit("⏳ در حال رونویسی...")
    try:
        text = await transcribe_message(reply)
    except local_speech.LocalSpeechError as e:
        _record_error()
        return await msg.edit(f"❌ خطا در رونویسی: {e}")
    except Exception as e:
        _record_error()
        return await msg.edit(f"❌ خطا در رونویسی: {e}")

    if not followup:
        return await msg.edit(f"📝 **رونویسی:**\n\n{text}")

    # ترکیب با هسته‌ی AI: متنِ رونویسی‌شده به‌عنوانِ context به درخواستِ کاربر اضافه می‌شه.
    await msg.edit("📝 رونویسی شد؛ در حال پرسیدن از AI...")
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"متنِ زیر رونویسیِ یه پیامِ صوتیه:\n\n{text}\n\nدرخواست: {followup}",
        },
    ]
    try:
        answer = await ai.ask_ai(messages)
    except ai.AIDisabledError:
        return await msg.edit(f"📝 **رونویسی:**\n\n{text}")
    except ai.AIRequestError as e:
        _record_error()
        return await msg.edit(f"📝 **رونویسی:**\n\n{text}\n\n❌ خطا در پاسخِ AI: {e}")

    await msg.edit(f"📝 **رونویسی:**\n{text}\n\n🤖 **پاسخ:**\n{answer or '(پاسخِ خالی)'}")


# --------------------------------------------------------------- متن‌به‌صوت
@client.on(events.NewMessage(outgoing=True, pattern=pat(["متن‌به‌صوت", "tts"])))
async def tts_handler(event):
    text = (event.pattern_match.group(1) or "").strip()
    reply_to_id = None
    if event.is_reply:
        reply = await event.get_reply_message()
        reply_to_id = reply.id
        if not text:
            text = reply.raw_text or ""

    if not text:
        return await event.edit(
            f"مثال: `{PREFIX}متن‌به‌صوت سلام، حالت چطوره؟` (یا ریپلای روی یه پیامِ متنی)"
        )
    if len(text) > 4000:
        text = text[:4000]

    msg = await event.edit("⏳ در حال ساختِ صدا...")
    try:
        mp3_bytes = await local_speech.synthesize_local(text)
    except local_speech.LocalSpeechError as e:
        _record_error()
        return await msg.edit(f"❌ خطا در تبدیلِ متن‌به‌صوت: {e}")

    try:
        # اگه ffmpeg باشه، به ogg/opus تبدیل می‌کنیم تا به‌شکلِ پیامِ صوتیِ
        # واقعیِ تلگرام (نه فایلِ ضمیمه) نمایش داده بشه.
        if _has_ffmpeg():
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, "in.mp3")
                dst = os.path.join(td, "out.ogg")
                with open(src, "wb") as f:
                    f.write(mp3_bytes)
                proc = subprocess.run(
                    ["ffmpeg", "-y", "-i", src, "-c:a", "libopus", "-b:a", "48k", "-vn", dst],
                    capture_output=True, timeout=120,
                )
                if proc.returncode == 0 and os.path.exists(dst):
                    with open(dst, "rb") as f:
                        ogg_bytes = f.read()
                    bio = BytesIO(ogg_bytes)
                    bio.name = "voice.ogg"
                    await client.send_file(
                        event.chat_id, bio, voice_note=True, reply_to=reply_to_id,
                    )
                    return await msg.delete()

        # fallback: بدون ffmpeg، همون mp3 خام رو به‌شکلِ فایلِ صوتی می‌فرستیم
        bio = BytesIO(mp3_bytes)
        bio.name = "speech.mp3"
        await client.send_file(event.chat_id, bio, reply_to=reply_to_id)
        await msg.delete()
    except Exception as e:
        _record_error()
        await msg.edit(f"❌ خطا در ارسالِ فایلِ صوتی: {e}")
