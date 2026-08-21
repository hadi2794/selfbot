from .conftest import requires_db


@requires_db
async def test_clock_settings_roundtrip():
    from bot.repositories import clock_repo

    await clock_repo.save_settings(enabled=False, style="star", base_name="Ali")
    settings = await clock_repo.get_settings()
    assert settings.enabled is False
    assert settings.style == "star"
    assert settings.base_name == "Ali"


@requires_db
async def test_font_settings_roundtrip():
    from bot.repositories import font_repo

    await font_repo.save_settings(enabled=True, style="doublestruck")
    settings = await font_repo.get_settings()
    assert settings.enabled is True
    assert settings.style == "doublestruck"
