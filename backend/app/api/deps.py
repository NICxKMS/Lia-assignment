"""API dependencies for FastAPI routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, RateLimitError
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.core.tasks import create_background_task
from app.db.models import User
from app.db.session import get_db
from app.services.cache import CacheService, get_cache_service
from app.services.rate_limit import RateLimitService, get_rate_limit_service

logger = get_logger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> User:
    """Get the current authenticated user from JWT token.
    
    Reads token from httpOnly cookie first (browser clients),
    falls back to Authorization header (API clients).
    Uses cache-aside pattern to reduce database lookups.
    
    Raises:
        HTTPException: If authentication fails
    """
    settings = get_settings()

    # Try cookie first (browser), then Authorization header (API)
    token: str | None = request.cookies.get(settings.cookie_name)
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject refresh tokens used as access tokens (FIX 5)
    if payload.get("type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot use refresh token as access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try cache first for user data
    if cache.is_available:
        cached_user = await cache.get_user_data(user_id)
        if cached_user:
            # Reconstruct User object from cached data (no password needed — JWT proves identity)
            from datetime import datetime
            user = User(
                id=cached_user["id"],
                email=cached_user["email"],
                username=cached_user["username"],
                hashed_password="",
                created_at=datetime.fromisoformat(cached_user["created_at"]) if cached_user.get("created_at") else datetime.now(),
            )
            # Mark as not new (from cache)
            return user

    # Cache miss - fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Write-through: Cache user data asynchronously (don't block response)
    if cache.is_available:
        create_background_task(
            cache.set_user_data(user_id, {
                "id": db_user.id,
                "email": db_user.email,
                "username": db_user.username,
                "created_at": db_user.created_at.isoformat(),
            }),
            name="cache_user_get_current",
        )

    return db_user


async def get_optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> User | None:
    """Get the current user if authenticated, None otherwise."""
    settings = get_settings()
    has_cookie = settings.cookie_name in request.cookies
    if not credentials and not has_cookie:
        return None

    try:
        return await get_current_user(request, credentials, db, cache)
    except HTTPException:
        return None


async def check_rate_limit(
    request: Request,
    rate_limiter: Annotated[RateLimitService, Depends(get_rate_limit_service)],
    user: User | None = None,
) -> None:
    """Check general API rate limit.
    
    Uses user ID if authenticated, otherwise client IP.
    
    Raises:
        RateLimitError: If rate limit exceeded
    """
    # Determine identifier
    if user:
        identifier = f"user:{user.id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_ip}"

    allowed, remaining = await rate_limiter.check_general_limit(identifier)
    
    if not allowed:
        raise RateLimitError()


async def check_chat_rate_limit(
    user: User,
    rate_limiter: Annotated[RateLimitService, Depends(get_rate_limit_service)],
) -> None:
    """Check chat-specific rate limit.
    
    Raises:
        RateLimitError: If rate limit exceeded
    """
    allowed, remaining = await rate_limiter.check_chat_limit(f"user:{user.id}")
    
    if not allowed:
        raise RateLimitError()


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
