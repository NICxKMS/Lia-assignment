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

import asyncio
import json
import time
from typing import Any, TypeVar, Callable, Coroutine

from upstash_redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Cache TTL constants (in seconds)
TTL_CONVERSATION_CONTEXT = 3600  # 1 hour - frequently accessed during chat
TTL_USER_CONVERSATIONS = 300  # 5 minutes - list updates frequently
TTL_CONVERSATION_DETAIL = 600  # 10 minutes - detailed view less frequent
TTL_CONVERSATION_METADATA = 1800  # 30 minutes - basic info
TTL_AVAILABLE_MODELS = 86400  # 24 hours - static data
TTL_RATE_LIMIT = 60  # 1 minute
TTL_USER_DATA = 900  # 15 minutes - auth data
TTL_SENTIMENT_METHODS = 86400  # 24 hours - static data
TTL_MESSAGE = 3600  # 1 hour - individual messages
TTL_USER_MESSAGES = 120  # 2 minutes - short TTL for cumulative sentiment (low ttl as requested)

# Cache key prefixes - using Redis naming conventions
KEY_PREFIX_CONVERSATION = "conv"  # conv:{id}:context, conv:{id}:meta
KEY_PREFIX_USER = "user"  # user:{id}:data, user:{id}:email:{email}
KEY_PREFIX_RATE = "rate"  # rate:{type}:{id}
KEY_PREFIX_MODELS = "models"  # models:all
KEY_PREFIX_HISTORY = "history"  # history:{user_id} (sorted set)
KEY_PREFIX_DETAIL = "detail"  # detail:{conv_id}
KEY_PREFIX_SENTIMENT = "sentiment"  # sentiment:methods
KEY_PREFIX_MESSAGE = "msg"  # msg:{conv_id}:{msg_id}
KEY_PREFIX_EMAIL_INDEX = "email"  # email:{email} -> user_id (for login lookup)
KEY_PREFIX_USER_MESSAGES = "usrmsg"  # usrmsg:{conv_id} -> list of user message contents


