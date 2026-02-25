"""Chat API endpoint tests.

Tests for: history, conversation detail, delete, rename, models, methods, stream.
"""

import uuid
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.db.models import Conversation, Message, User

pytestmark = pytest.mark.asyncio


# =============================================================================
# History
# =============================================================================


async def test_history_empty(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.get("/api/v1/chat/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_history_returns_conversations(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_conversation: Conversation,
):
    resp = await client.get("/api/v1/chat/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == test_conversation.id


async def test_history_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/chat/history")
    assert resp.status_code == 401


# =============================================================================
# Conversation Detail
# =============================================================================


async def test_conversation_detail(
    client: AsyncClient,
    auth_headers: dict[str, str],
    conversation_with_messages: tuple[Conversation, list[Message]],
):
    conv, msgs = conversation_with_messages
    resp = await client.get(
        f"/api/v1/chat/conversation/{conv.id}", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == conv.id
    assert len(data["messages"]) == len(msgs)


async def test_conversation_detail_not_found(
    client: AsyncClient, auth_headers: dict[str, str],
):
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/v1/chat/conversation/{fake_id}", headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_conversation_detail_other_user(
    client: AsyncClient,
    test_conversation: Conversation,
    second_user: User,
):
    """A second user cannot see the first user's conversation."""
    login = await client.post("/api/v1/auth/login", json={
        "email": "second@example.com",
        "password": "Secondpass123",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(
        f"/api/v1/chat/conversation/{test_conversation.id}", headers=headers,
    )
    assert resp.status_code == 404


# =============================================================================
# Delete Conversation
# =============================================================================


async def test_delete_conversation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_conversation: Conversation,
):
    resp = await client.delete(
        f"/api/v1/chat/conversation/{test_conversation.id}", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_delete_conversation_not_found(
    client: AsyncClient, auth_headers: dict[str, str],
):
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/api/v1/chat/conversation/{fake_id}", headers=auth_headers,
    )
    assert resp.status_code == 404


# =============================================================================
# Delete All Conversations
# =============================================================================


async def test_delete_all_conversations(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_conversation: Conversation,
):
    resp = await client.delete("/api/v1/chat/conversations", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["deleted_count"] >= 1


async def test_delete_all_no_conversations(
    client: AsyncClient, auth_headers: dict[str, str],
):
    resp = await client.delete("/api/v1/chat/conversations", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == 0


# =============================================================================
# Rename Conversation
# =============================================================================


async def test_rename_conversation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_conversation: Conversation,
):
    resp = await client.patch(
        f"/api/v1/chat/conversation/{test_conversation.id}/rename",
        json={"title": "New Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_rename_conversation_not_found(
    client: AsyncClient, auth_headers: dict[str, str],
):
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/chat/conversation/{fake_id}/rename",
        json={"title": "New Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# =============================================================================
# Models & Methods
# =============================================================================


async def test_get_models(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.get("/api/v1/chat/models", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert len(data) > 0


async def test_get_sentiment_methods(
    client: AsyncClient, auth_headers: dict[str, str],
):
    resp = await client.get("/api/v1/chat/methods", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


# =============================================================================
# Chat Stream Validation
# =============================================================================


async def test_stream_rejects_empty_message(
    client: AsyncClient, auth_headers: dict[str, str],
):
    resp = await client.post(
        "/api/v1/chat/stream",
        json={"message": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_stream_rejects_no_content(
    client: AsyncClient, auth_headers: dict[str, str],
):
    resp = await client.post(
        "/api/v1/chat/stream",
        json={},
        headers=auth_headers,
    )
    # No message or messages → get_user_message() raises ValueError → 400
    assert resp.status_code in (400, 422)


@pytest.mark.parametrize("provider", ["invalid", "notreal"])
async def test_stream_rejects_invalid_provider(
    client: AsyncClient, auth_headers: dict[str, str], provider: str,
):
    resp = await client.post(
        "/api/v1/chat/stream",
        json={"message": "Hi", "provider": provider},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# =============================================================================
# Chat Stream SSE (mocked LLM)
# =============================================================================


async def test_stream_sse_events(
    client: AsyncClient, auth_headers: dict[str, str],
):
    """Test that the stream endpoint returns proper SSE events with mocked orchestrator."""
    from app.main import app
    from app.services.chat import ChatOrchestrator, get_chat_orchestrator

    async def mock_process_stream(**kwargs):
        yield 'event: start\ndata: {"conversation_id": "test-123", "message_id": 1}\n\n'
        yield 'event: chunk\ndata: {"content": "Hello!"}\n\n'
        yield 'event: done\ndata: {"finish_reason": "stop"}\n\n'

    original = app.dependency_overrides.get(get_chat_orchestrator)
    mock_orch = MagicMock(spec=ChatOrchestrator)
    mock_orch.process_chat_stream = MagicMock(side_effect=lambda **kw: mock_process_stream(**kw))
    app.dependency_overrides[get_chat_orchestrator] = lambda: mock_orch

    try:
        resp = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: start" in body
        assert "event: chunk" in body
        assert "event: done" in body
    finally:
        if original is not None:
            app.dependency_overrides[get_chat_orchestrator] = original
        else:
            app.dependency_overrides.pop(get_chat_orchestrator, None)
