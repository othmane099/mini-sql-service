from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from connections.models import DBType

_HOSTNAME_RE = re.compile(
    r"^(?:"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"  # hostname
    r"|(?:\d{1,3}\.){3}\d{1,3}"  # IPv4
    r"|localhost"
    r")$"
)


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("name", "database", "username", mode="before")
    @classmethod
    def strip_and_reject_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must not be blank")
        if re.search(r"\s", v):
            raise ValueError("field must not contain whitespace")
        return v

    @field_validator("host", mode="before")
    @classmethod
    def validate_host(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("host must not be blank")
        if not _HOSTNAME_RE.match(v):
            raise ValueError(f"'{v}' is not a valid hostname or IP address")
        return v


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    db_type: DBType
    host: str
    port: int
    database: str
    username: str
    created_at: datetime


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool
    foreign_key: str | None


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]


class SchemaResponse(BaseModel):
    connection_id: uuid.UUID
    connection_name: str
    tables: list[TableInfo]


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
