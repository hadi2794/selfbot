"""
Repository برای قوانین اعلان (Notification Rules).
"""

from sqlalchemy import select, update, delete
from typing import List, Optional

from ..db.engine import session_scope
from ..db.models_ext import NotificationRule


async def create_rule(
    name: str,
    trigger_type: str,
    trigger_value: str,
    action_type: str,
    action_value: Optional[str] = None,
    enabled: bool = True,
) -> NotificationRule:
    """ایجاد قانون اعلان جدید."""
    async with session_scope() as session:
        rule = NotificationRule(
            name=name,
            enabled=enabled,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            action_type=action_type,
            action_value=action_value,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def get_rules(enabled_only: bool = True) -> List[NotificationRule]:
    """دریافت لیست قوانین."""
    async with session_scope() as session:
        stmt = select(NotificationRule)
        if enabled_only:
            stmt = stmt.where(NotificationRule.enabled == True)
        stmt = stmt.order_by(NotificationRule.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_rule(rule_id: int) -> Optional[NotificationRule]:
    """دریافت یک قانون با ID."""
    async with session_scope() as session:
        stmt = select(NotificationRule).where(NotificationRule.id == rule_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def update_rule(rule_id: int, **kwargs) -> Optional[NotificationRule]:
    """بروزرسانی قانون."""
    async with session_scope() as session:
        stmt = select(NotificationRule).where(NotificationRule.id == rule_id)
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
        stmt = delete(NotificationRule).where(NotificationRule.id == rule_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def toggle_rule(rule_id: int, enabled: bool) -> bool:
    """فعال/غیرفعال کردن قانون."""
    async with session_scope() as session:
        stmt = update(NotificationRule).where(NotificationRule.id == rule_id).values(enabled=enabled)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0