# Lia Chatbot

**Author: Nikhil Kumar**

A production-ready, full-stack AI chatbot application featuring real-time sentiment analysis, multi-provider LLM support, and streaming responses.

<p align="center">
  <a href="https://lia.nicx.app"><img src="https://img.shields.io/badge/🚀_Live_Demo-lia.nicx.app-00C853?style=for-the-badge" alt="Live Demo" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Frontend-React%2019-61DAFB?style=for-the-badge&logo=react" alt="React" />
  <img src="https://img.shields.io/badge/AI-Gemini%20|%20OpenAI-FF6F00?style=for-the-badge" alt="AI" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql" alt="PostgreSQL" />
</p>

---

## Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 🧠 Dual Sentiment Analysis

Analyzes user sentiment at both message and conversation levels using three switchable strategies:

| Strategy | Description | Best For |
|----------|-------------|----------|
| **Structured Output** | Single LLM call returns response + sentiment in JSON | Performance & efficiency |
| **LLM Separate** | Dedicated LLM call for detailed sentiment analysis | Accuracy & nuance |
| **Google Cloud NLP** | Google's Natural Language API for fast analysis | Production scale |

**Conversation-Level (Tier 1):** Aggregates all user messages to track overall emotional trajectory  
**Statement-Level (Tier 2):** Analyzes each message individually with real-time visualization

### 🤖 Multi-Model LLM Support

- **Google Gemini**: 2.0 Flash, 1.5 Pro, 1.5 Flash
- **OpenAI**: GPT-4o, GPT-4o Mini, GPT-3.5 Turbo
- Hot-swappable at runtime via unified adapter interface

### ⚡ Real-Time Streaming

- Server-Sent Events (SSE) for token-by-token response streaming
- Live sentiment updates as conversations progress
- Visual trend charts powered by Recharts

### 🔐 Secure Authentication

- JWT-based authentication with configurable expiration
- Async bcrypt password hashing
- Per-user conversation isolation

### 🚀 High Performance

- Fully async backend with `asyncpg` and SQLAlchemy 2.0
- Redis caching via Upstash (serverless)
- Connection pooling for database scalability

---

## 🛠 Tech Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.115+ | Web framework |
| Python | 3.11+ | Runtime |
| SQLAlchemy | 2.0+ | Async ORM |
| PostgreSQL | (Neon) | Database |
| Upstash Redis | REST API | Caching & rate limiting |
| google-genai | 1.0+ | Gemini integration |
| OpenAI | 1.57+ | GPT integration |
| Pydantic | 2.10+ | Validation |
| structlog | 24.4+ | Structured logging |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2 | UI framework |
| TypeScript | 5.9 | Type safety |
| Vite | (Rolldown) | Build tool |
| TailwindCSS | 4.1 | Styling |
| TanStack Query | 5.90 | Server state |
| Recharts | 3.5 | Data visualization |
| Radix UI | Latest | Accessible components |
| Framer Motion | 12.23 | Animations |

---

## 📁 Project Structure

