"""Conversation-related cache operations."""

import json
import time
from typing import Any

from app.core.logging import get_logger
from app.services.cache.base import BaseCacheOperations
from app.services.cache.constants import (
    KEY_PREFIX_CONVERSATION,
    KEY_PREFIX_DETAIL,
    KEY_PREFIX_HISTORY,
    KEY_PREFIX_USER_MESSAGES,
    TTL_CONVERSATION_CONTEXT,
    TTL_CONVERSATION_DETAIL,
    TTL_USER_CONVERSATIONS,
    TTL_USER_MESSAGES,
)

logger = get_logger(__name__)


class ConversationCacheMixin(BaseCacheOperations):
    """Conversation caching operations."""

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
            async with self._client.pipeline() as pipe:  # type: ignore[union-attr]
                pipe.delete(key)
                if messages:
                    serialized = [json.dumps(msg) for msg in messages]
                    pipe.rpush(key, *serialized)
                    pipe.expire(key, TTL_CONVERSATION_CONTEXT)
                await pipe.execute()  # type: ignore[call-arg, misc]
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
            async with self._client.pipeline() as pipe:  # type: ignore[union-attr]
                pipe.rpush(key, serialized)
                # Trim to keep only last N messages
                pipe.ltrim(key, -max_messages, -1)
                pipe.expire(key, TTL_CONVERSATION_CONTEXT)
                await pipe.execute()  # type: ignore[call-arg, misc]
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
            async with self._client.pipeline() as pipe:  # type: ignore[union-attr]
                pipe.delete(key)
                pipe.rpush(key, *messages)
                pipe.expire(key, TTL_USER_MESSAGES)
                await pipe.execute()  # type: ignore[call-arg, misc]
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
            async with self._client.pipeline() as pipe:  # type: ignore[union-attr]
                pipe.rpush(key, message)
                pipe.expire(key, TTL_USER_MESSAGES)
                await pipe.execute()  # type: ignore[call-arg, misc]
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
            return [json.loads(str(item)) for item in raw_items]
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
                    conv = json.loads(str(item))
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

    async def invalidate_user_conversations(self, user_id: int) -> bool:
        """Invalidate user's conversation list cache."""
        return await self.invalidate_user_history(user_id)
