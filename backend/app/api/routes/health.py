"""Health check and monitoring endpoints.

Created by: Nikhil Kumar
GitHub: https://github.com/NICxKMS
LinkedIn: https://www.linkedin.com/in/nicx/
Email: admin@nicx.me
"""

import asyncio
import gc
import multiprocessing
import socket
import threading
from datetime import datetime, timezone
import os
import platform
import sys
import time
from typing import Any

# resource module is only available on Unix-like systems
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    resource = None  # type: ignore
    HAS_RESOURCE = False

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.schemas import CreatorInfo, HealthResponse, ServiceHealth
from app.core.config import get_settings
from app.db.session import check_db_health
from app.services.cache import get_cache_service

router = APIRouter(tags=["Health"])

# Track server start time for uptime calculation
_server_start_time = datetime.now(timezone.utc)

# Creator Information
CREATOR_INFO: dict[str, Any] = {
    "name": "Nikhil Kumar",
    "github": "https://github.com/NICxKMS",
    "linkedin": "https://www.linkedin.com/in/nicx/",
    "email": "admin@nicx.me",
}


def _get_memory_info() -> dict[str, Any]:
    """Get process memory information."""
    memory_info: dict[str, Any] = {}
    
    if HAS_RESOURCE and resource is not None:
        try:
            # Try to get resource usage on Unix-like systems
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            memory_info["max_rss_kb"] = rusage.ru_maxrss
            memory_info["shared_memory_kb"] = rusage.ru_ixrss
            memory_info["unshared_data_kb"] = rusage.ru_idrss
            memory_info["unshared_stack_kb"] = rusage.ru_isrss
            memory_info["page_faults"] = rusage.ru_majflt + rusage.ru_minflt
            memory_info["voluntary_context_switches"] = rusage.ru_nvcsw
            memory_info["involuntary_context_switches"] = rusage.ru_nivcsw
        except (AttributeError, OSError):
            # Resource module unavailable
            memory_info["note"] = "Detailed memory info not available on this platform"
    else:
        memory_info["note"] = "Detailed memory info not available on Windows"
    
    return memory_info


def _get_cpu_info() -> dict[str, Any]:
    """Get CPU information."""
    cpu_info: dict[str, Any] = {
        "processor": platform.processor() or "Unknown",
        "physical_cores": 1,
        "logical_cores": 1,
        "architecture": platform.machine(),
        "byte_order": sys.byteorder,
    }
    
    try:
        cpu_info["physical_cores"] = multiprocessing.cpu_count()
        cpu_info["logical_cores"] = os.cpu_count() or multiprocessing.cpu_count()
    except (NotImplementedError, OSError):
        pass
    
    # Platform-specific CPU info
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
                for line in cpuinfo.split("\n"):
                    if "model name" in line:
                        cpu_info["model_name"] = line.split(":")[1].strip()
                        break
        except (FileNotFoundError, PermissionError, OSError):
            pass
    
    return cpu_info


def _get_python_info() -> dict[str, Any]:
    """Get detailed Python runtime information."""
    return {
        "version": sys.version,
        "version_info": {
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "micro": sys.version_info.micro,
            "releaselevel": sys.version_info.releaselevel,
            "serial": sys.version_info.serial,
        },
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "build": platform.python_build(),
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "default_encoding": sys.getdefaultencoding(),
        "filesystem_encoding": sys.getfilesystemencoding(),
        "recursion_limit": sys.getrecursionlimit(),
        "float_info": {
            "max": sys.float_info.max,
            "min": sys.float_info.min,
            "epsilon": sys.float_info.epsilon,
            "dig": sys.float_info.dig,
        },
        "int_info": {
            "bits_per_digit": sys.int_info.bits_per_digit,
            "sizeof_digit": sys.int_info.sizeof_digit,
        },
        "hash_info": {
            "algorithm": sys.hash_info.algorithm,
            "hash_bits": sys.hash_info.hash_bits,
            "modulus": sys.hash_info.modulus,
        },
    }


