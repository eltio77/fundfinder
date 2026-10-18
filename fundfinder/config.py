from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from the environment (or a local, uncommitted .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: SecretStr
    mongodb_db: str = "fund_finder"
    mongodb_timeout_ms: int = 5000

    # "auto": Atlas Automated Embedding (autoEmbed index, key registered in Atlas).
    # "client": fallback where the app calls Voyage itself and stores vectors.
    embedding_mode: Literal["auto", "client"] = "auto"
    embed_model: str = "voyage-4"
    voyage_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
