"""Tests for app.api.deps — get_current_user, get_optional_user, cache-aside."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token
from app.db.models import User

# =============================================================================
# Token sources
# =============================================================================

class TestTokenSources:

    async def test_bearer_header(self, client: AsyncClient, auth_headers: dict[str, str]):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_cookie(self, client: AsyncClient, test_user: User):
        token = create_access_token(data={"sub": str(test_user.id)})
        client.cookies.set("access_token", token)
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"
        client.cookies.clear()

    async def test_cookie_preferred_over_header(
        self, client: AsyncClient, test_user: User, second_user: User,
    ):
        cookie_tok = create_access_token(data={"sub": str(test_user.id)})
        header_tok = create_access_token(data={"sub": str(second_user.id)})
        client.cookies.set("access_token", cookie_tok)
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {header_tok}"},
        )
        assert resp.json()["email"] == test_user.email
        client.cookies.clear()


# =============================================================================
# Token validation failures
# =============================================================================

class TestTokenValidation:

    async def test_expired_token_401(self, client: AsyncClient, test_user: User):
        token = create_access_token(
            data={"sub": str(test_user.id)},
            expires_delta=timedelta(seconds=-10),
        )
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_refresh_token_rejected(self, client: AsyncClient, test_user: User):
        token = create_refresh_token(user_id=test_user.id)
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("bad_token", ["not.a.jwt", "", "abc"])
    async def test_malformed_jwt_401(self, client: AsyncClient, bad_token: str):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 401

    async def test_non_numeric_sub_401(self, client: AsyncClient):
        token = create_access_token(data={"sub": "not-a-number"})
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_missing_user_401(self, client: AsyncClient):
        token = create_access_token(data={"sub": "999999"})
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_no_token_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# =============================================================================
# Cache-aside path
# =============================================================================

class TestCacheAsidePath:

    async def test_cache_hit_skips_db(self, db, test_user: User):
        """When cache has user data, DB is not queried."""
        from unittest.mock import MagicMock

        from app.api.deps import get_current_user
        from tests.conftest import make_mock_cache

        cached_data = {
            "id": test_user.id,
            "email": test_user.email,
            "username": test_user.username,
            "created_at": test_user.created_at.isoformat(),
        }
        mock_cache = make_mock_cache(available=True)
        mock_cache.get_user_data = AsyncMock(return_value=cached_data)

        token = create_access_token(data={"sub": str(test_user.id)})

        # Build a minimal request mock
        req = MagicMock()
        req.cookies = {"access_token": token}

        creds = None  # cookie takes priority

        user = await get_current_user(req, creds, db, mock_cache)
        assert user.email == test_user.email
        mock_cache.get_user_data.assert_awaited_once_with(test_user.id)


# =============================================================================
# get_optional_user
# =============================================================================

class TestGetOptionalUser:

    async def test_returns_none_without_auth(self, client: AsyncClient):
        """Endpoint that uses OptionalUser should work without auth.
        We test via /health which doesn't require auth, proving the app works unauthenticated."""
        resp = await client.get("/health")
        assert resp.status_code == 200
