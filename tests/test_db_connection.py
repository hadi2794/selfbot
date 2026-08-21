import pytest

from .conftest import requires_db


@requires_db
async def test_engine_connects():
    from bot.db.engine import engine

    async with engine.connect() as conn:
        result = await conn.exec_driver_sql("SELECT 1")
        assert result.scalar() == 1


@requires_db
async def test_session_scope_commits():
    from bot.db.engine import session_scope
    from bot.db.models import Note

    async with session_scope() as session:
        session.add(Note(key="conn-test", text="ok"))

    async with session_scope() as session:
        obj = await session.get(Note, "conn-test")
        assert obj is not None
        assert obj.text == "ok"
        await session.delete(obj)


@requires_db
async def test_session_scope_rolls_back_on_error():
    from sqlalchemy.exc import IntegrityError

    from bot.db.engine import session_scope
    from bot.db.models import Note

    with pytest.raises(IntegrityError):
        async with session_scope() as session:
            session.add(Note(key="rollback-test", text="a"))
            await session.flush()
            session.add(Note(key="rollback-test", text="b"))  # کلید تکراری -> خطا

    async with session_scope() as session:
        obj = await session.get(Note, "rollback-test")
        assert obj is None  # تراکنش کامل rollback شده، حتی رکورد اول هم نمونده
