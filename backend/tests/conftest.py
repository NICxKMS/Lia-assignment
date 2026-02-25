"""Test configuration and shared fixtures."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Conversation, Message, User

# ---- Environment (before any app imports) ----

TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-32-chars")
os.environ.setdefault("DEBUG", "true")

from app.core.security import create_access_token, get_password_hash  # noqa: E402
from app.main import app  # noqa: E402

# =============================================================================
# Session / Event-loop
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# App & Client
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.db.session import get_db
    from app.services.cache import get_cache_service
    from app.services.chat import ChatOrchestrator, get_chat_orchestrator
    from app.services.rate_limit import RateLimitService, get_rate_limit_service

    async def override_get_db():
        yield db

    mock_cache = make_mock_cache()
    mock_rate = MagicMock(spec=RateLimitService)
    mock_rate.is_enabled = False
    mock_rate.check_auth_limit = AsyncMock(return_value=(True, -1))
    mock_rate.check_general_limit = AsyncMock(return_value=(True, -1))
    mock_rate.check_chat_limit = AsyncMock(return_value=(True, -1))
    mock_rate.close = AsyncMock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service] = lambda: mock_cache
    app.dependency_overrides[get_rate_limit_service] = lambda: mock_rate
    app.dependency_overrides[get_chat_orchestrator] = lambda: ChatOrchestrator(
        cache_service=mock_cache,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# Users
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_user(db: AsyncSession) -> User:
    hashed = await get_password_hash("Testpassword123")
    user = User(email="test@example.com", username="testuser", hashed_password=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def second_user(db: AsyncSession) -> User:
    hashed = await get_password_hash("Secondpass123")
    user = User(email="second@example.com", username="seconduser", hashed_password=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, test_user: User) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Testpassword123"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_token(test_user: User) -> str:
    return create_access_token(data={"sub": str(test_user.id)})


@pytest.fixture
def auth_token_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


# =============================================================================
# Conversation / Message helpers
# =============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_conversation(db: AsyncSession, test_user: User) -> Conversation:
    conv = Conversation(id=str(uuid.uuid4()), user_id=test_user.id, title="Test Conversation")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@pytest_asyncio.fixture(scope="function")
async def conversation_with_messages(
    db: AsyncSession, test_conversation: Conversation,
) -> tuple[Conversation, list[Message]]:
    msgs = [
        Message(conversation_id=test_conversation.id, role="user", content="Hello"),
        Message(
            conversation_id=test_conversation.id,
            role="assistant",
            content="Hi there!",
            model_info={"provider": "gemini", "model": "gemini-2.5-flash"},
        ),
    ]
    db.add_all(msgs)
    await db.commit()
    for m in msgs:
        await db.refresh(m)
    return test_conversation, msgs


# =============================================================================
# Mock helpers
# =============================================================================

def make_mock_cache(available: bool = False, **overrides: Any) -> MagicMock:
    """Create a mock CacheService. All async methods return sensible defaults."""
    from app.services.cache import CacheService

    mock = MagicMock(spec=CacheService)
    mock.is_available = available

    # Read methods → None
    for meth in (
        "get_conversation_context",
        "get_user_messages",
        "get_conversation_history",
        "get_conversation_detail",
        "get_available_models",
        "get_sentiment_methods",
        "get_user_data",
    ):
        setattr(mock, meth, AsyncMock(return_value=None))

    # Write/invalidate methods → available flag
    for meth in (
        "set_conversation_context",
        "set_user_messages",
        "set_conversation_history",
        "set_conversation_detail",
        "set_available_models",
        "set_sentiment_methods",
        "set_user_data",
        "append_to_context",
        "append_user_message",
        "invalidate_conversation",
        "invalidate_user_history",
    ):
        setattr(mock, meth, AsyncMock(return_value=available))

    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock
