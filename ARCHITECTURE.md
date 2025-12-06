# Lia Chatbot - System Architecture

**Author: Nikhil Kumar**

> Comprehensive architectural documentation for the full-stack AI chatbot application

<p align="center">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Frontend-React%2019-61DAFB?style=flat-square&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=flat-square&logo=postgresql" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/AI-Gemini%20|%20OpenAI-FF6F00?style=flat-square" alt="AI" />
</p>

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Database Schema](#5-database-schema)
6. [Authentication & Security](#6-authentication--security)
7. [Sentiment Analysis System](#7-sentiment-analysis-system)
8. [Streaming Architecture](#8-streaming-architecture)
9. [Caching Strategy](#9-caching-strategy)
10. [API Design](#10-api-design)
11. [Design Patterns](#11-design-patterns)
12. [Deployment Architecture](#12-deployment-architecture)

---

## 1. System Overview

### 1.1 Key Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-Model Chat** | Google Gemini (2.5 Flash, 2.5 Pro) and OpenAI (GPT-4o, GPT-4.1) |
| **Real-time Streaming** | Server-Sent Events (SSE) for token-by-token responses |
| **Dual Sentiment Analysis** | Per-message and cumulative conversation sentiment |
| **Three Sentiment Methods** | Structured output, LLM separate calls, Google Cloud NLP |
| **JWT Authentication** | Secure user authentication with async bcrypt |
| **Conversation Persistence** | PostgreSQL-backed history per user |
| **Redis Caching** | Conversation context caching via Upstash |
| **Rate Limiting** | Per-user request throttling |

### 1.2 Technology Stack Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  React 19 │ TypeScript │ Vite │ TailwindCSS 4 │ Radix UI │ SSE │
└─────────────────────────────────────────────────────────────────┘
                                │
                           HTTPS/REST
                                │
┌─────────────────────────────────────────────────────────────────┐
│                          API GATEWAY                             │
├─────────────────────────────────────────────────────────────────┤
│      FastAPI │ Pydantic v2 │ JWT Auth │ CORS │ SSE Streaming    │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  ChatOrchestrator │ LLM Adapters │ Sentiment Strategies │ Cache │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│     PostgreSQL (Neon) │ SQLAlchemy 2.0 Async │ Upstash Redis    │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES                          │
├─────────────────────────────────────────────────────────────────┤
│       Google Gemini API │ OpenAI API │ Google Cloud NLP API     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. High-Level Architecture

### 2.1 System Context Diagram

```
                    ┌──────────────┐
                    │   End User   │
                    └──────┬───────┘
                           │ HTTPS
                           ▼
                    ┌──────────────┐
                    │   React SPA  │
                    │   (Vercel)   │
                    └──────┬───────┘
                           │ REST + SSE
                           ▼
                    ┌──────────────┐
                    │   FastAPI    │
                    │   (Render)   │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │   Redis     │ │   LLM APIs      │
│   (Neon)        │ │  (Upstash)  │ │ Gemini / OpenAI │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

### 2.2 Component Interaction Matrix

| Component | Interacts With | Protocol | Purpose |
|-----------|---------------|----------|---------|
| Frontend | Backend API | HTTPS + SSE | User interface, real-time streaming |
| API Routes | ChatOrchestrator | Async Python | Request coordination |
| ChatOrchestrator | LLMService | Async | AI response generation |
| ChatOrchestrator | SentimentService | Async | Emotion analysis |
| ChatOrchestrator | CacheService | Async | Context caching |
| ChatOrchestrator | Database | SQLAlchemy | Persistence |
| LLMService | Gemini/OpenAI | HTTPS | External AI calls |
| CacheService | Redis | REST API | Upstash operations |

---

## 3. Backend Architecture

### 3.1 Layer Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      API LAYER (Routes)                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐│
│  │  auth.py   │  │  chat.py   │  │       health.py            ││
│  │ /register  │  │  /stream   │  │     /health                ││
│  │  /login    │  │  /history  │  │     /health/live           ││
│  │   /me      │  │ /conversation│ │     /health/ready          ││
│  └────────────┘  └────────────┘  └────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
                              │
┌────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                               │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                   ChatOrchestrator                      │    │
│  │  • Coordinates chat flow                                │    │
│  │  • Manages conversation state                           │    │
│  │  • Routes to appropriate services                       │    │
│  └────────────────────────────────────────────────────────┘    │
│       │                    │                    │               │
│  ┌────┴────┐         ┌─────┴─────┐        ┌────┴────┐         │
│  │   LLM   │         │ Sentiment │        │  Cache  │         │
│  │ Service │         │  Service  │        │ Service │         │
│  └─────────┘         └───────────┘        └─────────┘         │
└────────────────────────────────────────────────────────────────┘
                              │
┌────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   models.py  │  │  session.py  │  │    Redis Client      │  │
│  │ User, Conv,  │  │ AsyncSession │  │   Upstash REST       │  │
│  │   Message    │  │   Factory    │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 Service Responsibilities

| Service | File | Key Methods |
|---------|------|-------------|
| **ChatOrchestrator** | `services/chat.py` | `process_chat_stream()`, `get_conversation_history()`, `delete_conversation()` |
| **LLMService** | `services/llm.py` | `generate_stream()`, `generate_structured_stream()`, `get_all_models()` |
| **SentimentService** | `services/sentiment.py` | `analyze()`, `get_available_methods()` |
| **CacheService** | `services/cache.py` | `get_conversation_context()`, `set_conversation_context()` |
| **RateLimitService** | `services/rate_limit.py` | `check_rate_limit()`, `increment_request_count()` |

### 3.3 Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry
│   ├── cli.py                   # CLI commands (dev, start, migrate)
│   ├── api/
│   │   ├── deps.py              # Dependencies (auth, rate limit)
│   │   ├── schemas.py           # Pydantic request/response models
│   │   └── routes/
│   │       ├── auth.py          # Authentication endpoints
│   │       ├── chat.py          # Chat & conversation endpoints
│   │       └── health.py        # Health check endpoints
│   ├── core/
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── security.py          # JWT & password utilities
│   │   ├── logging.py           # Structured logging (structlog)
│   │   └── exceptions.py        # Custom exception handlers
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── session.py           # Async session factory
│   └── services/
│       ├── chat.py              # ChatOrchestrator
│       ├── llm.py               # GeminiAdapter, OpenAIAdapter
│       ├── sentiment.py         # Sentiment strategies
│       ├── cache.py             # Redis caching
│       └── rate_limit.py        # Rate limiting
├── alembic/                     # Database migrations
├── tests/                       # Pytest test suite
├── pyproject.toml               # Dependencies (uv)
└── render.yaml                  # Render deployment config
```

---

## 4. Frontend Architecture

### 4.1 Component Hierarchy

```
App
├── AuthProvider (Context)
│   ├── AuthPage
│   │   ├── LoginForm
│   │   └── RegisterForm
│   └── ChatInterface
│       ├── ChatSidebar
│       │   ├── ConversationList
│       │   └── NewChatButton
│       ├── MessageList
│       │   └── MarkdownMessage (×n)
│       ├── ChatInput
│       │   ├── TextArea
│       │   ├── ModelSelector
│       │   └── SendButton
│       └── ChatInspector
│           ├── SentimentGauge
│           ├── SentimentChart (Recharts)
│           └── MessageMetadata
```

### 4.2 Key Frontend Technologies

| Feature | Implementation |
|---------|---------------|
| **SSE Streaming** | Native EventSource with reconnection |
| **Markdown Rendering** | react-markdown + rehype-highlight |
| **Charts** | Recharts for sentiment visualization |
| **State Management** | TanStack Query for server state |
| **Forms** | Controlled components with validation |
| **Styling** | TailwindCSS 4 + Radix UI primitives |
| **Animations** | Framer Motion |

### 4.3 Component Files

```
frontend/src/
├── components/
│   ├── chat/
│   │   ├── ChatInterface.tsx    # Main chat container
│   │   ├── ChatInput.tsx        # Message input with model selector
│   │   ├── ChatSidebar.tsx      # Conversation list sidebar
│   │   ├── ChatInspector.tsx    # Sentiment analysis panel
│   │   └── MessageList.tsx      # Message display
│   ├── ui/                      # Radix-based UI primitives
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── scroll-area.tsx
│   │   └── ...
│   ├── AuthPage.tsx             # Login/Register page
│   └── MarkdownMessage.tsx      # Markdown renderer
├── context/
│   ├── AuthContext.ts           # Auth context definition
│   ├── AuthProvider.tsx         # Auth state provider
│   └── useAuth.ts               # Auth hook
├── lib/
│   ├── api.ts                   # Axios API client
│   ├── useChat.ts               # Chat hook with SSE
│   └── utils.ts                 # Utility functions
└── __tests__/                   # Vitest test suite
```

---

## 5. Database Schema

### 5.1 Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────┐
│       users         │       │    conversations    │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │───┐   │ id (PK, UUID)       │
│ email (UNIQUE)      │   │   │ user_id (FK)        │◄──┐
│ username (UNIQUE)   │   └──►│ title               │   │
│ hashed_password     │       │ created_at          │   │
│ created_at          │       │ updated_at          │   │
│ updated_at          │       └──────────┬──────────┘   │
└─────────────────────┘                  │              │
                                         │              │
                              ┌──────────▼──────────┐   │
                              │      messages       │   │
                              ├─────────────────────┤   │
                              │ id (PK)             │   │
                              │ conversation_id (FK)│───┘
                              │ role ('user'/'assistant')
                              │ content (TEXT)      │
                              │ sentiment_data (JSONB)
                              │ model_info (JSONB)  │
                              │ created_at          │
                              └─────────────────────┘
```

### 5.2 Table Definitions

#### `users`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PRIMARY KEY |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL |
| `username` | VARCHAR(100) | UNIQUE, NOT NULL |
| `hashed_password` | VARCHAR(255) | NOT NULL |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() |

#### `conversations`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| `user_id` | INTEGER | FOREIGN KEY → users.id, ON DELETE CASCADE |
| `title` | VARCHAR(255) | NULLABLE |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() |

#### `messages`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | SERIAL | PRIMARY KEY |
| `conversation_id` | UUID | FOREIGN KEY → conversations.id, ON DELETE CASCADE |
| `role` | VARCHAR(20) | NOT NULL ('user' or 'assistant') |
| `content` | TEXT | NOT NULL |
| `sentiment_data` | JSONB | NULLABLE |
| `model_info` | JSONB | NULLABLE |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |

### 5.3 Indexes

```sql
CREATE INDEX ix_conversations_user_updated ON conversations(user_id, updated_at DESC);
CREATE INDEX ix_messages_conversation_created ON messages(conversation_id, created_at);
```

---

## 6. Authentication & Security

### 6.1 Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Transport Security (HTTPS/TLS)                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: CORS Policy (Allowed origins only)                │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: JWT Token Validation                              │
│  • Algorithm: HS256                                         │
│  • Expiry: 7 days (configurable)                            │
│  • Claims: sub (user_id), exp, iat                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Password Security                                 │
│  • Algorithm: Bcrypt (async)                                │
│  • Work factor: Default rounds                              │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Input Validation (Pydantic v2 schemas)            │
├─────────────────────────────────────────────────────────────┤
│  Layer 6: Rate Limiting (Per-user/Per-IP)                   │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Authentication Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │     │Frontend │     │ Backend │     │Database │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │ 1. Register   │               │               │
     │──────────────►│               │               │
     │               │ POST /register│               │
     │               │──────────────►│               │
     │               │               │ hash_password │
     │               │               │──────────────►│
     │               │               │◄──────────────│
     │               │               │ create_user   │
     │               │               │──────────────►│
     │               │               │◄──────────────│
     │               │  JWT Token    │               │
     │               │◄──────────────│               │
     │  Token stored │               │               │
     │◄──────────────│               │               │
     │               │               │               │
     │ 2. API Call   │               │               │
     │──────────────►│               │               │
     │               │ Authorization │               │
     │               │ Bearer <token>│               │
     │               │──────────────►│               │
     │               │               │ verify_token  │
     │               │  Response     │               │
     │               │◄──────────────│               │
     │  Data         │               │               │
     │◄──────────────│               │               │
```

---

## 7. Sentiment Analysis System

### 7.1 Dual Sentiment Architecture

The system analyzes **user messages** (not assistant responses) at two levels:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Message Input                       │
└─────────────────────────────┬───────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
┌───────────────────────┐       ┌───────────────────────────────┐
│   MESSAGE SENTIMENT   │       │   CUMULATIVE SENTIMENT        │
│   (Single message)    │       │   (All user messages)         │
├───────────────────────┤       ├───────────────────────────────┤
│ Analyzes the current  │       │ Concatenates all previous     │
│ user message only     │       │ user messages and analyzes    │
│                       │       │ overall emotional trajectory  │
└───────────────────────┘       └───────────────────────────────┘
            │                                   │
            └─────────────────┬─────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Sentiment Response                        │
│  {                                                          │
│    "message": { score, label, emotion },                    │
│    "cumulative": { score, label, emotion } | null           │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Sentiment Methods Comparison

| Method | Implementation | API Calls | Latency | Best For |
|--------|---------------|-----------|---------|----------|
| **structured** | LLM returns response + sentiment in JSON | 1 | Low | Performance |
| **llm_separate** | Dedicated LLM call for sentiment | 2 | Medium | Accuracy |
| **nlp_api** | Google Cloud Natural Language API | 1 + API | Low | Production |

### 7.3 Sentiment Response Schema

```json
{
  "message": {
    "score": 0.75,
    "label": "Positive",
    "emotion": "happy",
    "confidence": 0.85
  },
  "cumulative": {
    "score": 0.45,
    "label": "Neutral",
    "emotion": "curious",
    "confidence": 0.72
  }
}
```

---

## 8. Streaming Architecture

### 8.1 Server-Sent Events (SSE) Protocol

```
Client                                    Server
   │                                         │
   │──── POST /api/v1/chat/stream ──────────►│
   │     Authorization: Bearer <token>       │
   │     { message, model, sentiment_method }│
   │                                         │
   │◄──── HTTP 200 OK ──────────────────────│
   │      Content-Type: text/event-stream    │
   │                                         │
   │◄──── event: start                      │
   │      data: { conversation_id, ... }     │
   │                                         │
   │◄──── event: chunk                      │
   │      data: { content: "Hello" }         │
   │                                         │
   │◄──── event: chunk                      │
   │      data: { content: " there!" }       │
   │                                         │
   │◄──── event: sentiment                  │
   │      data: { message: {...},            │
   │              cumulative: {...} }        │
   │                                         │
   │◄──── event: done                       │
   │      data: { finish_reason: "stop" }    │
   │                                         │
```

### 8.2 Stream Event Types

| Event | Payload | Description |
|-------|---------|-------------|
| `start` | `{ conversation_id, message_id }` | Stream initialization |
| `chunk` | `{ content: string }` | Token from LLM |
| `sentiment` | `{ message: {...}, cumulative: {...} }` | Sentiment analysis |
| `done` | `{ finish_reason: string }` | Stream complete |
| `error` | `{ message: string }` | Error occurred |

---

## 9. Caching Strategy

### 9.1 Redis Cache Keys

| Key Pattern | Data | TTL |
|-------------|------|-----|
| `conv:{id}:context` | Conversation message context | 1 hour |
| `conv:{id}:usrmsg` | User messages for sentiment | 2 minutes |
| `user:{id}:history` | Conversation list (sorted set) | 5 minutes |
| `models:available` | Available LLM models | 24 hours |
| `methods:sentiment` | Available sentiment methods | 24 hours |

### 9.2 Cache Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Request   │     │    Cache    │     │  Database   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │ 1. Check cache    │                   │
       │──────────────────►│                   │
       │                   │                   │
       │ 2a. Cache HIT     │                   │
       │◄──────────────────│                   │
       │                   │                   │
       │ 2b. Cache MISS    │                   │
       │◄──────────────────│                   │
       │                   │                   │
       │ 3. Query database │                   │
       │───────────────────────────────────────►
       │                   │                   │
       │ 4. Response       │                   │
       │◄───────────────────────────────────────
       │                   │                   │
       │ 5. Update cache (async)               │
       │──────────────────►│                   │
       │                   │                   │
```

---

## 10. API Design

### 10.1 Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| `POST` | `/api/v1/auth/register` | ❌ | User registration |
| `POST` | `/api/v1/auth/login` | ❌ | User login |
| `GET` | `/api/v1/auth/me` | ✅ | Get current user |
| `POST` | `/api/v1/chat/stream` | ✅ | Streaming chat |
| `GET` | `/api/v1/chat/history` | ✅ | List conversations |
| `GET` | `/api/v1/chat/conversation/{id}` | ✅ | Get conversation |
| `DELETE` | `/api/v1/chat/conversation/{id}` | ✅ | Delete conversation |
| `DELETE` | `/api/v1/chat/conversations` | ✅ | Delete all conversations |
| `PATCH` | `/api/v1/chat/conversation/{id}/rename` | ✅ | Rename conversation |
| `GET` | `/api/v1/chat/models` | ✅ | List available models |
| `GET` | `/api/v1/chat/methods` | ✅ | List sentiment methods |
| `GET` | `/health` | ❌ | Health check |
| `GET` | `/health/live` | ❌ | Liveness probe |
| `GET` | `/health/ready` | ❌ | Readiness probe |

### 10.2 Request/Response Examples

#### Chat Stream Request

```http
POST /api/v1/chat/stream
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Hello, how are you?",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "sentiment_method": "structured",
  "conversation_id": null
}
```

#### Chat Response (SSE)

```
event: start
data: {"conversation_id": "550e8400-e29b-41d4-a716-446655440000", "message_id": 1}

event: chunk
data: {"content": "Hello! "}

event: chunk
data: {"content": "I'm doing well, thank you!"}

event: sentiment
data: {"message": {"score": 0.6, "label": "Positive", "emotion": "friendly"}, "cumulative": null}

event: done
data: {"finish_reason": "stop"}
```

---

## 11. Design Patterns

### 11.1 Patterns Used

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Strategy** | `SentimentService` | Interchangeable analysis algorithms |
| **Adapter** | `LLMService` | Unified interface for Gemini/OpenAI |
| **Factory** | `session.py` | Async session creation |
| **Orchestrator** | `ChatOrchestrator` | Coordinate complex workflows |
| **Singleton** | Service getters | Single instance management |
| **Dependency Injection** | FastAPI `Depends()` | Loose coupling, testability |

### 11.2 Adapter Pattern (LLM Service)

```
┌─────────────────────────────────────────────┐
│                 LLMService                  │
│  ┌─────────────────────────────────────┐   │
│  │           get_adapter()             │   │
│  └──────────────────┬──────────────────┘   │
│                     │                       │
│         ┌───────────┼───────────┐          │
│         │           │           │          │
│         ▼           ▼           ▼          │
│  ┌────────────┐ ┌────────────┐ ┌────────┐ │
│  │  Gemini    │ │   OpenAI   │ │ Future │ │
│  │  Adapter   │ │   Adapter  │ │Adapter │ │
│  └────────────┘ └────────────┘ └────────┘ │
└─────────────────────────────────────────────┘
```

---

## 12. Deployment Architecture

### 12.1 Production Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────────┐                     ┌───────────────────┐
│      Vercel       │                     │      Render       │
│  (Frontend CDN)   │                     │    (Backend)      │
│                   │                     │                   │
│  React SPA        │   HTTPS/REST/SSE   │  FastAPI + uv     │
│  Static Assets    │ ◄─────────────────► │  Uvicorn Workers  │
└───────────────────┘                     └─────────┬─────────┘
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              │                     │                     │
                              ▼                     ▼                     ▼
                     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
                     │     Neon        │  │    Upstash      │  │   LLM APIs      │
                     │   PostgreSQL    │  │     Redis       │  │                 │
                     │                 │  │                 │  │ • Gemini        │
                     │ • Users         │  │ • Cache         │  │ • OpenAI        │
                     │ • Conversations │  │ • Rate Limits   │  │ • Cloud NLP     │
                     │ • Messages      │  │                 │  │                 │
                     └─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 12.2 Environment Configuration

| Environment | Database | Cache | Workers |
|-------------|----------|-------|---------|
| Development | SQLite (local) | Mock/Local | 1 |
| Production | Neon PostgreSQL | Upstash Redis | 2+ |

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [README.md](./README.md) | Project overview & quick start |
| [backend/README.md](./backend/README.md) | Backend setup & API reference |
| [backend/ARCHITECTURE.md](./backend/ARCHITECTURE.md) | Detailed backend architecture |
| [backend/OPTIMIZATION_REPORT.md](./backend/OPTIMIZATION_REPORT.md) | Performance analysis |
| [frontend/README.md](./frontend/README.md) | Frontend documentation |

---

*Last Updated: December 2025*
