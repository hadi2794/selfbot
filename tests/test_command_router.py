import datetime as dt

import pytest

from bot.handlers.command_router import ACTIONS, _extract_json, _parse_router_time


def test_extract_json_plain():
    assert _extract_json('{"intent": "reminder", "params": {}}') == {
        "intent": "reminder",
        "params": {},
    }


def test_extract_json_with_surrounding_text():
    raw = 'Sure, here you go:\n{"intent": "calc", "params": {"expr": "1+1"}}\nthanks!'
    data = _extract_json(raw)
    assert data == {"intent": "calc", "params": {"expr": "1+1"}}


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


def test_all_actions_registered_with_required_keys():
    expected = {
        "reminder", "schedule_message", "note_add", "note_get", "note_delete",
        "calc", "translate", "currency", "genpass", "setbio", "setname",
        "font_apply", "coin_flip", "random_number", "choose", "magic8ball",
    }
    assert expected.issubset(ACTIONS.keys())
    for name, spec in ACTIONS.items():
        assert "prompt_spec" in spec and spec["prompt_spec"]
        assert callable(spec["build"])
        assert callable(spec["execute"])


@pytest.mark.asyncio
async def test_calc_build_ok_and_missing():
    ok, preview, norm = await ACTIONS["calc"]["build"]({"expr": "1+1"}, None)
    assert ok and norm == {"expr": "1+1"}
    ok, preview, norm = await ACTIONS["calc"]["build"]({}, None)
    assert not ok and norm is None


@pytest.mark.asyncio
async def test_calc_execute():
    result = await ACTIONS["calc"]["execute"](None, {"expr": "2*3"})
    assert "6" in result


@pytest.mark.asyncio
async def test_choose_build_requires_two_options():
    ok, _, norm = await ACTIONS["choose"]["build"]({"options": ["a"]}, None)
    assert not ok
    ok, _, norm = await ACTIONS["choose"]["build"]({"options": ["a", "b"]}, None)
    assert ok and norm == {"options": ["a", "b"]}


@pytest.mark.asyncio
async def test_currency_build_validates_amount():
    ok, _, norm = await ACTIONS["currency"]["build"](
        {"amount": "10", "src": "usd", "dst": "irr"}, None
    )
    assert ok and norm == {"amount": 10.0, "src": "USD", "dst": "IRR"}
    ok, _, norm = await ACTIONS["currency"]["build"]({"amount": "x", "src": "usd", "dst": "irr"}, None)
    assert not ok


@pytest.mark.asyncio
async def test_note_add_build_requires_key_and_text():
    ok, _, norm = await ACTIONS["note_add"]["build"]({"key": "k", "text": "v"}, None)
    assert ok and norm == {"key": "k", "text": "v"}
    ok, _, norm = await ACTIONS["note_add"]["build"]({"key": "k"}, None)
    assert not ok


@pytest.mark.asyncio
async def test_random_number_build_swaps_bounds():
    ok, _, norm = await ACTIONS["random_number"]["build"]({"min": 10, "max": 1}, None)
    assert ok and norm == {"lo": 1, "hi": 10}


@pytest.mark.asyncio
async def test_genpass_build_defaults_and_clamps():
    ok, _, norm = await ACTIONS["genpass"]["build"]({}, None)
    assert ok and norm == {"length": 16}
    ok, _, norm = await ACTIONS["genpass"]["build"]({"length": 999}, None)
    assert ok and norm == {"length": 128}
