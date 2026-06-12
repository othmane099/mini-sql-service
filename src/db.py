from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config import settings as app_settings

Base = declarative_base()


async def db_resource() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    engine_kwargs = {
        "pool_size": app_settings.DATABASE_POOL_SIZE,
        "pool_recycle": app_settings.DATABASE_POOL_TTL,
        "pool_pre_ping": app_settings.DATABASE_POOL_PRE_PING,
    }
    engine = create_async_engine(app_settings.DATABASE_URL, **engine_kwargs)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
