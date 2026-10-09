import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    logger.info(f"New connection from {addr}")
    
    try:
        # Loop to continuously read and echo data until the client disconnects
        while True:
            data = await reader.read(4096)
            if not data:
                break # Client disconnected
            
            logger.info(f"Received {len(data)} bytes, echoing back.")
            writer.write(data)
            await writer.drain() # Ensure data is sent over the network
            
    except Exception as e:
        logger.error(f"Connection error with {addr}: {e}")
    finally:
        logger.info(f"Closing connection with {addr}")
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
        # Graceful shutdown on Ctrl+C (KeyboardInterrupt)
        logger.info("Graceful shutdown complete.")
