"""Configuration management for Pixie AI Service.

Uses Pydantic Settings for type-safe configuration with .env file support.
All sensitive values are loaded from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    # LLM APIs
    openai_api_key: str = ""
    anthropic_api_key: str | None = None

    # Vector Database (Qdrant)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    # PostgreSQL (read-only access)
    database_url: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Service Configuration
    port: int = 8000
    allowed_origins: str = "http://localhost:3000"

    # Internal API Key (for Node.js backend communication)
    internal_api_key: str = ""

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse allowed origins as list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


settings = Settings()
