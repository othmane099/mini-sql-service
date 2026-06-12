from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)


class QueryResponse(BaseModel):
    sql: str
    explanation: str


class ExecuteRequest(BaseModel):
    sql: str = Field(min_length=1)


class ExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]


class ExplainRequest(BaseModel):
    sql: str = Field(min_length=1)


class ExplainResponse(BaseModel):
    explanation: str
