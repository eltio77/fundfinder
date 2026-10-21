"""Small in-process cache for search responses.

Results only change when the data is re-seeded, but every search embeds the query
(a Voyage call through Atlas, ~200 ms). Repeats (shared links, example searches,
going back, toggling a filter back) skip that. Per process, like the rate limits;
the CDN (Cache-Control on /search) covers repeats across instances.
"""

import time
from collections import OrderedDict
from collections.abc import Callable

SEARCH_CACHE_SIZE = 500
SEARCH_CACHE_TTL_S = 600.0


class TTLCache[V]:
    """Least-recently-used cache whose entries expire `ttl_s` after being stored."""

    def __init__(
        self,
        max_size: int = SEARCH_CACHE_SIZE,
        ttl_s: float = SEARCH_CACHE_TTL_S,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_size = max_size
        self.ttl_s = ttl_s
        self.clock = clock
        self._items: OrderedDict[str, tuple[float, V]] = OrderedDict()

    def get(self, key: str) -> V | None:
        item = self._items.get(key)
        if item is None:
            return None
        stored, value = item
        if self.clock() - stored > self.ttl_s:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return value

    def set(self, key: str, value: V) -> None:
        self._items[key] = (self.clock(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)
