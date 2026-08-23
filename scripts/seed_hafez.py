#!/usr/bin/env python3
"""
اسکریپتِ یک‌بارِ Seed: کلِ دیوانِ حافظ رو با پکیجِ پایتونیِ `hafez`
(https://pypi.org/project/hafez - دیتاش از گنجور استخراج شده) می‌خونه و توی
جدولِ PostgreSQL خودمون (hafez_poems) ذخیره می‌کنه.

چرا این‌جوری؟
    نسخه‌ی قبلی، پکیجِ `hafez` رو مستقیماً توی خودِ ربات و در لحظه‌ی اجرای
    دستورِ `.فال` import می‌کرد. این باعث می‌شد اگه سرویس فقط ری‌استارت بشه
    (نه یه بیلدِ کامل - که خیلی وقتا روی Railway/Replit پیش میاد)، پکیج اصلاً
    نصب نباشه و `.فال` خطا بده. با این روش، `hafez` فقط **یک‌بار و فقط روی
    ماشینِ خودِ توسعه‌دهنده/CI** لازمه - خودِ ربات موقعِ اجرا هیچ‌وقت اون رو
    import نمی‌کنه؛ فقط از PostgreSQL (که همین‌طوری هم منبعِ اصلیِ داده‌ی
    کلِ پروژه‌ست) یه ردیفِ رندوم می‌خونه.

قبل از اجرا:
    ۱. مطمئن شو DATABASE_URL ست شده (همون چیزی که خودِ ربات هم ازش استفاده می‌کنه).
    ۲. جدول‌ها رو با Alembic بساز/آپدیت کن:
         alembic upgrade head
    ۳. پکیجِ `hafez` رو (فقط برای همین اسکریپت، یه‌بار) نصب کن:
         pip install hafez
    ۴. این اسکریپت رو از ریشه‌ی پروژه اجرا کن:
         python scripts/seed_hafez.py

Idempotent است - هر چندبار اجرا بشه فقط upsert می‌کنه، رکورد تکراری نمی‌سازه.
بعد از اجرای موفق، دیگه نیازی به نگه‌داشتنِ `hafez` توی محیطِ اجرایِ ربات
نیست (توی requirements.txt هم نیست - فقط این‌جا لازمه).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.repositories import hafez_repo  # noqa: E402


def _read_all_poems() -> list[dict]:
    try:
        import hafez
    except ImportError:
        print(
            "❌ پکیجِ `hafez` نصب نیست. اول این رو بزن:\n"
            "    pip install hafez\n"
            "(این پکیج فقط برای همین اسکریپتِ seed لازمه، نه برای خودِ ربات.)",
            file=sys.stderr,
        )
        sys.exit(1)

    total = hafez.total_poems()
    print(f"در حالِ خوندنِ {total} غزل از پکیجِ hafez...")
    poems = []
    for i in range(1, total + 1):
        data = hafez.get_poem(i)
        verses = data.get("poem") or []
        if isinstance(verses, str):
            verses = [v for v in verses.splitlines() if v.strip()]
        poems.append(
            {
                "id": data.get("id", i),
                "poem": "\n".join(verses),
                "interpretation": (data.get("interpretation") or "").strip() or None,
                "alt_interpretation": (data.get("alt_interpretation") or "").strip() or None,
            }
        )
    return poems


async def main():
    poems = _read_all_poems()
    if not poems:
        print("⚠️ هیچ غزلی از پکیجِ hafez خونده نشد؛ چیزی ذخیره نشد.")
        return

    print(f"در حالِ ذخیره‌ی {len(poems)} غزل توی PostgreSQL (جدولِ hafez_poems)...")
    # به‌صورتِ دسته‌ای (هر بار ۵۰ تا) upsert می‌کنیم که یه تراکنشِ خیلی
    # بزرگ روی کل جدول باز نمونه
    batch_size = 50
    saved = 0
    for start in range(0, len(poems), batch_size):
        batch = poems[start:start + batch_size]
        saved += await hafez_repo.bulk_upsert(batch)
        print(f"  ...{saved}/{len(poems)}")

    total_in_db = await hafez_repo.count()
    print(f"✅ تمام شد. الان {total_in_db} غزل توی جدولِ hafez_poems هست.")


if __name__ == "__main__":
    asyncio.run(main())
