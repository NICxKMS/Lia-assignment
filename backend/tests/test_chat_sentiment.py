"""Comprehensive tests for chat service and sentiment analysis.

Tests cover:
- Chat orchestrator functionality
- User message caching for cumulative sentiment
- Conversation CRUD operations
- Message context loading
- Sentiment analysis integration
- Cache-first patterns
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.db.models import Conversation, Message, User
from app.services.cache import CacheService
from app.services.chat import ChatOrchestrator
from app.services.sentiment import SentimentResult


class MockStreamChunk:
    """Mock stream chunk for LLM responses."""
    
    def __init__(self, content: str, is_final: bool = False, is_thought: bool = False):
        self.content = content
        self.is_final = is_final
        self.is_thought = is_thought


async def mock_llm_stream(*args, **kwargs):
    """Generate mock LLM stream response."""
    yield MockStreamChunk("Hello, ")
    yield MockStreamChunk("I'm ")
    yield MockStreamChunk("Lia!")
    yield MockStreamChunk("", is_final=True)


class TestChatOrchestrator:
    """Tests for ChatOrchestrator class."""

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_new(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test creating a new conversation when none exists."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        conversation = await orchestrator._get_or_create_conversation(
            test_db, test_user.id, None
        )
        
        assert conversation is not None
        assert conversation.user_id == test_user.id
        assert conversation.id is not None

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_existing(
        self,
        test_db,
        test_user: User,
        test_conversation: Conversation,
        mock_cache_service,
    ):
        """Test retrieving an existing conversation."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        conversation = await orchestrator._get_or_create_conversation(
            test_db, test_user.id, test_conversation.id
        )
        
        assert conversation.id == test_conversation.id
        assert conversation.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_wrong_user(
        self,
        test_db,
        second_user: User,
        test_conversation: Conversation,
        mock_cache_service,
    ):
        """Test that getting another user's conversation creates a new one."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        # Try to get test_user's conversation as second_user
        conversation = await orchestrator._get_or_create_conversation(
            test_db, second_user.id, test_conversation.id
        )
        
        # Should create a new conversation, not return the existing one
        assert conversation.id != test_conversation.id
        assert conversation.user_id == second_user.id

    @pytest.mark.asyncio
    async def test_load_context_from_db(
        self,
        test_db,
        conversation_with_messages,
        mock_cache_service,
    ):
        """Test loading conversation context from database."""
        conversation, messages = conversation_with_messages
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        context = await orchestrator._load_context(test_db, conversation.id)
        
        assert len(context) == 4  # All messages loaded
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Hello, how are you?"

    @pytest.mark.asyncio
    async def test_load_context_from_cache(
        self,
        test_db,
        test_conversation: Conversation,
        mock_cache_service_enabled,
    ):
        """Test loading conversation context from cache."""
        cached_context = [
            {"role": "user", "content": "Cached message"},
            {"role": "assistant", "content": "Cached response"},
        ]
        mock_cache_service_enabled.get_conversation_context = AsyncMock(
            return_value=cached_context
        )
        
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service_enabled)
        
        context = await orchestrator._load_context(test_db, test_conversation.id)
        
        assert context == cached_context
        mock_cache_service_enabled.get_conversation_context.assert_called_once()


class TestIncrementalSentiment:
    """Tests for incremental cumulative sentiment calculation.
    
    The new approach uses incremental sentiment updates instead of
    re-analyzing all messages each time.
    """

    @pytest.mark.asyncio
    async def test_cumulative_sentiment_called_for_multiple_messages(
        self,
        test_db,
        conversation_with_messages,
        mock_cache_service,
        mock_sentiment_service,
    ):
        """Test that cumulative sentiment is calculated when there are multiple user messages."""
        conversation, messages = conversation_with_messages
        
        mock_llm = MagicMock()
        mock_llm.get_adapter.return_value.generate_stream = mock_llm_stream
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        # Get the user from the conversation
        result = await test_db.execute(
            select(User).where(User.id == conversation.user_id)
        )
        user = result.scalar_one()
        
        # Process a new message
        events = []
        async for event in orchestrator.process_chat_stream(
            db=test_db,
            user=user,
            message="New message",
            conversation_id=conversation.id,
        ):
            events.append(event)
        
        # With incremental sentiment, we now only call analyze once for the current message
        # Cumulative is calculated incrementally using update_cumulative
        assert mock_sentiment_service.analyze.call_count == 1

    @pytest.mark.asyncio
    async def test_cumulative_sentiment_uses_incremental_update(
        self,
        test_db,
        conversation_with_messages,
        mock_cache_service,
        mock_sentiment_service,
    ):
        """Test that cumulative sentiment uses incremental update method."""
        conversation, messages = conversation_with_messages
        
        mock_llm = MagicMock()
        mock_llm.get_adapter.return_value.generate_stream = mock_llm_stream
        
        orchestrator = ChatOrchestrator(
            llm_service=mock_llm,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service,
        )
        
        result = await test_db.execute(
            select(User).where(User.id == conversation.user_id)
        )
        user = result.scalar_one()
        
        async for _ in orchestrator.process_chat_stream(
            db=test_db,
            user=user,
            message="New message",
            conversation_id=conversation.id,
        ):
            pass
        
        # With incremental sentiment, analyze is called once for the message
        assert mock_sentiment_service.analyze.call_count == 1
        
        # And update_cumulative is called once to update the cumulative sentiment
        assert mock_sentiment_service.update_cumulative.call_count == 1
        
        # Check that update_cumulative received the new message
        update_call_args = mock_sentiment_service.update_cumulative.call_args
        assert update_call_args[1]["new_message"] == "New message"


class TestConversationHistory:
    """Tests for conversation history operations."""

    @pytest.mark.asyncio
    async def test_get_conversation_history(
        self,
        test_db,
        test_user: User,
        test_conversation: Conversation,
        mock_cache_service,
    ):
        """Test getting conversation history for a user."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        history = await orchestrator.get_conversation_history(
            test_db, test_user.id, limit=20
        )
        
        assert len(history) >= 1
        assert any(c["id"] == test_conversation.id for c in history)

    @pytest.mark.asyncio
    async def test_get_conversation_history_empty(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test getting conversation history when user has no conversations."""
        # Create a new user with no conversations
        from app.core.security import get_password_hash
        
        hashed_password = await get_password_hash("password123")
        new_user = User(
            email="empty@example.com",
            username="emptyuser",
            hashed_password=hashed_password,
        )
        test_db.add(new_user)
        await test_db.commit()
        await test_db.refresh(new_user)
        
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        history = await orchestrator.get_conversation_history(
            test_db, new_user.id, limit=20
        )
        
        assert history == []


class TestConversationDetail:
    """Tests for conversation detail operations."""

    @pytest.mark.asyncio
    async def test_get_conversation_detail(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test getting full conversation with messages."""
        # Create conversation inline to ensure proper session handling
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test Detail Conversation",
        )
        test_db.add(conversation)
        await test_db.commit()
        await test_db.refresh(conversation)
        
        # Create messages
        messages = [
            Message(conversation_id=conversation.id, role="user", content="Hello"),
            Message(conversation_id=conversation.id, role="assistant", content="Hi!"),
            Message(conversation_id=conversation.id, role="user", content="Test"),
            Message(conversation_id=conversation.id, role="assistant", content="OK"),
        ]
        test_db.add_all(messages)
        await test_db.commit()
        
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        detail = await orchestrator.get_conversation_detail(
            test_db, test_user.id, conversation.id
        )
        
        assert detail is not None
        assert detail["id"] == conversation.id
        assert len(detail["messages"]) == 4
        assert detail["total_messages"] == 4
        assert detail["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_conversation_detail_not_found(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test getting non-existent conversation returns None."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        detail = await orchestrator.get_conversation_detail(
            test_db, test_user.id, str(uuid.uuid4())
        )
        
        assert detail is None

    @pytest.mark.asyncio
    async def test_get_conversation_detail_wrong_user(
        self,
        test_db,
        second_user: User,
        test_conversation: Conversation,
        mock_cache_service,
    ):
        """Test getting another user's conversation returns None."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        detail = await orchestrator.get_conversation_detail(
            test_db, second_user.id, test_conversation.id
        )
        
        assert detail is None


class TestConversationDelete:
    """Tests for conversation deletion."""

    @pytest.mark.asyncio
    async def test_delete_conversation(
        self,
        test_db,
        test_user: User,
        test_conversation: Conversation,
        mock_cache_service,
    ):
        """Test deleting a conversation."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        result = await orchestrator.delete_conversation(
            test_db, test_user.id, test_conversation.id
        )
        
        assert result is True
        
        # Verify conversation is deleted
        detail = await orchestrator.get_conversation_detail(
            test_db, test_user.id, test_conversation.id
        )
        assert detail is None

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test deleting non-existent conversation returns False."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        result = await orchestrator.delete_conversation(
            test_db, test_user.id, str(uuid.uuid4())
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_all_conversations(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test deleting all conversations for a user."""
        # Create multiple conversations
        for i in range(3):
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id=test_user.id,
                title=f"Conversation {i}",
            )
            test_db.add(conv)
        await test_db.commit()
        
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        count = await orchestrator.delete_all_conversations(test_db, test_user.id)
        
        assert count == 3
        
        # Verify all conversations are deleted
        history = await orchestrator.get_conversation_history(
            test_db, test_user.id, limit=20
        )
        assert len(history) == 0


class TestConversationRename:
    """Tests for conversation renaming."""

    @pytest.mark.asyncio
    async def test_rename_conversation(
        self,
        test_db,
        test_user: User,
        test_conversation: Conversation,
        mock_cache_service,
    ):
        """Test renaming a conversation."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        result = await orchestrator.rename_conversation(
            test_db, test_user.id, test_conversation.id, "New Title"
        )
        
        assert result is True
        
        # Verify title is updated
        detail = await orchestrator.get_conversation_detail(
            test_db, test_user.id, test_conversation.id
        )
        assert detail["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_rename_conversation_not_found(
        self,
        test_db,
        test_user: User,
        mock_cache_service,
    ):
        """Test renaming non-existent conversation returns False."""
        orchestrator = ChatOrchestrator(cache_service=mock_cache_service)
        
        result = await orchestrator.rename_conversation(
            test_db, test_user.id, str(uuid.uuid4()), "New Title"
        )
        
        assert result is False


