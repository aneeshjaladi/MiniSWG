import asyncio
import logging
import urllib.parse
from miniswg.parser import parse_request, ParseError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

async def relay_stream(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            data = await asyncio.wait_for(reader.read(8192), timeout=60.0)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except asyncio.TimeoutError:
        pass
    except Exception:
        pass

async def handle_connect(req, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    target = req.target
    if ':' in target:
        host, port_str = target.split(':', 1)
        port = int(port_str)
    else:
        host = target
        port = 443

    try:
        origin_reader, origin_writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10.0
        )
    except Exception as e:
        logger.error(f"Failed to connect to {host}:{port} for CONNECT: {e}")
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await writer.drain()
        return

    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await writer.drain()

    task1 = asyncio.create_task(relay_stream(reader, origin_writer))
    task2 = asyncio.create_task(relay_stream(origin_reader, writer))
    
    done, pending = await asyncio.wait(
        [task1, task2],
        return_when=asyncio.FIRST_COMPLETED
    )
    
    for t in pending:
        t.cancel()
        
    origin_writer.close()
    try:
        await origin_writer.wait_closed()
    except Exception:
        pass

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    logger.info(f"New connection from {addr}")
    
    try:
        # Use our new robust parser
        req = await parse_request(reader)
        logger.info(f"Parsed valid request: {req.method} {req.target} (Body: {len(req.body)} bytes)")
        
        if req.method == 'CONNECT':
            await handle_connect(req, reader, writer)
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
            
        path = parsed_url.path or '/'
        if parsed_url.query:
            path += '?' + parsed_url.query
            
        try:
            origin_reader, origin_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            writer.write(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
            await writer.drain()
            return
        except Exception as e:
            logger.error(f"Failed to connect to origin {host}:{port}: {e}")
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
            return
            
        request_line = f"{req.method} {path} {req.version}\r\n".encode()
        
        hop_by_hop = {'proxy-connection', 'connection', 'keep-alive', 'te', 'trailer', 'upgrade', 'proxy-authorization'}
        
        headers_out = []
        for k, v in req.headers.items():
            if k not in hop_by_hop:
                headers_out.append(f"{k.title()}: {v}\r\n".encode())
                
        headers_out.append(b"Connection: close\r\n")
        
        origin_writer.write(request_line)
        for h in headers_out:
            origin_writer.write(h)
        origin_writer.write(b"\r\n")
        
        if req.body:
            origin_writer.write(req.body)
            
        await origin_writer.drain()
        
        while True:
            try:
                data = await asyncio.wait_for(origin_reader.read(8192), timeout=10.0)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
            except asyncio.TimeoutError:
                break
            except Exception as e:
                logger.error(f"Error streaming response from {host}: {e}")
                break
                
        origin_writer.close()
        await origin_writer.wait_closed()
        
    except ParseError as e:
        logger.warning(f"Parse error from {addr}: {e.code} {e.message}")
        # Send proper HTTP error response back to the client
        error_resp = f"HTTP/1.1 {e.code} {e.message}\r\nContent-Length: 0\r\n\r\n"
        writer.write(error_resp.encode())
        await writer.drain()
        
    except Exception as e:
        logger.error(f"Connection error with {addr}: {e}")
        
    finally:
        logger.info(f"Closing client connection with {addr}")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

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
