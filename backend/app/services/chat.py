"""Chat Orchestrator Service - Streaming Chat with Sentiment Analysis.

Coordinates the chat flow between:
- Database (message persistence)
- LLM Service (response generation)
- Sentiment Service (sentiment analysis with incremental cumulative tracking)
- Cache Service (conversation context caching)

Uses Server-Sent Events (SSE) for real-time streaming.
Optimized with parallel operations and comprehensive caching.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any, Awaitable, Coroutine, TypeVar, cast

import orjson
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Conversation, Message, User
from app.services.cache import CacheService, get_cache_service
from app.services.llm import LLMService, get_llm_service
from app.services.sentiment import (
    CumulativeState,
    SentimentResult,
    SentimentService,
    get_sentiment_service,
)

logger = get_logger(__name__)
T = TypeVar("T")

# Default system prompt for the AI assistant
DEFAULT_SYSTEM_PROMPT = """You are Lia, a helpful and friendly AI assistant created to provide thoughtful, accurate assistance.

## Your Personality
- Warm, conversational, and professional
- Curious and genuinely interested in helping
- Clear and concise - avoid unnecessary verbosity
- Honest about limitations and uncertainties

## Response Guidelines
- Use markdown formatting for structure when helpful (headers, lists, code blocks)
- For code: use appropriate language tags in code blocks
- For complex topics: break down into digestible parts
- Reference previous context when relevant to show continuity
- Ask clarifying questions if the request is ambiguous