class CacheService:
    """Async Redis caching service with graceful degradation."""

    def __init__(self) -> None:
        """Initialize the cache service."""
        settings = get_settings()
        self._client: Redis | None = None
        
        if settings.redis_available:
            try:
                self._client = Redis(
                    url=settings.upstash_redis_rest_url,
                    token=settings.upstash_redis_rest_token,
                )
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning("Failed to initialize Redis cache", error=str(e))
                self._client = None
        else:
            logger.info("Redis cache not configured, caching disabled")

    @property
    def is_available(self) -> bool:
        """Check if cache is available."""
        return self._client is not None

    def _make_key(self, prefix: str, *parts: str | int) -> str:
        """Create a cache key from prefix and parts."""
        return f"{prefix}:{':'.join(str(p) for p in parts)}"

    # ========== Low-level operations ==========

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        if not self.is_available:
            return None
        
        try:
            result = await self._client.get(key)  # type: ignore
            return result if isinstance(result, str) else None
        except Exception as e:
            logger.debug("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in cache with optional TTL."""
        if not self.is_available:
            return False
        
        try:
            if ttl:
                await self._client.set(key, value, ex=ttl)  # type: ignore
            else:
                await self._client.set(key, value)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if not self.is_available:
            return False
        
        try:
            await self._client.delete(key)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache delete failed", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.
        
        Note: Upstash REST API doesn't support SCAN, so this is limited.
        For production, consider using specific key deletion.
        """
        if not self.is_available:
            return 0
        
        try:
            # Upstash supports KEYS command but use cautiously
            keys = await self._client.keys(pattern)  # type: ignore
            if keys:
                await self._client.delete(*keys)  # type: ignore
                return len(keys)
            return 0
        except Exception as e:
            logger.debug("Cache delete pattern failed", pattern=pattern, error=str(e))
            return 0

    # ========== High-level operations ==========

    async def get_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        """Get and deserialize JSON from cache."""
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                logger.debug("Cache JSON decode failed", key=key)
        return None

    async def set_json(
        self,
        key: str,
        value: dict[str, Any] | list[Any],
        ttl: int | None = None,
    ) -> bool:
        """Serialize and store JSON in cache."""
        return await self.set(key, json.dumps(value), ttl)

    # ========== Write-through helper ==========

    async def write_through(
        self,
        db_operation: Coroutine[Any, Any, T],
        cache_operation: Coroutine[Any, Any, bool],
    ) -> T:
        """Execute DB and cache writes in parallel for write-through caching.
        
        DB operation result is returned; cache failures are logged but don't fail the request.
        """
        db_result, cache_result = await asyncio.gather(
            db_operation,
            cache_operation,
            return_exceptions=True,
        )
        
        # Log cache failures but don't propagate
        if isinstance(cache_result, Exception):
            logger.debug("Write-through cache operation failed", error=str(cache_result))
        
        # Re-raise DB exceptions
        if isinstance(db_result, Exception):
            raise db_result
        
        return db_result

    # ========== Hash operations for structured data ==========

    async def hget(self, key: str, field: str) -> str | None:
        """Get a field from a hash."""
        if not self.is_available:
            return None
        try:
            result = await self._client.hget(key, field)  # type: ignore
            return result if isinstance(result, str) else None
        except Exception as e:
            logger.debug("Cache hget failed", key=key, field=field, error=str(e))
            return None

    async def hset(self, key: str, mapping: dict[str, str], ttl: int | None = None) -> bool:
        """Set multiple fields in a hash."""
        if not self.is_available or not mapping:
            return False
        try:
            # Upstash Redis client expects values= keyword argument for multiple fields
            await self._client.hset(key, values=mapping)  # type: ignore
            if ttl:
                await self._client.expire(key, ttl)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache hset failed", key=key, error=str(e))
            return False

    async def hgetall(self, key: str) -> dict[str, str] | None:
        """Get all fields from a hash."""
        if not self.is_available:
            return None
        try:
            result = await self._client.hgetall(key)  # type: ignore
            return result if result else None
        except Exception as e:
            logger.debug("Cache hgetall failed", key=key, error=str(e))
            return None

    # ========== List operations for ordered data ==========

    async def lpush(self, key: str, *values: str) -> bool:
        """Push values to the head of a list."""
        if not self.is_available or not values:
            return False
        try:
            await self._client.lpush(key, *values)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache lpush failed", key=key, error=str(e))
            return False

    async def rpush(self, key: str, *values: str, ttl: int | None = None) -> bool:
        """Push values to the tail of a list (maintains chronological order)."""
        if not self.is_available or not values:
            return False
        try:
            await self._client.rpush(key, *values)  # type: ignore
            if ttl:
                await self._client.expire(key, ttl)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache rpush failed", key=key, error=str(e))
            return False

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        """Get a range of elements from a list."""
        if not self.is_available:
            return []
        try:
            result = await self._client.lrange(key, start, stop)  # type: ignore
            return result if result else []
        except Exception as e:
            logger.debug("Cache lrange failed", key=key, error=str(e))
            return []

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        """Trim a list to the specified range."""
        if not self.is_available:
            return False
        try:
            await self._client.ltrim(key, start, stop)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache ltrim failed", key=key, error=str(e))
            return False

    # ========== Sorted Set operations for ranked/timed data ==========

    async def zadd(self, key: str, mapping: dict[str, float], ttl: int | None = None) -> bool:
        """Add members to a sorted set with scores."""
        if not self.is_available or not mapping:
            return False
        try:
            # Convert to format expected by zadd: {member: score}
            await self._client.zadd(key, mapping)  # type: ignore
            if ttl:
                await self._client.expire(key, ttl)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache zadd failed", key=key, error=str(e))
            return False

    async def zrange(
        self, 
        key: str, 
        start: int, 
        stop: int, 
        desc: bool = False,
        with_scores: bool = False,
    ) -> list[str] | list[tuple[str, float]]:
        """Get a range of members from a sorted set."""
        if not self.is_available:
            return []
        try:
            if desc:
                result = await self._client.zrange(key, start, stop, rev=True, withscores=with_scores)  # type: ignore
            else:
                result = await self._client.zrange(key, start, stop, withscores=with_scores)  # type: ignore
            return result if result else []
        except Exception as e:
            logger.debug("Cache zrange failed", key=key, error=str(e))
            return []

    async def zrem(self, key: str, *members: str) -> bool:
        """Remove members from a sorted set."""
        if not self.is_available or not members:
            return False
        try:
            await self._client.zrem(key, *members)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache zrem failed", key=key, error=str(e))
            return False

    # ========== Batch operations for reduced latency ==========

    async def mget(self, keys: list[str]) -> list[str | None]:
        """Get multiple values from cache in a single request."""
        if not self.is_available or not keys:
            return [None] * len(keys)
        
        try:
            results = await self._client.mget(*keys)  # type: ignore
            return [r if isinstance(r, str) else None for r in results]
        except Exception as e:
            logger.debug("Cache mget failed", error=str(e))
            return [None] * len(keys)

    async def mset(self, mapping: dict[str, str], ttl: int | None = None) -> bool:
        """Set multiple values in cache. Note: TTL applied per-key via pipeline."""
        if not self.is_available or not mapping:
            return False
        
        try:
            if ttl:
                async with self._client.pipeline() as pipe:  # type: ignore
                    for key, value in mapping.items():
                        pipe.set(key, value, ex=ttl)
                    await pipe.execute()
            else:
                await self._client.mset(mapping)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache mset failed", error=str(e))
            return False

    # ========== Conversation context caching (using List for O(1) append) ==========

    async def get_conversation_context(
        self,
        conversation_id: str,
        max_messages: int = 10,
    ) -> list[dict[str, str]] | None:
        """Get cached conversation context using List (LRANGE for last N)."""
        key = self._make_key(KEY_PREFIX_CONVERSATION, conversation_id, "context")
        
        # Get last N messages (negative indices from end)
        raw_messages = await self.lrange(key, -max_messages, -1)
        if not raw_messages:
            return None
        
        try:
            return [json.loads(msg) for msg in raw_messages]
        except json.JSONDecodeError:
            logger.debug("Cache context decode failed", conversation_id=conversation_id)
            return None

    async def set_conversation_context(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
    ) -> bool:
        """Cache conversation context (replace entire list)."""
        key = self._make_key(KEY_PREFIX_CONVERSATION, conversation_id, "context")
        
        if not self.is_available:
            return False
        
        try:
            async with self._client.pipeline() as pipe:  # type: ignore
                pipe.delete(key)
                if messages:
                    serialized = [json.dumps(msg) for msg in messages]
                    pipe.rpush(key, *serialized)
                    pipe.expire(key, TTL_CONVERSATION_CONTEXT)
                await pipe.execute()
            return True
        except Exception as e:
            logger.debug("Cache set context failed", error=str(e))
            return False

    async def append_to_context(
        self,
        conversation_id: str,
        message: dict[str, str | list[str] | None],
        max_messages: int = 50,
    ) -> bool:
        """Append a single message to context (efficient O(1) operation)."""
        key = self._make_key(KEY_PREFIX_CONVERSATION, conversation_id, "context")
        
        if not self.is_available:
            return False
        
        try:
            serialized = json.dumps(message)
            async with self._client.pipeline() as pipe:  # type: ignore
                pipe.rpush(key, serialized)
            # Trim to keep only last N messages
                pipe.ltrim(key, -max_messages, -1)
                pipe.expire(key, TTL_CONVERSATION_CONTEXT)
                await pipe.execute()
            return True
        except Exception as e:
            logger.debug("Cache append context failed", error=str(e))
            return False

    async def invalidate_conversation(self, conversation_id: str) -> bool:
        """Invalidate all cache entries for a conversation."""
        # Invalidate context, detail, and user messages cache
        context_key = self._make_key(KEY_PREFIX_CONVERSATION, conversation_id, "context")
        detail_key = self._make_key(KEY_PREFIX_DETAIL, conversation_id)
        user_msg_key = self._make_key(KEY_PREFIX_USER_MESSAGES, conversation_id)
        
        try:
            if self.is_available:
                await self._client.delete(context_key, detail_key, user_msg_key)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache invalidate conversation failed", error=str(e))
            return False

    # ========== User messages caching (for cumulative sentiment) ==========

    async def get_user_messages(
        self,
        conversation_id: str,
    ) -> list[str] | None:
        """Get cached user messages for cumulative sentiment analysis.
        
        Returns list of user message contents or None if not cached.
        Uses short TTL to ensure relatively fresh data.
        """
        key = self._make_key(KEY_PREFIX_USER_MESSAGES, conversation_id)
        
        # Get all messages from list
        raw_messages = await self.lrange(key, 0, -1)
        if not raw_messages:
            return None
        
        return raw_messages

    async def set_user_messages(
        self,
        conversation_id: str,
        messages: list[str],
    ) -> bool:
        """Cache user messages for cumulative sentiment analysis.
        
        Uses short TTL (2 minutes) for fresh cumulative sentiment data.
        """
        key = self._make_key(KEY_PREFIX_USER_MESSAGES, conversation_id)
        
        if not self.is_available or not messages:
            return False
        
        try:
            async with self._client.pipeline() as pipe:  # type: ignore
                pipe.delete(key)
                pipe.rpush(key, *messages)
                pipe.expire(key, TTL_USER_MESSAGES)
                await pipe.execute()
            return True
        except Exception as e:
            logger.debug("Cache set user messages failed", error=str(e))
            return False

    async def append_user_message(
        self,
        conversation_id: str,
        message: str,
    ) -> bool:
        """Append a single user message to the cache (O(1) operation).
        
        Efficiently adds to existing cache without full replacement.
        """
        key = self._make_key(KEY_PREFIX_USER_MESSAGES, conversation_id)
        
        if not self.is_available:
            return False
        
        try:
            async with self._client.pipeline() as pipe:  # type: ignore
                pipe.rpush(key, message)
                pipe.expire(key, TTL_USER_MESSAGES)
                await pipe.execute()
            return True
        except Exception as e:
            logger.debug("Cache append user message failed", error=str(e))
            return False

    # ========== Conversation history caching (using Sorted Set by updated_at) ==========

    async def get_conversation_history(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]] | None:
        """Get cached conversation history using Sorted Set (most recent first)."""
        key = self._make_key(KEY_PREFIX_HISTORY, user_id)
        
        # Get top N by score (descending = most recent)
        raw_items = await self.zrange(key, 0, limit - 1, desc=True)
        if not raw_items:
            return None
        
        try:
            return [json.loads(item) for item in raw_items]
        except json.JSONDecodeError:
            logger.debug("Cache history decode failed", user_id=user_id)
            return None

    async def set_conversation_history(
        self,
        user_id: int,
        limit: int,
        conversations: list[dict[str, Any]],
    ) -> bool:
        """Cache conversation history using Sorted Set (scored by timestamp)."""
        key = self._make_key(KEY_PREFIX_HISTORY, user_id)
        
        if not self.is_available:
            return False
        
        try:
            # Clear existing and add new
            await self._client.delete(key)  # type: ignore
            if conversations:
                # Use updated_at timestamp as score for ordering
                mapping = {}
                for conv in conversations:
                    # Parse ISO timestamp to unix timestamp for score
                    try:
                        from datetime import datetime
                        ts = datetime.fromisoformat(conv["updated_at"].replace("Z", "+00:00")).timestamp()
                    except (KeyError, ValueError):
                        ts = time.time()
                    mapping[json.dumps(conv)] = ts
                
                await self._client.zadd(key, mapping)  # type: ignore
                await self._client.expire(key, TTL_USER_CONVERSATIONS)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache set history failed", error=str(e))
            return False

    async def add_to_history(
        self,
        user_id: int,
        conversation: dict[str, Any],
    ) -> bool:
        """Add/update a single conversation in history (efficient O(log N))."""
        key = self._make_key(KEY_PREFIX_HISTORY, user_id)
        
        if not self.is_available:
            return False
        
        try:
            from datetime import datetime
            try:
                ts = datetime.fromisoformat(conversation["updated_at"].replace("Z", "+00:00")).timestamp()
            except (KeyError, ValueError):
                ts = time.time()
            
            await self._client.zadd(key, {json.dumps(conversation): ts})  # type: ignore
            await self._client.expire(key, TTL_USER_CONVERSATIONS)  # type: ignore
            return True
        except Exception as e:
            logger.debug("Cache add to history failed", error=str(e))
            return False

    async def remove_from_history(
        self,
        user_id: int,
        conversation_id: str,
    ) -> bool:
        """Remove a conversation from history by finding and removing the member."""
        key = self._make_key(KEY_PREFIX_HISTORY, user_id)
        
        if not self.is_available:
            return False
        
        try:
            # Get all items and find the one with matching ID
            items = await self.zrange(key, 0, -1)
            for item in items:
                try:
                    conv = json.loads(item)
                    if conv.get("id") == conversation_id:
                        await self._client.zrem(key, item)  # type: ignore
                        return True
                except json.JSONDecodeError:
                    continue
            return False
        except Exception as e:
            logger.debug("Cache remove from history failed", error=str(e))
            return False

    async def invalidate_user_history(self, user_id: int) -> bool:
        """Invalidate user's conversation history cache."""
        key = self._make_key(KEY_PREFIX_HISTORY, user_id)
        return await self.delete(key)

    # ========== Conversation detail caching ==========

    async def get_conversation_detail(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
    ) -> dict[str, Any] | None:
        """Get cached conversation detail."""
        key = self._make_key(KEY_PREFIX_DETAIL, conversation_id, f"limit:{limit}")
        data = await self.get_json(key)
        return data if isinstance(data, dict) else None

    async def set_conversation_detail(
        self,
        conversation_id: str,
        detail: dict[str, Any],
        *,
        limit: int = 50,
    ) -> bool:
        """Cache conversation detail."""
        key = self._make_key(KEY_PREFIX_DETAIL, conversation_id, f"limit:{limit}")
        return await self.set_json(key, detail, TTL_CONVERSATION_DETAIL)

    # ========== User cache operations (using Hash for field access) ==========

    async def get_user_data(self, user_id: int) -> dict[str, Any] | None:
        """Get cached user data using Hash (efficient field access)."""
        key = self._make_key(KEY_PREFIX_USER, user_id, "data")
        data = await self.hgetall(key)
        
        if not data:
            return None
        
        # Convert string values back to proper types
        return {
            "id": int(data["id"]) if "id" in data else None,
            "email": data.get("email"),
            "username": data.get("username"),
            "created_at": data.get("created_at"),
        }

    async def set_user_data(
        self,
        user_id: int,
        user_data: dict[str, Any],
    ) -> bool:
        """Cache user data using Hash."""
        key = self._make_key(KEY_PREFIX_USER, user_id, "data")
        
        # Convert all values to strings for Redis hash
        mapping = {
            "id": str(user_data["id"]),
            "email": user_data["email"],
            "username": user_data["username"],
            "created_at": user_data.get("created_at", ""),
        }
        
        success = await self.hset(key, mapping, TTL_USER_DATA)
        
        # Also set email index for fast login lookup
        if success:
            email_key = self._make_key(KEY_PREFIX_EMAIL_INDEX, user_data["email"])
            await self.set(email_key, str(user_id), TTL_USER_DATA)
        
        return success

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user data by email using index lookup."""
        # Look up user_id from email index
        email_key = self._make_key(KEY_PREFIX_EMAIL_INDEX, email)
        user_id_str = await self.get(email_key)
        
        if not user_id_str:
            return None
        
        try:
            user_id = int(user_id_str)
            return await self.get_user_data(user_id)
        except ValueError:
            return None

    async def invalidate_user_data(self, user_id: int, email: str | None = None) -> bool:
        """Invalidate user data cache and email index."""
        key = self._make_key(KEY_PREFIX_USER, user_id, "data")
        success = await self.delete(key)
        
        # Also delete email index if provided
        if email:
            email_key = self._make_key(KEY_PREFIX_EMAIL_INDEX, email)
            await self.delete(email_key)
        
        return success

    async def invalidate_user_conversations(self, user_id: int) -> bool:
        """Invalidate user's conversation list cache."""
        return await self.invalidate_user_history(user_id)

    # ========== LLM Models caching ==========

    async def get_available_models(self) -> dict[str, list[dict[str, Any]]] | None:
        """Get cached available LLM models."""
        key = self._make_key(KEY_PREFIX_MODELS, "all")
        data = await self.get_json(key)
        return data if isinstance(data, dict) else None

    async def set_available_models(
        self,
        models: dict[str, list[dict[str, Any]]],
    ) -> bool:
        """Cache available LLM models."""
        key = self._make_key(KEY_PREFIX_MODELS, "all")
        return await self.set_json(key, models, TTL_AVAILABLE_MODELS)

    # ========== Sentiment methods caching ==========

    async def get_sentiment_methods(self) -> list[str] | None:
        """Get cached sentiment analysis methods."""
        key = self._make_key(KEY_PREFIX_SENTIMENT, "methods")
        data = await self.get_json(key)
        return data if isinstance(data, list) else None

    async def set_sentiment_methods(self, methods: list[str]) -> bool:
        """Cache sentiment analysis methods."""
        key = self._make_key(KEY_PREFIX_SENTIMENT, "methods")
        return await self.set_json(key, methods, TTL_SENTIMENT_METHODS)

    # ========== Health check ==========

    async def check_health(self, timeout: float = 5.0) -> bool:
        """Check Redis connectivity with timeout."""
        import asyncio
        
        if not self.is_available:
            return False
        
        try:
            result = await asyncio.wait_for(
                self._client.ping(),  # type: ignore
                timeout=timeout
            )
            return bool(result)
        except asyncio.TimeoutError:
            logger.error("Redis health check timed out", timeout=timeout)
            return False
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False


from functools import lru_cache


@lru_cache
def get_cache_service() -> CacheService:
    """Get or create the cache service instance (cached)."""
    return CacheService()
