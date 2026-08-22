"""
Repository برای قوانین اتوماسیون (Automation Rules).
"""

from sqlalchemy import select, update, delete
from typing import List, Optional, Dict, Any
import json

from ..db.engine import session_scope
from ..db.models_ext import AutomationRule


async def create_rule(
    name: str,
    event_type: str,
    action_type: str,
    action_value: str,
    event_value: Optional[str] = None,
    condition: Optional[str] = None,
    priority: int = 0,
    enabled: bool = True,
) -> AutomationRule:
    """ایجاد قانون اتوماسیون جدید."""
    async with session_scope() as session:
        rule = AutomationRule(
            name=name,
            enabled=enabled,
            event_type=event_type,
            event_value=event_value,
            condition=condition,
            action_type=action_type,
            action_value=action_value,
            priority=priority,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def get_rules(
    enabled_only: bool = True,
    event_type: Optional[str] = None,
) -> List[AutomationRule]:
    """دریافت قوانین اتوماسیون."""
    async with session_scope() as session:
        stmt = select(AutomationRule)
        if enabled_only:
            stmt = stmt.where(AutomationRule.enabled == True)
        if event_type:
            stmt = stmt.where(AutomationRule.event_type == event_type)
        stmt = stmt.order_by(AutomationRule.priority.desc(), AutomationRule.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_rule(rule_id: int) -> Optional[AutomationRule]:
    """دریافت یک قانون با ID."""
    async with session_scope() as session:
        stmt = select(AutomationRule).where(AutomationRule.id == rule_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def update_rule(rule_id: int, **kwargs) -> Optional[AutomationRule]:
    """بروزرسانی قانون."""
    async with session_scope() as session:
        stmt = select(AutomationRule).where(AutomationRule.id == rule_id)
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            return None
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        await session.commit()
        await session.refresh(rule)
        return rule


async def delete_rule(rule_id: int) -> bool:
    """حذف قانون."""
    async with session_scope() as session:
        stmt = delete(AutomationRule).where(AutomationRule.id == rule_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def toggle_rule(rule_id: int, enabled: bool) -> bool:
    """فعال/غیرفعال کردن قانون."""
    async with session_scope() as session:
        stmt = update(AutomationRule).where(AutomationRule.id == rule_id).values(enabled=enabled)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def get_rules_for_event(event_type: str, context: Dict[str, Any]) -> List[AutomationRule]:
    """دریافت قوانین مناسب برای یک رویداد خاص."""
    rules = await get_rules(enabled_only=True, event_type=event_type)
    # می‌توان فیلتر بر اساس شرط را اینجا پیاده‌سازی کرد
    return rules