"""Main CacheService combining all cache operations."""

from app.services.cache.conversation import ConversationCacheMixin
from app.services.cache.user import StaticDataCacheMixin, UserCacheMixin


class CacheService(ConversationCacheMixin, UserCacheMixin, StaticDataCacheMixin):
    """Async Redis caching service with graceful degradation.

    Combines all cache operations through multiple inheritance:
    - BaseCacheOperations: Low-level Redis primitives
    - ConversationCacheMixin: Conversation context, history, detail caching
    - UserCacheMixin: User data and email index caching
    - StaticDataCacheMixin: Models and sentiment methods caching
    """
    pass


# Global cache service instance
_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get or create the global cache service instance."""
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()

    return _cache_service
