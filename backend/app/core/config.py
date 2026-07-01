from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    request_timeout_seconds: int = 30

    # --- LLM Provider selection ---
    llm_provider: str = "openrouter"  # "openrouter" | "gemini"

    # --- OpenRouter ---
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Gemini (up to 3 keys for automatic rotation on rate limits) ---
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""
    gemini_api_key_3: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # --- Batch processing tuning (free-tier rate-limit friendly) ---
    batch_max_concurrency: int = 2
    batch_request_delay_seconds: float = 1.5
    batch_max_retries_per_message: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gemini_api_keys(self) -> List[str]:
        """All configured Gemini keys, in fallback order, empty ones skipped."""
        return [k for k in (self.gemini_api_key, self.gemini_api_key_2, self.gemini_api_key_3) if k]


@lru_cache
def get_settings() -> Settings:
    return Settings()