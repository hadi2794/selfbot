"""ذخیره‌سازیِ یادداشت‌ها - از طریق Repository Layer (PostgreSQL)."""
from ..repositories import notes_repo


async def load_notes() -> dict:
    return await notes_repo.get_all()


async def save_note(key: str, text: str) -> None:
    await notes_repo.upsert(key, text)


async def delete_note(key: str) -> bool:
    return await notes_repo.delete_note(key)
