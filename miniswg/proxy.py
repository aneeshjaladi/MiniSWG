import asyncio
import logging
import urllib.parse
import time
import json
import os
from datetime import datetime, timezone
from miniswg.parser import parse_request, ParseError

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

class ConnectionContext:
    def __init__(self, client_ip):
        self.client_ip = client_ip
        self.method = "-"
        self.host = "-"
        self.port = 0
        self.action = "allow"
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
        
        if req.method == 'CONNECT':
            await handle_connect(req, reader, writer, ctx)
            return
            
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
                
        if not host:
            raise ParseError(400, "Bad Request: No host in request")
            
        ctx.host = host
        ctx.port = port
        
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

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 8080)
    logger.info("MiniSWG Proxy listening on 127.0.0.1:8080... (Press Ctrl+C to stop)")
    
    async with server:
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            logger.info("Server shutdown initiated...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Graceful shutdown complete.")
