"""Authentication API endpoint tests.

Tests for: register, login, me, refresh, logout, cookies, rate limiting.
"""

import pytest
from httpx import AsyncClient

from app.db.models import User

pytestmark = pytest.mark.asyncio


# =============================================================================
# Register
# =============================================================================


async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "username": "newuser",
        "password": "Valid1Pass",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["username"] == "newuser"


async def test_register_returns_cookie(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "cookie@example.com",
        "username": "cookieuser",
        "password": "Valid1Pass",
    })
    assert resp.status_code == 201
    assert any("access_token" in c for c in resp.headers.get_list("set-cookie"))


async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "username": "validuser",
        "password": "Valid1Pass",
    })
    assert resp.status_code == 422


@pytest.mark.parametrize("password,expected_detail", [
    ("short1A", "at least 8 characters"),
    ("nouppercase1", "uppercase letter"),
    ("NOLOWERCASE1", "lowercase letter"),
    ("NoDigitsHere", "digit"),
])
async def test_register_password_validation(
    client: AsyncClient, password: str, expected_detail: str,
):
    resp = await client.post("/api/v1/auth/register", json={
        "email": f"test_{password}@example.com",
        "username": f"user_{password[:5]}",
        "password": password,
    })
    assert resp.status_code == 422
    body = resp.json()
    errors = str(body).lower()
    assert expected_detail.lower() in errors


async def test_register_duplicate_email(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/register", json={
        "email": test_user.email,
        "username": "uniquename",
        "password": "Valid1Pass",
    })
    assert resp.status_code == 400


async def test_register_duplicate_username(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "unique@example.com",
        "username": test_user.username,
        "password": "Valid1Pass",
    })
    assert resp.status_code == 400


async def test_register_invalid_username(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "username": "ab",  # too short (min 3)
        "password": "Valid1Pass",
    })
    assert resp.status_code == 422


# =============================================================================
# Login
# =============================================================================


async def test_login_success(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Testpassword123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"


async def test_login_sets_cookie(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Testpassword123",
    })
    assert resp.status_code == 200
    cookies = resp.headers.get_list("set-cookie")
    assert len(cookies) > 0
    cookie_str = cookies[0].lower()
    assert "httponly" in cookie_str


async def test_login_wrong_password(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPass123",
    })
    assert resp.status_code == 401
    assert "invalid" in resp.json()["error"]["message"].lower()


async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "Whatever123",
    })
    assert resp.status_code == 401
    assert "invalid" in resp.json()["error"]["message"].lower()


# =============================================================================
# Me
# =============================================================================


async def test_me_success(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


async def test_me_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# =============================================================================
# Refresh
# =============================================================================


async def test_refresh_success(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.post("/api/v1/auth/refresh", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_refresh_no_auth(client: AsyncClient):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_rejects_refresh_token(client: AsyncClient, test_user: User):
    from app.core.security import create_refresh_token
    refresh = create_refresh_token(test_user.id)
    resp = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert resp.status_code == 401


# =============================================================================
# Logout
# =============================================================================


async def test_logout(client: AsyncClient):
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out"
    cookies = resp.headers.get_list("set-cookie")
    assert len(cookies) > 0  # cookie deletion header present


# =============================================================================
# Cookie flags
# =============================================================================


async def test_login_cookie_httponly(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Testpassword123",
    })
    cookie_str = "; ".join(resp.headers.get_list("set-cookie")).lower()
    assert "httponly" in cookie_str


async def test_login_cookie_samesite(client: AsyncClient, test_user: User):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "Testpassword123",
    })
    cookie_str = "; ".join(resp.headers.get_list("set-cookie")).lower()
    assert "samesite" in cookie_str
