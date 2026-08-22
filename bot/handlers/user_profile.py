"""
دستورات پروفایل کاربر: .کاربر، .برچسب، .یادداشت‌کاربر
"""
import logging

from telethon import events
from telethon.tl.types import Message

from ..config import PREFIX
from ..runtime import client
from ..utils import pat
from ..repositories import user_profile_repo

logger = logging.getLogger("selfbot.handlers.user_profile")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["کاربر", "profile"])))
async def user_profile_handler(event):
    """نمایش اطلاعات کاربر."""
    args = (event.pattern_match.group(1) or "").strip().split()

    # اگر ریپلای شده، کاربر ریپلای را بگیر
    user_id = None
    if event.is_reply:
        reply: Message = await event.get_reply_message()
        if reply and reply.sender_id:
            user_id = reply.sender_id

    # یا از آرگومان
    if not user_id and args and args[0].isdigit():
        user_id = int(args[0])

    if not user_id:
        # کاربر خودش
        me = await event.client.get_me()
        user_id = me.id

    try:
        user = await event.client.get_entity(user_id)
        profile = await user_profile_repo.get_or_create(user_id)

        lines = [
            "👤 **پروفایل کاربر**",
            "",
            f"🆔 ID: `{user_id}`",
            f"👤 نام: {user.first_name or 'نامشخص'}",
            f"🔹 نام‌کاربری: @{user.username}" if user.username else "",
            f"📱 شماره: {user.phone}" if hasattr(user, 'phone') and user.phone else "",
            "",
            "🏷 **برچسب‌ها:**",
        ]

        if profile.tags:
            tags = [f"#{t.strip()}" for t in profile.tags.split(",") if t.strip()]
            lines.append("  " + " ".join(tags))
        else:
            lines.append("  (هیچ برچسبی)")

        if profile.is_vip:
            lines.append("⭐ **VIP**")

        if profile.notes:
            lines.append("")
            lines.append("📝 **یادداشت:**")
            lines.append(f"  {profile.notes}")

        lines.append("")
        lines.append(f"• افزودن برچسب: `{PREFIX}برچسب <کاربر> <برچسب>`")
        lines.append(f"• حذف برچسب: `{PREFIX}برچسب حذف <کاربر> <برچسب>`")
        lines.append(f"• یادداشت: `{PREFIX}یادداشت‌کاربر <کاربر> <متن>`")

        await event.edit("\n".join(lines))

    except Exception as e:
        await event.edit(f"❌ خطا: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["برچسب", "tag"])))
async def tag_handler(event):
    """مدیریت برچسب‌های کاربر."""
    args = (event.pattern_match.group(1) or "").strip().split()
    if not args:
        return await event.edit(f"❌ استفاده: `{PREFIX}برچسب <کاربر> <برچسب>` یا `{PREFIX}برچسب حذف <کاربر> <برچسب>`")

    # تشخیص کاربر
    user_id = None
    if event.is_reply:
        reply: Message = await event.get_reply_message()
        if reply and reply.sender_id:
            user_id = reply.sender_id

    if not user_id and args and (args[0].isdigit() or args[0].lstrip("-").isdigit()):
        user_id = int(args[0])
        args = args[1:]

    if not user_id:
        return await event.edit("❌ کاربر مشخص نشد. روی پیام ریپلای کنید یا ID را وارد کنید.")

    sub = args[0].lower() if args else ""
    if sub in ("حذف", "remove", "rm"):
        if len(args) < 2:
            return await event.edit(f"❌ استفاده: `{PREFIX}برچسب حذف <کاربر> <برچسب>`")
        tag = args[1]
        success = await user_profile_repo.remove_tag(user_id, tag)
        if success:
            await event.edit(f"✅ برچسب `{tag}` از کاربر {user_id} حذف شد.")
        else:
            await event.edit(f"❌ برچسب `{tag}` برای کاربر {user_id} یافت نشد.")
    else:
        tag = args[0] if args else ""
        if not tag:
            return await event.edit(f"❌ استفاده: `{PREFIX}برچسب <کاربر> <برچسب>`")
        success = await user_profile_repo.add_tag(user_id, tag)
        if success:
            await event.edit(f"✅ برچسب `{tag}` به کاربر {user_id} اضافه شد.")
        else:
            await event.edit(f"❌ خطا در افزودن برچسب.")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["یادداشت‌کاربر", "usernote"])))
async def user_note_handler(event):
    """افزودن یادداشت به کاربر."""
    args = (event.pattern_match.group(1) or "").strip().split()
    if not args:
        return await event.edit(f"❌ استفاده: `{PREFIX}یادداشت‌کاربر <کاربر> <متن>`")

    user_id = None
    if event.is_reply:
        reply: Message = await event.get_reply_message()
        if reply and reply.sender_id:
            user_id = reply.sender_id

    if not user_id and args and (args[0].isdigit() or args[0].lstrip("-").isdigit()):
        user_id = int(args[0])
        args = args[1:]

    if not user_id:
        return await event.edit("❌ کاربر مشخص نشد. روی پیام ریپلای کنید یا ID را وارد کنید.")

    note = " ".join(args) if args else ""
    if not note:
        return await event.edit(f"❌ استفاده: `{PREFIX}یادداشت‌کاربر <کاربر> <متن>`")

    profile = await user_profile_repo.update_profile(user_id, notes=note)
    if profile:
        await event.edit(f"✅ یادداشت برای کاربر {user_id} ذخیره شد:\n{note}")
    else:
        await event.edit("❌ خطا در ذخیره یادداشت.")