class TestSentimentResult:
    """Tests for SentimentResult dataclass."""

    def test_sentiment_result_to_dict(self):
        """Test SentimentResult.to_dict() method."""
        result = SentimentResult(
            score=0.75,
            label="Positive",
            source="test",
            emotion="happy",
            details={"key": "value"},
        )
        
        data = result.to_dict()
        
        assert data["score"] == 0.75
        assert data["label"] == "Positive"
        assert data["emotion"] == "happy"
        assert data["source"] == "test"
        assert data["details"] == {"key": "value"}

    def test_score_to_label_positive(self):
        """Test score to label conversion for positive."""
        assert SentimentResult.score_to_label(0.5) == "Positive"
        assert SentimentResult.score_to_label(0.11) == "Positive"
        assert SentimentResult.score_to_label(1.0) == "Positive"

    def test_score_to_label_negative(self):
        """Test score to label conversion for negative."""
        assert SentimentResult.score_to_label(-0.5) == "Negative"
        assert SentimentResult.score_to_label(-0.11) == "Negative"
        assert SentimentResult.score_to_label(-1.0) == "Negative"

    def test_score_to_label_neutral(self):
        """Test score to label conversion for neutral."""
        assert SentimentResult.score_to_label(0.0) == "Neutral"
        assert SentimentResult.score_to_label(0.1) == "Neutral"
        assert SentimentResult.score_to_label(-0.1) == "Neutral"

    def test_neutral_factory(self):
        """Test SentimentResult.neutral() factory method."""
        result = SentimentResult.neutral()
        
        assert result.score == 0.0
        assert result.label == "Neutral"
        assert result.source == "default"
