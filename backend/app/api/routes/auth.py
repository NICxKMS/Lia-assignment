"""Authentication API endpoints."""

import asyncio
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DBSession
from app.api.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.core.logging import get_logger
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.tasks import create_background_task
from app.db.models import User
from app.services.cache import CacheService, get_cache_service
from app.services.rate_limit import RateLimitService, get_rate_limit_service

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        400: {"description": "Email or username already exists"},
    },
)
async def register(
    user_data: UserCreate,
    request: Request,
    db: DBSession,
    cache: Annotated[CacheService, Depends(get_cache_service)],
    rate_limiter: Annotated[RateLimitService, Depends(get_rate_limit_service)],
) -> TokenResponse:
    """
    Register a new user account.
    
    - **email**: Valid email address (unique)
    - **username**: 3-50 characters, alphanumeric with _ and - (unique)
    - **password**: 8-100 characters
    
    Uses write-through caching: DB + Cache writes in parallel.
    """
    settings = get_settings()

    # Rate limit auth attempts
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await rate_limiter.check_auth_limit(f"ip:{client_ip}")
    if not allowed:
        raise RateLimitError()

    # Start password hashing in parallel (CPU-bound, safe to run concurrently)
    password_hash_task = asyncio.create_task(get_password_hash(user_data.password))
    
    # Check if email or username already exists (single query to prevent enumeration)
    existing = await db.execute(
        select(User).where(
            or_(User.email == user_data.email, User.username == user_data.username)
        )
    )
    if existing.scalar_one_or_none():
        password_hash_task.cancel()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or username already exists",
        )

    # Await the password hash (should be done by now)
    hashed_password = await password_hash_task

    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists",
        )
    await db.refresh(user)

    # Capture user data immediately while session is valid
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
    )

    logger.info("User registered", user_id=user.id, username=user.username)

    # Write-through: Populate cache in parallel with token generation (no sensitive data)
    if cache.is_available:
        create_background_task(
            cache.set_user_data(user.id, {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "created_at": user.created_at.isoformat(),
            }),
            name="cache_user_register",
        )

    # Generate access token
    access_token = create_access_token(data={"sub": str(user.id)})
    expires_in = settings.jwt_access_token_expire_days * 24 * 60 * 60

    body = TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=user_response,
    )
    resp = JSONResponse(content=body.model_dump(mode="json"), status_code=201)
    resp.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=expires_in,
        path="/",
        domain=settings.cookie_domain,
    )
    return resp


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    credentials: UserLogin,
    request: Request,
    db: DBSession,
    cache: Annotated[CacheService, Depends(get_cache_service)],
    rate_limiter: Annotated[RateLimitService, Depends(get_rate_limit_service)],
) -> TokenResponse:
    """
    Authenticate user and return JWT token.
    
    - **email**: Registered email address
    - **password**: User password
    
    Uses cache-first lookup for faster authentication.
    """
    settings = get_settings()

    # Rate limit auth attempts
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await rate_limiter.check_auth_limit(f"ip:{client_ip}")
    if not allowed:
        raise RateLimitError()

    # Always fetch from database for login (need verified password hash)
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user:
        # Perform dummy bcrypt to prevent timing-based user enumeration
        try:
            await verify_password("dummy_password", "$2b$12$abcdefghijklmnopqrstuvABCDEFGHIJKLMNOPQRSTUVWXYZ01234")
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password asynchronously
    if not await verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User logged in", user_id=user.id, username=user.username)

    user_response = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
    )

    # Write-through: Cache non-sensitive user data
    if cache.is_available:
        create_background_task(
            cache.set_user_data(user.id, {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "created_at": user.created_at.isoformat(),
            }),
            name="cache_user_login",
        )

    # Generate access token
    access_token = create_access_token(data={"sub": str(user.id)})
    expires_in = settings.jwt_access_token_expire_days * 24 * 60 * 60

    body = TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=user_response,
    )
    response = JSONResponse(content=body.model_dump(mode="json"))
    response.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=expires_in,
        path="/",
        domain=settings.cookie_domain,
    )
    return response


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get the currently authenticated user's information."""
    return UserResponse.model_validate(current_user, from_attributes=True)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    current_user: CurrentUser,
) -> TokenResponse:
    """
    Refresh the access token for the current user.
    
    Requires a valid (non-expired) token.
    """
    settings = get_settings()
    
    # Generate new access token
    access_token = create_access_token(data={"sub": str(current_user.id)})
    expires_in = settings.jwt_access_token_expire_days * 24 * 60 * 60

    body = TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(current_user, from_attributes=True),
    )
    response = JSONResponse(content=body.model_dump(mode="json"))
    response.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=expires_in,
        path="/",
        domain=settings.cookie_domain,
    )
    return response


@router.post(
    "/logout",
    summary="Logout and clear auth cookie",
)
async def logout():
    """Clear the authentication cookie."""
    settings = get_settings()
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        domain=settings.cookie_domain,
    )
    return response
