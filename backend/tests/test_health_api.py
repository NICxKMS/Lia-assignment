"""Health API endpoint tests.

Tests for: root, health, liveness, readiness, info, db check, cache check.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# =============================================================================
# No-auth smoke tests (parametrized)
# =============================================================================


@pytest.mark.parametrize("endpoint", [
    "/",
    "/health",
    "/health/live",
    "/health/ready",
    "/health/info",
    "/health/db",
    "/health/cache",
])
async def test_health_no_auth_required(client: AsyncClient, endpoint: str):
    resp = await client.get(endpoint)
    assert resp.status_code == 200


# =============================================================================
# Root
# =============================================================================


async def test_root_status_and_version(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "name" in data
    assert "created_by" in data


# =============================================================================
# Health
# =============================================================================


async def test_health_response_structure(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "services" in data
    assert "version" in data
    assert "timestamp" in data
    assert "created_by" in data


async def test_health_contains_db_service(client: AsyncClient):
    resp = await client.get("/health")
    data = resp.json()
    assert "database" in data["services"]


# =============================================================================
# Liveness
# =============================================================================


async def test_liveness_ok(client: AsyncClient):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# =============================================================================
# Readiness
# =============================================================================


async def test_readiness_success(client: AsyncClient):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


# =============================================================================
# Info
# =============================================================================


async def test_info_system_data(client: AsyncClient):
    resp = await client.get("/health/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "system" in data
    assert "application" in data
    assert "uptime" in data
    assert "created_by" in data


# =============================================================================
# DB Check
# =============================================================================


async def test_db_check_healthy(client: AsyncClient):
    resp = await client.get("/health/db")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "latency_ms" in data


# =============================================================================
# Cache Check
# =============================================================================


async def test_cache_check(client: AsyncClient):
    resp = await client.get("/health/cache")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "cache"
    assert "status" in data


# =============================================================================
# DB Failure Path
# =============================================================================


async def test_health_db_failure_degraded(client: AsyncClient):
    with patch("app.api.routes.health.check_db_health", new_callable=AsyncMock, return_value=False):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("unhealthy", "degraded")
        assert data["services"]["database"]["status"] == "unhealthy"


async def test_db_check_failure(client: AsyncClient):
    with patch("app.api.routes.health.check_db_health", new_callable=AsyncMock, return_value=False):
        resp = await client.get("/health/db")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"


async def test_readiness_db_failure(client: AsyncClient):
    with patch("app.api.routes.health.check_db_health", new_callable=AsyncMock, return_value=False):
        resp = await client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "not_ready"


# =============================================================================
# Response format checks
# =============================================================================


@pytest.mark.parametrize("endpoint,key", [
    ("/", "created_by"),
    ("/health", "created_by"),
    ("/health/live", "created_by"),
    ("/health/db", "created_by"),
])
async def test_endpoints_include_creator(client: AsyncClient, endpoint: str, key: str):
    resp = await client.get(endpoint)
    assert resp.status_code == 200
    data = resp.json()
    assert key in data
    assert data[key]["name"] == "Nikhil Kumar"
