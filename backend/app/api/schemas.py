"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Authentication Schemas
# ============================================================

class UserCreate(BaseModel):
    """Schema for user registration."""
    
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    """Schema for user login."""
    
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user data in responses."""
    
    id: int
    email: str
    username: str
    created_at: datetime

    class ConfigDict:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiration time in seconds")
    user: UserResponse


# ============================================================
# Sentiment Schemas
# ============================================================

class SentimentData(BaseModel):
    """Schema for sentiment analysis result."""
    
    score: float = Field(..., ge=-1.0, le=1.0)
    label: str = Field(..., pattern=r"^(Positive|Negative|Neutral)$")
    emotion: str | None = None
    source: str | None = None
    details: dict[str, Any] | None = None


class DualSentiment(BaseModel):
    """Schema for message and cumulative sentiment."""
    
    message: SentimentData | None = None
    cumulative: SentimentData | None = None


# ============================================================
# Chat Schemas
# ============================================================

class MessagePart(BaseModel):
    """Schema for AI SDK message part."""
    
    type: str
    text: str | None = None


class UIMessage(BaseModel):
    """Schema for AI SDK UI message format."""
    
    id: str
    role: str
    parts: list[MessagePart]


class ModelSettings(BaseModel):
    """Schema for model generation settings."""
    
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Controls randomness (0=deterministic, 2=very random)")
    max_tokens: int = Field(default=2048, ge=1, le=32000, description="Maximum tokens in response")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling threshold")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Penalize repeated tokens")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Penalize tokens already present")


class ChatRequest(BaseModel):
    """Schema for chat request supporting multiple formats."""
    
    # Legacy format
    message: str | None = Field(default=None, min_length=1, max_length=10000)
    
    # AI SDK format
    messages: list[UIMessage] | None = None
    
    # Common fields
    conversation_id: str | None = None
    provider: str = Field(default="gemini", pattern=r"^(gemini|openai)$")
    model: str = Field(default="gemini-2.5-flash")
    sentiment_method: str = Field(
        default="llm_separate",
        pattern=r"^(nlp_api|llm_separate|structured)$",
    )
    
    # Model settings
    model_settings: ModelSettings | None = None
    
    # AI SDK extras (accepted but ignored)
    id: str | None = None
    trigger: str | None = None

    def get_user_message(self) -> str:
        """Extract the user message from either format."""
        if self.message:
            return self.message
        
        if self.messages:
            # Get the last user message from the messages array
            for msg in reversed(self.messages):
                if msg.role == "user":
                    return " ".join(
                        part.text for part in msg.parts
                        if part.type == "text" and part.text
                    )
        
        raise ValueError("No message content provided")


# ============================================================
# Message & Conversation Schemas
# ============================================================

class MessageResponse(BaseModel):
    """Schema for message in responses."""
    
    id: int
    role: str
    content: str
    sentiment_data: dict[str, Any] | None = None
    model_info: dict[str, Any] | None = None
    created_at: datetime

    class ConfigDict:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Schema for conversation summary in list."""
    
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int

    class ConfigDict:
        from_attributes = True


class ConversationDetail(BaseModel):
    """Schema for full conversation with messages."""
    
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    total_messages: int
    limit: int
    offset: int
    has_more: bool
    messages: list[MessageResponse]

    class ConfigDict:
        from_attributes = True


class ConversationRename(BaseModel):
    """Schema for renaming a conversation."""
    
    title: str = Field(..., min_length=1, max_length=255)


# ============================================================
# Common Response Schemas
# ============================================================

class SuccessResponse(BaseModel):
    """Schema for generic success response."""
    
    success: bool = True
    message: str


class DeleteResponse(BaseModel):
    """Schema for delete operation response."""
    
    success: bool = True
    message: str
    deleted_count: int | None = None


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    
    error: dict[str, Any] = Field(
        ...,
        json_schema_extra={"example": {"message": "Error description", "details": {}}},
    )


# ============================================================
# Health Check Schemas
# ============================================================

class CreatorInfo(BaseModel):
    """Schema for creator/author information."""
    
    name: str
    github: str
    linkedin: str
    email: str


class ServiceHealth(BaseModel):
    """Schema for individual service health."""
    
    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    latency_ms: float | None = None
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Schema for health check response."""
    
    created_by: CreatorInfo
    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    timestamp: datetime
    version: str
    services: dict[str, ServiceHealth]

