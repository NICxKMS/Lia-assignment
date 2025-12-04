"""Health check and monitoring endpoints."""

import asyncio
from datetime import datetime, timezone
import time

from fastapi import APIRouter

from app.api.schemas import HealthResponse, ServiceHealth
from app.core.config import get_settings
from app.db.session import check_db_health
from app.services.cache import get_cache_service

router = APIRouter(tags=["Health"])


@router.get(
    "/",
    summary="Root endpoint",
)
async def root():
    """Root endpoint with API information."""
    settings = get_settings()
    
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _timed_health_check(name: str, check_fn, timeout: float = 5.0) -> tuple[str, bool, float]:
    """Execute a health check and measure its latency with timeout.
    
    Returns:
        Tuple of (name, healthy, latency_ms)
    """
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(check_fn(), timeout=timeout)
        latency = (time.perf_counter() - start) * 1000
        return (name, result, latency)
    except asyncio.TimeoutError:
        latency = (time.perf_counter() - start) * 1000
        return (name, False, latency)
    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return (name, False, latency)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
)
async def health_check() -> HealthResponse:
    """
    Comprehensive health check endpoint for monitoring.
    
    Checks:
    - Database connectivity
    - Redis cache connectivity
    
    Returns overall status and individual service status.
    Health checks are run in parallel with accurate per-service latency tracking.
    """
    settings = get_settings()
    services: dict[str, ServiceHealth] = {}
    overall_status = "healthy"

    cache_service = get_cache_service()
    
    # Run health checks in parallel with accurate latency tracking
    tasks = [_timed_health_check("database", check_db_health)]
    
    if cache_service.is_available:
        tasks.append(_timed_health_check("cache", cache_service.check_health))
    
    # Execute all checks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for result in results:
        if isinstance(result, Exception):
            continue
            
        name, healthy, latency = result
        
        if name == "database":
            services["database"] = ServiceHealth(
                status="healthy" if healthy else "unhealthy",
                latency_ms=round(latency, 2),
                details={"type": "postgresql"},
            )
            if not healthy:
                overall_status = "unhealthy"
                
        elif name == "cache":
            services["cache"] = ServiceHealth(
                status="healthy" if healthy else "degraded",
                latency_ms=round(latency, 2),
                details={"type": "redis", "provider": "upstash"},
            )
            if not healthy and overall_status == "healthy":
                overall_status = "degraded"
    
    # Handle cache not configured case
    if "cache" not in services:
        services["cache"] = ServiceHealth(
            status="degraded",
            details={"type": "redis", "provider": "not configured"},
        )
        if overall_status == "healthy":
            overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        version=settings.app_version,
        services=services,
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
)
async def liveness():
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the service is running.
    """
    return {"status": "ok"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
)
async def readiness():
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the service is ready to handle requests.
    Checks database connectivity with timeout.
    """
    try:
        db_healthy = await asyncio.wait_for(check_db_health(), timeout=5.0)
    except asyncio.TimeoutError:
        return {"status": "not ready", "reason": "database check timed out"}
    
    if not db_healthy:
        return {"status": "not ready", "reason": "database unavailable"}
    
    return {"status": "ready"}
