import datetime as dt

import os

os.environ.setdefault("TIMEZONE_OFFSET", "3.5")

from bot.handlers.scheduler import parse_time  # noqa: E402


def test_relative_minutes_english_unit():
    result = parse_time("10m")
    assert result is not None
    run_at_utc, _ = result
    delta = run_at_utc - dt.datetime.now(dt.timezone.utc)
    assert dt.timedelta(minutes=9) < delta <= dt.timedelta(minutes=10)


def test_relative_persian_unit():
    result = parse_time("2ساعت")
    assert result is not None
    run_at_utc, _ = result
    delta = run_at_utc - dt.datetime.now(dt.timezone.utc)
    assert dt.timedelta(hours=1, minutes=59) < delta <= dt.timedelta(hours=2)


def test_clock_time_rolls_to_tomorrow_if_passed():
    # ساعتی که مطمئناً امروز گذشته: یک دقیقه قبل از الان (به وقت محلی)
    from bot.handlers.scheduler import _local_now

    almost_passed = _local_now() - dt.timedelta(minutes=1)
    raw = almost_passed.strftime("%H:%M")
    result = parse_time(raw)
    assert result is not None
    run_at_utc, _ = result
    assert run_at_utc > dt.datetime.now(dt.timezone.utc)


def test_full_datetime_in_past_is_rejected():
    result = parse_time("2020-01-01 00:00")
    assert result is None


def test_invalid_format_returns_none():
    assert parse_time("نامعتبر") is None
    assert parse_time("25:99") is None
