"""Tests for authentication dependencies (get_current_user).

Tests cover:
- Token read from cookie
- Token read from Authorization header
- Cookie preferred over header
- Expired token returns 401
- Refresh token rejected as access token
- Malformed JWT returns 401
"""

import pytest
from datetime import timedelta
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token
from app.db.models import User


class TestGetCurrentUserTokenSources:
    """Tests for how get_current_user reads tokens."""

    @pytest.mark.asyncio
    async def test_reads_token_from_authorization_header(
        self, client: AsyncClient, auth_headers: dict,
    ):
        """get_current_user accepts token in Authorization header."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_reads_token_from_cookie(
        self, client: AsyncClient, test_user: User,
    ):
        """get_current_user reads token from httponly cookie."""
        token = create_access_token(data={"sub": str(test_user.id)})
        # Set cookie directly on the client
        client.cookies.set("access_token", token)

        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

        # Cleanup
        client.cookies.clear()

    @pytest.mark.asyncio
    async def test_prefers_cookie_over_header(
        self, client: AsyncClient, test_user: User, second_user: User,
    ):
        """get_current_user prefers cookie token over Authorization header."""
        # Cookie token → test_user
        cookie_token = create_access_token(data={"sub": str(test_user.id)})
        # Header token → second_user
        header_token = create_access_token(data={"sub": str(second_user.id)})

        client.cookies.set("access_token", cookie_token)
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {header_token}"},
        )
        assert response.status_code == 200
        # Should resolve to test_user (cookie), not second_user (header)
        assert response.json()["email"] == test_user.email

        client.cookies.clear()

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client: AsyncClient, test_user: User):
        """Expired JWT returns 401."""
        expired_token = create_access_token(
            data={"sub": str(test_user.id)},
            expires_delta=timedelta(seconds=-10),
        )
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_as_access_token(
        self, client: AsyncClient, test_user: User,
    ):
        """Refresh token (type=refresh) is rejected when used as access token."""
        refresh_token = create_refresh_token(user_id=test_user.id)
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_jwt_returns_401(self, client: AsyncClient):
        """Completely invalid JWT string returns 401."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.at.all"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, client: AsyncClient):
        """No token at all returns 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_token_with_invalid_user_id_returns_401(
        self, client: AsyncClient,
    ):
        """Token with non-existent user ID returns 401."""
        token = create_access_token(data={"sub": "999999"})
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_token_with_non_numeric_sub_returns_401(
        self, client: AsyncClient,
    ):
        """Token with non-numeric sub claim returns 401."""
        token = create_access_token(data={"sub": "not-a-number"})
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
