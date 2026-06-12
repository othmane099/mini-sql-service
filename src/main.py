from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from connections.api import router as connections_router
from containers import Container
from log_config import configure_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    logger.info("app.startup", project=settings.PROJECT_NAME)
    yield
    await app.container.shutdown_resources()  # type: ignore[attr-defined]
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    container = Container()
    container.wire(packages=["connections"])

    app = FastAPI(title=settings.PROJECT_NAME, debug=settings.is_debug, lifespan=lifespan)
    app.container = container  # type: ignore[attr-defined]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(connections_router, prefix="/api/v1")

    return app


app = create_app()
