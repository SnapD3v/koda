import asyncio
from koda.api.kodik import KodikClient
from koda.config import load_config

async def main():
    config = load_config()
    async with KodikClient(config["token"]) as client:
        results = await client.search("наруто", limit=1)
        print("Результат:", results[0].title, results[0].link)
        url = await client.get_stream_url(results[0].link)
        print("Stream URL:", url)

asyncio.run(main())