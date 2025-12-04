"""Comprehensive tests for authentication endpoints.

Tests cover:
- User registration (success, validation, duplicates)
- User login (success, invalid credentials)
- Token refresh
- Getting current user info
- Authorization edge cases
"""

import pytest
from httpx import AsyncClient

from app.db.models import User


class TestAuthRegister:
    """Tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "securepass123",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["username"] == "newuser"
        assert "id" in data["user"]
        assert "created_at" in data["user"]
        # Password should never be returned
        assert "password" not in data["user"]
        assert "hashed_password" not in data["user"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration fails with existing email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,  # Use existing user's email
                "username": "differentuser",
                "password": "password123",
            },
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "email" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, test_user: User):
        """Test registration fails with existing username."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "different@example.com",
                "username": test_user.username,  # Use existing user's username
                "password": "password123",
            },
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "username" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration fails with invalid email format."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "username": "testuser",
                "password": "password123",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration fails with password < 8 characters."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "short",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_username(self, client: AsyncClient):
        """Test registration fails with username < 3 characters."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "ab",
                "password": "password123",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username_characters(self, client: AsyncClient):
        """Test registration fails with invalid username characters."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "user@name!",  # Invalid characters
                "password": "password123",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Test registration fails with missing required fields."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                # Missing username and password
            },
        )
        
        assert response.status_code == 422


class TestAuthLogin:
    """Tests for user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login with correct credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login fails with incorrect password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login fails with nonexistent email."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Test login fails with invalid email format."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "invalid-email",
                "password": "password123",
            },
        )
        
        assert response.status_code == 422


class TestAuthMe:
    """Tests for getting current user endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, client: AsyncClient, auth_headers: dict):
        """Test getting current user info with valid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting current user without token fails."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token fails."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_malformed_header(self, client: AsyncClient):
        """Test getting current user with malformed auth header fails."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "NotBearer token"},
        )
        
        assert response.status_code == 401


class TestAuthRefresh:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, auth_headers: dict):
        """Test refreshing token with valid token."""
        import asyncio
        
        # Wait a bit to ensure tokens are generated with different timestamps
        await asyncio.sleep(1.1)
        
        response = await client.post(
            "/api/v1/auth/refresh",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Token should be valid JWT
        assert len(data["access_token"].split(".")) == 3

    @pytest.mark.asyncio
    async def test_refresh_token_unauthorized(self, client: AsyncClient):
        """Test refreshing token without valid token fails."""
        response = await client.post("/api/v1/auth/refresh")
        
        assert response.status_code == 401
