import aio_pika

async def handle_order(message):
    try:
        await message.ack()
    except Exception:
        await message.nack()

async def register(channel: aio_pika.Channel):
    queue = await channel.declare_queue('orders')
    await queue.consume(handle_order)
