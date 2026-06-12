from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from dependency_injector.wiring import Provide, inject
from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork(Protocol):
    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkImpl:
    @inject
    def __init__(
        self,
        session_factory: Callable[[], Any] = Provide["DEFAULT_SESSION_FACTORY"],
    ) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        if self.session is not None:
            await self.session.aclose()

    async def commit(self) -> None:
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        if self.session is not None:
            await self.session.rollback()
