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
