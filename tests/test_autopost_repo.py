from .conftest import requires_db


@requires_db
async def test_settings_roundtrip():
    from bot.repositories import autopost_repo

    await autopost_repo.save_settings(enabled=True, interval_minutes=10, text="hi")
    settings = await autopost_repo.get_settings()
    assert settings.enabled is True
    assert settings.interval_minutes == 10
    assert settings.text == "hi"


@requires_db
async def test_chats_upsert_remove_clear():
    from bot.repositories import autopost_repo

    await autopost_repo.upsert_chat(100, "Group A")
    await autopost_repo.upsert_chat(100, "Group A renamed")  # آپدیت، نه رکورد تکراری
    chats = await autopost_repo.list_chats()
    assert chats == {"100": "Group A renamed"}

    await autopost_repo.upsert_chat(200, "Group B")
    await autopost_repo.remove_chat(100)
    assert await autopost_repo.list_chats() == {"200": "Group B"}

    await autopost_repo.clear_chats()
    assert await autopost_repo.list_chats() == {}
