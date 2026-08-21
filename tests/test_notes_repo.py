from .conftest import requires_db


@requires_db
async def test_upsert_and_get_all():
    from bot.repositories import notes_repo

    await notes_repo.upsert("k1", "v1")
    await notes_repo.upsert("k2", "v2")
    notes = await notes_repo.get_all()
    assert notes == {"k1": "v1", "k2": "v2"}


@requires_db
async def test_upsert_overwrites_existing_key():
    from bot.repositories import notes_repo

    await notes_repo.upsert("k1", "v1")
    await notes_repo.upsert("k1", "v2")
    notes = await notes_repo.get_all()
    assert notes == {"k1": "v2"}


@requires_db
async def test_delete_note():
    from bot.repositories import notes_repo

    await notes_repo.upsert("k1", "v1")
    deleted = await notes_repo.delete_note("k1")
    assert deleted is True
    assert await notes_repo.get_all() == {}
    assert await notes_repo.delete_note("missing") is False
