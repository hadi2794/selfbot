"""۸) منشی چت: پاسخ خودکار هوشمند با تشخیص آنلاین/آفلاین"""
import asyncio
import logging
from datetime import datetime, timezone

from telethon import events, functions

from .. import ai, config, runtime
from ..config import PREFIX
from ..runtime import client
from ..storage.assistant_store import assistant_state, save_assistant
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from . import audio

logger = logging.getLogger("selfbot.handlers.assistant")

_ASSISTANT_MODE_FA = {
    "auto": "خودکار (همه‌جا)",
    "mention": "فقط با منشن/ریپلای",
    "pm": "فقط پیوی",
    "groups": "فقط گروه‌ها",
}

# ورودیِ کاربر برای «حالت پاسخ» -> کلید داخلیِ همیشگی (auto/mention/pm/groups).
# هم نسخه‌ی فارسی و هم انگلیسیِ قدیمی رو قبول می‌کنه.
_ASSISTANT_MODE_ALIASES = {
    "خودکار": "auto", "auto": "auto",
    "منشن": "mention", "mention": "mention",
    "پیوی": "pm", "pm": "pm",
    "گروه‌ها": "groups", "گروهها": "groups", "groups": "groups",
}


def _assistant_status_text():
    status = "روشن ✅" if assistant_state["enabled"] else "خاموش ❌"
    mode_fa = _ASSISTANT_MODE_FA.get(assistant_state["mode"], assistant_state["mode"])
    if assistant_state["auto_detect"]:
        control_line = f"خودکار (بر اساس آنلاین/آفلاین‌بودنت، هر {config.ASSISTANT_CHECK_INTERVAL} ثانیه چک می‌شه)"
        footer = (
            f"با `{PREFIX}منشی روشن` یا `{PREFIX}منشی خاموش` می‌تونی دستی قفلش کنی "
            "(از اون به بعد حتی اگه آنلاین/آفلاین بشی، تشخیص خودکار دیگه دست بهش نمی‌زنه)."
        )
    else:
        control_line = "دستی 🔒 (قفل‌شده - تشخیص آنلاین/آفلاین روش تاثیری نداره)"
        footer = f"برای برگردوندن به تشخیص خودکار: `{PREFIX}منشی خودکار`"
    return (
        "🤖 **منشی چت**\n\n"
        f"• وضعیت: {status}\n"
        f"• کنترل: {control_line}\n"
        f"• حالت پاسخ: {mode_fa}\n"
        f"• تأخیر پاسخ: {assistant_state['delay']} ثانیه\n"
        f"• منبعِ پاسخ: {'هوش مصنوعی 🤖' if assistant_state['ai_mode'] else 'متنِ ثابت'}\n"
        f"• محدودیتِ پاسخ: "
        f"{'بدون محدودیت - به همه‌ی پیام‌ها جواب می‌ده' if assistant_state['ai_mode'] else 'فقط یک‌بار به هر نفر در هر نشست'}\n"
        f"• متن ثابت (fallback): {assistant_state['text'] or '(تنظیم نشده)'}\n"
        f"• چت‌های مستثنی: {len(assistant_state['exclude'])}\n"
        f"• چت‌های همیشه‌فعال: {len(assistant_state['include'])}\n\n"
        f"{footer}"
    )


def _assistant_should_respond(event):
    if event.is_channel and not event.is_group:
        return False  # کانال‌های برادکست رو نادیده بگیر
    chat_id = event.chat_id
    if chat_id in assistant_state["exclude"]:
        return False
    if chat_id in assistant_state["include"]:
        return True
    mode = assistant_state["mode"]
    if mode == "auto":
        return True
    if mode == "pm":
        return event.is_private
    if mode == "groups":
        return event.is_group
    if mode == "mention":
        if event.is_private:
            return True
        return bool(getattr(event.message, "mentioned", False))
    return False


