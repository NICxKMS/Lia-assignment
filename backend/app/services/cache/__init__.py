"""Async Redis caching service using Upstash.

Provides a unified caching interface with optimal data structures:
- Hash (HSET/HGET): User data, conversation metadata - O(1) field access
- List (LPUSH/LRANGE): Conversation context messages - O(1) append, O(N) range
- String (SET/GET): JSON blobs for complex nested data
- Sorted Set (ZADD/ZRANGE): Conversation history by timestamp - O(log N) insert

Features:
- Write-through caching with parallel DB+Cache writes
- Cache-aside pattern for reads
- TTL management per data type
- Graceful degradation when cache is unavailable
- Batch operations for improved latency
"""

from app.core.config import get_settings
from app.services.cache.constants import (
    KEY_PREFIX_CONVERSATION,
    KEY_PREFIX_DETAIL,
    KEY_PREFIX_EMAIL_INDEX,
    KEY_PREFIX_HISTORY,
    KEY_PREFIX_MESSAGE,
    KEY_PREFIX_MODELS,
    KEY_PREFIX_RATE,
    KEY_PREFIX_SENTIMENT,
    KEY_PREFIX_USER,
    KEY_PREFIX_USER_MESSAGES,
    TTL_AVAILABLE_MODELS,
    TTL_CONVERSATION_CONTEXT,
    TTL_CONVERSATION_DETAIL,
    TTL_CONVERSATION_METADATA,
    TTL_MESSAGE,
    TTL_RATE_LIMIT,
    TTL_SENTIMENT_METHODS,
    TTL_USER_CONVERSATIONS,
    TTL_USER_DATA,
    TTL_USER_MESSAGES,
)
from app.services.cache.service import CacheService, get_cache_service

__all__ = [
    # TTL constants
    "TTL_CONVERSATION_CONTEXT",
    "TTL_USER_CONVERSATIONS",
    "TTL_CONVERSATION_DETAIL",
    "TTL_CONVERSATION_METADATA",
    "TTL_AVAILABLE_MODELS",
    "TTL_RATE_LIMIT",
    "TTL_USER_DATA",
    "TTL_SENTIMENT_METHODS",
    "TTL_MESSAGE",
    "TTL_USER_MESSAGES",
    # Key prefix constants
    "KEY_PREFIX_CONVERSATION",
    "KEY_PREFIX_USER",
    "KEY_PREFIX_RATE",
    "KEY_PREFIX_MODELS",
    "KEY_PREFIX_HISTORY",
    "KEY_PREFIX_DETAIL",
    "KEY_PREFIX_SENTIMENT",
    "KEY_PREFIX_MESSAGE",
    "KEY_PREFIX_EMAIL_INDEX",
    "KEY_PREFIX_USER_MESSAGES",
    # Service
    "CacheService",
    "get_cache_service",
    "get_settings",
]
