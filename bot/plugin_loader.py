"""Dynamic plugin manager with hot install/remove/reload support.

Built-in plugins live in ``plugins/``. Plugins installed at runtime live in
``PLUGIN_INSTALL_DIR`` (set this to a Railway Volume path such as /data/plugins
for persistence across deploys/restarts).
"""
import ast
import hashlib
import importlib
import importlib.util
import inspect
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from .runtime import get_http_session

logger = logging.getLogger("selfbot.plugin_loader")

BUILTIN_PLUGIN_DIR = Path(os.getenv("PLUGIN_DIR", "plugins")).resolve()
# Runtime-installed plugins should normally point to a Railway Volume, e.g. /data/plugins.
PLUGIN_INSTALL_DIR = Path(os.getenv("PLUGIN_INSTALL_DIR", "plugins_installed")).resolve()
MAX_PLUGIN_BYTES = int(os.getenv("PLUGIN_MAX_BYTES", str(512 * 1024)))

_loaded_plugins: Dict[str, "Plugin"] = {}


def _safe_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("._-")
    return name[:80] or "plugin"


def _module_key(name: str, installed: bool) -> str:
    return f"selfbot_installed_{name}" if installed else f"plugins.{name}"


class Plugin:
    def __init__(self, name: str, module: ModuleType, path: Path, installed: bool = False):
        self.name = name
        self.module = module
        self.path = path
        self.installed = installed
        self.commands = getattr(module, "commands", [])
        self.handlers = list(getattr(module, "handlers", []) or [])
        self.config = getattr(module, "config", {})
        self.startup = getattr(module, "startup", None)
        self.shutdown = getattr(module, "shutdown", None)
        self._registered_callbacks = self._collect_callbacks()

    def _collect_callbacks(self):
        callbacks = []
        for value in vars(self.module).values():
            if callable(value) and getattr(value, "__module__", None) == self.module.__name__:
                callbacks.append(value)
        for value in self.handlers:
            if callable(value) and value not in callbacks:
                callbacks.append(value)
        return callbacks

    async def run_startup(self):
        if self.startup and callable(self.startup):
            result = self.startup()
            if inspect.isawaitable(result):
                await result

    async def run_shutdown(self):
        if self.shutdown and callable(self.shutdown):
            result = self.shutdown()
            if inspect.isawaitable(result):
                await result


def _discover_dir(directory: Path) -> List[Tuple[str, Path, bool]]:
    if not directory.exists():
        return []
    result = []
    for item in directory.iterdir():
        if item.name.startswith("_"):
            continue
        if item.is_file() and item.suffix == ".py":
            result.append((item.stem, item, directory != BUILTIN_PLUGIN_DIR))
        elif item.is_dir() and (item / "__init__.py").exists():
            result.append((item.name, item, directory != BUILTIN_PLUGIN_DIR))
    return result


def discover_plugins() -> List[str]:
    """Return unique plugin names from built-in and installed directories."""
    names = []
    seen = set()
    for directory in (BUILTIN_PLUGIN_DIR, PLUGIN_INSTALL_DIR):
        for name, _, _ in _discover_dir(directory):
            if name not in seen:
                names.append(name)
                seen.add(name)
    return names


def _find_plugin(name: str) -> Optional[Tuple[Path, bool]]:
    safe = _safe_name(name)
    for directory, installed in ((PLUGIN_INSTALL_DIR, True), (BUILTIN_PLUGIN_DIR, False)):
        for candidate in (directory / f"{safe}.py", directory / safe):
            if candidate.is_file() and (candidate.suffix == ".py"):
                return candidate, installed
            if candidate.is_dir() and (candidate / "__init__.py").exists():
                return candidate, installed
    return None


