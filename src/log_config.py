from __future__ import annotations

import warnings

import structlog

from config import settings

# LangChain's with_structured_output emits a spurious Pydantic serialization
# warning when used inside astream_events; the parsed output is still correct.
warnings.filterwarnings(
    "ignore",
    message=".*PydanticSerializationUnexpectedValue.*",
    category=UserWarning,
)

# Avoid importing stdlib `logging` — this filename shadows it on sys.path.
_LEVELS: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


def configure_logging() -> None:
    level = _LEVELS.get(settings.LOG_LEVEL.upper(), 20)
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.is_debug
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
