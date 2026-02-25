"""Tests for ChatOrchestrator — CRUD, SSE formatting, streaming, thinking, sentiment.

Replaces test_chat_sentiment.py and test_chat_thinking.py.
"""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, User
from app.services.chat import ChatOrchestrator, _sentiment_stream_payload, make_sse_formatter
from app.services.llm import LLMService, StreamChunk
from app.services.sentiment import CumulativeState, SentimentResult, SentimentService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse(raw: str) -> tuple[str, dict[str, Any]]:
    """Parse an SSE event string into (event_type, data_dict)."""
    event_type = ""
    data_str = ""
    for line in raw.strip().split("\n"):
        if line.startswith("event: "):
            event_type = line[len("event: "):]
        elif line.startswith("data: "):
            data_str = line[len("data: "):]
    return event_type, json.loads(data_str) if data_str else {}


def _make_mock_cache(available: bool = False) -> MagicMock:
    """Create a mock CacheService for chat tests."""
    from tests.conftest import make_mock_cache
    return make_mock_cache(available=available)


def _make_mock_sentiment() -> MagicMock:
    """Create a mock SentimentService for chat tests."""
    mock = MagicMock(spec=SentimentService)
    mock.analyze = AsyncMock(return_value=SentimentResult(
        score=0.5, label="Positive", source="test", emotion="happy",
    ))
    mock.update_cumulative = AsyncMock(return_value=(
        SentimentResult(score=0.3, label="Positive", source="test", emotion="happy"),
        CumulativeState(summary="ok", score=0.3, count=1, label="Positive"),
    ))
    return mock


async def _mock_stream(*_a, **_kw):
    yield StreamChunk(content="Hi!", model="m", provider="gemini")
    yield StreamChunk(content="", is_final=True, model="m", provider="gemini", finish_reason="stop")


async def _mock_thought_stream(*_a, **_kw):
    yield StreamChunk(content="Thinking...", is_thought=True, model="m", provider="gemini")
    yield StreamChunk(content="Result", is_thought=False, model="m", provider="gemini")
    yield StreamChunk(content="", is_final=True, model="m", provider="gemini", finish_reason="stop")


# ---------------------------------------------------------------------------
# SSE formatter
# ---------------------------------------------------------------------------

class TestMakeSSEFormatter:
    def test_counter_increments(self):
        fmt = make_sse_formatter()
        e1 = fmt("chunk", {"content": "a"})
        e2 = fmt("chunk", {"content": "b"})
        assert e1.startswith("id: 1\n")
        assert e2.startswith("id: 2\n")

    def test_event_format_structure(self):
        fmt = make_sse_formatter()
        raw = fmt("chunk", {"content": "hi"})
        assert "event: chunk\n" in raw
        assert raw.endswith("\n\n")
        assert "data: " in raw

    def test_data_is_valid_json(self):
        fmt = make_sse_formatter()
        raw = fmt("sentiment", {"score": 0.5})
        _, data = _parse_sse(raw)
        assert data["score"] == 0.5

    @pytest.mark.parametrize("event_type", ["start", "chunk", "thought", "sentiment", "done", "error"])
    def test_event_types_roundtrip(self, event_type: str):
        fmt = make_sse_formatter()
        raw = fmt(event_type, {"x": 1})
        parsed_type, _ = _parse_sse(raw)
        assert parsed_type == event_type

    def test_separate_formatters_have_independent_counters(self):
        f1 = make_sse_formatter()
        f2 = make_sse_formatter()
        assert f1("a", {}).startswith("id: 1\n")
        assert f2("b", {}).startswith("id: 1\n")


# ---------------------------------------------------------------------------
# _sentiment_stream_payload
# ---------------------------------------------------------------------------

class TestSentimentStreamPayload:
    def test_none_returns_none(self):
        assert _sentiment_stream_payload(None) is None

    def test_basic_payload(self):
        r = SentimentResult(score=0.12345, label="Positive", source="t", emotion="happy")
        p = _sentiment_stream_payload(r)
        assert p is not None
        assert p["score"] == 0.1235
        assert p["label"] == "Positive"
        assert p["emotion"] == "happy"
        assert "summary" not in p

    def test_includes_summary_when_set(self):
        r = SentimentResult(score=0.0, label="Neutral", source="t", summary="test summary")
        p = _sentiment_stream_payload(r)
        assert p is not None
        assert p["summary"] == "test summary"