@client.on(events.NewMessage(outgoing=True, pattern=pat(["منشی", "assistant"])))
async def assistant_handler(event):
    raw = (event.pattern_match.group(1) or "").strip()
    parts = raw.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not sub or sub in ("وضعیت", "status"):
        return await event.edit(_assistant_status_text())

    if sub in ("روشن", "on"):
        assistant_state["enabled"] = True
        assistant_state["auto_detect"] = False  # قفل دستی - تشخیص خودکار دیگه دست بهش نمی‌زنه
        assistant_state["replied"] = set()
        await save_assistant()
        return await event.edit(_assistant_status_text())

    if sub in ("خاموش", "off"):
        assistant_state["enabled"] = False
        assistant_state["auto_detect"] = False  # قفل دستی - حتی اگه آفلاین بشی خاموش می‌مونه
        await save_assistant()
        return await event.edit(_assistant_status_text())

    if sub in ("خودکار", "auto"):
        assistant_state["auto_detect"] = True
        await save_assistant()
        return await event.edit(
            "✅ تشخیص خودکار آنلاین/آفلاین دوباره فعال شد.\n"
            "از این به بعد روشن/خاموش‌بودن منشی خودش بر اساس آنلاین/آفلاین‌بودنت مدیریت می‌شه."
        )

    if sub in ("متن", "text"):
        text = rest
        if not text and event.is_reply:
            reply = await event.get_reply_message()
            text = reply.raw_text or ""
        if not text:
            return await event.edit(f"مثال: `{PREFIX}منشی متن سلام، فعلاً آنلاین نیستم`")
        assistant_state["text"] = text
        await save_assistant()
        return await event.edit("✅ متن پاسخ ذخیره شد")

    if sub in ("تأخیر", "تاخیر", "delay"):
        if not rest.strip().isdigit():
            return await event.edit(f"مثال: `{PREFIX}منشی تأخیر 3`")
        assistant_state["delay"] = max(int(rest.strip()), 0)
        await save_assistant()
        return await event.edit(f"✅ تأخیر روی {assistant_state['delay']} ثانیه تنظیم شد")

    if sub in ("حالت", "mode"):
        m_raw = rest.strip().lower()
        m = _ASSISTANT_MODE_ALIASES.get(m_raw)
        if not m:
            return await event.edit(f"مثال: `{PREFIX}منشی حالت خودکار` (خودکار/منشن/پیوی/گروه‌ها)")
        assistant_state["mode"] = m
        await save_assistant()
        warn = ""
        if m == "auto":
            warn = (
                "\n⚠️ توجه: توی این حالت به همه‌ی پیام‌های هر چتی (حتی بدون تگ/ریپلای) "
                "جواب می‌ده - توی گروه‌های شلوغ ممکنه شبیه اسپم به‌نظر برسه."
            )
        return await event.edit(f"✅ حالت روی `{_ASSISTANT_MODE_FA[m]}` تنظیم شد{warn}")

    if sub in ("هوش‌مصنوعی", "هوشمصنوعی", "ai"):
        opt = rest.strip().lower()
        if opt in ("روشن", "on"):
            assistant_state["ai_mode"] = True
            await save_assistant()
            return await event.edit(
                "✅ پاسخِ خودکارِ منشی از این به بعد به‌جای متنِ ثابت، با هوش مصنوعی تولید می‌شه.\n"
                "⚠️ توی این حالت به **همه‌ی** پیام‌ها جواب می‌ده (نه فقط یک‌بار به هر نفر) - "
                "توی چت‌های شلوغ ممکنه هزینه/تعدادِ درخواستِ زیادی به سرویسِ AI بزنه.\n"
                "⚠️ نیازمندِ `AI_API_KEY` ست‌شده‌ست؛ اگه ست نباشه یا خطا بده، خودکار به متنِ ثابتِ فعلی fallback می‌کنه."
            )
        if opt in ("خاموش", "off"):
            assistant_state["ai_mode"] = False
            await save_assistant()
            return await event.edit("❌ پاسخِ منشی دوباره فقط از متنِ ثابت استفاده می‌کنه (یک‌بار به هر نفر)")
        status = "روشن ✅" if assistant_state["ai_mode"] else "خاموش ❌"
        return await event.edit(
            f"🤖 وضعیتِ پاسخِ هوش‌مصنوعیِ منشی: {status}\n\n"
            f"`{PREFIX}منشی هوش‌مصنوعی روشن` / `{PREFIX}منشی هوش‌مصنوعی خاموش`\n"
            "توی این حالت به همه‌ی پیام‌ها جواب می‌ده (نه فقط یک‌بار به هر نفر).\n"
            "برای سوال/خلاصه‌سازیِ دستی (جدا از منشی) هم می‌تونی از "
            f"`{PREFIX}پرسش` و `{PREFIX}خلاصه` استفاده کنی."
        )

    if sub in ("مستثنی", "exclude"):
        assistant_state["exclude"].add(event.chat_id)
        assistant_state["include"].discard(event.chat_id)
        await save_assistant()
        return await event.edit("🚫 این چت مستثنی شد (منشی اینجا پاسخ نمی‌ده)")

    if sub in ("شامل", "include"):
        assistant_state["include"].add(event.chat_id)
        assistant_state["exclude"].discard(event.chat_id)
        await save_assistant()
        return await event.edit("✅ این چت به لیست همیشه‌فعال اضافه شد")

    if sub in ("پاک", "clear"):
        assistant_state["include"].clear()
        assistant_state["exclude"].clear()
        await save_assistant()
        return await event.edit("🗑 لیست مستثنی/شامل پاک شد")

    await event.edit(f"دستور نامعتبره. برای وضعیت کامل: `{PREFIX}منشی`")


_ASSISTANT_AI_SYSTEM = (
    "شما دستیارِ شخصیِ صاحبِ این اکانتِ تلگرام هستید و دارید وقتی صاحبِ اکانت "
    "آفلاین/مشغوله به‌جاش به پیام‌ها پاسخِ کوتاه و مؤدبانه می‌دید. پاسخ رو خیلی "
    "کوتاه (حداکثر ۲-۳ جمله) و به همون زبانِ پیامِ ورودی بده، بدون مقدمه‌چینی."
)

