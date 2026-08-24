# 🧩 Plugin System

The bot supports hot plugin installation, removal and reload.

## Commands

- `.پلاگین` — list loaded plugins
- `.پلاگین نصب <GitHub blob/raw URL>` — install a Python plugin at runtime
- `.پلاگین حذف <name>` — remove an installed plugin
- `.پلاگین reload <name>` — unload and load again without restarting

English aliases are also supported: `plugins`, `install`, `remove`, `reload`.

## Plugin format

A plugin can use the same Telethon pattern as built-in handlers:

```python
from bot.runtime import client
from telethon import events

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.hello$"))
async def hello(event):
    await event.edit("Hello from plugin ✅")

commands = ["hello"]

async def startup():
    pass

async def shutdown():
    pass
```

For clean hot-unload, the loader tracks callback functions defined by the plugin.
If a plugin registers handlers dynamically, put those callback functions in the
module-level `handlers` list.

## Railway persistence

Railway containers do not guarantee runtime-written files will survive a new
deployment. For persistent installed plugins, attach a Railway Volume and mount
it at `/data`, then set:

```text
PLUGIN_INSTALL_DIR=/data/plugins
```

The repository's built-in `plugins/` directory remains separate from installed
plugins, so the Volume does not hide the built-ins.

## Security

A Python plugin executes with the same privileges as the userbot. Only install
code you trust. The loader checks size, UTF-8 and Python syntax before loading,
but these checks are **not** a sandbox.
