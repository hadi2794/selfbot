from .conftest import requires_db


@requires_db
async def test_settings_roundtrip():
    from bot.repositories import assistant_repo

    await assistant_repo.save_settings(
        mode="auto", text="hi", delay_seconds=5, auto_detect=False, manual_enabled=True
    )
    settings = await assistant_repo.get_settings()
    assert settings.mode == "auto"
    assert settings.text == "hi"
    assert settings.delay_seconds == 5
    assert settings.auto_detect is False
    assert settings.manual_enabled is True
    assert settings.ai_mode is False  # پیش‌فرض، چون این تست پاسش نداده


@requires_db
async def test_ai_mode_roundtrip():
    from bot.repositories import assistant_repo

    await assistant_repo.save_settings(
        mode="mention",
        text="hi",
        delay_seconds=3,
        auto_detect=True,
        manual_enabled=False,
        ai_mode=True,
    )
    settings = await assistant_repo.get_settings()
    assert settings.ai_mode is True


@requires_db
async def test_chat_rules_replace_is_atomic_and_exclusive():
    from bot.repositories import assistant_repo

    await assistant_repo.replace_chat_rules(include={1, 2}, exclude={3})
    rules = await assistant_repo.list_chat_rules()
    assert rules == {1: "include", 2: "include", 3: "exclude"}

    # جایگزینیِ کامل - قانون‌های قبلی باید پاک بشن، نه merge
    await assistant_repo.replace_chat_rules(include={5}, exclude=set())
    rules = await assistant_repo.list_chat_rules()
    assert rules == {5: "include"}
