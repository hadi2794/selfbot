"""
Storage لایه برای مدیریت state و کش قوانین اتوماسیون.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set

from ..repositories import automation_repo
from ..db.models_automation import AutomationRule

logger = logging.getLogger("selfbot.storage.automation_store")

# کش درون‌حافظه‌ای قوانین فعال
_rules_cache: Dict[int, AutomationRule] = {}
_cache_lock = asyncio.Lock()
_last_refresh: Optional[float] = None
_REFRESH_INTERVAL_SECONDS = 30  # هر ۳۰ ثانیه یک‌بار کش را به‌روز می‌کنیم


async def refresh_cache() -> None:
    """بارگذاری مجدد قوانین فعال از دیتابیس."""
    global _last_refresh
    async with _cache_lock:
        rules = await automation_repo.get_active_rules()
        _rules_cache.clear()
        for rule in rules:
            _rules_cache[rule.id] = rule
        _last_refresh = asyncio.get_event_loop().time()
        logger.info("کش قوانین اتوماسیون به‌روز شد (%d قانون فعال)", len(_rules_cache))


async def ensure_cache_fresh() -> None:
    """اطمینان از تازه بودن کش."""
    global _last_refresh
    if _last_refresh is None or asyncio.get_event_loop().time() - _last_refresh > _REFRESH_INTERVAL_SECONDS:
        await refresh_cache()


async def get_active_rules() -> List[AutomationRule]:
    """دریافت لیست قوانین فعال (از کش یا دیتابیس)."""
    await ensure_cache_fresh()
    async with _cache_lock:
        return list(_rules_cache.values())


async def get_rule(rule_id: int) -> Optional[AutomationRule]:
    """دریافت یک قانون خاص (از کش یا دیتابیس)."""
    await ensure_cache_fresh()
    async with _cache_lock:
        rule = _rules_cache.get(rule_id)
        if rule:
            return rule
    # اگر در کش نبود، از دیتابیس بخوان
    return await automation_repo.get_rule(rule_id)


async def invalidate_cache() -> None:
    """بی‌اعتبار کردن کش (بعد از تغییرات)."""
    global _last_refresh
    async with _cache_lock:
        _last_refresh = None
        _rules_cache.clear()
    await refresh_cache()


async def reload_rule(rule_id: int) -> None:
    """بارگذاری مجدد یک قانون خاص."""
    rule = await automation_repo.get_rule(rule_id)
    async with _cache_lock:
        if rule and rule.status == "active":
            _rules_cache[rule_id] = rule
        else:
            _rules_cache.pop(rule_id, None)