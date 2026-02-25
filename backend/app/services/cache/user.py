"""User and static data cache operations."""

from typing import Any

from app.services.cache.base import BaseCacheOperations
from app.services.cache.constants import (
    KEY_PREFIX_EMAIL_INDEX,
    KEY_PREFIX_MODELS,
    KEY_PREFIX_SENTIMENT,
    KEY_PREFIX_USER,
    TTL_AVAILABLE_MODELS,
    TTL_SENTIMENT_METHODS,
    TTL_USER_DATA,
)


class UserCacheMixin(BaseCacheOperations):
    """User data caching operations."""

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
            "hashed_password": data.get("hashed_password"),
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
            "hashed_password": user_data["hashed_password"],
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


class StaticDataCacheMixin(BaseCacheOperations):
    """Static data caching operations (models, methods)."""

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

    async def get_sentiment_methods(self) -> list[str] | None:
        """Get cached sentiment analysis methods."""
        key = self._make_key(KEY_PREFIX_SENTIMENT, "methods")
        data = await self.get_json(key)
        return data if isinstance(data, list) else None

    async def set_sentiment_methods(self, methods: list[str]) -> bool:
        """Cache sentiment analysis methods."""
        key = self._make_key(KEY_PREFIX_SENTIMENT, "methods")
        return await self.set_json(key, methods, TTL_SENTIMENT_METHODS)
