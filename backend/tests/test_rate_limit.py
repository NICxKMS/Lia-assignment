"""Tests for rate limiting service.

Tests cover:
- Chat rate limit allows under limit
- Chat rate limit blocks over limit
- Auth rate limit fail-closed on Redis error
- General rate limit allows when disabled
- Rate limit returns correct remaining count
- Sliding window behavior
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.rate_limit import RateLimitService


def _make_pipeline_response(count: int) -> list[dict]:
    """Build a fake Upstash pipeline response with the given ZCARD count."""
    return [
        {"result": 0},       # ZREMRANGEBYSCORE
        {"result": 1},       # ZADD
        {"result": 1},       # EXPIRE
        {"result": count},   # ZCARD
    ]


class TestRateLimitServiceDisabled:
    """Tests when rate limiting is disabled."""

    @pytest.mark.asyncio
    async def test_check_general_limit_allows_when_disabled(self):
        """General limit returns (True, -1) when disabled."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = False
            mock_settings.return_value.redis_available = False
            mock_settings.return_value.upstash_redis_rest_url = ""
            mock_settings.return_value.upstash_redis_rest_token = ""
            mock_settings.return_value.rate_limit_requests_per_minute = 60
            mock_settings.return_value.rate_limit_chat_requests_per_minute = 20

            service = RateLimitService()
            assert service.is_enabled is False

            allowed, remaining = await service.check_general_limit("user:1")
            assert allowed is True
            assert remaining == -1

    @pytest.mark.asyncio
    async def test_check_chat_limit_allows_when_disabled(self):
        """Chat limit returns (True, -1) when disabled."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = False
            mock_settings.return_value.redis_available = False
            mock_settings.return_value.upstash_redis_rest_url = ""
            mock_settings.return_value.upstash_redis_rest_token = ""
            mock_settings.return_value.rate_limit_requests_per_minute = 60
            mock_settings.return_value.rate_limit_chat_requests_per_minute = 20

            service = RateLimitService()
            allowed, remaining = await service.check_chat_limit("user:1")
            assert allowed is True
            assert remaining == -1

    @pytest.mark.asyncio
    async def test_check_auth_limit_allows_when_disabled(self):
        """Auth limit also short-circuits when disabled."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = False
            mock_settings.return_value.redis_available = False
            mock_settings.return_value.upstash_redis_rest_url = ""
            mock_settings.return_value.upstash_redis_rest_token = ""
            mock_settings.return_value.rate_limit_requests_per_minute = 60
            mock_settings.return_value.rate_limit_chat_requests_per_minute = 20

            service = RateLimitService()
            allowed, remaining = await service.check_auth_limit("ip:127.0.0.1")
            assert allowed is True
            assert remaining == -1


class TestRateLimitServiceEnabled:
    """Tests when rate limiting is enabled (mock HTTP calls)."""

    def _create_enabled_service(self, general_limit: int = 60, chat_limit: int = 20):
        """Create a RateLimitService that thinks it is enabled."""
        with patch("app.services.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_enabled = True
            mock_settings.return_value.redis_available = True
            mock_settings.return_value.upstash_redis_rest_url = "https://fake-redis.upstash.io"
            mock_settings.return_value.upstash_redis_rest_token = "fake-token"
            mock_settings.return_value.rate_limit_requests_per_minute = general_limit
            mock_settings.return_value.rate_limit_chat_requests_per_minute = chat_limit

            service = RateLimitService()
        assert service.is_enabled is True
        return service

    @pytest.mark.asyncio
    async def test_check_chat_limit_allows_under_limit(self):
        """Chat limit allows when count <= limit."""
        service = self._create_enabled_service(chat_limit=20)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = _make_pipeline_response(count=5)
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        service._client = mock_client

        allowed, remaining = await service.check_chat_limit("user:1")
        assert allowed is True
        assert remaining == 15

    @pytest.mark.asyncio
    async def test_check_chat_limit_blocks_over_limit(self):
        """Chat limit blocks when count > limit."""
        service = self._create_enabled_service(chat_limit=20)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = _make_pipeline_response(count=21)
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        service._client = mock_client

        allowed, remaining = await service.check_chat_limit("user:1")
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_check_chat_limit_allows_at_exact_limit(self):
        """Chat limit allows when count == limit (boundary)."""
        service = self._create_enabled_service(chat_limit=20)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = _make_pipeline_response(count=20)
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        service._client = mock_client

        allowed, remaining = await service.check_chat_limit("user:1")
        assert allowed is True
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_check_general_limit_returns_correct_remaining(self):
        """General limit correctly calculates remaining requests."""
        service = self._create_enabled_service(general_limit=60)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = _make_pipeline_response(count=45)
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        service._client = mock_client

        allowed, remaining = await service.check_general_limit("user:1")
        assert allowed is True
        assert remaining == 15

    @pytest.mark.asyncio
    async def test_check_auth_limit_fail_closed_on_redis_error(self):
        """Auth limit denies requests when Redis is unavailable (fail-closed)."""
        service = self._create_enabled_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        service._client = mock_client

        allowed, remaining = await service.check_auth_limit("ip:127.0.0.1")
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_check_general_limit_fail_open_on_redis_error(self):
        """General limit allows requests when Redis is unavailable (fail-open)."""
        service = self._create_enabled_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        service._client = mock_client

        allowed, remaining = await service.check_general_limit("user:1")
        assert allowed is True
        assert remaining == -1

    @pytest.mark.asyncio
    async def test_check_chat_limit_fail_open_on_redis_error(self):
        """Chat limit allows requests when Redis is unavailable (fail-open)."""
        service = self._create_enabled_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        service._client = mock_client

        allowed, remaining = await service.check_chat_limit("user:1")
        assert allowed is True
        assert remaining == -1

    @pytest.mark.asyncio
    async def test_sliding_window_sends_correct_pipeline_commands(self):
        """Verify the sliding window pipeline calls ZREMRANGEBYSCORE, ZADD, EXPIRE, ZCARD."""
        service = self._create_enabled_service(chat_limit=10)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = _make_pipeline_response(count=3)
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        service._client = mock_client

        await service.check_chat_limit("user:42")

        # Verify the pipeline POST was called with correct commands
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://fake-redis.upstash.io/pipeline"

        pipeline_commands = call_args[1]["json"]
        assert len(pipeline_commands) == 4
        assert pipeline_commands[0][0] == "ZREMRANGEBYSCORE"
        assert pipeline_commands[1][0] == "ZADD"
        assert pipeline_commands[2][0] == "EXPIRE"
        assert pipeline_commands[3][0] == "ZCARD"

        # Key should contain the identifier
        assert "ratelimit:chat:user:42" in pipeline_commands[0][1]

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing the HTTP client."""
        service = self._create_enabled_service()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        service._client = mock_client

        await service.close()

        mock_client.aclose.assert_awaited_once()
        assert service._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        """Test closing when client was never created."""
        service = self._create_enabled_service()
        assert service._client is None

        # Should not raise
        await service.close()

    @pytest.mark.asyncio
    async def test_get_client_creates_client_lazily(self):
        """Test that _get_client creates the httpx client on first call."""
        service = self._create_enabled_service()
        assert service._client is None

        client = await service._get_client()
        assert client is not None
        assert service._client is client

        # Second call returns same client
        client2 = await service._get_client()
        assert client2 is client

        # Cleanup
        await service.close()
