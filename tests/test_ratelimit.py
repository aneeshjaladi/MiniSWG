import asyncio
import pytest
from miniswg.ratelimit import TokenBucket, RateLimiter
from miniswg.policy import Policy
from miniswg.proxy import (
    set_rate_limiter,
    get_rate_limiter,
    set_policy,
    handle_client_inner,
)


class FakeClock:
    """Deterministic fake clock for testing rate limiter time progression."""

    def __init__(self, start: float = 1000.0) -> None:
        self.current = float(start)

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += float(seconds)


def test_burst_allowed():
    clock = FakeClock(1000.0)
    limiter = RateLimiter(rate=1.0, burst=5.0, time_func=clock)

    # All 5 burst requests must be allowed immediately
    for i in range(5):
        allowed, retry_after = limiter.check("192.168.1.1")
        assert allowed is True
        assert retry_after == 0.0

    # 6th request exceeding burst must be denied
    allowed, retry_after = limiter.check("192.168.1.1")
    assert allowed is False
    assert retry_after > 0.0


def test_refill_over_time():
    clock = FakeClock(1000.0)
    limiter = RateLimiter(rate=2.0, burst=4.0, time_func=clock)

    # Exhaust all 4 tokens
    for _ in range(4):
        allowed, _ = limiter.check("192.168.1.1")
        assert allowed is True

    # Immediate next request is rejected
    allowed, retry_after = limiter.check("192.168.1.1")
    assert allowed is False
    assert retry_after == 0.5  # 1 token needed at 2 tokens/sec = 0.5s

    # Advance clock by 1.0 second -> exactly 2 tokens should refill
    clock.advance(1.0)

    # 2 requests succeed
    allowed1, _ = limiter.check("192.168.1.1")
    allowed2, _ = limiter.check("192.168.1.1")
    assert allowed1 is True
    assert allowed2 is True

    # 3rd request is rejected
    allowed3, _ = limiter.check("192.168.1.1")
    assert allowed3 is False


def test_bucket_cap():
    clock = FakeClock(1000.0)
    limiter = RateLimiter(rate=2.0, burst=5.0, time_func=clock)

    # Consume 2 tokens
    assert limiter.check("192.168.1.1")[0] is True
    assert limiter.check("192.168.1.1")[0] is True

    # Fast forward clock by 100,000 seconds (huge idle time)
    clock.advance(100_000.0)

    # Tokens must be capped at burst (5.0), not 200,000 tokens!
    for _ in range(5):
        allowed, _ = limiter.check("192.168.1.1")
        assert allowed is True

    # 6th request must be rejected
    allowed, retry_after = limiter.check("192.168.1.1")
    assert allowed is False
    assert retry_after > 0.0


def test_idle_bucket_cleanup():
    clock = FakeClock(1000.0)
    limiter = RateLimiter(
        rate=1.0,
        burst=10.0,
        idle_timeout=60.0,
        cleanup_interval=10.0,
        time_func=clock,
    )

    # Client A and Client B make requests at t=1000
    limiter.check("client_a")
    clock.advance(10.0)  # t=1010
    limiter.check("client_b")

    assert len(limiter) == 2
    assert "client_a" in limiter
    assert "client_b" in limiter

    # Advance clock to t=1065 (65 seconds since client_a, 55 seconds since client_b)
    clock.advance(55.0)

    # Client C arrives at t=1065, triggering cleanup check
    limiter.check("client_c")

    # Client A has been idle for 65s (> 60s timeout) -> must be pruned
    # Client B has been idle for 55s (< 60s timeout) -> must be retained
    assert "client_a" not in limiter
    assert "client_b" in limiter
    assert "client_c" in limiter
    assert len(limiter) == 2


def test_per_client_ip_isolation():
    clock = FakeClock(1000.0)
    limiter = RateLimiter(rate=1.0, burst=2.0, time_func=clock)

    # Client 1 exhausts their burst
    assert limiter.check("1.1.1.1")[0] is True
    assert limiter.check("1.1.1.1")[0] is True
    assert limiter.check("1.1.1.1")[0] is False

    # Client 2 is isolated and still has full burst available
    assert limiter.check("2.2.2.2")[0] is True
    assert limiter.check("2.2.2.2")[0] is True
    assert limiter.check("2.2.2.2")[0] is False


def test_from_config():
    clock = FakeClock(1000.0)
    config = {"requests_per_minute": 120, "burst": 20}
    limiter = RateLimiter.from_config(config, time_func=clock)

    assert limiter.rate == 2.0  # 120 / 60
    assert limiter.burst == 20.0


@pytest.mark.asyncio
async def test_proxy_rate_limit_exceeded_returns_429():
    clock = FakeClock(1000.0)
    limiter = RateLimiter(rate=1.0, burst=2.0, time_func=clock)
    policy = Policy({"blocked_categories": ["malware"], "categories": {"malware": ["blocked.test"]}})
    set_policy(policy)
    set_rate_limiter(limiter)

    class MockWriter:
        def __init__(self):
            self.data = bytearray()
            self.closed = False

        def get_extra_info(self, name):
            return ("192.168.100.50", 54321)

        def write(self, b):
            self.data.extend(b)

        async def drain(self):
            pass

        def close(self):
            self.closed = True

        async def wait_closed(self):
            pass

    async def send_req():
        reader = asyncio.StreamReader()
        reader.feed_data(b"GET http://blocked.test/ HTTP/1.1\r\nHost: blocked.test\r\n\r\n")
        reader.feed_eof()
        writer = MockWriter()
        await handle_client_inner(reader, writer)
        return bytes(writer.data)

    try:
        # Request 1: allowed by rate limiter (returns 403 by policy, not 429)
        resp1 = await send_req()
        assert b"429 Too Many Requests" not in resp1
        assert b"403 Forbidden" in resp1

        # Request 2: allowed by rate limiter
        resp2 = await send_req()
        assert b"429 Too Many Requests" not in resp2
        assert b"403 Forbidden" in resp2

        # Request 3: burst of 2 exceeded -> 429 Too Many Requests with Retry-After header
        resp3 = await send_req()
        assert b"429 Too Many Requests" in resp3
        assert b"Retry-After:" in resp3
    finally:
        set_rate_limiter(None)
        set_policy(None)
