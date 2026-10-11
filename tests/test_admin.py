import asyncio
import json
import os
import pytest
from miniswg.policy import load_policy
from miniswg.proxy import (
    set_policy,
    handle_client_inner,
    reload_policy,
)


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
async def test_admin_dashboard_serves_html():
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET /admin HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter()

    await handle_client_inner(reader, writer)
    resp = bytes(writer.data)

    assert b"HTTP/1.1 200 OK" in resp
    assert b"Content-Type: text/html" in resp
    assert b"MiniSWG Admin" in resp
    assert b"<!DOCTYPE html>" in resp


@pytest.mark.asyncio
async def test_admin_api_status():
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET /api/status HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter()

    await handle_client_inner(reader, writer)
    resp = bytes(writer.data)

    assert b"HTTP/1.1 200 OK" in resp
    assert b"application/json" in resp
    body_part = resp.split(b"\r\n\r\n", 1)[1]
    data = json.loads(body_part.decode("utf-8"))
    assert data["status"] == "online"
    assert "uptime_seconds" in data
    assert "windows_proxy_enabled" in data


@pytest.mark.asyncio
async def test_admin_api_test_domain():
    policy = load_policy("config/policy.json")
    set_policy(policy)

    try:
        # 1. Test blocked domain
        reader1 = asyncio.StreamReader()
        reader1.feed_data(b"GET /api/test-domain?domain=evil.example HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n\r\n")
        reader1.feed_eof()
        writer1 = MockWriter()

        await handle_client_inner(reader1, writer1)
        resp1 = bytes(writer1.data)
        assert b"HTTP/1.1 200 OK" in resp1
        body1 = json.loads(resp1.split(b"\r\n\r\n", 1)[1].decode("utf-8"))
        assert body1["domain"] == "evil.example"
        assert body1["action"] == "block"
        assert body1["category"] == "malware"

        # 2. Test allowed domain
        reader2 = asyncio.StreamReader()
        reader2.feed_data(b"GET /api/test-domain?domain=google.com HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n\r\n")
        reader2.feed_eof()
        writer2 = MockWriter()

        await handle_client_inner(reader2, writer2)
        resp2 = bytes(writer2.data)
        assert b"HTTP/1.1 200 OK" in resp2
        body2 = json.loads(resp2.split(b"\r\n\r\n", 1)[1].decode("utf-8"))
        assert body2["domain"] == "google.com"
        assert body2["action"] == "allow"
    finally:
        set_policy(None)


@pytest.mark.asyncio
async def test_admin_api_policy_crud(tmp_path):
    policy = load_policy("config/policy.json")
    set_policy(policy)

    try:
        # GET policy
        reader = asyncio.StreamReader()
        reader.feed_data(b"GET /api/policy HTTP/1.1\r\nHost: 127.0.0.1:8080\r\n\r\n")
        reader.feed_eof()
        writer = MockWriter()

        await handle_client_inner(reader, writer)
        resp = bytes(writer.data)
        assert b"HTTP/1.1 200 OK" in resp
        body = json.loads(resp.split(b"\r\n\r\n", 1)[1].decode("utf-8"))
        assert "blocked_categories" in body
        assert "categories" in body
    finally:
        set_policy(None)
