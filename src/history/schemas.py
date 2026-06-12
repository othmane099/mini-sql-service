from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from history.models import QueryEventType


class QueryHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    event_type: QueryEventType
    question: str | None
    sql: str
    explanation: str | None
    row_count: int | None
    created_at: datetime
