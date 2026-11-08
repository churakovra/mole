import aio_pika
import asyncio

async def consume(queue):
    async for message in queue.iterator():
        try:
            await asyncio.wait_for(handle(message), timeout=2)
            await message.ack()
        except Exception:
            await asyncio.sleep(1)
            await message.nack()
