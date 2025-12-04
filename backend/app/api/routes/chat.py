"""Chat API endpoints with streaming support."""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBSession, check_chat_rate_limit
from app.api.schemas import (
    ChatRequest,
    ConversationDetail,
    ConversationRename,
    ConversationSummary,
    DeleteResponse,
    SuccessResponse,
)
from app.core.logging import get_logger
from app.services.chat import ChatOrchestrator, get_chat_orchestrator
from app.services.rate_limit import RateLimitService, get_rate_limit_service

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/stream",
    summary="Send message and receive streaming response",
    responses={
        200: {
            "description": "Server-Sent Events stream",
            "content": {"text/event-stream": {}},
        },
        429: {"description": "Rate limit exceeded"},
    },
)
async def send_message_stream(
    request: ChatRequest,
    current_user: CurrentUser,
    db: DBSession,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
    rate_limiter: Annotated[RateLimitService, Depends(get_rate_limit_service)],
):
    """
    Send a chat message and receive a streaming AI response with sentiment analysis.
    
    **SSE Event Types:**
    - `start`: Stream started with conversation_id and message_id
    - `chunk`: Content chunk from AI response
    - `sentiment`: Sentiment analysis results (message and cumulative)
    - `done`: Stream completed
    - `error`: Error occurred
    
    **Request Formats:**
    - Legacy: `{"message": "Hello"}`
    - AI SDK: `{"messages": [{"id": "1", "role": "user", "parts": [{"type": "text", "text": "Hello"}]}]}`
    """
    # Check rate limit
    await check_chat_rate_limit(current_user, rate_limiter)

    # Extract user message
    try:
        user_message = request.get_user_message()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    async def event_generator():
        try:
            async for event in orchestrator.process_chat_stream(
                db=db,
                user=current_user,
                message=user_message,
                conversation_id=request.conversation_id,
                provider=request.provider,
                model=request.model,
                sentiment_method=request.sentiment_method,
            ):
                yield event
        except Exception as e:
            logger.error("Stream error", error=str(e))
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get(
    "/history",
    response_model=list[ConversationSummary],
    summary="Get conversation history",
)
async def get_history(
    current_user: CurrentUser,
    db: DBSession,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
    limit: int = 20,
) -> list[ConversationSummary]:
    """
    Get the conversation history for the current user.
    
    Returns a list of conversation summaries sorted by most recent first.
    """
    conversations = await orchestrator.get_conversation_history(
        db, current_user.id, limit
    )
    return [ConversationSummary(**conv) for conv in conversations]


@router.get(
    "/conversation/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get conversation details",
    responses={
        404: {"description": "Conversation not found"},
    },
)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    db: DBSession,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> ConversationDetail:
    """
    Get a specific conversation with all messages.
    
    - **conversation_id**: UUID of the conversation
    """
    conversation = await orchestrator.get_conversation_detail(
        db, current_user.id, conversation_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    return ConversationDetail(**conversation)


@router.delete(
    "/conversation/{conversation_id}",
    response_model=DeleteResponse,
    summary="Delete a conversation",
    responses={
        404: {"description": "Conversation not found"},
    },
)
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    db: DBSession,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> DeleteResponse:
    """
    Delete a specific conversation and all its messages.
    
    - **conversation_id**: UUID of the conversation to delete
    """
    if not await orchestrator.delete_conversation(db, current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    return DeleteResponse(
        success=True,
        message="Conversation deleted successfully",
    )


@router.delete(
    "/conversations",
    response_model=DeleteResponse,
    summary="Delete all conversations",
)
async def delete_all_conversations(
    current_user: CurrentUser,
    db: DBSession,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> DeleteResponse:
    """Delete all conversations for the current user."""
    count = await orchestrator.delete_all_conversations(db, current_user.id)
    
    return DeleteResponse(
        success=True,
        message=f"Deleted {count} conversation(s)",
        deleted_count=count,
    )


@router.patch(
    "/conversation/{conversation_id}/rename",
    response_model=SuccessResponse,
    summary="Rename a conversation",
    responses={
        404: {"description": "Conversation not found"},
    },
)
async def rename_conversation(
    conversation_id: str,
    rename_request: ConversationRename,
    current_user: CurrentUser,
    db: DBSession,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> SuccessResponse:
    """
    Rename a conversation.
    
    - **conversation_id**: UUID of the conversation
    - **title**: New title (1-255 characters)
    """
    if not await orchestrator.rename_conversation(
        db, current_user.id, conversation_id, rename_request.title
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    
    return SuccessResponse(
        success=True,
        message="Conversation renamed successfully",
    )


@router.get(
    "/models",
    summary="Get available LLM models",
)
async def get_available_models(
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> dict:
    """Get available LLM models grouped by provider.
    
    Results are cached for 24 hours for improved latency.
    Static data - rarely changes.
    """
    cache = orchestrator.cache_service
    
    # Try cache first
    if cache.is_available:
        cached = await cache.get_available_models()
        if cached is not None:
            return cached
    
    # Fetch from service (static data)
    models = orchestrator.llm_service.get_all_models()
    
    # Cache for future requests (fire and forget for static data)
    if cache.is_available:
        asyncio.create_task(cache.set_available_models(models))
    
    return models


@router.get(
    "/methods",
    response_model=list[str],
    summary="Get sentiment analysis methods",
)
async def get_sentiment_methods(
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> list[str]:
    """Get available sentiment analysis methods.
    
    Results are cached for 24 hours for improved latency.
    Static data - rarely changes.
    """
    cache = orchestrator.cache_service
    
    # Try cache first
    if cache.is_available:
        cached = await cache.get_sentiment_methods()
        if cached is not None:
            return cached
    
    # Fetch from service (static data)
    methods = orchestrator.sentiment_service.get_available_methods()
    
    # Cache for future requests (fire and forget for static data)
    if cache.is_available:
        asyncio.create_task(cache.set_sentiment_methods(methods))
    
    return methods
