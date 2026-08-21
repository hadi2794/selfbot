"""وضعیتِ فونتِ خودکار - PostgreSQL از طریق Repository Layer."""
from ..repositories import font_repo

_DEFAULT = {"enabled": False, "style": "bold"}

font_state = dict(_DEFAULT)


async def init_font_state() -> None:
    settings = await font_repo.get_settings()
    font_state["enabled"] = settings.enabled
    font_state["style"] = settings.style


async def save_font_state() -> None:
    await font_repo.save_settings(enabled=font_state["enabled"], style=font_state["style"])
