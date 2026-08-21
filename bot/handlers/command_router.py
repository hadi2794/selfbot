# -*- coding: utf-8 -*-
"""
Command router with AI intent detection for all selfbot commands.
"""
import asyncio
import datetime as dt
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from telethon import events

from .. import ai, runtime
from ..config import PREFIX
from ..runtime import client
from ..storage.notes_store import delete_note, load_notes, save_note
from ..storage.scheduler_store import create_job, delete_job, get_job, list_jobs
from ..storage.assistant_store import assistant_state, save_assistant
from ..storage.autopost_store import (
    autopost_state,
    save_autopost,
    add_autopost_chat,
    remove_autopost_chat,
    clear_autopost_chats,
    set_force_now,
    _reset_autopost_timer,
)
from ..storage.stats_store import STATS, reset_stats
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from .scheduler import _FULL_RE, _local_now, _to_utc_aware

logger = logging.getLogger("selfbot.handlers.command_router")
PENDING: Dict[int, Dict[str, Any]] = {}
_PENDING_TTL_SECONDS = 5 * 60

_ROUTER_SYSTEM_PROMPT = (
    "You are a command router for a Telegram selfbot. "
    "User writes a free-form sentence; you detect intent and extract parameters. "
    "Return ONLY raw JSON with this structure:\n"
    "{\n"
    '  "intent": "reminder" | "scheduler" | "note" | "assistant" | "autopost" | "stats" | "backup" | "unknown",\n'
    "  \"params\": { ... },\n"
    "  \"display_summary\": \"Short summary of what will be done\"\n"
    "}\n\n"
    "Rules:\n"
    "- Current local time of user: {now}\n"
    "- If intent is unclear -> \"unknown\".\n\n"
    "Intent: reminder -> params: \"time\" (YYYY-MM-DD HH:MM), \"text\"\n"
    "Intent: scheduler -> params: \"time\", \"text\"\n"
    "Intent: note -> params: \"action\" (save/list/delete/get), \"key\", \"text\"\n"
    "Intent: assistant -> params: \"mode\" (on/off/auto/mention/pm/groups), \"text\", \"delay\", \"ai\" (on/off), \"exclude\", \"include\", \"clear\"\n"
    "Intent: autopost -> params: \"action\" (on/off/text/interval/add/remove/clear/now), \"value\"\n"
    "Intent: stats -> params: \"action\" (summary/chats/reset)\n"
    "Intent: backup -> params: \"action\" (settings/chats/media/json), \"count\"\n"
    "Return only JSON, no extra text."
)

def _extract_json(raw: str) -> Optional[Dict]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None

def _parse_router_time(raw_time: str) -> Optional[Tuple[dt.datetime, str]]:
    if not isinstance(raw_time, str) or not raw_time.strip():
        return None
    m = _FULL_RE.match(raw_time.strip())
    if not m:
        return None
    date_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
    try:
        target_local = dt.datetime.strptime(date_part, "%Y-%m-%d").replace(hour=hh, minute=mm)
    except ValueError:
        return None
    if target_local <= _local_now():
        return None
    return _to_utc_aware(target_local), target_local.strftime("%Y-%m-%d %H:%M")

async def _handle_reminder(chat_id: int, params: Dict, event) -> dict:
    time_str = params.get("time")
    text = params.get("text", "").strip()
    parsed = _parse_router_time(time_str) if time_str else None
    if parsed is None or not text:
        return None
    run_at_utc, local_display = parsed
    self_id = runtime.SELF_ID or chat_id
    job = await create_job(self_id, text, run_at_utc, "reminder")
    return {"job_id": job.id, "summary": "Reminder for {}: {}".format(local_display, text)}

async def _handle_scheduler(chat_id: int, params: Dict, event) -> dict:
    time_str = params.get("time")
    text = params.get("text", "").strip()
    parsed = _parse_router_time(time_str) if time_str else None
    if parsed is None or not text:
        return None
    run_at_utc, local_display = parsed
    job = await create_job(chat_id, text, run_at_utc, "schedule")
    return {"job_id": job.id, "summary": "Scheduled for {}: {}".format(local_display, text)}

