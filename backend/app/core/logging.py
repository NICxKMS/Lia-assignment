"""Structured logging configuration using structlog.

Provides JSON-formatted logs for production and colored console
output for development. Includes request ID correlation.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import get_settings


def add_app_context(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application context to log events."""
    settings = get_settings()
    event_dict["app"] = settings.app_name
    event_dict["version"] = settings.app_version
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()
    
    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_app_context,
    ]

    if settings.debug:
        # Development: colored console output
        processors: list[Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    log_level = getattr(logging, settings.log_level)
    
    # Root logger configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.db_echo else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Suppress Google GenAI SDK "AFC is enabled" info messages
    # The SDK uses logger name "google_genai.models"
    logging.getLogger("google_genai.models").setLevel(logging.WARNING)
    logging.getLogger("google.genai").setLevel(logging.WARNING)
    logging.getLogger("google.generativeai").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
