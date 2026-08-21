"""
تستِ منطقِ شمارشِ اسکریپتِ migration، بدون نیاز به یک دیتابیس واقعی - فقط
مطمئن می‌شه که count_json_records() دقیقاً روی فایل‌های JSون موجود درست
می‌شمره (چیزی که migrate() قبل/بعد باهاش مقایسه می‌کنه).
"""
import importlib
import json
import os
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


def _import_migration_module():
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import migrate_json_to_postgres as m

    importlib.reload(m)
    return m


def test_count_json_records_matches_files(tmp_path, monkeypatch):
    notes_path = tmp_path / "notes.json"
    notes_path.write_text(json.dumps({"a": "1", "b": "2"}), encoding="utf-8")

    autopost_path = tmp_path / "autopost.json"
    autopost_path.write_text(
        json.dumps({"chats": {"1": "A", "2": "B", "3": "C"}}), encoding="utf-8"
    )

    assistant_path = tmp_path / "assistant.json"
    assistant_path.write_text(
        json.dumps({"include": [1, 2], "exclude": [3]}), encoding="utf-8"
    )

    monkeypatch.setenv("NOTES_FILE", str(notes_path))
    monkeypatch.setenv("AUTOPOST_FILE", str(autopost_path))
    monkeypatch.setenv("ASSISTANT_FILE", str(assistant_path))
    monkeypatch.setenv("FONT_STATE_FILE", str(tmp_path / "does_not_exist.json"))
    monkeypatch.setenv("STATS_FILE", str(tmp_path / "does_not_exist2.json"))

    # bot.config مقادیرِ env رو فقط موقع import اول می‌خونه؛ چون از قبل import
    # شده، مستقیم مقادیرِ ماژول رو برای این تست عوض می‌کنیم.
    from bot import config as bot_config

    monkeypatch.setattr(bot_config, "NOTES_FILE", str(notes_path))
    monkeypatch.setattr(bot_config, "AUTOPOST_FILE", str(autopost_path))
    monkeypatch.setattr(bot_config, "ASSISTANT_FILE", str(assistant_path))
    monkeypatch.setattr(bot_config, "FONT_STATE_FILE", str(tmp_path / "does_not_exist.json"))
    monkeypatch.setattr(bot_config, "STATS_FILE", str(tmp_path / "does_not_exist2.json"))

    m = _import_migration_module()
    counts = m.count_json_records()

    assert counts["notes"] == 2
    assert counts["autopost_chats"] == 3
    assert counts["assistant_chat_rules"] == 3
    assert counts["font_settings"] == 0
    assert counts["stats_commands"] == 0
    assert counts["stats_chats"] == 0
    assert set(counts.keys()) == {
        "notes",
        "autopost_chats",
        "assistant_chat_rules",
        "font_settings",
        "stats_commands",
        "stats_chats",
    }


def test_backup_json_files_copies_existing_files_only(tmp_path, monkeypatch):
    notes_path = tmp_path / "notes.json"
    notes_path.write_text("{}", encoding="utf-8")

    from bot import config as bot_config

    monkeypatch.setattr(bot_config, "NOTES_FILE", str(notes_path))
    monkeypatch.setattr(bot_config, "AUTOPOST_FILE", str(tmp_path / "missing_autopost.json"))
    monkeypatch.setattr(bot_config, "ASSISTANT_FILE", str(tmp_path / "missing_assistant.json"))
    monkeypatch.setattr(bot_config, "FONT_STATE_FILE", str(tmp_path / "missing_font.json"))
    monkeypatch.setattr(bot_config, "STATS_FILE", str(tmp_path / "missing_stats.json"))

    m = _import_migration_module()
    dest_dir = tmp_path / "backup_out"
    copied = m.backup_json_files(str(dest_dir))

    assert len(copied) == 1
    assert os.path.exists(copied[0])
    assert notes_path.exists()  # فایل اصلی دست‌نخورده می‌مونه
