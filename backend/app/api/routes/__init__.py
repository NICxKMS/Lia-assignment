"""Routes module exports."""

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router

__all__ = [
    "auth_router",
    "chat_router",
    "health_router",
]
