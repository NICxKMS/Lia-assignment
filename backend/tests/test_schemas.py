"""Tests for app.api.schemas — Pydantic validation."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    ChatRequest,
    ConversationSummary,
    MessagePart,
    ModelSettings,
    UIMessage,
    UserCreate,
)

# =============================================================================
# UserCreate password validation
# =============================================================================

class TestUserCreatePassword:

    @pytest.mark.parametrize(
        "password, error_fragment",
        [
            ("alllower1", "uppercase"),
            ("ALLUPPER1", "lowercase"),
            ("NoDigitsHere", "digit"),
            ("Sh0rt", "at least 8"),    # min_length=8
        ],
        ids=["no-upper", "no-lower", "no-digit", "too-short"],
    )
    def test_invalid_passwords(self, password: str, error_fragment: str):
        with pytest.raises(ValidationError, match=error_fragment):
            UserCreate(email="a@b.com", username="user1", password=password)

    def test_valid_password(self):
        u = UserCreate(email="a@b.com", username="user1", password="ValidPass1")
        assert u.password == "ValidPass1"


# =============================================================================
# ChatRequest.get_user_message()
# =============================================================================

class TestChatRequestGetUserMessage:

    def test_legacy_message_field(self):
        req = ChatRequest(message="hello")
        assert req.get_user_message() == "hello"

    def test_ai_sdk_format(self):
        req = ChatRequest(
            messages=[
                UIMessage(
                    id="1",
                    role="user",
                    parts=[MessagePart(type="text", text="world")],
                ),
            ],
        )
        assert req.get_user_message() == "world"

    def test_ai_sdk_last_user_message(self):
        req = ChatRequest(
            messages=[
                UIMessage(id="1", role="user", parts=[MessagePart(type="text", text="first")]),
                UIMessage(id="2", role="assistant", parts=[MessagePart(type="text", text="resp")]),
                UIMessage(id="3", role="user", parts=[MessagePart(type="text", text="second")]),
            ],
        )
        assert req.get_user_message() == "second"

    def test_empty_messages_raises(self):
        req = ChatRequest(messages=[])
        with pytest.raises(ValueError, match="No message content"):
            req.get_user_message()

    def test_no_content_raises(self):
        req = ChatRequest()
        with pytest.raises(ValueError, match="No message content"):
            req.get_user_message()


# =============================================================================
# ModelSettings bounds
# =============================================================================

class TestModelSettings:

    @pytest.mark.parametrize(
        "field, bad_value",
        [
            ("temperature", -0.1),
            ("temperature", 2.1),
            ("top_p", -0.1),
            ("top_p", 1.1),
            ("max_tokens", 0),
            ("max_tokens", 33000),
        ],
        ids=["temp-low", "temp-high", "top_p-low", "top_p-high", "tokens-zero", "tokens-over"],
    )
    def test_out_of_bounds(self, field: str, bad_value: float):
        with pytest.raises(ValidationError):
            ModelSettings(**{field: bad_value})  # type: ignore[arg-type]

    def test_defaults(self):
        m = ModelSettings()
        assert m.temperature == 0.7
        assert m.max_tokens == 2048


# =============================================================================
# ConversationSummary serialization
# =============================================================================

class TestConversationSummary:

    def test_from_dict(self):
        from datetime import datetime

        now = datetime.now(UTC)
        cs = ConversationSummary(
            id="abc", title="Chat", created_at=now, updated_at=now, message_count=5,
        )
        assert cs.id == "abc"
        assert cs.message_count == 5
