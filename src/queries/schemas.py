from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class QueryResponse(BaseModel):
    sql: str
    explanation: str


class ExecuteRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=8000)


class ExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]


class ExplainRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=8000)


class ExplainResponse(BaseModel):
    explanation: str
