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

    # Optional "Interpret with AI" search (fundfinder/llm_intent.py). Without a key the
    # toggle is unavailable and search uses the rule-based reading only.
    anthropic_api_key: SecretStr | None = None
    intent_model: str = "claude-haiku-5-5"
    intent_timeout_s: float = 10.0

    # Abuse limits (fundfinder/ratelimit.py), per instance; 0 turns one off. Searches
    # embed the query, so they cost Voyage quota; AI searches also call Claude. Repeat
    # AI readings of the same query are cached but still count.
    search_rate_per_min: int = 60  # per client IP: /search and /funds/{id}/similar
    llm_rate_per_min: int = 20  # per client IP: intent=llm
    llm_daily_budget: int = 1000  # all clients: intent=llm requests a day


@lru_cache
def get_settings() -> Settings:
    return Settings()
