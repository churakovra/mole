import aio_pika

async def publish_order(exchange: aio_pika.Exchange):
    await exchange.publish(message, routing_key='orders')
