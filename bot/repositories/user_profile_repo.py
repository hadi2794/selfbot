"""
Repository برای پروفایل کاربران (User Profile).
"""

from sqlalchemy import select, update, delete
from typing import List, Optional

from ..db.engine import session_scope
from ..db.models_ext import UserProfile


async def get_or_create(user_id: int) -> UserProfile:
    """دریافت یا ساخت پروفایل کاربر."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            return profile
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile


async def update_profile(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    tags: Optional[str] = None,
    notes: Optional[str] = None,
    is_vip: Optional[bool] = None,
) -> Optional[UserProfile]:
    """بروزرسانی پروفایل کاربر (اگه پروفایل هنوز وجود نداشته باشه، می‌سازدش)."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            profile = UserProfile(user_id=user_id)
            session.add(profile)
        if username is not None:
            profile.username = username
        if first_name is not None:
            profile.first_name = first_name
        if last_name is not None:
            profile.last_name = last_name
        if tags is not None:
            profile.tags = tags
        if notes is not None:
            profile.notes = notes
        if is_vip is not None:
            profile.is_vip = is_vip
        await session.commit()
        await session.refresh(profile)
        return profile


async def get_profile(user_id: int) -> Optional[UserProfile]:
    """دریافت پروفایل کاربر."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def search_profiles(query: str) -> List[UserProfile]:
    """جستجوی کاربران بر اساس نام یا تگ."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(
            (UserProfile.first_name.ilike(f"%{query}%")) |
            (UserProfile.last_name.ilike(f"%{query}%")) |
            (UserProfile.username.ilike(f"%{query}%")) |
            (UserProfile.tags.ilike(f"%{query}%"))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_by_tags(tag: str) -> List[UserProfile]:
    """دریافت کاربران با یک تگ خاص."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(UserProfile.tags.ilike(f"%{tag}%"))
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def add_tag(user_id: int, tag: str) -> bool:
    """افزودن تگ به کاربر (اگه پروفایل هنوز وجود نداشته باشه، می‌سازدش)."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            profile = UserProfile(user_id=user_id)
            session.add(profile)
        current_tags = set(profile.tags.split(",")) if profile.tags else set()
        current_tags.add(tag.strip())
        profile.tags = ",".join(filter(None, current_tags))
        await session.commit()
        return True


async def remove_tag(user_id: int, tag: str) -> bool:
    """حذف تگ از کاربر."""
    async with session_scope() as session:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile or not profile.tags:
            return False
        tags = [t.strip() for t in profile.tags.split(",") if t.strip() != tag.strip()]
        profile.tags = ",".join(tags) if tags else None
        await session.commit()
        return True