"""
وضعیتِ منشیِ چت (پاسخ خودکار) - PostgreSQL از طریق Repository Layer.

`assistant_state` دقیقاً مثل قبل یک دیکشنریِ درون‌حافظه‌ای می‌مونه، چون همه‌ی
Handlerها و تسکِ پس‌زمینه (assistant_status_watcher) مستقیماً به همین آبجکت
رفرنس دارن؛ فقط منبع ذخیره‌سازیِ دائمی از فایل JSON به PostgreSQL عوض شده.
init_assistant_state() باید موقع استارتاپِ پروسه (bot/db/bootstrap.py) صدا
زده بشه تا این دیکشنری با آخرین وضعیتِ ذخیره‌شده در دیتابیس پر بشه.
"""
from ..repositories import assistant_repo

_DEFAULT = {
    "mode": "mention",
    "text": "سلام 👋 در حال حاضر آنلاین نیستم. پیامتون رو دیدم، به‌محض امکان جواب می‌دم.",
    "delay": 3,
    "include": [],
    "exclude": [],
    "auto_detect": True,  # اگه False باشه، یعنی کاربر دستی قفلش کرده و تشخیص خودکار دست بهش نمی‌زنه
    "manual_enabled": False,  # فقط وقتی auto_detect=False معتبره
    "ai_mode": False,  # اگه True باشه، پاسخِ خودکار به‌جای متنِ ثابت با هوش مصنوعی تولید می‌شه
}


def _build_initial_state(loaded: dict) -> dict:
    return {
        # اگه auto_detect خاموش باشه، وضعیت اولیه همون چیزیه که کاربر دستی قفل کرده بود؛
        # وگرنه False می‌مونه تا تسک پس‌زمینه‌ی تشخیص آنلاین/آفلاین خودش تعیینش کنه
        "enabled": loaded["manual_enabled"] if not loaded["auto_detect"] else False,
        "auto_detect": loaded["auto_detect"],
        "mode": loaded["mode"],
        "text": loaded["text"],
        "delay": loaded["delay"],
        "include": set(loaded["include"]),
        "exclude": set(loaded["exclude"]),
        "ai_mode": loaded["ai_mode"],
        "replied": set(),  # (chat_id, sender_id) که توی این نشست جواب گرفتن
    }


# تا قبل از init_assistant_state() با مقادیر پیش‌فرض پر می‌مونه؛ همه‌ی
# import هایی که در جاهای دیگه `from ..storage.assistant_store import
# assistant_state` می‌کنن همین یک آبجکت رو به اشتراک می‌ذارن (mutate-in-place).
assistant_state = _build_initial_state(dict(_DEFAULT))


async def init_assistant_state() -> None:
    """موقع بالا اومدنِ پروسه صدا زده می‌شه: state رو از PostgreSQL می‌خونه و IN-PLACE پر می‌کنه."""
    settings = await assistant_repo.get_settings()
    rules = await assistant_repo.list_chat_rules()
    loaded = dict(_DEFAULT)
    loaded.update(
        {
            "mode": settings.mode,
            "text": settings.text,
            "delay": settings.delay_seconds,
            "auto_detect": settings.auto_detect,
            "manual_enabled": settings.manual_enabled,
            "ai_mode": settings.ai_mode,
            "include": [cid for cid, rule in rules.items() if rule == "include"],
            "exclude": [cid for cid, rule in rules.items() if rule == "exclude"],
        }
    )
    fresh = _build_initial_state(loaded)
    assistant_state.clear()
    assistant_state.update(fresh)


async def save_assistant() -> None:
    await assistant_repo.save_settings(
        mode=assistant_state["mode"],
        text=assistant_state["text"],
        delay_seconds=assistant_state["delay"],
        auto_detect=assistant_state["auto_detect"],
        manual_enabled=assistant_state["enabled"] if not assistant_state["auto_detect"] else False,
        ai_mode=assistant_state["ai_mode"],
    )
    await assistant_repo.replace_chat_rules(
        include=assistant_state["include"],
        exclude=assistant_state["exclude"],
    )