# اسپویلرِ تلگرامی (سینتکسِ ||...||): تا لمس نشه به‌صورتِ یه تکه‌ی کوچیکِ محو/تار
# نمایش داده می‌شه، پس ظاهرِ کلیِ پیام رو خراب نمی‌کنه - ولی هرکسی که بخواد
# بفهمه این پاسخ از هوش مصنوعی بوده، کافیه لمسش کنه تا آشکار بشه.
_AI_WATERMARK = "||🤖||"


@client.on(events.NewMessage(incoming=True))
async def assistant_autoreply(event):
    if not assistant_state["enabled"]:
        return
    if not assistant_state["ai_mode"] and not assistant_state["text"]:
        return
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return
    if not _assistant_should_respond(event):
        return

    key = (event.chat_id, sender_id)
    if not assistant_state["ai_mode"]:
        # حالتِ متنِ ثابت: فقط یک‌بار به هر نفر توی هر نشست، تا اسپم نشه.
        if key in assistant_state["replied"]:
            return
        assistant_state["replied"].add(key)
    # حالتِ هوش‌مصنوعی: هیچ محدودیتی نداره - به تک‌تکِ پیام‌ها جواب می‌ده،
    # چون هر جواب بر اساسِ همون پیامِ مشخص تولید می‌شه (نه یه متنِ تکراری).

    try:
        delay = assistant_state["delay"]
        if delay > 0:
            async with client.action(event.chat_id, "typing"):
                await asyncio.sleep(delay)

        reply_text = assistant_state["text"]
        if assistant_state["ai_mode"]:
            try:
                incoming_text = event.raw_text or ""
                if not incoming_text and audio.is_audio_message(event.message):
                    # پیامِ ورودی صوتیه؛ قبل از دادن به AI خودمون رونویسی می‌کنیم.
                    try:
                        incoming_text = await audio.transcribe_message(event.message)
                    except (ai.AIDisabledError, ai.AIRequestError):
                        incoming_text = ""
                incoming_text = incoming_text or "(بدون متن)"
                messages = [
                    {"role": "system", "content": _ASSISTANT_AI_SYSTEM},
                    {"role": "user", "content": incoming_text},
                ]
                ai_answer = await ai.ask_ai(messages, max_tokens=300)
                if ai_answer:
                    reply_text = f"{ai_answer}\n{_AI_WATERMARK}"
            except (ai.AIDisabledError, ai.AIRequestError):
                _record_error()
                logger.exception("خطا در پاسخِ هوش‌مصنوعیِ منشی - fallback به متنِ ثابت")

        if not reply_text:
            return  # نه متنِ ثابتی هست، نه AI جواب داد
        await event.reply(reply_text)
    except Exception:
        _record_error()
        logger.exception("خطا در پاسخ خودکار منشی")


async def assistant_status_watcher():
    """
    هر چند ثانیه یک‌بار (ASSISTANT_CHECK_INTERVAL) لیست سشن‌های فعال اکانت رو
    از تلگرام می‌گیره. اگه سشنی غیر از همین اسکریپت (مثلاً گوشی خودت) به‌تازگی
    فعال بوده باشه، یعنی خودت آنلاینی -> منشی خاموش می‌شه. اگه هیچ سشن دیگه‌ای
    به‌تازگی فعال نبوده -> یعنی آفلاینی -> منشی خودش روشن می‌شه.

    اگه با .assistant on یا .assistant off دستی قفلش کرده باشی (auto_detect
    خاموش)، این تابع اصلاً دست به enabled نمی‌زنه - حتی اگه آفلاین بشی.
    """
    from .. import health
    while True:
        if not assistant_state["auto_detect"]:
            health.update_worker_status("assistant", "ok")
            await asyncio.sleep(config.ASSISTANT_CHECK_INTERVAL)
            continue
        try:
            result = await client(functions.account.GetAuthorizationsRequest())
            others = [a for a in result.authorizations if not a.current]
            if others:
                last_active = max(a.date_active for a in others)
                seconds_since = (datetime.now(timezone.utc) - last_active).total_seconds()
                online_elsewhere = seconds_since < config.ASSISTANT_ONLINE_THRESHOLD
            else:
                online_elsewhere = False  # هیچ سشن دیگه‌ای وصل نیست

            new_enabled = not online_elsewhere
            if new_enabled != assistant_state["enabled"]:
                if new_enabled:
                    assistant_state["replied"] = set()  # نشست تازه = دوباره به همه جواب بده
                assistant_state["enabled"] = new_enabled
            health.update_worker_status("assistant", "ok")
        except Exception as e:
            _record_error()
            logger.exception("خطا در بررسی وضعیت آنلاین/آفلاین")
            health.update_worker_status("assistant", "error", str(e))
        await asyncio.sleep(config.ASSISTANT_CHECK_INTERVAL)
