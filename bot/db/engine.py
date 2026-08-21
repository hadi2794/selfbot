"""
موتور اتصال به PostgreSQL: SQLAlchemy 2.x (async) + درایور psycopg 3.

نکات مهم:
- اتصال فقط و فقط از روی متغیر محیطی DATABASE_URL خونده می‌شه. هیچ‌جای دیگه‌ی
  کد نباید host/user/password/دیتابیس رو هاردکد کنه.
- Connection Pool با pool_pre_ping=True و pool_recycle ساخته می‌شه تا کانکشن‌های
  مرده (مثلاً بعد از idle طولانی روی زیرساخت‌های مدیریت‌شده مثل Railway) خودکار
  دوباره‌سازی بشن و به خطاهای عجیب در وسط request نخوریم.
- session_scope() یک واحد کاریِ (Unit of Work) کامل با commit/rollback خودکار
  می‌سازه؛ همه‌ی Repository ها از همین استفاده می‌کنن تا هیچ Session بازی
  نیمه‌کاره یا connection اضافه‌ای باز نمونه.
"""
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from .. import config

logger = logging.getLogger("selfbot.db")


def _normalize_database_url(raw_url: str) -> str:
    """
    Railway/Heroku و اکثر سرویس‌های PostgreSQL معمولاً DATABASE_URL رو با
    اسکیمِ ``postgres://`` یا ``postgresql://`` می‌دن. درایور asyncِ ما
    (psycopg 3 از طریق SQLAlchemy) نیاز داره اسکیم دقیقاً
    ``postgresql+psycopg://`` باشه؛ این تابع فقط همین تبدیل رو انجام می‌ده و
    بقیه‌ی URL (هاست/یوزر/پسورد/دیتابیس/query params) رو دست‌نخورده می‌ذاره.
    """
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL تنظیم نشده. این پروژه دیگه از فایل JSON برای ذخیره‌سازی "
            "استفاده نمی‌کنه؛ باید یک اتصال PostgreSQL (مثلاً Plugin پستگرسِ "
            "Railway) بسازی و متغیر محیطی DATABASE_URL رو روی connection string "
            "اون ست کنی."
        )
    parts = urlsplit(raw_url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+psycopg"
    elif scheme == "postgresql+psycopg":
        pass
    else:
        # اسکیم دیگه‌ای (مثلاً sqlite برای تست‌های محلی) رو دست‌نخورده برمی‌گردونیم
        return raw_url
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


DATABASE_URL = _normalize_database_url(config.DATABASE_URL)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool if _is_sqlite else AsyncAdaptedQueuePool,
    pool_size=None if _is_sqlite else config.DB_POOL_SIZE,
    max_overflow=None if _is_sqlite else config.DB_MAX_OVERFLOW,
    pool_pre_ping=not _is_sqlite,  # جلوگیری از استفاده از کانکشنِ مرده بعد از idle طولانی
    pool_recycle=None if _is_sqlite else config.DB_POOL_RECYCLE_SECONDS,
    echo=config.DB_ECHO,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope():
    """
    یک واحد کاریِ کامل: Session می‌سازه، در پایان commit می‌کنه، و اگه هر
    خطایی وسطش بیفته rollback می‌کنه و همون خطا رو دوباره raise می‌کنه (تا
    caller بفهمه چیزی ذخیره نشده). در هر حالت، در نهایت Session بسته می‌شه تا
    connection به pool برگرده و connection اضافه باز نمونه.
    """
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("خطا در تراکنش دیتابیس - rollback شد")
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """در خاموش‌شدنِ تمیزِ پروسه صدا زده می‌شه تا همه‌ی کانکشن‌های pool بسته بشن."""
    await engine.dispose()
