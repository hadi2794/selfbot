"""
تست‌های خالص (بدون نیاز به دیتابیس) برای منطقِ زمان‌بندیِ منشیِ خودکار:
پارس‌کردنِ ساعت، محاسبه‌ی بازه (از جمله رد‌شدن از نیمه‌شب)، و ترکیبِ
سیگنالِ زمان‌بندی + فعالیت توی _recompute_enabled_from_signals.

مثلِ test_scheduler_time_parsing.py، این‌ها همیشه اجرا می‌شن (نه فقط وقتی
SELFBOT_TEST_DATABASE_URL ست شده) چون به دیتابیسِ واقعی نیازی ندارن.
"""
import datetime as dt
import os

os.environ.setdefault("TIMEZONE_OFFSET", "3.5")

import pytest  # noqa: E402

from bot.handlers import assistant as assistant_mod  # noqa: E402
from bot.handlers.assistant import (  # noqa: E402
    _active_schedule_window,
    _current_signal_reason,
    _format_clock,
    _parse_clock,
    _window_contains,
)
from bot.storage.assistant_store import assistant_state  # noqa: E402


def test_parse_clock_valid():
    assert _parse_clock("23:00") == 23 * 60
    assert _parse_clock("08:00") == 8 * 60
    assert _parse_clock("8:00") == 8 * 60  # ساعتِ تک‌رقمی هم قبول
    assert _parse_clock("00:00") == 0
    assert _parse_clock("23:59") == 23 * 60 + 59


def test_parse_clock_invalid():
    assert _parse_clock("24:00") is None  # ساعتِ نامعتبر
    assert _parse_clock("08:60") is None  # دقیقه‌ی نامعتبر
    assert _parse_clock("نامعتبر") is None
    assert _parse_clock("8-00") is None
    assert _parse_clock("") is None


def test_format_clock_roundtrip():
    for raw in ("00:00", "08:00", "13:05", "23:59"):
        assert _format_clock(_parse_clock(raw)) == raw


def test_window_contains_normal_range():
    start, end = 9 * 60, 13 * 60  # ۰۹:۰۰ تا ۱۳:۰۰
    assert _window_contains(start, end, 9 * 60) is True  # مرزِ شروع، inclusive
    assert _window_contains(start, end, 13 * 60) is True  # مرزِ پایان، inclusive
    assert _window_contains(start, end, 11 * 60) is True
    assert _window_contains(start, end, 8 * 60 + 59) is False
    assert _window_contains(start, end, 13 * 60 + 1) is False


def test_window_contains_midnight_wraparound():
    start, end = 23 * 60, 8 * 60  # ۲۳:۰۰ تا ۰۸:۰۰ی روزِ بعد
    assert _window_contains(start, end, 23 * 60) is True  # لحظه‌ی شروع
    assert _window_contains(start, end, 23 * 60 + 59) is True  # قبل از نیمه‌شب
    assert _window_contains(start, end, 0) is True  # نیمه‌شب
    assert _window_contains(start, end, 8 * 60) is True  # لحظه‌ی پایان
    assert _window_contains(start, end, 8 * 60 + 1) is False  # درست بعد از پایان
    assert _window_contains(start, end, 22 * 60 + 59) is False  # درست قبل از شروع


@pytest.fixture
def _reset_schedule_state():
    """
    assistant_state و _last_self_activity هر دو ماژول‌سطحی و مشترک با بقیه‌ی
    تست‌ها (و حتی فایل‌های تستِ دیگه) هستن - قبل/بعدِ هر تست snapshot/restore
    می‌کنیم تا نشتیِ حالت بینِ تست‌ها پیش نیاد.
    """
    before_windows = assistant_state["schedule_windows"]
    before_layer_enabled = assistant_state["schedule_enabled"]
    before_enabled = assistant_state["enabled"]
    before_activity = assistant_mod._last_self_activity
    yield
    assistant_state["schedule_windows"] = before_windows
    assistant_state["schedule_enabled"] = before_layer_enabled
    assistant_state["enabled"] = before_enabled
    assistant_mod._last_self_activity = before_activity


def test_active_schedule_window_respects_layer_toggle(_reset_schedule_state):
    assistant_state["schedule_windows"] = [
        {"id": 1, "label": "خواب", "start_minute": 23 * 60, "end_minute": 8 * 60},
    ]
    assistant_state["schedule_enabled"] = True
    assert _active_schedule_window(23 * 60 + 30) is not None
    assert _active_schedule_window(12 * 60) is None  # ظهر - خارج از بازه

    # لایه رو خاموش کن: حتی وسطِ بازه هم دیگه نباید فعال باشه
    assistant_state["schedule_enabled"] = False
    assert _active_schedule_window(23 * 60 + 30) is None


def test_current_signal_reason_schedule_vs_activity(_reset_schedule_state):
    # پنجره‌ای که کلِ شبانه‌روز رو می‌پوشونه - صرف‌نظر از ساعتِ واقعیِ اجرای
    # تست، همیشه باید "schedule" برگردونه (تستِ deterministic، نه وابسته به
    # ساعتِ فعلی).
    assistant_state["schedule_enabled"] = True
    assistant_state["schedule_windows"] = [
        {"id": 1, "label": "همیشه", "start_minute": 0, "end_minute": 23 * 60 + 59},
    ]
    kind, window = _current_signal_reason()
    assert kind == "schedule"
    assert window is not None and window["label"] == "همیشه"

    assistant_state["schedule_windows"] = []
    kind, window = _current_signal_reason()
    assert kind == "activity"
    assert window is None


def test_recompute_prefers_schedule_over_recent_activity(_reset_schedule_state):
    # طبقِ روشِ قدیم (فقط فعالیت)، فعالیتِ همین‌الانه یعنی «آنلاینم» -> منشی
    # باید خاموش بمونه. ولی چون یه بازه‌ی زمان‌بندی‌شده‌ی فعال هم داریم (که
    # کلِ روز رو می‌پوشونه)، باید *صرف‌نظر* از تازگیِ فعالیت روشن بمونه -
    # این دقیقاً همون رفتارِ ترکیبی‌ای هست که این بازطراحی اضافه کرده.
    assistant_mod._last_self_activity = dt.datetime.now(dt.timezone.utc)
    assistant_state["schedule_enabled"] = True
    assistant_state["schedule_windows"] = [
        {"id": 1, "label": "همیشه", "start_minute": 0, "end_minute": 23 * 60 + 59},
    ]
    assistant_state["enabled"] = False

    assistant_mod._recompute_enabled_from_signals()

    assert assistant_state["enabled"] is True


def test_recompute_falls_back_to_activity_outside_any_window(_reset_schedule_state):
    assistant_state["schedule_windows"] = []  # هیچ پنجره‌ای تعریف نشده
    assistant_mod._last_self_activity = dt.datetime.now(dt.timezone.utc)  # همین الان فعال بودی
    assistant_state["enabled"] = True

    assistant_mod._recompute_enabled_from_signals()

    assert assistant_state["enabled"] is False  # آنلاینی -> باید خاموش بشه، دقیقاً مثلِ رفتارِ قبلی
