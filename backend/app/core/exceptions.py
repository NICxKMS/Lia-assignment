"""Custom exception classes and exception handlers."""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_cors_headers(request: Request) -> dict[str, str]:
    """Get CORS headers for error responses."""
    origin = request.headers.get("origin", "")
    # Import here to avoid circular imports
    from app.core.config import get_settings
    settings = get_settings()

    # Check if origin is allowed
    if origin and (origin in settings.cors_origins or "*" in settings.cors_origins):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Request-ID",
        }
    return {}


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(AppError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(AppError):
    """Authorization failed."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status.HTTP_409_CONFLICT)


class ValidationError(AppError):
    """Validation error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class RateLimitError(AppError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            "Rate limit exceeded. Please try again later.",
            status.HTTP_429_TOO_MANY_REQUESTS,
            {"retry_after": retry_after},
        )


class LLMProviderError(AppError):
    """LLM provider error."""

    def __init__(self, provider: str, message: str):
        super().__init__(
            f"LLM provider error ({provider}): {message}",
            status.HTTP_502_BAD_GATEWAY,
            {"provider": provider},
        )


class DatabaseError(AppError):
    """Database operation error."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE)


class CacheError(AppError):
    """Cache operation error (non-fatal, logged only)."""

    def __init__(self, message: str = "Cache operation failed"):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE)


async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle application exceptions."""
    logger.warning(
        "Application exception",
        status_code=exc.status_code,
        message=exc.message,
        details=exc.details,
        path=str(request.url),
    )

    headers = _get_cors_headers(request)

    # Add Retry-After header for 429 rate-limit responses
    if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        retry_after = exc.details.get("retry_after")
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "details": exc.details,
            }
        },
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=str(request.url),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
            }
        },
        headers=_get_cors_headers(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    logger.exception(
        "Unhandled exception",
        exc_info=exc,
        path=str(request.url),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An internal error occurred. Please try again later.",
            }
        },
        headers=_get_cors_headers(request),
    )
