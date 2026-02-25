"""Shared background task utilities."""

import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def create_background_task(
    coro: Coroutine[Any, Any, Any], *, name: str = ""
) -> asyncio.Task[Any]:
    """Create an asyncio task with exception logging."""
    task: asyncio.Task[Any] = asyncio.create_task(coro)

    def _done(t: asyncio.Task[Any]) -> None:
        if t.cancelled():
            return
        if exc := t.exception():
            logger.error("Background task failed", task_name=name, error=str(exc))

    task.add_done_callback(_done)
    return task
