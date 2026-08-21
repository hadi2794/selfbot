"""
پیکربندی مرکزیِ logging.

این تابع باید همون خط اولِ main.py (قبل از import هر ماژول دیگه‌ای که
`logging.getLogger(...)` می‌سازه) صدا زده بشه. با این کار همه‌ی logger های
زیرمجموعه‌ی "selfbot" (مثلاً selfbot.db، selfbot.clock، selfbot.handlers.*)
از همین فرمت/سطح استفاده می‌کنن، بدون این‌که خودشون basicConfig جدا صدا بزنن.

روی Railway هر چیزی که به stdout/stderr نوشته بشه خودکار توی تب Logs
نمایش داده می‌شه؛ پس نیازی به فایل لاگ یا هندلر جداگونه نیست - فقط کافیه
از logging استفاده بشه، نه print().

نکته‌ی مهم درباره‌ی logger.exception(): این متد فقط باید *داخل یک except
block* صدا زده بشه؛ خودش به‌طور خودکار traceback کامل خطای در حال مدیریت‌شدن
(sys.exc_info()) رو به پیام لاگ اضافه می‌کنه - نیازی نیست خودِ exception رو
دستی به رشته تبدیل کنی.
"""
import logging
import os


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # کتابخونه‌های شخص‌ثالث (به‌خصوص telethon) به‌صورت پیش‌فرض خیلی پرحرفن؛
    # سطح‌شون رو بالاتر می‌بریم که لاگ‌های خودِ بات توی Railway گم نشه.
    logging.getLogger("telethon").setLevel(logging.WARNING)
