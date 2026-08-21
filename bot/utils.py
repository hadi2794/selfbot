"""ابزارهای کمکیِ عمومی: ساخت الگوی regex برای دستورات."""
import re

from . import config

# نام‌مستعار (فارسی/انگلیسی) -> نام اصلیِ فارسی؛ توسط pat() پر می‌شه، برای آمار استفاده می‌شه
ALL_COMMAND_NAMES = {}


def pat(name, arg=True):
    """
    ساخت الگوی regex برای دستورات خروجی (پیام‌هایی که خودتون می‌فرستید).
    name می‌تونه یک رشته باشه یا لیستی از نام‌های مترادف برای یک دستور (مثلاً
    نام فارسیِ جدید + نام انگلیسیِ قدیمی، برای سازگاری با عادت قبلی). اولین
    عضو لیست به‌عنوان نام اصلی/نمایشی (برای آمار و راهنما) در نظر گرفته می‌شه.
    """
    names = list(name) if isinstance(name, (list, tuple)) else [name]
    canonical = names[0]
    for n in names:
        ALL_COMMAND_NAMES[n] = canonical
    esc = re.escape(config.PREFIX)
    alt = "|".join(re.escape(n) for n in names)
    if arg:
        return rf"^{esc}(?:{alt})(?:\s+([\s\S]*))?$"
    return rf"^{esc}(?:{alt})$"
