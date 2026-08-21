from .conftest import requires_db


@requires_db
async def test_save_and_get_snapshot():
    from bot.repositories import stats_repo

    snapshot = {
        "commands_total": 3,
        "messages_total": 10,
        "autopost_ok": 1,
        "autopost_fail": 0,
        "errors": 0,
        "commands_by_name": {"note": 2, "stats": 1},
        "per_chat": {"123": {"messages": 5, "commands": 1, "title": "Test"}},
    }
    await stats_repo.save_snapshot(snapshot)
    loaded = await stats_repo.get_snapshot()
    assert loaded["commands_total"] == 3
    assert loaded["commands_by_name"]["note"] == 2
    assert loaded["per_chat"]["123"]["title"] == "Test"


@requires_db
async def test_save_snapshot_upserts_not_duplicates():
    from bot.repositories import stats_repo

    base = {
        "commands_total": 1,
        "messages_total": 1,
        "autopost_ok": 0,
        "autopost_fail": 0,
        "errors": 0,
        "commands_by_name": {"note": 1},
        "per_chat": {"1": {"messages": 1, "commands": 1, "title": None}},
    }
    await stats_repo.save_snapshot(base)
    base["commands_by_name"]["note"] = 5
    await stats_repo.save_snapshot(base)
    loaded = await stats_repo.get_snapshot()
    assert loaded["commands_by_name"] == {"note": 5}


@requires_db
async def test_reset_clears_everything():
    from bot.repositories import stats_repo

    await stats_repo.save_snapshot(
        {
            "commands_total": 1,
            "messages_total": 1,
            "autopost_ok": 0,
            "autopost_fail": 0,
            "errors": 0,
            "commands_by_name": {"note": 1},
            "per_chat": {"1": {"messages": 1, "commands": 1, "title": None}},
        }
    )
    await stats_repo.reset()
    loaded = await stats_repo.get_snapshot()
    assert loaded["commands_total"] == 0
    assert loaded["commands_by_name"] == {}
    assert loaded["per_chat"] == {}
