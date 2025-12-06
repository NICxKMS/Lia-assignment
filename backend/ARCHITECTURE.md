# Lia Backend - Architecture Document

**Author: Nikhil Kumar**

> Detailed architectural documentation for the FastAPI backend service

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [System Architecture](#3-system-architecture)
4. [Component Details](#4-component-details)
5. [Data Flow](#5-data-flow)
6. [Security Architecture](#6-security-architecture)
7. [Caching Strategy](#7-caching-strategy)
8. [Observability](#8-observability)
9. [Scalability](#9-scalability)

---

## 1. Overview

The Lia Backend is a fully asynchronous Python application built with FastAPI, designed for high-performance AI chatbot operations with real-time streaming and sentiment analysis.

### Key Characteristics

| Aspect | Implementation |
|--------|---------------|
| **Runtime** | Python 3.11+ with async/await |
| **Framework** | FastAPI with Pydantic v2 |
| **Database** | PostgreSQL via SQLAlchemy 2.0 Async |
| **Cache** | Upstash Redis (REST API) |
| **LLM Providers** | Google Gemini, OpenAI |
| **Authentication** | JWT with async bcrypt |
| **Package Manager** | uv (fast Python package manager) |

---

## 2. Architecture Principles

### 2.1 Core Principles

1. **Fully Asynchronous**: All I/O operations are non-blocking using `async/await`
2. **Clean Separation**: API → Service → Data layer separation
3. **Fail-Safe Design**: Graceful degradation when external services are unavailable
4. **Observable**: Structured logging with request correlation
5. **Horizontally Scalable**: Stateless design for multi-instance deployment
6. **Testable**: Dependency injection for easy mocking

### 2.2 Design Decisions

| Decision | Rationale |
|----------|-----------|
| Async SQLAlchemy | Non-blocking database operations for high concurrency |
| Upstash Redis REST | Serverless-compatible, no persistent connections needed |
| Adapter Pattern for LLMs | Easy addition of new providers (Claude, Llama, etc.) |
| Strategy Pattern for Sentiment | Swappable analysis methods at runtime |
| SSE over WebSocket | Simpler implementation, better HTTP/2 compatibility |

---

## 3. System Architecture

### 3.1 Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         MIDDLEWARE                               │
│  CORS │ Request Logging │ Error Handling │ Rate Limiting        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                          API LAYER                               │
│                                                                  │
│  /api/v1/auth/*              Authentication endpoints           │
│  /api/v1/chat/*              Chat & conversation endpoints      │
│  /health/*                   Health monitoring                  │
│                                                                  │
│  Dependencies: JWT Validation │ Rate Limiting │ DB Sessions     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                        SERVICE LAYER                             │
│                                                                  │
│  ChatOrchestrator           Central coordinator                  │
│  ├── Conversation management                                     │
│  ├── Context loading/caching                                     │
│  └── SSE stream coordination                                     │
│                                                                  │
│  LLMService                 Multi-provider abstraction           │
│  ├── GeminiAdapter                                               │
│  └── OpenAIAdapter                                               │
│                                                                  │
│  SentimentService           Strategy-based analysis              │
│  ├── StructuredStrategy                                          │
│  ├── LLMSeparateStrategy                                         │
│  └── NLPAPIStrategy                                              │
│                                                                  │
│  CacheService               Redis operations                     │
│  └── Context caching, history caching                            │
│                                                                  │
│  RateLimitService           Request throttling                   │
│  └── Token bucket via Redis                                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                       INFRASTRUCTURE                             │
│                                                                  │
│  PostgreSQL (Neon)          Users, Conversations, Messages       │
│  Redis (Upstash)            Cache, Rate Limits                   │
│  External APIs              Gemini, OpenAI, Cloud NLP            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Module Dependencies

```
main.py
    │
    ├── api/routes/auth.py
    │       └── core/security.py
    │       └── db/models.py
    │
    ├── api/routes/chat.py
    │       └── services/chat.py (ChatOrchestrator)
    │               ├── services/llm.py (LLMService)
    │               ├── services/sentiment.py (SentimentService)
    │               ├── services/cache/ (CacheService)
    │               └── db/models.py
    │
    ├── api/routes/health.py
    │       └── services/cache/ (CacheService)
    │       └── db/session.py
    │
    └── core/
            ├── config.py (Settings)
            ├── logging.py (structlog)
            └── exceptions.py (handlers)
```

---

## 4. Component Details

### 4.1 API Layer

#### Routes

| File | Endpoints | Description |
|------|-----------|-------------|
| `auth.py` | `/register`, `/login`, `/me` | User authentication |
| `chat.py` | `/stream`, `/history`, `/conversation/*`, `/models`, `/methods` | Chat operations |
| `health.py` | `/`, `/health`, `/health/*` | Health monitoring (7 endpoints) |

#### Dependencies (`deps.py`)

| Dependency | Purpose |
|------------|---------|
| `get_db` | Async database session |
| `get_current_user` | JWT token validation |
| `get_rate_limiter` | Rate limit checking |

#### Schemas (`schemas.py`)

```python
# Request Models
ChatRequest(message, provider, model, sentiment_method, conversation_id)
RegisterRequest(email, username, password)
LoginRequest(email, password)

# Response Models
ChatStartEvent(conversation_id, message_id)
ChatChunkEvent(content)
SentimentEvent(message, cumulative)
TokenResponse(access_token, token_type, expires_in, user)
```

### 4.2 Service Layer

#### ChatOrchestrator (`services/chat.py`)

The central coordinator for all chat operations:

```python
class ChatOrchestrator:
    async def process_chat_stream(request, user_id, db) -> AsyncGenerator[str, None]
    async def get_conversation_history(user_id, db, limit) -> list[dict]
    async def get_conversation_detail(user_id, conversation_id, db) -> dict | None
    async def delete_conversation(user_id, conversation_id, db) -> bool
    async def delete_all_conversations(user_id, db) -> int
    async def rename_conversation(user_id, conversation_id, title, db) -> bool
```

**Flow:**
1. Get or create conversation
2. Load context from cache (fallback to DB)
3. Save user message
4. Stream LLM response via SSE
5. Analyze sentiment (parallel or post-stream)
6. Save assistant message with sentiment
7. Update cache

#### LLMService (`services/llm.py`)

Unified interface for multiple LLM providers:

```python
class LLMService:
    def get_adapter(provider: str) -> LLMAdapter
    def get_all_models() -> dict[str, list[ModelInfo]]
    def prewarm_adapters() -> None

class LLMAdapter(Protocol):
    async def generate_stream(messages, model, system_prompt) -> AsyncGenerator
    async def generate_structured_stream(messages, model, system_prompt) -> AsyncGenerator
```

**Adapters:**
- `GeminiAdapter`: Google Gemini models via `google-genai`
- `OpenAIAdapter`: OpenAI models via `openai` SDK

#### SentimentService (`services/sentiment.py`)

Strategy-based sentiment analysis:

```python
class SentimentService:
    async def analyze(text, method, llm_service) -> SentimentResult
    def get_available_methods() -> list[MethodInfo]

@dataclass
class SentimentResult:
    score: float      # -1.0 to 1.0
    label: str        # "Positive", "Negative", "Neutral"
    emotion: str      # "happy", "sad", "angry", etc.
    confidence: float
```

**Strategies:**
- `structured`: Parse sentiment from LLM structured output
- `llm_separate`: Dedicated LLM call for sentiment
- `nlp_api`: Google Cloud Natural Language API

#### CacheService (`services/cache/`)

Redis caching via Upstash REST API, organized into a modular package:

```
services/cache/
├── __init__.py           # Public exports
├── base.py               # Base cache operations
├── constants.py          # Key patterns and TTLs
├── conversation.py       # Conversation-specific caching
├── history.py            # User history caching
├── models.py             # Static model/method caching
└── user.py               # User data caching
```

```python
class CacheService(BaseCacheService):
    # Conversation context (1 hour TTL)
    async def get_conversation_context(conversation_id) -> list[dict] | None
    async def set_conversation_context(conversation_id, messages) -> bool
    async def append_to_context(conversation_id, message) -> bool
    
    # User messages for cumulative sentiment (2 min TTL)
    async def get_user_messages(conversation_id) -> list[str] | None
    async def set_user_messages(conversation_id, messages) -> bool
    async def append_user_message(conversation_id, message) -> bool
    
    # History caching using sorted sets (5 min TTL)
    async def get_user_history(user_id) -> list[dict] | None
    async def add_to_history(user_id, conversation) -> bool
    async def invalidate_conversation(conversation_id) -> bool
```

### 4.3 Data Layer

#### Models (`db/models.py`)

```python
class User(Base):
    id: int (PK)
    email: str (unique)
    username: str (unique)
    hashed_password: str
    created_at: datetime
    updated_at: datetime

class Conversation(Base):
    id: UUID (PK)
    user_id: int (FK -> users.id)
    title: str | None
    created_at: datetime
    updated_at: datetime

class Message(Base):
    id: int (PK)
    conversation_id: UUID (FK -> conversations.id)
    role: str  # "user" | "assistant"
    content: str
    sentiment_data: dict | None  # JSONB
    model_info: dict | None      # JSONB
    created_at: datetime
```

#### Session Factory (`db/session.py`)

```python
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

**Configuration:**
- `NullPool` for serverless compatibility
- Connection string from `DATABASE_URL`
- Async driver: `asyncpg`

---

## 5. Data Flow

### 5.1 Chat Stream Flow

```
1. Client: POST /api/v1/chat/stream
                    │
2. Middleware: Rate limit check
                    │ (blocked → 429)
                    │
3. Dependency: JWT validation
                    │ (invalid → 401)
                    │
4. Route: Validate request body
                    │ (invalid → 422)
                    │
5. ChatOrchestrator.process_chat_stream()
   │
   ├── Get/create conversation (DB)
   ├── Load context (Cache → DB fallback)
   ├── Auto-generate title if new conversation
   ├── Save user message (DB)
   │
   ├── yield SSE: event: start
   │
   ├── LLM streaming:
   │   ├── yield SSE: event: chunk (per token)
   │   └── Accumulate full response
   │
   ├── Sentiment analysis (async):
   │   ├── Message sentiment (current message)
   │   └── Cumulative sentiment (all user messages)
   │
   ├── Save assistant message with sentiment (DB)
   ├── Update cache (async, fire-and-forget)
   │
   ├── yield SSE: event: sentiment
   └── yield SSE: event: done

6. Response: StreamingResponse (text/event-stream)
```

### 5.2 Authentication Flow

```
Register:
  Client → POST /register → Validate → Hash password → Create user → Generate JWT → Return token

Login:
  Client → POST /login → Find user → Verify password → Generate JWT → Return token

Authenticated Request:
  Client → Request with Bearer token → Validate JWT → Extract user_id → Execute handler
```

---

## 6. Security Architecture

### 6.1 Layers

| Layer | Implementation |
|-------|---------------|
| Transport | HTTPS/TLS (handled by infrastructure) |
| CORS | Configurable allowed origins |
| Authentication | JWT tokens (HS256) |
| Password | Bcrypt hashing (async) |
| Validation | Pydantic v2 schemas |
| Rate Limiting | Per-user token bucket |

### 6.2 JWT Configuration

```python
# Token structure
{
    "sub": "user_id",
    "exp": timestamp,
    "iat": timestamp
}

# Settings
algorithm = "HS256"
expiration = 7 days (configurable)
secret = JWT_SECRET_KEY (min 32 chars)
```

### 6.3 Password Security

- **Algorithm**: Bcrypt via `passlib`
- **Hashing**: Async to prevent blocking
- **Verification**: Constant-time comparison

---

## 7. Caching Strategy

### 7.1 Cache Keys

| Pattern | Data | TTL |
|---------|------|-----|
| `conv:{id}:context` | Message context (last N messages) | 1 hour |
| `conv:{id}:usrmsg` | User messages for cumulative sentiment | 2 minutes |
| `user:{id}:history` | Conversation list (sorted set) | 5 minutes |
| `models:available` | Available LLM models | 24 hours |
| `methods:sentiment` | Available sentiment methods | 24 hours |

### 7.2 Cache Strategy

```
Read:
  1. Check cache
  2. If HIT → return cached data
  3. If MISS → query database → update cache (async) → return data

Write:
  1. Write to database
  2. Update cache (async, fire-and-forget)

Delete:
  1. Delete from database
  2. Invalidate cache
```

### 7.3 Graceful Degradation

Cache operations are wrapped in try/except. If Redis is unavailable:
- Read operations fall back to database
- Write operations proceed without caching
- No user-facing errors

---

## 8. Observability

### 8.1 Structured Logging

Using `structlog` for JSON-formatted logs:

```python
logger.info(
    "chat_request_started",
    user_id=user_id,
    conversation_id=conversation_id,
    model=model,
    provider=provider
)
```

**Log Fields:**
- `timestamp`: ISO 8601 format
- `level`: debug, info, warning, error
- `event`: Event name
- `request_id`: Correlation ID
- `user_id`: When authenticated

### 8.2 Health Checks

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `/` | Root info | Application metadata with environment |
| `/health` | Full health | Database, Cache with latency metrics |
| `/health/live` | Liveness | Application running (lightweight) |
| `/health/ready` | Readiness | Database connected (503 if not) |
| `/health/info` | System info | Hostname, platform, Python version, uptime |
| `/health/db` | Database health | PostgreSQL connectivity with latency |
| `/health/cache` | Cache health | Redis/Upstash connectivity with latency |

### 8.3 OpenTelemetry

Instrumentation ready for:
- FastAPI requests
- SQLAlchemy queries
- HTTPX external calls

---

## 9. Scalability

### 9.1 Horizontal Scaling

The backend is designed for horizontal scaling:

- **Stateless**: No server-side session storage
- **External State**: PostgreSQL + Redis
- **Connection Pooling**: SQLAlchemy async pools

### 9.2 Performance Optimizations

| Optimization | Implementation |
|--------------|---------------|
| Async I/O | All database and HTTP operations |
| Connection Pooling | Configurable pool size/overflow |
| Context Caching | Redis with TTL |
| Fire-and-Forget | Background cache updates |
| Streaming | SSE for large responses |

### 9.3 Configuration Tuning

```python
# Database pool
DB_POOL_SIZE = 5       # Base connections
DB_MAX_OVERFLOW = 10   # Extra connections under load

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = 60      # General API
RATE_LIMIT_CHAT_REQUESTS_PER_MINUTE = 20 # Chat endpoint
```

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [README.md](./README.md) | Quick start & API reference |
| [OPTIMIZATION_REPORT.md](./OPTIMIZATION_REPORT.md) | Performance analysis |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | Full system architecture |

---

*Last Updated: December 2025*
