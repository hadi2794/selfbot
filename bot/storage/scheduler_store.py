"""
کارهای زمان‌بندی‌شده - PostgreSQL از طریق Repository Layer.

برخلاف autopost/assistant/font/clock، اینجا هیچ state درون‌حافظه‌ای نگه
داشته نمی‌شه (نیازی هم نیست: نرخ استفاده از `.زمان‌بند`/`.یادآوری` خیلی کمتر
از هر پیامه، پس مستقیم از PostgreSQL خوندن مشکلی نداره) - برای همین نیازی به
init_*_state() توی bootstrap.py هم نیست.
"""
import datetime as dt

from ..repositories import scheduler_repo


async def create_job(chat_id: int, text: str, run_at: dt.datetime, kind: str):
    return await scheduler_repo.create(chat_id, text, run_at, kind)


async def list_jobs(kind: str):
    return await scheduler_repo.list_by_kind(kind)


async def list_due_jobs(now: dt.datetime):
    return await scheduler_repo.list_due(now)


async def get_job(job_id: int):
    return await scheduler_repo.get(job_id)


async def delete_job(job_id: int) -> bool:
    return await scheduler_repo.delete(job_id)