async def _handle_note(chat_id: int, params: Dict, event) -> dict:
    action = params.get("action", "save")
    if action == "list" or (action == "save" and not params.get("key")):
        notes = await load_notes()
        if not notes:
            return {"summary": "No notes found.", "immediate": True}
        lines = "\n".join("* `{}`".format(k) for k in notes)
        return {"summary": "Notes:\n{}".format(lines), "immediate": True}
    elif action == "delete" and params.get("key"):
        key = params["key"]
        notes = await load_notes()
        if key not in notes:
            return {"summary": "Note '{}' not found.".format(key), "immediate": True}
        await delete_note(key)
        return {"summary": "Note '{}' deleted.".format(key), "immediate": True}
    elif action == "get" and params.get("key"):
        key = params["key"]
        notes = await load_notes()
        if key not in notes:
            return {"summary": "Note '{}' not found.".format(key), "immediate": True}
        return {"summary": "{}:\n{}".format(key, notes[key]), "immediate": True}
    elif action == "save" and params.get("key") and params.get("text"):
        await save_note(params["key"], params["text"])
        return {"summary": "Note '{}' saved.".format(params["key"]), "immediate": True}
    return None

async def _handle_assistant(chat_id: int, params: Dict, event) -> dict:
    changes = []
    if "mode" in params:
        mode = params["mode"]
        if mode == "on":
            assistant_state["enabled"] = True
            assistant_state["auto_detect"] = False
            changes.append("on (manual)")
        elif mode == "off":
            assistant_state["enabled"] = False
            assistant_state["auto_detect"] = False
            changes.append("off (manual)")
        elif mode == "auto":
            assistant_state["auto_detect"] = True
            changes.append("auto mode")
        elif mode in ("mention", "pm", "groups"):
            assistant_state["mode"] = mode
            changes.append("mode: {}".format(mode))
    if "text" in params and params["text"]:
        assistant_state["text"] = params["text"]
        changes.append("reply text updated")
    if "delay" in params and isinstance(params["delay"], (int, float)):
        assistant_state["delay"] = max(0, int(params["delay"]))
        changes.append("delay: {}s".format(assistant_state["delay"]))
    if "ai" in params:
        if params["ai"] == "on":
            assistant_state["ai_mode"] = True
            changes.append("AI replies on")
        elif params["ai"] == "off":
            assistant_state["ai_mode"] = False
            changes.append("AI replies off")
    if params.get("exclude"):
        assistant_state["exclude"].add(chat_id)
        assistant_state["include"].discard(chat_id)
        changes.append("chat excluded")
    if params.get("include"):
        assistant_state["include"].add(chat_id)
        assistant_state["exclude"].discard(chat_id)
        changes.append("chat included")
    if params.get("clear"):
        assistant_state["include"].clear()
        assistant_state["exclude"].clear()
        changes.append("lists cleared")
    if not changes:
        return None
    await save_assistant()
    return {"summary": "OK: " + " | ".join(changes), "immediate": True}

