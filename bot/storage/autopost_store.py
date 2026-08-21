"""وضعیتِ ارسالِ خودکارِ متن - PostgreSQL از طریق Repository Layer."""
import time

from .. import config
from ..repositories import autopost_repo

_DEFAULT = {"enabled": False, "interval_minutes": 5, "text": "", "chats": {}}

# دقیقاً مثل قبل یک دیکشنریِ درون‌حافظه‌ای مشترک؛ init_autopost_state() موقع
# استارتاپ این رو از PostgreSQL پر می‌کنه.
autopost_state = dict(_DEFAULT)
autopost_state["chats"] = {}

_autopost_next_run = time.time() + max(
    autopost_state["interval_minutes"], config.AUTOPOST_MIN_INTERVAL_MINUTES
) * 60
_autopost_force_now = False


async def init_autopost_state() -> None:
    global _autopost_next_run
    settings = await autopost_repo.get_settings()
    chats = await autopost_repo.list_chats()
    autopost_state["enabled"] = settings.enabled
    autopost_state["interval_minutes"] = settings.interval_minutes
    autopost_state["text"] = settings.text
    autopost_state["chats"] = chats
    _autopost_next_run = time.time() + max(
        autopost_state["interval_minutes"], config.AUTOPOST_MIN_INTERVAL_MINUTES
    ) * 60


async def save_autopost() -> None:
    """تنظیماتِ کلی (enabled/interval/text) رو ذخیره می‌کنه - نه لیست چت‌ها (اونا API جدا دارن)."""
    await autopost_repo.save_settings(
        enabled=autopost_state["enabled"],
        interval_minutes=autopost_state["interval_minutes"],
        text=autopost_state["text"],
    )


async def add_autopost_chat(chat_id: int, title: str) -> None:
    autopost_state["chats"][str(chat_id)] = title
    await autopost_repo.upsert_chat(chat_id, title)


async def remove_autopost_chat(chat_id: int):
    removed = autopost_state["chats"].pop(str(chat_id), None)
    if removed is not None:
        await autopost_repo.remove_chat(chat_id)
    return removed


async def clear_autopost_chats() -> None:
    autopost_state["chats"].clear()
    await autopost_repo.clear_chats()


def reset_autopost_timer():
    global _autopost_next_run
    _autopost_next_run = time.time() + max(
        autopost_state["interval_minutes"], config.AUTOPOST_MIN_INTERVAL_MINUTES
    ) * 60


def get_next_run():
    return _autopost_next_run


def set_force_now(value: bool):
    global _autopost_force_now
    _autopost_force_now = value


def get_force_now():
    return _autopost_force_now
