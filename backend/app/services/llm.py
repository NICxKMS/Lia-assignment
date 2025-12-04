"""LLM Provider Adapters with unified streaming interface.

Supports multiple LLM providers with a common interface:
- Google Gemini (default)
- OpenAI
- Extensible for future providers
"""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response."""
    
    content: str
    is_final: bool = False
    model: str = ""
    provider: str = ""
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


@dataclass
class StructuredStreamChunk(StreamChunk):
    """A chunk from structured streaming with optional sentiment data."""
    
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    sentiment_emotion: str | None = None


@dataclass
class ModelInfo:
    """Information about an LLM model."""
    
    id: str
    name: str
    provider: str
    context_window: int = 0
    supports_streaming: bool = True
    supports_structured: bool = False


class ChatWithSentiment(BaseModel):
    """Schema for structured chat response with sentiment."""
    
    response: str
    sentiment_score: float
    sentiment_label: str
    sentiment_emotion: str


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    provider_name: str = "base"

    @abstractmethod
    def generate_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response from the LLM."""
        ...

    @abstractmethod
    def generate_structured_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StructuredStreamChunk]:
        """Generate a structured streaming response with sentiment."""
        ...

    @abstractmethod
    def get_available_models(self) -> list[ModelInfo]:
        """Return list of available models for this provider."""
        ...


def _build_sentiment_system_prompt(
    last_user_message: str,
    base_prompt: str | None = None,
) -> str:
    """Build system prompt for structured sentiment analysis."""
    prompt = f"""You are a helpful AI assistant named Lia.

You have TWO tasks:
1. Write a clear, helpful response to the user's message
2. Analyze the sentiment of the USER'S message (not your response)

The user's message to analyze: "{last_user_message}"

Return ONLY valid JSON in this exact format:
{{"response": "your helpful response here", "sentiment_score": 0.4, "sentiment_label": "Positive", "sentiment_emotion": "curious"}}

Sentiment fields describe the USER's emotion:
- sentiment_score: float from -1.0 (very negative) to 1.0 (very positive)
- sentiment_label: exactly one of "Positive", "Negative", "Neutral"
- sentiment_emotion: 1-5 word description of the user's emotion"""
    
    return f"{base_prompt}\n\n{prompt}" if base_prompt else prompt


def _extract_incremental_content(
    full_json: str,
    last_content: str,
) -> tuple[str, str]:
    """Extract incremental content from partial JSON response field."""
    if '"response"' not in full_json:
        return "", last_content

    try:
        start = full_json.find('"response"')
        colon_pos = full_json.find(":", start)
        if colon_pos == -1:
            return "", last_content

        quote_start = full_json.find('"', colon_pos + 1)
        if quote_start == -1:
            return "", last_content

        # Extract content handling escape sequences
        content = ""
        i = quote_start + 1
        while i < len(full_json):
            if full_json[i] == "\\" and i + 1 < len(full_json):
                content += full_json[i : i + 2]
                i += 2
            elif full_json[i] == '"':
                break
            else:
                content += full_json[i]
                i += 1

        # Unescape content
        try:
            content = json.loads(f'"{content}"')
        except json.JSONDecodeError:
            pass

        if len(content) > len(last_content):
            return content[len(last_content):], content
    except Exception:
        pass
    
    return "", last_content


