from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment (or a local, uncommitted .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Optional so the app still boots (and /health says why) when it's missing.
    mongodb_uri: SecretStr | None = None
    mongodb_db: str = "fund_finder"
    mongodb_timeout_ms: int = 5000

    # Voyage model for the autoEmbed index and query-time embedding. Embedding runs
    # inside mongot (Atlas or local), so the app itself never holds a Voyage key.
    embed_model: str = "voyage-4"


@lru_cache
def get_settings() -> Settings:
    return Settings()
