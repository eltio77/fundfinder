from fundfinder.cache import TTLCache


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_entries_expire_after_ttl():
    clock = Clock()
    cache = TTLCache(ttl_s=10, clock=clock)
    cache.set("a", 1)
    clock.now = 10
    assert cache.get("a") == 1
    clock.now = 10.1
    assert cache.get("a") is None
    assert len(cache) == 0


def test_least_recently_used_is_evicted():
    cache = TTLCache(max_size=2, clock=Clock())
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # "b" is now the least recently used
    cache.set("c", 3)
    assert cache.get("b") is None
    assert (cache.get("a"), cache.get("c")) == (1, 3)
