"""Security utilities for JWT authentication and password hashing.

Uses bcrypt for password hashing and python-jose for JWT.
All operations are designed to be non-blocking for async usage.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.
    
    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    
    def _verify() -> bool:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    
    return await loop.run_in_executor(None, _verify)


async def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.
    
    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    
    def _hash() -> str:
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")
    
    return await loop.run_in_executor(None, _hash)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.
    
    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_access_token_expire_days
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    })
    
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


def create_refresh_token(user_id: int) -> str:
    """Create a refresh token with extended expiration.
    
    Args:
        user_id: User ID to encode in the token
        
    Returns:
        Encoded JWT refresh token
    """
    return create_access_token(
        data={"sub": str(user_id), "type": "refresh"},
        expires_delta=timedelta(days=30),
    )
