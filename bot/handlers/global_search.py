"""
دستور .جستجو - جستجوی جهانی: هم توی داده‌های داخلیِ ربات (یادداشت‌ها،
حافظه‌ی AI، پروفایلِ کاربران، اینباکس، کارهای زمان‌بندی‌شده)، هم توی خودِ
تلگرام (پیام‌های چت‌های خودت + کانال/گروه‌های عمومیِ کلِ تلگرام).
"""
import logging
from typing import List, Dict, Any

from telethon import errors, events
from telethon.tl.functions.contacts import SearchRequest as ContactsSearchRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import (
    InputMessagesFilterEmpty,
    InputPeerEmpty,
    PeerChannel,
    PeerChat,
    PeerUser,
)

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import (
    notes_repo,
    ai_memory_repo,
    user_profile_repo,
    inbox_repo,
    settings_repo,
    scheduler_repo,
)

logger = logging.getLogger("selfbot.handlers.global_search")

# چندتا از این بخش‌ها به سرورهای تلگرام درخواست می‌زنن؛ اگه یکی‌شون fail کنه
# (FloodWait، خطای شبکه، ...) نباید بقیه‌ی نتایج رو از بین ببره - برای همین
# هر بخش try/except جدای خودش رو داره، نه یه try/except دورِ همه‌چی.


def _peer_title(peer, chats_map: dict, users_map: dict) -> str:
    if isinstance(peer, PeerUser):
        u = users_map.get(peer.user_id)
        if u:
            return " ".join(filter(None, [u.first_name, u.last_name])) or (u.username or str(peer.user_id))
        return str(peer.user_id)
    if isinstance(peer, PeerChat):
        c = chats_map.get(peer.chat_id)
        return c.title if c else str(peer.chat_id)
    if isinstance(peer, PeerChannel):
        c = chats_map.get(peer.channel_id)
        return c.title if c else str(peer.channel_id)
    return "نامشخص"


def _message_link(chat_id: int, message_id: int, username: str = None) -> str:
    """
    لینکِ یک پیامِ مشخص می‌سازه تا با زدن روش، دقیقاً همون پیام باز بشه:
    - اگه چت/کانال یوزرنیم داشته باشه: https://t.me/<username>/<msg_id>
    - سوپرگروه/کانالِ خصوصی (chat_id با -100 شروع می‌شه): https://t.me/c/<id>/<msg_id>
    - گروهِ ساده یا چتِ خصوصی (بدون یوزرنیم): tg://openmessage?...
      (این‌ها فقط توی اپ/دسکتاپِ تلگرام باز می‌شن، نه توی مرورگر)
    """
    if username:
        return f"https://t.me/{username}/{message_id}"
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"
    if chat_id < 0:
        return f"tg://openmessage?chat_id={abs(chat_id)}&message_id={message_id}"
    return f"tg://openmessage?user_id={chat_id}&message_id={message_id}"


def _peer_to_chat_id(peer) -> "int | None":
    """پیوندِ Peer تلگرام (User/Chat/Channel) رو به یه chat_id قابل‌استفاده برای
    _message_link تبدیل می‌کنه (همون قراردادِ chat_id منفی/مثبتِ تلگرام)."""
    if isinstance(peer, PeerUser):
        return peer.user_id
    if isinstance(peer, PeerChat):
        return -peer.chat_id
    if isinstance(peer, PeerChannel):
        return int(f"-100{peer.channel_id}")
    return None


def _fmt_item(text: str, link: str = None) -> str:
    """اگه لینک داشته باشیم، متن رو به یه لینکِ قابل‌کلیک تبدیل می‌کنه که با
    زدن روش دقیقاً همون پیام/چت باز می‌شه؛ وگرنه متنِ ساده برمی‌گرده."""
    if link:
        return f"[{text}]({link})"
    return text


