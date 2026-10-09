import asyncio
import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)

MAX_HEADER_SIZE = 16384  # 16KB limit to protect against buffer overflows
READ_TIMEOUT = 10.0      # 10 seconds timeout for slow lorises

class ParseError(Exception):
    """Custom exception for HTTP parsing errors."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

@dataclass
class HTTPRequest:
    method: str
    target: str
    version: str
    headers: Dict[str, str]
    body: bytes

async def parse_request(reader: asyncio.StreamReader) -> HTTPRequest:
    """Reads from the stream and parses a full HTTP/1.1 request."""
    try:
        # 1. Read headers until the blank line (\r\n\r\n)
        header_data = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=READ_TIMEOUT)
    except asyncio.exceptions.LimitOverrunError:
        raise ParseError(431, "Request Header Fields Too Large")
    except asyncio.TimeoutError:
        raise ParseError(408, "Request Timeout")
    except asyncio.IncompleteReadError:
        raise ParseError(400, "Bad Request: Connection closed prematurely")
        
    if len(header_data) > MAX_HEADER_SIZE:
        raise ParseError(431, "Request Header Fields Too Large")

    # Decode and split into lines, ignoring trailing blank line
    lines = header_data.decode('utf-8', errors='ignore').strip('\r\n').split('\r\n')
    if not lines or not lines[0]:
        raise ParseError(400, "Bad Request: Empty request line")

    # 2. Parse the Request Line (e.g., "GET / HTTP/1.1")
    request_line = lines[0].split(' ')
    if len(request_line) != 3:
        raise ParseError(400, "Bad Request: Malformed request line")
    
    method, target, version = request_line
    
    # 3. Parse the Headers (case-insensitive keys)
    headers = {}
    for line in lines[1:]:
        if ':' not in line:
            raise ParseError(400, "Bad Request: Malformed header")
        key, value = line.split(':', 1)
        headers[key.strip().lower()] = value.strip()
        
    if 'host' not in headers and version == 'HTTP/1.1':
        raise ParseError(400, "Bad Request: Missing Host header")

    # 4. Parse the Body (if Content-Length exists)
    body = b""
    content_length = int(headers.get('content-length', 0))
    if content_length > 0:
        try:
            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=READ_TIMEOUT)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            raise ParseError(400, "Bad Request: Incomplete body")
            
    return HTTPRequest(method, target, version, headers, body)
