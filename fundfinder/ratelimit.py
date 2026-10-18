"""In-process rate limits for the public API.

Every search embeds the query (Voyage, via Atlas) and "Interpret with AI" also
calls Claude, so both cost money and share provider quotas with every other
user. Token buckets keep one client from using them all: per client IP for
search and for AI search, plus one global bucket as a budget on Claude calls.

State lives in the process, so each instance (and each Vercel instance) counts
separately; good enough for a prototype, not a substitute for a shared store.
"""

import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request

from fundfinder.config import Settings

DAY_S = 24 * 60 * 60
# Bounds memory if many addresses call once; an evicted client gets a full bucket.
MAX_CLIENTS = 10_000


class RateLimiter:
    """Token buckets per key: `capacity` requests at once, refilled evenly over
    `period_s`. capacity <= 0 disables the limit."""

    def __init__(
        self,
        capacity: int,
        period_s: float = 60.0,
        *,
        max_keys: int = MAX_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = capacity
        self.rate = capacity / period_s if capacity > 0 else 0.0  # tokens a second
        self.max_keys = max_keys
        self.clock = clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()  # tokens, at

    def acquire(self, key: str) -> float:
        """Takes a token for `key`: 0 if allowed, else seconds until one is free."""
        if self.capacity <= 0:
            return 0.0
        now = self.clock()
        tokens, at = self._buckets.pop(key, (float(self.capacity), now))
        tokens = min(self.capacity, tokens + (now - at) * self.rate)
        wait = 0.0
        if tokens >= 1:
            tokens -= 1
        else:
            wait = (1 - tokens) / self.rate
        self._buckets[key] = (tokens, now)
        if len(self._buckets) > self.max_keys:
            self._buckets.popitem(last=False)
        return wait


@dataclass
class Limits:
    search: RateLimiter  # per client: /search and /funds/{id}/similar
    llm: RateLimiter  # per client: intent=llm
    llm_budget: RateLimiter  # all clients together: intent=llm

    @classmethod
    def from_settings(cls, settings: Settings) -> "Limits":
        return cls(
            search=RateLimiter(settings.search_rate_per_min),
            llm=RateLimiter(settings.llm_rate_per_min),
            llm_budget=RateLimiter(settings.llm_daily_budget, DAY_S),
        )

    @classmethod
    def unlimited(cls) -> "Limits":
        return cls(RateLimiter(0), RateLimiter(0), RateLimiter(0))


def client_key(request: Request) -> str:
    # uvicorn runs with --proxy-headers, so this is the address Vercel puts in
    # X-Forwarded-For (Vercel overwrites any value the client sends).
    return request.client.host if request.client else "unknown"


def too_many(wait: float, detail: str) -> HTTPException:
    return HTTPException(429, detail, headers={"Retry-After": str(max(1, math.ceil(wait)))})


def get_limits(request: Request) -> Limits:
    limits = getattr(request.app.state, "limits", None)
    return limits if limits is not None else Limits.unlimited()


def limit_search(request: Request) -> None:
    """Dependency for the endpoints that embed text."""
    if wait := get_limits(request).search.acquire(client_key(request)):
        raise too_many(wait, "too many searches, retry later")


def limit_llm(request: Request) -> None:
    """Called before each AI reading. The per-client check runs first so one busy
    client can't drain the shared budget while being refused."""
    limits = get_limits(request)
    if wait := limits.llm.acquire(client_key(request)):
        raise too_many(wait, "too many AI searches, retry later")
    if wait := limits.llm_budget.acquire("*"):
        raise too_many(wait, "AI search budget used up, retry later")
