"""Tests for app.core.exceptions — handlers and error classes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)


def _make_request(origin: str = "") -> MagicMock:
    """Build a minimal mock Starlette Request."""
    req = MagicMock()
    req.headers = {"origin": origin} if origin else {}
    req.url = "http://test/path"
    return req


# =============================================================================
# AppError basics
# =============================================================================

class TestAppError:

    def test_carries_status_and_message(self):
        err = AppError("boom", status_code=418)
        assert err.status_code == 418
        assert err.message == "boom"

    def test_default_status_is_500(self):
        assert AppError("x").status_code == 500

    def test_subclass_status_codes(self):
        assert AuthenticationError().status_code == 401
        assert NotFoundError("Item").status_code == 404


# =============================================================================
# app_exception_handler
# =============================================================================

class TestAppExceptionHandler:

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        """Patch get_settings so CORS origin check works."""
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://allowed.example.com"]
        with patch("app.core.config.get_settings", return_value=mock_settings):
            yield

    async def test_returns_correct_status_and_json(self):
        req = _make_request()
        exc = AppError("not found", status_code=404)
        resp = await app_exception_handler(req, exc)
        assert resp.status_code == 404
        assert b"not found" in resp.body

    async def test_429_includes_retry_after(self):
        req = _make_request()
        exc = RateLimitError(retry_after=30)
        resp = await app_exception_handler(req, exc)
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "30"

    async def test_non_429_has_no_retry_after(self):
        req = _make_request()
        exc = AppError("err", status_code=400)
        resp = await app_exception_handler(req, exc)
        assert "Retry-After" not in resp.headers


# =============================================================================
# http_exception_handler
# =============================================================================

class TestHttpExceptionHandler:

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://allowed.example.com"]
        with patch("app.core.config.get_settings", return_value=mock_settings):
            yield

    async def test_returns_status_and_body(self):
        req = _make_request()
        exc = HTTPException(status_code=403, detail="forbidden")
        resp = await http_exception_handler(req, exc)
        assert resp.status_code == 403
        assert b"forbidden" in resp.body

    async def test_cors_headers_for_allowed_origin(self):
        req = _make_request(origin="http://allowed.example.com")
        exc = HTTPException(status_code=400, detail="bad")
        resp = await http_exception_handler(req, exc)
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://allowed.example.com"

    async def test_no_cors_for_unknown_origin(self):
        req = _make_request(origin="http://evil.example.com")
        exc = HTTPException(status_code=400, detail="bad")
        resp = await http_exception_handler(req, exc)
        assert "Access-Control-Allow-Origin" not in resp.headers


# =============================================================================
# unhandled_exception_handler
# =============================================================================

class TestUnhandledExceptionHandler:

    @pytest.fixture(autouse=True)
    def _patch_settings(self):
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://allowed.example.com"]
        with patch("app.core.config.get_settings", return_value=mock_settings):
            yield

    async def test_returns_500(self):
        req = _make_request()
        resp = await unhandled_exception_handler(req, RuntimeError("kaboom"))
        assert resp.status_code == 500

    async def test_generic_message(self):
        req = _make_request()
        resp = await unhandled_exception_handler(req, RuntimeError("secret"))
        body = bytes(resp.body)
        assert b"internal error" in body.lower()
        assert b"secret" not in body
