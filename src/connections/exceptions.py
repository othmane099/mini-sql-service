from __future__ import annotations

import uuid

from exceptions import DomainException


class ConnectionNotFoundError(DomainException):
    def __init__(self, connection_id: uuid.UUID) -> None:
        super().__init__(f"Connection {connection_id} not found")


class ConnectionNameConflictError(DomainException):
    def __init__(self, name: str) -> None:
        super().__init__(f"Connection with name '{name}' already exists")


class ConnectionFailedError(DomainException):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Could not connect to database: {detail}")


class IntrospectionError(DomainException):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Schema introspection failed: {detail}")
