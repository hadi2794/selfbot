"""
۱۵) مدیریت گروه پیشرفته: فیلترلینک / خوش‌آمدگویی / برچسب‌همه

  - `.فیلترلینک روشن/خاموش/وضعیت`  → حذف خودکار پیام‌های حاویِ لینک از
    اعضای غیرادمینِ همین گروه (چک ادمین‌بودن با client.get_permissions، پس
    خودِ ادمین‌ها و owner همیشه مستثنی‌ان).
  - `.خوش‌آمد روشن/خاموش/وضعیت/متن <متن>`  → پیامِ خوش‌آمدگویی خودکار برای
    عضو جدیدِ همین گروه. توی متن می‌شه از `{نام}` (اسمِ کاربر) یا `{منشن}`
    (تگِ واقعیِ کاربر) استفاده کرد.
  - `.برچسب‌همه <متن اختیاری>`  → با یه دستور همه‌ی اعضای گروه رو تگ می‌زنه؛
    برای کاهشِ ریسکِ اسپم/فلاد، در batchهای چندتایی با فاصله ارسال می‌شه و
    سقفِ تعداد عضو داره - این ویژگی رو با احتیاط و کم استفاده کن.

هر دو تنظیمِ فیلترلینک/خوش‌آمد به‌ازای هر گروه (chat_id) در PostgreSQL ذخیره
می‌شن، پس با ری‌استارت/ری‌دیپلوی از دست نمی‌رن.
"""
import asyncio
import logging
import re

from telethon import events

from .. import runtime
from ..config import PREFIX
from ..runtime import client
from ..storage.group_guard_store import (
    get_welcome_text,
    group_guard_state,
    is_link_filter_enabled,
    is_welcome_enabled,
    set_link_filter,
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


async def _is_admin_or_creator(chat_id: int, user_id: int) -> bool:
    try:
        perms = await client.get_permissions(chat_id, user_id)
    except Exception:
        return False  # اگه نتونستیم چک کنیم، برای احتیاط پیام رو حذف نمی‌کنیم
    return bool(getattr(perms, "is_admin", False) or getattr(perms, "is_creator", False))


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
