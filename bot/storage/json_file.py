"""
بارگذاری/ذخیره‌ی عمومیِ فایل‌های JSON با merge روی مقادیر پیش‌فرض.

⚠️ از migration به PostgreSQL به بعد، هیچ‌کدوم از bot/storage/*.py دیگه از
این ماژول استفاده نمی‌کنن (منبع اصلیِ داده الان Repository Layer/PostgreSQL
است). این فایل فقط برای سازگاریِ عقب‌رو نگه داشته شده (مثلاً اگه اسکریپت یا
ابزار بیرونی‌ای بهش وابسته بود) و حذف نشده - قابلیتی رو هم پیاده‌سازی نمی‌کنه
که جای دیگه‌ای نباشه.
"""
import json
import os


def load_json(path, default):
    """اگه فایل وجود داشته باشه، مقادیرش رو روی یه کپی از default می‌شینه."""
    result = dict(default)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            result.update({k: data.get(k, v) for k, v in default.items()})
    return result


def save_json(path, payload):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
