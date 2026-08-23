"""
وضعیتِ «مدیریت گروه پیشرفته» (فیلترلینک + خوش‌آمدگویی + فیلترِ پورن + فیلترِ
اسپم) - PostgreSQL از طریق Repository Layer، دقیقاً مثل بقیه‌ی storeها: یک
دیکشنریِ درون‌حافظه‌ای که Handlerها مستقیم بهش رفرنس دارن،
init_group_guard_state() موقع استارتاپ (bot/db/bootstrap.py) پرش می‌کنه.
"""
from ..repositories import group_guard_repo

DEFAULT_WELCOME_TEXT = "سلام {نام} 👋 به گروه خوش اومدی!"

group_guard_state = {
    "link_filter_chats": set(),  # chat_id هایی که فیلترلینک روشنه
    "welcome": {},  # chat_id -> {"enabled": bool, "text": str | None}
    "porn_filter_chats": set(),  # chat_id هایی که فیلترِ پورن روشنه
    "spam_filter_chats": set(),  # chat_id هایی که فیلترِ اسپم روشنه
}


async def init_group_guard_state() -> None:
    rows = await group_guard_repo.list_all()
    link_chats = set()
    welcome = {}
    porn_chats = set()
    spam_chats = set()
    for row in rows:
        if row.link_filter_enabled:
            link_chats.add(row.chat_id)
        if row.welcome_enabled or row.welcome_text:
            welcome[row.chat_id] = {"enabled": row.welcome_enabled, "text": row.welcome_text}
        if row.porn_filter_enabled:
            porn_chats.add(row.chat_id)
        if row.spam_filter_enabled:
            spam_chats.add(row.chat_id)
    group_guard_state["link_filter_chats"] = link_chats
    group_guard_state["welcome"] = welcome
    group_guard_state["porn_filter_chats"] = porn_chats
    group_guard_state["spam_filter_chats"] = spam_chats


async def set_link_filter(chat_id: int, enabled: bool) -> None:
    if enabled:
        group_guard_state["link_filter_chats"].add(chat_id)
    else:
        group_guard_state["link_filter_chats"].discard(chat_id)
    await group_guard_repo.set_link_filter(chat_id, enabled)


def is_link_filter_enabled(chat_id: int) -> bool:
    return chat_id in group_guard_state["link_filter_chats"]


async def set_porn_filter(chat_id: int, enabled: bool) -> None:
    if enabled:
        group_guard_state["porn_filter_chats"].add(chat_id)
    else:
        group_guard_state["porn_filter_chats"].discard(chat_id)
    await group_guard_repo.set_porn_filter(chat_id, enabled)


def is_porn_filter_enabled(chat_id: int) -> bool:
    return chat_id in group_guard_state["porn_filter_chats"]


async def set_spam_filter(chat_id: int, enabled: bool) -> None:
    if enabled:
        group_guard_state["spam_filter_chats"].add(chat_id)
    else:
        group_guard_state["spam_filter_chats"].discard(chat_id)
    await group_guard_repo.set_spam_filter(chat_id, enabled)


def is_spam_filter_enabled(chat_id: int) -> bool:
    return chat_id in group_guard_state["spam_filter_chats"]


async def set_welcome_enabled(chat_id: int, enabled: bool) -> None:
    entry = group_guard_state["welcome"].setdefault(chat_id, {"enabled": False, "text": None})
    entry["enabled"] = enabled
    await group_guard_repo.set_welcome(chat_id, enabled=enabled)


async def set_welcome_text(chat_id: int, text: str) -> None:
    entry = group_guard_state["welcome"].setdefault(chat_id, {"enabled": False, "text": None})
    entry["text"] = text
    await group_guard_repo.set_welcome(chat_id, text=text)


def is_welcome_enabled(chat_id: int) -> bool:
    entry = group_guard_state["welcome"].get(chat_id)
    return bool(entry and entry["enabled"])


def get_welcome_text(chat_id: int) -> str:
    entry = group_guard_state["welcome"].get(chat_id)
    text = entry.get("text") if entry else None
    return text or DEFAULT_WELCOME_TEXT
