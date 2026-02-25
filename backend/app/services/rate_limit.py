"""Rate limiting service using Upstash Redis REST API.

Implements sliding window rate limiting with configurable limits
per endpoint and user. Uses direct REST API calls for async compatibility.

Optimized with:
- Persistent httpx.AsyncClient for connection reuse
- Connection pooling to reduce TCP handshake overhead
- Lazy client initialization
"""

import time
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitService:
    """Rate limiting service using Upstash Redis REST API.

    Uses persistent httpx.AsyncClient for connection reuse.
    """

    def __init__(self) -> None:
        """Initialize rate limit service."""
        settings = get_settings()
        self._enabled = settings.rate_limit_enabled and settings.redis_available
        self._url = settings.upstash_redis_rest_url
        self._token = settings.upstash_redis_rest_token
        self._general_limit = settings.rate_limit_requests_per_minute
        self._chat_limit = settings.rate_limit_chat_requests_per_minute
        self._auth_limit = settings.rate_limit_auth_requests_per_minute
        self._window_seconds = 60  # 1 minute window

        # Persistent HTTP client for connection reuse (reduces latency by ~50-100ms per request)
        self._client: httpx.AsyncClient | None = None

        if self._enabled:
            logger.info(
                "Rate limiting initialized",
                general_limit=self._general_limit,
                chat_limit=self._chat_limit,
            )
        else:
            logger.info("Rate limiting disabled")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent HTTP client.

        Uses connection pooling for better performance.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=2.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers={"Authorization": f"Bearer {self._token}"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled."""
        return self._enabled

    async def _check_limit(self, key: str, limit: int, *, fail_closed: bool = False) -> tuple[bool, int]:
        """Check rate limit using sliding window counter.

        Uses persistent connection for reduced latency.

        Args:
            key: Redis key for the rate limit counter
            limit: Maximum requests allowed in window

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        if not self._enabled:
            return True, -1

        try:
            current_time = int(time.time())
            window_start = current_time - self._window_seconds
            request_id = f"{current_time}:{id(current_time)}:{time.time_ns()}"

            # Use persistent client for connection reuse
            client = await self._get_client()

            # Pipeline: remove old entries, add new, set expiry, count
            response = await client.post(
                f"{self._url}/pipeline",
                json=[
                    ["ZREMRANGEBYSCORE", key, "0", str(window_start)],
                    ["ZADD", key, str(current_time), request_id],
                    ["EXPIRE", key, str(self._window_seconds * 2)],
                    ["ZCARD", key],
                ],
            )
            response.raise_for_status()
            results = response.json()

            # ZCARD result is the last item in pipeline
            count = results[-1].get("result", 0) if results else 0

            allowed = count <= limit
            remaining = max(0, limit - count)

            return allowed, remaining

        except Exception as e:
            logger.warning("Rate limit check failed", key=key, error=str(e))
            if fail_closed:
                return False, 0
            return True, -1  # Allow on error

    async def check_general_limit(self, identifier: str) -> tuple[bool, int]:
        """Check general API rate limit.

        Args:
            identifier: Unique identifier (user ID or IP)

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        key = f"ratelimit:general:{identifier}"
        return await self._check_limit(key, self._general_limit)

    async def check_chat_limit(self, identifier: str) -> tuple[bool, int]:
        """Check chat-specific rate limit.

        Args:
            identifier: Unique identifier (user ID)

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        key = f"ratelimit:chat:{identifier}"
        return await self._check_limit(key, self._chat_limit)

    async def check_auth_limit(self, identifier: str) -> tuple[bool, int]:
        """Check auth endpoint rate limit (fail-closed).

        For login/registration endpoints, denies requests when
        the rate limiter is unavailable to prevent brute-force attacks.

        Args:
            identifier: Unique identifier (IP address)

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        key = f"ratelimit:auth:{identifier}"
        return await self._check_limit(key, self._auth_limit, fail_closed=True)



@lru_cache
def get_rate_limit_service() -> RateLimitService:
    """Get or create the rate limit service instance (cached)."""
    return RateLimitService()