# ---------------------------------------------------------------------------
# ChatOrchestrator CRUD
# ---------------------------------------------------------------------------

class TestOrchestratorCRUD:
    @pytest.mark.asyncio
    async def test_create_new_conversation(self, db: AsyncSession, test_user: User):
        orch = ChatOrchestrator(cache_service=_make_mock_cache())
        conv = await orch._get_or_create_conversation(db, test_user.id, None)
        assert conv.user_id == test_user.id
        assert conv.id is not None

    @pytest.mark.asyncio
    async def test_get_existing_conversation(
        self, db: AsyncSession, test_user: User, test_conversation: Conversation,
    ):
        orch = ChatOrchestrator(cache_service=_make_mock_cache())
        conv = await orch._get_or_create_conversation(db, test_user.id, test_conversation.id)
        assert conv.id == test_conversation.id

    @pytest.mark.asyncio
    async def test_wrong_user_creates_new_conversation(
        self, db: AsyncSession, second_user: User, test_conversation: Conversation,
    ):
        orch = ChatOrchestrator(cache_service=_make_mock_cache())
        conv = await orch._get_or_create_conversation(db, second_user.id, test_conversation.id)
        assert conv.id != test_conversation.id
        assert conv.user_id == second_user.id

    @pytest.mark.asyncio
    async def test_load_context_from_db(
        self, db: AsyncSession, conversation_with_messages,
    ):
        conversation, messages = conversation_with_messages
        orch = ChatOrchestrator(cache_service=_make_mock_cache())
        ctx = await orch._load_context(db, conversation.id)
        assert len(ctx) == 2  # 2 messages in fixture
        assert ctx[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_load_context_from_cache(
        self, db: AsyncSession, test_conversation: Conversation,
    ):
        cached = [{"role": "user", "content": "cached"}]
        mock_cache = _make_mock_cache(available=True)
        mock_cache.get_conversation_context = AsyncMock(return_value=cached)
        orch = ChatOrchestrator(cache_service=mock_cache)
        ctx = await orch._load_context(db, test_conversation.id)
        assert ctx == cached

    @pytest.mark.parametrize("msg,expected_title", [
        ("Hello", "Hello"),
        ("x" * 60, "x" * 50),  # truncated — rsplit may shorten further
    ])
    def test_generate_title(self, msg: str, expected_title: str):
        title = ChatOrchestrator._generate_title(msg)
        assert len(title) <= 53  # 50 + "..."
        if len(msg) <= 50:
            assert title == expected_title


# ---------------------------------------------------------------------------
# Streaming — event types
# ---------------------------------------------------------------------------

class TestStreamEventTypes:
    @pytest.mark.asyncio
    async def test_stream_emits_start_chunk_sentiment_done(
        self, db: AsyncSession, test_user: User,
    ):
        mock_cache = _make_mock_cache()
        mock_sentiment = _make_mock_sentiment()
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_adapter.return_value.generate_stream = _mock_stream
        orch = ChatOrchestrator(
            llm_service=mock_llm, sentiment_service=mock_sentiment, cache_service=mock_cache,
        )
        conv = Conversation(id=str(uuid.uuid4()), user_id=test_user.id, title="T")
        db.add(conv)
        await db.commit()

        types = []
        async for ev in orch.process_chat_stream(db, test_user, "hi", conv.id):
            t, _ = _parse_sse(ev)
            types.append(t)

        assert "start" in types
        assert "chunk" in types
        assert "sentiment" in types
        assert "done" in types


# ---------------------------------------------------------------------------
# Thinking
# ---------------------------------------------------------------------------

class TestThinking:
    @pytest.mark.asyncio
    async def test_thought_events_emitted(self, db: AsyncSession, test_user: User):
        mock_cache = _make_mock_cache()
        mock_sentiment = _make_mock_sentiment()
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_adapter.return_value.generate_stream = _mock_thought_stream
        orch = ChatOrchestrator(
            llm_service=mock_llm, sentiment_service=mock_sentiment, cache_service=mock_cache,
        )
        conv = Conversation(id=str(uuid.uuid4()), user_id=test_user.id, title="T")
        db.add(conv)
        await db.commit()

        types = []
        async for ev in orch.process_chat_stream(db, test_user, "hi", conv.id):
            t, _ = _parse_sse(ev)
            types.append(t)

        assert "thought" in types

    @pytest.mark.asyncio
    async def test_thoughts_stored_in_model_info(self, db: AsyncSession, test_user: User):
        mock_cache = _make_mock_cache()
        mock_sentiment = _make_mock_sentiment()
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_adapter.return_value.generate_stream = _mock_thought_stream
        orch = ChatOrchestrator(
            llm_service=mock_llm, sentiment_service=mock_sentiment, cache_service=mock_cache,
        )
        conv = Conversation(id=str(uuid.uuid4()), user_id=test_user.id, title="T")
        db.add(conv)
        await db.commit()

        async for _ in orch.process_chat_stream(db, test_user, "hi", conv.id):
            pass
        await db.commit()

        result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id, Message.role == "assistant")
        )
        msg = result.scalar_one()
        assert msg.model_info is not None
        assert "Thinking..." in msg.model_info["thoughts"]


