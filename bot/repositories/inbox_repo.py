"""
Repository برای صندوق ورودی هوشمند (Inbox).
"""

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
import datetime as dt

from ..db.engine import session_scope
from ..db.models_ext import InboxItem


async def save_item(
    chat_id: int,
    message_id: int,
    text: str,
    sender_id: Optional[int] = None,
    sender_name: Optional[str] = None,
    date: Optional[dt.datetime] = None,
    importance: int = 0,
    tags: Optional[str] = None,
    note: Optional[str] = None,
) -> InboxItem:
    """ذخیره یک پیام در صندوق ورودی."""
    if date is None:
        date = dt.datetime.now(dt.timezone.utc)

    async with session_scope() as session:
        # بررسی وجود رکورد تکراری
        stmt = select(InboxItem).where(
            InboxItem.chat_id == chat_id,
            InboxItem.message_id == message_id
        )
        existing = await session.execute(stmt)
        existing_item = existing.scalar_one_or_none()

        if existing_item:
            # بروزرسانی
            existing_item.text = text
            existing_item.sender_id = sender_id or existing_item.sender_id
            existing_item.sender_name = sender_name or existing_item.sender_name
            existing_item.importance = importance
            existing_item.tags = tags
            existing_item.note = note
            await session.commit()
            return existing_item

        item = InboxItem(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            sender_id=sender_id,
            sender_name=sender_name,
            date=date,
            importance=importance,
            tags=tags,
            note=note,
            read=False,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item


async def mark_read(item_id: int) -> bool:
    """علامت‌گذاری یک آیتم به‌عنوان خوانده‌شده."""
    async with session_scope() as session:
        stmt = update(InboxItem).where(InboxItem.id == item_id).values(read=True)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def mark_unread(item_id: int) -> bool:
    """علامت‌گذاری یک آیتم به‌عنوان خوانده‌نشده."""
    async with session_scope() as session:
        stmt = update(InboxItem).where(InboxItem.id == item_id).values(read=False)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def delete_item(item_id: int) -> bool:
    """حذف یک آیتم از صندوق ورودی."""
    async with session_scope() as session:
        stmt = delete(InboxItem).where(InboxItem.id == item_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def get_items(
    read: Optional[bool] = None,
    importance: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[InboxItem]:
    """دریافت آیتم‌های صندوق ورودی با فیلتر."""
    async with session_scope() as session:
        stmt = select(InboxItem)
        if read is not None:
            stmt = stmt.where(InboxItem.read == read)
        if importance is not None:
            stmt = stmt.where(InboxItem.importance >= importance)
        stmt = stmt.order_by(InboxItem.date.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_stats() -> Dict[str, int]:
    """آمار صندوق ورودی."""
    async with session_scope() as session:
        stmt_all = select(func.count(InboxItem.id))
        all_count = await session.scalar(stmt_all) or 0

        stmt_unread = select(func.count(InboxItem.id)).where(InboxItem.read == False)
        unread_count = await session.scalar(stmt_unread) or 0

        stmt_important = select(func.count(InboxItem.id)).where(InboxItem.importance >= 1)
        important_count = await session.scalar(stmt_important) or 0

        stmt_high = select(func.count(InboxItem.id)).where(InboxItem.importance >= 2)
        high_count = await session.scalar(stmt_high) or 0

        return {
            "total": all_count,
            "unread": unread_count,
            "important": important_count,
            "high": high_count,
        }


async def search_items(query: str, limit: int = 50) -> List[InboxItem]:
    """جستجو در متن آیتم‌ها."""
    async with session_scope() as session:
        stmt = select(InboxItem).where(
            InboxItem.text.ilike(f"%{query}%")
        ).order_by(InboxItem.date.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_by_chat(chat_id: int, limit: int = 50) -> List[InboxItem]:
    """دریافت آیتم‌های یک چت خاص."""
    async with session_scope() as session:
        stmt = select(InboxItem).where(InboxItem.chat_id == chat_id).order_by(
            InboxItem.date.desc()
        ).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())