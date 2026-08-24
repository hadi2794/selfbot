"""Plugin manager commands: list, install, remove and hot-reload plugins."""
import logging

from telethon import events

from ..config import PREFIX
from ..plugin_loader import (
    get_all_plugins,
    get_plugin_commands,
    install_plugin_from_github,
    load_plugin,
    remove_installed_plugin,
    unload_plugin,
)
from ..runtime import client
from ..utils import pat

logger = logging.getLogger("selfbot.handlers.plugins_cmd")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پلاگین", "plugins"])))
async def plugins_handler(event):
    args = (event.pattern_match.group(1) or "").strip()
    if not args:
        plugins = get_all_plugins()
        if not plugins:
            return await event.edit(
                "🧩 هیچ پلاگینی بارگذاری نشده.\n\n"
                f"نصب: `{PREFIX}پلاگین نصب <GitHub file URL>`"
            )
        lines = [f"🧩 **{len(plugins)} پلاگین فعال**", ""]
        commands_map = get_plugin_commands()
        for name, plugin in plugins.items():
            source = "نصب‌شده" if plugin.installed else "داخلی"
            cmds = commands_map.get(name)
            suffix = " — " + ", ".join(f"`{PREFIX}{c}`" for c in cmds) if cmds else ""
            lines.append(f"• `{name}` ({source}){suffix}")
        lines += ["", "**مدیریت:**", f"`{PREFIX}پلاگین نصب <url>`", f"`{PREFIX}پلاگین حذف <name>`", f"`{PREFIX}پلاگین reload <name>`"]
        return await event.edit("\n".join(lines))

    parts = args.split(maxsplit=1)
    action = parts[0].lower()
    value = parts[1].strip() if len(parts) > 1 else ""

    if action in ("نصب", "install"):
        if not value:
            return await event.edit(f"❌ استفاده: `{PREFIX}پلاگین نصب <GitHub file URL>`")
        await event.edit("📥 در حال دانلود و بررسی پلاگین...")
        ok, message, _ = await install_plugin_from_github(value)
        return await event.edit(("✅ " if ok else "❌ ") + message)

    if action in ("حذف", "remove", "uninstall"):
        if not value:
            return await event.edit(f"❌ استفاده: `{PREFIX}پلاگین حذف <name>`")
        ok = await remove_installed_plugin(value)
        return await event.edit("🗑️ پلاگین حذف شد و از حافظه خارج شد." if ok else "❌ پلاگین نصب‌شده‌ای با این نام پیدا نشد.")

    if action in ("reload", "بارگذاری", "بارگذاری_مجدد", "ریلود"):
        if not value:
            return await event.edit(f"❌ استفاده: `{PREFIX}پلاگین reload <name>`")
        was_loaded = await unload_plugin(value)
        if not was_loaded:
            return await event.edit("❌ این پلاگین فعال نیست.")
        plugin = await load_plugin(value)
        return await event.edit("🔄 پلاگین با موفقیت Reload شد." if plugin else "❌ Reload ناموفق بود؛ خطای پلاگین را در لاگ Railway ببین.")

    return await event.edit(
        f"❌ دستور ناشناخته.\n\n"
        f"`{PREFIX}پلاگین` — لیست\n"
        f"`{PREFIX}پلاگین نصب <url>` — نصب\n"
        f"`{PREFIX}پلاگین حذف <name>` — حذف\n"
        f"`{PREFIX}پلاگین reload <name>` — Reload"
    )
