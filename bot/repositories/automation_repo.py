"""
Repository برای دسترسی به قوانین اتوماسیون در PostgreSQL.
"""

import datetime as dt
import logging
from typing import List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models_automation import AutomationRule
from ..db.engine import async_session_factory

logger = logging.getLogger("selfbot.repositories.automation_repo")


async def create_rule(
    name: str,
    trigger_type: str,
    action_type: str,
    description: str | None = None,
    trigger_filter: dict | None = None,
    action_params: dict | None = None,
    schedule_cron: str | None = None,
    schedule_timezone: str | None = None,
    cooldown_seconds: int = 0,
    max_executions: int | None = None,
    status: str = "active",
) -> AutomationRule:
    """ایجاد یک قانون جدید."""
    async with async_session_factory() as session:
        rule = AutomationRule(
            name=name,
            description=description,
            status=status,
            trigger_type=trigger_type,
            trigger_filter=trigger_filter or {},
            action_type=action_type,
            action_params=action_params or {},
            schedule_cron=schedule_cron,
            schedule_timezone=schedule_timezone or "Asia/Tehran",
            cooldown_seconds=cooldown_seconds,
            max_executions=max_executions,
            executions_count=0,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def get_rule(rule_id: int) -> Optional[AutomationRule]:
    """دریافت یک قانون با شناسه."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(AutomationRule).where(AutomationRule.id == rule_id)
        )
        return result.scalar_one_or_none()


async def list_rules(
    status: str | None = None,
    trigger_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> List[AutomationRule]:
    """لیست قوانین با فیلترهای اختیاری."""
    async with async_session_factory() as session:
        stmt = select(AutomationRule)
        if status:
            stmt = stmt.where(AutomationRule.status == status)
        if trigger_type:
            stmt = stmt.where(AutomationRule.trigger_type == trigger_type)
        stmt = stmt.order_by(AutomationRule.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_active_rules() -> List[AutomationRule]:
    """دریافت تمام قوانین فعال."""
    return await list_rules(status="active")


async def update_rule(
    rule_id: int,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    trigger_filter: dict | None = None,
    action_params: dict | None = None,
    schedule_cron: str | None = None,
    cooldown_seconds: int | None = None,
    max_executions: int | None = None,
) -> Optional[AutomationRule]:
    """به‌روزرسانی یک قانون."""
    async with async_session_factory() as session:
        stmt = select(AutomationRule).where(AutomationRule.id == rule_id)
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            return None
        
        if name is not None:
            rule.name = name
        if description is not None:
            rule.description = description
        if status is not None:
            rule.status = status
        if trigger_filter is not None:
            rule.trigger_filter = trigger_filter
        if action_params is not None:
            rule.action_params = action_params
        if schedule_cron is not None:
            rule.schedule_cron = schedule_cron
        if cooldown_seconds is not None:
            rule.cooldown_seconds = cooldown_seconds
        if max_executions is not None:
            rule.max_executions = max_executions
        
        await session.commit()
        await session.refresh(rule)
        return rule


async def delete_rule(rule_id: int) -> bool:
    """حذف یک قانون."""
    async with async_session_factory() as session:
        stmt = delete(AutomationRule).where(AutomationRule.id == rule_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def increment_executions(rule_id: int) -> None:
    """افزایش شمارندهٔ اجراهای یک قانون."""
    async with async_session_factory() as session:
        await session.execute(
            update(AutomationRule)
            .where(AutomationRule.id == rule_id)
            .values(
                executions_count=AutomationRule.executions_count + 1,
                last_executed_at=func.now(),
            )
        )
        await session.commit()


async def reset_executions(rule_id: int) -> None:
    """بازنشانی شمارندهٔ اجراها."""
    async with async_session_factory() as session:
        await session.execute(
            update(AutomationRule)
            .where(AutomationRule.id == rule_id)
            .values(executions_count=0, last_executed_at=None)
        )
        await session.commit()