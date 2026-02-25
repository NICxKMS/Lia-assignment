"""Security utilities for JWT authentication and password hashing.

Uses argon2-cffi for new password hashing, with bcrypt support for legacy hashes.
PyJWT for JWT. All operations are designed to be non-blocking for async usage.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt as pyjwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt.exceptions import InvalidTokenError

from app.core.config import get_settings

_ph = PasswordHasher()


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Supports both argon2 (new) and bcrypt (legacy) hashes.
    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()

    def _verify() -> bool:
        if hashed_password.startswith(("$2b$", "$2a$")):
            # Legacy bcrypt hash
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        # Argon2 hash (default)
        return _ph.verify(hashed_password, plain_password)

    try:
        return await loop.run_in_executor(None, _verify)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


async def get_password_hash(password: str) -> str:
    """Hash a password using argon2.

    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ph.hash, password)


def needs_rehash(hashed: str) -> bool:
    """Check if a password hash should be upgraded to argon2."""
    if hashed.startswith(("$2b$", "$2a$")):
        return True
    return _ph.check_needs_rehash(hashed)


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
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            days=settings.jwt_access_token_expire_days
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(UTC),
    })

    return pyjwt.encode(
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
        payload = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except InvalidTokenError:
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
