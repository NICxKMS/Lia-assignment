"""Chat Orchestrator Service - Streaming Chat with Sentiment Analysis.

Coordinates the chat flow between:
- Database (message persistence)
- LLM Service (response generation)
- Sentiment Service (sentiment analysis)
- Cache Service (conversation context caching)

Uses Server-Sent Events (SSE) for real-time streaming.
Optimized with parallel operations and comprehensive caching.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Conversation, Message, User
from app.services.cache import CacheService, get_cache_service
from app.services.llm import LLMService, StructuredStreamChunk, get_llm_service
from app.services.sentiment import SentimentResult, SentimentService, get_sentiment_service

logger = get_logger(__name__)

# Default system prompt for the AI assistant
DEFAULT_SYSTEM_PROMPT = """You are Lia, a helpful and friendly AI assistant.
You provide clear, accurate, and thoughtful responses.
Be conversational but professional. Keep responses concise unless more detail is needed."""


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


class ChatOrchestrator:
    """Orchestrates streaming chat flow between services."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        sentiment_service: SentimentService | None = None,
        cache_service: CacheService | None = None,
    ) -> None:
        self.llm_service = llm_service or get_llm_service()
        self.sentiment_service = sentiment_service or get_sentiment_service()
        self.cache_service = cache_service or get_cache_service()

    async def process_chat_stream(
        self,
        db: AsyncSession,
        user: User,
        message: str,
        conversation_id: str | None = None,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash",
        sentiment_method: str = "llm_separate",
    ) -> AsyncIterator[str]:
        """
        Process a chat message with streaming response.
        
        Yields SSE formatted events:
        - event: start     -> { conversation_id, message_id }
        - event: chunk     -> { content }
        - event: sentiment -> { message: {...}, cumulative: {...} | null }
        - event: done      -> { finish_reason }
        - event: error     -> { message }
        """
        logger.info(
            "Processing chat",
            user_id=user.id,
            provider=provider,
            model=model,
            sentiment_method=sentiment_method,
        )

        try:
            # Get or create conversation
            conversation = await self._get_or_create_conversation(
                db, user.id, conversation_id
            )

            # Load conversation context
            context = await self._load_context(db, conversation.id)

            # Auto-generate title from first message if new conversation
            if not context and not conversation.title:
                title = message[:50].strip()
                if len(message) > 50:
                    title = title.rsplit(" ", 1)[0] + "..."
                conversation.title = title

            # Save user message
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=message,
            )
            db.add(user_message)
            await db.flush()
            await db.refresh(user_message)

            # Add to context
            context.append({"role": "user", "content": message})

            # Send start event
            yield sse_event("start", {
                "conversation_id": conversation.id,
                "message_id": user_message.id,
            })

            # Get LLM adapter
            adapter = self.llm_service.get_adapter(provider)
            full_response = ""
            message_sentiment: SentimentResult | None = None
            sentiment_task: asyncio.Task[SentimentResult] | None = None
            
            # Count existing user messages from context to decide if we need cumulative sentiment
            # Context has max 10 messages, so we need DB query only for cumulative analysis
            existing_user_count = sum(1 for m in context if m.get("role") == "user")

            if sentiment_method == "structured":
                # Structured: Single LLM call with response + sentiment
                async for chunk in adapter.generate_structured_stream(
                    messages=context,
                    model=model,
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                ):
                    if chunk.content:
                        full_response += chunk.content
                        yield sse_event("chunk", {"content": chunk.content})

                    if chunk.is_final and isinstance(chunk, StructuredStreamChunk):
                        message_sentiment = SentimentResult(
                            score=chunk.sentiment_score or 0.0,
                            label=chunk.sentiment_label or "Neutral",
                            emotion=chunk.sentiment_emotion,
                            source="structured",
                            details={"provider": provider, "model": model},
                        )
                        break
            else:
                # OPTIMIZATION: Start sentiment analysis immediately in parallel
                # with streaming response to reduce total latency
                sentiment_task = asyncio.create_task(
                    self.sentiment_service.analyze(
                        message,
                        sentiment_method,
                        provider,
                        model,
                    )
                )
                
                # Regular streaming response
                async for chunk in adapter.generate_stream(
                    messages=context,
                    model=model,
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                ):
                    if chunk.content:
                        full_response += chunk.content
                        yield sse_event("chunk", {"content": chunk.content})
                    if chunk.is_final:
                        break

                # Await sentiment result (should already be done or nearly done)
                message_sentiment = await sentiment_task

            # Calculate cumulative sentiment for multiple user messages
            # OPTIMIZATION: Use cache-first for user messages (low TTL ensures freshness)
            cumulative_sentiment: SentimentResult | None = None
            
            # +1 for current message being added
            message_count = existing_user_count + 1

            should_calculate_cumulative = message_count > 1
            
            cumulative_task: asyncio.Task[SentimentResult] | None = None
            if should_calculate_cumulative:
                # Use optimized cache-first method, pass current message directly
                # This avoids refetching since current message isn't in DB yet
                all_user_messages = await self._get_user_messages(
                    db, conversation.id, include_current=message
                )
                # Limit text length to avoid token limits (e.g. 50k chars)
                combined_text = "\n".join(all_user_messages)
                if len(combined_text) > 50000:
                    combined_text = combined_text[-50000:]
                
                method = "llm_separate" if sentiment_method == "structured" else sentiment_method
                cumulative_task = asyncio.create_task(
                    self.sentiment_service.analyze(
                        combined_text, method, provider, model
                    )
                )

            # Await cumulative sentiment if task was started
            if cumulative_task:
                cumulative_sentiment = await cumulative_task

            # Update user message with sentiment data
            user_message.sentiment_data = {
                "message": message_sentiment.to_dict() if message_sentiment else None,
                "cumulative": cumulative_sentiment.to_dict() if cumulative_sentiment else None,
            }

            # Save assistant message
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response,
                model_info={"provider": provider, "model": model},
            )
            db.add(assistant_message)
            await db.flush()

            # Update caches: context, user messages, and invalidate history cache
            # Use efficient append operations instead of replacing entire context
            if self.cache_service.is_available:
                # Append both user and assistant messages efficiently
                await asyncio.gather(
                    self.cache_service.append_to_context(
                        conversation.id, {"role": "user", "content": message}
                    ),
                    self.cache_service.append_to_context(
                        conversation.id, {"role": "assistant", "content": full_response}
                    ),
                    # Update user messages cache for faster cumulative sentiment next time
                    self.cache_service.append_user_message(conversation.id, message),
                    self.cache_service.invalidate_user_history(user.id),
                    return_exceptions=True,
                )

            logger.debug(
                "Chat completed",
                conversation_id=conversation.id,
                response_length=len(full_response),
            )

            # Send sentiment event
            yield sse_event("sentiment", {
                "message": message_sentiment.to_dict() if message_sentiment else None,
                "cumulative": cumulative_sentiment.to_dict() if cumulative_sentiment else None,
            })

            # Send done event
            yield sse_event("done", {"finish_reason": "stop"})

        except Exception as e:
            logger.error("Chat stream error", error=str(e))
            yield sse_event("error", {"message": str(e)})

    async def _get_or_create_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        conversation_id: str | None,
    ) -> Conversation:
        """Get existing conversation or create a new one."""
        if conversation_id:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
            )
            if conv := result.scalar_one_or_none():
                return conv

        # Create new conversation
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)
        return conversation

    async def _load_context(
        self,
        db: AsyncSession,
        conversation_id: str,
        max_messages: int = 10,
    ) -> list[dict[str, str]]:
        """Load conversation context from cache or database."""
        # Try cache first
        if self.cache_service.is_available:
            cached = await self.cache_service.get_conversation_context(
                conversation_id, max_messages
            )
            if cached:
                return cached

        # Load from database
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]

    async def _get_user_messages(
        self,
        db: AsyncSession,
        conversation_id: str,
        include_current: str | None = None,
    ) -> list[str]:
        """Fetch all user message contents for cumulative sentiment analysis.
        
        Optimized with cache-first strategy:
        1. Check cache first (low TTL for freshness)
        2. Fall back to DB on cache miss
        3. Populate cache on miss for subsequent requests
        
        Args:
            db: Database session
            conversation_id: Conversation ID
            include_current: Current message to append (not yet in DB/cache)
        """
        # Try cache first (should be fast with low TTL)
        if self.cache_service.is_available:
            cached = await self.cache_service.get_user_messages(conversation_id)
            if cached is not None:
                # Append current message if provided
                if include_current:
                    return cached + [include_current]
                return cached
        
        # Cache miss - fetch from database (optimized: only content column)
        result = await db.execute(
            select(Message.content)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user"
            )
            .order_by(Message.created_at.asc())
        )
        messages = list(result.scalars().all())
        
        # Populate cache for next request (fire and forget)
        if self.cache_service.is_available and messages:
            asyncio.create_task(
                self.cache_service.set_user_messages(conversation_id, messages)
            )
        
        # Append current message if provided
        if include_current:
            messages.append(include_current)
        
        return messages

    async def get_conversation_history(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get user's conversation history with summaries.
        
        Uses cache-aside pattern: check cache first, fallback to DB.
        Write-through: populate cache on miss in parallel with response.
        """
        # Try cache first (Sorted Set - O(log N) range query)
        if self.cache_service.is_available:
            cached = await self.cache_service.get_conversation_history(user_id, limit)
            if cached is not None:
                logger.debug("Cache hit for conversation history", user_id=user_id)
                return cached
        
        # Cache miss - fetch from database
        result = await db.execute(
            select(
                Conversation.id,
                Conversation.title,
                Conversation.created_at,
                Conversation.updated_at,
                func.count(Message.id).label("message_count"),
            )
            .outerjoin(Message)
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        
        conversations = [
            {
                "id": row.id,
                "title": row.title,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "message_count": row.message_count,
            }
            for row in result.all()
        ]
        
        # Write-through: populate cache asynchronously (don't block response)
        if self.cache_service.is_available:
            # Fire and forget - cache population shouldn't delay response
            asyncio.create_task(
                self.cache_service.set_conversation_history(user_id, limit, conversations)
            )
        
        return conversations

    async def get_conversation_detail(
        self,
        db: AsyncSession,
        user_id: int,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        """Get full conversation with all messages.
        
        Uses cache-aside pattern: check cache first, fallback to DB.
        Write-through: populate cache on miss asynchronously.
        Cache entries include user_id for ownership verification.
        """
        # Try cache first - verify user ownership from cached data
        if self.cache_service.is_available:
            cached = await self.cache_service.get_conversation_detail(conversation_id)
            if cached is not None:
                # Verify ownership - return None if user_id doesn't match (security check)
                if cached.get("user_id") != user_id:
                    return None
                logger.debug("Cache hit for conversation detail", conversation_id=conversation_id)
                return cached
        
        # Cache miss - fetch conversation from database
        conv_result = await db.execute(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        
        conv = conv_result.scalar_one_or_none()
        if not conv:
            return None
        
        # Fetch messages separately (more reliable than selectinload with async)
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()

        detail = {
            "id": conv.id,
            "user_id": conv.user_id,  # Include for ownership verification
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "sentiment_data": m.sentiment_data,
                    "model_info": m.model_info,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }
        
        # Write-through: populate cache asynchronously
        if self.cache_service.is_available:
            asyncio.create_task(
                self.cache_service.set_conversation_detail(conversation_id, detail)
            )
        
        return detail

    async def delete_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        conversation_id: str,
    ) -> bool:
        """Delete a specific conversation."""
        logger.info(
            "Deleting conversation",
            user_id=user_id,
            conversation_id=conversation_id,
        )
        
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        
        conv = result.scalar_one_or_none()
        if not conv:
            return False

        await db.delete(conv)
        await db.flush()

        # Invalidate caches in parallel
        if self.cache_service.is_available:
            await asyncio.gather(
                self.cache_service.invalidate_conversation(conversation_id),
                self.cache_service.invalidate_user_history(user_id),
                return_exceptions=True,
            )

        return True

    async def delete_all_conversations(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """Delete all conversations for a user."""
        logger.info("Deleting all conversations", user_id=user_id)
        
        # Get conversation IDs for cache invalidation
        result = await db.execute(
            select(Conversation.id).where(Conversation.user_id == user_id)
        )
        conv_ids = [row[0] for row in result.all()]

        # Delete all conversations
        delete_result = await db.execute(
            delete(Conversation).where(Conversation.user_id == user_id)
        )

        # Batch invalidate caches - always use individual invalidation to avoid
        # deleting cache entries from other users (pattern deletion is too broad)
        if self.cache_service.is_available:
            if conv_ids:
                # Invalidate each conversation's cache entries individually
                invalidation_tasks = [
                    self.cache_service.invalidate_conversation(cid)
                    for cid in conv_ids
                ]
                invalidation_tasks.append(self.cache_service.invalidate_user_history(user_id))
                await asyncio.gather(*invalidation_tasks, return_exceptions=True)
            else:
                # No conversations to delete, just invalidate history
                await self.cache_service.invalidate_user_history(user_id)

        # Get rowcount safely
        deleted_count = getattr(delete_result, 'rowcount', None) or len(conv_ids)
        return deleted_count

    async def rename_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        conversation_id: str,
        title: str,
    ) -> bool:
        """Rename a conversation."""
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        
        conv = result.scalar_one_or_none()
        if not conv:
            return False

        conv.title = title
        await db.flush()
        
        # Invalidate caches (title appears in history and detail)
        if self.cache_service.is_available:
            await asyncio.gather(
                self.cache_service.invalidate_conversation(conversation_id),
                self.cache_service.invalidate_user_history(user_id),
                return_exceptions=True,
            )
        
        return True


# Global chat orchestrator instance
_chat_orchestrator: ChatOrchestrator | None = None


def get_chat_orchestrator() -> ChatOrchestrator:
    """Get or create the global chat orchestrator instance."""
    global _chat_orchestrator
    
    if _chat_orchestrator is None:
        _chat_orchestrator = ChatOrchestrator()
    
    return _chat_orchestrator
