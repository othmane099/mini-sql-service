from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from connections.api import router as connections_router
from containers import Container
from history.api import router as history_router
from log_config import configure_logging
from queries.api import router as queries_router

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        structlog.contextvars.clear_contextvars()
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    logger.info("app.startup", project=settings.PROJECT_NAME)
    yield
    await app.container.shutdown_resources()  # type: ignore[attr-defined]
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    container = Container()
    container.wire(packages=["connections", "queries", "history"])

    app = FastAPI(title=settings.PROJECT_NAME, debug=settings.is_debug, lifespan=lifespan)
    app.container = container  # type: ignore[attr-defined]

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(connections_router, prefix="/api/v1")
    app.include_router(queries_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")

    return app


app = create_app()
