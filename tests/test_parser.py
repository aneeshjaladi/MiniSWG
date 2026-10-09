import asyncio
import pytest
from miniswg.parser import parse_request, ParseError

def make_reader(data: bytes) -> asyncio.StreamReader:
    """Helper to inject raw bytes into a fake network stream."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader

@pytest.mark.asyncio
async def test_normal_request():
    req_bytes = b"POST /submit HTTP/1.1\r\nHost: example.com\r\nContent-Length: 5\r\n\r\nHello"
    reader = make_reader(req_bytes)
    req = await parse_request(reader)
    
    assert req.method == "POST"
    assert req.target == "/submit"
    assert req.headers["host"] == "example.com"
    assert req.body == b"Hello"

@pytest.mark.asyncio
async def test_missing_host():
    # HTTP/1.1 requires a Host header
    req_bytes = b"GET / HTTP/1.1\r\n\r\n"
    reader = make_reader(req_bytes)
    
    with pytest.raises(ParseError) as exc_info:
        await parse_request(reader)
    
    assert exc_info.value.code == 400
    assert "Missing Host" in exc_info.value.message

@pytest.mark.asyncio
async def test_malformed_request_line():
    # Missing the HTTP version
    req_bytes = b"GET /somepath\r\nHost: example.com\r\n\r\n"
    reader = make_reader(req_bytes)
    
    with pytest.raises(ParseError) as exc_info:
        await parse_request(reader)
        
    assert exc_info.value.code == 400
    assert "Malformed request line" in exc_info.value.message

@pytest.mark.asyncio
async def test_oversized_headers():
    # Create a giant header > 16KB
    giant_header = b"X-Big-Header: " + b"A" * 17000 + b"\r\n"
    req_bytes = b"GET / HTTP/1.1\r\n" + giant_header + b"\r\n"
    reader = make_reader(req_bytes)
    
    with pytest.raises(ParseError) as exc_info:
        await parse_request(reader)
        
    assert exc_info.value.code == 431