async def _handle_autopost(chat_id: int, params: Dict, event) -> dict:
    action = params.get("action", "")
    value = params.get("value", "")
    if not action or action == "list" or action == "status" or action not in ("on", "off", "now", "clear", "text", "interval", "add", "remove"):
        status = "on" if autopost_state["enabled"] else "off"
        interval = autopost_state["interval_minutes"]
        chats = autopost_state["chats"]
        text_preview = autopost_state["text"] or "(not set)"
        chat_lines = "\n".join("  - {} (`{}`)".format(title, cid) for cid, title in chats.items()) if chats else "none"
        summary = "Autopost status: {}\nInterval: {} min\nText: {}\nChats: {}".format(status, interval, text_preview, chat_lines)
        return {"summary": summary, "immediate": True}
    if action in ("on", "off", "now", "clear", "text", "interval", "add", "remove"):
        if action == "on" and autopost_state["enabled"]:
            return {"summary": "Autopost is already on.", "immediate": True}
        if action == "on" and not autopost_state["text"]:
            return {"summary": "Set text first with 'autopost text <text>'.", "immediate": True}
        if action == "on" and not autopost_state["chats"]:
            return {"summary": "Add at least one chat first with 'autopost add'.", "immediate": True}
        if action == "on":
            autopost_state["enabled"] = True
            _reset_autopost_timer()
            await save_autopost()
            changes = ["turned on"]
        elif action == "off":
            autopost_state["enabled"] = False
            await save_autopost()
            changes = ["turned off"]
        elif action == "now":
            set_force_now(True)
            changes = ["force send queued"]
        elif action == "clear":
            await clear_autopost_chats()
            changes = ["chats cleared"]
        elif action == "text" and value:
            autopost_state["text"] = value
            await save_autopost()
            changes = ["text updated"]
        elif action == "interval" and value and value.isdigit():
            n = max(int(value), 1)
            autopost_state["interval_minutes"] = n
            _reset_autopost_timer()
            await save_autopost()
            changes = ["interval: {} min".format(n)]
        elif action == "add" and (value and value.lstrip('-').isdigit() or not value):
            cid = int(value) if value and value.lstrip('-').isdigit() else chat_id
            try:
                chat = await client.get_entity(cid)
                title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(cid)
                await add_autopost_chat(cid, title)
                changes = ["added chat: {}".format(title)]
            except Exception as e:
                return {"summary": "Error: {}".format(e), "immediate": True}
        elif action == "remove" and (value and value.lstrip('-').isdigit() or not value):
            cid = int(value) if value and value.lstrip('-').isdigit() else chat_id
            removed = await remove_autopost_chat(cid)
            if removed:
                changes = ["removed chat: {}".format(removed)]
            else:
                return {"summary": "Chat not in list.", "immediate": True}
        else:
            return None
        await save_autopost()
        return {"summary": "OK: " + " | ".join(changes), "immediate": True}
    return None

async def _handle_stats(chat_id: int, params: Dict, event) -> dict:
    action = params.get("action", "summary")
    if action == "summary" or not action:
        top_commands = sorted(STATS["commands_by_name"].items(), key=lambda kv: kv[1], reverse=True)[:5]
        cmd_lines = "\n".join("   {}. `{}` — {} times".format(i+1, name, n) for i, (name, n) in enumerate(top_commands)) if top_commands else "   (no commands yet)"
        per_chat = STATS["per_chat"]
        top_chats = sorted(per_chat.items(), key=lambda kv: kv[1]["messages"] + kv[1]["commands"], reverse=True)[:5]
        chat_lines = "\n".join(
            "   – {}: {} msgs, {} cmds".format(info.get('title') or cid, info['messages'], info['commands'])
            for cid, info in top_chats
        ) if top_chats else "   (no messages yet)"
        summary = (
            "Stats\n"
            "Commands executed: {}\n"
            "Messages processed: {}\n"
            "Autopost ok/fail: {}/{}\n"
            "System errors: {}\n\n"
            "Top commands:\n{}\n\n"
            "Top chats:\n{}"
        ).format(
            STATS['commands_total'],
            STATS['messages_total'],
            STATS['autopost_ok'],
            STATS['autopost_fail'],
            STATS['errors'],
            cmd_lines,
            chat_lines
        )
        return {"summary": summary, "immediate": True}
    elif action == "chats":
        per_chat = STATS["per_chat"]
        if not per_chat:
            return {"summary": "No stats for any chat yet.", "immediate": True}
        ordered = sorted(per_chat.items(), key=lambda kv: kv[1]["messages"] + kv[1]["commands"], reverse=True)[:20]
        lines = ["Chat stats:\n"]
        for cid, info in ordered:
            title = info.get("title")
            if not title:
                try:
                    chat = await client.get_entity(int(cid))
                    title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or cid
                    info["title"] = title
                except Exception:
                    title = cid
            lines.append(" - {}: {} msgs, {} cmds".format(title, info['messages'], info['commands']))
        return {"summary": "\n".join(lines), "immediate": True}
    elif action == "reset":
        await reset_stats()
        return {"summary": "Stats reset.", "immediate": True}
    return None

async def _handle_backup(chat_id: int, params: Dict, event) -> dict:
    return {
        "summary": (
            "For backup/restore, use direct commands:\n"
            "{}backup settings, {}backup chats, {}backup media, {}backup json\n"
            "or {}restore (reply to a backup file)"
        ).format(PREFIX, PREFIX, PREFIX, PREFIX, PREFIX),
        "immediate": True
    }

