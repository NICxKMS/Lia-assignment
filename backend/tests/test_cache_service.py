"""Tests for CacheService — unavailable path, key generation, TTLs, available path (mock Redis).

Replaces test_cache.py.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache import (
    KEY_PREFIX_CONVERSATION,
    KEY_PREFIX_DETAIL,
    KEY_PREFIX_HISTORY,
    KEY_PREFIX_USER,
    KEY_PREFIX_USER_MESSAGES,
    TTL_AVAILABLE_MODELS,
    TTL_CONVERSATION_CONTEXT,
    TTL_CONVERSATION_DETAIL,
    TTL_RATE_LIMIT,
    TTL_SENTIMENT_METHODS,
    TTL_USER_CONVERSATIONS,
    TTL_USER_DATA,
    TTL_USER_MESSAGES,
    CacheService,
)

# ---------------------------------------------------------------------------
# Helper — build an unavailable CacheService
# ---------------------------------------------------------------------------

def _unavailable_service() -> CacheService:
    with patch("app.services.cache.base.get_settings") as m:
        m.return_value.redis_available = False
        return CacheService()


def _available_service() -> tuple[CacheService, MagicMock]:
    """Return a CacheService with a mocked Redis client."""
    svc = _unavailable_service()
    mock_client = MagicMock()
    # Mark as available by injecting a client
    svc._client = mock_client
    return svc, mock_client


# ---------------------------------------------------------------------------
# Unavailable path — parametrized
# ---------------------------------------------------------------------------

class TestCacheUnavailable:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args,expected", [
        ("get_conversation_context", ("conv-123",), None),
        ("get_user_messages", ("conv-123",), None),
        ("get_conversation_history", (1,), None),
        ("get_conversation_detail", ("conv-123",), None),
        ("get_user_data", (1,), None),
        ("get_user_by_email", ("a@b.com",), None),
        ("get_available_models", (), None),
        ("get_sentiment_methods", (), None),
        ("get", ("key",), None),
        ("get_json", ("key",), None),
        ("hget", ("k", "f"), None),
        ("hgetall", ("k",), None),
    ])
    async def test_get_methods_return_default(self, method: str, args: tuple[Any, ...], expected):
        svc = _unavailable_service()
        result = await getattr(svc, method)(*args)
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args,expected", [
        ("set_conversation_context", ("conv-123", [{"role": "user", "content": "hi"}]), False),
        ("append_to_context", ("conv-123", {"role": "user", "content": "hi"}), False),
        ("set_user_messages", ("conv-123", ["m1"]), False),
        ("append_user_message", ("conv-123", "m1"), False),
        ("set_conversation_history", (1, 20, [{"id": "c1"}]), False),
        ("set_user_data", (1, {"id": 1, "email": "a@b.com", "username": "u", "hashed_password": "h"}), False),
        ("set_available_models", ({"g": []},), False),
        ("set_sentiment_methods", (["a"],), False),
        ("set", ("k", "v"), False),
        ("set_json", ("k", {"a": 1}), False),
        ("delete", ("k",), False),
        ("hset", ("k", {"f": "v"}), False),
    ])
    async def test_set_methods_return_false(self, method: str, args: tuple[Any, ...], expected):
        svc = _unavailable_service()
        result = await getattr(svc, method)(*args)
        assert result == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args,expected", [
        ("lrange", ("k", 0, -1), []),
        ("zrange", ("k", 0, -1), []),
        ("mget", (["k1", "k2"],), [None, None]),
    ])
    async def test_list_methods_return_empty(self, method: str, args: tuple[Any, ...], expected):
        svc = _unavailable_service()
        result = await getattr(svc, method)(*args)
        assert result == expected

    def test_is_available_false(self):
        svc = _unavailable_service()
        assert svc.is_available is False

    @pytest.mark.asyncio
    async def test_delete_pattern_returns_zero(self):
        svc = _unavailable_service()
        assert await svc.delete_pattern("*") == 0


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    def test_simple_key(self):
        svc = _unavailable_service()
        assert svc._make_key("conv", "123", "context") == "conv:123:context"

    def test_integer_parts(self):
        svc = _unavailable_service()
        assert svc._make_key("user", 42, "data") == "user:42:data"

    @pytest.mark.parametrize("prefix,parts,expected", [
        (KEY_PREFIX_CONVERSATION, ("c1", "context"), "conv:c1:context"),
        (KEY_PREFIX_USER, (1, "data"), "user:1:data"),
        (KEY_PREFIX_HISTORY, (99,), "history:99"),
        (KEY_PREFIX_DETAIL, ("abc",), "detail:abc"),
        (KEY_PREFIX_USER_MESSAGES, ("c1",), "usrmsg:c1"),
    ])
    def test_standard_keys(self, prefix, parts, expected):
        svc = _unavailable_service()
        assert svc._make_key(prefix, *parts) == expected


# ---------------------------------------------------------------------------
# TTL constants sanity
# ---------------------------------------------------------------------------

class TestTTLConstants:
    @pytest.mark.parametrize("ttl,min_val,max_val", [
        (TTL_CONVERSATION_CONTEXT, 60, 7200),
        (TTL_USER_CONVERSATIONS, 60, 3600),
        (TTL_CONVERSATION_DETAIL, 60, 3600),
        (TTL_AVAILABLE_MODELS, 3600, 172800),
        (TTL_RATE_LIMIT, 10, 300),
        (TTL_USER_DATA, 60, 3600),
        (TTL_SENTIMENT_METHODS, 3600, 172800),
        (TTL_USER_MESSAGES, 10, 600),
    ])
    def test_ttl_in_sensible_range(self, ttl: int, min_val: int, max_val: int):
        assert min_val <= ttl <= max_val


# ---------------------------------------------------------------------------
# Available path (mock Redis client)
# ---------------------------------------------------------------------------

class TestCacheAvailable:
    @pytest.mark.asyncio
    async def test_get_returns_string(self):
        svc, client = _available_service()
        client.get = AsyncMock(return_value="value")
        result = await svc.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        svc, client = _available_service()
        client.set = AsyncMock()
        result = await svc.set("k", "v", ttl=60)
        assert result is True
        client.set.assert_called_once_with("k", "v", ex=60)

    @pytest.mark.asyncio
    async def test_set_without_ttl(self):
        svc, client = _available_service()
        client.set = AsyncMock()
        result = await svc.set("k", "v")
        assert result is True
        client.set.assert_called_once_with("k", "v")

    @pytest.mark.asyncio
    async def test_delete_calls_client(self):
        svc, client = _available_service()
        client.delete = AsyncMock()
        result = await svc.delete("k")
        assert result is True
        client.delete.assert_called_once_with("k")

    @pytest.mark.asyncio
    async def test_get_json_parses(self):
        svc, client = _available_service()
        client.get = AsyncMock(return_value=json.dumps({"a": 1}))
        result = await svc.get_json("k")
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_hset_with_ttl(self):
        svc, client = _available_service()
        client.hset = AsyncMock()
        client.expire = AsyncMock()
        result = await svc.hset("k", {"f": "v"}, ttl=300)
        assert result is True
        client.hset.assert_called_once()
        client.expire.assert_called_once_with("k", 300)

    @pytest.mark.asyncio
    async def test_lpush(self):
        svc, client = _available_service()
        client.lpush = AsyncMock()
        result = await svc.lpush("k", "v1", "v2")
        assert result is True
        client.lpush.assert_called_once_with("k", "v1", "v2")

    @pytest.mark.asyncio
    async def test_lrange_returns_list(self):
        svc, client = _available_service()
        client.lrange = AsyncMock(return_value=["a", "b"])
        result = await svc.lrange("k", 0, -1)
        assert result == ["a", "b"]

    @pytest.mark.asyncio
    async def test_get_handles_exception_gracefully(self):
        svc, client = _available_service()
        client.get = AsyncMock(side_effect=Exception("conn error"))
        result = await svc.get("k")
        assert result is None
