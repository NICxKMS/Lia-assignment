"""Health check and monitoring endpoints."""

import asyncio
from datetime import datetime, timezone
import os
import platform
import sys
import time
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.schemas import HealthResponse, ServiceHealth
from app.core.config import get_settings
from app.db.session import check_db_health
from app.services.cache import get_cache_service

router = APIRouter(tags=["Health"])

# Track server start time for uptime calculation
_server_start_time = datetime.now(timezone.utc)


def _get_system_info() -> dict[str, Any]:
    """Get system information for health endpoints."""
    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": sys.version.split()[0],
        "architecture": platform.machine(),
    }


def _get_uptime() -> dict[str, Any]:
    """Calculate server uptime."""
    now = datetime.now(timezone.utc)
    delta = now - _server_start_time
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return {
        "started_at": _server_start_time.isoformat(),
        "uptime_seconds": int(delta.total_seconds()),
        "uptime_human": f"{days}d {hours}h {minutes}m {seconds}s",
    }


@router.get(
    "/",
    summary="Root endpoint",
    response_description="API information and basic health status",
)
async def root() -> dict[str, Any]:
    """
    Root endpoint with API information.
    
    Returns basic API metadata including:
    - Application name and version
    - Current status
    - Environment name
    - Server timestamp
    """
    settings = get_settings()
    
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "documentation": "/docs",
    }


async def _timed_health_check(
    name: str, 
    check_fn: Any, 
    timeout: float = 5.0
) -> tuple[str, bool, float, str | None]:
    """Execute a health check and measure its latency with timeout.
    
    Returns:
        Tuple of (name, healthy, latency_ms, error_message)
    """
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(check_fn(), timeout=timeout)
        latency = (time.perf_counter() - start) * 1000
        return (name, result, latency, None)
    except asyncio.TimeoutError:
        latency = (time.perf_counter() - start) * 1000
        return (name, False, latency, f"Health check timed out after {timeout}s")
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return (name, False, latency, str(e))


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Comprehensive health check",
    response_description="Detailed health status of all services",
)
async def health_check() -> HealthResponse:
    """
    Comprehensive health check endpoint for monitoring.
    
    Checks all critical services:
    - **Database**: PostgreSQL connectivity and response time
    - **Cache**: Redis/Upstash connectivity and response time
    
    Returns:
    - Overall system status (healthy/degraded/unhealthy)
    - Individual service status with latency metrics
    - System uptime information
    
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
    
    # Process results - type narrowing for mypy
    for result in results:
        if isinstance(result, BaseException):
            continue
        
        # result is now tuple[str, bool, float, str | None]
        name, healthy, latency, error = result
        
        if name == "database":
            details: dict[str, Any] = {"type": "postgresql"}
            if error:
                details["error"] = error
            services["database"] = ServiceHealth(
                status="healthy" if healthy else "unhealthy",
                latency_ms=round(latency, 2),
                details=details,
            )
            if not healthy:
                overall_status = "unhealthy"
                
        elif name == "cache":
            cache_details: dict[str, Any] = {"type": "redis", "provider": "upstash"}
            if error:
                cache_details["error"] = error
            services["cache"] = ServiceHealth(
                status="healthy" if healthy else "degraded",
                latency_ms=round(latency, 2),
                details=cache_details,
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
    response_description="Simple liveness check for orchestrators",
)
async def liveness() -> dict[str, str]:
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the service process is running.
    This is a lightweight check that doesn't verify external dependencies.
    
    Use this for container orchestration to determine if the process needs restart.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/ready",
    summary="Readiness probe",
    response_description="Readiness check for load balancers",
)
async def readiness() -> JSONResponse:
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the service is ready to handle requests.
    Checks critical dependencies (database) with timeout.
    
    Use this for load balancer routing decisions.
    Returns 503 Service Unavailable if not ready.
    """
    try:
        db_healthy = await asyncio.wait_for(check_db_health(), timeout=5.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "reason": "database_timeout",
                "message": "Database health check timed out after 5s",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    if not db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "reason": "database_unavailable",
                "message": "Database connection failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get(
    "/health/info",
    summary="System information",
    response_description="Detailed system and runtime information",
)
async def system_info() -> dict[str, Any]:
    """
    Get detailed system and runtime information.
    
    Returns:
    - Application metadata (name, version, environment)
    - System information (hostname, platform, Python version)
    - Uptime information
    """
    settings = get_settings()
    
    return {
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
        "system": _get_system_info(),
        "uptime": _get_uptime(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/db",
    summary="Database health check",
    response_description="Detailed database connectivity status",
)
async def database_health() -> JSONResponse:
    """
    Check database connectivity and response time.
    
    Returns detailed database health information including:
    - Connection status
    - Response latency
    - Error details if unhealthy
    """
    name, healthy, latency, error = await _timed_health_check("database", check_db_health)
    
    response_data: dict[str, Any] = {
        "service": "database",
        "type": "postgresql",
        "status": "healthy" if healthy else "unhealthy",
        "latency_ms": round(latency, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if error:
        response_data["error"] = error
    
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=response_data)


@router.get(
    "/health/cache",
    summary="Cache health check",
    response_description="Detailed cache connectivity status",
)
async def cache_health() -> JSONResponse:
    """
    Check cache (Redis/Upstash) connectivity and response time.
    
    Returns detailed cache health information including:
    - Connection status  
    - Response latency
    - Provider information
    - Error details if unhealthy
    """
    cache_service = get_cache_service()
    
    if not cache_service.is_available:
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Cache is optional, degraded is OK
            content={
                "service": "cache",
                "type": "redis",
                "provider": "not configured",
                "status": "degraded",
                "message": "Cache service is not configured",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    name, healthy, latency, error = await _timed_health_check("cache", cache_service.check_health)
    
    response_data: dict[str, Any] = {
        "service": "cache",
        "type": "redis",
        "provider": "upstash",
        "status": "healthy" if healthy else "degraded",
        "latency_ms": round(latency, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if error:
        response_data["error"] = error
    
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_data)
