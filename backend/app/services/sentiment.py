"""Sentiment Analysis Service with multiple strategies.

Supports three sentiment analysis approaches:
1. nlp_api - Google Cloud Natural Language API
2. llm_separate - Dedicated LLM call for sentiment
3. structured - Combined response + sentiment from LLM

Also supports incremental cumulative sentiment with rolling summary.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from google.genai import types as genai_types
from google.cloud import language_v1
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.llm import LLMService, get_llm_service

logger = get_logger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    
    score: float  # -1.0 to 1.0
    label: str  # 'Positive', 'Negative', 'Neutral'
    source: str  # Method used for analysis
    emotion: str | None = None
    summary: str | None = None  # Cumulative sentiment summary for incremental analysis
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "score": round(self.score, 4),
            "label": self.label,
            "emotion": self.emotion,
            "source": self.source,
        }
        if self.summary:
            result["summary"] = self.summary
        if self.details:
            result["details"] = self.details
        return result

    @staticmethod
    def score_to_label(score: float) -> str:
        """Convert numeric score to categorical label."""
        if score > 0.1:
            return "Positive"
        elif score < -0.1:
            return "Negative"
        return "Neutral"

    @staticmethod
    def neutral() -> "SentimentResult":
        """Create a neutral sentiment result."""
        return SentimentResult(
            score=0.0,
            label="Neutral",
            source="default",
            emotion="neutral",
        )


@dataclass
class CumulativeState:
    """State for incremental cumulative sentiment tracking."""
    summary: str = ""
    score: float = 0.0
    count: int = 0
    label: str = "Neutral"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "score": round(self.score, 4),
            "count": self.count,
            "label": self.label,
        }
    
    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "CumulativeState":
        if not data:
            return CumulativeState()
        return CumulativeState(
            summary=data.get("summary", ""),
            score=data.get("score", 0.0),
            count=data.get("count", 0),
            label=data.get("label", "Neutral"),
        )


class SentimentAnalysisSchema(BaseModel):
    """Schema for LLM sentiment analysis response."""
    
    score: float
    label: str
    emotion: str


class IncrementalSentimentSchema(BaseModel):
    """Schema for incremental cumulative sentiment update."""
    
    score: float
    label: str
    summary: str  # Updated summary incorporating new message


class SentimentStrategy(ABC):
    """Abstract base class for sentiment analysis strategies."""

    strategy_name: str = "base"

    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult:
        """Analyze the sentiment of the given text."""
        ...


class IncrementalSentimentAnalyzer:
    """Analyzer for incremental cumulative sentiment with rolling summary.
    
    Instead of re-analyzing all messages, this maintains a running summary
    that gets updated with each new message - O(1) per message.
    """
    
    INCREMENTAL_PROMPT = '''You are a sentiment analyst tracking conversation sentiment over time.

Given the previous conversation summary and a new user message, produce:
1. An updated summary (max 100 chars) capturing the overall emotional trajectory
2. A sentiment score from -1.0 (very negative) to 1.0 (very positive)
3. A label: "Positive", "Negative", or "Neutral"

Previous summary: {previous_summary}
Previous score: {previous_score}
Message count: {message_count}

New message to incorporate:
{new_message}

Respond with ONLY valid JSON:
{{"score": 0.5, "label": "Positive", "summary": "Brief emotional summary"}}'''

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()
    
    async def update(
        self,
        new_message: str,
        current_state: CumulativeState,
        message_sentiment: SentimentResult | None,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash-lite",
    ) -> tuple[SentimentResult, CumulativeState]:
        """Update cumulative sentiment with a new message.
        
        Returns updated SentimentResult and new CumulativeState.
        """
        # Only Gemini supports the incremental JSON API used below.
        # For other providers (e.g., OpenAI), fall back to local aggregation.
        if provider != "gemini":
            # If we have the per-message sentiment, use weighted average.
            if message_sentiment:
                old_weight = current_state.count
                new_weight = 1
                total = old_weight + new_weight
                new_score = (current_state.score * old_weight + message_sentiment.score * new_weight) / total
                new_label = SentimentResult.score_to_label(new_score)
                
                new_state = CumulativeState(
                    summary=current_state.summary,  # Keep old summary
                    score=new_score,
                    count=current_state.count + 1,
                    label=new_label,
                )
                result = SentimentResult(
                    score=new_score,
                    label=new_label,
                    summary=current_state.summary,
                    source="incremental_fallback",
                )
                return result, new_state
            
            # No per-message sentiment: just advance the count to keep state in sync.
            advanced_state = CumulativeState(
                summary=current_state.summary,
                score=current_state.score,
                count=current_state.count + 1,
                label=current_state.label,
            )
            return SentimentResult(
                score=current_state.score,
                label=current_state.label,
                summary=current_state.summary,
                source="incremental_unchanged",
            ), advanced_state

        # First message - use the message sentiment directly
        if current_state.count == 0 and message_sentiment:
            new_state = CumulativeState(
                summary=f"User is {message_sentiment.emotion or message_sentiment.label.lower()}",
                score=message_sentiment.score,
                count=1,
                label=message_sentiment.label,
            )
            result = SentimentResult(
                score=message_sentiment.score,
                label=message_sentiment.label,
                emotion=message_sentiment.emotion,
                summary=new_state.summary,
                source="incremental",
            )
            return result, new_state
        
        # Subsequent messages - use LLM to update summary
        prompt = self.INCREMENTAL_PROMPT.format(
            previous_summary=current_state.summary or "No previous context",
            previous_score=current_state.score,
            message_count=current_state.count,
            new_message=new_message[:1000],  # Limit message length
        )
        
        try:
            adapter = self.llm_service.get_adapter(provider)
            contents = [
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=prompt)],
                )
            ]
            config = genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=IncrementalSentimentSchema,
                temperature=0.1,
                thinking_config=genai_types.ThinkingConfig(
                    thinking_budget=-1,  # Dynamic thinking budget
                ),
            )
            
            response = await adapter.client.aio.models.generate_content(  # type: ignore[attr-defined]
                model=model,
                contents=contents,
                config=config,
            )
            
            if response.text:
                data = json.loads(response.text)
                score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
                label = data.get("label", SentimentResult.score_to_label(score))
                summary = data.get("summary", "")[:100]  # Cap summary length
                
                new_state = CumulativeState(
                    summary=summary,
                    score=score,
                    count=current_state.count + 1,
                    label=label,
                )
                result = SentimentResult(
                    score=score,
                    label=label,
                    summary=summary,
                    source="incremental",
                    details={"provider": provider, "model": model},
                )
                return result, new_state
        except Exception as e:
            logger.debug("Incremental sentiment update failed, using weighted average", error=str(e))
        
        # Fallback: weighted average if LLM fails
        if message_sentiment:
            old_weight = current_state.count
            new_weight = 1
            total = old_weight + new_weight
            new_score = (current_state.score * old_weight + message_sentiment.score * new_weight) / total
            new_label = SentimentResult.score_to_label(new_score)
            
            new_state = CumulativeState(
                summary=current_state.summary,  # Keep old summary
                score=new_score,
                count=current_state.count + 1,
                label=new_label,
            )
            result = SentimentResult(
                score=new_score,
                label=new_label,
                summary=current_state.summary,
                source="incremental_fallback",
            )
            return result, new_state
        
        # No sentiment available - return current state
        unchanged_state = CumulativeState(
            summary=current_state.summary,
            score=current_state.score,
            count=current_state.count + 1,
            label=current_state.label,
        )
        return SentimentResult(
            score=current_state.score,
            label=current_state.label,
            summary=current_state.summary,
            source="incremental_unchanged",
        ), unchanged_state


class GoogleCloudNLPStrategy(SentimentStrategy):
    """Sentiment analysis using Google Cloud Natural Language API.
    
    Lazily initializes the client on first use to avoid blocking startup.
    Uses thread pool for non-blocking API calls.
    """

    strategy_name = "nlp_api"

    def __init__(self) -> None:
        # Lazy initialization - don't create client until first use
        self._client: language_v1.LanguageServiceClient | None = None
        self._available: bool | None = None  # None = not checked yet
        self._init_lock = asyncio.Lock()

    async def _ensure_client(self) -> bool:
        """Lazily initialize the client in a non-blocking way.
        
        Returns True if client is available and ready.
        """
        if self._available is not None:
            return self._available
        
        async with self._init_lock:
            # Double-check after acquiring lock
            if self._available is not None:
                return self._available
            
            # Initialize in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                self._client = await loop.run_in_executor(
                    None,
                    language_v1.LanguageServiceClient,
                )
                self._available = True
                logger.info("Google Cloud NLP client initialized (lazy)")
            except Exception as e:
                logger.warning("Google Cloud NLP not available", error=str(e))
                self._available = False
        
        return self._available

    @property
    def is_available(self) -> bool:
        # For sync check, assume not available until initialized
        return self._available is True

    async def analyze(self, text: str) -> SentimentResult:
        if not await self._ensure_client():
            return SentimentResult(
                score=0.0,
                label="Neutral",
                source=self.strategy_name,
                emotion="neutral",
                details={"error": "Google Cloud NLP not configured"},
            )

        try:
            document = language_v1.Document(
                content=text,
                type_=language_v1.Document.Type.PLAIN_TEXT,
            )
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.analyze_sentiment(request={"document": document}),  # type: ignore
            )

            sentiment = response.document_sentiment
            return SentimentResult(
                score=sentiment.score,
                label=SentimentResult.score_to_label(sentiment.score),
                source=self.strategy_name,
                emotion=None,  # NLP API doesn't provide emotion labels
                details={
                    "magnitude": round(sentiment.magnitude, 4),
                    "service": "Google Cloud Natural Language API",
                },
            )
        except Exception as e:
            logger.error("Google Cloud NLP analysis failed", error=str(e))
            return SentimentResult(
                score=0.0,
                label="Neutral",
                source=self.strategy_name,
                details={"error": str(e)},
            )


class LLMSeparateStrategy(SentimentStrategy):
    """Sentiment analysis using a dedicated LLM call.
    
    Reuses the Gemini client from the LLM adapter to avoid
    creating multiple client instances (which causes 'AFC is enabled' spam).
    """

    strategy_name = "llm_separate"

    SYSTEM_PROMPT = """You are a sentiment analyst. Analyze the emotional tone and sentiment of the user's message.

