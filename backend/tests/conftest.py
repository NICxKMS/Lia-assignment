"""Test configuration and fixtures.

Provides isolated test fixtures for:
- Database sessions with proper cleanup
- HTTP client with dependency overrides
- Mock services for unit testing
- Authenticated user fixtures
"""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, Conversation, Message, User
from app.db.session import get_db
from app.services.cache import CacheService, get_cache_service
from app.services.rate_limit import RateLimitService, get_rate_limit_service
from app.services.sentiment import CumulativeState, SentimentResult, SentimentService


# Test database URL (SQLite in-memory with shared cache for proper async behavior)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"
# Ensure application uses test database for health/readiness checks BEFORE app import
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
os.environ.setdefault("DEBUG", "true")

from app.main import app  # noqa: E402  (import after setting env)


# =============================================================================
# Session Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with safe defaults."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret_key="test-secret-key-for-testing-only-min-32-chars",
        debug=True,
        rate_limit_enabled=False,
        upstash_redis_rest_url="",
        upstash_redis_rest_token="",
    )


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine with fresh schema for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables and dispose
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction rollback."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with session_factory() as session:
        yield session
        # Rollback any uncommitted changes
        await session.rollback()


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with database override."""
    from app.services.chat import ChatOrchestrator, get_chat_orchestrator
    
    async def override_get_db():
        yield test_db
    
    # Override database dependency
    app.dependency_overrides[get_db] = override_get_db
    
    # Create disabled cache service for tests
    mock_cache = MagicMock(spec=CacheService)
    mock_cache.is_available = False
    mock_cache.get_conversation_detail = AsyncMock(return_value=None)
    mock_cache.get_conversation_history = AsyncMock(return_value=None)
    mock_cache.get_available_models = AsyncMock(return_value=None)
    mock_cache.get_sentiment_methods = AsyncMock(return_value=None)
    mock_cache.set_conversation_detail = AsyncMock(return_value=True)
    mock_cache.set_conversation_history = AsyncMock(return_value=True)
    mock_cache.set_available_models = AsyncMock(return_value=True)
    mock_cache.set_sentiment_methods = AsyncMock(return_value=True)
    mock_cache.invalidate_conversation = AsyncMock(return_value=True)
    mock_cache.invalidate_user_history = AsyncMock(return_value=True)
    
    app.dependency_overrides[get_cache_service] = lambda: mock_cache

    # Create disabled rate limiter for tests
    mock_rate_limiter = MagicMock(spec=RateLimitService)
    mock_rate_limiter.is_enabled = False
    mock_rate_limiter.check_auth_limit = AsyncMock(return_value=(True, -1))
    mock_rate_limiter.check_general_limit = AsyncMock(return_value=(True, -1))
    mock_rate_limiter.check_chat_limit = AsyncMock(return_value=(True, -1))
    mock_rate_limiter.close = AsyncMock()
    app.dependency_overrides[get_rate_limit_service] = lambda: mock_rate_limiter

    # Override chat orchestrator to use mock cache
    test_orchestrator = ChatOrchestrator(cache_service=mock_cache)
    app.dependency_overrides[get_chat_orchestrator] = lambda: test_orchestrator
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user directly in the database."""
    from app.core.security import get_password_hash
    
    hashed_password = await get_password_hash("Testpassword123")
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hashed_password,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, test_user: User) -> dict[str, str]:
    """Get auth headers for a pre-created test user."""
    # Login with the test user
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "Testpassword123",
        },
    )
    
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def second_user(test_db: AsyncSession) -> User:
    """Create a second test user for isolation tests."""
    from app.core.security import get_password_hash
    
    hashed_password = await get_password_hash("Secondpass123")
    user = User(
        email="second@example.com",
        username="seconduser",
        hashed_password=hashed_password,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


# =============================================================================
# Conversation & Message Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_conversation(test_db: AsyncSession, test_user: User) -> Conversation:
    """Create a test conversation."""
    conversation = Conversation(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        title="Test Conversation",
    )
    test_db.add(conversation)
    await test_db.commit()
    await test_db.refresh(conversation)
    return conversation


@pytest_asyncio.fixture(scope="function")
async def conversation_with_messages(
    test_db: AsyncSession,
    test_conversation: Conversation,
) -> tuple[Conversation, list[Message]]:
    """Create a conversation with multiple messages."""
    messages = [
        Message(
            conversation_id=test_conversation.id,
            role="user",
            content="Hello, how are you?",
        ),
        Message(
            conversation_id=test_conversation.id,
            role="assistant",
            content="I'm doing well, thank you for asking!",
            model_info={"provider": "gemini", "model": "gemini-2.5-flash"},
        ),
        Message(
            conversation_id=test_conversation.id,
            role="user",
            content="What can you help me with?",
        ),
        Message(
            conversation_id=test_conversation.id,
            role="assistant",
            content="I can help with many things!",
            model_info={"provider": "gemini", "model": "gemini-2.5-flash"},
        ),
    ]
    
    test_db.add_all(messages)
    await test_db.commit()
    
    for msg in messages:
        await test_db.refresh(msg)
    
    return test_conversation, messages


# =============================================================================
# Mock Service Fixtures
# =============================================================================

@pytest.fixture
def mock_cache_service() -> MagicMock:
    """Create a mock cache service."""
    mock = MagicMock(spec=CacheService)
    mock.is_available = False
    mock.get_conversation_context = AsyncMock(return_value=None)
    mock.get_user_messages = AsyncMock(return_value=None)
    mock.get_conversation_history = AsyncMock(return_value=None)
    mock.get_conversation_detail = AsyncMock(return_value=None)
    mock.set_conversation_context = AsyncMock(return_value=True)
    mock.set_user_messages = AsyncMock(return_value=True)
    mock.append_to_context = AsyncMock(return_value=True)
    mock.append_user_message = AsyncMock(return_value=True)
    mock.invalidate_conversation = AsyncMock(return_value=True)
    mock.invalidate_user_history = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_cache_service_enabled() -> MagicMock:
    """Create a mock cache service with caching enabled."""
    mock = MagicMock(spec=CacheService)
    mock.is_available = True
    mock.get_conversation_context = AsyncMock(return_value=None)
    mock.get_user_messages = AsyncMock(return_value=None)
    mock.get_conversation_history = AsyncMock(return_value=None)
    mock.get_conversation_detail = AsyncMock(return_value=None)
    mock.set_conversation_context = AsyncMock(return_value=True)
    mock.set_user_messages = AsyncMock(return_value=True)
    mock.set_conversation_history = AsyncMock(return_value=True)
    mock.set_conversation_detail = AsyncMock(return_value=True)
    mock.append_to_context = AsyncMock(return_value=True)
    mock.append_user_message = AsyncMock(return_value=True)
    mock.invalidate_conversation = AsyncMock(return_value=True)
    mock.invalidate_user_history = AsyncMock(return_value=True)
    mock.get_available_models = AsyncMock(return_value=None)
    mock.set_available_models = AsyncMock(return_value=True)
    mock.get_sentiment_methods = AsyncMock(return_value=None)
    mock.set_sentiment_methods = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_sentiment_service() -> MagicMock:
    """Create a mock sentiment service."""
    mock = MagicMock(spec=SentimentService)
    sentiment_result = SentimentResult(
        score=0.5,
        label="Positive",
        source="test",
        emotion="happy",
    )
    mock.analyze = AsyncMock(return_value=sentiment_result)
    
    # Mock update_cumulative for incremental sentiment
    async def mock_update_cumulative(
        new_message: str,
        current_state: CumulativeState,
        message_sentiment: SentimentResult | None,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash-lite",
    ) -> tuple[SentimentResult, CumulativeState]:
        """Mock incremental sentiment update."""
        new_state = CumulativeState(
            summary=f"Updated summary after: {new_message[:20]}...",
            score=message_sentiment.score if message_sentiment else 0.0,
            count=current_state.count + 1,
            label=message_sentiment.label if message_sentiment else "Neutral",
        )
        result = SentimentResult(
            score=new_state.score,
            label=new_state.label,
            summary=new_state.summary,
            source="incremental_mock",
        )
        return result, new_state
    
    mock.update_cumulative = AsyncMock(side_effect=mock_update_cumulative)
    mock.get_available_methods = MagicMock(
        return_value=["nlp_api", "llm_separate", "structured"]
    )
    return mock


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter with streaming support."""
    
    class MockStreamChunk:
        def __init__(self, content: str, is_final: bool = False):
            self.content = content
            self.is_final = is_final
    
    async def mock_stream(*args, **kwargs):
        yield MockStreamChunk("Hello, ")
        yield MockStreamChunk("I'm ")
        yield MockStreamChunk("Lia!")
        yield MockStreamChunk("", is_final=True)
    
    adapter = MagicMock()
    adapter.generate_stream = mock_stream
    return adapter


@pytest.fixture
def mock_llm_service(mock_llm_adapter):
    """Create a mock LLM service."""
    service = MagicMock()
    service.get_adapter = MagicMock(return_value=mock_llm_adapter)
    service.get_all_models = MagicMock(return_value={
        "gemini": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.0 Flash", "context_window": 1000000}
        ],
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o", "context_window": 128000}
        ],
    })
    return service
