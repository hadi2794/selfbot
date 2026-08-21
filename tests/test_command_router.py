import datetime as dt

from bot.handlers.command_router import _extract_json, _parse_router_time


def test_extract_json_plain():
    assert _extract_json('{"intent": "reminder", "time": null, "text": null}') == {
        "intent": "reminder",
        "time": None,
        "text": None,
    }


def test_extract_json_with_surrounding_text():
    raw = 'Sure, here you go:\n{"intent": "reminder", "time": "2026-08-22 09:00", "text": "x"}\nthanks!'
    data = _extract_json(raw)
    assert data == {"intent": "reminder", "time": "2026-08-22 09:00", "text": "x"}


def test_extract_json_invalid_returns_none():
    assert _extract_json("not json at all") is None
    assert _extract_json("") is None
    assert _extract_json(None) is None


def test_parse_router_time_future_ok():
    from bot.handlers.scheduler import _local_now

    future = _local_now() + dt.timedelta(days=1)
    raw = future.strftime("%Y-%m-%d %H:%M")
    result = _parse_router_time(raw)
    assert result is not None
    run_at_utc, local_display = result
    assert local_display == raw
    assert run_at_utc > dt.datetime.now(dt.timezone.utc)


def test_parse_router_time_past_rejected():
    assert _parse_router_time("2020-01-01 00:00") is None


def test_parse_router_time_bad_format_rejected():
    assert _parse_router_time("tomorrow at 9am") is None
    assert _parse_router_time(None) is None
    assert _parse_router_time("") is None