async def _search_local(query: str) -> Dict[str, List[str]]:
    """جستجو توی داده‌های داخلیِ ربات (دیتابیسِ خودش)."""
    results: Dict[str, List[str]] = {}

    try:
        notes = await notes_repo.search_notes(query)
        if notes:
            results["یادداشت‌ها"] = [f"`{n.key}`: {n.text[:80]}..." for n in notes]
    except Exception:
        logger.exception("خطا در جستجوی یادداشت‌ها")

    try:
        memories = await ai_memory_repo.search_memories(query)
        if memories:
            items = []
            for cat, mems in memories.items():
                for m in mems:
                    items.append(f"[{cat}] `{m.key}`: {m.value[:80]}...")
            if items:
                results["حافظه AI"] = items
    except Exception:
        logger.exception("خطا در جستجوی حافظه‌ی AI")

    try:
        profiles = await user_profile_repo.search_profiles(query)
        if profiles:
            items = []
            for p in profiles:
                label = f"@{p.username or p.first_name or str(p.user_id)}: {p.tags or 'بدون برچسب'}"
                # لینکِ باز شدنِ همون چتِ خصوصی با این کاربر
                link = f"https://t.me/{p.username}" if p.username else f"tg://user?id={p.user_id}"
                items.append(_fmt_item(label, link))
            results["کاربران"] = items
    except Exception:
        logger.exception("خطا در جستجوی پروفایل‌ها")

    try:
        inbox_items = await inbox_repo.search_items(query)
        if inbox_items:
            items = []
            for i in inbox_items:
                label = f"{i.sender_name or 'ناشناس'}: {i.text[:60]}..."
                link = _message_link(i.chat_id, i.message_id)
                items.append(_fmt_item(label, link))
            results["صندوق ورودی"] = items
    except Exception:
        logger.exception("خطا در جستجوی صندوق ورودی")

    try:
        jobs = await scheduler_repo.search_jobs(query)
        if jobs:
            results["زمان‌بندی"] = [
                f"#{j.id} {j.text[:40]}... ({j.run_at.strftime('%Y-%m-%d %H:%M')})"
                for j in jobs
            ]
    except Exception:
        logger.exception("خطا در جستجوی کارهای زمان‌بندی‌شده")

    try:
        settings = await settings_repo.get_all_settings()
        matched = {k: v for k, v in settings.items() if query.lower() in k.lower() or query.lower() in str(v).lower()}
        if matched:
            results["تنظیمات"] = [f"`{k}`: {str(v)[:40]}..." for k, v in matched.items()]
    except Exception:
        logger.exception("خطا در جستجوی تنظیمات")

    return results


async def _search_telegram_messages(query: str, limit: int = 20) -> List[str]:
    """
    جستجوی پیام توی همه‌ی چت‌هایی که خودت عضوشونی (SearchGlobalRequest -
    همون چیزی که نوارِ جستجویِ خودِ اپ تلگرام هم استفاده می‌کنه). چون فقط
    روی چت‌های خودت کار می‌کنه (نه هر چیزی توی کلِ تلگرام)، نتیجه رو جدا از
    جستجوی کانال/گروه گذاشتم.
    """
    try:
        result = await client(
            SearchGlobalRequest(
                q=query,
                filter=InputMessagesFilterEmpty(),
                min_date=None,
                max_date=None,
                offset_rate=0,
                offset_peer=InputPeerEmpty(),
                offset_id=0,
                limit=limit,
            )
        )
    except errors.FloodWaitError as e:
        logger.warning("FloodWait در جستجوی پیام‌های تلگرام: %s ثانیه", e.seconds)
        return []
    except Exception:
        logger.exception("خطا در جستجوی پیام‌های تلگرام")
        return []

    messages = getattr(result, "messages", []) or []
    chats_map = {c.id: c for c in getattr(result, "chats", [])}
    users_map = {u.id: u for u in getattr(result, "users", [])}

    items = []
    for m in messages[:limit]:
        text = (getattr(m, "message", "") or "").strip()
        if not text:
            continue
        peer = getattr(m, "peer_id", None)
        chat_title = _peer_title(peer, chats_map, users_map) if peer else "نامشخص"

        link = None
        chat_id = _peer_to_chat_id(peer) if peer else None
        message_id = getattr(m, "id", None)
        if chat_id is not None and message_id is not None:
            username = None
            if isinstance(peer, PeerChannel):
                c = chats_map.get(peer.channel_id)
                username = getattr(c, "username", None)
            elif isinstance(peer, PeerUser):
                u = users_map.get(peer.user_id)
                username = getattr(u, "username", None)
            link = _message_link(chat_id, message_id, username)

        items.append(_fmt_item(f"«{chat_title}»: {text[:80]}...", link))
    return items