def _load_module(name: str, path: Path, installed: bool) -> ModuleType:
    module_name = _module_key(name, installed)
    # Fresh import is important for reload.
    sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    source = path / "__init__.py" if path.is_dir() else path
    spec = importlib.util.spec_from_file_location(
        module_name,
        source,
        submodule_search_locations=[str(path)] if path.is_dir() else None,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


async def load_plugin(name: str) -> Optional[Plugin]:
    found = _find_plugin(name)
    if not found:
        logger.warning("Plugin not found: %s", name)
        return None
    path, installed = found
    try:
        # Avoid duplicate registrations on repeated load.
        if name in _loaded_plugins:
            await unload_plugin(name)
        module = _load_module(name, path, installed)
        plugin = Plugin(name, module, path, installed)
        _loaded_plugins[name] = plugin
        await plugin.run_startup()
        logger.info("Plugin loaded: %s (%s)", name, path)
        return plugin
    except Exception as exc:
        logger.exception("Error loading plugin %s: %s", name, exc)
        sys.modules.pop(_module_key(name, installed), None)
        return None


async def load_all_plugins() -> Dict[str, Plugin]:
    result = {}
    for name in discover_plugins():
        plugin = await load_plugin(name)
        if plugin:
            result[name] = plugin
    return result


async def unload_plugin(name: str) -> bool:
    plugin = _loaded_plugins.get(name)
    if not plugin:
        return False
    try:
        await plugin.run_shutdown()
    finally:
        # Telethon's public API lets us unregister the callbacks that were
        # registered with @client.on. This makes hot reload/removal possible.
        try:
            from .runtime import client
            for callback in plugin._registered_callbacks:
                try:
                    client.remove_event_handler(callback)
                except Exception:
                    logger.debug("Could not unregister callback %r", callback, exc_info=True)
        finally:
            _loaded_plugins.pop(name, None)
            sys.modules.pop(plugin.module.__name__, None)
    logger.info("Plugin unloaded: %s", name)
    return True


async def remove_installed_plugin(name: str) -> bool:
    # Installed plugins are always registered under their sanitized name (see
    # install_plugin_from_github), but a user can type the name with the
    # original punctuation/spacing from the source filename. Without this
    # normalization, _loaded_plugins.get(name) misses, the code below still
    # finds and deletes the file via _find_plugin's own sanitization, and the
    # plugin is left "loaded" in memory (handlers still registered) even
    # though its file is gone.
    name = _safe_name(name)
    plugin = _loaded_plugins.get(name)
    if plugin:
        if not plugin.installed:
            return False
        await unload_plugin(name)
    found = _find_plugin(name)
    if not found or not found[1]:
        return False
    path, _ = found
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    logger.info("Plugin removed: %s", name)
    return True


def _github_raw_url(url: str) -> Optional[str]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc == "raw.githubusercontent.com":
        return url.strip()
    if parsed.netloc not in ("github.com", "www.github.com"):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 5 and parts[2] == "blob":
        owner, repo, _, branch = parts[:4]
        file_path = "/".join(parts[4:])
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
    return None


async def install_plugin_from_github(url: str) -> Tuple[bool, str, Optional[Plugin]]:
    """Download a single Python plugin from a GitHub raw/blob URL and load it."""
    raw_url = _github_raw_url(url)
    if not raw_url:
        return False, "لینک باید لینک فایل `.py` در GitHub (blob یا raw) باشد.", None

    session = await get_http_session()
    try:
        async with session.get(raw_url, timeout=30) as response:
            if response.status != 200:
                return False, f"دانلود ناموفق بود (HTTP {response.status}).", None
            data = await response.read()
            content_type = response.headers.get("Content-Type", "")
    except Exception as exc:
        logger.exception("GitHub download failed: %s", exc)
        return False, f"خطا در دانلود: {exc}", None

    if len(data) > MAX_PLUGIN_BYTES:
        return False, f"فایل بیش از حد بزرگ است (حداکثر {MAX_PLUGIN_BYTES // 1024}KB).", None
    try:
        text = data.decode("utf-8")
        ast.parse(text)
    except UnicodeDecodeError:
        return False, "فایل UTF-8 معتبر نیست.", None
    except SyntaxError as exc:
        return False, f"کد Python معتبر نیست: خط {exc.lineno}.", None

    parsed = urlparse(raw_url)
    filename = Path(parsed.path).name
    name = _safe_name(Path(filename).stem)
    if not name or name.startswith("__"):
        return False, "نام پلاگین معتبر نیست.", None

    PLUGIN_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    destination = PLUGIN_INSTALL_DIR / f"{name}.py"
    backup = destination.with_suffix(".py.bak")
    if destination.exists():
        shutil.copy2(destination, backup)

    destination.write_bytes(data)
    plugin = await load_plugin(name)
    if not plugin:
        # Roll back a failed update.
        if backup.exists():
            backup.replace(destination)
            await load_plugin(name)
        else:
            destination.unlink(missing_ok=True)
        return False, "پلاگین دانلود شد ولی هنگام Load خطا داد؛ نصب برگردانده شد.", None
    backup.unlink(missing_ok=True)

    digest = hashlib.sha256(data).hexdigest()[:12]
    logger.info("Installed plugin %s sha256=%s content-type=%s", name, digest, content_type)
    return True, f"پلاگین `{name}` نصب شد. SHA256: `{digest}`", plugin


def get_plugin(name: str) -> Optional[Plugin]:
    return _loaded_plugins.get(name)


def get_all_plugins() -> Dict[str, Plugin]:
    return dict(_loaded_plugins)


def get_plugin_commands() -> Dict[str, List[str]]:
    return {name: plugin.commands for name, plugin in _loaded_plugins.items() if plugin.commands}
