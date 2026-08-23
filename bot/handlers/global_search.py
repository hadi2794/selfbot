"""
دستور .جستجو - جستجوی جهانی: هم توی داده‌های داخلیِ ربات (یادداشت‌ها،
حافظه‌ی AI، پروفایلِ کاربران، اینباکس، کارهای زمان‌بندی‌شده)، هم توی خودِ
تلگرام (پیام‌های چت‌های خودت + کانال/گروه‌های عمومیِ کلِ تلگرام).
"""
import asyncio
import logging
import re
from typing import List, Dict, Any, Tuple

from telethon import errors, events
from telethon.tl.functions.contacts import SearchRequest as ContactsSearchRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import (
    InputMessagesFilterDocument,
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

# هر بخشِ محلی حداکثر چندتا آیتم نشون بده (پروفایل‌ها/تنظیمات قبلاً هیچ سقفی
# نداشتن و یه جستجوی کوتاه مثل ".جستجو ا" می‌تونست صدها ردیف برگردونه).
LOCAL_SECTION_LIMIT = 20
# کلِ نتیجه حداکثر توی این تعداد پیام پخش بشه؛ وگرنه یه جستجوی خیلی عمومی
# می‌تونست ده‌ها پیامِ پشت‌سرهم بفرسته و به FloodWait بخوریم.
MAX_PAGES = 5
# بینِ پیام‌های پیاپیِ نتایج یه‌کم مکث بذاریم که به لیمیتِ ارسالِ تلگرام نخوریم.
PAGE_SEND_DELAY = 0.35

# نویسه‌های ویژه‌ی مارک‌داونِ تلثون (**bold**، __italic__، `code`، [link]) که اگه
# متنِ خودِ کاربر/پیام/تلگرام بی‌اسکیپ توش باشه، می‌تونه فرمت‌بندیِ کل پیام رو
# بهم بریزه یا لینک رو زودتر از موقع ببنده.
_MD_SPECIAL_RE = re.compile(r"([\\`*_\[\]])")

# چون خیلی از متن‌های فارسی با کیبورد عربی/کپی‌پیست‌شده حروفِ عربیِ ي/ك رو دارن
# ولی چیزی که کاربر خودش تایپ می‌کنه معمولاً ی/ک استانداردِ فارسیه، بدونِ این
# نرمال‌سازی جستجوهای خیلی رایج (مثلاً "علی" در برابرِ "علي") چیزی پیدا نمی‌کردن.
_FA_NORMALIZE_MAP = str.maketrans(
    {
        "ي": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "‌": " ",  # نیم‌فاصله -> فاصله، تا "می‌شه" با "می شه" هم مچ بشه
    }
)


def _normalize_fa(text: str) -> str:
    return text.translate(_FA_NORMALIZE_MAP).strip()


def _md_escape(text: str) -> str:
    """متنِ دینامیک (پیام کاربر، اسم فایل، مقدارِ دیتابیس، ...) رو قبلِ قرار
    دادن توی خروجیِ مارک‌داون‌دار امن می‌کنه، وگرنه یه `_` یا `*` تکی وسطِ
    متنِ یه یادداشت می‌تونست کلِ فرمت‌بندیِ بعدِ خودش رو خراب کنه."""
    if not text:
        return text
    return _MD_SPECIAL_RE.sub(r"\\\1", text)


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
    زدن روش دقیقاً همون پیام/چت باز می‌شه؛ وگرنه متنِ ساده برمی‌گرده.
    توجه: text باید از قبل با _md_escape امن شده باشه."""
    if link:
        return f"[{text}]({link})"
    return text


def _extract_filename(m) -> str:
    """اگه پیام یه فایل/مدیا داشته باشه، اسمِ فایلش رو برمی‌گردونه (وگرنه None).
    برای عکس/ویدیوهای بدون attribute فایل‌نیم (مثل عکس‌های معمولی)، چیزی
    برنمی‌گردونه - چون خودِ تلگرام هم اسمی براشون نداره که بشه باهاش سرچ کرد."""
    media = getattr(m, "media", None)
    doc = getattr(media, "document", None) if media else None
    if not doc:
        return None
    for attr in getattr(doc, "attributes", []) or []:
        fname = getattr(attr, "file_name", None)
        if fname:
            return fname
    return None


async def _local_notes(query: str) -> Tuple[str, List[str]]:
    try:
        notes = await notes_repo.search_notes(query, limit=LOCAL_SECTION_LIMIT)
        items = [f"`{_md_escape(n.key)}`: {_md_escape(n.text[:80])}..." for n in notes]
        return "یادداشت‌ها", items
    except Exception:
        logger.exception("خطا در جستجوی یادداشت‌ها")
        return "یادداشت‌ها", []


async def _local_ai_memory(query: str) -> Tuple[str, List[str]]:
    try:
        memories = await ai_memory_repo.search_memories(query)
        items = []
        for cat, mems in memories.items():
            for m in mems:
                items.append(f"[{_md_escape(cat)}] `{_md_escape(m.key)}`: {_md_escape(m.value[:80])}...")
        return "حافظه AI", items[:LOCAL_SECTION_LIMIT]
    except Exception:
        logger.exception("خطا در جستجوی حافظه‌ی AI")
        return "حافظه AI", []


async def _local_profiles(query: str) -> Tuple[str, List[str]]:
    try:
        profiles = await user_profile_repo.search_profiles(query)
        items = []
        for p in profiles[:LOCAL_SECTION_LIMIT]:
            label = f"@{_md_escape(p.username or p.first_name or str(p.user_id))}: {_md_escape(p.tags or 'بدون برچسب')}"
            # لینکِ باز شدنِ همون چتِ خصوصی با این کاربر
            link = f"https://t.me/{p.username}" if p.username else f"tg://user?id={p.user_id}"
            items.append(_fmt_item(label, link))
        return "کاربران", items
    except Exception:
        logger.exception("خطا در جستجوی پروفایل‌ها")
        return "کاربران", []


async def _local_inbox(query: str) -> Tuple[str, List[str]]:
    try:
        inbox_items = await inbox_repo.search_items(query, limit=LOCAL_SECTION_LIMIT)
        items = []
        for i in inbox_items:
            label = f"{_md_escape(i.sender_name or 'ناشناس')}: {_md_escape(i.text[:60])}..."
            link = _message_link(i.chat_id, i.message_id)
            items.append(_fmt_item(label, link))
        return "صندوق ورودی", items
    except Exception:
        logger.exception("خطا در جستجوی صندوق ورودی")
        return "صندوق ورودی", []


async def _local_scheduler(query: str) -> Tuple[str, List[str]]:
    try:
        jobs = await scheduler_repo.search_jobs(query, limit=LOCAL_SECTION_LIMIT)
        items = [
            f"#{j.id} {_md_escape(j.text[:40])}... ({j.run_at.strftime('%Y-%m-%d %H:%M')})"
            for j in jobs
        ]
        return "زمان‌بندی", items
    except Exception:
        logger.exception("خطا در جستجوی کارهای زمان‌بندی‌شده")
        return "زمان‌بندی", []


async def _local_settings(query: str) -> Tuple[str, List[str]]:
    try:
        settings = await settings_repo.get_all_settings()
        q = query.lower()
        matched = {k: v for k, v in settings.items() if q in k.lower() or q in str(v).lower()}
        items = [f"`{_md_escape(k)}`: {_md_escape(str(v)[:40])}..." for k, v in list(matched.items())[:LOCAL_SECTION_LIMIT]]
        return "تنظیمات", items
    except Exception:
        logger.exception("خطا در جستجوی تنظیمات")
        return "تنظیمات", []


async def _search_local(query: str) -> Dict[str, List[str]]:
    """جستجو توی داده‌های داخلیِ ربات (دیتابیسِ خودش).
    هر بخش یه کوئریِ جدا به دیتابیس می‌زنه؛ به‌جای این‌که یکی‌یکی صبر کنیم،
    همه‌شون رو هم‌زمان اجرا می‌کنیم تا کلِ جستجو به‌جای مجموعِ زمانِ همه‌ی
    کوئری‌ها، فقط به‌اندازه‌ی کندترینِ اون‌ها طول بکشه."""
    sections = await asyncio.gather(
        _local_notes(query),
        _local_ai_memory(query),
        _local_profiles(query),
        _local_inbox(query),
        _local_scheduler(query),
        _local_settings(query),
    )
    return {label: items for label, items in sections if items}


async def _search_telegram_messages(query: str, limit: int = 20) -> List[str]:
    """
    جستجوی پیام توی همه‌ی چت‌هایی که خودت عضوشونی (SearchGlobalRequest -
    همون چیزی که نوارِ جستجویِ خودِ اپ تلگرام هم استفاده می‌کنه). چون فقط
    روی چت‌های خودت کار می‌کنه (نه هر چیزی توی کلِ تلگرام)، نتیجه رو جدا از
    جستجوی کانال/گروه گذاشتم.

    دو تا درخواستِ جدا می‌زنیم:
    - InputMessagesFilterEmpty: متن/کپشنِ پیام‌ها
    - InputMessagesFilterDocument: اسمِ فایل‌ها/مدیا (سرورِ تلگرام موقعِ فیلترِ
      Document، q رو روی filename هم چک می‌کنه؛ برای همینه که سرچِ «اسمِ فایل»
      توی خودِ اپِ تلگرام هم همین‌جوری کار می‌کنه)
    این دو درخواست هم به‌صورتِ هم‌زمان (نه پشتِ‌سرِهم) به سرورِ تلگرام زده
    می‌شن. نتایج بر اساسِ (چت، شناسه‌ی پیام) دیدوپ می‌شن که یه پیام دوبار نیاد.
    """

    async def _one(filt):
        try:
            return await client(
                SearchGlobalRequest(
                    q=query,
                    filter=filt,
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
            return None
        except Exception:
            logger.exception("خطا در جستجوی پیام‌های تلگرام")
            return None

    raw_results = await asyncio.gather(
        _one(InputMessagesFilterEmpty()), _one(InputMessagesFilterDocument())
    )

    seen = set()
    all_messages = []
    chats_map: Dict[int, Any] = {}
    users_map: Dict[int, Any] = {}

    for result in raw_results:
        if result is None:
            continue

        for c in getattr(result, "chats", []) or []:
            chats_map[c.id] = c
        for u in getattr(result, "users", []) or []:
            users_map[u.id] = u

        for m in getattr(result, "messages", []) or []:
            peer = getattr(m, "peer_id", None)
            key = (_peer_to_chat_id(peer), getattr(m, "id", None))
            if key in seen:
                continue
            seen.add(key)
            all_messages.append(m)

    items = []
    for m in all_messages:
        text = (getattr(m, "message", "") or "").strip()
        filename = _extract_filename(m)
        if not text and not filename:
            continue

        peer = getattr(m, "peer_id", None)
        chat_title = _peer_title(peer, chats_map, users_map) if peer else "نامشخص"

        parts = []
        if filename:
            parts.append(f"📎 {_md_escape(filename)}")
        if text:
            parts.append(f"{_md_escape(text[:80])}...")
        body = " — ".join(parts)

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

        items.append(_fmt_item(f"«{_md_escape(chat_title)}»: {body}", link))
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
        items.append(_fmt_item(f"{kind} **{_md_escape(chat.title)}**{username}", link))
    for user in getattr(result, "users", []) or []:
        if getattr(user, "bot", False):
            continue
        name = " ".join(filter(None, [user.first_name, user.last_name])) or str(user.id)
        uname = getattr(user, "username", None)
        username = f" (@{uname})" if uname else ""
        link = f"https://t.me/{uname}" if uname else f"tg://user?id={user.id}"
        items.append(_fmt_item(f"👤 **{_md_escape(name)}**{username}", link))
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

    query = _normalize_fa(" ".join(args))
    await event.edit(f"🔍 در حال جستجوی `{_md_escape(query)}`...")

    # سه دسته‌ی مستقل (محلی/پیام‌های تلگرام/موجودیت‌های تلگرام) هیچ‌کدوم به
    # نتیجه‌ی اون‌یکی نیاز ندارن؛ قبلاً پشتِ‌سرِهم اجرا می‌شدن (مجموعِ زمانِ
    # هر سه)، الان هم‌زمان اجرا می‌شن (فقط به‌اندازه‌ی کندترینِ اون‌ها طول
    # می‌کشه) - برای جستجویی که چند تا درخواستِ شبکه‌ای هم داره، این فرق
    # می‌تونه چند ثانیه باشه.
    results, tg_messages, tg_entities = await asyncio.gather(
        _search_local(query),
        _search_telegram_messages(query),
        _search_telegram_entities(query),
    )

    if tg_messages:
        results["💬 پیام‌های تلگرام"] = tg_messages
    if tg_entities:
        results["📡 کانال/گروه/کاربرِ تلگرام"] = tg_entities

    if not results:
        return await event.edit(f"🔍 نتیجه‌ای برای `{_md_escape(query)}` یافت نشد.")

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
    hidden_pages = 0
    if len(pages) > MAX_PAGES:
        hidden_pages = len(pages) - MAX_PAGES
        pages = pages[:MAX_PAGES]

    if len(pages) == 1 and not hidden_pages:
        await event.edit(f"🔍 **نتایج جستجو: `{_md_escape(query)}`**\n\n{pages[0]}")
        return

    await event.edit(
        f"🔍 **نتایج جستجو: `{_md_escape(query)}`** (صفحه‌ی ۱ از {len(pages) + hidden_pages})\n\n{pages[0]}"
    )
    for i, page in enumerate(pages[1:], start=2):
        await asyncio.sleep(PAGE_SEND_DELAY)
        await event.respond(f"🔍 ادامه‌ی نتایج (صفحه‌ی {i} از {len(pages) + hidden_pages})\n\n{page}")

    if hidden_pages:
        await asyncio.sleep(PAGE_SEND_DELAY)
        await event.respond(
            f"⚠️ {hidden_pages} صفحه‌ی دیگه هم بود که برای جلوگیری از اسپم نشونش ندادم. "
            f"عبارتِ جستجو رو دقیق‌تر کن تا نتیجه‌ی کمتری بگیری."
        )
