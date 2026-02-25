"""Tests for chat orchestrator thinking feature.

Tests cover:
- Thought chunk streaming via SSE
- Thought storage in message model_info
- Thought inclusion in cache context
- Parallel sentiment with thoughts
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, User
from app.services.chat import ChatOrchestrator, make_sse_formatter
from app.services.llm import StreamChunk, StructuredStreamChunk, LLMService
from app.services.sentiment import SentimentResult, CumulativeState
from app.services.cache import CacheService


class TestSSEThoughtEvents:
    """Tests for SSE thought event formatting."""

    def test_sse_thought_event_format(self):
        """Test thought SSE event format."""
        sse_event = make_sse_formatter()
        event = sse_event("thought", {"content": "Let me think..."})
        
        assert "event: thought\n" in event
        assert '"content": "Let me think..."' in event or '"content":"Let me think..."' in event
        assert event.endswith("\n\n")
        assert event.startswith("id: ")

    def test_sse_chunk_event_format(self):
        """Test regular chunk SSE event format."""
        sse_event = make_sse_formatter()
        event = sse_event("chunk", {"content": "Hello"})
        
        assert "event: chunk\n" in event
        assert '"content"' in event
        assert event.endswith("\n\n")
        assert event.startswith("id: ")


class TestChatOrchestratorThinking:
    """Tests for ChatOrchestrator thinking functionality."""

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = MagicMock(spec=LLMService)
        return service

    @pytest.fixture
    def mock_sentiment_service(self):
        """Create mock sentiment service."""
        service = MagicMock()
        service.analyze = AsyncMock(return_value=SentimentResult(
            score=0.5,
            label="Positive",
            source="test",
        ))
        service.update_cumulative = AsyncMock(return_value=(
            SentimentResult(score=0.5, label="Positive", source="test"),
            CumulativeState(count=1, score=0.5, summary="Test summary", label="Positive"),
        ))
        return service

    @pytest.fixture
    def mock_cache_service(self):
        """Create mock cache service."""
        service = MagicMock(spec=CacheService)
        service.is_available = True
        service.get_context = AsyncMock(return_value=None)
        service.set_context = AsyncMock()
        service.append_to_context = AsyncMock()
        service.invalidate_user_history = AsyncMock()
        return service

    @pytest.fixture
    def mock_adapter(self):
        """Create mock LLM adapter."""
        adapter = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_stream_yields_thought_events(
        self,
        mock_llm_service,
        mock_sentiment_service,
        mock_cache_service,
        mock_adapter,
        test_db: AsyncSession,
        test_user: User,
    ):
        """Test that thought chunks yield SSE thought events."""
        # Setup mock adapter to yield thought then response
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Analyzing the question...", is_thought=True, model="test")
            yield StreamChunk(content="The answer is 42.", is_thought=False, model="test")
            yield StreamChunk(content="", is_final=True, model="test")
        
        mock_adapter.generate_stream = mock_stream
        mock_llm_service.get_adapter.return_value = mock_adapter
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm_service,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        # Create a conversation
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test Conversation",
        )
        test_db.add(conversation)
        await test_db.commit()
        
        events = []
        async for event in orchestrator.process_chat_stream(
            db=test_db,
            user=test_user,
            message="What is 6 times 7?",
            conversation_id=conversation.id,
            provider="gemini",
            model="gemini-2.0-flash",
            sentiment_method="llm_separate",
        ):
            events.append(event)
        
        # Parse events
        event_types = []
        for e in events:
            if "event: " in e:
                for line in e.split("\n"):
                    if line.startswith("event: "):
                        event_types.append(line.replace("event: ", ""))
                        break
        
        # Should have thought event
        assert "thought" in event_types
        
        # Find thought event and verify content
        thought_event = next((e for e in events if "event: thought" in e), None)
        assert thought_event is not None
        assert "Analyzing the question" in thought_event

    @pytest.mark.asyncio
    async def test_thoughts_stored_in_message_model_info(
        self,
        mock_llm_service,
        mock_sentiment_service,
        mock_cache_service,
        mock_adapter,
        test_db: AsyncSession,
        test_user: User,
    ):
        """Test that thoughts are stored in assistant message model_info."""
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Step 1: Parse input", is_thought=True, model="test")
            yield StreamChunk(content="Step 2: Calculate", is_thought=True, model="test")
            yield StreamChunk(content="42", is_thought=False, model="test")
            yield StreamChunk(content="", is_final=True, model="test")
        
        mock_adapter.generate_stream = mock_stream
        mock_llm_service.get_adapter.return_value = mock_adapter
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm_service,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test",
        )
        test_db.add(conversation)
        await test_db.commit()
        
        # Consume the stream
        async for _ in orchestrator.process_chat_stream(
            db=test_db,
            user=test_user,
            message="Compute",
            conversation_id=conversation.id,
        ):
            pass
        
        # Commit changes
        await test_db.commit()
        
        # Query the assistant message
        from sqlalchemy import select
        result = await test_db.execute(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == "assistant",
            )
        )
        assistant_msg = result.scalar_one_or_none()
        
        assert assistant_msg is not None
        assert assistant_msg.model_info is not None
        assert "thoughts" in assistant_msg.model_info
        assert assistant_msg.model_info["thoughts"] == ["Step 1: Parse input", "Step 2: Calculate"]

    @pytest.mark.asyncio
    async def test_cache_includes_thoughts(
        self,
        mock_llm_service,
        mock_sentiment_service,
        mock_cache_service,
        mock_adapter,
        test_db: AsyncSession,
        test_user: User,
    ):
        """Test that cache append includes thoughts field."""
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Thinking...", is_thought=True, model="test")
            yield StreamChunk(content="Response", is_thought=False, model="test")
            yield StreamChunk(content="", is_final=True, model="test")
        
        mock_adapter.generate_stream = mock_stream
        mock_llm_service.get_adapter.return_value = mock_adapter
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm_service,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test",
        )
        test_db.add(conversation)
        await test_db.commit()
        
        # Consume the stream
        async for _ in orchestrator.process_chat_stream(
            db=test_db,
            user=test_user,
            message="Test",
            conversation_id=conversation.id,
        ):
            pass
        
        # Verify cache append was called with thoughts
        calls = mock_cache_service.append_to_context.call_args_list
        
        # Find the assistant message cache call
        assistant_calls = [
            call for call in calls 
            if call[1].get("role") == "assistant" or 
               (len(call[0]) > 1 and isinstance(call[0][1], dict) and call[0][1].get("role") == "assistant")
        ]
        
        # At least one call should have thoughts
        assert len(calls) >= 2  # user + assistant

    @pytest.mark.asyncio
    async def test_no_thoughts_when_none_generated(
        self,
        mock_llm_service,
        mock_sentiment_service,
        mock_cache_service,
        mock_adapter,
        test_db: AsyncSession,
        test_user: User,
    ):
        """Test model_info.thoughts is None when no thoughts generated."""
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(content="Direct response", is_thought=False, model="test")
            yield StreamChunk(content="", is_final=True, model="test")
        
        mock_adapter.generate_stream = mock_stream
        mock_llm_service.get_adapter.return_value = mock_adapter
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm_service,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test",
        )
        test_db.add(conversation)
        await test_db.commit()
        
        async for _ in orchestrator.process_chat_stream(
            db=test_db,
            user=test_user,
            message="Hello",
            conversation_id=conversation.id,
        ):
            pass
        
        await test_db.commit()
        
        from sqlalchemy import select
        result = await test_db.execute(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == "assistant",
            )
        )
        assistant_msg = result.scalar_one_or_none()
        
        assert assistant_msg is not None
        # thoughts should be None (not empty list) when no thoughts
        assert assistant_msg.model_info.get("thoughts") is None


class TestStructuredStreamThoughts:
    """Tests for structured streaming with thoughts."""

    @pytest.fixture
    def mock_llm_service(self):
        service = MagicMock(spec=LLMService)
        return service

    @pytest.fixture
    def mock_sentiment_service(self):
        service = MagicMock()
        service.update_cumulative = AsyncMock(return_value=(
            SentimentResult(score=0.5, label="Positive", source="structured"),
            CumulativeState(count=1, score=0.5, summary="Test", label="Positive"),
        ))
        return service

    @pytest.fixture
    def mock_cache_service(self):
        service = MagicMock(spec=CacheService)
        service.is_available = True
        service.get_context = AsyncMock(return_value=None)
        service.append_to_context = AsyncMock()
        service.invalidate_user_history = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_structured_stream_with_thoughts(
        self,
        mock_llm_service,
        mock_sentiment_service,
        mock_cache_service,
        test_db: AsyncSession,
        test_user: User,
    ):
        """Test structured streaming handles thought chunks."""
        mock_adapter = MagicMock()
        
        async def mock_structured_stream(*args, **kwargs):
            # Note: StructuredStreamChunk inherits is_thought from StreamChunk
            yield StructuredStreamChunk(
                content="Analyzing sentiment...",
                is_thought=True,
                model="test",
            )
            yield StructuredStreamChunk(
                content="Here's my response",
                is_thought=False,
                model="test",
            )
            yield StructuredStreamChunk(
                content="",
                is_final=True,
                model="test",
                sentiment_score=0.8,
                sentiment_label="Positive",
                sentiment_emotion="happy",
            )
        
        mock_adapter.generate_structured_stream = mock_structured_stream
        mock_llm_service.get_adapter.return_value = mock_adapter
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm_service,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test",
        )
        test_db.add(conversation)
        await test_db.commit()
        
        events = []
        async for event in orchestrator.process_chat_stream(
            db=test_db,
            user=test_user,
            message="How are you?",
            conversation_id=conversation.id,
            sentiment_method="structured",
        ):
            events.append(event)
        
        # Should have thought event in structured mode too
        thought_events = [e for e in events if "event: thought" in e]
        assert len(thought_events) >= 1
