"""Tests for RateLimitService — disabled, enabled, parametrized, fail modes, lifecycle.

Replaces previous test_rate_limit.py.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.rate_limit import RateLimitService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pipeline_response(count: int) -> list[dict[str, Any]]:
    return [
        {"result": 0},      # ZREMRANGEBYSCORE
        {"result": 1},      # ZADD
        {"result": 1},      # EXPIRE
        {"result": count},  # ZCARD
    ]


def _disabled_service() -> RateLimitService:
    with patch("app.services.rate_limit.get_settings") as m:
        s = m.return_value
        s.rate_limit_enabled = False
        s.redis_available = False
        s.upstash_redis_rest_url = ""
        s.upstash_redis_rest_token = ""
        s.rate_limit_requests_per_minute = 60
        s.rate_limit_chat_requests_per_minute = 20
        s.rate_limit_auth_requests_per_minute = 10
        return RateLimitService()


def _enabled_service(general: int = 60, chat: int = 20, auth: int = 10) -> RateLimitService:
    with patch("app.services.rate_limit.get_settings") as m:
        s = m.return_value
        s.rate_limit_enabled = True
        s.redis_available = True
        s.upstash_redis_rest_url = "https://fake.upstash.io"
        s.upstash_redis_rest_token = "tok"
        s.rate_limit_requests_per_minute = general
        s.rate_limit_chat_requests_per_minute = chat
        s.rate_limit_auth_requests_per_minute = auth
        return RateLimitService()


def _mock_client(count: int) -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.json.return_value = _pipeline_response(count)
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    return client


# ---------------------------------------------------------------------------
# Disabled
# ---------------------------------------------------------------------------

class TestDisabled:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", [
        "check_general_limit", "check_chat_limit", "check_auth_limit",
    ])
    async def test_all_checks_pass_when_disabled(self, method: str):
        svc = _disabled_service()
        allowed, remaining = await getattr(svc, method)("user:1")
        assert allowed is True
        assert remaining == -1

    def test_is_enabled_false(self):
        assert _disabled_service().is_enabled is False


# ---------------------------------------------------------------------------
# Enabled — parametrized limits
# ---------------------------------------------------------------------------

class TestEnabledLimits:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("check_method,limit_attr", [
        ("check_general_limit", "_general_limit"),
        ("check_chat_limit", "_chat_limit"),
        ("check_auth_limit", "_auth_limit"),
    ])
    async def test_allows_under_limit(self, check_method: str, limit_attr: str):
        svc = _enabled_service()
        limit = getattr(svc, limit_attr)
        svc._client = _mock_client(count=limit - 5)
        allowed, remaining = await getattr(svc, check_method)("id")
        assert allowed is True
        assert remaining == 5

    @pytest.mark.asyncio
    @pytest.mark.parametrize("check_method,limit_attr", [
        ("check_general_limit", "_general_limit"),
        ("check_chat_limit", "_chat_limit"),
        ("check_auth_limit", "_auth_limit"),
    ])
    async def test_blocks_over_limit(self, check_method: str, limit_attr: str):
        svc = _enabled_service()
        limit = getattr(svc, limit_attr)
        svc._client = _mock_client(count=limit + 1)
        allowed, remaining = await getattr(svc, check_method)("id")
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("check_method,limit_attr", [
        ("check_general_limit", "_general_limit"),
        ("check_chat_limit", "_chat_limit"),
        ("check_auth_limit", "_auth_limit"),
    ])
    async def test_boundary_at_exact_limit(self, check_method: str, limit_attr: str):
        svc = _enabled_service()
        limit = getattr(svc, limit_attr)
        svc._client = _mock_client(count=limit)
        allowed, remaining = await getattr(svc, check_method)("id")
        assert allowed is True
        assert remaining == 0


# ---------------------------------------------------------------------------
# Fail modes
# ---------------------------------------------------------------------------

class TestFailModes:
    @pytest.mark.asyncio
    async def test_auth_fail_closed_on_error(self):
        svc = _enabled_service()
        svc._client = AsyncMock(spec=httpx.AsyncClient)
        svc._client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        allowed, remaining = await svc.check_auth_limit("ip:1")
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_general_fail_open_on_error(self):
        svc = _enabled_service()
        svc._client = AsyncMock(spec=httpx.AsyncClient)
        svc._client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        allowed, remaining = await svc.check_general_limit("u:1")
        assert allowed is True
        assert remaining == -1

    @pytest.mark.asyncio
    async def test_chat_fail_open_on_error(self):
        svc = _enabled_service()
        svc._client = AsyncMock(spec=httpx.AsyncClient)
        svc._client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        allowed, remaining = await svc.check_chat_limit("u:1")
        assert allowed is True
        assert remaining == -1


# ---------------------------------------------------------------------------
# Pipeline commands
# ---------------------------------------------------------------------------

class TestPipelineCommands:
    @pytest.mark.asyncio
    async def test_pipeline_sends_four_commands(self):
        svc = _enabled_service()
        svc._client = _mock_client(count=1)
        await svc.check_general_limit("u:1")
        body = svc._client.post.call_args[1]["json"]
        assert len(body) == 4
        assert body[0][0] == "ZREMRANGEBYSCORE"
        assert body[1][0] == "ZADD"
        assert body[2][0] == "EXPIRE"
        assert body[3][0] == "ZCARD"


# ---------------------------------------------------------------------------
# Client lifecycle
# ---------------------------------------------------------------------------

class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        svc = _enabled_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_called_once()
        assert svc._client is None

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        svc = _disabled_service()
        await svc.close()  # should not raise
