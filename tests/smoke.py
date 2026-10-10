import asyncio
import sys

async def fetch_one(i):
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 8080)
        req = f"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n"
        writer.write(req.encode())
        await writer.drain()
        
        response = b""
        while True:
            data = await reader.read(4096)
            if not data:
                break
            response += data
            
        writer.close()
        await writer.wait_closed()
        
        if b"200 OK" in response:
            return True
        else:
            print(f"Request {i} failed with response: {response[:100]}")
            return False
    except Exception as e:
        print(f"Exception on request {i}: {e}")
        return False

async def main():
    print("Sending 50 concurrent requests...")
    tasks = [asyncio.create_task(fetch_one(i)) for i in range(50)]
    results = await asyncio.gather(*tasks)
    success_count = sum(results)
    print(f"Success: {success_count}/50")
    if success_count != 50:
        sys.exit(1)
    print("All requests succeeded.")

if __name__ == "__main__":
    asyncio.run(main())
