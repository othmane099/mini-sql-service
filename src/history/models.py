from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class QueryEventType(StrEnum):
    GENERATE = "generate"
    EXECUTE = "execute"


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    event_type: Mapped[QueryEventType] = mapped_column(
        Enum(QueryEventType, name="queryeventtype", values_callable=lambda x: [e.value for e in x]),
    )
    question: Mapped[str | None] = mapped_column(Text)
    sql: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
