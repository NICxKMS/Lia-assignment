"""Comprehensive tests for health check endpoints.

Tests cover:
- Root endpoint
- Health check with service status
- Liveness probe (Kubernetes)
- Readiness probe (Kubernetes)
- Response schemas
"""

import pytest
from httpx import AsyncClient


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_200(self, client: AsyncClient):
        """Test root endpoint returns 200 OK."""
        response = await client.get("/")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_root_contains_app_info(self, client: AsyncClient):
        """Test root endpoint contains application info."""
        response = await client.get("/")
        data = response.json()
        
        assert "name" in data
        assert "version" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_root_timestamp_format(self, client: AsyncClient):
        """Test root endpoint timestamp is ISO format."""
        response = await client.get("/")
        data = response.json()
        
        # Should be ISO 8601 format
        assert "T" in data["timestamp"]
        assert data["timestamp"].endswith("Z") or "+" in data["timestamp"]


class TestHealthEndpoint:
    """Tests for the comprehensive health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient):
        """Test health endpoint returns 200 OK."""
        response = await client.get("/health")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_contains_required_fields(self, client: AsyncClient):
        """Test health response contains all required fields."""
        response = await client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data

    @pytest.mark.asyncio
    async def test_health_status_values(self, client: AsyncClient):
        """Test health status is one of valid values."""
        response = await client.get("/health")
        data = response.json()
        
        assert data["status"] in ["healthy", "unhealthy", "degraded"]

    @pytest.mark.asyncio
    async def test_health_services_structure(self, client: AsyncClient):
        """Test health services have proper structure."""
        response = await client.get("/health")
        data = response.json()
        
        services = data["services"]
        
        # Should have database service
        assert "database" in services
        db_health = services["database"]
        assert "status" in db_health
        assert db_health["status"] in ["healthy", "unhealthy", "degraded"]

    @pytest.mark.asyncio
    async def test_health_cache_service_present(self, client: AsyncClient):
        """Test health check includes cache service info."""
        response = await client.get("/health")
        data = response.json()
        
        # Cache should always be present (even if degraded/not configured)
        assert "cache" in data["services"]
        cache_health = data["services"]["cache"]
        assert "status" in cache_health

    @pytest.mark.asyncio
    async def test_health_latency_tracking(self, client: AsyncClient):
        """Test health check includes latency metrics."""
        response = await client.get("/health")
        data = response.json()
        
        # Database should have latency (if healthy)
        db_health = data["services"]["database"]
        if db_health["status"] == "healthy":
            assert "latency_ms" in db_health
            assert db_health["latency_ms"] >= 0


class TestLivenessProbe:
    """Tests for Kubernetes liveness probe endpoint."""

    @pytest.mark.asyncio
    async def test_liveness_returns_200(self, client: AsyncClient):
        """Test liveness probe returns 200 OK."""
        response = await client.get("/health/live")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_liveness_status_ok(self, client: AsyncClient):
        """Test liveness probe returns status ok."""
        response = await client.get("/health/live")
        data = response.json()
        
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_liveness_fast_response(self, client: AsyncClient):
        """Test liveness probe responds quickly (no heavy checks)."""
        import time
        
        start = time.perf_counter()
        response = await client.get("/health/live")
        elapsed = time.perf_counter() - start
        
        assert response.status_code == 200
        # Should be very fast (< 100ms)
        assert elapsed < 0.1


class TestReadinessProbe:
    """Tests for Kubernetes readiness probe endpoint."""

    @pytest.mark.asyncio
    async def test_readiness_returns_200(self, client: AsyncClient):
        """Test readiness probe returns 200 OK when ready."""
        response = await client.get("/health/ready")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_status_present(self, client: AsyncClient):
        """Test readiness probe includes status."""
        response = await client.get("/health/ready")
        data = response.json()
        
        assert "status" in data

    @pytest.mark.asyncio
    async def test_readiness_checks_database(self, client: AsyncClient):
        """Test readiness probe checks database connectivity."""
        response = await client.get("/health/ready")
        
        # If we get here with 200, database is working
        assert response.status_code == 200
        
        data = response.json()
        # Status should be "ready" if DB is healthy
        if response.status_code == 200:
            assert data["status"] == "ready"


class TestHealthEndpointNoAuth:
    """Tests verifying health endpoints don't require auth."""

    @pytest.mark.asyncio
    async def test_root_no_auth_required(self, client: AsyncClient):
        """Test root endpoint doesn't require authentication."""
        response = await client.get("/")
        
        # Should not be 401 Unauthorized
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client: AsyncClient):
        """Test health endpoint doesn't require authentication."""
        response = await client.get("/health")
        
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_liveness_no_auth_required(self, client: AsyncClient):
        """Test liveness probe doesn't require authentication."""
        response = await client.get("/health/live")
        
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_readiness_no_auth_required(self, client: AsyncClient):
        """Test readiness probe doesn't require authentication."""
        response = await client.get("/health/ready")
        
        assert response.status_code != 401


