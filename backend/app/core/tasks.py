"""Shared background task utilities."""

import asyncio

import structlog

logger = structlog.get_logger(__name__)


def create_background_task(coro, *, name: str = "") -> asyncio.Task:
    """Create an asyncio task with exception logging."""
    task = asyncio.create_task(coro)

    def _done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        if exc := t.exception():
            logger.error("Background task failed", task_name=name, error=str(exc))

    task.add_done_callback(_done)
    return task
