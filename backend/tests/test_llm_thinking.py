"""Tests for LLM thinking feature with dynamic thinking budget.

Tests cover:
- StreamChunk is_thought field
- Thinking config in generate_stream
- Thought chunk detection and yielding
- Structured stream thinking config
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm import (
    StreamChunk,
    StructuredStreamChunk,
    GeminiAdapter,
    ModelInfo,
)


class TestStreamChunk:
    """Tests for StreamChunk dataclass with thinking support."""

    def test_stream_chunk_default_values(self):
        """Test StreamChunk default values."""
        chunk = StreamChunk(content="Hello")
        
        assert chunk.content == "Hello"
        assert chunk.is_final is False
        assert chunk.model == ""
        assert chunk.provider == ""
        assert chunk.finish_reason is None
        assert chunk.usage is None
        assert chunk.is_thought is False

    def test_stream_chunk_thought_flag(self):
        """Test StreamChunk with is_thought=True."""
        chunk = StreamChunk(
            content="Let me think about this...",
            model="gemini-2.0-flash",
            provider="gemini",
            is_thought=True,
        )
        
        assert chunk.content == "Let me think about this..."
        assert chunk.is_thought is True
        assert chunk.model == "gemini-2.0-flash"
        assert chunk.provider == "gemini"

    def test_stream_chunk_regular_content(self):
        """Test StreamChunk for regular response content."""
        chunk = StreamChunk(
            content="The answer is 42.",
            model="gemini-2.0-flash",
            provider="gemini",
            is_thought=False,
        )
        
        assert chunk.content == "The answer is 42."
        assert chunk.is_thought is False

    def test_stream_chunk_final(self):
        """Test final StreamChunk."""
        chunk = StreamChunk(
            content="",
            is_final=True,
            model="gemini-2.0-flash",
            provider="gemini",
            finish_reason="stop",
        )
        
        assert chunk.is_final is True
        assert chunk.finish_reason == "stop"
        assert chunk.is_thought is False

    def test_structured_stream_chunk_inherits_thought(self):
        """Test StructuredStreamChunk inherits is_thought field."""
        chunk = StructuredStreamChunk(
            content="Response",
            sentiment_score=0.8,
            sentiment_label="Positive",
            is_thought=False,
        )
        
        assert chunk.is_thought is False
        assert chunk.sentiment_score == 0.8


class TestGeminiAdapterThinking:
    """Tests for GeminiAdapter thinking configuration."""

    @pytest.fixture
    def adapter(self):
        """Create a Gemini adapter with mocked client."""
        with patch('app.services.llm.genai.Client'):
            adapter = GeminiAdapter(api_key="test-key")
        return adapter

    @pytest.mark.asyncio
    async def test_generate_stream_creates_thinking_config(self, adapter):
        """Test that generate_stream uses thinking config."""
        # Create mock chunk with thought part
        mock_thought_part = MagicMock()
        mock_thought_part.thought = True
        mock_thought_part.text = "Let me analyze this..."
        
        mock_response_part = MagicMock()
        mock_response_part.thought = False
        mock_response_part.text = "The answer is 42."
        
        mock_content = MagicMock()
        mock_content.parts = [mock_thought_part, mock_response_part]
        
        mock_candidate = MagicMock()
        mock_candidate.content = mock_content
        
        mock_chunk1 = MagicMock()
        mock_chunk1.candidates = [mock_candidate]
        mock_chunk1.text = None
        
        # Final chunk
        mock_chunk_final = MagicMock()
        mock_chunk_final.candidates = None
        mock_chunk_final.text = None
        
        async def mock_stream():
            yield mock_chunk1
        
        adapter.client.aio.models.generate_content_stream = AsyncMock(
            return_value=mock_stream()
        )
        
        messages = [{"role": "user", "content": "What is 6 times 7?"}]
        chunks = []
        
        async for chunk in adapter.generate_stream(
            messages=messages,
            model="gemini-2.0-flash",
        ):
            chunks.append(chunk)
        
        # Should have thought chunk, response chunk, and final chunk
        assert len(chunks) >= 2
        
        # First chunk should be thought
        thought_chunks = [c for c in chunks if c.is_thought]
        assert len(thought_chunks) == 1
        assert thought_chunks[0].content == "Let me analyze this..."
        
        # Should have response chunk
        response_chunks = [c for c in chunks if not c.is_thought and c.content]
        assert len(response_chunks) == 1
        assert response_chunks[0].content == "The answer is 42."

    @pytest.mark.asyncio
    async def test_generate_stream_handles_text_only_chunk(self, adapter):
        """Test generate_stream handles chunks without parts."""
        mock_chunk = MagicMock()
        mock_chunk.candidates = None
        mock_chunk.text = "Simple response"
        
        async def mock_stream():
            yield mock_chunk
        
        adapter.client.aio.models.generate_content_stream = AsyncMock(
            return_value=mock_stream()
        )
        
        messages = [{"role": "user", "content": "Hello"}]
        chunks = []
        
        async for chunk in adapter.generate_stream(
            messages=messages,
            model="gemini-2.0-flash",
        ):
            chunks.append(chunk)
        
        # Should have response chunk (not thought) and final
        text_chunks = [c for c in chunks if c.content and not c.is_final]
        assert len(text_chunks) == 1
        assert text_chunks[0].is_thought is False
        assert text_chunks[0].content == "Simple response"

    @pytest.mark.asyncio
    async def test_generate_stream_no_api_key_raises(self):
        """Test generate_stream raises when no API key."""
        with patch('app.services.llm.genai.Client'):
            adapter = GeminiAdapter(api_key="")
        
        adapter.api_key = None  # Force no API key
        
        with pytest.raises(Exception):  # Should raise LLMProviderError
            async for _ in adapter.generate_stream(
                messages=[{"role": "user", "content": "test"}],
                model="gemini-2.0-flash",
            ):
                pass


class TestThinkingConfigParameters:
    """Tests for thinking configuration parameters."""

    def test_thinking_budget_dynamic(self):
        """Test that thinking_budget=-1 enables dynamic thinking."""
        from google.genai import types as genai_types
        
        config = genai_types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=True,
        )
        
        assert config.thinking_budget == -1
        assert config.include_thoughts is True

    def test_thinking_config_include_thoughts_false(self):
        """Test thinking config with include_thoughts=False."""
        from google.genai import types as genai_types
        
        config = genai_types.ThinkingConfig(
            thinking_budget=-1,
            include_thoughts=False,
        )
        
        assert config.thinking_budget == -1
        assert config.include_thoughts is False


class TestModelInfo:
    """Tests for ModelInfo with thinking support."""

    def test_gemini_flash_model_info(self):
        """Test Gemini Flash model info."""
        adapter = GeminiAdapter.__new__(GeminiAdapter)
        models = GeminiAdapter.MODELS
        
        flash_model = next((m for m in models if m.id == "gemini-2.5-flash"), None)
        assert flash_model is not None
        assert flash_model.supports_streaming is True
        assert flash_model.supports_structured is True
        assert flash_model.provider == "gemini"
