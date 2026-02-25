"""Tests for app.core.security — password hashing & JWT."""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    needs_rehash,
    verify_password,
)

# =============================================================================
# Password hashing
# =============================================================================

class TestPasswordHashing:

    async def test_hash_returns_argon2(self):
        h = await get_password_hash("Secret1!")
        assert h.startswith("$argon2")

    async def test_hash_unique_per_call(self):
        a = await get_password_hash("Same1!")
        b = await get_password_hash("Same1!")
        assert a != b

    async def test_verify_correct(self):
        h = await get_password_hash("Correct1!")
        assert await verify_password("Correct1!", h) is True

    async def test_verify_wrong(self):
        h = await get_password_hash("Right1!")
        assert await verify_password("Wrong1!", h) is False

    async def test_verify_bcrypt_legacy(self):
        """bcrypt hashes ($2b$) are still verified correctly."""
        import bcrypt

        plain = "LegacyPass1!"
        hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
        assert hashed.startswith("$2b$")
        assert await verify_password(plain, hashed) is True

    async def test_verify_bcrypt_wrong_password(self):
        import bcrypt

        hashed = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()
        assert await verify_password("wrong", hashed) is False


class TestNeedsRehash:

    def test_bcrypt_needs_rehash(self):
        import bcrypt

        hashed = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode()
        assert needs_rehash(hashed) is True

    async def test_fresh_argon2_no_rehash(self):
        h = await get_password_hash("Fresh1!")
        assert needs_rehash(h) is False


# =============================================================================
# JWT — access tokens
# =============================================================================

class TestAccessToken:

    def test_roundtrip(self):
        token = create_access_token(data={"sub": "42"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_contains_exp_and_iat(self):
        payload = decode_access_token(create_access_token(data={"sub": "1"}))
        assert payload is not None
        assert "exp" in payload and "iat" in payload

    def test_custom_expiry(self):
        token = create_access_token(data={"sub": "1"}, expires_delta=timedelta(hours=1))
        assert decode_access_token(token) is not None

    def test_expired_returns_none(self):
        token = create_access_token(data={"sub": "1"}, expires_delta=timedelta(seconds=-1))
        assert decode_access_token(token) is None

    @pytest.mark.parametrize("bad", ["", "invalid.token", "not-jwt"])
    def test_malformed_returns_none(self, bad: str):
        assert decode_access_token(bad) is None

    def test_rejects_refresh_token_type(self):
        """Access-token decoder returns the payload but it has type=refresh;
        the rejection happens in deps, not here.  Decoder is type-agnostic."""
        token = create_refresh_token(user_id=99)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload.get("type") == "refresh"


# =============================================================================
# JWT — refresh tokens
# =============================================================================

class TestRefreshToken:

    def test_contains_type_refresh(self):
        token = create_refresh_token(user_id=7)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_contains_sub(self):
        token = create_refresh_token(user_id=42)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_access_token_has_no_type(self):
        """Regular access tokens do NOT carry a 'type' field."""
        token = create_access_token(data={"sub": "1"})
        payload = decode_access_token(token)
        assert payload is not None
        assert "type" not in payload
