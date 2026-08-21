"""
موتور پس‌زمینهٔ اتوماسیون - بررسی و اجرای قوانین.
"""

import asyncio
import datetime as dt
import logging
import re
from typing import Any, Dict, Optional

from telethon import events

from .. import ai, runtime
from ..config import PREFIX, TIMEZONE_OFFSET
from ..runtime import client
from ..storage.automation_store import get_active_rules, reload_rule, invalidate_cache
from ..storage.notes_store import save_note
from ..storage.scheduler_store import create_job
from ..storage.stats_store import STATS, record_error as _record_error
from ..repositories import automation_repo
from ..handlers.scheduler import parse_time, _local_now

logger = logging.getLogger("selfbot.handlers.automation_engine")

# کش آخرین اجراها برای جلوگیری از اجرای مکرر (cooldown)
_last_execution_cache: Dict[int, float] = {}

# --- توابع کمکی برای اجرای عمل‌ها ---

async def _execute_action(rule, event, chat_id: int) -> str:
    """اجرای عمل یک قانون و بازگشت نتیجه."""
    action_type = rule.action_type
    params = rule.action_params or {}
    
    if action_type == "reply":
        text = params.get("text", "")
        if event and hasattr(event, "reply"):
            await event.reply(text)
            return f"پاسخ داده شد: {text[:50]}..."
        else:
            await client.send_message(chat_id, text)
            return f"پیام ارسال شد: {text[:50]}..."
    
    elif action_type == "message":
        text = params.get("text", "")
        target = params.get("target", chat_id)
        await client.send_message(target, text)
        return f"پیام به {target} ارسال شد"
    
    elif action_type == "note":
        key = params.get("key", f"auto_{rule.id}")
        text = params.get("text", "")
        await save_note(key, text)
        return f"یادداشت {key} ذخیره شد"
    
    elif action_type == "reminder":
        time_str = params.get("time", "")
        text = params.get("text", "")
        parsed = parse_time(time_str)
        if parsed is None:
            return "زمان یادآوری نامعتبر"
        run_at_utc, _ = parsed
        self_id = runtime.SELF_ID or chat_id
        job = await create_job(self_id, text, run_at_utc, "reminder")
        return f"یادآوری ثبت شد (شناسه {job.id})"
    
    elif action_type == "assistant":
        from ..storage.assistant_store import assistant_state, save_assistant
        mode = params.get("mode", "toggle")
        if mode == "on":
            assistant_state["enabled"] = True
            assistant_state["auto_detect"] = False
        elif mode == "off":
            assistant_state["enabled"] = False
            assistant_state["auto_detect"] = False
        elif mode == "auto":
            assistant_state["auto_detect"] = True
        elif mode == "toggle":
            assistant_state["enabled"] = not assistant_state["enabled"]
        await save_assistant()
        return f"منشی: {mode}"
    
    elif action_type == "autopost":
        from ..storage.autopost_store import autopost_state, save_autopost, _reset_autopost_timer, set_force_now
        action = params.get("action", "toggle")
        if action == "on":
            autopost_state["enabled"] = True
            _reset_autopost_timer()
        elif action == "off":
            autopost_state["enabled"] = False
        elif action == "toggle":
            autopost_state["enabled"] = not autopost_state["enabled"]
            if autopost_state["enabled"]:
                _reset_autopost_timer()
        elif action == "now":
            set_force_now(True)
        await save_autopost()
        return f"ارسال خودکار: {action}"
    
    elif action_type == "stats":
        from ..handlers.stats import _stats_summary_text
        return _stats_summary_text()
    
    elif action_type == "ai":
        question = params.get("text", "")
        if not question:
            return "سوالی برای هوش مصنوعی وارد نشده"
        messages = [
            {"role": "system", "content": "شما یک دستیار هوشمند هستید که به سوالات کاربر پاسخ می‌دهید."},
            {"role": "user", "content": question},
        ]
        try:
            answer = await ai.ask_ai(messages, max_tokens=300)
            return f"AI: {answer[:200]}..."
        except Exception as e:
            return f"خطای AI: {e}"
    
    elif action_type == "webhook":
        import aiohttp
        url = params.get("url", "")
        if not url:
            return "URL مشخص نشده"
        payload = params.get("payload", {})
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                return f"Webhook: {resp.status}"
    
    return "عمل ناشناخته"