```
Lia-assignment/
├── backend/                     # FastAPI Backend Service
│   ├── app/
│   │   ├── api/                 # REST API endpoints
│   │   │   ├── routes/
│   │   │   │   ├── auth.py      # Authentication routes
│   │   │   │   ├── chat.py      # Chat & streaming routes
│   │   │   │   └── health.py    # Health check routes
│   │   │   ├── deps.py          # Dependencies (auth, rate limit)
│   │   │   └── schemas.py       # Pydantic models
│   │   ├── core/                # Configuration & security
│   │   │   ├── config.py        # Settings management
│   │   │   ├── security.py      # JWT & password utils
│   │   │   └── logging.py       # Structured logging
│   │   ├── db/                  # Database layer
│   │   │   ├── models.py        # SQLAlchemy models
│   │   │   └── session.py       # Async session factory
│   │   └── services/            # Business logic
│   │       ├── chat.py          # Chat orchestrator
│   │       ├── llm.py           # LLM adapters (Gemini/OpenAI)
│   │       ├── sentiment.py     # Sentiment strategies
│   │       ├── cache/           # Modular cache system
│   │       │   ├── base.py      # Base caching operations
│   │       │   ├── conversation.py  # Conversation caching
│   │       │   ├── static.py    # Static content caching
│   │       │   ├── rate_limit.py    # Rate limiting cache
│   │       │   └── user.py      # User data caching
│   │       └── rate_limit.py    # Rate limiting service
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Pytest test suite
│   ├── pyproject.toml           # Python dependencies (uv)
│   └── render.yaml              # Render deployment config
│
├── frontend/                    # React Frontend Application
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/            # Chat UI components
│   │   │   │   ├── ChatInterface.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── ChatSidebar.tsx
│   │   │   │   ├── ChatInspector.tsx
│   │   │   │   └── MessageList.tsx
│   │   │   ├── ui/              # Reusable UI primitives
│   │   │   ├── AuthPage.tsx     # Login/Register
│   │   │   └── MarkdownMessage.tsx
│   │   ├── context/             # React context (Auth)
│   │   ├── lib/                 # Utilities & API client
│   │   └── __tests__/           # Vitest test suite
│   ├── package.json             # Node dependencies (pnpm)
│   └── vite.config.ts           # Vite configuration
│
├── ARCHITECTURE.md              # System architecture documentation
└── README.md                    # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** with [uv](https://github.com/astral-sh/uv) package manager
- **Node.js 20+** with **pnpm**
- **PostgreSQL** database (or [Neon](https://neon.tech) account)
- **Redis** (or [Upstash](https://upstash.com) account)
- **API Keys**: At least one of Gemini or OpenAI

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Lia-assignment.git
cd Lia-assignment
```

### 2. Backend Setup

```bash
cd backend

# Install uv if not installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and configure environment
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Create environment file
echo "VITE_API_URL=http://localhost:8000" > .env

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

### 4. Access the Application

Open your browser to **http://localhost:5173**

---

## 🔑 Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|----------|-------------|:--------:|
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `JWT_SECRET_KEY` | Secret for JWT signing (min 32 chars) | ✅ |
| `GEMINI_API_KEY` | Google Gemini API key | ⚡ |
| `OPENAI_API_KEY` | OpenAI API key | ⚡ |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL | ❌ |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis token | ❌ |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | ✅ |
| `GOOGLE_CLOUD_PROJECT` | GCP project for NLP API | ❌ |

> ⚡ At least one LLM provider key is required

### Frontend (`frontend/.env`)

| Variable | Description | Required |
|----------|-------------|:--------:|
| `VITE_API_URL` | Backend API URL | ✅ |

---

## 🌐 Deployment

### Backend (Render)

1. Connect your GitHub repository to [Render](https://render.com)
2. Render auto-detects `render.yaml` configuration
3. Configure environment variables in Render dashboard
4. Deploy automatically on push to main

### Frontend (Vercel)

1. Import project to [Vercel](https://vercel.com)
2. Set `VITE_API_URL` to your Render backend URL
3. Deploy with automatic preview deployments

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture & design patterns |
| [backend/README.md](./backend/README.md) | Backend setup & API reference |
| [backend/ARCHITECTURE.md](./backend/ARCHITECTURE.md) | Backend architecture details |
| [backend/OPTIMIZATION_REPORT.md](./backend/OPTIMIZATION_REPORT.md) | Performance analysis & recommendations |
| [frontend/README.md](./frontend/README.md) | Frontend documentation |

---

## 🧪 Testing

The project has comprehensive test coverage across both frontend and backend.

### Backend (169 tests, ~51s)

```bash
cd backend
uv run pytest                    # Run all tests
uv run pytest --cov=app          # With coverage
uv run pytest tests/test_auth.py # Specific file
```

### Frontend (300 tests, ~6s)

```bash
cd frontend
pnpm test                        # Run all tests (watch mode)
pnpm test --run                  # Run once
pnpm test -- --coverage          # With coverage
```

> **Total: 469 tests** with sub-second individual test execution

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

Please ensure:
- Tests pass (`uv run pytest` / `pnpm test`)
- Code follows existing style (Ruff for Python, ESLint for TypeScript)
- Documentation is updated if needed

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for details.

---

<p align="center">
  Built with ❤️ using FastAPI, React, and modern AI
</p>
