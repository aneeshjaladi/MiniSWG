import asyncio
import json
import os
import pytest
from miniswg.policy import Policy, load_policy
from miniswg.proxy import (
    set_policy,
    set_rate_limiter,
    reload_policy,
    handle_client_inner,
    make_html_block_page,
)
from miniswg.ratelimit import RateLimiter


class MockWriter:
    def __init__(self, ip: str = "127.0.0.1", port: int = 54321):
        self.ip = ip
        self.port = port
        self.data = bytearray()
        self.closed = False

    def get_extra_info(self, name):
        return (self.ip, self.port)

    def write(self, b):
        self.data.extend(b)

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


@pytest.mark.asyncio
async def test_blocked_http_returns_html_block_page():
    policy = load_policy("config/policy.json")
    set_policy(policy)
    set_rate_limiter(None)

    # evil.example is in category 'malware', which is blocked
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET / HTTP/1.1\r\nHost: evil.example\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter()

    try:
        await handle_client_inner(reader, writer)
        response = bytes(writer.data)

        # Confirm 403 Forbidden
        assert b"HTTP/1.1 403 Forbidden" in response
        assert b"Content-Type: text/html" in response

        # Confirm HTML page contains host and category
        assert b"evil.example" in response
        assert b"malware" in response
        assert b"<html>" in response.lower()
    finally:
        set_policy(None)


@pytest.mark.asyncio
async def test_blocked_connect_returns_403_no_tunnel():
    policy = load_policy("config/policy.json")
    set_policy(policy)
    set_rate_limiter(None)

    # *.casino.com is in category 'gambling', which is blocked
    reader = asyncio.StreamReader()
    reader.feed_data(b"CONNECT poker.casino.com:443 HTTP/1.1\r\nHost: poker.casino.com:443\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter()

    try:
        await handle_client_inner(reader, writer)
        response = bytes(writer.data)

        # Confirm 403 Forbidden and no 200 Connection Established
        assert b"HTTP/1.1 403 Forbidden" in response
        assert b"200 Connection Established" not in response
    finally:
        set_policy(None)


@pytest.mark.asyncio
async def test_access_log_updated_with_action_reason_and_category():
    policy = load_policy("config/policy.json")
    set_policy(policy)
    set_rate_limiter(None)

    log_path = "logs/access.log"

    # Capture log line position
    start_pos = os.path.getsize(log_path) if os.path.exists(log_path) else 0

    reader = asyncio.StreamReader()
    reader.feed_data(b"GET /login HTTP/1.1\r\nHost: evil.example\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter(ip="10.20.30.40")

    try:
        await handle_client_inner(reader, writer)

        # Read latest log entry
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            f.seek(start_pos)
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) >= 1
        entry = json.loads(lines[-1])

        # Verify action, reason, and category in access log
        assert entry["client_ip"] == "10.20.30.40"
        assert entry["action"] == "block"
        assert entry["reason"] == "blocked_category"
        assert entry["category"] == "malware"
        assert entry["status"] == 403
    finally:
        set_policy(None)


@pytest.mark.asyncio
async def test_access_log_records_rate_limited_action():
    set_policy(None)
    limiter = RateLimiter(rate=0.1, burst=1.0)
    set_rate_limiter(limiter)

    log_path = "logs/access.log"
    start_pos = os.path.getsize(log_path) if os.path.exists(log_path) else 0

    # Exhaust single token
    limiter.check("10.0.0.99")

    # Second connection exceeds rate limit
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter(ip="10.0.0.99")

    try:
        await handle_client_inner(reader, writer)
        assert b"429 Too Many Requests" in writer.data

        with open(log_path, "r", encoding="utf-8") as f:
            f.seek(start_pos)
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["action"] == "rate_limited"
        assert entry["reason"] == "rate_limit_exceeded"
        assert entry["status"] == 429
    finally:
        set_rate_limiter(None)


def test_reload_policy_without_restart(tmp_path):
    policy_file = tmp_path / "dynamic_policy.json"
    policy_file.write_text(json.dumps({
        "blocked_categories": ["malware"],
        "categories": {"malware": ["site1.com"]}
    }))

    # Initial load
    reload_policy(str(policy_file))
    from miniswg.proxy import get_policy
    pol1 = get_policy()
    assert pol1.evaluate("site1.com").action == "block"
    assert pol1.evaluate("site2.com").action == "allow"

    # Modify policy file
    policy_file.write_text(json.dumps({
        "blocked_categories": ["malware", "gambling"],
        "categories": {
            "malware": ["site1.com"],
            "gambling": ["site2.com"]
        }
    }))

    # Reload without restart
    success = reload_policy(str(policy_file))
    assert success is True

    pol2 = get_policy()
    assert pol2.evaluate("site1.com").action == "block"
    assert pol2.evaluate("site2.com").action == "block"
    assert pol2.evaluate("site2.com").category == "gambling"
