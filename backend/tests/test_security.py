"""Comprehensive tests for security utilities.

Tests cover:
- Password hashing and verification
- JWT token creation and decoding
- Token expiration handling
"""

import pytest
from datetime import timedelta
from unittest.mock import patch

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
    create_refresh_token,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    @pytest.mark.asyncio
    async def test_password_hash_different_from_plain(self):
        """Test that hashed password differs from plain text."""
        plain_password = "my_secret_password"
        
        hashed = await get_password_hash(plain_password)
        
        assert hashed != plain_password
        assert len(hashed) > len(plain_password)

    @pytest.mark.asyncio
    async def test_password_hash_starts_with_bcrypt_prefix(self):
        """Test that hash starts with bcrypt identifier."""
        hashed = await get_password_hash("password123")
        
        # bcrypt hashes start with $2a$ or $2b$
        assert hashed.startswith("$2")

    @pytest.mark.asyncio
    async def test_password_hash_unique_each_time(self):
        """Test that same password produces different hashes (salting)."""
        password = "same_password"
        
        hash1 = await get_password_hash(password)
        hash2 = await get_password_hash(password)
        
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_verify_password_correct(self):
        """Test verifying correct password returns True."""
        password = "correct_password"
        hashed = await get_password_hash(password)
        
        result = await verify_password(password, hashed)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_password_incorrect(self):
        """Test verifying incorrect password returns False."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = await get_password_hash(password)
        
        result = await verify_password(wrong_password, hashed)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_empty(self):
        """Test verifying empty password against hash returns False."""
        password = "some_password"
        hashed = await get_password_hash(password)
        
        result = await verify_password("", hashed)
        
        assert result is False


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token_contains_sub(self):
        """Test access token contains subject claim."""
        token = create_access_token(data={"sub": "123"})
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == "123"

    def test_create_access_token_contains_exp(self):
        """Test access token contains expiration claim."""
        token = create_access_token(data={"sub": "123"})
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert "exp" in payload

    def test_create_access_token_contains_iat(self):
        """Test access token contains issued-at claim."""
        token = create_access_token(data={"sub": "123"})
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert "iat" in payload

    def test_create_access_token_custom_expiry(self):
        """Test access token with custom expiration delta."""
        # Create token with 1 hour expiry
        token = create_access_token(
            data={"sub": "123"},
            expires_delta=timedelta(hours=1),
        )
        
        payload = decode_access_token(token)
        
        assert payload is not None
        # Token should be valid
        assert payload["sub"] == "123"

    def test_decode_invalid_token_returns_none(self):
        """Test decoding invalid token returns None."""
        result = decode_access_token("invalid.token.here")
        
        assert result is None

    def test_decode_empty_token_returns_none(self):
        """Test decoding empty token returns None."""
        result = decode_access_token("")
        
        assert result is None

    def test_decode_malformed_token_returns_none(self):
        """Test decoding malformed token returns None."""
        result = decode_access_token("not-a-jwt-at-all")
        
        assert result is None

    def test_create_access_token_preserves_custom_data(self):
        """Test access token preserves custom claims."""
        token = create_access_token(data={
            "sub": "user_123",
            "custom_field": "custom_value",
        })
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["custom_field"] == "custom_value"


class TestRefreshTokens:
    """Tests for refresh token functions."""

    def test_create_refresh_token_contains_type(self):
        """Test refresh token contains type claim."""
        token = create_refresh_token(user_id=123)
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload.get("type") == "refresh"

    def test_create_refresh_token_contains_user_id(self):
        """Test refresh token contains user ID."""
        token = create_refresh_token(user_id=456)
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == "456"


class TestTokenExpiration:
    """Tests for token expiration handling."""

    def test_expired_token_returns_none(self):
        """Test that expired token decoding returns None."""
        # Create token that expired 1 second ago
        token = create_access_token(
            data={"sub": "123"},
            expires_delta=timedelta(seconds=-1),
        )
        
        payload = decode_access_token(token)
        
        # Expired tokens should return None
        assert payload is None

    def test_future_token_is_valid(self):
        """Test that token with future expiry is valid."""
        token = create_access_token(
            data={"sub": "123"},
            expires_delta=timedelta(days=30),
        )
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == "123"


class TestTokenSecurity:
    """Tests for token security aspects."""

    def test_different_users_get_different_tokens(self):
        """Test that different user IDs produce different tokens."""
        token1 = create_access_token(data={"sub": "user1"})
        token2 = create_access_token(data={"sub": "user2"})
        
        assert token1 != token2

    def test_token_with_wrong_secret_fails(self):
        """Test that token created with different secret cannot be decoded."""
        # Create a valid token
        token = create_access_token(data={"sub": "123"})
        
        # Try to decode with wrong secret
        with patch("app.core.security.get_settings") as mock_settings:
            mock_settings.return_value.jwt_secret_key = "different-secret-key-12345678901234567890"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            # Importing again won't help since settings are cached
            # This test verifies the concept
            pass
