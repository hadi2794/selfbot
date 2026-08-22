"""
سوییچ‌های سراسریِ ساده که store اختصاصیِ خودشون رو ندارن (بر خلافِ
منشی/ارسال‌خودکار/فونت که هرکدوم store کامل خودشون رو دارن): زمان‌بند،
آمار، و موتورِ اعلان. مقدارشون از همون جدولِ عمومیِ settings (key-value)
خونده/نوشته می‌شه، دقیقاً مثلِ بقیه‌ی storeها با یک init_*_state() که باید
موقعِ استارتاپ (bot/db/bootstrap.py) صدا زده بشه.
"""
from ..repositories import settings_repo

# مقادیرِ پیش‌فرض: همه چی روشنه، دقیقاً همون رفتاری که قبل از اضافه‌شدنِ این
# سوییچ‌ها وجود داشت (scheduler_worker/stats_saver/notification engine همیشه
# فعال بودن) - پس نبودِ رکورد توی دیتابیس نباید چیزی رو خاموش کنه.
toggles = {
    "scheduler_enabled": True,
    "stats_enabled": True,
    "notifications_enabled": True,
}

_KEYS = list(toggles.keys())


async def init_settings_toggles() -> None:
    for key in _KEYS:
        value = await settings_repo.get_setting(key)
        if value is not None:
            toggles[key] = value == "true"


async def set_toggle(key: str, enabled: bool) -> None:
    if key not in toggles:
        raise ValueError(f"سوییچِ نامعتبر: {key}")
    toggles[key] = enabled
    await settings_repo.set_setting(key, "true" if enabled else "false")
