"""
ثبت تمام هندلرهای دستورات سلف‌بات.
هر فایل جدید باید در اینجا import شود تا دکوریتورهای @client.on فعال شوند.
"""

# هندلرهای اصلی
from . import (
    admin,
    ai,
    assistant,
    audio,
    autopost,
    backup,
    command_router,
    daily_digest,
    font,
    fun,
    general,
    groupguard,
    help,
    media,
    messages,
    notes,
    ocr,
    panel,
    profile,
    scheduler,
    stats,
    tools,
)

# هندلرهای جدید (v9.3+)
from . import (
    health,
    settings_center,
    inbox,
    smart_reply,
    ai_memory,
    user_profile,
    global_search,
    notifications,
    automation,
    plugins_cmd,
)