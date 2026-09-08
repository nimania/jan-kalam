"""Application configuration.

All settings come from environment variables (or a local .env file). No secret
is ever hard-coded. See .env.example for the documented set.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "Jan Kalam"
    environment: str = Field(default="development")  # development | test | production
    debug: bool = Field(default=True)
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    # Production targets Postgres; tests/dev fall back to a local SQLite file so
    # the suite runs with zero external services.
    database_url: str = Field(default="sqlite:///./jankalam.db")

    # --- AI providers (used from Phase 4; never exposed to clients) ---
    ai_provider: str = Field(default="none")  # none | anthropic | gemini | openai
    ai_api_key: str | None = Field(default=None)
    ai_model_cheap: str = Field(default="")
    ai_model_strong: str = Field(default="")
    # Cost tracking (USD per million tokens). Defaults 0 so the mock is free.
    ai_price_in_per_mtok: float = Field(default=0.0)
    ai_price_out_per_mtok: float = Field(default=0.0)

    # --- Ingestion ---
    ingest_poll_interval_seconds: int = Field(default=900)
    ingest_user_agent: str = Field(default="JanKalamBot/0.1 (+https://jankalam.app)")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