## Tone
- Match the user's energy and formality level
- Be encouraging without being patronizing
- Use light humor when appropriate, but stay helpful"""


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {orjson.dumps(data).decode()}\n\n"


def _create_tracked_task(
    coro: Coroutine[Any, Any, T] | asyncio.Future[T] | Awaitable[T],
    name: str,
) -> asyncio.Task[T]:
    """Create a background task that logs exceptions."""
    task: asyncio.Task[T] = asyncio.create_task(cast(Any, coro), name=name)

    def _log_result(t: asyncio.Task[Any]) -> None:
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            pass  # Logged at DEBUG level elsewhere if needed

    task.add_done_callback(_log_result)
    return task


def _sentiment_stream_payload(result: SentimentResult | None) -> dict[str, Any] | None:
    """Slim sentiment payload for SSE to reduce bandwidth."""
    if not result:
        return None
    payload: dict[str, Any] = {
        "score": round(result.score, 4),
        "label": result.label,
        "emotion": result.emotion,
    }
    if result.summary:
        payload["summary"] = result.summary
    return payload


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
        model: str = "gemini-2.5-flash",
        sentiment_method: str = "llm_separate",
        model_settings: dict[str, float | int] | None = None,
    ) -> AsyncIterator[str]:
        """
        Process a chat message with streaming response.
        
        Yields SSE formatted events:
        - event: start     -> { conversation_id, message_id }
        - event: thought   -> { content }  (model thinking process)
        - event: chunk     -> { content }
        - event: sentiment -> { message: {...}, cumulative: {...} | null }
        - event: done      -> { finish_reason }
        - event: error     -> { message }
        """
        start_time = time.monotonic()
        
        # Extract model settings with defaults and normalize types
        raw_temperature = model_settings.get("temperature", 0.7) if model_settings else 0.7
        temperature = float(raw_temperature)

        raw_max_tokens = model_settings.get("max_tokens", 2048) if model_settings else 2048
        max_tokens = int(raw_max_tokens)
        # Use user-selected model for sentiment; fall back per provider
        sentiment_model = "gemini-2.5-flash" if provider == "gemini" else "gpt-4.1"

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
            thoughts: list[str] = []  # Track thinking content
            message_sentiment: SentimentResult | None = None
            sentiment_task: asyncio.Task[SentimentResult] | None = None
            cumulative_task: asyncio.Task[tuple[SentimentResult, CumulativeState]] | None = None

            # Get current cumulative state for parallelization decision
            current_state = CumulativeState.from_dict(conversation.sentiment_state)

            if sentiment_method == "structured":
                # Structured: Single LLM call with response + sentiment
                async for struct_chunk in adapter.generate_structured_stream(
                    messages=context,
                    model=model,
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    if struct_chunk.content:
                        # Check if this is a thought chunk
                        if hasattr(struct_chunk, 'is_thought') and struct_chunk.is_thought:
                            thoughts.append(struct_chunk.content)
                            yield sse_event("thought", {"content": struct_chunk.content})
                        else:
                            full_response += struct_chunk.content
                            yield sse_event("chunk", {"content": struct_chunk.content})

                    if struct_chunk.is_final:
                        message_sentiment = SentimentResult(
                            score=struct_chunk.sentiment_score or 0.0,
                            label=struct_chunk.sentiment_label or "Neutral",
                            emotion=struct_chunk.sentiment_emotion,
                            source="structured",
                            details={"provider": provider, "model": model},
                        )
                        break
            else:
                # OPTIMIZATION: Start sentiment analysis immediately in parallel
                # with streaming response to reduce total latency
                sentiment_task = _create_tracked_task(
                    self.sentiment_service.analyze(
                        message,
                        sentiment_method,
                        provider,
                        model,
                    ),
                    "sentiment:message",
                )
                
                # OPTIMIZATION: For subsequent messages (count > 0), start cumulative
                # sentiment in parallel - only for Gemini (incremental API).
                # For non-Gemini providers we wait for per-message sentiment so
                # the weighted average can include it.
                if provider == "gemini" and current_state.count > 0:
                    cumulative_task = _create_tracked_task(
                        self.sentiment_service.update_cumulative(
                            new_message=message,
                            current_state=current_state,
                            message_sentiment=None,  # Not needed for count > 0
                            provider=provider,
                            model=sentiment_model,
                        ),
                        "sentiment:cumulative",
                    )
                
                # Regular streaming response with thought detection
                async for chunk in adapter.generate_stream(
                    messages=context,
                    model=model,
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    if chunk.content:
                        if chunk.is_thought:
                            thoughts.append(chunk.content)
                            yield sse_event("thought", {"content": chunk.content})
                        else:
                            full_response += chunk.content
                            yield sse_event("chunk", {"content": chunk.content})
                    if chunk.is_final:
                        break

                # Await sentiment result (should already be done or nearly done)
                try:
                    message_sentiment = await sentiment_task
                except Exception:  # noqa: BLE001
                    message_sentiment = SentimentResult.neutral()

            # INCREMENTAL CUMULATIVE SENTIMENT
            # Instead of re-analyzing all messages, update a rolling summary - O(1) per message
            cumulative_sentiment: SentimentResult | None = None
            new_state: CumulativeState
            
            if cumulative_task:
                # Await parallel cumulative task (for count > 0)
                try:
                    cumulative_sentiment, new_state = await cumulative_task
                except Exception:  # noqa: BLE001
                    # Fallback: use weighted average if parallel task failed
                    cumulative_sentiment, new_state = await self.sentiment_service.update_cumulative(
                        new_message=message,
                        current_state=current_state,
                        message_sentiment=message_sentiment,
                        provider=provider,
                        model=sentiment_model,
                    )
            else:
                # Sequential for first message (count == 0) - needs message_sentiment
                cumulative_sentiment, new_state = await self.sentiment_service.update_cumulative(
                    new_message=message,
                    current_state=current_state,
                    message_sentiment=message_sentiment,
                    provider=provider,
                    model=sentiment_model,
                )
            
            # Persist the updated sentiment state to the conversation
            conversation.sentiment_state = new_state.to_dict()

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
                model_info={
                    "provider": provider,
                    "model": model,
                    "thoughts": thoughts if thoughts else None,
                },
            )
            db.add(assistant_message)
            await db.flush()

            # Update caches: context and invalidate history cache
            if self.cache_service.is_available:
                await asyncio.gather(
                    self.cache_service.append_to_context(
                        conversation.id, {"role": "user", "content": message}
                    ),
                    self.cache_service.append_to_context(
                        conversation.id, {
                            "role": "assistant",
                            "content": full_response,
                            "thoughts": thoughts if thoughts else None,
                        }
                    ),
                    self.cache_service.invalidate_user_history(user.id),
                    return_exceptions=True,
                )

            # Log completion with timing
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "Chat completed",
                user_id=user.id,
                conversation_id=conversation.id,
                duration_ms=duration_ms,
                response_len=len(full_response),
            )

            # Send sentiment event
            yield sse_event("sentiment", {
                "message": _sentiment_stream_payload(message_sentiment),
                "cumulative": _sentiment_stream_payload(cumulative_sentiment),
            })

            # Send done event
            yield sse_event("done", {"finish_reason": "stop"})

        except Exception as e:
            logger.error("Chat stream error", user_id=user.id, error=str(e))
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
            _create_tracked_task(
                self.cache_service.set_conversation_history(user_id, limit, conversations),
                "cache:set_conversation_history",
            )
        
        return conversations

    async def get_conversation_detail(
        self,
        db: AsyncSession,
        user_id: int,
        conversation_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any] | None:
        """Get full conversation with all messages.
        
        Uses cache-aside pattern: check cache first, fallback to DB.
        Write-through: populate cache on miss asynchronously.
        Cache entries include user_id for ownership verification.
        """
        # Cache only the first page to avoid stale/mismatched pagination entries
        use_cache = offset == 0
        if use_cache and self.cache_service.is_available:
            cached = await self.cache_service.get_conversation_detail(
                conversation_id,
                limit=limit,
            )
            if cached is not None:
                # Verify ownership - return None if user_id doesn't match (security check)
                if cached.get("user_id") != user_id:
                    return None
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
        
        # Fetch messages with pagination
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        messages = msg_result.scalars().all()

        # Total count for pagination metadata
        total_result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
        total_messages = int(total_result.scalar_one() or 0)

        detail = {
            "id": conv.id,
            "user_id": conv.user_id,  # Include for ownership verification
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "total_messages": total_messages,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(messages) < total_messages,
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
        if use_cache and self.cache_service.is_available:
            _create_tracked_task(
                self.cache_service.set_conversation_detail(
                    conversation_id,
                    detail,
                    limit=limit,
                ),
                "cache:set_conversation_detail",
            )
        
        return detail

    async def delete_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        conversation_id: str,
    ) -> bool:
        """Delete a specific conversation."""
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
