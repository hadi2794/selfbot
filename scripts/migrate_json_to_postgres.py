#!/usr/bin/env python3
"""
اسکریپت یک‌بارِ Migration: انتقال داده‌های JSON فعلی (notes / autopost /
assistant / font / stats) به PostgreSQL.

قبل از اجرا:
    1. مطمئن شو DATABASE_URL ست شده.
    2. جدول‌ها رو با Alembic بساز:
         alembic upgrade head
    3. این اسکریپت رو از ریشه‌ی پروژه اجرا کن:
         python scripts/migrate_json_to_postgres.py

کاری که انجام می‌ده (idempotent - می‌تونی چندبار اجراش کنی):
    ۱) از تمام فایل‌های JSON فعلی یک بکاپِ timestamped توی
       ./json_backup/<timestamp>/ می‌گیره (فایل‌های اصلی دست‌نخورده می‌مونن).
    ۲) تعداد رکوردهای هر بخش رو *قبل* از migration می‌شمره.
    ۳) داده‌ها رو (با upsert) به PostgreSQL منتقل می‌کنه.
    ۴) دوباره از PostgreSQL می‌شمره و با تعداد قبلی مقایسه می‌کنه؛ اگه
       مطابقت نداشته باشن، با کد خروج غیرصفر متوقف می‌شه (چیزی از دیتابیس
       پاک نمی‌کنه - دوباره قابل‌اجراست).

بعد از این‌که مطمئن شدی migration درست انجام شده، فایل‌های JSON دیگه در
زمان اجرا خونده نمی‌شن (PostgreSQL منبع اصلیه) - می‌تونی نگه‌شون داری
(به‌عنوان بکاپ) یا حذفشون کنی؛ این اسکریپت خودش هیچ فایلی رو حذف نمی‌کنه.
"""
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import config  # noqa: E402
from bot.repositories import (  # noqa: E402
    assistant_repo,
    autopost_repo,
    font_repo,
    notes_repo,
    stats_repo,
)


def _read_json(path, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  خطا در خواندن {path}: {e} - از مقدار پیش‌فرض استفاده می‌شه")
        return default


def backup_json_files(dest_dir: str) -> list:
    os.makedirs(dest_dir, exist_ok=True)
    paths = {
        "notes": config.NOTES_FILE,
        "autopost": config.AUTOPOST_FILE,
        "assistant": config.ASSISTANT_FILE,
        "font": config.FONT_STATE_FILE,
        "stats": config.STATS_FILE,
    }
    copied = []
    for _name, path in paths.items():
        if path and os.path.exists(path):
            dest = os.path.join(dest_dir, os.path.basename(path))
            shutil.copy2(path, dest)
            copied.append(dest)
    return copied


def count_json_records() -> dict:
    notes = _read_json(config.NOTES_FILE, {})
    autopost = _read_json(config.AUTOPOST_FILE, {"chats": {}})
    assistant = _read_json(config.ASSISTANT_FILE, {"include": [], "exclude": []})
    font = _read_json(config.FONT_STATE_FILE, {})
    stats = _read_json(config.STATS_FILE, {"commands_by_name": {}, "per_chat": {}})
    return {
        "notes": len(notes),
        "autopost_chats": len(autopost.get("chats", {}) or {}),
        "assistant_chat_rules": len(assistant.get("include", []) or [])
        + len(assistant.get("exclude", []) or []),
        "font_settings": 1 if font else 0,
        "stats_commands": len(stats.get("commands_by_name", {}) or {}),
        "stats_chats": len(stats.get("per_chat", {}) or {}),
    }


async def _migrate_data() -> None:
    notes = _read_json(config.NOTES_FILE, {})
    for key, text in notes.items():
        await notes_repo.upsert(key, text)

    autopost = _read_json(
        config.AUTOPOST_FILE,
        {"enabled": False, "interval_minutes": 5, "text": "", "chats": {}},
    )
    await autopost_repo.save_settings(
        enabled=autopost.get("enabled", False),
        interval_minutes=autopost.get("interval_minutes", 5),
        text=autopost.get("text", ""),
    )
    for cid_str, title in (autopost.get("chats", {}) or {}).items():
        await autopost_repo.upsert_chat(int(cid_str), title)

    assistant = _read_json(
        config.ASSISTANT_FILE,
        {
            "mode": "mention",
            "text": "",
            "delay": 3,
            "include": [],
            "exclude": [],
            "auto_detect": True,
            "manual_enabled": False,
        },
    )
    await assistant_repo.save_settings(
        mode=assistant.get("mode", "mention"),
        text=assistant.get("text", ""),
        delay_seconds=assistant.get("delay", 3),
        auto_detect=assistant.get("auto_detect", True),
        manual_enabled=assistant.get("manual_enabled", False),
    )
    await assistant_repo.replace_chat_rules(
        include=set(assistant.get("include", []) or []),
        exclude=set(assistant.get("exclude", []) or []),
    )

    font = _read_json(config.FONT_STATE_FILE, {"enabled": False, "style": "bold"})
    await font_repo.save_settings(enabled=font.get("enabled", False), style=font.get("style", "bold"))

    stats = _read_json(
        config.STATS_FILE,
        {
            "commands_total": 0,
            "commands_by_name": {},
            "messages_total": 0,
            "autopost_ok": 0,
            "autopost_fail": 0,
            "errors": 0,
            "per_chat": {},
        },
    )
    await stats_repo.save_snapshot(stats)


async def migrate() -> None:
    print("=== Migration: JSON -> PostgreSQL ===")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join("json_backup", ts)
    copied = backup_json_files(backup_dir)
    print(f"[1/4] بکاپ گرفته شد از {len(copied)} فایل -> {backup_dir}")

    before = count_json_records()
    print(f"[2/4] تعداد رکوردها قبل از migration: {before}")

    await _migrate_data()
    print("[3/4] داده‌ها به PostgreSQL منتقل شدن")

    after_notes = len(await notes_repo.get_all())
    after_autopost_chats = len(await autopost_repo.list_chats())
    after_rules = len(await assistant_repo.list_chat_rules())
    after_stats = await stats_repo.get_snapshot()

    after = {
        "notes": after_notes,
        "autopost_chats": after_autopost_chats,
        "assistant_chat_rules": after_rules,
        "font_settings": 1,
        "stats_commands": len(after_stats["commands_by_name"]),
        "stats_chats": len(after_stats["per_chat"]),
    }
    print(f"[4/4] تعداد رکوردها بعد از migration: {after}")

    mismatches = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    if mismatches:
        print("\n❌ عدم تطابق در شمارش رکوردها - migration ناقص/مشکوکه:")
        for k, (b, a) in mismatches.items():
            print(f"   {k}: قبل={b} بعد={a}")
        print(f"فایل‌های JSON اصلی دست‌نخورده موندن و از {backup_dir} هم بکاپ دارید.")
        print("هیچ‌چیزی از PostgreSQL پاک نشد - می‌تونی این اسکریپت رو دوباره اجرا کنی.")
        sys.exit(1)

    print("\n✅ Migration با موفقیت انجام شد و تعداد رکوردها قبل/بعد مطابقت داره.")
    print("   از این به بعد PostgreSQL منبع اصلیِ داده‌هاست؛ فایل‌های JSON فقط به‌عنوان بکاپ باقی می‌مونن.")


if __name__ == "__main__":
    asyncio.run(migrate())
