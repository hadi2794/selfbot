"""
بارگذاریِ اولیه‌ی همه‌ی state های دائمی از PostgreSQL، درست موقعِ بالا اومدنِ
پروسه (چه اجرای اول، چه بعد از Restart/Redeploy روی Railway).

⚠️ باید فقط و فقط یک‌بار، *قبل* از client.loop.create_task(...) برای
clock_updater/autopost_worker/assistant_status_watcher/stats_saver صدا زده
بشه؛ وگرنه اون تسک‌های پس‌زمینه با مقادیر پیش‌فرض (نه آخرین وضعیتِ ذخیره‌شده)
شروع به‌کار می‌کنن. main.py دقیقاً همین ترتیب رو رعایت می‌کنه.

چون در این پروژه همیشه فقط یک پروسه‌ی worker (طبق Procfile/railway.json)
اجرا می‌شه، همین یک‌بار-در-استارتاپ بارگذاری از PostgreSQL کافیه تا تسک‌های
پس‌زمینه بعد از هر Restart/Redeploy دقیقاً از همون وضعیتی که در PostgreSQL
ذخیره شده ادامه بدن و duplicate/state پریده‌ای رخ نده.
"""
import logging

from ..clock import init_clock_state
from ..storage.assistant_store import init_assistant_state
from ..storage.autopost_store import init_autopost_state
from ..storage.daily_digest_store import init_daily_digest_state
from ..storage.font_store import init_font_state
from ..storage.group_guard_store import init_group_guard_state
from ..storage.settings_toggles import init_settings_toggles
from ..storage.stats_store import init_stats

logger = logging.getLogger("selfbot.db")


async def load_all_persistent_state() -> None:
    await init_assistant_state()
    await init_autopost_state()
    await init_daily_digest_state()
    await init_font_state()
    await init_clock_state()
    await init_group_guard_state()
    await init_stats()
    await init_settings_toggles()
    logger.info(
        "همه‌ی وضعیت‌های دائمی (منشی/ارسال‌خودکار/خلاصه‌روز/فونت/ساعت/مدیریت‌گروه/آمار/سوییچ‌های سراسری) از PostgreSQL بارگذاری شدن"
    )
