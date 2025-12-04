"""Comprehensive tests for cache service.

Tests cover:
- Cache key generation
- Conversation context caching
- User messages caching (for cumulative sentiment)
- Conversation history caching
- User data caching
- Cache invalidation
- Graceful degradation when cache unavailable
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache import (
    CacheService,
    KEY_PREFIX_CONVERSATION,
    KEY_PREFIX_DETAIL,
    KEY_PREFIX_HISTORY,
    KEY_PREFIX_USER,
    KEY_PREFIX_USER_MESSAGES,
    TTL_CONVERSATION_CONTEXT,
    TTL_USER_MESSAGES,
)


class TestCacheServiceInit:
    """Tests for cache service initialization."""

    def test_init_without_redis(self):
        """Test cache service initializes without Redis config."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            
            assert service.is_available is False

    def test_make_key(self):
        """Test cache key generation."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            
            key = service._make_key("prefix", "part1", "part2")
            assert key == "prefix:part1:part2"
            
            key_with_int = service._make_key("prefix", 123, "part")
            assert key_with_int == "prefix:123:part"


class TestConversationContextCache:
    """Tests for conversation context caching."""

    @pytest.mark.asyncio
    async def test_get_conversation_context_unavailable(self):
        """Test get_conversation_context returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_conversation_context("conv-123")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_conversation_context_unavailable(self):
        """Test set_conversation_context returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_conversation_context(
                "conv-123",
                [{"role": "user", "content": "Hello"}]
            )
            
            assert result is False

    @pytest.mark.asyncio
    async def test_append_to_context_unavailable(self):
        """Test append_to_context returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.append_to_context(
                "conv-123",
                {"role": "user", "content": "Hello"}
            )
            
            assert result is False


class TestUserMessagesCache:
    """Tests for user messages caching (cumulative sentiment)."""

    @pytest.mark.asyncio
    async def test_get_user_messages_unavailable(self):
        """Test get_user_messages returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_user_messages("conv-123")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_user_messages_unavailable(self):
        """Test set_user_messages returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_user_messages(
                "conv-123",
                ["Message 1", "Message 2"]
            )
            
            assert result is False

    @pytest.mark.asyncio
    async def test_set_user_messages_empty_list(self):
        """Test set_user_messages returns False for empty list."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_user_messages("conv-123", [])
            
            assert result is False

    @pytest.mark.asyncio
    async def test_append_user_message_unavailable(self):
        """Test append_user_message returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.append_user_message("conv-123", "New message")
            
            assert result is False


class TestConversationHistoryCache:
    """Tests for conversation history caching."""

    @pytest.mark.asyncio
    async def test_get_conversation_history_unavailable(self):
        """Test get_conversation_history returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_conversation_history(1)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_conversation_history_unavailable(self):
        """Test set_conversation_history returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_conversation_history(
                1, 20,
                [{"id": "conv-1", "title": "Test"}]
            )
            
            assert result is False


class TestUserDataCache:
    """Tests for user data caching."""

    @pytest.mark.asyncio
    async def test_get_user_data_unavailable(self):
        """Test get_user_data returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_user_data(1)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_user_data_unavailable(self):
        """Test set_user_data returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_user_data(1, {
                "id": 1,
                "email": "test@example.com",
                "username": "testuser",
                "hashed_password": "hash",
            })
            
            assert result is False

    @pytest.mark.asyncio
    async def test_get_user_by_email_unavailable(self):
        """Test get_user_by_email returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_user_by_email("test@example.com")
            
            assert result is None


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_conversation_unavailable(self):
        """Test invalidate_conversation succeeds when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.invalidate_conversation("conv-123")
            
            # Should return True even when unavailable (no-op)
            assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_user_history_unavailable(self):
        """Test invalidate_user_history returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.invalidate_user_history(1)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_user_data_unavailable(self):
        """Test invalidate_user_data returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.invalidate_user_data(1)
            
            assert result is False


class TestStaticDataCache:
    """Tests for static data caching (models, methods)."""

    @pytest.mark.asyncio
    async def test_get_available_models_unavailable(self):
        """Test get_available_models returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_available_models()
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_available_models_unavailable(self):
        """Test set_available_models returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_available_models({
                "gemini": [{"id": "gemini-2.0-flash"}]
            })
            
            assert result is False

    @pytest.mark.asyncio
    async def test_get_sentiment_methods_unavailable(self):
        """Test get_sentiment_methods returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_sentiment_methods()
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_sentiment_methods_unavailable(self):
        """Test set_sentiment_methods returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set_sentiment_methods(
                ["nlp_api", "llm_separate", "structured"]
            )
            
            assert result is False


class TestLowLevelOperations:
    """Tests for low-level cache operations."""

    @pytest.mark.asyncio
    async def test_get_unavailable(self):
        """Test get returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get("key")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_set_unavailable(self):
        """Test set returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.set("key", "value")
            
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_unavailable(self):
        """Test delete returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.delete("key")
            
            assert result is False

    @pytest.mark.asyncio
    async def test_mget_unavailable(self):
        """Test mget returns list of Nones when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.mget(["key1", "key2", "key3"])
            
            assert result == [None, None, None]

    @pytest.mark.asyncio
    async def test_get_json_unavailable(self):
        """Test get_json returns None when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.get_json("key")
            
            assert result is None


class TestHealthCheck:
    """Tests for cache health check."""

    @pytest.mark.asyncio
    async def test_check_health_unavailable(self):
        """Test check_health returns False when cache unavailable."""
        with patch("app.services.cache.get_settings") as mock_settings:
            mock_settings.return_value.redis_available = False
            
            service = CacheService()
            result = await service.check_health()
            
            assert result is False


class TestCacheKeyPrefixes:
    """Tests for cache key prefix constants."""

    def test_key_prefixes_defined(self):
        """Test that all key prefixes are properly defined."""
        assert KEY_PREFIX_CONVERSATION == "conv"
        assert KEY_PREFIX_USER == "user"
        assert KEY_PREFIX_HISTORY == "history"
        assert KEY_PREFIX_DETAIL == "detail"
        assert KEY_PREFIX_USER_MESSAGES == "usrmsg"

    def test_ttl_constants_defined(self):
        """Test that all TTL constants are properly defined."""
        assert TTL_CONVERSATION_CONTEXT == 3600  # 1 hour
        assert TTL_USER_MESSAGES == 120  # 2 minutes (low TTL for freshness)
