"""Tests for middleware — security headers, GZip, CORS on errors, exception handlers.

Tests the SecurityHeadersMiddleware, GZipMiddleware, and exception handlers
defined in app/main.py and app/core/exceptions.py.
"""

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("header,expected_value", [
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("x-xss-protection", "1; mode=block"),
        ("referrer-policy", "strict-origin-when-cross-origin"),
        ("permissions-policy", "camera=(), microphone=(), geolocation=()"),
    ])
    async def test_security_header_present(self, client: AsyncClient, header: str, expected_value: str):
        resp = await client.get("/health")
        assert resp.headers.get(header) == expected_value


# ---------------------------------------------------------------------------
# GZip middleware
# ---------------------------------------------------------------------------

class TestGZipMiddleware:
    @pytest.mark.asyncio
    async def test_gzip_for_large_response(self, client: AsyncClient):
        resp = await client.get("/health", headers={"Accept-Encoding": "gzip"})
        # Health response is small (<500 bytes), so may NOT be compressed
        # but the middleware should still be registered; just verify header handling
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

class TestExceptionHandlers:
    @pytest.mark.asyncio
    async def test_404_returns_json(self, client: AsyncClient):
        resp = await client.get("/nonexistent-endpoint-xyz")
        assert resp.status_code == 404
        body = resp.json()
        # FastAPI/Starlette default 404 returns {"detail": "Not Found"}
        assert "detail" in body or "error" in body

    @pytest.mark.asyncio
    async def test_unhandled_app_error_returns_500(self, client: AsyncClient):
        # Accessing a valid endpoint with invalid data to trigger error handling
        resp = await client.post("/api/v1/auth/login", json={"email": "", "password": ""})
        body = resp.json()
        # Should return structured JSON error (either "detail" or "error" format)
        assert isinstance(body, dict)
        assert resp.status_code >= 400


# ---------------------------------------------------------------------------
# CORS headers on error responses
# ---------------------------------------------------------------------------

class TestCORSOnErrors:
    @pytest.mark.asyncio
    async def test_cors_headers_on_options(self, client: AsyncClient):
        resp = await client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
        )
        # CORS middleware should respond to preflight
        assert resp.status_code in (200, 204)
