"""
وضعیتِ زمانِ‌اجرا: نمونه‌ی TelegramClient، سشن مشترک HTTP، و اطلاعاتی که فقط
موقع اتصال (main()) پر می‌شن. همه‌ی ماژول‌های دیگه از اینجا `client` رو
import می‌کنن.
"""
import time
import aiohttp
from telethon import TelegramClient

from . import config

if config.SESSION_STRING:
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(config.SESSION_STRING), config.API_ID, config.API_HASH)
else:
    client = TelegramClient("selfbot_session", config.API_ID, config.API_HASH)

# بات کمکیِ پنل (اختیاری) - فقط اگه BOT_TOKEN ست شده باشه ساخته می‌شه.
# نکته: این کلاینت هنوز به تلگرام وصل نیست؛ فقط توی main() با bot_client.start()
# با bot_token لاگین/وصل می‌شه. تا اون موقع bot_client غیر None ولی قطعه.
bot_client = (
    TelegramClient("selfbot_panel_bot", config.API_ID, config.API_HASH)
    if config.BOT_TOKEN
    else None
)

START_TIME = time.time()
SELF_ID = None  # توی main() موقع اتصال پر می‌شه
BOT_USERNAME = None  # توی main() بعد از وصل‌شدنِ bot_client پر می‌شه

HTTP_SESSION: "aiohttp.ClientSession | None" = None  # توی main() ساخته می‌شه


async def get_http_session() -> aiohttp.ClientSession:
    """یک aiohttp.ClientSession مشترک برمی‌گردونه (اگه هنوز ساخته نشده، می‌سازدش)."""
    global HTTP_SESSION
    if HTTP_SESSION is None or HTTP_SESSION.closed:
        HTTP_SESSION = aiohttp.ClientSession()
    return HTTP_SESSION


async def close_http_session():
    if HTTP_SESSION is not None and not HTTP_SESSION.closed:
        await HTTP_SESSION.close()


def set_self_id(user_id: int):
    global SELF_ID
    SELF_ID = user_id


def set_bot_username(username: str):
    global BOT_USERNAME
    BOT_USERNAME = username