Respond with ONLY valid JSON in this format:
{"score": 0.5, "label": "Positive", "emotion": "happy and engaged"}

Where:
- score: float from -1.0 (very negative) to 1.0 (very positive), 0 is neutral
- label: exactly one of "Positive", "Negative", "Neutral"
- emotion: 1-5 word description of the dominant emotion"""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash",
    ) -> None:
        self.llm_service = llm_service or get_llm_service()
        self.provider = provider
        self.model = model

    async def analyze(self, text: str) -> SentimentResult:
        # Reuse the adapter's Gemini client instead of creating a new one
        # This avoids 'AFC is enabled' message spam from multiple client instantiations
        if self.provider == "gemini":
            try:
                adapter = self.llm_service.get_adapter("gemini")
                contents = [
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part.from_text(text=f"Analyze the sentiment of this text:\n\n{text}")],
                    )
                ]
                config = genai_types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=SentimentAnalysisSchema,
                    temperature=0.1,
                    thinking_config=genai_types.ThinkingConfig(
                        thinking_budget=-1,  # Dynamic thinking budget
                    ),
                )
                
                # Use the adapter's existing client
                response = await adapter.client.aio.models.generate_content(  # type: ignore[attr-defined]
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                
                if response.text:
                    data = json.loads(response.text)
                    score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
                    return SentimentResult(
                        score=score,
                        label=data.get("label", SentimentResult.score_to_label(score)),
                        emotion=data.get("emotion", "neutral"),
                        source=self.strategy_name,
                        details={"provider": self.provider, "model": self.model},
                    )
            except Exception as e:
                logger.warning("Gemini sentiment analysis failed", error=str(e))

        # Fallback: use streaming with JSON parsing
        try:
            adapter = self.llm_service.get_adapter(self.provider)
            full_response = ""
            
            async for chunk in adapter.generate_stream(
                messages=[{"role": "user", "content": f"Analyze sentiment:\n\n{text}"}],
                model=self.model,
                system_prompt=self.SYSTEM_PROMPT + "\n\nRespond with ONLY valid JSON.",
                temperature=0.1,
                max_tokens=150,
            ):
                full_response += chunk.content

            # Parse JSON response
            content = full_response.strip()
            if "```" in content:
                content = content.split("```")[1].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            
            data = json.loads(content)
            score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
            
            return SentimentResult(
                score=score,
                label=data.get("label", SentimentResult.score_to_label(score)),
                emotion=data.get("emotion", "neutral"),
                source=self.strategy_name,
                details={"provider": self.provider, "model": self.model},
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse LLM sentiment response", error=str(e))
            return SentimentResult(
                score=0.0,
                label="Neutral",
                emotion="neutral",
                source=self.strategy_name,
                details={"provider": self.provider, "model": self.model, "error": str(e)},
            )
        except Exception as e:
            logger.error("LLM sentiment analysis failed", error=str(e))
            return SentimentResult.neutral()


class StructuredOutputStrategy(SentimentStrategy):
    """Sentiment analysis integrated with response generation.
    
    This strategy is handled in the chat orchestrator.
    For standalone analysis, it falls back to Cloud NLP.
    """

    strategy_name = "structured"

    def __init__(self, cloud_nlp: GoogleCloudNLPStrategy | None = None) -> None:
        # Share the Cloud NLP instance instead of creating a new one
        self._cloud_nlp = cloud_nlp

    async def analyze(self, text: str) -> SentimentResult:
        # For standalone analysis, use Cloud NLP as fallback
        if self._cloud_nlp is None:
            return SentimentResult.neutral()
        result = await self._cloud_nlp.analyze(text)
        result.source = self.strategy_name
        return result


class SentimentService:
    """Service to manage sentiment analysis strategies.
    
    Uses singleton pattern for provider-agnostic strategies (nlp_api, structured)
    and caches provider-specific strategies (llm_separate) by provider:model.
    Also provides incremental cumulative sentiment analysis.
    """

    AVAILABLE_METHODS = ["nlp_api", "llm_separate", "structured"]

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()
        self._strategies: dict[str, SentimentStrategy] = {}
        
        # Create shared singleton instances for provider-agnostic strategies
        self._cloud_nlp = GoogleCloudNLPStrategy()
        self._structured = StructuredOutputStrategy(self._cloud_nlp)
        self._incremental = IncrementalSentimentAnalyzer(self.llm_service)

    def get_strategy(
        self,
        method: str,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash-lite",
    ) -> SentimentStrategy:
        """Get or create a sentiment strategy instance.
        
        Provider-agnostic strategies (nlp_api, structured) are singletons.
        Provider-specific strategies (llm_separate) are cached by provider:model.
        """
        # Return singleton for provider-agnostic strategies
        if method == "nlp_api":
            return self._cloud_nlp
        elif method == "structured":
            return self._structured
        
        # Cache provider-specific strategies
        cache_key = f"{method}:{provider}:{model}"
        
        if cache_key not in self._strategies:
            if method == "llm_separate":
                self._strategies[cache_key] = LLMSeparateStrategy(
                    self.llm_service, provider, model
                )
            else:
                raise ValueError(f"Unknown sentiment method: {method}")
        
        return self._strategies[cache_key]

    async def analyze(
        self,
        text: str,
        method: str = "llm_separate",
        provider: str = "gemini",
        model: str = "gemini-2.5-flash-lite",
    ) -> SentimentResult:
        """Analyze sentiment using the specified method."""
        strategy = self.get_strategy(method, provider, model)
        return await strategy.analyze(text)

    async def update_cumulative(
        self,
        new_message: str,
        current_state: CumulativeState,
        message_sentiment: SentimentResult | None,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash-lite",
    ) -> tuple[SentimentResult, CumulativeState]:
        """Update cumulative sentiment incrementally with a new message.
        
        Returns (SentimentResult for cumulative, new CumulativeState).
        """
        return await self._incremental.update(
            new_message, current_state, message_sentiment, provider, model
        )

    def get_available_methods(self) -> list[str]:
        """Get list of available sentiment analysis methods."""
        return self.AVAILABLE_METHODS


# Global sentiment service instance
_sentiment_service: SentimentService | None = None


def get_sentiment_service() -> SentimentService:
    """Get or create the global sentiment service instance."""
    global _sentiment_service
    
    if _sentiment_service is None:
        _sentiment_service = SentimentService()
    
    return _sentiment_service
