"""Repository لایه‌ی کارهای زمان‌بندی‌شده (`.زمان‌بند` / `.یادآوری`)."""
import datetime as dt

from sqlalchemy import select

from ..db.engine import session_scope
from ..db.models import ScheduledJob


async def create(chat_id: int, text: str, run_at: dt.datetime, kind: str) -> ScheduledJob:
    async with session_scope() as session:
        obj = ScheduledJob(chat_id=chat_id, text=text, run_at=run_at, kind=kind)
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        # جدا از session برگردونده می‌شه (بعد از commit خودِ session_scope)، پس
        # مقادیر رو همینجا کپی می‌کنیم تا بعد از بسته‌شدنِ session هم قابل خوندن باشن.
        return _detached_copy(obj)


async def list_by_kind(kind: str) -> list[ScheduledJob]:
    async with session_scope() as session:
        rows = (
            (
                await session.execute(
                    select(ScheduledJob)
                    .where(ScheduledJob.kind == kind)
                    .order_by(ScheduledJob.run_at.asc())
                )
            )
            .scalars()
            .all()
        )
        return [_detached_copy(r) for r in rows]


async def list_due(now: dt.datetime) -> list[ScheduledJob]:
    async with session_scope() as session:
        rows = (
            (await session.execute(select(ScheduledJob).where(ScheduledJob.run_at <= now)))
            .scalars()
            .all()
        )
        return [_detached_copy(r) for r in rows]


async def get(job_id: int) -> ScheduledJob | None:
    async with session_scope() as session:
        obj = await session.get(ScheduledJob, job_id)
        return _detached_copy(obj) if obj else None


async def delete(job_id: int) -> bool:
    async with session_scope() as session:
        obj = await session.get(ScheduledJob, job_id)
        if obj is None:
            return False
        await session.delete(obj)
        return True


async def search_jobs(query: str, limit: int = 50) -> list[ScheduledJob]:
    """جستجوی کارهای زمان‌بندی‌شده بر اساسِ متن (برای `.جستجو`)."""
    async with session_scope() as session:
        rows = (
            (
                await session.execute(
                    select(ScheduledJob)
                    .where(ScheduledJob.text.ilike(f"%{query}%"))
                    .order_by(ScheduledJob.run_at.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [_detached_copy(r) for r in rows]


def _detached_copy(obj: ScheduledJob) -> ScheduledJob:
    """
    یه کپیِ ساده و detached (بدون وابستگی به session بسته‌شده) برمی‌گردونه، چون
    caller بعد از خروج از session_scope هم نیاز داره فیلدهاش رو بخونه.
    """
    return ScheduledJob(
        id=obj.id,
        chat_id=obj.chat_id,
        text=obj.text,
        run_at=obj.run_at,
        kind=obj.kind,
        created_at=obj.created_at,
    )
