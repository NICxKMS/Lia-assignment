"""Tests for LLM service — StreamChunk, StructuredStreamChunk, ModelInfo, adapters, retry.

Replaces test_llm_thinking.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import LLMProviderError
from app.services.llm import (
    GeminiAdapter,
    LLMService,
    ModelInfo,
    OpenAIAdapter,
    StreamChunk,
    StructuredStreamChunk,
    _run_with_retry,
)

# ---------------------------------------------------------------------------
# StreamChunk
# ---------------------------------------------------------------------------

class TestStreamChunk:
    def test_defaults(self):
        c = StreamChunk(content="hi")
        assert c.content == "hi"
        assert c.is_final is False
        assert c.model == ""
        assert c.provider == ""
        assert c.finish_reason is None
        assert c.usage is None
        assert c.is_thought is False

    def test_thought_flag(self):
        c = StreamChunk(content="think", is_thought=True, model="m", provider="gemini")
        assert c.is_thought is True

    def test_final_chunk(self):
        c = StreamChunk(content="", is_final=True, finish_reason="stop")
        assert c.is_final is True
        assert c.finish_reason == "stop"


# ---------------------------------------------------------------------------
# StructuredStreamChunk
# ---------------------------------------------------------------------------

class TestStructuredStreamChunk:
    def test_sentiment_fields_default_none(self):
        c = StructuredStreamChunk(content="x")
        assert c.sentiment_score is None
        assert c.sentiment_label is None
        assert c.sentiment_emotion is None

    def test_sentiment_fields_set(self):
        c = StructuredStreamChunk(
            content="hi", sentiment_score=0.8, sentiment_label="Positive", sentiment_emotion="happy",
        )
        assert c.sentiment_score == 0.8
        assert c.sentiment_label == "Positive"
        assert c.sentiment_emotion == "happy"

    def test_inherits_is_thought(self):
        c = StructuredStreamChunk(content="x", is_thought=True)
        assert c.is_thought is True


# ---------------------------------------------------------------------------
# ModelInfo
# ---------------------------------------------------------------------------

class TestModelInfo:
    def test_fields(self):
        m = ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai", context_window=128000)
        assert m.id == "gpt-4o"
        assert m.name == "GPT-4o"
        assert m.provider == "openai"
        assert m.context_window == 128000
        assert m.supports_streaming is True
        assert m.supports_structured is False

    def test_supports_thinking_not_in_base(self):
        m = ModelInfo(id="x", name="x", provider="x")
        assert not hasattr(m, "supports_thinking")


# ---------------------------------------------------------------------------
# GeminiAdapter
# ---------------------------------------------------------------------------

class TestGeminiAdapter:
    @pytest.fixture
    def adapter(self):
        with patch("app.services.llm.genai.Client"):
            return GeminiAdapter(api_key="test-key")

    def test_provider_name(self, adapter):
        assert adapter.provider_name == "gemini"

    def test_models_list_not_empty(self):
        assert len(GeminiAdapter.MODELS) >= 2

    @pytest.mark.parametrize("model", GeminiAdapter.MODELS)
    def test_model_has_required_fields(self, model):
        assert model.id
        assert model.name
        assert model.provider == "gemini"
        assert model.context_window > 0

    def test_get_available_models_returns_models(self, adapter):
        models = adapter.get_available_models()
        assert models is GeminiAdapter.MODELS

    @pytest.mark.asyncio
    async def test_stream_thought_and_response(self, adapter):
        thought = MagicMock(thought=True, text="thinking")
        resp = MagicMock(thought=False, text="answer")
        content = MagicMock(parts=[thought, resp])
        candidate = MagicMock(content=content)
        chunk = MagicMock(candidates=[candidate], text=None)

        async def mock_gen():
            yield chunk

        adapter.client.aio.models.generate_content_stream = AsyncMock(return_value=mock_gen())
        chunks = [c async for c in adapter.generate_stream([{"role": "user", "content": "q"}], "m")]
        thoughts = [c for c in chunks if c.is_thought]
        regular = [c for c in chunks if not c.is_thought and c.content]
        assert len(thoughts) == 1
        assert len(regular) == 1

    @pytest.mark.asyncio
    async def test_stream_text_only_fallback(self, adapter):
        chunk = MagicMock(candidates=None, text="simple")

        async def mock_gen():
            yield chunk

        adapter.client.aio.models.generate_content_stream = AsyncMock(return_value=mock_gen())
        chunks = [c async for c in adapter.generate_stream([{"role": "user", "content": "q"}], "m")]
        text_chunks = [c for c in chunks if c.content and not c.is_final]
        assert text_chunks[0].content == "simple"
        assert text_chunks[0].is_thought is False

    @pytest.mark.asyncio
    async def test_stream_no_api_key_raises(self):
        with patch("app.services.llm.genai.Client"):
            a = GeminiAdapter(api_key="")
        a.api_key = None  # type: ignore[assignment]
        with pytest.raises(LLMProviderError):
            async for _ in a.generate_stream([{"role": "user", "content": "x"}], "m"):
                pass


# ---------------------------------------------------------------------------
# OpenAIAdapter
# ---------------------------------------------------------------------------

class TestOpenAIAdapter:
    def test_provider_name(self):
        with patch("app.services.llm.AsyncOpenAI"):
            a = OpenAIAdapter(api_key="test-key")
        assert a.provider_name == "openai"

    def test_models_list_not_empty(self):
        assert len(OpenAIAdapter.MODELS) >= 2

    @pytest.mark.parametrize("model", OpenAIAdapter.MODELS)
    def test_model_has_required_fields(self, model):
        assert model.id
        assert model.name
        assert model.provider == "openai"
        assert model.context_window > 0


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class TestLLMService:
    def test_get_adapter_gemini(self):
        svc = LLMService()
        with patch("app.services.llm.GeminiAdapter"):
            adapter = svc.get_adapter("gemini")
        assert adapter is not None

    def test_get_adapter_openai(self):
        svc = LLMService()
        with patch("app.services.llm.OpenAIAdapter"):
            adapter = svc.get_adapter("openai")
        assert adapter is not None

    def test_get_adapter_unknown_raises(self):
        svc = LLMService()
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            svc.get_adapter("anthropic")

    def test_get_adapter_caches(self):
        svc = LLMService()
        with patch("app.services.llm.GeminiAdapter"):
            a1 = svc.get_adapter("gemini")
            a2 = svc.get_adapter("gemini")
        assert a1 is a2

    def test_get_all_models_both_providers(self):
        svc = LLMService()
        models = svc.get_all_models()
        assert "gemini" in models
        assert "openai" in models
        assert len(models["gemini"]) == len(GeminiAdapter.MODELS)
        assert len(models["openai"]) == len(OpenAIAdapter.MODELS)

    def test_get_providers(self):
        svc = LLMService()
        assert set(svc.get_providers()) == {"gemini", "openai"}


# ---------------------------------------------------------------------------
# _run_with_retry
# ---------------------------------------------------------------------------

class TestRunWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        result = await _run_with_retry(AsyncMock(return_value=42))
        assert result == 42

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            return "ok"

        result = await _run_with_retry(flaky)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        with pytest.raises(httpx.TimeoutException):
            await _run_with_retry(AsyncMock(side_effect=httpx.TimeoutException("timeout")))