# ---------------------------------------------------------------------------
# Sentiment integration
# ---------------------------------------------------------------------------

class TestSentimentIntegration:
    @pytest.mark.asyncio
    async def test_sentiment_event_in_stream(self, db: AsyncSession, test_user: User):
        mock_cache = _make_mock_cache()
        mock_sentiment = _make_mock_sentiment()
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_adapter.return_value.generate_stream = _mock_stream
        orch = ChatOrchestrator(
            llm_service=mock_llm, sentiment_service=mock_sentiment, cache_service=mock_cache,
        )
        conv = Conversation(id=str(uuid.uuid4()), user_id=test_user.id, title="T")
        db.add(conv)
        await db.commit()

        sentiment_data = None
        async for ev in orch.process_chat_stream(db, test_user, "hi", conv.id):
            t, d = _parse_sse(ev)
            if t == "sentiment":
                sentiment_data = d

        assert sentiment_data is not None
        assert "message" in sentiment_data
        assert "cumulative" in sentiment_data

    @pytest.mark.asyncio
    async def test_analyze_called_once_per_message(self, db: AsyncSession, test_user: User):
        mock_cache = _make_mock_cache()
        mock_sentiment = _make_mock_sentiment()
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_adapter.return_value.generate_stream = _mock_stream
        orch = ChatOrchestrator(
            llm_service=mock_llm, sentiment_service=mock_sentiment, cache_service=mock_cache,
        )
        conv = Conversation(id=str(uuid.uuid4()), user_id=test_user.id, title="T")
        db.add(conv)
        await db.commit()

        async for _ in orch.process_chat_stream(db, test_user, "hi", conv.id):
            pass

        assert mock_sentiment.analyze.call_count == 1


# ---------------------------------------------------------------------------
# SentimentResult (single canonical location)
# ---------------------------------------------------------------------------

class TestSentimentResult:
    def test_to_dict_complete(self):
        r = SentimentResult(score=0.75, label="Positive", source="llm_separate", emotion="happy",
                            details={"provider": "gemini"})
        d = r.to_dict()
        assert d["score"] == 0.75
        assert d["label"] == "Positive"
        assert d["emotion"] == "happy"

    def test_to_dict_omits_none_summary_and_details(self):
        r = SentimentResult(score=0.0, label="Neutral", source="t")
        d = r.to_dict()
        assert "summary" not in d
        assert "details" not in d

    def test_score_rounding(self):
        r = SentimentResult(score=0.123456789, label="Positive", source="t")
        assert r.to_dict()["score"] == 0.1235

    @pytest.mark.parametrize("score,expected", [
        (0.5, "Positive"), (-0.5, "Negative"), (0.0, "Neutral"),
        (0.1, "Neutral"), (-0.1, "Neutral"), (0.11, "Positive"), (-0.11, "Negative"),
        (1.0, "Positive"), (-1.0, "Negative"),
    ])
    def test_score_to_label(self, score: float, expected: str):
        assert SentimentResult.score_to_label(score) == expected

    def test_neutral_factory(self):
        r = SentimentResult.neutral()
        assert r.score == 0.0
        assert r.label == "Neutral"
        assert r.source == "default"
        assert r.emotion == "neutral"

    def test_to_dict_includes_summary(self):
        r = SentimentResult(score=0.0, label="Neutral", source="t", summary="sum")
        assert r.to_dict()["summary"] == "sum"