class GeminiAdapter(LLMAdapter):
    """Adapter for Google Gemini models."""

    provider_name = "gemini"
    
    MODELS = [
        ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini", 1000000, True, True),
        ModelInfo("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", "gemini", 1000000, True, True),
        ModelInfo("gemini-1.5-pro", "Gemini 1.5 Pro", "gemini", 2000000, True, True),
        ModelInfo("gemini-1.5-flash", "Gemini 1.5 Flash", "gemini", 1000000, True, True),
    ]

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        
        if not self.api_key:
            logger.warning("Gemini API key not configured")
        
        self.client = genai.Client(api_key=self.api_key)

    def get_available_models(self) -> list[ModelInfo]:
        return self.MODELS

    def _to_contents(
        self,
        messages: list[dict[str, str]],
    ) -> list[genai_types.Content]:
        """Convert chat messages to Gemini content format."""
        return [
            genai_types.Content(
                role="model" if msg["role"] == "assistant" else "user",
                parts=[genai_types.Part.from_text(text=msg["content"])],
            )
            for msg in messages
        ]

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamChunk]:
        if not self.api_key:
            raise LLMProviderError("gemini", "API key not configured")

        try:
            config = genai_types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt,
            )

            stream = await self.client.aio.models.generate_content_stream(
                model=model,
                contents=self._to_contents(messages),
                config=config,
            )

            async for chunk in stream:
                if chunk.text:
                    yield StreamChunk(
                        content=chunk.text,
                        model=model,
                        provider=self.provider_name,
                    )

            yield StreamChunk(
                content="",
                is_final=True,
                model=model,
                provider=self.provider_name,
                finish_reason="stop",
            )
        except Exception as e:
            logger.error("Gemini streaming error", error=str(e), model=model)
            raise LLMProviderError("gemini", str(e))

    async def generate_structured_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StructuredStreamChunk]:
        if not self.api_key:
            raise LLMProviderError("gemini", "API key not configured")

        try:
            last_user_message = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"),
                "",
            )

            config = genai_types.GenerateContentConfig(
                system_instruction=_build_sentiment_system_prompt(
                    last_user_message, system_prompt
                ),
                response_mime_type="application/json",
                response_schema=ChatWithSentiment,
            )

            stream = await self.client.aio.models.generate_content_stream(
                model=model,
                contents=self._to_contents(messages),
                config=config,
            )

            full_json = ""
            last_content = ""

            async for chunk in stream:
                if chunk.text:
                    full_json += chunk.text
                    new_content, last_content = _extract_incremental_content(
                        full_json, last_content
                    )
                    if new_content:
                        yield StructuredStreamChunk(
                            content=new_content,
                            model=model,
                            provider=self.provider_name,
                        )

            # Parse final JSON for sentiment
            sentiment_score, sentiment_label, sentiment_emotion = 0.0, "Neutral", "neutral"
            try:
                data = json.loads(full_json)
                sentiment_score = float(data.get("sentiment_score", 0.0))
                sentiment_label = data.get("sentiment_label", "Neutral")
                sentiment_emotion = data.get("sentiment_emotion", "neutral")
                
                final_content = data.get("response", "")
                if len(final_content) > len(last_content):
                    yield StructuredStreamChunk(
                        content=final_content[len(last_content):],
                        model=model,
                        provider=self.provider_name,
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse structured response JSON")

            yield StructuredStreamChunk(
                content="",
                is_final=True,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                sentiment_emotion=sentiment_emotion,
                model=model,
                provider=self.provider_name,
                finish_reason="stop",
            )
        except LLMProviderError:
            raise
        except Exception as e:
            logger.error("Gemini structured streaming error", error=str(e), model=model)
            raise LLMProviderError("gemini", str(e))


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI models."""

    provider_name = "openai"
    
    MODELS = [
        ModelInfo("gpt-4o", "GPT-4o", "openai", 128000, True, True),
        ModelInfo("gpt-4o-mini", "GPT-4o Mini", "openai", 128000, True, True),
        ModelInfo("gpt-4-turbo", "GPT-4 Turbo", "openai", 128000, True, True),
        ModelInfo("gpt-3.5-turbo", "GPT-3.5 Turbo", "openai", 16385, True, True),
    ]

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
        
        self.client = AsyncOpenAI(api_key=self.api_key)

    def get_available_models(self) -> list[ModelInfo]:
        return self.MODELS

    def _to_messages(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> list[ChatCompletionMessageParam]:
        """Convert messages to OpenAI format."""
        result: list[ChatCompletionMessageParam] = []
        
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        
        for msg in messages:
            result.append({
                "role": msg["role"],  # type: ignore
                "content": msg["content"],
            })
        
        return result

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamChunk]:
        if not self.api_key:
            raise LLMProviderError("openai", "API key not configured")

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=self._to_messages(messages, system_prompt),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(
                        content=chunk.choices[0].delta.content,
                        model=model,
                        provider=self.provider_name,
                    )

            yield StreamChunk(
                content="",
                is_final=True,
                model=model,
                provider=self.provider_name,
                finish_reason="stop",
            )
        except Exception as e:
            logger.error("OpenAI streaming error", error=str(e), model=model)
            raise LLMProviderError("openai", str(e))

    async def generate_structured_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StructuredStreamChunk]:
        if not self.api_key:
            raise LLMProviderError("openai", "API key not configured")

        try:
            last_user_message = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"),
                "",
            )

            stream = await self.client.chat.completions.create(
                model=model,
                messages=self._to_messages(
                    messages,
                    _build_sentiment_system_prompt(last_user_message, system_prompt),
                ),
                response_format={"type": "json_object"},
                temperature=0.7,
                stream=True,
            )

            full_json = ""
            last_content = ""

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_json += chunk.choices[0].delta.content
                    new_content, last_content = _extract_incremental_content(
                        full_json, last_content
                    )
                    if new_content:
                        yield StructuredStreamChunk(
                            content=new_content,
                            model=model,
                            provider=self.provider_name,
                        )

            # Parse final JSON for sentiment
            sentiment_score, sentiment_label, sentiment_emotion = 0.0, "Neutral", "neutral"
            try:
                data = json.loads(full_json)
                sentiment_score = float(data.get("sentiment_score", 0.0))
                sentiment_label = data.get("sentiment_label", "Neutral")
                sentiment_emotion = data.get("sentiment_emotion", "neutral")
                
                final_content = data.get("response", "")
                if len(final_content) > len(last_content):
                    yield StructuredStreamChunk(
                        content=final_content[len(last_content):],
                        model=model,
                        provider=self.provider_name,
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse structured response JSON")

            yield StructuredStreamChunk(
                content="",
                is_final=True,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                sentiment_emotion=sentiment_emotion,
                model=model,
                provider=self.provider_name,
                finish_reason="stop",
            )
        except LLMProviderError:
            raise
        except Exception as e:
            logger.error("OpenAI structured streaming error", error=str(e), model=model)
            raise LLMProviderError("openai", str(e))


class LLMService:
    """Service class to manage LLM adapters.
    
    Supports pre-warming adapters on startup to eliminate
    first-request latency for adapter initialization.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, LLMAdapter] = {}

    def get_adapter(self, provider: str) -> LLMAdapter:
        """Get or create an adapter for the specified provider."""
        if provider not in self._adapters:
            if provider == "gemini":
                self._adapters[provider] = GeminiAdapter()
            elif provider == "openai":
                self._adapters[provider] = OpenAIAdapter()
            else:
                raise ValueError(f"Unknown LLM provider: {provider}")
        
        return self._adapters[provider]

    def prewarm_adapters(self) -> None:
        """Pre-initialize adapters to avoid first-request latency.
        
        Call during application startup to warm up adapter instances.
        """
        settings = get_settings()
        
        # Pre-warm Gemini adapter if configured
        if settings.gemini_api_key:
            try:
                self.get_adapter("gemini")
                logger.info("Pre-warmed Gemini adapter")
            except Exception as e:
                logger.warning("Failed to pre-warm Gemini adapter", error=str(e))
        
        # Pre-warm OpenAI adapter if configured
        if settings.openai_api_key:
            try:
                self.get_adapter("openai")
                logger.info("Pre-warmed OpenAI adapter")
            except Exception as e:
                logger.warning("Failed to pre-warm OpenAI adapter", error=str(e))

    def get_all_models(self) -> dict[str, list[dict[str, Any]]]:
        """Get all available models grouped by provider."""
        return {
            "gemini": [
                {"id": m.id, "name": m.name, "context_window": m.context_window}
                for m in GeminiAdapter.MODELS
            ],
            "openai": [
                {"id": m.id, "name": m.name, "context_window": m.context_window}
                for m in OpenAIAdapter.MODELS
            ],
        }

    def get_providers(self) -> list[str]:
        """Get list of available providers."""
        return ["gemini", "openai"]


# Global LLM service instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create the global LLM service instance."""
    global _llm_service
    
    if _llm_service is None:
        _llm_service = LLMService()
    
    return _llm_service
