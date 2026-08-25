from .conftest import requires_db


@requires_db
async def test_gather_and_apply_config_snapshot_roundtrip():
    from bot.handlers.backup import _apply_config_snapshot, _gather_config_snapshot
    from bot.storage.assistant_store import assistant_state
    from bot.storage.notes_store import load_notes, save_note

    await save_note("hello", "world")
    snapshot = await _gather_config_snapshot()
    assert snapshot["_kind"] == "selfbot_config_backup"
    assert snapshot["notes"]["hello"] == "world"

    snapshot["notes"]["hello2"] = "world2"
    snapshot["assistant"]["text"] = "restored text"
    applied = await _apply_config_snapshot(snapshot)
    assert "یادداشت‌ها" in applied
    assert "منشی" in applied

    notes = await load_notes()
    assert notes["hello2"] == "world2"
    assert assistant_state["text"] == "restored text"


@requires_db
async def test_schedule_windows_survive_backup_roundtrip():
    from bot.handlers.backup import _apply_config_snapshot, _gather_config_snapshot
    from bot.storage.assistant_store import add_schedule_window, assistant_state, clear_schedule_windows

    await clear_schedule_windows()
    await add_schedule_window("خواب", 23 * 60, 8 * 60)
    assistant_state["schedule_enabled"] = True

    snapshot = await _gather_config_snapshot()
    assert snapshot["assistant"]["schedule_enabled"] is True
    assert snapshot["assistant"]["schedule_windows"] == [
        {"label": "خواب", "start_minute": 23 * 60, "end_minute": 8 * 60}
    ]

    # وانمود کن یه بکاپِ قدیمی‌تر داریم با یه بازه‌ی متفاوت و لایه‌ی خاموش -
    # بازگردانی باید کاملاً جایگزین کنه (نه merge با چیزی که الان هست).
    snapshot["assistant"]["schedule_enabled"] = False
    snapshot["assistant"]["schedule_windows"] = [
        {"label": "کاری", "start_minute": 9 * 60, "end_minute": 13 * 60}
    ]
    await _apply_config_snapshot(snapshot)

    assert assistant_state["schedule_enabled"] is False
    assert len(assistant_state["schedule_windows"]) == 1
    restored = assistant_state["schedule_windows"][0]
    assert (restored["label"], restored["start_minute"], restored["end_minute"]) == ("کاری", 9 * 60, 13 * 60)
