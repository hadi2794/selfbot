"""
Telegram Selfbot (Userbot) - نسخه فارسی
ساخته‌شده با Telethon - نسخه‌ی ماژولار

نکات مهم امنیتی/قانونی:
- این اسکریپت با اکانت شخصی تلگرام شما وارد می‌شه (نه یک بات جدا از BotFather)
- فقط پیام‌هایی که خودتون (owner) بفرستید به‌عنوان دستور اجرا می‌شن
- استفاده افراطی از دستورات، مخصوصاً ساعت زنده با فاصله خیلی کم، یا اسپم و
  ادعای عضویت انبوه ممکنه باعث محدودیت اکانت توسط تلگرام بشه. مقادیر پیش‌فرض
  رعایت شده تا ریسک این موضوع کم باشه.
- دستورات مدیریتی (kick/ban/promote/demote) رو فقط توی گروه‌هایی که خودتون
  ادمین هستید استفاده کنید.

ساختار پروژه (ماژولار):
    bot/config.py            تنظیمات (از .env / متغیرهای محیطی Railway)
    bot/runtime.py           نمونه‌ی TelegramClient + سشن HTTP مشترک
    bot/utils.py             ساخت الگوی دستورات (pat)
    bot/calc.py              ماشین‌حساب امن
    bot/fonts.py             فونت‌های پیام
    bot/clock.py             ساعت زنده در نام پروفایل + تسک پس‌زمینه
    bot/db/                  اتصال PostgreSQL (SQLAlchemy async) + ORM models
    bot/repositories/        Repository/Database Layer (تنها لایه‌ای که SQL می‌زنه)
    bot/storage/             آداپتورهای async روی Repository Layer برای هر دامنه
    bot/handlers/            همه‌ی دستورات، دسته‌بندی‌شده بر اساس موضوع

⚠️ منبع اصلیِ داده‌های دائمی (Notes/Assistant/AutoPost/Statistics/Clock/
Profile Settings) از این به بعد PostgreSQL است، نه فایل JSON. فایل‌های JSON
قدیمی فقط برای اسکریپت یک‌بارِ migration (scripts/migrate_json_to_postgres.py)
و برای Import/Export دستیِ بکاپ (دستورهای `.پشتیبان تنظیمات` / `.بازیابی`)
استفاده می‌شن.
"""
from bot.logging_config import setup_logging

setup_logging()  # باید قبل از import هر ماژولی که logger می‌سازه صدا زده بشه

import logging

from bot import config
from bot.runtime import (
    client,
    bot_client,
    get_http_session,
    close_http_session,
    set_self_id,
    set_bot_username,
)
from bot.db.bootstrap import load_all_persistent_state
from bot.db.engine import dispose_engine
from bot.plugin_loader import load_all_plugins
from bot.clock import clock_updater
from bot.handlers.autopost import autopost_worker
from bot.handlers.assistant import assistant_status_watcher
from bot.handlers.daily_digest import daily_digest_worker
from bot.handlers.scheduler import scheduler_worker
from bot.handlers.stats import stats_saver

from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError

# فقط import کردنِ این پکیج کافیه تا همه‌ی دکوریتورهای @client.on ثبت بشن
from bot import handlers  # noqa: F401

logger = logging.getLogger("selfbot.main")


async def main():
    await get_http_session()  # ساخت ClientSession مشترک قبل از شروع کار

    # باید قبل از استارت شدنِ تسک‌های پس‌زمینه انجام بشه، وگرنه اون تسک‌ها با
    # مقادیر پیش‌فرض (نه آخرین وضعیتِ ذخیره‌شده در PostgreSQL) شروع می‌کنن.
    await load_all_persistent_state()

    # پلاگین‌های اختیاریِ کاربر (پوشه‌ی plugins/ کنارِ bot/) - اگه پوشه وجود
    # نداشته باشه یا خالی باشه، بدونِ خطا رد می‌شه؛ صرفاً یه قابلیتِ اختیاریه.
    loaded_plugins = await load_all_plugins()
    if loaded_plugins:
        logger.info("پلاگین‌های بارگذاری‌شده: %s", ", ".join(loaded_plugins.keys()))

    me = await client.get_me()
    set_self_id(me.id)
    logger.info("سلف‌بات با اکانت %s روشن شد", me.first_name)

    # بات کمکیِ پنل (اختیاری) - چون تلگرام دکمه‌های شیشه‌ای رو فقط برای
    # پیام‌های ارسالی از طرف یه بات واقعی نمایش می‌ده، دستور «.پنل» پنل
    # دکمه‌ای رو از طریق این بات (نه اکانت شخصی) نشون می‌ده.
    if bot_client is not None:
        await bot_client.start(bot_token=config.BOT_TOKEN)
        bot_me = await bot_client.get_me()
        set_bot_username(bot_me.username)
        logger.info("بات کمکیِ پنل به @%s وصل شد", bot_me.username)
        client.loop.create_task(bot_client.run_until_disconnected())
    else:
        logger.warning("BOT_TOKEN تنظیم نشده؛ «.پنل» فقط راهنما می‌ده (بقیه‌ی دستورات عادی کار می‌کنن)")

    client.loop.create_task(clock_updater())
    client.loop.create_task(autopost_worker())
    client.loop.create_task(assistant_status_watcher())
    client.loop.create_task(scheduler_worker())
    client.loop.create_task(daily_digest_worker())
    client.loop.create_task(stats_saver())
    try:
        await client.run_until_disconnected()
    finally:
        await close_http_session()
        if bot_client is not None:
            await bot_client.disconnect()
        await dispose_engine()


if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except AuthKeyDuplicatedError:
        # این یعنی SESSION_STRING هم‌زمان از دو IP متفاوت استفاده شده و
        # تلگرام برای همیشه باطلش کرده - ری‌استارتِ ساده حلش نمی‌کنه.
        # به‌جای کرش‌لوپِ سریع (که فشار اضافی روی سرورهای تلگرام می‌ذاره)،
        # یه پیام واضح می‌دیم و چند دقیقه قبل از خروج صبر می‌کنیم تا اگه
        # پلتفرم (مثل Railway) خودکار ری‌استارت می‌کنه، این‌قدر تند تکرار نشه.
        import time

        logger.critical(
            "سشن (SESSION_STRING) باطل شده: هم‌زمان از دو IP/جای مختلف استفاده شده.\n"
            "این خطا با ری‌استارتِ ساده حل نمی‌شه - باید یه سشن جدید بسازی:\n"
            "  ۱) روی سیستم خودت: python generate_session.py\n"
            "  ۲) SESSION_STRING جدید رو جای مقدار قبلی بذار\n"
            "  ۳) مطمئن شو همون سشن هم‌زمان جای دیگه‌ای (لوکال/دیپلوی دیگه) در حال اجرا نیست\n"
            "برای جلوگیری از اسپم لاگ/درخواست به تلگرام، ۳۰۰ ثانیه صبر می‌کنیم و بعد خارج می‌شیم..."
        )
        time.sleep(300)
        raise