# --- تابع اصلی بررسی قوانین ---

async def _check_and_execute_rules(trigger_type: str, event=None, chat_id: int = None, context: dict = None):
    """بررسی و اجرای قوانین مربوط به یک رویداد."""
    try:
        rules = await get_active_rules()
        now = dt.datetime.now(dt.timezone.utc)
        
        for rule in rules:
            if rule.trigger_type != trigger_type:
                continue
            
            # بررسی cooldown
            last_run = _last_execution_cache.get(rule.id, 0)
            if now.timestamp() - last_run < rule.cooldown_seconds:
                continue
            
            # بررسی max_executions
            if rule.max_executions is not None and rule.executions_count >= rule.max_executions:
                continue
            
            # بررسی فیلترها
            if rule.trigger_filter and event:
                filter_data = rule.trigger_filter
                # فیلتر بر اساس متن
                if "pattern" in filter_data:
                    pattern = filter_data["pattern"]
                    text = event.raw_text or ""
                    if not re.search(pattern, text, re.IGNORECASE):
                        continue
                # فیلتر بر اساس chat_id
                if "chat_id" in filter_data:
                    if str(event.chat_id) != str(filter_data["chat_id"]):
                        continue
                # فیلتر بر اساس sender_id
                if "sender_id" in filter_data:
                    if event.sender_id != filter_data["sender_id"]:
                        continue
            
            # اجرای عمل
            try:
                result = await _execute_action(rule, event, chat_id or event.chat_id)
                logger.info("قانون %s (%s) اجرا شد: %s", rule.id, rule.name, result)
                await automation_repo.increment_executions(rule.id)
                _last_execution_cache[rule.id] = now.timestamp()
                await reload_rule(rule.id)
            except Exception as e:
                logger.exception("خطا در اجرای قانون %s", rule.id)
                _record_error()
                
    except Exception as e:
        logger.exception("خطا در موتور اتوماسیون")
        _record_error()

# --- هندلرهای رویدادها ---

@client.on(events.NewMessage(incoming=True))
async def automation_message_handler(event):
    """بررسی قوانین برای پیام‌های ورودی."""
    sender_id = event.sender_id
    if sender_id is None or sender_id == runtime.SELF_ID:
        return  # پیام‌های خودمان را نادیده بگیر
    
    chat_id = event.chat_id
    text = event.raw_text or ""
    
    # تشخیص نوع رویداد
    trigger = "message"
    if event.is_private:
        trigger = "message"  # پیوی
    elif event.is_group:
        if getattr(event.message, "mentioned", False):
            trigger = "mention"
        else:
            trigger = "message"
    
    await _check_and_execute_rules(trigger, event, chat_id)

@client.on(events.NewMessage(outgoing=True, pattern=re.compile(rf"^{PREFIX}.*")))
async def automation_command_handler(event):
    """بررسی قوانین برای دستورات خروجی."""
    chat_id = event.chat_id
    await _check_and_execute_rules("command", event, chat_id)

# --- تسک زمان‌بندی‌شده ---

async def automation_scheduler_worker():
    """کارگر زمان‌بندی - هر دقیقه قوانین schedule را بررسی می‌کند."""
    import asyncio
    import datetime as dt
    from croniter import croniter
    
    while True:
        await asyncio.sleep(60)  # هر دقیقه یک‌بار
        
        try:
            rules = await get_active_rules()
            now_local = _local_now()
            
            for rule in rules:
                if rule.trigger_type != "schedule":
                    continue
                if not rule.schedule_cron:
                    continue
                
                # بررسی زمان‌بندی
                try:
                    cron = croniter(rule.schedule_cron, now_local)
                    next_run = cron.get_next(dt.datetime)
                    if abs((next_run - now_local).total_seconds()) < 120:  # +/- 2 دقیقه
                        await _execute_action(rule, None, runtime.SELF_ID or 0)
                        await automation_repo.increment_executions(rule.id)
                        _last_execution_cache[rule.id] = dt.datetime.now(dt.timezone.utc).timestamp()
                        await reload_rule(rule.id)
                except Exception as e:
                    logger.exception("خطا در زمان‌بندی قانون %s", rule.id)
                    
        except Exception as e:
            logger.exception("خطا در کارگر زمان‌بندی اتوماسیون")
            _record_error()