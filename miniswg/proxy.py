import asyncio
import logging
import urllib.parse
import time
import json
import os
import argparse
import math
import signal
from datetime import datetime, timezone
from miniswg.parser import parse_request, ParseError
from miniswg.policy import Policy, load_policy
from miniswg.ratelimit import RateLimiter
from miniswg.admin import handle_admin_request

# Set up logging
os.makedirs("logs", exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

access_logger = logging.getLogger("access")
access_logger.setLevel(logging.INFO)
access_handler = logging.FileHandler("logs/access.log")
access_handler.setFormatter(logging.Formatter("%(message)s"))
access_logger.addHandler(access_handler)
access_logger.propagate = False

CONCURRENCY_LIMIT = 1000
concurrency_semaphore = None
active_policy: Policy | None = None
active_rate_limiter: RateLimiter | None = None
active_policy_path: str = "config/policy.json"

def set_policy(policy: Policy | None) -> None:
    global active_policy, active_rate_limiter
    active_policy = policy
    if policy and policy.rate_limit:
        active_rate_limiter = RateLimiter.from_config(policy.rate_limit)

def get_policy() -> Policy | None:
    return active_policy

def set_rate_limiter(limiter: RateLimiter | None) -> None:
    global active_rate_limiter
    active_rate_limiter = limiter

def get_rate_limiter() -> RateLimiter | None:
    return active_rate_limiter

def reload_policy(policy_path: str | None = None) -> bool:
    global active_policy_path
    path = policy_path or active_policy_path
    if not os.path.exists(path):
        logger.warning(f"Cannot reload policy: file {path} not found")
        return False
    try:
        new_policy = load_policy(path)
        set_policy(new_policy)
        active_policy_path = path
        logger.info(f"Successfully reloaded policy from {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to reload policy from {path}: {e}")
        return False

def setup_sighup_handler():
    if hasattr(signal, "SIGHUP"):
        def _on_sighup(signum, frame):
            logger.info("Received SIGHUP, reloading policy...")
            reload_policy()
        signal.signal(signal.SIGHUP, _on_sighup)

async def policy_reload_watcher(policy_path: str, interval: float = 1.0):
    last_mtime = os.path.getmtime(policy_path) if os.path.exists(policy_path) else 0
    try:
        while True:
            await asyncio.sleep(interval)
            if os.path.exists(policy_path):
                current_mtime = os.path.getmtime(policy_path)
                if current_mtime > last_mtime:
                    last_mtime = current_mtime
                    logger.info(f"Policy file {policy_path} modified; reloading...")
                    reload_policy(policy_path)
    except asyncio.CancelledError:
        pass

def make_html_block_page(host: str, category: str) -> bytes:
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>403 Forbidden - Access Denied by MiniSWG</title>
    <style>
        body {{
            background: #0b0f19;
            color: #f3f4f6;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 1.5rem;
            box-sizing: border-box;
        }}
        .card {{
            background: rgba(18, 24, 38, 0.95);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 16px;
            padding: 2.5rem;
            max-width: 520px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6), 0 0 30px rgba(239, 68, 68, 0.15);
        }}
        .icon-wrap {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: rgba(239, 68, 68, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.25rem;
            border: 2px solid rgba(239, 68, 68, 0.4);
        }}
        .error-code {{
            display: inline-block;
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            padding: 0.3rem 0.8rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            letter-spacing: 0.05em;
        }}
        h1 {{
            font-size: 1.55rem;
            margin: 0 0 0.75rem;
            color: #ffffff;
        }}
        p {{
            color: #9ca3af;
            font-size: 0.92rem;
            line-height: 1.5;
            margin: 0 0 1.5rem;
        }}
        .details-box {{
            background: rgba(10, 14, 23, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 1rem;
            text-align: left;
            margin-bottom: 1.75rem;
            font-size: 0.88rem;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.35rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            color: #6b7280;
        }}
        .detail-value {{
            color: #e2e8f0;
            font-weight: 600;
            font-family: monospace;
        }}
        .badge-cat {{
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
        }}
        .footer-note {{
            font-size: 0.75rem;
            color: #4b5563;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon-wrap">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="#ef4444">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
        </div>
        <div class="error-code">HTTP 403 FORBIDDEN</div>
        <h1>403 Forbidden</h1>
        <p>Blocked by policy: access to <strong>{host}</strong> is denied.</p>
        
        <div class="details-box">
            <div class="detail-row">
                <span class="detail-label">Blocked Host:</span>
                <span class="detail-value">{host}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Threat Category:</span>
                <span class="detail-value"><span class="badge-cat">{category}</span></span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Enforced By:</span>
                <span class="detail-value">MiniSWG Gateway</span>
            </div>
        </div>
        
        <div class="footer-note">
            If you believe this site was blocked in error, contact your network administrator.
        </div>
    </div>
</body>
</html>"""
    return html.encode("utf-8")

class ConnectionContext:
    def __init__(self, client_ip):
        self.client_ip = client_ip
        self.method = "-"
        self.host = "-"
        self.port = 0
        self.action = "allow"
        self.reason = "-"
        self.category = "-"
        self.status = 0
        self.bytes_up = 0
        self.bytes_down = 0
        self.start_time = time.time()
        
    def add_up(self, count):
        self.bytes_up += count
        
    def add_down(self, count):
        self.bytes_down += count
        
    def log(self):
        latency_ms = int((time.time() - self.start_time) * 1000)
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "client_ip": self.client_ip,
            "method": self.method,
            "host": self.host,
            "port": self.port,
            "action": self.action,
            "reason": self.reason,
            "category": self.category,
            "status": self.status,
            "bytes_up": self.bytes_up,
            "bytes_down": self.bytes_down,
            "latency_ms": latency_ms
        }
        access_logger.info(json.dumps(log_entry))

async def relay_stream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, on_data=None):
    try:
        while True:
            data = await asyncio.wait_for(reader.read(8192), timeout=60.0)
            if not data:
                break
            if on_data:
                on_data(len(data))
            writer.write(data)
            await writer.drain()
    except (asyncio.TimeoutError, asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
        pass
    except Exception as e:
        logger.debug(f"Relay stream exception: {e}")

async def handle_connect(req, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, ctx: ConnectionContext):
    target = req.target
    if ':' in target:
        host, port_str = target.split(':', 1)
        port = int(port_str)
    else:
        host = target
        port = 443

    ctx.host = host
    ctx.port = port
    ctx.method = "CONNECT"

    if active_policy is not None:
        decision = active_policy.evaluate(host)
        ctx.reason = decision.reason
        ctx.category = decision.category or "-"
        if decision.action == "block":
            logger.warning(f"CONNECT blocked by policy for {host}: {decision.reason} ({decision.category})")
            ctx.action = "block"
            ctx.status = 403
            body = make_html_block_page(host, decision.category or "unknown")
            resp = (
                f"HTTP/1.1 403 Forbidden\r\n"
                f"Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n"
            ).encode("utf-8") + body
            writer.write(resp)
            ctx.add_down(len(resp))
            await writer.drain()
            return

    try:
        origin_reader, origin_writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10.0
        )
    except Exception as e:
        logger.error(f"Failed to connect to {host}:{port} for CONNECT: {e}")
        ctx.status = 502
        error_resp = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
        writer.write(error_resp)
        ctx.add_down(len(error_resp))
        await writer.drain()
        return

    success_resp = b"HTTP/1.1 200 Connection Established\r\n\r\n"
    writer.write(success_resp)
    ctx.add_down(len(success_resp))
    await writer.drain()
    ctx.status = 200

    task1 = asyncio.create_task(relay_stream(reader, origin_writer, ctx.add_up))
    task2 = asyncio.create_task(relay_stream(origin_reader, writer, ctx.add_down))
    
    try:
        done, pending = await asyncio.wait(
            [task1, task2],
            return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
    finally:
        origin_writer.close()
        try:
            await origin_writer.wait_closed()
        except Exception:
            pass

async def handle_client_inner(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    client_ip = addr[0] if addr else "unknown"
    ctx = ConnectionContext(client_ip)
    logger.info(f"New connection from {addr}")

    try:
        req = await parse_request(reader)
        ctx.method = req.method
        ctx.host = req.target
        logger.info(f"Parsed valid request: {req.method} {req.target} (Body: {len(req.body)} bytes)")

        # Admin Web Dashboard and API routes (never rate-limited)
        parsed_url = urllib.parse.urlparse(req.target)
        host = parsed_url.hostname
        port = parsed_url.port or 80
        if not host:
            host_header = req.headers.get('host', '')
            if ':' in host_header:
                host, port_str = host_header.split(':', 1)
                port = int(port_str)
            else:
                host = host_header

        is_local_host = host in ('127.0.0.1', 'localhost', '::1', 'miniswg.local')
        path_str = parsed_url.path or req.target
        if is_local_host and (path_str.startswith('/admin') or path_str.startswith('/api') or path_str.startswith('/blocked') or path_str == '/'):
            ctx.host = host or "127.0.0.1"
            ctx.port = port or 8080
            handled = await handle_admin_request(req, reader, writer, ctx, get_policy, reload_policy)
            if handled:
                return

        if active_rate_limiter is not None:
            allowed, retry_after = active_rate_limiter.check(client_ip)
            if not allowed:
                retry_secs = max(1, math.ceil(retry_after))
                logger.warning(f"Rate limit exceeded for {client_ip}. Retry-After: {retry_secs}s")
                ctx.action = "rate_limited"
                ctx.reason = "rate_limit_exceeded"
                ctx.category = "-"
                ctx.status = 429
                body = b"Too Many Requests\n"
                resp = (
                    f"HTTP/1.1 429 Too Many Requests\r\n"
                    f"Content-Type: text/plain\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Retry-After: {retry_secs}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode() + body
                writer.write(resp)
                ctx.add_down(len(resp))
                await writer.drain()
                return

        if req.method == 'CONNECT':
            await handle_connect(req, reader, writer, ctx)
            return

        if not host:
            raise ParseError(400, "Bad Request: No host in request")
            
        ctx.host = host
        ctx.port = port

        if active_policy is not None:
            decision = active_policy.evaluate(host)
            ctx.reason = decision.reason
            ctx.category = decision.category or "-"
            if decision.action == "block":
                logger.warning(f"HTTP request blocked by policy for {host}: {decision.reason} ({decision.category})")
                ctx.action = "block"
                ctx.status = 403
                body = make_html_block_page(host, decision.category or "unknown")
                resp = (
                    f"HTTP/1.1 403 Forbidden\r\n"
                    f"Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n"
                ).encode() + body
                writer.write(resp)
                ctx.add_down(len(resp))
                await writer.drain()
                return
        
        path = parsed_url.path or '/'
        if parsed_url.query:
            path += '?' + parsed_url.query
            
        try:
            origin_reader, origin_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            ctx.status = 504
            error_resp = b"HTTP/1.1 504 Gateway Timeout\r\n\r\n"
            writer.write(error_resp)
            ctx.add_down(len(error_resp))
            await writer.drain()
            return
        except Exception as e:
            logger.error(f"Failed to connect to origin {host}:{port}: {e}")
            ctx.status = 502
            error_resp = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
            writer.write(error_resp)
            ctx.add_down(len(error_resp))
            await writer.drain()
            return
            
        try:
            request_line = f"{req.method} {path} {req.version}\r\n".encode()
            
            hop_by_hop = {'proxy-connection', 'connection', 'keep-alive', 'te', 'trailer', 'upgrade', 'proxy-authorization'}
            
            headers_out = []
            for k, v in req.headers.items():
                if k not in hop_by_hop:
                    headers_out.append(f"{k.title()}: {v}\r\n".encode())
                    
            headers_out.append(b"Connection: close\r\n")
            
            origin_writer.write(request_line)
            ctx.add_up(len(request_line))
            for h in headers_out:
                origin_writer.write(h)
                ctx.add_up(len(h))
            origin_writer.write(b"\r\n")
            ctx.add_up(2)
            
            if req.body:
                origin_writer.write(req.body)
                ctx.add_up(len(req.body))
                
            await origin_writer.drain()
            
            ctx.status = 200
            
            while True:
                try:
                    data = await asyncio.wait_for(origin_reader.read(8192), timeout=10.0)
                    if not data:
                        break
                    ctx.add_down(len(data))
                    writer.write(data)
                    await writer.drain()
                except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
                    break
                except Exception as e:
                    logger.error(f"Error streaming response from {host}: {e}")
                    break
        finally:
            origin_writer.close()
            try:
                await origin_writer.wait_closed()
            except Exception:
                pass
        
    except ParseError as e:
        logger.warning(f"Parse error from {addr}: {e.code} {e.message}")
        ctx.status = e.code
        error_resp = f"HTTP/1.1 {e.code} {e.message}\r\nContent-Length: 0\r\n\r\n".encode()
        writer.write(error_resp)
        ctx.add_down(len(error_resp))
        try:
            await writer.drain()
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"Connection error with {addr}: {e}")
        ctx.status = 500
        
    finally:
        logger.info(f"Closing client connection with {addr}")
        ctx.log()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global concurrency_semaphore
    if concurrency_semaphore is None:
        concurrency_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        
    async with concurrency_semaphore:
        await handle_client_inner(reader, writer)

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="MiniSWG Proxy")
    parser.add_argument(
        "--policy",
        default="config/policy.json",
        help="Path to policy JSON file (default: config/policy.json)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--no-rate-limit",
        action="store_true",
        help="Disable rate limiting",
    )
    parser.add_argument(
        "--no-policy",
        action="store_true",
        help="Disable policy engine",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload policy file on modification",
    )
    return parser.parse_args(args)

async def main(args=None):
    parsed = parse_args(args)
    setup_sighup_handler()

    global active_policy_path
    active_policy_path = parsed.policy

    if parsed.no_policy:
        set_policy(None)
        logger.info("Policy engine disabled via --no-policy")
    elif os.path.exists(parsed.policy):
        reload_policy(parsed.policy)
    else:
        logger.warning(f"Policy file {parsed.policy} not found; running without policy")

    if parsed.no_rate_limit:
        set_rate_limiter(None)
        logger.info("Rate limiting disabled via --no-rate-limit")

    watcher_task = None
    if parsed.reload:
        watcher_task = asyncio.create_task(policy_reload_watcher(parsed.policy))
        logger.info(f"Auto-reload enabled for policy file: {parsed.policy}")

    server = await asyncio.start_server(handle_client, parsed.host, parsed.port, backlog=512)
    logger.info(f"MiniSWG Proxy listening on {parsed.host}:{parsed.port}... (Press Ctrl+C to stop)")
    
    async with server:
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            logger.info("Server shutdown initiated...")
        finally:
            if watcher_task:
                watcher_task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Graceful shutdown complete.")
