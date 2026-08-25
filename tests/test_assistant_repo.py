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


@requires_db
async def test_schedule_enabled_defaults_true_and_roundtrips():
    from bot.repositories import assistant_repo

    # پاس‌ندادنش -> پیش‌فرض True (سازگار با کدهای قدیمی‌ای مثل اسکریپتِ migrate
    # که schedule_enabled رو اصلاً نمی‌دونن).
    await assistant_repo.save_settings(
        mode="mention", text="hi", delay_seconds=3, auto_detect=True, manual_enabled=False
    )
    settings = await assistant_repo.get_settings()
    assert settings.schedule_enabled is True

    await assistant_repo.save_settings(
        mode="mention",
        text="hi",
        delay_seconds=3,
        auto_detect=True,
        manual_enabled=False,
        schedule_enabled=False,
    )
    settings = await assistant_repo.get_settings()
    assert settings.schedule_enabled is False


@requires_db
async def test_schedule_windows_crud():
    from bot.repositories import assistant_repo

    assert await assistant_repo.list_schedule_windows() == []

    sleep_id = await assistant_repo.add_schedule_window("خواب", 23 * 60, 8 * 60)
    work_id = await assistant_repo.add_schedule_window("کاری", 9 * 60, 13 * 60)

    windows = await assistant_repo.list_schedule_windows()
    # مرتب بر اساسِ start_minute: کاری (۹:۰۰) قبل از خواب (۲۳:۰۰)
    assert [w["label"] for w in windows] == ["کاری", "خواب"]
    assert {w["id"] for w in windows} == {sleep_id, work_id}

    assert await assistant_repo.delete_schedule_window(sleep_id) is True
    assert await assistant_repo.delete_schedule_window(sleep_id) is False  # دوباره حذف -> چیزی نبود
    remaining = await assistant_repo.list_schedule_windows()
    assert len(remaining) == 1 and remaining[0]["id"] == work_id

    deleted_count = await assistant_repo.clear_schedule_windows()
    assert deleted_count == 1
    assert await assistant_repo.list_schedule_windows() == []
