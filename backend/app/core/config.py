"""Application configuration using pydantic-settings.

Provides type-safe, validated configuration from environment variables
with sensible defaults for development.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========== Database (Neon PostgreSQL) ==========
    database_url: str = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/lia",
        description="Async PostgreSQL connection string",
    )
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_timeout: int = Field(default=30, ge=5, le=120)
    db_echo: bool = Field(default=False, description="Echo SQL queries")

    # ========== Cache (Upstash Redis) ==========
    upstash_redis_rest_url: str = Field(default="", description="Upstash Redis REST URL")
    upstash_redis_rest_token: str = Field(default="", description="Upstash Redis REST Token")

    # ========== Authentication ==========
    jwt_secret_key: str = Field(
        ...,
        min_length=32,
        description="JWT signing secret key",
    )
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode='after')
    def _reject_placeholder_jwt_secret(self) -> 'Settings':
        if self.jwt_secret_key == "CHANGE-THIS-IN-PRODUCTION-USE-SECRETS-TOKEN":
            raise ValueError(
                "jwt_secret_key must be changed from the placeholder value. "
                "Set JWT_SECRET_KEY environment variable to a secure random string."
            )
        return self

    # ========== LLM Providers ==========
    gemini_api_key: str = Field(default="", description="Google Gemini API Key")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    default_llm_provider: Literal["gemini", "openai"] = "gemini"
    default_llm_model: str = "gemini-2.5-flash"

    # ========== Google Cloud (Optional) ==========
    google_cloud_project_id: str = Field(default="", description="GCP Project ID for NLP API")

    # ========== Cookie Settings ==========
    cookie_name: str = Field(default="access_token", description="Cookie name for JWT")
    cookie_secure: bool = Field(default=True, description="Secure flag for cookies")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(default="lax", description="SameSite policy")
    cookie_domain: str | None = Field(default=None, description="Cookie domain")

    # ========== CORS ==========
    cors_origins_str: str = Field(
        default="http://localhost:5173,http://localhost:3000,https://lia.nicx.app",
        alias="CORS_ORIGINS",
        description="Comma-separated CORS origins",
    )

    # ========== Rate Limiting ==========
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60, ge=1)
    rate_limit_chat_requests_per_minute: int = Field(default=20, ge=1)

    # ========== Application ==========
    app_name: str = "Lia Chatbot"
    app_version: str = "2.5.1"
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # ========== Observability ==========
    otel_exporter_otlp_endpoint: str = Field(default="", description="OTLP endpoint for tracing")
    otel_service_name: str = "lia-backend"

    # ========== Computed Properties ==========
    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    @computed_field
    @property
    def redis_available(self) -> bool:
        """Check if Redis credentials are configured."""
        return bool(self.upstash_redis_rest_url and self.upstash_redis_rest_token)

    @computed_field
    @property
    def processed_database_url(self) -> str:
        """Convert database URL for asyncpg compatibility with Neon / Supabase."""
        url = self.database_url
        # Neon uses sslmode, asyncpg uses ssl
        replacements = [
            ("sslmode=require", "ssl=require"),
            ("sslmode=prefer", "ssl=prefer"),
            ("sslmode=verify-full", "ssl=verify-full"),
        ]
        for old, new in replacements:
            url = url.replace(old, new)
        # Ensure pgbouncer flag for Supabase pooler connections
        if "pooler.supabase.com" in url and "pgbouncer=true" not in url:
            separator = "&" if "?" in url else "?"
            url += f"{separator}pgbouncer=true"
        return url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
