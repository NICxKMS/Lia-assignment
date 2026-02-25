"""FastAPI application entry point."""

import asyncio as _asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth_router, chat_router, health_router
from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db, init_db
from app.services.cache import get_cache_service
from app.services.llm import get_llm_service
from app.services.rate_limit import get_rate_limit_service
from app.services.sentiment import get_sentiment_service

# Initialize logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events.

    Startup:
    - Initialize database connections
    - Pre-warm LLM adapters to eliminate first-request latency

    Shutdown:
    - Close database connections
    - Close HTTP client connections (rate limiter)
    """
    settings = get_settings()

    logger.info(
        "Starting application",
        app_name=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # Initialize database with retry logic for transient connection failures
    for _attempt in range(3):
        try:
            await init_db()
            break
        except Exception as exc:
            if _attempt == 2:
                logger.error("Failed to initialize database after 3 attempts", error=str(exc))
                raise
            logger.warning(
                "Database init failed, retrying...",
                attempt=_attempt + 1,
                error=str(exc),
            )
            await _asyncio.sleep(2 ** _attempt)
    logger.info("Database initialized")

    # Pre-warm LLM adapters to eliminate first-request latency
    llm_service = get_llm_service()
    llm_service.prewarm_adapters()
    logger.info("LLM adapters pre-warmed")

    # Warm static caches (models, sentiment methods) if cache is configured
    cache_service = get_cache_service()
    sentiment_service = get_sentiment_service()
    if cache_service.is_available:
        await cache_service.set_available_models(llm_service.get_all_models())
        await cache_service.set_sentiment_methods(sentiment_service.get_available_methods())
        logger.info("Static caches warmed")

    yield

    # Cleanup
    logger.info("Shutting down application")

    # Close LLM adapter HTTP clients
    llm = get_llm_service()
    await llm.close()
    logger.info("LLM adapter connections closed")

    # Close rate limiter HTTP client
    rate_limiter = get_rate_limit_service()
    await rate_limiter.close()
    logger.info("Rate limiter connections closed")

    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI Chatbot API with Multi-LLM Support and Sentiment Analysis",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    # Security headers middleware
    from starlette.middleware.base import BaseHTTPMiddleware

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Any, call_next: Any) -> Any:
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if not settings.debug:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # GZip compression for responses
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # Register exception handlers
    app.add_exception_handler(AppError, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")

    return app


# Create application instance
app = create_app()
