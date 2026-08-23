from .conftest import requires_db


@requires_db
async def test_link_filter_roundtrip():
    from bot.repositories import group_guard_repo

    await group_guard_repo.set_link_filter(111, True)
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[111].link_filter_enabled is True

    await group_guard_repo.set_link_filter(111, False)
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[111].link_filter_enabled is False


@requires_db
async def test_welcome_settings_independent_of_link_filter():
    from bot.repositories import group_guard_repo

    await group_guard_repo.set_welcome(222, enabled=True, text="سلام {نام}")
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[222].welcome_enabled is True
    assert rows[222].welcome_text == "سلام {نام}"
    assert rows[222].link_filter_enabled is False

    # آپدیتِ فقط متن نباید enabled رو تغییر بده
    await group_guard_repo.set_welcome(222, text="خوش اومدی {منشن}")
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[222].welcome_enabled is True
    assert rows[222].welcome_text == "خوش اومدی {منشن}"


@requires_db
async def test_porn_and_spam_filter_independent_of_each_other():
    from bot.repositories import group_guard_repo

    await group_guard_repo.set_porn_filter(333, True)
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[333].porn_filter_enabled is True
    assert rows[333].spam_filter_enabled is False  # هنوز روشن نشده

    await group_guard_repo.set_spam_filter(333, True)
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[333].porn_filter_enabled is True  # دست‌نخورده مونده
    assert rows[333].spam_filter_enabled is True

    await group_guard_repo.set_porn_filter(333, False)
    rows = {r.chat_id: r for r in await group_guard_repo.list_all()}
    assert rows[333].porn_filter_enabled is False
    assert rows[333].spam_filter_enabled is True  # دست‌نخورده مونده
