"""وضعیتِ خلاصه‌ی روزانه (`.خلاصه‌روز`) - PostgreSQL از طریق Repository Layer."""
from .. import config
from ..repositories import daily_digest_repo

_DEFAULT = {
    "enabled": False,
    "mode": "all",  # all | custom
    "hour": config.DAILY_DIGEST_DEFAULT_HOUR,
    "minute": config.DAILY_DIGEST_DEFAULT_MINUTE,
    "last_run_date": None,  # "YYYY-MM-DD" به‌وقتِ محلی؛ جلوی ارسالِ دوباره‌ی همون روز رو می‌گیره
    "chats": {},
}

daily_digest_state = dict(_DEFAULT)
daily_digest_state["chats"] = {}


async def init_daily_digest_state() -> None:
    settings = await daily_digest_repo.get_settings()
    chats = await daily_digest_repo.list_chats()
    daily_digest_state["enabled"] = settings.enabled
    daily_digest_state["mode"] = settings.mode
    daily_digest_state["hour"] = settings.hour
    daily_digest_state["minute"] = settings.minute
    daily_digest_state["last_run_date"] = settings.last_run_date
    daily_digest_state["chats"] = chats


async def save_daily_digest() -> None:
    """تنظیماتِ کلی (enabled/mode/hour/minute/last_run_date) - نه لیستِ چت‌ها (اونا API جدا دارن)."""
    await daily_digest_repo.save_settings(
        enabled=daily_digest_state["enabled"],
        mode=daily_digest_state["mode"],
        hour=daily_digest_state["hour"],
        minute=daily_digest_state["minute"],
        last_run_date=daily_digest_state["last_run_date"],
    )


async def add_digest_chat(chat_id: int, title: str) -> None:
    daily_digest_state["chats"][str(chat_id)] = title
    await daily_digest_repo.upsert_chat(chat_id, title)


async def remove_digest_chat(chat_id: int):
    removed = daily_digest_state["chats"].pop(str(chat_id), None)
    if removed is not None:
        await daily_digest_repo.remove_chat(chat_id)
    return removed


async def clear_digest_chats() -> None:
    daily_digest_state["chats"].clear()
    await daily_digest_repo.clear_chats()
