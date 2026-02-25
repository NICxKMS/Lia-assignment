"""Tests for SentimentService — strategy selection, available methods, cumulative state.

SentimentResult tests live in test_chat_service.py (single canonical location).
Replaces previous test_sentiment.py — no duplicates.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sentiment import (
    CumulativeState,
    GoogleCloudNLPStrategy,
    LLMSeparateStrategy,
    SentimentResult,
    SentimentService,
    StructuredOutputStrategy,
)

# ---------------------------------------------------------------------------
# SentimentService — strategy selection
# ---------------------------------------------------------------------------

class TestSentimentService:
    def test_available_methods(self):
        svc = SentimentService()
        methods = svc.get_available_methods()
        assert set(methods) == {"nlp_api", "llm_separate", "structured"}

    @pytest.mark.parametrize("method,cls", [
        ("nlp_api", GoogleCloudNLPStrategy),
        ("llm_separate", LLMSeparateStrategy),
        ("structured", StructuredOutputStrategy),
    ])
    def test_get_strategy_returns_correct_type(self, method: str, cls: type):
        svc = SentimentService()
        assert isinstance(svc.get_strategy(method), cls)

    def test_unknown_strategy_raises(self):
        svc = SentimentService()
        with pytest.raises(ValueError, match="Unknown sentiment method"):
            svc.get_strategy("unknown")

    def test_nlp_api_is_singleton(self):
        svc = SentimentService()
        assert svc.get_strategy("nlp_api") is svc.get_strategy("nlp_api")

    def test_structured_is_singleton(self):
        svc = SentimentService()
        assert svc.get_strategy("structured") is svc.get_strategy("structured")

    def test_llm_separate_cached_by_provider_model(self):
        svc = SentimentService()
        s1 = svc.get_strategy("llm_separate", "gemini", "m1")
        s2 = svc.get_strategy("llm_separate", "gemini", "m2")
        s3 = svc.get_strategy("llm_separate", "gemini", "m1")
        assert s1 is not s2
        assert s1 is s3

    @pytest.mark.asyncio
    async def test_analyze_delegates_to_strategy(self):
        svc = SentimentService()
        mock_result = SentimentResult(score=0.8, label="Positive", source="test")
        with patch.object(svc, "get_strategy") as mock_get:
            mock_strategy = MagicMock()
            mock_strategy.analyze = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_strategy
            result = await svc.analyze("txt", "llm_separate")
            mock_strategy.analyze.assert_called_once_with("txt")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_analyze_passes_provider_model(self):
        svc = SentimentService()
        with patch.object(svc, "get_strategy") as mock_get:
            mock_strategy = MagicMock()
            mock_strategy.analyze = AsyncMock(return_value=SentimentResult.neutral())
            mock_get.return_value = mock_strategy
            await svc.analyze("t", method="llm_separate", provider="openai", model="gpt-4o")
            mock_get.assert_called_once_with("llm_separate", "openai", "gpt-4o")

    def test_default_method_is_llm_separate(self):
        svc = SentimentService()
        # analyze() default method param is "llm_separate"
        import inspect
        sig = inspect.signature(svc.analyze)
        assert sig.parameters["method"].default == "llm_separate"


# ---------------------------------------------------------------------------
# Strategy names
# ---------------------------------------------------------------------------

class TestStrategyNames:
    @pytest.mark.parametrize("cls,name", [
        (GoogleCloudNLPStrategy, "nlp_api"),
        (LLMSeparateStrategy, "llm_separate"),
        (StructuredOutputStrategy, "structured"),
    ])
    def test_strategy_name_attr(self, cls, name):
        assert cls.strategy_name == name

    def test_llm_separate_has_system_prompt(self):
        assert "sentiment" in LLMSeparateStrategy.SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# GoogleCloudNLPStrategy
# ---------------------------------------------------------------------------

class TestGoogleCloudNLP:
    @pytest.mark.asyncio
    async def test_returns_neutral_when_unavailable(self):
        strategy = GoogleCloudNLPStrategy()
        strategy._available = False
        result = await strategy.analyze("hello")
        assert result.label == "Neutral"
        assert result.source == "nlp_api"


# ---------------------------------------------------------------------------
# StructuredOutputStrategy
# ---------------------------------------------------------------------------

class TestStructuredOutput:
    @pytest.mark.asyncio
    async def test_returns_neutral_without_cloud_nlp(self):
        strategy = StructuredOutputStrategy(cloud_nlp=None)
        result = await strategy.analyze("test")
        assert result.score == 0.0
        assert result.label == "Neutral"

    @pytest.mark.asyncio
    async def test_falls_back_to_cloud_nlp(self):
        nlp = GoogleCloudNLPStrategy()
        nlp._available = False
        strategy = StructuredOutputStrategy(nlp)
        result = await strategy.analyze("test")
        assert result.source == "structured"


# ---------------------------------------------------------------------------
# CumulativeState
# ---------------------------------------------------------------------------

class TestCumulativeState:
    def test_to_dict(self):
        cs = CumulativeState(summary="ok", score=0.5, count=3, label="Positive")
        d = cs.to_dict()
        assert d == {"summary": "ok", "score": 0.5, "count": 3, "label": "Positive"}

    def test_from_dict_none(self):
        cs = CumulativeState.from_dict(None)
        assert cs.count == 0
        assert cs.score == 0.0

    def test_from_dict_roundtrip(self):
        original = CumulativeState(summary="s", score=-0.3, count=5, label="Negative")
        restored = CumulativeState.from_dict(original.to_dict())
        assert restored.summary == original.summary
        assert restored.score == original.score
        assert restored.count == original.count