def _get_process_info() -> dict[str, Any]:
    """Get current process information."""
    process_info: dict[str, Any] = {
        "pid": os.getpid(),
        "ppid": os.getppid() if hasattr(os, "getppid") else None,
        "cwd": os.getcwd(),
        "thread_count": threading.active_count(),
        "threads": [t.name for t in threading.enumerate()],
    }
    
    # User and group info (Unix-like systems)
    try:
        process_info["uid"] = os.getuid()
        process_info["gid"] = os.getgid()
        process_info["euid"] = os.geteuid()
        process_info["egid"] = os.getegid()
    except AttributeError:
        # Windows doesn't have these
        pass
    
    # File descriptors (Unix-like systems)
    try:
        fd_dir = f"/proc/{os.getpid()}/fd"
        if os.path.exists(fd_dir):
            process_info["open_file_descriptors"] = len(os.listdir(fd_dir))
    except (PermissionError, OSError):
        pass
    
    # Resource limits
    if HAS_RESOURCE and resource is not None:
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            process_info["file_descriptor_limit"] = {"soft": soft, "hard": hard}
        except (AttributeError, OSError):
            pass
    
    return process_info


def _get_network_info() -> dict[str, Any]:
    """Get network information."""
    network_info: dict[str, Any] = {
        "hostname": socket.gethostname(),
    }
    
    try:
        network_info["fqdn"] = socket.getfqdn()
    except (socket.error, OSError):
        pass
    
    # Get IP addresses
    try:
        network_info["ip_addresses"] = []
        hostname = socket.gethostname()
        addrs = socket.getaddrinfo(hostname, None)
        seen = set()
        for addr in addrs:
            ip = addr[4][0]
            if ip not in seen:
                seen.add(ip)
                network_info["ip_addresses"].append({
                    "address": ip,
                    "family": "IPv6" if addr[0] == socket.AF_INET6 else "IPv4",
                })
    except (socket.error, OSError):
        pass
    
    return network_info


def _get_environment_info() -> dict[str, Any]:
    """Get environment information (sanitized)."""
    # List of safe environment variables to expose
    safe_vars = [
        "PATH", "SHELL", "TERM", "LANG", "LC_ALL", "TZ", "HOME", "USER",
        "HOSTNAME", "PWD", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV",
        "NODE_ENV", "ENVIRONMENT", "RENDER", "RENDER_SERVICE_NAME",
        "RENDER_INSTANCE_ID", "RENDER_GIT_COMMIT", "RENDER_GIT_BRANCH",
    ]
    
    env_info: dict[str, Any] = {
        "variables_count": len(os.environ),
        "python_path_entries": len(sys.path),
        "safe_variables": {},
    }
    
    for var in safe_vars:
        if var in os.environ:
            env_info["safe_variables"][var] = os.environ[var]
    
    return env_info


def _get_runtime_info() -> dict[str, Any]:
    """Get runtime information about loaded modules and GC."""
    gc_stats = gc.get_stats()
    
    return {
        "loaded_modules_count": len(sys.modules),
        "sys_path_entries": len(sys.path),
        "garbage_collector": {
            "enabled": gc.isenabled(),
            "counts": gc.get_count(),
            "thresholds": gc.get_threshold(),
            "generations": [
                {
                    "generation": i,
                    "collections": stat.get("collections", 0),
                    "collected": stat.get("collected", 0),
                    "uncollectable": stat.get("uncollectable", 0),
                }
                for i, stat in enumerate(gc_stats)
            ],
        },
        "object_counts": {
            "total_objects": len(gc.get_objects()),
        },
    }


