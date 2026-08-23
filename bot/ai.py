"""
هسته‌ی هوش مصنوعی: یه wrapper سبک روی APIِ چت‌تکمیلیِ سازگار با OpenAI
(خودِ OpenAI، یا هر سرویسِ دیگه‌ای مثل OpenRouter که همون فرمتِ
`/chat/completions` رو پیاده کنه - با AI_API_BASE می‌تونی به هر endpoint
سازگاری هدایتش کنی).

استفاده‌کننده‌ها (bot/handlers/ai.py برای `.پرسش`/`.خلاصه`، و اختیاری
bot/handlers/assistant.py برای پاسخِ خودکارِ هوشمند) فقط باید ask_ai() رو
صدا بزنن و AIDisabledError/AIRequestError رو مدیریت کنن - این ماژول هیچ
وابستگی‌ای به Telethon/event نداره.
"""
import json

import aiohttp

from . import config
from .runtime import get_http_session


class AIDisabledError(RuntimeError):
    """AI_API_KEY تنظیم نشده - قابلیت غیرفعاله."""


class AIRequestError(RuntimeError):
    """درخواست به سرویسِ هوش مصنوعی fail شد (شبکه/تایم‌اوت/پاسخِ نامعتبر/خطای API)."""


def _parse_json_body(text: str):
    """
    بعضی providerها (مثلاً OpenRouter، مخصوصاً روی مدل‌های کندتر) بعد از
    JSON اصلی یه سری بایتِ اضافه/کامنتِ keep-alive (برای زنده نگه‌داشتنِ
    کانکشن) هم توی بدنه‌ی پاسخ می‌فرستن؛ json.loads معمولی روی این حالت
    خطای "Extra data" می‌ده. اینجا فقط اولین JSON معتبرِ ابتدای متن رو
    parse می‌کنیم و بقیه‌ی متن رو نادیده می‌گیریم.
    """
    text = text.strip()
    if not text:
        raise AIRequestError("پاسخِ خالی از سرویسِ هوش مصنوعی")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        return obj
    except json.JSONDecodeError as e:
        raise AIRequestError(f"پاسخِ نامعتبر (JSON) از سرویسِ هوش مصنوعی: {e}") from e


async def ask_ai(messages: list[dict], *, max_tokens: int | None = None, return_raw: bool = False):
    """
    messages: لیستِ استانداردِ OpenAI chat messages (هرکدوم {"role": ..., "content": ...}).
    خروجی: متنِ پاسخِ مدل (str) - مگر این‌که return_raw=True باشه، که کلِ
    دیکشنریِ JSONِ پاسخ (خام) برگردونده می‌شه. این برای مواقعیه که فقط متنِ
    content کافی نیست و لازمه finish_reason هم دیده بشه (مثلاً برای
    عیب‌یابیِ این‌که چرا content خالی برگشته: تمومِ max_tokens شده؟ فیلترِ
    محتوای خودِ سرویس زده؟ یا واقعاً یه پاسخِ عادیِ خالیه؟).
    """
    if not config.AI_API_KEY:
        raise AIDisabledError(
            "متغیر محیطیِ AI_API_KEY تنظیم نشده - این قابلیت غیرفعاله."
        )

    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=config.AI_TIMEOUT)
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "max_tokens": max_tokens or config.AI_MAX_TOKENS,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {config.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    url = config.AI_API_BASE.rstrip("/") + "/chat/completions"

    try:
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as r:
            raw_text = await r.text()
            data = _parse_json_body(raw_text)
            if r.status != 200:
                err = None
                if isinstance(data, dict):
                    err = (data.get("error") or {}).get("message")
                raise AIRequestError(err or f"HTTP {r.status}")
    except AIRequestError:
        raise
    except Exception as e:
        raise AIRequestError(str(e)) from e

    if return_raw:
        return data

    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        raise AIRequestError("پاسخِ نامعتبر از سرویسِ هوش مصنوعی") from e


async def transcribe_audio(raw: bytes, *, filename: str = "audio.ogg") -> str:
    """
    Speech-to-Text: بایت‌های خامِ یه فایلِ صوتی رو می‌گیره و متنِ رونویسی‌شده
    (str) برمی‌گردونه. از endpointِ استانداردِ OpenAI (`/audio/transcriptions`،
    مدل پیش‌فرض whisper-1) استفاده می‌کنه.
    """
    if not config.AI_AUDIO_API_KEY:
        raise AIDisabledError(
            "متغیر محیطیِ AI_API_KEY (یا AI_AUDIO_API_KEY) تنظیم نشده - این قابلیت غیرفعاله."
        )

    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=config.AI_TIMEOUT)
    form = aiohttp.FormData()
    form.add_field("model", config.AI_STT_MODEL)
    form.add_field("file", raw, filename=filename, content_type="application/octet-stream")
    headers = {"Authorization": f"Bearer {config.AI_AUDIO_API_KEY}"}
    url = config.AI_AUDIO_API_BASE.rstrip("/") + "/audio/transcriptions"

    try:
        async with session.post(url, data=form, headers=headers, timeout=timeout) as r:
            raw_text = await r.text()
            data = _parse_json_body(raw_text)
            if r.status != 200:
                err = None
                if isinstance(data, dict):
                    err = (data.get("error") or {}).get("message")
                raise AIRequestError(err or f"HTTP {r.status}")
    except AIRequestError:
        raise
    except Exception as e:
        raise AIRequestError(str(e)) from e

    text = data.get("text") if isinstance(data, dict) else None
    if not text or not text.strip():
        raise AIRequestError("سرویسِ رونویسی متنِ خالی برگردوند")
    return text.strip()


async def synthesize_speech(text: str, *, voice: str | None = None) -> bytes:
    """
    Text-to-Speech: یه متن می‌گیره و بایت‌های خامِ صدا (معمولاً mp3) رو
    برمی‌گردونه. از endpointِ استانداردِ OpenAI (`/audio/speech`، مدل
    پیش‌فرض tts-1) استفاده می‌کنه.
    """
    if not config.AI_AUDIO_API_KEY:
        raise AIDisabledError(
            "متغیر محیطیِ AI_API_KEY (یا AI_AUDIO_API_KEY) تنظیم نشده - این قابلیت غیرفعاله."
        )

    session = await get_http_session()
    timeout = aiohttp.ClientTimeout(total=config.AI_TTS_TIMEOUT)
    payload = {
        "model": config.AI_TTS_MODEL,
        "voice": voice or config.AI_TTS_VOICE,
        "input": text,
    }
    headers = {
        "Authorization": f"Bearer {config.AI_AUDIO_API_KEY}",
        "Content-Type": "application/json",
    }
    url = config.AI_AUDIO_API_BASE.rstrip("/") + "/audio/speech"

    try:
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as r:
            body = await r.read()
            if r.status != 200:
                err = None
                try:
                    data = _parse_json_body(body.decode("utf-8", errors="ignore"))
                    if isinstance(data, dict):
                        err = (data.get("error") or {}).get("message")
                except AIRequestError:
                    pass
                raise AIRequestError(err or f"HTTP {r.status}")
    except AIRequestError:
        raise
    except Exception as e:
        raise AIRequestError(str(e)) from e

    if not body:
        raise AIRequestError("سرویسِ متن‌به‌صوت پاسخِ خالی برگردوند")
    return body
