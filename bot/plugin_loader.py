"""
سیستم پلاگین - بارگذاری پویای ماژول‌ها
"""
import importlib
import logging
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger("selfbot.plugin_loader")

# پوشه پلاگین‌ها
PLUGIN_DIR = "plugins"

# پلاگین‌های بارگذاری‌شده
_loaded_plugins: Dict[str, Any] = {}


class Plugin:
    """نماینده یک پلاگین."""

    def __init__(self, name: str, module):
        self.name = name
        self.module = module
        self.commands = getattr(module, "commands", [])
        self.handlers = getattr(module, "handlers", [])
        self.config = getattr(module, "config", {})
        self.startup = getattr(module, "startup", None)
        self.shutdown = getattr(module, "shutdown", None)

    async def run_startup(self):
        if self.startup and callable(self.startup):
            await self.startup()

    async def run_shutdown(self):
        if self.shutdown and callable(self.shutdown):
            await self.shutdown()


def discover_plugins() -> List[str]:
    """یافتن پلاگین‌ها در پوشه plugins."""
    if not os.path.exists(PLUGIN_DIR):
        return []

    plugins = []
    for item in os.listdir(PLUGIN_DIR):
        if os.path.isdir(os.path.join(PLUGIN_DIR, item)):
            # بررسی وجود __init__.py
            init_path = os.path.join(PLUGIN_DIR, item, "__init__.py")
            if os.path.exists(init_path):
                plugins.append(item)
        elif item.endswith(".py") and item != "__init__.py":
            plugins.append(item[:-3])

    return plugins


async def load_plugin(name: str) -> Optional[Plugin]:
    """بارگذاری یک پلاگین."""
    try:
        module_path = f"{PLUGIN_DIR}.{name}" if not name.startswith(PLUGIN_DIR) else name
        module = importlib.import_module(module_path)

        plugin = Plugin(name, module)
        _loaded_plugins[name] = plugin

        # اجرای startup
        await plugin.run_startup()

        logger.info(f"پلاگین {name} بارگذاری شد")
        return plugin

    except Exception as e:
        logger.exception(f"خطا در بارگذاری پلاگین {name}: {e}")
        return None


async def load_all_plugins() -> Dict[str, Plugin]:
    """بارگذاری همه پلاگین‌ها."""
    plugin_names = discover_plugins()
    result = {}

    for name in plugin_names:
        plugin = await load_plugin(name)
        if plugin:
            result[name] = plugin

    return result


async def unload_plugin(name: str) -> bool:
    """بارگیری یک پلاگین."""
    if name not in _loaded_plugins:
        return False

    plugin = _loaded_plugins[name]
    await plugin.run_shutdown()

    del _loaded_plugins[name]
    logger.info(f"پلاگین {name} بارگیری شد")
    return True


def get_plugin(name: str) -> Optional[Plugin]:
    """دریافت یک پلاگین بارگذاری‌شده."""
    return _loaded_plugins.get(name)


def get_all_plugins() -> Dict[str, Plugin]:
    """دریافت همه پلاگین‌های بارگذاری‌شده."""
    return dict(_loaded_plugins)


def get_plugin_commands() -> Dict[str, List[str]]:
    """دریافت دستورات همه پلاگین‌ها."""
    result = {}
    for name, plugin in _loaded_plugins.items():
        if plugin.commands:
            result[name] = plugin.commands
    return result