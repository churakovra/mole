from repository import Store
from publisher import publish_order
from sqlalchemy.orm import Session
import aio_pika

async def execute(session: Session, exchange: aio_pika.Exchange):
    store = Store()
    order = store.save(session)
    await publish_order(exchange)
    return order
