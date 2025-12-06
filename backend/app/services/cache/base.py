"""Base cache operations - low-level Redis primitives."""

import asyncio
import json
from typing import Any, Coroutine, TypeVar

from upstash_redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class BaseCacheOperations:
    """Low-level Redis operations with graceful degradation."""

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

    # ========== String operations ==========

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

    # ========== JSON operations ==========

    async def get_json(self, key: str) -> dict[str, Any] | list[Any] | None:
        """Get and deserialize JSON from cache."""
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)  # type: ignore[no-any-return]
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
        if isinstance(db_result, BaseException):
            raise db_result
        
        return db_result  # type: ignore[no-any-return]

    # ========== Hash operations ==========

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

    # ========== List operations ==========

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

    # ========== Sorted Set operations ==========

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

    # ========== Batch operations ==========

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
                async with self._client.pipeline() as pipe:  # type: ignore[union-attr]
                    for key, value in mapping.items():
                        pipe.set(key, value, ex=ttl)
                    await pipe.execute()  # type: ignore[call-arg, misc]
            else:
                await self._client.mset(mapping)  # type: ignore[union-attr]
            return True
        except Exception as e:
            logger.debug("Cache mset failed", error=str(e))
            return False

    # ========== Health check ==========

    async def check_health(self, timeout: float = 5.0) -> bool:
        """Check Redis connectivity with timeout."""
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
