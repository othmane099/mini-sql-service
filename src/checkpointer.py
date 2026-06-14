from __future__ import annotations

from collections.abc import AsyncGenerator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from config import settings


async def create_checkpointer() -> AsyncGenerator[AsyncPostgresSaver]:
    conn_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
