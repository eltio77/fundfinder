from fundfinder.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_bucket_allows_capacity_then_waits_for_refill():
    clock = Clock()
    rl = RateLimiter(3, 60, clock=clock)  # one token every 20 s
    assert [rl.acquire("a") for _ in range(3)] == [0, 0, 0]
    assert rl.acquire("a") == 20
    clock.now = 10
    assert rl.acquire("a") == 10  # half a token back
    clock.now = 20
    assert rl.acquire("a") == 0


def test_buckets_are_per_key():
    rl = RateLimiter(1, clock=Clock())
    assert rl.acquire("a") == 0
    assert rl.acquire("a") > 0
    assert rl.acquire("b") == 0


def test_refill_never_exceeds_capacity():
    clock = Clock()
    rl = RateLimiter(2, 60, clock=clock)
    rl.acquire("a")
    clock.now = 3600
    assert [rl.acquire("a") for _ in range(2)] == [0, 0]
    assert rl.acquire("a") > 0


def test_zero_capacity_disables():
    rl = RateLimiter(0, clock=Clock())
    assert all(rl.acquire("a") == 0 for _ in range(100))


def test_key_count_is_bounded():
    rl = RateLimiter(1, max_keys=2, clock=Clock())
    for key in ("a", "b", "c"):
        rl.acquire(key)
    assert list(rl._buckets) == ["b", "c"]
    assert rl.acquire("a") == 0  # evicted, so it starts with a full bucket
