"""bot/local_speech.py

پیاده‌سازیِ رایگان و بدونِ‌نیاز-به-کلیدِ AIِ بخشِ 🔊 صوت‌ومتن، به‌جایِ
هسته‌ی OpenAI-محورِ bot/ai.py:

- رونویسی (Speech-to-Text): از موتورِ رایگانِ گوگل (کتابخونه‌ی
  SpeechRecognition، متدِ recognize_google) استفاده می‌کنه. بدون هیچ
  API keyی؛ فقط دسترسی به اینترنت لازمه. این یه endpointِ رسمی/تجاریِ
  گوگل نیست (همون سرویسِ رایگانی که خودِ کتابخونه ازش استفاده می‌کنه)،
  پس برای استفاده‌ی شخصی/حجمِ کم مناسبه، نه بارِ سنگین/تجاری.
- متن‌به‌صوت (Text-to-Speech): از edge-tts استفاده می‌کنه (همون موتورِ
  Read Aloud مرورگرِ Microsoft Edge) - رایگان و بدون کلید.

هر دو از ffmpeg (که توی Dockerfile نصب شده) برای تبدیلِ فرمتِ صوتی
استفاده می‌کنن.
"""
import asyncio
import os
import subprocess
import tempfile

import edge_tts
import speech_recognition as sr


class LocalSpeechError(RuntimeError):
    """خطای رونویسی/متن‌به‌صوتِ محلی (بدونِ ربط به AI_API_KEY)."""


def _convert_to_wav(raw: bytes, ext: str) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, f"in.{ext}")
        dst = os.path.join(td, "out.wav")
        with open(src, "wb") as f:
            f.write(raw)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
            capture_output=True, timeout=60,
        )
        if proc.returncode != 0 or not os.path.exists(dst):
            stderr_tail = proc.stderr.decode("utf-8", errors="ignore")[-300:]
            raise LocalSpeechError(f"تبدیلِ فرمتِ صوتی (ffmpeg) fail شد: {stderr_tail}")
        with open(dst, "rb") as f:
            return f.read()


def _recognize_sync(wav_bytes: bytes, language: str) -> str:
    recognizer = sr.Recognizer()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "audio.wav")
        with open(path, "wb") as f:
            f.write(wav_bytes)
        with sr.AudioFile(path) as source:
            audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError as e:
        raise LocalSpeechError("گفتار قابلِ‌تشخیص نبود (صدا نامفهوم/خیلی کوتاهه)") from e
    except sr.RequestError as e:
        raise LocalSpeechError(f"سرویسِ رایگانِ رونویسیِ گوگل جواب نداد: {e}") from e


async def transcribe_local(raw: bytes, *, ext: str = "ogg", language: str = "fa-IR") -> str:
    """رونویسیِ بایت‌های خامِ یه فایلِ صوتی به متن - رایگان، بدون AI_API_KEY."""
    wav_bytes = await asyncio.to_thread(_convert_to_wav, raw, ext)
    text = await asyncio.to_thread(_recognize_sync, wav_bytes, language)
    if not text or not text.strip():
        raise LocalSpeechError("متنِ رونویسی‌شده خالی بود")
    return text.strip()


async def synthesize_local(text: str, *, voice: str = "fa-IR-FaridNeural") -> bytes:
    """متن‌به‌صوت (خروجی mp3) - رایگان، بدون AI_API_KEY (از edge-tts)."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                chunks.extend(chunk["data"])
    except LocalSpeechError:
        raise
    except Exception as e:
        raise LocalSpeechError(f"سرویسِ رایگانِ متن‌به‌صوت (edge-tts) fail شد: {e}") from e
    if not chunks:
        raise LocalSpeechError("سرویسِ متن‌به‌صوت پاسخِ خالی برگردوند")
    return bytes(chunks)