class TestSystemInfoEndpoint:
    """Tests for the system information endpoint."""

    @pytest.mark.asyncio
    async def test_info_returns_200(self, client: AsyncClient):
        """Test info endpoint returns 200 OK."""
        response = await client.get("/health/info")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_info_contains_application_data(self, client: AsyncClient):
        """Test info endpoint contains application metadata."""
        response = await client.get("/health/info")
        data = response.json()
        
        assert "application" in data
        app = data["application"]
        assert "name" in app
        assert "version" in app
        assert "environment" in app

    @pytest.mark.asyncio
    async def test_info_contains_system_data(self, client: AsyncClient):
        """Test info endpoint contains system information."""
        response = await client.get("/health/info")
        data = response.json()
        
        assert "system" in data
        sys_info = data["system"]
        assert "hostname" in sys_info
        assert "platform" in sys_info
        assert "python_version" in sys_info

    @pytest.mark.asyncio
    async def test_info_contains_uptime(self, client: AsyncClient):
        """Test info endpoint contains uptime data."""
        response = await client.get("/health/info")
        data = response.json()
        
        assert "uptime" in data
        uptime = data["uptime"]
        assert "started_at" in uptime
        assert "uptime_seconds" in uptime
        assert "uptime_human" in uptime
        assert uptime["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_info_no_auth_required(self, client: AsyncClient):
        """Test info endpoint doesn't require authentication."""
        response = await client.get("/health/info")
        
        assert response.status_code != 401


class TestDatabaseHealthEndpoint:
    """Tests for the database health check endpoint."""

    @pytest.mark.asyncio
    async def test_db_health_returns_200_when_healthy(self, client: AsyncClient):
        """Test database health endpoint returns 200 when DB is healthy."""
        response = await client.get("/health/db")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_db_health_contains_required_fields(self, client: AsyncClient):
        """Test database health response contains all required fields."""
        response = await client.get("/health/db")
        data = response.json()
        
        assert data["service"] == "database"
        assert data["type"] == "postgresql"
        assert "status" in data
        assert "latency_ms" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_db_health_latency_positive(self, client: AsyncClient):
        """Test database health latency is a positive number."""
        response = await client.get("/health/db")
        data = response.json()
        
        assert data["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_db_health_no_auth_required(self, client: AsyncClient):
        """Test database health endpoint doesn't require authentication."""
        response = await client.get("/health/db")
        
        assert response.status_code != 401


class TestCacheHealthEndpoint:
    """Tests for the cache health check endpoint."""

    @pytest.mark.asyncio
    async def test_cache_health_returns_200(self, client: AsyncClient):
        """Test cache health endpoint returns 200 (cache is optional)."""
        response = await client.get("/health/cache")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cache_health_contains_required_fields(self, client: AsyncClient):
        """Test cache health response contains all required fields."""
        response = await client.get("/health/cache")
        data = response.json()
        
        assert data["service"] == "cache"
        assert data["type"] == "redis"
        assert "status" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_cache_health_status_valid(self, client: AsyncClient):
        """Test cache health status is a valid value."""
        response = await client.get("/health/cache")
        data = response.json()
        
        assert data["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_cache_health_no_auth_required(self, client: AsyncClient):
        """Test cache health endpoint doesn't require authentication."""
        response = await client.get("/health/cache")
        
        assert response.status_code != 401


class TestRootEndpointEnriched:
    """Tests for the enriched root endpoint."""

    @pytest.mark.asyncio
    async def test_root_contains_environment(self, client: AsyncClient):
        """Test root endpoint contains environment info."""
        response = await client.get("/")
        data = response.json()
        
        assert "environment" in data
        assert data["environment"] in ["development", "staging", "production"]

    @pytest.mark.asyncio
    async def test_root_contains_documentation_link(self, client: AsyncClient):
        """Test root endpoint contains documentation link."""
        response = await client.get("/")
        data = response.json()
        
        assert "documentation" in data
        assert data["documentation"] == "/docs"


class TestLivenessEnriched:
    """Tests for the enriched liveness probe."""

    @pytest.mark.asyncio
    async def test_liveness_contains_timestamp(self, client: AsyncClient):
        """Test liveness probe includes timestamp."""
        response = await client.get("/health/live")
        data = response.json()
        
        assert "timestamp" in data
        assert "T" in data["timestamp"]


class TestReadinessEnriched:
    """Tests for the enriched readiness probe."""

    @pytest.mark.asyncio
    async def test_readiness_contains_timestamp(self, client: AsyncClient):
        """Test readiness probe includes timestamp."""
        response = await client.get("/health/ready")
        data = response.json()
        
        assert "timestamp" in data
