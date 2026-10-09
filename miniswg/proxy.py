import asyncio
import logging
from miniswg.parser import parse_request, ParseError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    logger.info(f"New connection from {addr}")
    
    try:
        # Use our new robust parser
        req = await parse_request(reader)
        logger.info(f"Parsed valid request: {req.method} {req.target} (Body: {len(req.body)} bytes)")
        
        # Just sending a basic success response for now
        response = b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\nProxy Parser Success"
        writer.write(response)
        await writer.drain()
        
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
        await writer.wait_closed()

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