def _get_platform_info() -> dict[str, Any]:
    """Get detailed platform information."""
    platform_info: dict[str, Any] = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor() or "Unknown",
        "architecture": platform.architecture(),
        "platform": platform.platform(),
        "node": platform.node(),
    }
    
    # Linux-specific info
    if platform.system() == "Linux":
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    os_release = {}
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            os_release[key.lower()] = value.strip('"')
                    platform_info["os_release"] = os_release
        except (PermissionError, OSError):
            pass
        
        # Kernel info
        try:
            with open("/proc/version") as f:
                platform_info["kernel_version"] = f.read().strip()
        except (FileNotFoundError, PermissionError, OSError):
            pass
    
    # macOS-specific info
    if platform.system() == "Darwin":
        mac_ver = platform.mac_ver()
        if mac_ver[0]:
            platform_info["macos_version"] = mac_ver[0]
            platform_info["macos_version_info"] = mac_ver
    
    # Windows-specific info
    if platform.system() == "Windows":
        win_ver = platform.win32_ver()
        platform_info["windows_version"] = win_ver
        platform_info["windows_edition"] = platform.win32_edition() if hasattr(platform, "win32_edition") else None
    
    return platform_info


def _get_system_info() -> dict[str, Any]:
    """Get comprehensive system information for health endpoints."""
    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "platform_release": platform.release(),
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "Unknown",
        "cpu_count": os.cpu_count(),
        "byte_order": sys.byteorder,
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
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
    }


def _get_full_system_info() -> dict[str, Any]:
    """Get exhaustive system information."""
    return {
        "platform": _get_platform_info(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "python": _get_python_info(),
        "process": _get_process_info(),
        "network": _get_network_info(),
        "environment": _get_environment_info(),
        "runtime": _get_runtime_info(),
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
    - Creator information
    """
    settings = get_settings()
    
    return {
        "created_by": CREATOR_INFO,
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
    - Creator information
    
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
        created_by=CreatorInfo(**CREATOR_INFO),
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
async def liveness() -> dict[str, Any]:
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the service process is running.
    This is a lightweight check that doesn't verify external dependencies.
    
    Use this for container orchestration to determine if the process needs restart.
    """
    return {
        "created_by": CREATOR_INFO,
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
                "created_by": CREATOR_INFO,
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
                "created_by": CREATOR_INFO,
                "status": "not_ready",
                "reason": "database_unavailable",
                "message": "Database connection failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "created_by": CREATOR_INFO,
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get(
    "/health/info",
    summary="Comprehensive system information",
    response_description="Exhaustive system and runtime information",
)
async def system_info() -> dict[str, Any]:
    """
    Get exhaustive system and runtime information.
    
    Returns comprehensive details about:
    - **Application**: Name, version, environment
    - **Platform**: OS details, kernel, architecture
    - **CPU**: Cores, processor info, architecture
    - **Memory**: RSS, page faults, context switches
    - **Python**: Version, implementation, paths, encoding
    - **Process**: PID, threads, file descriptors
    - **Network**: Hostname, IP addresses
    - **Environment**: Safe variables, paths
    - **Runtime**: GC stats, loaded modules
    - **Uptime**: Start time, duration
    - **Creator**: Project author information
    """
    settings = get_settings()
    
    return {
        "created_by": CREATOR_INFO,
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
            "log_level": settings.log_level,
        },
        "system": _get_full_system_info(),
        "uptime": _get_uptime(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/info/summary",
    summary="System information summary",
    response_description="Brief system information summary",
)
async def system_info_summary() -> dict[str, Any]:
    """
    Get a brief summary of system information.
    
    Lighter-weight alternative to /health/info for quick checks.
    """
    settings = get_settings()
    
    return {
        "created_by": CREATOR_INFO,
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
    - Creator information
    """
    name, healthy, latency, error = await _timed_health_check("database", check_db_health)
    
    response_data: dict[str, Any] = {
        "created_by": CREATOR_INFO,
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
    - Creator information
    """
    cache_service = get_cache_service()
    
    if not cache_service.is_available:
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Cache is optional, degraded is OK
            content={
                "created_by": CREATOR_INFO,
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
        "created_by": CREATOR_INFO,
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
