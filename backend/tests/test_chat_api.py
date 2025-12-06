"""Comprehensive tests for chat API endpoints.

Tests cover:
- Chat streaming endpoint
- Conversation history endpoint
- Conversation detail endpoint
- Conversation deletion endpoints
- Conversation rename endpoint
- Models and methods endpoints
- Authorization and access control
"""

import uuid

import pytest
from httpx import AsyncClient

from app.db.models import Conversation, Message, User


class TestChatHistory:
    """Tests for conversation history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting empty conversation history."""
        response = await client.get(
            "/api/v1/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        # User should have at least the test conversation
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_history_with_conversations(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_db,
        test_user: User,
    ):
        """Test getting conversation history with existing conversations."""
        # Create a conversation for the test user
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test Conversation",
        )
        test_db.add(conversation)
        await test_db.commit()
        await test_db.refresh(conversation)
        
        response = await client.get(
            "/api/v1/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        
        # Find our test conversation
        conv = next((c for c in data if c["id"] == conversation.id), None)
        assert conv is not None
        assert conv["title"] == conversation.title
        assert "created_at" in conv
        assert "updated_at" in conv

    @pytest.mark.asyncio
    async def test_get_history_unauthorized(self, client: AsyncClient):
        """Test getting history without auth fails."""
        response = await client.get("/api/v1/chat/history")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_history_with_limit(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_db,
        test_user: User,
    ):
        """Test getting history with limit parameter."""
        # Create multiple conversations
        for i in range(5):
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id=test_user.id,
                title=f"Conversation {i}",
            )
            test_db.add(conv)
        await test_db.commit()
        
        response = await client.get(
            "/api/v1/chat/history?limit=3",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3


class TestConversationDetail:
    """Tests for conversation detail endpoint."""

    @pytest.mark.asyncio
    async def test_get_conversation_detail(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_db,
        test_user: User,
    ):
        """Test getting full conversation with messages."""
        from app.db.models import Message as MessageModel
        
        # Create conversation with messages
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            title="Test Conversation with Messages",
        )
        test_db.add(conversation)
        await test_db.commit()
        await test_db.refresh(conversation)
        
        # Create messages
        messages = [
            MessageModel(
                conversation_id=conversation.id,
                role="user",
                content="Hello, how are you?",
            ),
            MessageModel(
                conversation_id=conversation.id,
                role="assistant",
                content="I'm doing well!",
            ),
            MessageModel(
                conversation_id=conversation.id,
                role="user",
                content="Great!",
            ),
            MessageModel(
                conversation_id=conversation.id,
                role="assistant",
                content="How can I help?",
            ),
        ]
        test_db.add_all(messages)
        await test_db.commit()
        
        response = await client.get(
            f"/api/v1/chat/conversation/{conversation.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conversation.id
        assert data["title"] == conversation.title
        assert len(data["messages"]) == 4
        assert data["total_messages"] == 4
        assert data["has_more"] is False
        assert data["limit"] == 50
        assert data["offset"] == 0
        
        # Check message structure
        msg = data["messages"][0]
        assert "id" in msg
        assert "role" in msg
        assert "content" in msg
        assert "created_at" in msg

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting non-existent conversation returns 404."""
        response = await client.get(
            f"/api/v1/chat/conversation/{uuid.uuid4()}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_conversation_unauthorized(
        self,
        client: AsyncClient,
        test_conversation: Conversation,
    ):
        """Test getting conversation without auth fails."""
        response = await client.get(
            f"/api/v1/chat/conversation/{test_conversation.id}",
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_other_users_conversation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_db,
        second_user: User,
    ):
        """Test getting another user's conversation returns 404."""
        # Create conversation for second user
        other_conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=second_user.id,
            title="Other User's Conversation",
        )
        test_db.add(other_conv)
        await test_db.commit()
        
        # Try to access as test_user
        response = await client.get(
            f"/api/v1/chat/conversation/{other_conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404


class TestDeleteConversation:
    """Tests for conversation deletion endpoints."""

    @pytest.mark.asyncio
    async def test_delete_conversation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_conversation: Conversation,
    ):
        """Test deleting a conversation."""
        response = await client.delete(
            f"/api/v1/chat/conversation/{test_conversation.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify conversation is deleted
        get_response = await client.get(
            f"/api/v1/chat/conversation/{test_conversation.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test deleting non-existent conversation returns 404."""
        response = await client.delete(
            f"/api/v1/chat/conversation/{uuid.uuid4()}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation_unauthorized(
        self,
        client: AsyncClient,
        test_conversation: Conversation,
    ):
        """Test deleting conversation without auth fails."""
        response = await client.delete(
            f"/api/v1/chat/conversation/{test_conversation.id}",
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_all_conversations(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_db,
        test_user: User,
    ):
        """Test deleting all conversations."""
        # Create multiple conversations
        for i in range(3):
            conv = Conversation(
                id=str(uuid.uuid4()),
                user_id=test_user.id,
                title=f"Conversation {i}",
            )
            test_db.add(conv)
        await test_db.commit()
        
        response = await client.delete(
            "/api/v1/chat/conversations",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 3


class TestRenameConversation:
    """Tests for conversation rename endpoint."""

    @pytest.mark.asyncio
    async def test_rename_conversation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_conversation: Conversation,
    ):
        """Test renaming a conversation."""
        response = await client.patch(
            f"/api/v1/chat/conversation/{test_conversation.id}/rename",
            headers=auth_headers,
            json={"title": "New Awesome Title"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify title is updated
        get_response = await client.get(
            f"/api/v1/chat/conversation/{test_conversation.id}",
            headers=auth_headers,
        )
        assert get_response.json()["title"] == "New Awesome Title"

    @pytest.mark.asyncio
    async def test_rename_conversation_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test renaming non-existent conversation returns 404."""
        response = await client.patch(
            f"/api/v1/chat/conversation/{uuid.uuid4()}/rename",
            headers=auth_headers,
            json={"title": "New Title"},
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rename_conversation_empty_title(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_conversation: Conversation,
    ):
        """Test renaming with empty title fails validation."""
        response = await client.patch(
            f"/api/v1/chat/conversation/{test_conversation.id}/rename",
            headers=auth_headers,
            json={"title": ""},
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rename_conversation_unauthorized(
        self,
        client: AsyncClient,
        test_conversation: Conversation,
    ):
        """Test renaming conversation without auth fails."""
        response = await client.patch(
            f"/api/v1/chat/conversation/{test_conversation.id}/rename",
            json={"title": "New Title"},
        )
        
        assert response.status_code == 401


class TestChatModels:
    """Tests for available models endpoint."""

    @pytest.mark.asyncio
    async def test_get_models(self, client: AsyncClient):
        """Test getting available LLM models."""
        response = await client.get("/api/v1/chat/models")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have gemini and openai providers
        assert "gemini" in data
        assert "openai" in data
        
        # Each provider should have models
        assert len(data["gemini"]) > 0
        assert len(data["openai"]) > 0
        
        # Check model structure
        model = data["gemini"][0]
        assert "id" in model
        assert "name" in model


class TestSentimentMethods:
    """Tests for sentiment methods endpoint."""

    @pytest.mark.asyncio
    async def test_get_methods(self, client: AsyncClient):
        """Test getting available sentiment methods."""
        response = await client.get("/api/v1/chat/methods")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert "nlp_api" in data
        assert "llm_separate" in data
        assert "structured" in data


class TestChatRequestValidation:
    """Tests for chat request validation."""

    @pytest.mark.asyncio
    async def test_invalid_provider(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test chat request with invalid provider fails."""
        response = await client.post(
            "/api/v1/chat/stream",
            headers=auth_headers,
            json={
                "message": "Hello",
                "provider": "invalid_provider",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_sentiment_method(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test chat request with invalid sentiment method fails."""
        response = await client.post(
            "/api/v1/chat/stream",
            headers=auth_headers,
            json={
                "message": "Hello",
                "sentiment_method": "invalid_method",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_message(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test chat request with empty message fails."""
        response = await client.post(
            "/api/v1/chat/stream",
            headers=auth_headers,
            json={
                "message": "",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_unauthorized(self, client: AsyncClient):
        """Test chat request without auth fails."""
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hello"},
        )
        
        assert response.status_code == 401
