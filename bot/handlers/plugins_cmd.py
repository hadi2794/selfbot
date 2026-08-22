"""
دستورِ .پلاگین - نمایشِ پلاگین‌هایی که موقعِ استارتاپ از پوشه‌ی plugins/
بارگذاری شدن (bot/plugin_loader.py). خودِ بارگذاری فقط یه‌بار موقعِ بالا
اومدنِ پروسه انجام می‌شه (main.py)؛ این دستور صرفاً برای دیدنِ وضعیتشونه.
"""
import logging

from telethon import events

from ..config import PREFIX
from ..plugin_loader import get_all_plugins, get_plugin_commands
from ..runtime import client
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.plugins_cmd")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پلاگین", "plugins"])))
async def plugins_handler(event):
    plugins = get_all_plugins()
    if not plugins:
        return await event.edit(
            "🧩 هیچ پلاگینی بارگذاری نشده.\n\n"
            "برای اضافه‌کردنِ یه پلاگین: یه فایلِ `.py` توی پوشه‌ی `plugins/` "
            "بذار (کنارِ `bot/`) و ربات رو ری‌استارت کن - راهنمای کامل: `plugins/README.md`."
        )

    lines = [f"🧩 **{len(plugins)} پلاگینِ بارگذاری‌شده**", ""]
    commands_map = get_plugin_commands()
    for name in plugins:
        cmds = commands_map.get(name)
        if cmds:
            lines.append(f"• `{name}` — دستورها: " + ", ".join(f"`{PREFIX}{c}`" for c in cmds))
        else:
            lines.append(f"• `{name}`")
    lines.append("")
    lines.append("⚠️ برای اضافه/حذفِ پلاگین باید ربات ری‌استارت بشه (بارگذاری فقط موقعِ استارتاپ انجام می‌شه).")

    await event.edit("\n".join(lines))