_INTENT_HANDLERS = {
    "reminder": _handle_reminder,
    "scheduler": _handle_scheduler,
    "note": _handle_note,
    "assistant": _handle_assistant,
    "autopost": _handle_autopost,
    "stats": _handle_stats,
    "backup": _handle_backup,
}

async def _confirm(event, chat_id: int):
    pending = PENDING.get(chat_id)
    if pending is None:
        return await event.edit("Nothing to confirm. Send `{}ai <sentence>` first.".format(PREFIX))
    if time.monotonic() - pending["created_at"] > _PENDING_TTL_SECONDS:
        PENDING.pop(chat_id, None)
        return await event.edit("This suggestion expired.")
    handler = _INTENT_HANDLERS.get(pending["intent"])
    if handler is None:
        PENDING.pop(chat_id, None)
        return await event.edit("Error: unknown intent.")
    try:
        result = await handler(chat_id, pending["params"], event)
    except Exception as e:
        _record_error()
        logger.exception("Error executing intent %s", pending["intent"])
        return await event.edit("Error: {}".format(e))
    PENDING.pop(chat_id, None)
    if result is None:
        return await event.edit("Action not executable (missing parameters).")
    if isinstance(result, dict) and result.get("immediate"):
        await event.edit(result["summary"])
    else:
        await event.edit("Done: " + result.get("summary", ""))
    if isinstance(result, dict) and "job_id" in result:
        await event.reply(
            "To cancel: `{}reminder cancel {}` or `{}scheduler cancel {}`".format(PREFIX, result['job_id'], PREFIX, result['job_id'])
        )

@client.on(events.NewMessage(outgoing=True, pattern=pat(["ai", "ai_router"])))
async def command_router_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    chat_id = event.chat_id
    sub = arg.split(maxsplit=1)[0].lower() if arg else ""
    if sub in ("confirm", "ok"):
        return await _confirm(event, chat_id)
    if sub in ("cancel"):
        if PENDING.pop(chat_id, None) is not None:
            return await event.edit("Cancelled.")
        return await event.edit("Nothing to cancel.")
    if not arg:
        return await event.edit(
            "AI Command Router\n\n"
            "Write your sentence naturally. I'll detect the command and ask for confirmation before executing.\n\n"
            "Examples:\n"
            "• `{}ai remind me tomorrow at 9am to call Ali` -> reminder\n"
            "• `{}ai note shopping: milk and bread` -> note\n"
            "• `{}ai turn assistant on` -> assistant\n"
            "• `{}ai turn autopost off` -> autopost\n"
            "• `{}ai show stats` -> stats\n\n"
            "After detection, use `{}ai confirm` to execute or `{}ai cancel` to cancel."
        ).format(PREFIX, PREFIX, PREFIX, PREFIX, PREFIX, PREFIX, PREFIX)
    await event.edit("Detecting command...")
    messages = [
        {"role": "system", "content": _ROUTER_SYSTEM_PROMPT.format(now=_local_now().strftime("%Y-%m-%d %H:%M"))},
        {"role": "user", "content": arg},
    ]
    try:
        answer = await ai.ask_ai(messages, max_tokens=400)
    except ai.AIDisabledError:
        return await event.edit("AI disabled. Set `AI_API_KEY`.")
    except ai.AIRequestError as e:
        _record_error()
        return await event.edit("AI error: {}".format(e))
    data = _extract_json(answer)
    if not data or not isinstance(data, dict):
        return await event.edit(
            "Could not detect command. Try being more specific.\n"
            "Example: `{}ai remind me tomorrow at 9am to call Ali`".format(PREFIX)
        )
    intent = data.get("intent", "unknown")
    params = data.get("params", {})
    display_summary = data.get("display_summary", "")
    if intent == "unknown" or not params:
        return await event.edit(
            "Could not confidently detect the command. Try being more specific."
        )
    PENDING[chat_id] = {"intent": intent, "params": params, "created_at": time.monotonic()}
    await event.edit(
        "Detected: `{}`\n\n"
        "{}\n\n"
        "Confirm: `{}ai confirm`  •  Cancel: `{}ai cancel`"
    ).format(intent, display_summary, PREFIX, PREFIX)