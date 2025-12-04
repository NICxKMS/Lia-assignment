"""API dependencies for FastAPI routes."""

import asyncio
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, RateLimitError
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db
from app.services.cache import CacheService, get_cache_service
from app.services.rate_limit import RateLimitService, get_rate_limit_service

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> User:
    """Get the current authenticated user from JWT token.
    
    Uses cache-aside pattern to reduce database lookups.
    
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode and validate token
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
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
            # Reconstruct User object from cached data
            user = User(
                id=cached_user["id"],
                email=cached_user["email"],
                username=cached_user["username"],
                hashed_password=cached_user["hashed_password"],
            )
            # Mark as not new (from cache)
            return user

    # Cache miss - fetch user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Write-through: Cache user data asynchronously (don't block response)
    if cache.is_available:
        asyncio.create_task(
            cache.set_user_data(user_id, {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "hashed_password": user.hashed_password,
                "created_at": user.created_at.isoformat(),
            })
        )

    return user


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> User | None:
    """Get the current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db, cache)
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
        # Use client IP from X-Forwarded-For or direct connection
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            identifier = f"ip:{forwarded.split(',')[0].strip()}"
        else:
            identifier = f"ip:{request.client.host if request.client else 'unknown'}"

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
