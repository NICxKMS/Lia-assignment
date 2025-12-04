"""Comprehensive tests for sentiment analysis service.

Tests cover:
- SentimentResult dataclass
- SentimentService strategy selection
- Available methods
- Strategy caching
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sentiment import (
    SentimentResult,
    SentimentService,
    GoogleCloudNLPStrategy,
    LLMSeparateStrategy,
    StructuredOutputStrategy,
)


class TestSentimentResult:
    """Tests for SentimentResult dataclass."""

    def test_to_dict_complete(self):
        """Test to_dict with all fields populated."""
        result = SentimentResult(
            score=0.75,
            label="Positive",
            source="llm_separate",
            emotion="happy",
            details={"provider": "gemini", "model": "gemini-2.0-flash"},
        )
        
        data = result.to_dict()
        
        assert data["score"] == 0.75
        assert data["label"] == "Positive"
        assert data["source"] == "llm_separate"
        assert data["emotion"] == "happy"
        assert data["details"]["provider"] == "gemini"

    def test_to_dict_minimal(self):
        """Test to_dict with minimal fields."""
        result = SentimentResult(
            score=0.0,
            label="Neutral",
            source="test",
        )
        
        data = result.to_dict()
        
        assert data["score"] == 0.0
        assert data["label"] == "Neutral"
        assert data["source"] == "test"
        assert data["emotion"] is None
        assert data["details"] is None

    def test_score_rounding(self):
        """Test that score is rounded to 4 decimal places."""
        result = SentimentResult(
            score=0.123456789,
            label="Positive",
            source="test",
        )
        
        data = result.to_dict()
        
        assert data["score"] == 0.1235

    def test_score_to_label_boundaries(self):
        """Test score_to_label at boundary values."""
        # Exactly at boundaries
        assert SentimentResult.score_to_label(0.1) == "Neutral"
        assert SentimentResult.score_to_label(-0.1) == "Neutral"
        assert SentimentResult.score_to_label(0.11) == "Positive"
        assert SentimentResult.score_to_label(-0.11) == "Negative"

    def test_score_to_label_extremes(self):
        """Test score_to_label at extreme values."""
        assert SentimentResult.score_to_label(1.0) == "Positive"
        assert SentimentResult.score_to_label(-1.0) == "Negative"
        assert SentimentResult.score_to_label(0.0) == "Neutral"

    def test_neutral_factory(self):
        """Test neutral() factory creates proper neutral result."""
        result = SentimentResult.neutral()
        
        assert result.score == 0.0
        assert result.label == "Neutral"
        assert result.source == "default"
        assert result.emotion == "neutral"
        assert result.details is None


class TestSentimentService:
    """Tests for SentimentService class."""

    def test_available_methods(self):
        """Test get_available_methods returns all methods."""
        service = SentimentService()
        
        methods = service.get_available_methods()
        
        assert "nlp_api" in methods
        assert "llm_separate" in methods
        assert "structured" in methods
        assert len(methods) == 3

    def test_get_strategy_nlp_api(self):
        """Test getting NLP API strategy."""
        service = SentimentService()
        
        strategy = service.get_strategy("nlp_api")
        
        assert isinstance(strategy, GoogleCloudNLPStrategy)
        assert strategy.strategy_name == "nlp_api"

    def test_get_strategy_llm_separate(self):
        """Test getting LLM separate strategy."""
        service = SentimentService()
        
        strategy = service.get_strategy("llm_separate")
        
        assert isinstance(strategy, LLMSeparateStrategy)
        assert strategy.strategy_name == "llm_separate"

    def test_get_strategy_structured(self):
        """Test getting structured output strategy."""
        service = SentimentService()
        
        strategy = service.get_strategy("structured")
        
        assert isinstance(strategy, StructuredOutputStrategy)
        assert strategy.strategy_name == "structured"

    def test_get_strategy_unknown(self):
        """Test getting unknown strategy raises error."""
        service = SentimentService()
        
        with pytest.raises(ValueError, match="Unknown sentiment method"):
            service.get_strategy("unknown_method")

    def test_strategy_caching(self):
        """Test that strategies are cached and reused."""
        service = SentimentService()
        
        strategy1 = service.get_strategy("nlp_api")
        strategy2 = service.get_strategy("nlp_api")
        
        # Should be the same instance
        assert strategy1 is strategy2

    def test_strategy_caching_with_different_params(self):
        """Test that different params create different strategies."""
        service = SentimentService()
        
        strategy1 = service.get_strategy("llm_separate", "gemini", "model1")
        strategy2 = service.get_strategy("llm_separate", "gemini", "model2")
        
        # Should be different instances (different models)
        assert strategy1 is not strategy2


class TestGoogleCloudNLPStrategy:
    """Tests for Google Cloud NLP strategy."""

    def test_strategy_name(self):
        """Test strategy has correct name."""
        strategy = GoogleCloudNLPStrategy()
        
        assert strategy.strategy_name == "nlp_api"

    @pytest.mark.asyncio
    async def test_analyze_not_available(self):
        """Test analyze returns neutral when NLP not available."""
        strategy = GoogleCloudNLPStrategy()
        strategy._available = False  # Force unavailable
        
        result = await strategy.analyze("Test text")
        
        assert result.label == "Neutral"
        assert result.source == "nlp_api"
        assert "error" in (result.details or {})


class TestLLMSeparateStrategy:
    """Tests for LLM separate strategy."""

    def test_strategy_name(self):
        """Test strategy has correct name."""
        strategy = LLMSeparateStrategy()
        
        assert strategy.strategy_name == "llm_separate"

    def test_system_prompt_defined(self):
        """Test system prompt is defined."""
        assert LLMSeparateStrategy.SYSTEM_PROMPT is not None
        assert "sentiment" in LLMSeparateStrategy.SYSTEM_PROMPT.lower()


class TestStructuredOutputStrategy:
    """Tests for structured output strategy."""

    def test_strategy_name(self):
        """Test strategy has correct name."""
        strategy = StructuredOutputStrategy()
        
        assert strategy.strategy_name == "structured"

    @pytest.mark.asyncio
    async def test_analyze_falls_back_to_nlp(self):
        """Test analyze falls back to Cloud NLP for standalone calls."""
        # Create with a Cloud NLP instance
        cloud_nlp = GoogleCloudNLPStrategy()
        strategy = StructuredOutputStrategy(cloud_nlp)
        
        # Force NLP unavailable
        strategy._cloud_nlp._available = False
        
        result = await strategy.analyze("Test text")
        
        # Source should be 'structured' even though it used NLP fallback
        assert result.source == "structured"

    @pytest.mark.asyncio
    async def test_analyze_returns_neutral_without_cloud_nlp(self):
        """Test analyze returns neutral when no cloud_nlp is provided."""
        strategy = StructuredOutputStrategy(cloud_nlp=None)
        
        result = await strategy.analyze("Test text")
        
        assert result.label == "Neutral"
        assert result.score == 0.0


class TestSentimentServiceAnalyze:
    """Tests for SentimentService.analyze method."""

    @pytest.mark.asyncio
    async def test_analyze_calls_strategy(self):
        """Test analyze calls the correct strategy."""
        service = SentimentService()
        
        # Mock the strategy
        mock_result = SentimentResult(
            score=0.8,
            label="Positive",
            source="test",
        )
        
        with patch.object(service, "get_strategy") as mock_get:
            mock_strategy = MagicMock()
            mock_strategy.analyze = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_strategy
            
            result = await service.analyze("Test text", "llm_separate")
            
            mock_get.assert_called_once_with("llm_separate", "gemini", "gemini-2.0-flash-lite")
            mock_strategy.analyze.assert_called_once_with("Test text")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_analyze_with_custom_provider(self):
        """Test analyze passes provider and model to strategy."""
        service = SentimentService()
        
        mock_result = SentimentResult(
            score=0.5,
            label="Positive",
            source="test",
        )
        
        with patch.object(service, "get_strategy") as mock_get:
            mock_strategy = MagicMock()
            mock_strategy.analyze = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_strategy
            
            await service.analyze(
                "Test text",
                method="llm_separate",
                provider="openai",
                model="gpt-4o",
            )
            
            mock_get.assert_called_once_with("llm_separate", "openai", "gpt-4o")
