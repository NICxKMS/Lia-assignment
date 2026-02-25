"""Tests for app.core.config.Settings."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

# Shared kwargs that satisfy required fields
_BASE: dict[str, Any] = {
    "jwt_secret_key": "a-valid-secret-key-that-is-long-enough-for-testing",
    "database_url": "postgresql+asyncpg://u:p@localhost/db",
}


class TestJwtSecretValidation:
    """Reject the known placeholder secret."""

    def test_placeholder_secret_rejected(self):
        with pytest.raises(ValidationError, match="jwt_secret_key must be changed"):
            Settings(
                jwt_secret_key="CHANGE-THIS-IN-PRODUCTION-USE-SECRETS-TOKEN",
                database_url="postgresql+asyncpg://u:p@localhost/db",
            )

    def test_valid_secret_accepted(self):
        s = Settings(**_BASE)
        assert len(s.jwt_secret_key) >= 32


class TestCorsOrigins:
    """cors_origins parses comma-separated string."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("http://a,http://b", ["http://a", "http://b"]),
            ("http://a , http://b ", ["http://a", "http://b"]),
            ("http://only", ["http://only"]),
            ("", []),
        ],
        ids=["basic", "whitespace", "single", "empty"],
    )
    def test_cors_parsing(self, raw: str, expected: list[str]):
        s = Settings(**_BASE, CORS_ORIGINS=raw)
        assert s.cors_origins == expected


class TestProcessedDatabaseUrl:
    """processed_database_url transforms connection strings."""

    @pytest.mark.parametrize(
        "input_url, must_contain, must_not_contain",
        [
            (
                "postgresql+asyncpg://u:p@host/db?sslmode=require",
                "ssl=require",
                "sslmode",
            ),
            (
                "postgresql+asyncpg://u:p@host/db?sslmode=verify-full",
                "ssl=verify-full",
                "sslmode",
            ),
            (
                "postgresql+asyncpg://u:p@host/db?pgbouncer=true",
                "postgresql",
                "pgbouncer",
            ),
            (
                "postgresql+asyncpg://u:p@host/db?a=1&pgbouncer=true",
                "a=1",
                "pgbouncer",
            ),
            (
                "postgresql+asyncpg://u:p@host/db?pgbouncer=true&b=2",
                "b=2",
                "pgbouncer",
            ),
        ],
        ids=["sslmode-require", "sslmode-verify-full", "pgbouncer-only", "pgbouncer-end", "pgbouncer-start"],
    )
    def test_url_transformation(self, input_url: str, must_contain: str, must_not_contain: str):
        s = Settings(**{**_BASE, "database_url": input_url})
        assert must_contain in s.processed_database_url
        assert must_not_contain not in s.processed_database_url


class TestRedisAvailable:
    """redis_available flag based on credentials."""

    def test_redis_available_when_both_set(self):
        s = Settings(
            **_BASE,
            upstash_redis_rest_url="https://redis.example.com",
            upstash_redis_rest_token="tok",
        )
        assert s.redis_available is True

    def test_redis_unavailable_when_url_missing(self):
        s = Settings(**_BASE, upstash_redis_rest_url="", upstash_redis_rest_token="tok")
        assert s.redis_available is False

    def test_redis_unavailable_when_token_missing(self):
        s = Settings(**_BASE, upstash_redis_rest_url="https://r.io", upstash_redis_rest_token="")
        assert s.redis_available is False

    def test_redis_unavailable_when_both_empty(self):
        s = Settings(**_BASE, upstash_redis_rest_url="", upstash_redis_rest_token="")
        assert s.redis_available is False


class TestDefaults:
    """Sensible default values."""

    def test_app_name(self):
        assert Settings(**_BASE).app_name == "Lia Chatbot"

    def test_environment_default(self):
        s = Settings(**_BASE, environment="development")
        assert s.environment == "development"

    def test_jwt_algorithm_default(self):
        assert Settings(**_BASE).jwt_algorithm == "HS256"

    def test_rate_limit_enabled_default(self):
        assert Settings(**_BASE).rate_limit_enabled is True
