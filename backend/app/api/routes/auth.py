"""Authentication API endpoints."""

import asyncio
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.api.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.models import User
from app.services.cache import CacheService, get_cache_service

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
    db: DBSession,
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> TokenResponse:
    """
    Register a new user account.
    
    - **email**: Valid email address (unique)
    - **username**: 3-50 characters, alphanumeric with _ and - (unique)
    - **password**: 8-100 characters
    
    Uses write-through caching: DB + Cache writes in parallel.
    """
    settings = get_settings()
    
    # Start password hashing in parallel (CPU-bound, safe to run concurrently)
    password_hash_task = asyncio.create_task(get_password_hash(user_data.password))
    
    # Run DB queries sequentially (async sessions don't support concurrent operations)
    email_check = await db.execute(select(User).where(User.email == user_data.email))
    if email_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    username_check = await db.execute(select(User).where(User.username == user_data.username))
    if username_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
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
    await db.flush()
    await db.refresh(user)

    # Capture user data immediately while session is valid
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
    )

    logger.info("User registered", user_id=user.id, username=user.username)

    # Write-through: Populate cache in parallel with token generation
    cache_task = None
    if cache.is_available:
        cache_task = asyncio.create_task(
            cache.set_user_data(user.id, {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "hashed_password": user.hashed_password,
                "created_at": user.created_at.isoformat(),
            })
        )

    # Generate access token
    access_token = create_access_token(data={"sub": str(user.id)})
    expires_in = settings.jwt_access_token_expire_days * 24 * 60 * 60

    # Await cache task if started (don't block on failure)
    if cache_task:
        try:
            await cache_task
        except Exception as e:
            logger.warning("Cache write-through failed", error=str(e))

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=user_response,
    )


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
    db: DBSession,
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> TokenResponse:
    """
    Authenticate user and return JWT token.
    
    - **email**: Registered email address
    - **password**: User password
    
    Uses cache-first lookup for faster authentication.
    """
    settings = get_settings()
    user = None
    user_response = None
    from_cache = False
    
    # Try cache first for faster lookup (using email index)
    if cache.is_available:
        cached_user = await cache.get_user_by_email(credentials.email)
        if cached_user:
            # Create User object from cached data for password verification
            user = User(
                id=cached_user["id"],
                email=cached_user["email"],
                username=cached_user["username"],
                hashed_password=cached_user["hashed_password"],
            )
            # Create response from cached data (includes created_at)
            user_response = UserResponse(
                id=cached_user["id"],
                email=cached_user["email"],
                username=cached_user["username"],
                created_at=datetime.fromisoformat(cached_user["created_at"]) if cached_user.get("created_at") else datetime.now(),
            )
            from_cache = True
    
    # Cache miss - fallback to database
    if not user:
        result = await db.execute(select(User).where(User.email == credentials.email))
        user = result.scalar_one_or_none()

    if not user:
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

    logger.info("User logged in", user_id=user.id, username=user.username, from_cache=from_cache)

    # Build user response from DB if not from cache
    if not user_response:
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            created_at=user.created_at,
        )

    # Write-through: Populate/refresh cache if not from cache
    if not from_cache and cache.is_available:
        asyncio.create_task(
            cache.set_user_data(user.id, {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "hashed_password": user.hashed_password,
                "created_at": user.created_at.isoformat(),
            })
        )

    # Generate access token
    access_token = create_access_token(data={"sub": str(user.id)})
    expires_in = settings.jwt_access_token_expire_days * 24 * 60 * 60

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=user_response,
    )


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

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(current_user, from_attributes=True),
    )
