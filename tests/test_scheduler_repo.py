import datetime as dt

from .conftest import requires_db


@requires_db
async def test_create_and_get():
    from bot.repositories import scheduler_repo

    run_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)
    job = await scheduler_repo.create(chat_id=111, text="سلام", run_at=run_at, kind="schedule")
    fetched = await scheduler_repo.get(job.id)
    assert fetched is not None
    assert fetched.chat_id == 111
    assert fetched.text == "سلام"
    assert fetched.kind == "schedule"


@requires_db
async def test_list_by_kind_only_returns_matching_kind():
    from bot.repositories import scheduler_repo

    run_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)
    await scheduler_repo.create(chat_id=1, text="a", run_at=run_at, kind="schedule")
    await scheduler_repo.create(chat_id=2, text="b", run_at=run_at, kind="reminder")

    schedules = await scheduler_repo.list_by_kind("schedule")
    reminders = await scheduler_repo.list_by_kind("reminder")
    assert [j.text for j in schedules] == ["a"]
    assert [j.text for j in reminders] == ["b"]


@requires_db
async def test_list_due_only_returns_past_due_jobs():
    from bot.repositories import scheduler_repo

    now = dt.datetime.now(dt.timezone.utc)
    past = await scheduler_repo.create(
        chat_id=1, text="due", run_at=now - dt.timedelta(minutes=1), kind="schedule"
    )
    await scheduler_repo.create(
        chat_id=1, text="not-due", run_at=now + dt.timedelta(hours=1), kind="schedule"
    )

    due = await scheduler_repo.list_due(now)
    assert [j.id for j in due] == [past.id]


@requires_db
async def test_delete_job():
    from bot.repositories import scheduler_repo

    run_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)
    job = await scheduler_repo.create(chat_id=1, text="x", run_at=run_at, kind="schedule")

    assert await scheduler_repo.delete(job.id) is True
    assert await scheduler_repo.get(job.id) is None
    assert await scheduler_repo.delete(job.id) is False
