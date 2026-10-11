"""Per-client-IP TokenBucket rate limiter for MiniSWG."""

import math
import time
from typing import Callable, Any


class TokenBucket:
    """Token bucket for rate limiting a single client.

    Tokens refill lazily upon each check based on elapsed monotonic time.
    """

    def __init__(
        self,
        rate: float,
        capacity: float,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate = float(rate)  # tokens refilled per second
        self.capacity = float(capacity)  # maximum bucket capacity (burst)
        self.tokens = float(capacity)  # starts full
        self.time_func = time_func
        self.last_refill = self.time_func()
        self.last_access = self.last_refill

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        if elapsed > 0:
            # Bucket cap: tokens can never exceed capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

    def consume(self, tokens: float = 1.0, now: float | None = None) -> tuple[bool, float]:
        """Attempt to consume tokens.

        Returns:
            (allowed: bool, retry_after: float)
            where retry_after is the number of seconds until enough tokens are available.
        """
        if now is None:
            now = self.time_func()
        self.last_access = now
        self._refill(now)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0

        needed = tokens - self.tokens
        retry_after = needed / self.rate if self.rate > 0 else 1.0
        return False, retry_after


class RateLimiter:
    """Per-client-IP TokenBucket rate limiter.

    Features:
    - Lazy token refills on each check (no background threads)
    - Lazy cleanup of idle buckets to prevent memory leaks
    - Configurable rate and burst capacity
    - Pluggable time_func for deterministic testing with a fake clock
    """

    def __init__(
        self,
        rate: float = 2.0,  # tokens per second (120 req/min)
        burst: float = 20.0,  # max burst capacity
        idle_timeout: float = 300.0,  # seconds before idle bucket is pruned (5 mins)
        time_func: Callable[[], float] = time.monotonic,
        cleanup_interval: float = 60.0,  # how often to trigger lazy cleanup
    ) -> None:
        self.rate = float(rate)
        self.burst = float(burst)
        self.idle_timeout = float(idle_timeout)
        self.time_func = time_func
        self.cleanup_interval = float(cleanup_interval)
        self.buckets: dict[str, TokenBucket] = {}
        self.last_cleanup = self.time_func()

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        time_func: Callable[[], float] = time.monotonic,
    ) -> "RateLimiter":
        """Initialize RateLimiter from a rate_limit dictionary (e.g. from policy.json)."""
        requests_per_minute = config.get("requests_per_minute", 120)
        burst = config.get("burst", 20)
        rate = (requests_per_minute / 60.0) if requests_per_minute > 0 else 2.0
        return cls(rate=rate, burst=burst, time_func=time_func)

    def _maybe_cleanup(self, now: float) -> None:
        if now - self.last_cleanup >= self.cleanup_interval:
            self.cleanup(now=now)

    def cleanup(self, idle_timeout: float | None = None, now: float | None = None) -> int:
        """Prune client buckets that have not been accessed within idle_timeout.

        Returns count of pruned buckets.
        """
        if now is None:
            now = self.time_func()
        if idle_timeout is None:
            idle_timeout = self.idle_timeout

        to_remove = [
            ip for ip, bucket in self.buckets.items()
            if now - bucket.last_access >= idle_timeout
        ]
        for ip in to_remove:
            del self.buckets[ip]

        self.last_cleanup = now
        return len(to_remove)

    def check(
        self,
        client_ip: str,
        tokens: float = 1.0,
        now: float | None = None,
    ) -> tuple[bool, float]:
        """Check if client_ip has enough tokens and consumes them.

        Returns:
            (allowed: bool, retry_after: float)
        """
        if now is None:
            now = self.time_func()

        self._maybe_cleanup(now)

        if client_ip not in self.buckets:
            self.buckets[client_ip] = TokenBucket(
                rate=self.rate,
                capacity=self.burst,
                time_func=self.time_func,
            )

        return self.buckets[client_ip].consume(tokens=tokens, now=now)

    def is_allowed(self, client_ip: str, tokens: float = 1.0) -> bool:
        """Convenience method returning True if allowed, False otherwise."""
        allowed, _ = self.check(client_ip, tokens=tokens)
        return allowed

    def __contains__(self, client_ip: str) -> bool:
        return client_ip in self.buckets

    def __len__(self) -> int:
        return len(self.buckets)

    def __bool__(self) -> bool:
        return True
