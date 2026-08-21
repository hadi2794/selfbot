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
