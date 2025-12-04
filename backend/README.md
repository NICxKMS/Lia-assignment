# Lia Chatbot Backend

**Author: Nikhil Kumar**

A high-performance, fully async Python backend for the Lia AI Chatbot with multi-LLM support and real-time sentiment analysis.

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=for-the-badge" alt="SQLAlchemy" />
</p>

---

## Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [API Reference](#-api-reference)
- [Database](#-database)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Deployment](#-deployment)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Fully Async** | Non-blocking I/O throughout with `asyncpg` and `httpx` |
| **Multi-LLM Support** | Google Gemini and OpenAI via unified adapter interface |
| **Real-time Streaming** | SSE for token-by-token response delivery |
| **Sentiment Analysis** | 3 methods: Structured, LLM Separate, Google Cloud NLP |
| **Rate Limiting** | Redis-based per-user request throttling |
| **JWT Authentication** | Secure token-based auth with async bcrypt |
| **Structured Logging** | JSON logs with request correlation via structlog |
| **Health Monitoring** | Comprehensive health checks for all services |
| **OpenTelemetry Ready** | Instrumentation for FastAPI, SQLAlchemy, and HTTPX |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** package manager
- **PostgreSQL** (or [Neon](https://neon.tech) account)
- **Redis** (or [Upstash](https://upstash.com) account)
- **API Keys**: At least one of Gemini or OpenAI

### Installation

```bash
# Navigate to backend directory
cd backend

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using CLI Commands

```bash
# Development server with auto-reload
uv run dev

# Production server
uv run start

# Run migrations
uv run migrate
```

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point
│   ├── cli.py                   # CLI commands (dev, start, migrate)
│   │
│   ├── api/                     # API Layer
│   │   ├── __init__.py
│   │   ├── deps.py              # Dependencies (auth, rate limit, db)
│   │   ├── schemas.py           # Pydantic request/response models
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py          # POST /register, /login, GET /me
│   │       ├── chat.py          # POST /stream, GET /history, etc.
│   │       └── health.py        # GET /health, /health/live, /health/ready
│   │
│   ├── core/                    # Core Configuration
│   │   ├── __init__.py
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── security.py          # JWT creation/validation, password hashing
│   │   ├── logging.py           # Structured logging configuration
│   │   └── exceptions.py        # Custom exception handlers
│   │
│   ├── db/                      # Database Layer
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy ORM models (User, Conversation, Message)
│   │   └── session.py           # Async session factory
│   │
│   └── services/                # Business Logic
│       ├── __init__.py
│       ├── chat.py              # ChatOrchestrator - main coordinator
│       ├── llm.py               # LLMService with Gemini/OpenAI adapters
│       ├── sentiment.py         # SentimentService with 3 strategies
│       ├── cache.py             # CacheService for Redis operations
│       └── rate_limit.py        # RateLimitService
│
├── alembic/                     # Database Migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_add_updated_at_columns.py
│       ├── 003_add_messages_columns.py
│       ├── 004_fix_conversation_id_type.py
│       ├── 005_add_conversation_updated_index.py
│       └── 006_remove_redundant_user_id_index.py
│
├── tests/                       # Test Suite
│   ├── conftest.py              # Pytest fixtures
│   ├── test_auth.py
│   ├── test_chat_api.py
│   ├── test_chat_sentiment.py
│   ├── test_health.py
│   ├── test_security.py
│   ├── test_sentiment.py
│   └── test_cache.py
│
├── .env.example                 # Environment template
├── alembic.ini                  # Alembic configuration
├── pyproject.toml               # Project dependencies (uv)
├── render.yaml                  # Render deployment config
├── Procfile                     # Heroku-style process file
├── README.md                    # This file
├── ARCHITECTURE.md              # Detailed architecture docs
└── OPTIMIZATION_REPORT.md       # Performance analysis
```

---

## 📚 API Reference

### Authentication

#### Register User

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepass123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "johndoe",
    "created_at": "2025-12-03T10:00:00Z"
  }
}
```

#### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepass123"
}
```

#### Get Current User

```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

---

### Chat

#### Send Message (Streaming)

```http
POST /api/v1/chat/stream
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Hello, how are you?",
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "sentiment_method": "structured",
  "conversation_id": null
}
```

**SSE Response Events:**

```
event: start
data: {"conversation_id": "uuid", "message_id": 1}

event: chunk
data: {"content": "Hello! "}

event: chunk
data: {"content": "I'm doing great, thank you for asking!"}

event: sentiment
data: {"message": {"score": 0.7, "label": "Positive", "emotion": "friendly"}, "cumulative": null}

event: done
data: {"finish_reason": "stop"}
```

#### Get Conversation History

```http
GET /api/v1/chat/history?limit=20
Authorization: Bearer <token>
```

**Response:**
```json
{
  "conversations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Hello conversation",
      "message_count": 5,
      "created_at": "2025-12-03T10:00:00Z",
      "updated_at": "2025-12-03T10:30:00Z"
    }
  ]
}
```

#### Get Conversation Detail

```http
GET /api/v1/chat/conversation/{conversation_id}
Authorization: Bearer <token>
```

#### Delete Conversation

```http
DELETE /api/v1/chat/conversation/{conversation_id}
Authorization: Bearer <token>
```

#### Delete All Conversations

```http
DELETE /api/v1/chat/conversations
Authorization: Bearer <token>
```

#### Rename Conversation

```http
PATCH /api/v1/chat/conversation/{conversation_id}/rename
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "New Title"
}
```

#### List Available Models

```http
GET /api/v1/chat/models
Authorization: Bearer <token>
```

**Response:**
```json
{
  "gemini": [
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Fast and efficient"},
    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Most capable"}
  ],
  "openai": [
    {"id": "gpt-4o", "name": "GPT-4o", "description": "Most capable"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Fast and affordable"}
  ]
}
```

#### List Sentiment Methods

```http
GET /api/v1/chat/methods
Authorization: Bearer <token>
```

**Response:**
```json
{
  "methods": [
    {"id": "structured", "name": "Structured Output", "description": "Single call with JSON response"},
    {"id": "llm_separate", "name": "LLM Separate", "description": "Dedicated sentiment analysis call"},
    {"id": "nlp_api", "name": "Google Cloud NLP", "description": "Google Natural Language API"}
  ]
}
```

---

### Health

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-03T10:00:00Z",
  "version": "2.0.0",
  "services": {
    "database": {
      "status": "healthy",
      "latency_ms": 5.2
    },
    "cache": {
      "status": "healthy",
      "latency_ms": 12.8
    }
  }
}
```

#### Liveness Probe

```http
GET /health/live
```

#### Readiness Probe

```http
GET /health/ready
```

---

## 🗄 Database

### Schema

```sql
-- Users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sentiment_data JSONB,
    model_info JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX ix_conversations_user_updated ON conversations(user_id, updated_at DESC);
CREATE INDEX ix_messages_conversation_created ON messages(conversation_id, created_at);
```

### Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "Description"

# Apply all migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

---

## ⚙ Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|:--------:|---------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ | - |
| `JWT_SECRET_KEY` | Secret for JWT signing (min 32 chars) | ✅ | - |
| `GEMINI_API_KEY` | Google Gemini API key | ⚡ | - |
| `OPENAI_API_KEY` | OpenAI API key | ⚡ | - |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis URL | ❌ | - |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis token | ❌ | - |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | ✅ | - |
| `GOOGLE_CLOUD_PROJECT` | GCP project for NLP API | ❌ | - |
| `JWT_EXPIRATION_DAYS` | JWT token expiration | ❌ | 7 |
| `DB_POOL_SIZE` | Database pool size | ❌ | 5 |
| `DB_MAX_OVERFLOW` | Database pool overflow | ❌ | 10 |
| `RATE_LIMIT_ENABLED` | Enable rate limiting | ❌ | true |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | General API limit | ❌ | 60 |
| `RATE_LIMIT_CHAT_REQUESTS_PER_MINUTE` | Chat endpoint limit | ❌ | 20 |

> ⚡ At least one LLM provider key is required

### Cache TTLs

| Key | TTL | Purpose |
|-----|-----|---------|
| `conv:{id}:context` | 1 hour | Conversation context |
| `conv:{id}:usrmsg` | 2 minutes | User messages for sentiment |
| `user:{id}:history` | 5 minutes | Conversation list |
| `models:available` | 24 hours | Available LLM models |

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_auth.py -v

# Run specific test
uv run pytest tests/test_auth.py::test_register_user -v

# Run with verbose output
uv run pytest -v --tb=short
```

### Test Structure

| File | Coverage |
|------|----------|
| `test_auth.py` | Authentication endpoints |
| `test_chat_api.py` | Chat API endpoints |
| `test_chat_sentiment.py` | Chat with sentiment |
| `test_health.py` | Health check endpoints |
| `test_security.py` | JWT and password utilities |
| `test_sentiment.py` | Sentiment analysis service |
| `test_cache.py` | Cache service operations |

---

## 🚀 Deployment

### Render.com

1. **Database**: Create a [Neon PostgreSQL](https://neon.tech) database
2. **Cache**: Create an [Upstash Redis](https://upstash.com) database
3. **Deploy**:
   - Connect your GitHub repository to Render
   - Render auto-detects `render.yaml`
   - Configure environment variables in dashboard

**Build Command:**
```bash
pip install uv && uv sync --frozen --no-dev && uv run alembic upgrade head
```

**Start Command:**
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
```

### Docker (Alternative)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY . .
RUN uv sync --frozen --no-dev
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📖 Related Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Detailed backend architecture |
| [OPTIMIZATION_REPORT.md](./OPTIMIZATION_REPORT.md) | Performance analysis & recommendations |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | Full system architecture |

---

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details.