async def _search_telegram_entities(query: str, limit: int = 20) -> List[str]:
    """
    جستجوی کانال/گروه/کاربر توی دایرکتوریِ عمومیِ کلِ تلگرام (contacts.SearchRequest -
    همون چیزی که وقتی توی جستجوی تلگرام یه اسم می‌زنی و نتایجِ «Global search»
    نشون داده می‌شن) - نتایجش محدود به چت‌های خودت نیست، هر کانال/گروه/کاربرِ
    عمومیِ کل تلگرام که با عبارت مچ بشه رو می‌گیره.
    """
    try:
        result = await client(ContactsSearchRequest(q=query, limit=limit))
    except errors.FloodWaitError as e:
        logger.warning("FloodWait در جستجوی سراسریِ تلگرام: %s ثانیه", e.seconds)
        return []
    except Exception:
        logger.exception("خطا در جستجوی کانال/گروهِ تلگرام")
        return []

    items = []
    for chat in getattr(result, "chats", []) or []:
        kind = "📢 کانال" if getattr(chat, "broadcast", False) else "👥 گروه"
        uname = getattr(chat, "username", None)
        username = f" (@{uname})" if uname else ""
        link = f"https://t.me/{uname}" if uname else None
        items.append(_fmt_item(f"{kind} **{chat.title}**{username}", link))
    for user in getattr(result, "users", []) or []:
        if getattr(user, "bot", False):
            continue
        name = " ".join(filter(None, [user.first_name, user.last_name])) or str(user.id)
        uname = getattr(user, "username", None)
        username = f" (@{uname})" if uname else ""
        link = f"https://t.me/{uname}" if uname else f"tg://user?id={user.id}"
        items.append(_fmt_item(f"👤 **{name}**{username}", link))
    return items[:limit]


def _paginate_lines(lines: List[str], limit: int = 3500) -> List[str]:
    """
    خطوط رو به چند صفحه (هرکدوم زیرِ سقفِ کاراکتریِ تلگرام) می‌شکنه - فقط سرِ
    خط‌ها می‌بره، وسطِ یه خط رو نصف نمی‌کنه. برای اینکه جا برای هدر/شماره‌ی
    صفحه هم بمونه، limit عمداً زیرِ ۴۰۹۶ گذاشته شده.
    """
    pages: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1  # +1 برای \n
        if current and current_len + line_len > limit:
            pages.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        pages.append("\n".join(current))
    return pages or [""]


@client.on(events.NewMessage(outgoing=True, pattern=pat(["جستجو", "search"])))
async def global_search_handler(event):
    """جستجو در تمام داده‌ها + خودِ تلگرام."""
    args = (event.pattern_match.group(1) or "").strip().split()
    if not args:
        return await event.edit(
            f"🔍 **جستجوی جهانی**\n\n"
            f"استفاده: `{PREFIX}جستجو <عبارت>`\n\n"
            f"جستجو در:\n"
            f"• یادداشت‌ها\n"
            f"• حافظه AI\n"
            f"• پروفایل کاربران\n"
            f"• صندوق ورودی\n"
            f"• تنظیمات\n"
            f"• کارهای زمان‌بندی‌شده\n"
            f"• پیام‌های تلگرام (توی چت‌هایی که خودت عضوشونی)\n"
            f"• کانال/گروه/کاربرهای عمومیِ کلِ تلگرام"
        )

    query = " ".join(args)
    await event.edit(f"🔍 در حال جستجوی `{query}`...")

    results = await _search_local(query)

    tg_messages = await _search_telegram_messages(query)
    if tg_messages:
        results["💬 پیام‌های تلگرام"] = tg_messages

    tg_entities = await _search_telegram_entities(query)
    if tg_entities:
        results["📡 کانال/گروه/کاربرِ تلگرام"] = tg_entities

    if not results:
        return await event.edit(f"🔍 نتیجه‌ای برای `{query}` یافت نشد.")

    body_lines = []
    total = 0
    for section, items in results.items():
        body_lines.append(f"📁 **{section}** ({len(items)})")
        for item in items:
            body_lines.append(f"  • {item}")
        body_lines.append("")
        total += len(items)
    body_lines.append(f"📊 مجموع: {total} نتیجه")

    pages = _paginate_lines(body_lines)

    if len(pages) == 1:
        await event.edit(f"🔍 **نتایج جستجو: `{query}`**\n\n{pages[0]}")
        return

    await event.edit(f"🔍 **نتایج جستجو: `{query}`** (صفحه‌ی ۱ از {len(pages)})\n\n{pages[0]}")
    for i, page in enumerate(pages[1:], start=2):
        await event.respond(f"🔍 ادامه‌ی نتایج (صفحه‌ی {i} از {len(pages)})\n\n{page}")
